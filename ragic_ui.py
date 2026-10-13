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
            "類別": c.類別, "業務": c.業務, "主管": c.主管, "付款條件": c.付款條件,
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
