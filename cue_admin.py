# -*- coding: utf-8 -*-
"""
CUE 管理與統計（Ragic 串接第 5 期）。規格：docs/specs/Ragic串接_第5期_存檔編號與統計.md

- 📁 CUE 管理：業務看自己的存檔；營運主管／管理員依業務分資料夾看全部。可開啟（編輯／營運加贈）、
  選一份存檔直接送出訂檔（附回簽檔，CUE Excel 取存檔時附在 Ragic 的檔案）；
  主管預設看「待審」，選一份直接核准／退回（每份送出的訂檔都要審）。
- 📊 統計：依存檔編號年月，每位業務出 CUE 張數、成交張數、成交率、成交實收。
"""
from datetime import date

import streamlit as st

import cue_registry as reg
import cue_store as cs
import ragic_ui

STATUS_FILTER = ["全部", "待審", "未成交", "成交", "退回"]


def _need_login():
    if not ragic_ui.current_user():
        st.info("請先在左側以 Ragic 帳號登入。")
        return True
    url, key = ragic_ui._ragic_conn()
    if not (url and key):
        st.info("尚未設定 Ragic 連線。")
        return True
    return False


def _load():
    url, key = ragic_ui._ragic_conn()
    try:
        return ragic_ui.all_saved(url, key)
    except Exception as e:  # noqa: BLE001
        st.error(f"讀取 Ragic 失敗：{e}")
        return []


def _visible(items):
    """主管看全部；業務只看自己存的（存檔人信箱）。"""
    u = ragic_ui.current_user() or {}
    if ragic_ui.is_reviewer():
        return items
    return [(r, s) for r, s in items if reg.owner_of(s).get("email") == u.get("email")]


def _date(v):
    v = cs.from_jsonable(v)
    return v.strftime("%Y/%m/%d") if isinstance(v, date) else ""


def _row(rec, snap):
    h = snap.get("header", {})
    last = (snap.get("history") or [{}])[-1]
    return {
        "編號": reg.display_no(snap) or f"#{rec['_ragicId']}",
        "客戶": h.get("client") or "",
        "產品": h.get("product") or "",
        "模式": snap.get("mode") or "",
        "走期": f"{_date(h.get('start'))}～{_date(h.get('end'))}",
        "實收": reg.net_total(snap),
        "狀態": cs.status_of(snap),
        "審核": cs.audit_of(snap),
        "CUE號": (snap.get("booking") or {}).get("cue_id", ""),
        "版本": snap.get("version"),
        "最後修改": f"{last.get('at', '')} {last.get('by', '')}",
        "標記": "🎁營運加贈" if snap.get("ops") else "",
    }


def _status_ok(snap, flt):
    if flt == "待審":
        return cs.audit_of(snap) == cs.AUDIT_PENDING
    if flt == "成交":
        return reg.is_deal(snap)
    if flt == "退回":
        return cs.status_of(snap) == cs.REJECTED
    if flt == "未成交":
        return not reg.is_deal(snap) and cs.status_of(snap) != cs.REJECTED
    return True


def render_manage():
    st.title("📁 CUE 管理")
    if st.session_state.get("adm_msg"):
        st.success(st.session_state.pop("adm_msg"))
    if _need_login():
        return
    items = _visible(_load())
    reviewer = ragic_ui.is_reviewer()
    if reviewer:
        # 資料夾：依業務分
        owners = {}
        for r, s in items:
            o = reg.owner_of(s)
            owners.setdefault(o.get("name") or "（舊存檔／無存檔人）", []).append((r, s))
        names = ["全部業務"] + sorted(owners, key=lambda n: -len(owners[n]))
        folder = st.radio("業務資料夾", names, horizontal=True, key="adm_folder",
                          format_func=lambda n: f"📁 {n}（{len(items) if n == '全部業務' else len(owners[n])}）")
        if folder != "全部業務":
            items = owners[folder]
    else:
        st.caption("這裡列出你存過的 CUE；營運主管可看到所有業務的資料夾。")
    c1, c2 = st.columns([1, 2])
    flt = c1.selectbox("狀態", STATUS_FILTER, key="adm_status", index=1 if reviewer else 0)
    kw = c2.text_input("搜尋（編號、客戶、產品、CUE號）", key="adm_kw").strip()
    rows = []
    for r, s in items:
        if not _status_ok(s, flt):
            continue
        row = _row(r, s)
        if kw and not any(kw in str(v) for v in row.values()):
            continue
        rows.append((r, s, row))
    if not rows:
        st.caption("沒有符合的存檔。")
        return
    st.dataframe([x[2] for x in rows], hide_index=True, use_container_width=True,
                 column_config={"實收": st.column_config.NumberColumn(format="$%d")})
    idx = st.selectbox("選一份", range(len(rows)), key="adm_pick",
                       format_func=lambda i: f"{rows[i][2]['編號']}｜{rows[i][2]['客戶']} {rows[i][2]['產品']}｜{rows[i][2]['狀態']}")
    rec, snap, _row_d = rows[idx]
    with st.expander("異動紀錄", expanded=False):
        for h in reversed(snap.get("history", [])):
            st.caption(f"v{h['v']}｜{h['at']}｜{h['by']}：" + "；".join(h.get("changes", [])))
    if reviewer and cs.audit_of(snap) == cs.AUDIT_PENDING:
        _audit_box(rec, snap)
    b1, _b2 = st.columns(2)
    if b1.button("📂 開啟（編輯／加贈）", key="adm_open", type="primary"):
        ragic_ui.open_record(rec, snap)
    if not reg.is_deal(snap) or cs.status_of(snap) == cs.BOOKED_CHANGED:
        _submit_box(rec, snap)


