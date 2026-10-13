"""（2026-10-13 自 cueupload/cueparse 搬入，兩邊修改請同步）
Ragic 寫入層——唯一會「改動」Ragic 的模組（建立／上傳附件／刪除）。

其餘模組全是唯讀。把寫入集中在此，方便審計與加安全閘。

Ragic 寫入 API（官方文件）：
  建立：POST  {SERVER}/{ACCOUNT}/<form>?api&v=3   JSON body {欄位ID: 值}
        多值欄＝陣列；子表＝{"_subtable_<容器ID>": {"-1": {欄ID: 值}}}
        旗標 doLinkLoad/doFormula/doDefaultValue（連動/公式/預設值）
  附件：POST  {SERVER}/{ACCOUNT}/<form>/<rid>     multipart/form-data
        -F "<欄位ID>=@檔案" -F "api=" -F "v=3"      回 "<欄位ID>": "hash@檔名"
  刪除：DELETE {SERVER}/{ACCOUNT}/<form>/<rid>     -d "api"（只刪 URL 內那一個 rid）

🚨 安全鐵則：刪除只允許刪「本次執行剛建立、且我們記在 _CREATED_THIS_RUN 的 rid」，
   永不接受搜尋/批次刪除，避免動到既有正式資料。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import requests

from ragic_booking.fields import (
    FORM_CUE_APPLY,
    FORM_CUSTOMER,
    FORM_ORDER,
    OrderDraft,
    WRITE_FLAGS,
    _headers,
    cue_apply_payload_json,
    customer_payload_json,
    form_url,
    order_form_tuples,
    order_payload_json,
)

_TIMEOUT = 90

# 本次程式執行期間「我們親手建立」的紀錄 rid，(form, rid) 形式。刪除安全閘的白名單。
_CREATED_THIS_RUN: set[tuple[str, str]] = set()


class RagicWriteError(RuntimeError):
    """寫入層失敗（連線／HTTP／回傳無法解析）。"""


@dataclass
class WriteResult:
    ok: bool
    form: str
    rid: str = ""
    cue_id: str = ""              # 建立 CUE 申請後 Ragic 生成的真實 CUE 號
    raw: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    @property
    def url(self) -> str:
        """人可點的紀錄網址（非 API）。"""
        return form_url(self.form, self.rid) if self.rid else ""


# ---------------------------------------------------------------- 低階 HTTP
def _flags_qs(flags: dict[str, str] | None) -> str:
    fl = WRITE_FLAGS if flags is None else flags
    parts = ["api", "v=3"] + [f"{k}={v}" for k, v in fl.items()]
    return "&".join(parts)


def _parse_create_response(raw: Any) -> tuple[bool, str, str]:
    """容錯解析 Ragic 建立回傳 → (ok, rid, error)。

    已知成功形狀：{"status":"SUCCESS","ragicId":123,"data":{...}}；
    失敗：status 非 SUCCESS，訊息在 msg/validation。也擋非 dict 回傳。
    """
    if not isinstance(raw, dict):
        return False, "", f"非預期回傳：{str(raw)[:200]}"

    status = str(raw.get("status", "")).upper()
    rid = raw.get("ragicId") or raw.get("_ragicId") or raw.get("id") or ""

    # rid 有時只出現在 data 的鍵（記錄以 rid 為 key）
    if not rid:
        data = raw.get("data")
        if isinstance(data, dict):
            for k in data:
                if str(k).isdigit():
                    rid = k
                    break
    rid = str(rid) if rid not in (None, "") else ""

    if status and status != "SUCCESS":
        msg = raw.get("msg") or raw.get("validation") or raw.get("error") or raw
        return False, rid, f"Ragic 拒絕（status={status}）：{str(msg)[:300]}"

    # 沒有明確 status 但拿到 rid，視為成功（不同版本回傳略異）
    ok = (status == "SUCCESS") or bool(rid)
    if not ok:
        return False, "", f"無法判定成功且無 rid：{str(raw)[:200]}"
    return True, rid, ""


def create_record(form: str, payload_json: dict[str, Any],
                  flags: dict[str, str] | None = None) -> WriteResult:
    """建立一筆新紀錄（JSON body）。成功即把 rid 登記進本次執行白名單。"""
    url = f"{form_url(form)}?{_flags_qs(flags)}"
    try:
        resp = requests.post(url, json=payload_json, headers=_headers(),
                             timeout=_TIMEOUT)
    except requests.RequestException as e:
        return WriteResult(ok=False, form=form, error=f"連線 Ragic 失敗：{e}")
    if resp.status_code != 200:
        return WriteResult(ok=False, form=form,
                           error=f"HTTP {resp.status_code}：{resp.text[:300]}")
    try:
        raw = resp.json()
    except ValueError:
        return WriteResult(ok=False, form=form,
                           error=f"回傳非 JSON：{resp.text[:300]}")

    ok, rid, err = _parse_create_response(raw)
    if ok and rid:
        _CREATED_THIS_RUN.add((form, rid))
    return WriteResult(ok=ok, form=form, rid=rid,
                       raw=raw if isinstance(raw, dict) else {}, error=err)


def create_record_with_files(form: str, form_fields: list[tuple[str, str]],
                             files_map: dict[str, str],
                             flags: dict[str, str] | None = None) -> WriteResult:
    """一次 multipart POST 建立紀錄＋帶附件（欄位ID=值 的重複鍵 + 檔案欄ID=@檔）。

    為什麼需要：Ragic 對『訂檔CUE表／客戶回簽檔』等附件欄設為必填，會在**建檔當下**
    就檢查非空；先 JSON 建檔、後補附件的順序會被 status=INVALID 擋下。這裡把附件併進
    create 的同一個 multipart 請求，讓必填驗證在建檔當下即通過。

    成功即把 rid 登記進本次執行白名單（與 create_record 一致）。
    """
    import os
    from contextlib import ExitStack

    url = f"{form_url(form)}?{_flags_qs(flags)}"
    data = list(form_fields) + [("api", ""), ("v", "3")]
    try:
        with ExitStack() as stack:
            files = {}
            for field_id, path in (files_map or {}).items():
                if not path:
                    continue
                fh = stack.enter_context(open(path, "rb"))
                files[field_id] = (os.path.basename(path), fh)
            resp = requests.post(url, data=data, files=files or None,
                                 headers=_headers(), timeout=_TIMEOUT)
    except (requests.RequestException, OSError) as e:
        return WriteResult(ok=False, form=form, error=f"建檔(含附件)連線失敗：{e}")
    if resp.status_code != 200:
        return WriteResult(ok=False, form=form,
                           error=f"HTTP {resp.status_code}：{resp.text[:300]}")
    try:
        raw = resp.json()
    except ValueError:
        return WriteResult(ok=False, form=form,
                           error=f"回傳非 JSON：{resp.text[:300]}")
    ok, rid, err = _parse_create_response(raw)
    if ok and rid:
        _CREATED_THIS_RUN.add((form, rid))
    return WriteResult(ok=ok, form=form, rid=rid,
                       raw=raw if isinstance(raw, dict) else {}, error=err)


def read_record(form: str, rid: str) -> dict[str, Any]:
    """讀單筆（v3 具名欄位）。回傳內層欄位 dict（拆掉 {rid: {...}} 外層）。"""
    if not str(rid).strip():
        return {}
    url = f"{form_url(form, str(rid))}?api&v=3"
    try:
        resp = requests.get(url, headers=_headers(), timeout=_TIMEOUT)
    except requests.RequestException as e:
        raise RagicWriteError(f"讀取 Ragic 失敗：{e}") from e
    if resp.status_code != 200:
        raise RagicWriteError(f"讀取 HTTP {resp.status_code}：{resp.text[:200]}")
    try:
        data = resp.json()
    except ValueError as e:
        raise RagicWriteError(f"讀取回傳非 JSON：{resp.text[:200]}") from e
    if not isinstance(data, dict):
        return {}
    inner = data.get(str(rid))
    return inner if isinstance(inner, dict) else data


def upload_file(form: str, rid: str, field_id: str, filepath: str,
                filename: str | None = None) -> WriteResult:
    """把單一檔案上傳到某紀錄的檔案欄（multipart）。紀錄須已存在。"""
    if not str(rid).strip():
        return WriteResult(ok=False, form=form, error="上傳缺 rid（紀錄尚未建立）")
    url = f"{form_url(form, str(rid))}?api&v=3"
    import os
    fname = filename or os.path.basename(filepath)
    try:
        with open(filepath, "rb") as fh:
            resp = requests.post(
                url,
                headers=_headers(),
                data={"api": "", "v": "3"},
                files={field_id: (fname, fh)},
                timeout=_TIMEOUT,
            )
    except (requests.RequestException, OSError) as e:
        return WriteResult(ok=False, form=form, rid=str(rid),
                           error=f"附件上傳失敗：{e}")
    if resp.status_code != 200:
        return WriteResult(ok=False, form=form, rid=str(rid),
                           error=f"附件 HTTP {resp.status_code}：{resp.text[:200]}")
    try:
        raw = resp.json()
    except ValueError:
        raw = {"_text": resp.text[:200]}
    return WriteResult(ok=True, form=form, rid=str(rid),
                       raw=raw if isinstance(raw, dict) else {})


def delete_record(form: str, rid: str) -> WriteResult:
    """刪除單筆紀錄。🚨 只允許刪本次執行親手建立、已在白名單的 rid。

    這是全專案唯一的刪除入口，刻意不提供任何搜尋/批次刪除路徑，
    確保永遠不會動到既有正式資料。
    """
    rid = str(rid).strip()
    if not rid.isdigit():
        raise RagicWriteError(f"拒絕刪除：rid 必須是純數字，收到 {rid!r}")
    if (form, rid) not in _CREATED_THIS_RUN:
        raise RagicWriteError(
            f"拒絕刪除：{form}/{rid} 不在『本次執行親手建立』白名單，"
            f"為保護既有資料，只允許刪除本程式剛建立的紀錄。")

    url = f"{form_url(form, rid)}?api&v=3"
    try:
        resp = requests.delete(url, headers=_headers(),
                               data={"api": ""}, timeout=_TIMEOUT)
    except requests.RequestException as e:
        return WriteResult(ok=False, form=form, rid=rid,
                           error=f"刪除連線失敗：{e}")
    if resp.status_code != 200:
        return WriteResult(ok=False, form=form, rid=rid,
                           error=f"刪除 HTTP {resp.status_code}：{resp.text[:200]}")
    _CREATED_THIS_RUN.discard((form, rid))
    try:
        raw = resp.json()
    except ValueError:
        raw = {"_text": resp.text[:200]}
    return WriteResult(ok=True, form=form, rid=rid,
                       raw=raw if isinstance(raw, dict) else {})


# ---------------------------------------------------------------- 高階編排
def create_customer(customer_draft) -> WriteResult:
    """建立新客戶主檔，成功回傳含 rid 的結果（客戶編號 C013xx 需另讀回）。"""
    return create_record(FORM_CUSTOMER, customer_payload_json(customer_draft))


def _extract_cue_id(form: str, rid: str, create_raw: dict[str, Any]) -> str:
    """CUE 申請建立後取 Ragic 生成的真實 CUE 號：先看建立回傳，再讀回補強。"""
    from ragic_booking.fields import CueApplyF

    def scan(d: dict[str, Any]) -> str:
        for key in ("CUE號", CueApplyF.CUE號):
            v = d.get(key)
            if v:
                return str(v).strip()
        return ""

    # 建立回傳裡的 data
    data = create_raw.get("data") if isinstance(create_raw, dict) else None
    if isinstance(data, dict):
        inner = data.get(str(rid))
        if isinstance(inner, dict):
            got = scan(inner)
            if got:
                return got
        got = scan(data)
        if got:
            return got
    # 讀回
    try:
        return scan(read_record(form, rid))
    except RagicWriteError:
        return ""


def _find_leaked_order_rid(order: OrderDraft, within_sec: int = 300) -> str:
    """建檔回 ERROR 時，回搜『可能已建立卻沒回 rid』的殘留訂檔（best-effort，純讀取）。

    Ragic 的建檔後 Post-workflow 若崩潰，會出現「記錄已存在、API 卻回 status=ERROR
    且不給 ragicId」的情況。以 產品名稱＋電台播證開立名稱＋近 within_sec 秒 為簽名，
    在最近紀錄中找最新一筆相符者的 rid。找不到回空字串。
    """
    import time

    prod = str(order.產品名稱 or "").strip()
    cert = str(order.電台播證開立名稱 or "").strip()
    if not prod:
        return ""
    url = f"{form_url(FORM_ORDER)}?api&v=3&limit=20"
    try:
        resp = requests.get(url, headers=_headers(), timeout=_TIMEOUT)
        data = resp.json()
    except (requests.RequestException, ValueError):
        return ""
    if not isinstance(data, dict):
        return ""
    now_ms = time.time() * 1000.0
    best_rid, best_ts = "", -1.0
    for rid, r in data.items():
        if not isinstance(r, dict):
            continue
        if str(r.get("產品名稱", "")).strip() != prod:
            continue
        if cert and str(r.get("電台播證開立名稱", "")).strip() != cert:
            continue
        ts = float(r.get("_dataTimestamp") or 0)
        if now_ms - ts > within_sec * 1000:   # 只認近期，避免誤抓同名舊單
            continue
        if ts > best_ts:
            best_ts, best_rid = ts, str(rid)
    return best_rid


def submit_full_order(order: OrderDraft, *, apply_cue: bool,
                      起走日期: str = "", 總波段: str = "1",
                      申請人: str = "", 產品名稱: str = "",
                      attachments: dict[str, str] | None = None) -> dict[str, Any]:
    """端到端送出：（申請 CUE 號 →）建立訂檔 → 上傳附件。

    任一步失敗即停，回傳已完成步驟與已建立 rid（含孤兒 CUE 申請 rid），
    不 raise，讓 UI 呈現並可對『剛建立的 rid』做清理。

    attachments：{欄位ID: 檔案路徑}，於訂檔建立後逐一上傳。
    回傳：{ok, steps:[{name, ok, form, rid, url, error}], cue_id, order_rid, error}
    """
    steps: list[dict[str, Any]] = []

    def record(name: str, r: WriteResult) -> None:
        steps.append({"name": name, "ok": r.ok, "form": r.form, "rid": r.rid,
                      "url": r.url, "error": r.error})

    # 1) 申請 CUE 號（若需要且尚未有）
    cue_id = order.CUE號
    if apply_cue and not order.CUE號:
        cr = create_record(
            FORM_CUE_APPLY,
            cue_apply_payload_json(order.客戶編號, 起走日期, 總波段, 申請人, 產品名稱),
        )
        record("申請CUE號", cr)
        if not cr.ok:
            return {"ok": False, "steps": steps, "cue_id": "", "order_rid": "",
                    "leaked_rid": "", "error": f"CUE 號申請失敗：{cr.error}"}
        cue_id = _extract_cue_id(FORM_CUE_APPLY, cr.rid, cr.raw)
        steps[-1]["cue_id"] = cue_id
        order.CUE號 = cue_id

    # 2) 建立訂檔
    #    Ragic 對訂檔CUE表/客戶回簽檔等附件欄設為必填，會在建檔當下就驗證非空；
    #    因此有附件時走 multipart「一次建檔＋帶附件」，避免先建後補被 INVALID 擋下。
    files = {fid: p for fid, p in (attachments or {}).items() if p}
    if files:
        order_res = create_record_with_files(
            FORM_ORDER, order_form_tuples(order), files)
        record("建立訂檔(含附件)", order_res)
    else:
        # 無附件：走既有 JSON 建檔（子表/多值以 JSON 原生格式送）
        order_res = create_record(FORM_ORDER, order_payload_json(order))
        record("建立訂檔", order_res)

    if not order_res.ok:
        # 保險：Ragic 的建檔後 Post-workflow 出錯時，可能「已建好記錄卻回 ERROR、不給 rid」，
        # 造成半殘記錄留在正式庫。回搜近期同簽名記錄，找到就登記白名單讓 UI 能一鍵清除。
        leaked = _find_leaked_order_rid(order)
        if leaked:
            _CREATED_THIS_RUN.add((FORM_ORDER, leaked))
        return {"ok": False, "steps": steps, "cue_id": cue_id, "order_rid": "",
                "leaked_rid": leaked,
                "error": f"訂檔建立失敗：{order_res.error}"
                + (f"（⚠️ 偵測到可能殘留 rid={leaked}，請用『清除殘留』刪掉）" if leaked else "")}
    return {"ok": True, "steps": steps, "cue_id": cue_id,
            "order_rid": order_res.rid, "leaked_rid": "", "error": ""}
