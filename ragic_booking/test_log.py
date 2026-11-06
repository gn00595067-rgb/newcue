"""測試期 CUE號／訂檔紀錄（Ragic cue/6「CUE系統訂檔測試」）與每月申請上限。

業務試用期間，程式申請的 CUE號、建立的訂檔都視為測試：
- 每申請一個 CUE號 → cue/6 新增一列（CUE號）；
- 送出訂檔後 → 把訂檔單號回填到同一列（沒有該列就新增，例如沿用已申請的 CUE號）；
- 本月（台北時間，依紀錄建立時間）cue/6 已有 N 列就擋住再申請（Ragic CUE號每月上限 99，測試只用 15）。
spec：docs/specs/測試期CUE號上限.md
"""
from __future__ import annotations

import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Any

from ragic_booking.fields import _get_json, form_url

FORM_TEST_LOG = "cue/6"
TEST_MARK = "【newcue 系統測試】"
DEFAULT_LIMIT = 15
_TPE = timezone(timedelta(hours=8))


class LogF:
    訂檔單號 = "1016200"
    CUE號 = "1016201"


def _now():
    return datetime.now(_TPE)


def _month_of(rec: dict[str, Any]) -> tuple[int, int] | None:
    ts = rec.get("_dataTimestamp")
    try:
        d = datetime.fromtimestamp(float(ts) / 1000.0, _TPE)
    except (TypeError, ValueError):
        return None
    return d.year, d.month


def list_rows(getter=None, limit: int = 1000) -> dict[str, dict[str, Any]]:
    getter = getter or _get_json
    data = getter(f"{form_url(FORM_TEST_LOG)}?api&v=3&limit={limit}") or {}
    return {str(k): v for k, v in data.items() if isinstance(v, dict)}


def month_count(rows: dict[str, dict[str, Any]], now: datetime | None = None) -> int:
    """本月建立的列數；讀不到建立時間的列也算（寧可多算、不要超用）。"""
    now = now or _now()
    ym = (now.year, now.month)
    return sum(1 for r in rows.values() if _month_of(r) in (ym, None))


def count_this_month(getter=None, now=None) -> int:
    return month_count(list_rows(getter), now)


def quota_block(limit: int, getter=None, now=None) -> str:
    """達上限回提示文字；未達回空字串。"""
    n = count_this_month(getter, now)
    if n >= limit:
        return f"本月測試申請 CUE號已達 {limit} 筆上限（目前 {n} 筆），下個月才能再申請；急用請找 Jonathan。"
    return ""


def _find_row(cue_id: str, getter=None) -> tuple[str, dict[str, Any]] | None:
    getter = getter or _get_json
    data = getter(f"{form_url(FORM_TEST_LOG)}?api&v=3&where={LogF.CUE號},eq,{urllib.parse.quote(cue_id)}") or {}
    for rid, rec in data.items():
        if isinstance(rec, dict) and str(rec.get("CUE號", "")).strip() == cue_id:
            return str(rid), rec
    return None


def log_cue(cue_id: str, creator=None):
    """申請到 CUE號後記一列。回傳 WriteResult。"""
    if creator is None:
        from ragic_booking.write import create_record as creator
    return creator(FORM_TEST_LOG, {LogF.CUE號: str(cue_id)})


def merge_order_nos(old: str, new: list[str]) -> str:
    parts = [x.strip() for x in str(old or "").replace("，", "、").replace(",", "、").split("、") if x.strip()]
    for n in new:
        if n and n not in parts:
            parts.append(n)
    return "、".join(parts)


def log_orders(cue_id: str, order_nos: list[str], getter=None, creator=None, updater=None):
    """訂檔單號回填到該 CUE號 那一列（多波以「、」串接、不重複）；沒有那列就新增。回傳 WriteResult。"""
    if creator is None or updater is None:
        from ragic_booking import write as rw
        creator = creator or rw.create_record
        updater = updater or rw.update_record
    cue_id = str(cue_id or "").strip()
    found = _find_row(cue_id, getter)
    if found:
        rid, rec = found
        return updater(FORM_TEST_LOG, rid, {LogF.訂檔單號: merge_order_nos(rec.get("訂檔單號", ""), order_nos)})
    return creator(FORM_TEST_LOG, {LogF.CUE號: cue_id, LogF.訂檔單號: merge_order_nos("", order_nos)})


def mark_need(text: str) -> str:
    """訂檔「需求或狀況說明」前加測試標記（已有就不重加）。"""
    text = str(text or "")
    return text if text.startswith(TEST_MARK) else TEST_MARK + text