def _audit_box(rec, snap):
    """主管審核待審的訂檔：看 CUE Excel／回簽檔後核准或退回，不用開啟 CUE。"""
    from config import RAGIC_MAP
    from ragic_booking import cue2
    st.markdown("#### 🗂 主管審核（待審）")
    bk = snap.get("booking") or {}
    rv = snap.get("review") or {}
    st.caption(f"CUE號 {bk.get('cue_id', '')}｜送出 {bk.get('at', '')} {bk.get('by', '')}｜"
               f"訂檔 {len(bk.get('orders') or [])} 筆｜回簽檔 {rv.get('signback') or '—'}")
    url, key = ragic_ui._ragic_conn()
    files = {"CUE Excel": RAGIC_MAP["file_xls"], "CUE PDF": RAGIC_MAP["file_pdf"], "客戶回簽檔": ragic_ui.SIGNBACK_FIELD}
    cache = st.session_state.setdefault("adm_au_files", {})
    ck = (rec["_ragicId"], snap.get("version"))
    if ck not in cache:
        if st.button("📎 載入附件（CUE、回簽檔）", key="adm_au_load"):
            got = []
            for label, fid in files.items():
                val = rec.get(fid)
                val = val[0] if isinstance(val, list) and val else val
                data = cue2.download_file(url, key, val) if val else None
                if data:
                    got.append((label, val.split("@", 1)[-1], data))
            cache[ck] = got
            st.rerun()
    else:
        cols = st.columns(max(1, len(cache[ck])))
        for i, (label, name, data) in enumerate(cache[ck]):
            cols[i].download_button(f"⬇️ {label}", data, file_name=name, key=f"adm_au_dl_{i}")
        if not cache[ck]:
            st.caption("這筆沒有附件。")

    def save(new):
        legacy = cs.legacy_part(cue2.details_of(rec))
        return cue2.save_record(url, key, {RAGIC_MAP["details"]: cs.details_text(new, legacy)}, rid=rec["_ragicId"])

    if ragic_ui.render_audit_box(snap, save, "adm"):
        ragic_ui.all_saved.clear()
        st.session_state["adm_msg"] = f"✅ {reg.display_no(snap) or '#' + str(rec['_ragicId'])} 已完成審核"
        st.rerun()


