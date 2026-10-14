# -*- coding: utf-8 -*-
"""
Ragic 串接的共用畫面（第 1 期：Ragic 帳號登入、客戶帶入、新增客戶）。
規格：docs/specs/Ragic串接_訂檔流程.md

寫入安全：新增客戶預設「乾跑」只顯示將送出的內容；Secrets 設 RAGIC_WRITE_ENABLED = "true"
才真的寫入 Ragic 客戶表。
"""
import os
import tempfile

import streamlit as st

from config import _secret
from ragic_booking import auth
from ragic_booking import fields as rf

SS_USER = "ragic_user"           # 登入者 {"email","name","groups"}
SS_CUSTOMER = "ragic_customer"   # 目前帶入的客戶 {"編號","名稱","統編","產品","類別","現折","退佣",...}


def write_enabled():
    return str(_secret("RAGIC_WRITE_ENABLED", "")).strip().lower() in ("1", "true", "yes")


def current_user():
    return st.session_state.get(SS_USER)


# =============================================================================
# 登入（側欄）
# =============================================================================
def render_login_sidebar():
    st.header("👤 Ragic 帳號")
    u = current_user()
    if u:
        st.success(f"✅ {u['name']}")
        with st.expander("帳號資訊", expanded=False):
            st.caption(u["email"])
            st.caption("群組：" + ("、".join(u["groups"]) or "（無）"))
        if st.button("登出 Ragic", key="ragic_logout"):
            st.session_state.pop(SS_USER, None)
            st.session_state.pop(SS_CUSTOMER, None)
            st.rerun()
        return
    with st.form("ragic_login_form", clear_on_submit=False):
        email = st.text_input("公司信箱", key="ragic_login_email")
        pwd = st.text_input("Ragic 密碼", type="password", key="ragic_login_pwd")
        ok = st.form_submit_button("登入")
    st.caption("用 Ragic 的帳號密碼登入，才能從 Ragic 帶入客戶資料。")
    if ok:
        try:
            user = auth.ragic_login(email, pwd)
        except auth.RagicAuthError as e:
            st.error(str(e))
            return
        st.session_state[SS_USER] = {"email": user.email, "name": user.name, "groups": user.groups}
        st.session_state.pop("ragic_login_pwd", None)
        st.rerun()


# =============================================================================
# 客戶帶入
# =============================================================================
@st.cache_data(ttl=300, show_spinner=False)
def _search(query):
    return [_cust_dict(c) for c in rf.search_customers(query, limit=30)]


def _cust_dict(c):
    return {"rid": c.rid, "編號": c.編號, "名稱": c.名稱, "統編": c.統編, "產品": c.產品,
            "類別": c.類別, "業務": c.業務, "主管": c.主管, "客服": list(c.客服), "付款條件": c.付款條件,
            "現折": c.現折pct, "退佣": c.退佣pct}


def _cust_label(c):
    parts = [c["編號"], c["名稱"]]
    if c["產品"]:
        parts.append(f"／{c['產品']}")
    if c["統編"]:
        parts.append(f"（{c['統編']}）")
    return " ".join(p for p in parts if p)


def _apply(c, targets):
    """把客戶資料寫進該模式的輸入欄。targets：{"client"|"tax"|"product": session key}。"""
    vals = {"client": c["名稱"], "tax": c["統編"], "product": c["產品"]}
    for f, key in targets.items():
        if key and vals.get(f) is not None:
            st.session_state[key] = vals[f]
    st.session_state[SS_CUSTOMER] = c


def customer_picker(targets, key_prefix):
    """「從 Ragic 帶入客戶」區塊，放在客戶名稱欄位之上。
    targets：{"client": key, "tax": key, "product": key}，值為該模式輸入欄的 session key
    （一般CUE 傳 temp_* 預設值 key）。未登入時只顯示提示。"""
    sel = st.session_state.get(SS_CUSTOMER)
    title = f"🔗 Ragic 客戶：{sel['編號']} {sel['名稱']}" if sel else "🔎 從 Ragic 帶入客戶"
    with st.expander(title, expanded=False):
        if not current_user():
            st.caption("請先在左側以 Ragic 帳號登入。")
            return
        if sel:
            st.caption(f"客戶編號 {sel['編號']}｜{sel['類別'] or '—'}｜統編 {sel['統編'] or '—'}｜"
                       f"現折 {sel['現折'] or '—'}％｜退佣 {sel['退佣'] or '—'}％｜付款 {sel['付款條件'] or '—'}")
            if st.button("取消帶入", key=f"{key_prefix}_cust_clear"):
                st.session_state.pop(SS_CUSTOMER, None)
                st.rerun()
        q = st.text_input("輸入統一編號、客戶名稱或客戶編號", key=f"{key_prefix}_cust_q")
        if not q.strip():
            return
        try:
            found = _search(q.strip())
        except Exception as e:  # noqa: BLE001
            st.error(f"查詢 Ragic 失敗：{e}")
            return
        if not found:
            st.info("查無此客戶，可在下方「新增客戶」。")
            return
        idx = st.selectbox(f"找到 {len(found)} 筆（同客戶不同產品會分開列）", range(len(found)),
                           format_func=lambda i: _cust_label(found[i]), key=f"{key_prefix}_cust_pick")
        if st.button("帶入這個客戶", key=f"{key_prefix}_cust_apply", type="primary"):
            _apply(found[idx], targets)
            st.rerun()


