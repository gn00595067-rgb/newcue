"""cue/2（CUE 存檔表）讀寫：新建／更新同一筆（版本）、讀回、列表。第 2 期。

寫入一律走 multipart（欄位＋附件同一請求），帶 doLinkLoad／doFormula 讓「客戶編號(成交)」連動帶出客戶欄位。
網址／金鑰沿用 app 的 ragic_url／ragic_key（主管可在側欄改）。不 import streamlit。
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import requests

from config import RAGIC_FIELD_SERIAL, RAGIC_MAP

_TIMEOUT = 120
_FLAGS = {"doLinkLoad": "true", "doFormula": "true"}


@dataclass
class SaveResult:
    ok: bool
    rid: str = ""
    serial: str = ""
    error: str = ""


def _base(url):
    return url.split("?")[0].rstrip("/")


def _hdr(key):
    return {"Authorization": f"Basic {key}"}


def _multi_data(fields):
    """{id: 值或 list} → multipart 欄位清單（多值欄重複 key）。"""
    data = []
    for k, v in fields.items():
        if isinstance(v, (list, tuple)):
            data.extend((k, str(x)) for x in v)
        elif v is not None:
            data.append((k, str(v)))
    return data


def save_record(url, key, fields, files=None, rid=None):
    """rid 為空＝新建；有值＝更新該筆。files：{欄位ID: (檔名, bytes, mime)}。"""
    if not url or not key:
        return SaveResult(False, error="未設定 Ragic 網址或金鑰")
    target = f"{_base(url)}/{rid}" if rid else _base(url)
    params = {"api": "", "v": "3", **_FLAGS}
    try:
        resp = requests.post(target, params=params, headers=_hdr(key), data=_multi_data(fields),
                             files=files or None, timeout=_TIMEOUT)
    except requests.RequestException as e:
        return SaveResult(False, error=f"連線 Ragic 失敗：{e}")
    if resp.status_code != 200:
        return SaveResult(False, error=f"HTTP {resp.status_code}：{resp.text[:200]}")
    try:
        j = resp.json()
    except ValueError:
        return SaveResult(False, error=f"Ragic 回傳非 JSON：{resp.text[:200]}")
    if str(j.get("status", "")).upper() != "SUCCESS":
        return SaveResult(False, error=f"Ragic 拒絕：{j.get('msg') or j}")
    new_rid = str(j.get("ragicId") or rid or "")
    return SaveResult(True, rid=new_rid, serial=_read_serial(url, key, new_rid))


def _read_serial(url, key, rid, tries=3):
    """讀回 Cue表模擬編號（Ragic 自動編號需一點時間）。"""
    for i in range(tries):
        rec = get_record(url, key, rid)
        if rec and rec.get(RAGIC_FIELD_SERIAL):
            return str(rec[RAGIC_FIELD_SERIAL])
        time.sleep(1.5 if i < tries - 1 else 0)
    return ""


def get_record(url, key, rid):
    """單筆（欄位 ID 為鍵）；失敗回 None。"""
    try:
        resp = requests.get(f"{_base(url)}/{rid}", params={"api": "", "v": "3", "naming": "EID"},
                            headers=_hdr(key), timeout=30)
        j = resp.json() if resp.status_code == 200 else None
    except (requests.RequestException, ValueError):
        return None
    if isinstance(j, dict) and str(rid) in j and isinstance(j[str(rid)], dict):
        j = j[str(rid)]
    if isinstance(j, dict):
        j["_ragicId"] = str(rid)
    return j


def list_records(url, key, keyword="", limit=200):
    """最近的紀錄（新到舊），欄位 ID 為鍵；keyword 走全文檢索。"""
    params = {"api": "", "v": "3", "naming": "EID", "limit": limit}
    if keyword:
        params["fts"] = keyword
    resp = requests.get(_base(url), params=params, headers=_hdr(key), timeout=60)
    resp.raise_for_status()
    data = resp.json() or {}
    out = []
    for rid, row in data.items():
        if isinstance(row, dict):
            row["_ragicId"] = str(rid)
            out.append(row)
    out.sort(key=lambda r: int(r["_ragicId"]) if r["_ragicId"].isdigit() else 0, reverse=True)
    return out


def details_of(rec):
    return (rec or {}).get(RAGIC_MAP["details"], "") or ""