def _submit_box(rec, snap):
    """選一份存檔直接送出訂檔：補訂檔資料＋上傳回簽檔（CUE Excel 用存檔時附在 Ragic 的檔案）。"""
    from config import RAGIC_MAP
    from ragic_booking import cue2
    st.markdown("#### 📨 送出訂檔")
    od = ragic_ui.render_order_preview(snap, "adm", prev_review=snap.get("review"), update=bool(snap.get("booking")),
                                       bind_session=False)
    has_sign = bool(od["signback"] or (snap.get("review") or {}).get("signback"))
    block = ([] if ragic_ui.write_enabled() else ["乾跑模式"]) \
        + ([] if ragic_ui.booking_enabled() else ["訂檔寫入未開放（RAGIC_BOOKING_ENABLED）"]) \
        + od["missing"] + ([] if has_sign else ["客戶回簽檔"])
    label = "📨 送出更新訂檔" if snap.get("booking") else "📨 送出訂檔（成交）"
    if not st.button(label, key="adm_submit", disabled=bool(block),
                     help=("尚缺：" + "、".join(block)) if block else "立即申請 CUE號並建立各波訂檔，算成交。"):
        return
    url, key = ragic_ui._ragic_conn()
    val = rec.get(RAGIC_MAP["file_xls"])
    val = val[0] if isinstance(val, list) and val else val
    xl = cue2.download_file(url, key, val) if val else None
    if not xl:
        st.error("找不到這份存檔的 CUE Excel，請先開啟並重新存檔一次。")
        return
    files_d = {"xlsx": (val.split("@", 1)[-1], xl)}
    u = ragic_ui.current_user() or {}
    final = ragic_ui.json_copy(snap)
    from config import RAGIC_FIELD_SERIAL
    res = ragic_ui._book(final, od, files_d, rid=rec["_ragicId"], serial=str(rec.get(RAGIC_FIELD_SERIAL) or ""))
    if not res.get("ok"):
        st.error(f"送出訂檔失敗：{res.get('error')}")
        return
    cs.mark_booked(final, u.get("name", ""), od["params"], {"cue_id": res.get("cue_id", ""),
                                                             "orders": res.get("orders", []),
                                                             "at": ragic_ui.datetime_now(), "by": u.get("name", "")})
    up = {}
    if od["signback"]:
        final["review"]["signback"] = od["signback"].name
        up[ragic_ui.SIGNBACK_FIELD] = (od["signback"].name, od["signback"].getvalue(), "application/octet-stream")
    legacy = cs.legacy_part(cue2.details_of(rec))
    sres = cue2.save_record(url, key, {RAGIC_MAP["details"]: cs.details_text(final, legacy)}, up, rid=rec["_ragicId"])
    if not sres.ok:
        st.error(f"訂檔已建立（CUE號 {final['booking'].get('cue_id')}），但回寫存檔失敗：{sres.error}，請通知 Jonathan。")
        return
    ragic_ui.all_saved.clear()
    st.session_state["adm_msg"] = f"✅ {reg.display_no(final)} 已送出訂檔：CUE號 {final['booking'].get('cue_id')}"
    st.rerun()


def render_stats():
    st.title("📊 CUE 統計")
    if _need_login():
        return
    items = _visible(_load())
    snaps = [s for _r, s in items]
    years = sorted({2000 + p[1] for p in (reg.parse_no(s.get("save_no")) for s in snaps) if p} | {date.today().year},
                   reverse=True)
    c1, c2 = st.columns([1, 3])
    year = c1.selectbox("年度", years, key="stat_year")
    months = c2.multiselect("月份（不選＝全年）", list(range(1, 13)), format_func=lambda m: f"{m}月", key="stat_months")
    data = reg.stats(snaps, year=year, months=set(months) or None)
    if not data:
        st.caption("這段期間沒有存檔紀錄（統計只算新程式存檔、有編號的 CUE）。")
        return
    table = [{"業務": n, "代碼": d["code"], "出 CUE 張數": d["saved"], "成交張數": d["deals"],
              "成交率": f"{d['rate']:.0%}", "成交實收": d["deal_net"]}
             for n, d in sorted(data.items(), key=lambda kv: -kv[1]["saved"])]
    tot_s = sum(d["saved"] for d in data.values())
    tot_d = sum(d["deals"] for d in data.values())
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("出 CUE 張數", f"{tot_s:,}")
    m2.metric("成交張數", f"{tot_d:,}")
    m3.metric("成交率", f"{(tot_d / tot_s if tot_s else 0):.0%}")
    m4.metric("成交實收", f"${sum(d['deal_net'] for d in data.values()):,}")
    st.dataframe(table, hide_index=True, use_container_width=True,
                 column_config={"成交實收": st.column_config.NumberColumn(format="$%d")})
    st.caption("出 CUE 張數＝依存檔編號年月計算的存檔數（同一份改版本不重複計）；成交＝已送出訂檔（退回不算）。")
    conflicts = reg.code_conflicts(snaps)
    if conflicts:
        st.warning("以下業務代碼重複，編號會混在一起，請在 Secrets 的 RAGIC_SALES_CODES 為其中一位指定代碼："
                   + "；".join(f"{c}：{'、'.join(n)}" for c, n in conflicts.items()))