# =============================================================================
# 新增客戶
# =============================================================================
@st.cache_data(ttl=3600, show_spinner=False)
def _options(field_name):
    try:
        return rf.customer_field_options(field_name)
    except Exception:  # noqa: BLE001
        return []


def _multi(label, opts, key, default=None):
    return st.multiselect(label, opts, default=[d for d in (default or []) if d in opts], key=key,
                          accept_new_options=True) if opts else \
        [x.strip() for x in st.text_input(label + "（多個以、分隔）", key=key).split("、") if x.strip()]


def _pick(label, opts, key, default=""):
    if opts:
        all_opts = [""] + opts + ([default] if default and default not in opts else [])
        idx = all_opts.index(default) if default in all_opts else 0
        return st.selectbox(label, all_opts, index=idx, key=key, accept_new_options=True)
    return st.text_input(label, default, key=key)


def render_new_customer(key_prefix="newcust"):
    """新增成交客戶（Ragic forms13/3）。必填齊才能送；未開啟寫入時只乾跑顯示內容。"""
    u = current_user()
    with st.expander("➕ 新增客戶到 Ragic", expanded=False):
        if not u:
            st.caption("請先在左側以 Ragic 帳號登入。")
            return
        d = rf.CustomerDraft()
        k = lambda s: f"{key_prefix}_{s}"
        c1, c2 = st.columns(2)
        with c1:
            d.客戶名稱 = st.text_input("客戶名稱 *", key=k("name"))
            d.統一編號 = st.text_input("統一編號 *", key=k("tax"))
            d.產品名稱 = st.text_input("產品名稱 *", key=k("product"))
            d.客戶類別 = st.selectbox("客戶類別 *", rf.CUSTOMER_CATEGORY_OPTIONS, key=k("cat"))
            d.產業別 = _pick("產業別 *", _options("產業別"), k("industry"))
            d.初次託播金額 = st.text_input("初次託播金額（含稅）*", key=k("amount"))
        with c2:
            d.業務 = _pick("業務 *", _options("業務"), k("sales"), default=u["name"])
            d.主管 = _pick("主管", _options("主管"), k("manager"))
            d.客服 = _multi("客服 *", _options("客服"), k("cs"))
            d.付款條件 = _pick("付款條件 *", rf.PAYMENT_TERM_OPTIONS, k("terms"))
            d.付款方式 = _multi("付款方式 *", rf.PAYMENT_METHOD_OPTIONS, k("paymethod"))
            pc1, pc2 = st.columns(2)
            d.現折pct = pc1.text_input("現折 %", key=k("disc"))
            d.退佣pct = pc2.text_input("退佣 %", "0", key=k("rebate"))
        c3, c4 = st.columns(2)
        with c3:
            d.承辦人 = st.text_input("承辦人（客戶窗口）*", key=k("contact"))
            d.職稱 = st.text_input("職稱", key=k("title"))
            d.專線分機 = st.text_input("專線分機 *", key=k("phone"))
            d.電子郵件 = st.text_input("電子郵件", key=k("email"))
        with c4:
            d.帳款聯絡人 = st.text_input("帳款聯絡人 *", key=k("ar"))
            d.通訊地址 = st.text_input("通訊地址 *", key=k("addr"))
            dc1, dc2 = st.columns(2)
            _close = dc1.date_input("每月結帳日 *", value=None, key=k("close"))
            _bill = dc2.date_input("每月請款日 *", value=None, key=k("bill"))
            d.每月結帳日 = _close.strftime("%Y/%m/%d") if _close else ""
            d.每月請款日 = _bill.strftime("%Y/%m/%d") if _bill else ""
        d.客戶重要注意事項 = st.text_input("客戶重要注意事項 *", "無", key=k("note"))
        biz = st.file_uploader("工商登記公示資料（PDF）*", type=["pdf"], key=k("biz"))

        miss = rf.missing_required_customer(d)["blocking"]
        if not biz:
            miss.append("工商登記公示資料（上傳 PDF）")
        if miss:
            st.warning("尚缺必填：" + "、".join(m.split("（")[0] for m in miss))

        live = write_enabled()
        with st.popover("👀 預覽將寫入 Ragic 的內容"):
            st.json({"表單": rf.FORM_CUSTOMER, "欄位": rf.customer_payload_json(d),
                     "附件": biz.name if biz else None})
        if not live:
            st.info("目前為**乾跑模式**：只預覽、不會寫入 Ragic（管理者在 Secrets 設 RAGIC_WRITE_ENABLED 後才會正式寫入）。")
        if st.button("送出新增客戶", key=k("submit"), type="primary", disabled=bool(miss) or not live):
            _submit_customer(d, biz)


