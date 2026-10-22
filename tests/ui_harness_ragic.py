# -*- coding: utf-8 -*-
"""AppTest 用的 app 外殼：Ragic 存檔改成記憶體假資料庫（不連真 Ragic），PDF 轉檔改假檔、st.pills 退回 radio。
由 tests/test_ui_ragic_flow.py 以 AppTest.from_file 載入，不是測試本身。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import streamlit as st  # noqa: E402


def _no_pills(*a, **k):   # AppTest 對 st.pills 的 format_func 支援有問題，改走程式內建的 radio 後備
    raise AttributeError("pills disabled in AppTest")


st.pills = _no_pills

import pdf_converter  # noqa: E402
import simple_preview  # noqa: E402

simple_preview.has_soffice = lambda: False
pdf_converter.xlsx_bytes_to_pdf_bytes = lambda b, *a, **k: (b"%PDF-fake", "fake", "")

import data_loader  # noqa: E402

# Google 設定表讀取常逾時（10-21／22 多次整批 skip）→ 測試專用磁碟快取：讀到就存，讀不到就用快取（正式 app 不受影響）
_GS_CACHE = os.path.join(ROOT, "tests", "_gsheet_cache")
_orig_read_csv_url = data_loader._read_csv_url


def _cached_read_csv_url(url, timeout=20):
    import hashlib

    import pandas as pd
    path = os.path.join(_GS_CACHE, hashlib.md5(url.encode()).hexdigest() + ".pkl")
    try:
        df = _orig_read_csv_url(url, timeout=timeout)
        os.makedirs(_GS_CACHE, exist_ok=True)
        df.to_pickle(path)
        return df
    except Exception:
        if os.path.exists(path):
            return pd.read_pickle(path)
        raise


data_loader._read_csv_url = _cached_read_csv_url
import cue_store  # noqa: E402
import ragic_ui  # noqa: E402
from ragic_booking import cue2  # noqa: E402

ragic_ui.write_enabled = lambda: True
ragic_ui._options = lambda field_name: []   # 客服等下拉選項不連 Ragic
ragic_ui._order_opts = lambda field_name: []
ragic_ui._search = lambda q: list(st.session_state.get("_fake_customers", []))   # 客戶搜尋改假資料
from ragic_booking import fields as _rf  # noqa: E402

_rf.notify_defaults = lambda limit=60: _rf.NOTIFY_FALLBACK


def _fake_save(url, key, fields, files=None, rid=None):
    db = st.session_state.setdefault("_fake_db", {})
    rid = rid or str(100 + len(db))
    old = db.get(rid, {})
    db[rid] = dict(old, **fields, _ragicId=rid, **{"1015306": "S" + rid})
    for fid, f in (files or {}).items():   # 真 Ragic 附件欄存「hash@檔名」
        db[rid][fid] = f"h@{f[0]}"
    st.session_state.setdefault("_fake_files", {})[rid] = {k: (v[0], len(v[1] or b"")) for k, v in (files or {}).items()}
    st.session_state["_fake_last_files"] = files or {}
    return cue2.SaveResult(True, rid=rid, serial="S" + rid)


def _fake_list(url, key, keyword="", limit=200):
    return [dict(v) for v in st.session_state.get("_fake_db", {}).values()]


cue2.save_record = _fake_save
cue2.list_records = _fake_list
cue2.list_all = lambda url, key, **k: _fake_list(url, key)
cue2.get_record = lambda url, key, rid: st.session_state.get("_fake_db", {}).get(str(rid))
cue2.download_file = lambda url, key, v: b"%PDF-signback"


# AppTest 無法操作 file_uploader：session 有 _fake_sign 時，「客戶回簽檔」回傳假檔
class _FakeUpload:
    name = "回簽.pdf"

    def getvalue(self):
        return b"%PDF-signback"


_orig_uploader = st.file_uploader


def _uploader(label, *a, key=None, **k):
    if key and str(key).endswith("_od_sign") and st.session_state.get("_fake_sign"):
        return _FakeUpload()
    return _orig_uploader(label, *a, key=key, **k)


st.file_uploader = _uploader

# 訂檔寫入改假的：記錄呼叫，回傳 CUE號／訂檔 rid
from ragic_booking import order_from_cue as oc  # noqa: E402

ragic_ui.booking_enabled = lambda: bool(st.session_state.get("_fake_booking_on", True))


def _fake_submit_booking(snap, orders, *, applicant="", attachments=None, submit=None, serial=""):
    st.session_state.setdefault("_fake_booking_calls", []).append(("submit", len(orders), sorted((attachments or {}).get("all", {}))))
    return {"ok": True, "cue_id": "1160101", "results": [], "error": "",
            "orders": [{"wave": i + 1, "rid": str(500 + i), "action": "新增"} for i in range(len(orders))]}


def _fake_update_booking(snap, orders, *, booking, attachments=None, applicant="", **k):
    st.session_state.setdefault("_fake_booking_calls", []).append(("update", booking["cue_id"], [o["rid"] for o in booking["orders"]]))
    return {"ok": True, "cue_id": booking["cue_id"], "error": "",
            "orders": [{"wave": o["wave"], "rid": o["rid"], "action": "更新"} for o in booking["orders"]]}


def _fake_apply_cue(snap, *, applicant="", serial="", **k):
    st.session_state["_fake_booking_serial"] = serial
    st.session_state.setdefault("_fake_booking_calls", []).append(("apply", serial))
    cust = snap.get("customer") or {}
    return {"ok": True, "error": "", "warning": "",
            "cue_apply": {"cue_id": "1160101", "rid": "9", "客戶編號": cust.get("編號", ""), "客戶名稱": cust.get("名稱", ""),
                          "產品名稱": "產品乙", "業務": cust.get("業務", ""), "主管": cust.get("主管", "")}}


oc.apply_cue = _fake_apply_cue
oc.submit_booking = _fake_submit_booking
oc.update_booking = _fake_update_booking
ragic_ui._list_saved = lambda url, key, kw: [(r, cue_store.parse_snapshot(cue2.details_of(r))) for r in _fake_list(url, key)]
st.session_state.setdefault("ragic_url", "https://example.invalid/cue/2")
st.session_state.setdefault("ragic_key", "fake")

import app  # noqa: E402

app.main()