def _submit_customer(d, biz):
    from ragic_booking import write as rw
    tuples = rf.customer_form_tuples(d)
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, biz.name)
        with open(path, "wb") as f:
            f.write(biz.getvalue())
        res = rw.create_record_with_files(rf.FORM_CUSTOMER, tuples, {rf.CustomerWriteF.工商登記公示資料: path})
    if not res.ok:
        st.error(f"新增失敗：{res.error}")
        return
    st.success(f"已新增客戶（Ragic 紀錄 {res.rid}）。客戶編號由 Ragic 自動產生，可用上方搜尋帶入。")
    st.cache_data.clear()


# =============================================================================
# 第 2 期：CUE 存檔（新建／更新版本）與「我的 CUE」讀回
# =============================================================================
SS_RECORD = "cue_record"
NAV_KEY = "_nav_cue_mode"   # 開啟存檔後要切換到的製作模式（app 在畫「製作模式」前套用）   # 目前編輯中的 Ragic 存檔 {"rid","serial","mode","snap"}

# 快照 mode → (製作模式 radio 值, 代理商子模式)
MODE_NAV = {
    "簡易模式": ("簡易模式", None),
    "一般CUE": ("一般CUE", None),
    "年約季約細CUE": ("年約季約細CUE", None),
    "專案CUE": ("專案CUE", None),
    "代理商一鍵": ("代理商CUE", "一鍵CUE（模板）"),
    "代理商CUE": ("代理商CUE", "自訂代理商CUE"),
}


def capture(keys):
    """從 session 取出 keys 中存在的值（供快照 restore）。"""
    return {k: st.session_state[k] for k in keys if k in st.session_state}


def _ragic_conn():
    return st.session_state.get("ragic_url"), st.session_state.get("ragic_key")


def json_copy(obj):
    import json
    return json.loads(json.dumps(obj, ensure_ascii=False))


SIGNBACK_FIELD = "1015884"   # cue/2「客戶回簽/業務認簽」附件欄（送出訂檔時上傳客戶回簽檔）


def reviewers():
    """營運主管／管理員的 Ragic 信箱（Secrets RAGIC_REVIEWERS，逗號分隔）。"""
    raw = str(_secret("RAGIC_REVIEWERS", "")).replace("，", ",")
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


def is_reviewer():
    """營運主管：信箱在 RAGIC_REVIEWERS 名單，或已用主管密碼登入。"""
    u = current_user()
    return bool(st.session_state.get("is_supervisor") or (u and u.get("email", "").lower() in reviewers()))


def booking_enabled():
    """送出時是否真的寫入 CUE號申請／訂檔（正式表單，預設關閉）。"""
    return str(_secret("RAGIC_BOOKING_ENABLED", "")).strip().lower() in ("1", "true", "yes")


def my_code(u):
    import cue_registry as reg
    return reg.sales_code(u.get("name", ""), u.get("email", ""), reg.parse_overrides(_secret("RAGIC_SALES_CODES", "")))


@st.cache_data(ttl=60, show_spinner=False)
def all_saved(url, key):
    """cue/2 全部有快照的存檔 [(紀錄, 快照)]（新到舊）。"""
    import cue_store as cs
    from ragic_booking import cue2
    out = []
    for rec in cue2.list_all(url, key):
        snap = cs.parse_snapshot(cue2.details_of(rec))
        if snap:
            out.append((rec, snap))
    return out


def _new_save_no(u):
    """第一次存檔的編號：同代碼同年最大流水 +1（直接讀 Ragic，不用快取）。"""
    import cue_registry as reg
    all_saved.clear()
    url, key = _ragic_conn()
    nos = [s.get("save_no") for _r, s in all_saved(url, key)]
    return reg.next_no(my_code(u), nos)


def _upload_dict(files, style=None):
    """files（dict 或產生 dict 的函式）→ (files dict, cue/2 附件 {欄位ID: (檔名, bytes, mime)})。"""
    from config import RAGIC_MAP
    if callable(files):   # 合併多波附件較耗時，只在真的要用時才產生
        with st.spinner("產生檔案中…"):
            files = files()
    up = {}
    xl, pdf = (files or {}).get("xlsx"), (files or {}).get("pdf")
    if xl:
        up[RAGIC_MAP["file_xls"]] = (xl[0], xl[1], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if pdf and pdf[1]:
        up[RAGIC_MAP["file_pdf"]] = (pdf[0], pdf[1], "application/pdf")
    if style is not None and RAGIC_MAP.get("file_style_xls"):
        up[RAGIC_MAP["file_style_xls"]] = (style.name, style.getvalue(), "application/octet-stream")
    return files or {}, up


_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _render_downloads(files, key_prefix, saved_ok):
    """存檔後才能下載（第 5 期：每張出過的 CUE 都納入統計）。files["extra"]＝各波個別檔案。"""
    if not saved_ok:
        st.caption("⬇️ 存檔後即可下載 Excel／PDF（內容有修改需再存一次）。")
        return
    can_x = st.session_state.get("is_supervisor", False) or st.session_state.get("allow_sales_excel_download", True)
    can_p = st.session_state.get("is_supervisor", False) or st.session_state.get("allow_sales_pdf_download", True)
    if callable(files):
        cache = f"{key_prefix}_dl_files"
        if cache not in st.session_state:
            if not st.button("📦 產生下載檔", key=f"{key_prefix}_dl_make"):
                return
            st.session_state[cache], _ = _upload_dict(files)
        files = st.session_state[cache]
    items = []
    if files.get("xlsx") and can_x:
        items.append(("⬇️ 下載 Excel", files["xlsx"][0], files["xlsx"][1], _XLSX))
    if files.get("pdf") and files["pdf"][1] and can_p:
        items.append(("⬇️ 下載 PDF", files["pdf"][0], files["pdf"][1], "application/pdf"))
    for label, name, data, mime in files.get("extra") or []:
        if (mime == _XLSX and can_x) or (mime != _XLSX and can_p):
            items.append((label, name, data, mime))
    if not items:
        st.caption("下載已由主管關閉")
        return
    cols = st.columns(min(len(items), 4))
    for i, (label, name, data, mime) in enumerate(items):
        cols[i % len(cols)].download_button(label, data, name, mime=mime, key=f"{key_prefix}_dl_{i}")


def render_save_panel(snap, *, files=None, legacy_details="", extra_fields=None, key_prefix="save",
                      allow_style_excel=True):
    """存檔到 Ragic（cue/2）＋下載＋送出訂檔＋主管抽查退回。
    - 第一次存檔給存檔編號（P2610-023）並記存檔人；同一份再存＝更新同一筆、版本 +1、編號不變。
    - 存檔後且內容未再改動才可下載。
    - 送出訂檔＝立即申請 CUE號＋建立各波訂檔＝成交；已訂檔後修改則更新原訂檔。
    files：{"xlsx": (檔名, bytes), "pdf": (檔名, bytes), "extra": [(按鈕, 檔名, bytes, mime)]}，或回傳該 dict 的函式。"""
    import cue_registry as reg
    import cue_store as cs
    from config import RAGIC_MAP
    from ragic_booking import cue2

    st.markdown("---")
    st.markdown("#### ☁️ 存檔到 Ragic")
    msg_key = f"{key_prefix}_saved_msg"
    rec = st.session_state.get(SS_RECORD)
    linked = rec if rec and rec.get("mode") == snap.get("mode") else None
    lsnap = (linked or {}).get("snap") or {}
    pv = lsnap.get("version", 0)
    dirty = bool(linked) and cs.has_changes(lsnap, snap)
    st.session_state["_cue_dirty"] = dirty
    if dirty:
        st.warning(f"⚠️ 內容已修改，尚未存檔（Ragic 上目前是 v{pv}）")
    elif st.session_state.get(msg_key):
        st.success(st.session_state[msg_key])
    if linked:
        _status_line(lsnap)

    u = current_user()
    if not u:
        st.caption("以 Ragic 帳號登入後才能存檔與下載（每張出過的 CUE 都會記錄編號、納入統計）。")
        return

    as_new = True
    if linked:
        choice = st.radio("存檔方式", [f"更新 {reg.display_no(lsnap) or '#' + str(linked['rid'])}（v{pv} → v{pv + 1}）",
                                       "另存為新的一筆（新編號）"], key=f"{key_prefix}_how", horizontal=True)
        as_new = choice.startswith("另存")
        if not as_new:
            st.caption("本次異動：" + "；".join(cs.diff_summary(lsnap, snap)))
        if st.button("開新的 CUE（不再關聯這筆存檔）", key=f"{key_prefix}_unlink"):
            clear_loaded()
            st.rerun()
    s = cs.summarize(snap)
    st.caption(f"{s['waves']} 波｜{s['platform_detail'] or s['platform']}｜{s['seconds']}秒｜"
               f"總檔次 {s['total_spots']:,}｜實收合計 ${s['net_total']:,}")

    style = None
    if allow_style_excel:
        style = st.file_uploader("自調外觀 Excel（選填）", type=["xlsx", "xlsm", "xls"], key=f"{key_prefix}_style",
                                 help="僅能調整外觀及呈列方式，請勿調整每日檔次及金額（訂檔以程式資料為主）。")

    prev = None if as_new else lsnap
    final = cs.carry_over(prev, cs.next_version(prev, json_copy(snap), u["name"]))
    owner = reg.owner_of(final)
    ops_edit = bool(owner) and owner.get("email") and owner.get("email") != u.get("email") and is_reviewer()
    if ops_edit:   # 營運主管替業務加贈／調整：特別標記
        final["ops"] = {"by": u["name"], "at": final["history"][-1]["at"], "note": "營運加贈"}
        final["history"][-1]["changes"] = ["【營運加贈】"] + final["history"][-1]["changes"]
        st.info(f"🎁 你正在修改 {owner.get('name', '')} 的 CUE，存檔會標記「營運加贈」。")
    live = write_enabled()
    saved_ok = bool(linked) and not dirty
    _render_downloads(files, key_prefix, saved_ok)

    booked_before = bool(final.get("booking"))
    od = render_order_preview(final, key_prefix, prev_review=(prev or {}).get("review"),
                              update=booked_before)
    if not live:
        st.info("目前為**乾跑模式**：只預覽、不會寫入 Ragic。")
    with st.popover("👀 預覽將寫入 Ragic 的內容"):
        st.json({"動作": "新建（存檔時給編號）" if as_new else f"更新紀錄 {linked['rid']}",
                 "欄位": cs.ragic_fields(final, RAGIC_MAP, extra_fields),
                 "附件": (["（存檔時產生 Excel／PDF）"] if callable(files) else
                        [f[0] for k, f in (files or {}).items() if f and k != "extra"]) + ([style.name] if style else []),
                 "異動紀錄": final["history"][-1], "狀態": cs.status_of(final)})

    has_sign = bool(od["signback"] or ((prev or {}).get("review") or {}).get("signback"))
    block = ([] if live else ["乾跑模式"]) + ([] if booking_enabled() else ["訂檔寫入未開放（RAGIC_BOOKING_ENABLED）"]) \
        + od["missing"] + ([] if has_sign else ["客戶回簽檔"])
    b1, b2 = st.columns(2)
    do_save = b1.button("💾 存檔到 Ragic", key=f"{key_prefix}_btn", type="primary", disabled=not live)
    do_book = b2.button("📨 存檔並" + ("送出更新訂檔" if booked_before else "送出訂檔（成交）"),
                        key=f"{key_prefix}_submit", disabled=bool(block),
                        help=("尚缺：" + "、".join(block)) if block else
                        "送出即申請 CUE號並建立各波訂檔（已訂檔則更新原訂檔），算成交。")
    if linked and is_reviewer() and reg.is_deal(lsnap) and not dirty:
        _render_spot_check(linked, legacy_details, key_prefix)
    if not (do_save or do_book):
        return

    if as_new:
        final["save_no"] = _new_save_no(u)
        final["owner"] = {"name": u["name"], "email": u.get("email", ""), "code": my_code(u)}
    url, key = _ragic_conn()
    files_d, up = _upload_dict(files, style)
    if do_book:
        res = _book(final, od, files_d, rid=None if as_new else linked["rid"])
        if not res.get("ok"):
            st.error(f"送出訂檔失敗：{res.get('error')}")
            return
        cs.mark_booked(final, u["name"], od["params"], {"cue_id": res.get("cue_id", ""), "orders": res.get("orders", []),
                                                        "at": datetime_now(), "by": u["name"]})
        if od["signback"]:
            final["review"]["signback"] = od["signback"].name
            up[SIGNBACK_FIELD] = (od["signback"].name, od["signback"].getvalue(), "application/octet-stream")
        elif (prev or {}).get("review", {}).get("signback"):
            final["review"]["signback"] = prev["review"]["signback"]
    fields = cs.ragic_fields(final, RAGIC_MAP, extra_fields)
    fields[RAGIC_MAP["details"]] = cs.details_text(final, legacy_details)
    with st.spinner("存檔中…"):
        res = cue2.save_record(url, key, fields, up, rid=None if as_new else linked["rid"])
    if not res.ok:
        extra = f"（訂檔已建立：CUE號 {final['booking'].get('cue_id')}，請記下並通知 Jonathan）" if do_book else ""
        st.error(f"存檔失敗：{res.error}{extra}")
        return
    st.session_state[SS_RECORD] = {"rid": res.rid, "serial": res.serial, "mode": snap.get("mode"), "snap": final}
    st.session_state.pop(f"{key_prefix}_dl_files", None)
    st.session_state[msg_key] = (f"✅ 已存檔 {reg.display_no(final)}（v{final['version']}）"
                                 + (f"，已送出訂檔：CUE號 {final['booking'].get('cue_id')}" if do_book else "，可下載"))
    all_saved.clear()
    st.cache_data.clear()
    st.rerun()


def datetime_now():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _book(snap, od, files_d, rid=None, signback_bytes=None):
    """申請 CUE號＋建立各波訂檔（已訂檔過則更新原訂檔）。附件＝本 CUE Excel＋客戶回簽檔。"""
    import os
    import tempfile

    from ragic_booking import cue2
    from ragic_booking import fields as rf
    from ragic_booking import order_from_cue as oc

    p = od["params"]
    fmt = lambda d: d.strftime("%Y/%m/%d") if d else ""   # noqa: E731
    orders = oc.build_orders(snap, applicant=(reg_owner_name(snap) or (current_user() or {}).get("name", "")),
                             company=p.get("公司", ""), category=p.get("類別", "商品"),
                             收款日期=fmt(p.get("收款日期")), 發票開立日=fmt(p.get("發票開立日")))
    url, key = _ragic_conn()
    with st.spinner("申請 CUE號、建立／更新訂檔中…"), tempfile.TemporaryDirectory() as td:
        att = {}
        if files_d.get("xlsx"):
            path = os.path.join(td, files_d["xlsx"][0])
            with open(path, "wb") as f:
                f.write(files_d["xlsx"][1])
            att[rf.OrderF.訂檔CUE表] = path
        sb_name, sb_data = None, None
        if od.get("signback"):
            sb_name, sb_data = od["signback"].name, od["signback"].getvalue()
        elif rid:   # 沿用上次附在 cue/2 的回簽檔
            val = (cue2.get_record(url, key, rid) or {}).get(SIGNBACK_FIELD)
            val = val[0] if isinstance(val, list) and val else val
            if val:
                sb_name, sb_data = val.split("@", 1)[-1], cue2.download_file(url, key, val)
        if sb_data:
            path = os.path.join(td, sb_name)
            with open(path, "wb") as f:
                f.write(sb_data)
            att[rf.OrderF.客戶回簽檔] = path
        applicant = reg_owner_name(snap) or (current_user() or {}).get("name", "")
        if snap.get("booking"):
            return oc.update_booking(snap, orders, booking=snap["booking"], attachments={"all": att}, applicant=applicant)
        return oc.submit_booking(snap, orders, applicant=applicant, attachments={"all": att})


def reg_owner_name(snap):
    return ((snap or {}).get("owner") or {}).get("name", "")


def _status_line(snap):
    import cue_registry as reg
    import cue_store as cs
    stt = cs.status_of(snap)
    rv = snap.get("review") or {}
    bk = snap.get("booking") or {}
    o = reg.owner_of(snap)
    extra = [x for x in (reg.display_no(snap), o.get("name") and f"存檔人 {o['name']}") if x]
    if bk.get("cue_id"):
        extra.append(f"CUE號 {bk['cue_id']}")
    if snap.get("ops"):
        extra.append(f"🎁 營運加贈（{snap['ops'].get('by', '')}）")
    if stt == cs.REJECTED and rv.get("reason"):
        extra.append(f"退回原因：{rv['reason']}（{rv.get('reviewed_by', '')}）")
    msg = f"狀態：**{stt}**" + ("｜" + "｜".join(extra) if extra else "")
    (st.error if stt == cs.REJECTED else st.info)(msg)


def _save_snapshot_only(linked, snap, legacy_details):
    """只更新 cue/2 的快照（不動其他欄位與附件），抽查退回用。"""
    import cue_store as cs
    from config import RAGIC_MAP
    from ragic_booking import cue2
    url, key = _ragic_conn()
    res = cue2.save_record(url, key, {RAGIC_MAP["details"]: cs.details_text(snap, legacy_details)}, rid=linked["rid"])
    if res.ok:
        st.session_state[SS_RECORD] = dict(linked, snap=snap)
        all_saved.clear()
        st.cache_data.clear()
    return res


def _render_spot_check(linked, legacy_details, key_prefix):
    """營運主管抽查已成交的 CUE：有問題可退回（記原因；已建立的訂檔請在 Ragic 處理）。"""
    import cue_store as cs
    with st.expander("🗂 主管抽查", expanded=False):
        reason = st.text_input("退回原因", key=f"{key_prefix}_rv_reason")
        st.caption("退回後狀態改為「退回」、不計成交；已申請的 CUE號與已建立的訂檔不會自動刪除，請營運在 Ragic 處理。")
        if st.button("↩️ 退回", key=f"{key_prefix}_rv_no", disabled=not write_enabled() or not reason.strip()):
            u = current_user() or {}
            res = _save_snapshot_only(linked, cs.mark_reviewed(json_copy(linked["snap"]), u.get("name", ""), False,
                                                               reason=reason.strip()), legacy_details)
            if not res.ok:
                st.error(f"退回失敗：{res.error}")
                return
            st.rerun()


def _order_lines(orders):
    for i, d in enumerate(orders, 1):
        st.caption(f"第 {i} 波｜{d.執行開始日期}～{d.執行結束日期}｜" + "；".join(
            f"{r['平台細項']}{(' ' + str(r['秒數']) + '秒') if r['秒數'] else ''} "
            f"{r['平台檔數']:,}檔 ${r['實收金額未稅']:,}" for r in d.收入明細))


def clear_loaded():
    """解除與 Ragic 存檔的關聯，並清掉讀回時設定的覆寫值。"""
    for k in (SS_RECORD, "_simple_restore", "_cue_dirty"):
        st.session_state.pop(k, None)


def _rec_label(rec, snap):
    from config import RAGIC_FIELD_SERIAL, RAGIC_MAP
    h = snap.get("header", {})
    last = (snap.get("history") or [{}])[-1]
    return (f"#{rec.get(RAGIC_FIELD_SERIAL) or rec['_ragicId']} {h.get('client') or rec.get(RAGIC_MAP['client'], '')}"
            f" {h.get('product') or ''}｜{snap.get('mode')}｜v{snap.get('version')}｜{snap.get('status') or '草稿'}"
            f"｜{last.get('by', '')} {last.get('at', '')}")


@st.cache_data(ttl=60, show_spinner=False)
def _list_saved(url, key, keyword):
    import cue_store as cs
    from ragic_booking import cue2
    out = []
    for rec in cue2.list_records(url, key, keyword=keyword, limit=200):
        snap = cs.parse_snapshot(cue2.details_of(rec))
        if snap:
            out.append((rec, snap))
    return out


def render_my_cues_sidebar():
    """側欄「📂 我的 CUE」：列出有快照的存檔，開啟後還原到對應模式繼續編輯。"""
    st.subheader("📂 我的 CUE")
    u = current_user()
    if not u:
        st.caption("以 Ragic 帳號登入後可查詢、開啟存檔。")
        return
    rec = st.session_state.get(SS_RECORD)
    if rec:
        st.caption(f"編輯中：#{rec.get('serial') or rec['rid']}（{rec.get('mode')} v{(rec.get('snap') or {}).get('version')}）")
        if st.session_state.get("_cue_dirty"):
            st.warning("⚠️ 有尚未存檔的修改")
    kw = st.text_input("關鍵字（客戶、產品、Cue號，可留白）", key="mycue_kw")
    mine = st.checkbox("只看我存過的", value=True, key="mycue_mine")
    url, key = _ragic_conn()
    if not (url and key):
        st.caption("尚未設定 Ragic 連線。")
        return
    try:
        items = _list_saved(url, key, kw.strip())
    except Exception as e:  # noqa: BLE001
        st.error(f"讀取 Ragic 失敗：{e}")
        return
    if mine:
        items = [(r, s) for r, s in items if any(h.get("by") == u["name"] for h in s.get("history", []))]
    if not items:
        st.caption("沒有符合的存檔（只列出新版程式存的 CUE）。")
        return
    idx = st.selectbox("存檔", range(len(items)), format_func=lambda i: _rec_label(*items[i]), key="mycue_pick")
    r, s = items[idx]
    with st.expander("異動紀錄", expanded=False):
        for h in reversed(s.get("history", [])):
            st.caption(f"v{h['v']}｜{h['at']}｜{h['by']}：" + "；".join(h.get("changes", [])))
    if st.button("📂 開啟這份 CUE", key="mycue_open", type="primary"):
        open_record(r, s)


def open_record(rec, snap):
    """把存檔還原到對應製作模式。一般CUE／代理商自訂沿用原本的還原（[EXT]／[AGENCY_EXT]），
    其他模式用快照 restore（設定 session 值，並清掉會由 restore 重算的動態欄位）。"""
    import cue_store as cs
    from config import RAGIC_FIELD_SERIAL
    mode = snap.get("mode")
    nav = MODE_NAV.get(mode)
    if not nav:
        st.error(f"無法開啟：未知的製作模式 {mode}")
        return
    clear_loaded()
    restore = cs.from_jsonable(snap.get("restore") or {})
    if mode == "一般CUE":
        from ragic_api import restore_state_from_ragic
        restore_state_from_ragic(rec)
    elif mode == "代理商CUE":
        from agency_ui import _restore_agency_state
        _restore_agency_state(rec)
    for prefix in restore.pop("_clear_prefixes", []):
        for k in [k for k in list(st.session_state.keys()) if str(k).startswith(prefix)]:
            del st.session_state[k]
    for k, v in restore.items():
        st.session_state[k] = v
    if snap.get("customer"):
        st.session_state[SS_CUSTOMER] = cs.from_jsonable(snap["customer"])
    # 「製作模式」選單可能已在本次執行畫出（例如從 CUE 管理頁開啟），改由下一次執行在畫選單前套用
    st.session_state[NAV_KEY] = nav[0]
    if nav[1]:
        st.session_state["agency_sub_mode"] = nav[1]
    st.session_state[SS_RECORD] = {"rid": rec["_ragicId"], "serial": str(rec.get(RAGIC_FIELD_SERIAL) or ""),
                                   "mode": mode, "snap": snap}
    st.rerun()


# =============================================================================
# 第 4 期：訂檔資料（送審時一起送出）
# =============================================================================
COMPANY_OPTIONS = ["東吳", "聲活", "鉑霖", "錄音室", "聲活(采藝)"]   # 訂檔表實際使用值


def render_order_preview(snap, key_prefix, prev_review=None, update=False):
    """訂檔補充資料（公司、收入類別、收款日、發票日、客戶回簽檔）＋各波訂檔預覽。
    回傳 {"params", "missing", "signback"} 供「送出訂檔」使用；欄位預設帶上次送出的值。"""
    import cue_store as cs
    from ragic_booking import fields as rf
    from ragic_booking import order_from_cue as oc
    last = cs.from_jsonable((prev_review or {}).get("params") or {})
    out = {"params": {}, "missing": [], "signback": None}
    title = "🧾 訂檔資料（送出即更新原訂檔）" if update else "🧾 訂檔資料（送出即申請 CUE號、建立訂檔＝成交）"
    with st.expander(title, expanded=False):
        u = current_user() or {}
        c1, c2, c3, c4 = st.columns(4)
        opts = [""] + COMPANY_OPTIONS
        dflt = last.get("公司") or oc.default_company(snap)
        company = c1.selectbox("公司", opts, index=opts.index(dflt) if dflt in opts else 0, key=f"{key_prefix}_od_company")
        cats = oc.INCOME_CATEGORIES
        category = c2.selectbox("收入類別", cats, index=cats.index(last["類別"]) if last.get("類別") in cats else 0,
                                key=f"{key_prefix}_od_cat")
        pay = c3.date_input("收款日期", value=last.get("收款日期"), key=f"{key_prefix}_od_pay")
        inv = c4.date_input("發票開立日", value=last.get("發票開立日"), key=f"{key_prefix}_od_inv")
        sign = st.file_uploader("客戶回簽檔（送出必附）", type=["pdf", "jpg", "jpeg", "png"], key=f"{key_prefix}_od_sign",
                                help="客戶回簽後的 CUE（PDF 或照片）；已送出過可不重傳，沿用上次的檔案。")
        if (prev_review or {}).get("signback") and not sign:
            st.caption(f"已附客戶回簽檔：{prev_review['signback']}")
        orders = oc.build_orders(snap, applicant=u.get("name", ""), company=company, category=category,
                                 收款日期=pay.strftime("%Y/%m/%d") if pay else "",
                                 發票開立日=inv.strftime("%Y/%m/%d") if inv else "")
        miss = oc.missing(snap, orders)
        missing = [x.split("（")[0] for x in miss["CUE號申請"] + miss["訂檔"]]
        if missing:
            st.warning("送出前還缺：" + "、".join(dict.fromkeys(missing)))
        else:
            st.success("訂檔必填欄位齊全。")
        _order_lines(orders)
        with st.popover("檢視將寫入 Ragic 的欄位"):
            st.json({"CUE號申請（forms13/4）": oc.cue_apply_payload(snap, u.get("name", "")),
                     "訂檔（forms12/17）": [rf.order_payload_json(d) for d in orders]})
        out = {"params": {"公司": company, "類別": category, "收款日期": pay, "發票開立日": inv},
               "missing": list(dict.fromkeys(missing)), "signback": sign}
    return out
