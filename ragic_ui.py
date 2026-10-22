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
SS_CUST_FILL = "_ragic_customer_fill"   # 訂檔區帶入的客戶：下次執行由頁首 customer_picker 回填空白的客戶名稱／統編／產品


def write_enabled():
    return str(_secret("RAGIC_WRITE_ENABLED", "")).strip().lower() in ("1", "true", "yes")


def current_user():
    return st.session_state.get(SS_USER)


def match_sales(name, options):
    """登入者姓名 → 業務下拉中的對應選項（Ragic 名稱可能帶英文名，如「楊心瑀 Alison」）；對不到回 None。"""
    name = str(name or "").strip()
    if not name:
        return None
    for o in options:
        if o == name:
            return o
    for o in options:
        if o and (name.startswith(o) or o in name.split()):
            return o
    return None


def default_sales_index(options, offset=0):
    """業務下拉預設＝登入者本人（10/14 實測：業務留「—」→ 存檔表業務人員空白）；對不到回 None。"""
    u = current_user() or {}
    o = match_sales(u.get("name"), list(options))
    return None if o is None else list(options).index(o) + offset


@st.cache_data(ttl=600, show_spinner=False)
def _ragic_users():
    return auth.fetch_ragic_users(str(_secret("RAGIC_API_KEY", "")))


SS_PENDING = "ragic_pending_user"   # 預設密碼登入、尚未改密碼的使用者（改完才算登入）


def _pw_store():
    """密碼表＝newcue 設定檔 Google Sheet 的「登入密碼」分頁（可用 APP_PASSWORD_SHEET_URL 改）；
    需 Secrets [gcp_service_account]，未設定回 None。"""
    import app_passwords as ap
    import config
    url = str(_secret("APP_PASSWORD_SHEET_URL", "")).strip() or config.GSHEET_SHARE_URL
    try:
        sa = st.secrets.get("gcp_service_account")
    except Exception:  # noqa: BLE001
        sa = None
    if not (url and sa):
        return None
    return ap.PasswordStore.from_service_account(url, sa)


def login(account_id, pwd):
    """登入 → (使用者, 是否還在用預設密碼需先改)。
    有設密碼表：帳號＝公司信箱或員工工號，身分取 Ragic 使用者清單，密碼比對 Google Sheet（沒列＝預設 123456）。
    沒設密碼表（本機開發）：用 Ragic 帳密 AUTH（Streamlit Cloud 會被 Ragic 擋）。"""
    import app_passwords as ap
    store = _pw_store()
    if store is None:
        return auth.ragic_login(account_id, pwd), False
    try:
        users = _ragic_users()
    except Exception as e:  # noqa: BLE001
        raise auth.RagicAuthError(f"讀取 Ragic 使用者清單失敗：{e}") from e
    user = auth.user_from_list(account_id, users)
    try:
        ok, must_change = store.check(user.email, pwd)
    except ap.PasswordError as e:
        raise auth.RagicAuthError(str(e)) from e
    if not ok:
        raise auth.RagicAuthError("帳號或密碼錯誤（忘記密碼請找 Jonathan 重設為 123456）")
    return user, must_change


def _change_password_form(email, key, need_old):
    """改密碼表單；成功回傳 True。need_old：已登入時要先輸入舊密碼。"""
    import app_passwords as ap
    store = _pw_store()
    if store is None:
        st.caption("尚未設定密碼表，無法改密碼。")
        return False
    with st.form(key, clear_on_submit=True):
        old = st.text_input("目前密碼", type="password") if need_old else None
        new = st.text_input(f"新密碼（至少 {ap.MIN_LEN} 個字）", type="password")
        again = st.text_input("再輸入一次新密碼", type="password")
        go = st.form_submit_button("更新密碼", type="primary")
    if not go:
        return False
    try:
        if need_old and not store.check(email, old)[0]:
            raise ap.PasswordError("目前密碼不正確")
        ap.check_new_password(new, again)
        store.set_password(email, new)
    except ap.PasswordError as e:
        st.error(str(e))
        return False
    return True


def dev_login_user(pwd):
    """開發者登入（給沒有公司 Ragic 帳號的開發者實測用）：只在 Secrets 設了 DEV_LOGIN_PASSWORD 的 app 啟用
    （正式 app 不設＝入口不出現）。密碼對 → 以 DEV_LOGIN_NAME／DEV_LOGIN_EMAIL 身分登入；否則 None。
    讀寫 Ragic 本來就用 Secrets 的 API Key，與登入身分無關。"""
    expect = str(_secret("DEV_LOGIN_PASSWORD", "")).strip()
    if not expect or pwd != expect:
        return None
    return {"email": str(_secret("DEV_LOGIN_EMAIL", "dev@newcue.local")).strip(),
            "name": str(_secret("DEV_LOGIN_NAME", "開發者")).strip(), "groups": ["開發者"]}


# =============================================================================
# 登入（側欄）
# =============================================================================
def render_login_sidebar():
    st.header("👤 Ragic 帳號")
    pending = st.session_state.get(SS_PENDING)
    if pending:   # 預設密碼登入：改完密碼才算登入
        st.warning(f"{pending['name']}，第一次登入請先設定自己的密碼（預設密碼 123456 不能繼續使用）。")
        if _change_password_form(pending["email"], "pw_first_form", need_old=False):
            st.session_state[SS_USER] = st.session_state.pop(SS_PENDING)
            st.rerun()
        if st.button("取消", key="pw_first_cancel"):
            st.session_state.pop(SS_PENDING, None)
            st.rerun()
        return
    u = current_user()
    if u:
        st.success(f"✅ {u['name']}")
        with st.expander("帳號資訊", expanded=False):
            st.caption(u["email"])
            st.caption("群組：" + ("、".join(u["groups"]) or "（無）"))
        if "開發者" not in (u.get("groups") or []):
            with st.expander("🔑 修改密碼", expanded=False):
                if _change_password_form(u["email"], "pw_change_form", need_old=True):
                    st.success("密碼已更新")
        if st.button("登出", key="ragic_logout"):
            st.session_state.pop(SS_USER, None)
            st.session_state.pop(SS_CUSTOMER, None)
            st.rerun()
        return
    with st.form("ragic_login_form", clear_on_submit=False):
        email = st.text_input("公司信箱或員工工號", key="ragic_login_email")
        pwd = st.text_input("密碼", type="password", key="ragic_login_pwd",
                            help="第一次登入請用預設密碼 123456，登入後會要求設定自己的密碼。")
        ok = st.form_submit_button("登入")
    st.caption("登入後才能存檔、下載與從 Ragic 帶入客戶。第一次登入密碼 123456；忘記密碼請找 Jonathan。"
               "這是本 app 專用密碼，和 Ragic 密碼分開、不會同步（Ragic 擋雲端登入）。")
    if ok:
        try:
            user, must_change = login(email, pwd)
        except auth.RagicAuthError as e:
            st.error(str(e))   # 不 return：登入失敗時下方「開發者登入」入口仍要顯示
        else:
            info = {"email": user.email, "name": user.name, "groups": user.groups}
            st.session_state[SS_PENDING if must_change else SS_USER] = info
            st.session_state.pop("ragic_login_pwd", None)
            st.rerun()
    if str(_secret("DEV_LOGIN_PASSWORD", "")).strip():
        with st.expander("🛠 開發者登入", expanded=False):
            st.caption("開發者不用填上方信箱，只輸入 Secrets 的 DEV_LOGIN_PASSWORD。")
            dpwd = st.text_input("開發者密碼", type="password", key="dev_login_pwd")
            if st.button("以開發者身分登入", key="dev_login_btn"):
                du = dev_login_user(dpwd)
                if not du:
                    st.error("開發者密碼錯誤")
                    return
                st.session_state[SS_USER] = du
                st.session_state.pop("dev_login_pwd", None)
                st.rerun()


# =============================================================================
# 客戶帶入
# =============================================================================
@st.cache_data(ttl=300, show_spinner=False)
def _search(query):
    return [_cust_dict(c) for c in rf.search_customers(query, limit=30)]


def _cust_dict(c):
    return {"rid": c.rid, "編號": c.編號, "名稱": c.名稱, "統編": c.統編, "產品": c.產品,
            "類別": c.類別, "業務": c.業務, "主管": c.主管, "客服": list(c.客服), "付款條件": c.付款條件, "產業別": c.產業別,
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
    pend = st.session_state.pop(SS_CUST_FILL, None)
    if pend:   # 只填空白欄，不蓋掉業務已輸入的名稱
        vals = {"client": pend.get("名稱"), "tax": pend.get("統編"), "product": pend.get("產品")}
        for f, key in targets.items():
            if key and vals.get(f) and not str(st.session_state.get(key) or "").strip():
                st.session_state[key] = vals[f]
    sel = st.session_state.get(SS_CUSTOMER)
    title = f"🔗 Ragic 客戶：{sel['編號']} {sel['名稱']}" if sel else "🔎 從 Ragic 帶入客戶"
    with st.expander(title, expanded=False):
        if not current_user():
            st.caption("請先在左側以 Ragic 帳號登入。")
            return
        if sel:
            st.caption(f"客戶編號 {sel['編號']}｜{sel['類別'] or '—'}｜統編 {sel['統編'] or '—'}｜"
                       f"現折 {sel['現折'] or '—'}％｜退佣 {sel['退佣'] or '—'}％｜付款 {sel['付款條件'] or '—'}")
            st.caption("要改 CUE 上顯示的客戶名稱，直接改下方客戶名稱欄（簡易模式在「客戶名稱／業務…」展開區）；"
                       "改名不影響訂檔，送 Ragic 仍以這個客戶編號為準。")
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
                      allow_style_excel=True, save_block=None):
    """存檔到 Ragic（cue/2）＋下載＋送出訂檔＋主管審核（核准／退回）。
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
    saver = None
    if linked and not dirty and not as_new:
        def saver(fn):
            new = json_copy(lsnap)
            fn(new)
            return _save_snapshot_only(linked, new, legacy_details)
    od = render_order_preview(final, key_prefix, prev_review=(prev or {}).get("review"),
                              update=booked_before, cue_saver=saver, serial=str((linked or {}).get("serial") or ""))
    if not live:
        st.info("目前為**乾跑模式**：只預覽、不會寫入 Ragic。")
    with st.expander("👀 預覽將寫入 Ragic 的內容（仿 Ragic 畫面）", expanded=False):
        import ragic_order_preview as rp
        att = (["（存檔時產生 Excel／PDF）"] if callable(files) else
               [f[0] for k, f in (files or {}).items() if f and k != "extra"]) + ([style.name] if style else [])
        t_cue, t_order = st.tabs(["CUE 存檔", "訂檔（送出訂檔時）"])
        with t_cue:
            st.caption(f"動作：{'新建（存檔時給編號）' if as_new else '更新紀錄 #' + str(linked['rid'])}｜"
                       f"狀態：{cs.status_of(final)}｜本次異動：{'；'.join(final['history'][-1].get('changes', []))}")
            st.html(rp.cue2_html(cs.ragic_fields(final, RAGIC_MAP, extra_fields), files=att,
                                 serial="" if as_new else str(linked.get("serial") or ""),
                                 action="新建" if as_new else "更新"))
        with t_order:
            if od.get("orders"):
                _ragic_preview(od["orders"], od.get("signback") or ((prev or {}).get("review") or {}).get("signback"),
                               od.get("materials"), link={"產業別": (final.get("customer") or {}).get("產業別", "")})
            else:
                st.caption("尚無訂檔內容（請先在上方「🧾 訂檔資料」帶入客戶）。")

    has_sign = bool(od["signback"] or ((prev or {}).get("review") or {}).get("signback"))
    block = ([] if live else ["乾跑模式"]) + ([] if booking_enabled() else ["訂檔寫入未開放（RAGIC_BOOKING_ENABLED）"]) \
        + od["missing"] + ([] if has_sign else ["客戶回簽檔"])
    if save_block:   # 呼叫端指定的存檔必填（如簡易模式的請款月份、付款兌現日）
        st.warning("存檔前請先在上方「客戶名稱／業務／產品／付款／甲乙方」填寫：" + "、".join(save_block))
        block = list(save_block) + block
    b1, b2 = st.columns(2)
    do_save = b1.button("💾 存檔到 Ragic", key=f"{key_prefix}_btn", type="primary",
                        disabled=not live or bool(save_block))
    do_book = b2.button("📨 存檔並" + ("送出更新訂檔" if booked_before else "送出訂檔（成交）"),
                        key=f"{key_prefix}_submit", disabled=bool(block),
                        help=("尚缺：" + "、".join(block)) if block else
                        "以 ⓪ 的 CUE號 建立各波訂檔（已訂檔則更新原訂檔），算成交；之後由主管審核。")
    if linked and is_reviewer() and cs.audit_of(lsnap) == cs.AUDIT_PENDING and not dirty:
        _render_audit(linked, legacy_details, key_prefix)
    if not (do_save or do_book):
        return

    if as_new:
        final["save_no"] = _new_save_no(u)
        final["owner"] = {"name": u["name"], "email": u.get("email", ""), "code": my_code(u)}
    url, key = _ragic_conn()
    files_d, up = _upload_dict(files, style)
    save_rid = None if as_new else linked["rid"]
    fail_msg = ""
    if do_book:
        res = _book(final, od, files_d, rid=save_rid)
        if not res.get("ok"):
            if not res.get("orders"):
                st.error(f"送出訂檔失敗：{res.get('error')}")
                return
            # 部分波段已建立：記進快照，修正後重送只補沒完成的（不重建、不重申請 CUE號）
            final["booking"] = {"cue_id": res.get("cue_id") or oc_current(final), "orders": res["orders"],
                                "partial": True, "at": datetime_now(), "by": u["name"]}
            fail_msg = (f"⚠️ 送出訂檔未完成：{res.get('error')}。已建立的 {len(res['orders'])} 波已記錄，"
                        "修正後再按送出只會補沒完成的波段。")
        else:
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
        res = cue2.save_record(url, key, fields, up, rid=save_rid)
    if not res.ok:
        extra = f"（訂檔已建立：CUE號 {final['booking'].get('cue_id')}，請記下並通知 Jonathan）" if do_book else ""
        st.error(f"存檔失敗：{res.error}{extra}")
        return
    st.session_state[SS_RECORD] = {"rid": res.rid, "serial": res.serial, "mode": snap.get("mode"), "snap": final}
    st.session_state[f"{key_prefix}_dl_files"] = files_d   # 存檔時產生的檔案直接給下載用，免再按「產生下載檔」
    st.session_state[msg_key] = fail_msg or (f"✅ 已存檔 {reg.display_no(final)}（v{final['version']}）"
                                             + (f"，已送出訂檔：CUE號 {final['booking'].get('cue_id')}，待主管審核"
                                                if do_book else "，可下載"))
    all_saved.clear()
    st.cache_data.clear()
    st.rerun()


def oc_current(snap):
    from ragic_booking import order_from_cue as oc
    return oc.current_cue(snap).get("cue_id", "")


def datetime_now():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _book(snap, od, files_d, rid=None, signback_bytes=None, serial=""):
    """申請 CUE號＋建立各波訂檔（已訂檔過則更新原訂檔）。附件＝本 CUE Excel＋客戶回簽檔。"""
    import os
    import tempfile

    from ragic_booking import cue2
    from ragic_booking import fields as rf
    from ragic_booking import order_from_cue as oc

    p = od["params"]
    if not oc.current_cue(snap).get("cue_id"):
        return {"ok": False, "error": "尚未申請 CUE號（請先在 ⓪ 申請，或輸入已申請的 CUE號）"}
    orders = _orders(snap, p, reg_owner_name(snap) or (current_user() or {}).get("name", ""))
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
        for n, m in enumerate(od.get("materials") or [], 1):   # 列號與 build_orders 的 素材明細 同序
            for fkey, up in zip(rf.material_file_keys(n), (m.get("音檔"), m.get("文案"))):
                if up:
                    mdir = os.path.join(td, f"m{n}")
                    os.makedirs(mdir, exist_ok=True)
                    path = os.path.join(mdir, up.name)
                    with open(path, "wb") as f:
                        f.write(up.getvalue())
                    att[fkey] = path
        applicant = reg_owner_name(snap) or (current_user() or {}).get("name", "")
        if snap.get("booking"):
            return oc.update_booking(snap, orders, booking=snap["booking"], attachments={"all": att}, applicant=applicant)
        return oc.submit_booking(snap, orders, applicant=applicant, attachments={"all": att}, serial=serial)


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
    au = snap.get("audit") or {}
    if cs.audit_of(snap):
        extra.append(f"主管審核：{cs.audit_of(snap)}" + (f"（{au['by']} {au.get('at', '')}）" if au.get("by") else ""))
    if stt == cs.REJECTED and (au.get("reason") or rv.get("reason")):
        extra.append(f"退回原因：{au.get('reason') or rv['reason']}（{au.get('by') or rv.get('reviewed_by', '')}）")
    msg = f"狀態：**{stt}**" + ("｜" + "｜".join(extra) if extra else "")
    (st.error if stt == cs.REJECTED else st.info)(msg)


def _save_snapshot_only(linked, snap, legacy_details):
    """只更新 cue/2 的快照（不動其他欄位與附件），主管審核用。"""
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


def render_audit_box(snap, save, key_prefix):
    """主管審核按鈕（核准／填原因退回）。save(新快照) → 寫回 Ragic 的結果（有 ok／error）。成功回傳 True。"""
    import cue_store as cs
    st.caption("核准＝確認這份訂檔沒問題；退回＝狀態改為「退回」、不計成交，"
               "已申請的 CUE號與已建立的訂檔不會自動刪除，請營運在 Ragic 處理。")
    reason = st.text_input("退回原因（退回時必填）", key=f"{key_prefix}_au_reason")
    c1, c2 = st.columns(2)
    ok = c1.button("✅ 核准", key=f"{key_prefix}_au_ok", type="primary", disabled=not write_enabled())
    no = c2.button("↩️ 退回", key=f"{key_prefix}_au_no", disabled=not write_enabled() or not reason.strip())
    if not (ok or no):
        return False
    u = current_user() or {}
    res = save(cs.mark_audited(json_copy(snap), u.get("name", ""), ok, reason="" if ok else reason.strip()))
    if not res.ok:
        st.error(f"審核寫入失敗：{res.error}")
        return False
    return True


def _render_audit(linked, legacy_details, key_prefix):
    """開啟的 CUE 已送訂檔、待主管審核：存檔區直接核准／退回。"""
    with st.expander("🗂 主管審核（待審）", expanded=True):
        if render_audit_box(linked["snap"], lambda new: _save_snapshot_only(linked, new, legacy_details), key_prefix):
            st.rerun()


def _order_lines(orders):
    def n(v):
        try:
            return int(float(v or 0))
        except (TypeError, ValueError):
            return 0
    for i, d in enumerate(orders, 1):
        st.caption(f"第 {i} 波｜{d.執行開始日期}～{d.執行結束日期}｜" + "；".join(
            f"{r.get('平台細項', '')}{(' ' + str(r['秒數']) + '秒') if r.get('秒數') else ''} "
            f"{n(r.get('平台檔數')):,}檔 ${n(r.get('實收金額未稅')):,}" for r in d.收入明細))


INCOME_COLS = ["類別", "業績年月", "平台細項", "平台檔數", "秒數", "製作成本", "配音員費用", "實收金額未稅", "其他成本", "公司"]
PLATFORM_DETAILS = ["全家企頻", "新鮮視", "家樂福企頻", "健康視", "廣播", "其他", "製作收入"]   # 訂檔表實際值
_NUM_COLS = ("平台檔數", "秒數", "製作成本", "配音員費用", "實收金額未稅", "其他成本")


@st.cache_data(ttl=3600, show_spinner=False)
def _order_opts(field_name):
    try:
        return rf.order_field_options(field_name)
    except Exception:  # noqa: BLE001
        return []


def _clean_income(records):
    """data_editor 回傳 → 乾淨的收入列（NaN→空、整數不帶 .0、整列空白略過）。"""
    import math
    out = []
    for r in records:
        row = {}
        for c in INCOME_COLS:
            v = r.get(c)
            if v is None or (isinstance(v, float) and math.isnan(v)):
                v = ""
            if c in _NUM_COLS and v != "":
                try:
                    f = float(v)
                    v = int(f) if f.is_integer() else f
                except (TypeError, ValueError):
                    pass
            row[c] = v
        if any(str(row[c]).strip() for c in INCOME_COLS if c not in ("類別", "公司", "業績年月")):
            out.append(row)
    return out


def _income_editor(base_orders, key_prefix):
    """逐波收入子表編輯（cueupload 同做法：data_editor 動態增列）。CUE 或 ② 的類別／公司改了就重設成新預填。
    回傳逐波的收入列清單。"""
    import hashlib
    import json

    import pandas as pd
    from ragic_booking import order_from_cue as oc
    tabs = st.tabs([f"第{i + 1}波" for i in range(len(base_orders))]) if len(base_orders) > 1 else [st.container()]
    out = []
    for i, (d, tab) in enumerate(zip(base_orders, tabs)):
        base = [{c: ("" if r.get(c) is None else r.get(c, "")) for c in INCOME_COLS} for r in d.收入明細]
        sig = hashlib.md5(json.dumps(base, ensure_ascii=False, default=str).encode()).hexdigest()[:8]
        df = pd.DataFrame(base, columns=INCOME_COLS)
        for c in _NUM_COLS:
            df[c] = pd.to_numeric(df[c].replace("", None), errors="coerce")
        for c in ("類別", "業績年月", "平台細項", "公司"):
            df[c] = df[c].astype(str)
        with tab:
            ed = st.data_editor(
                df, num_rows="dynamic", hide_index=True, key=f"{key_prefix}_od_inc_{i}_{sig}", width="stretch",
                column_config={
                    "類別": st.column_config.SelectboxColumn("類別*", options=oc.INCOME_CATEGORIES),
                    "業績年月": st.column_config.TextColumn("業績年月*", help="yyyy/MM/dd（Ragic 顯示成 yyyy/MM）"),
                    "平台細項": st.column_config.SelectboxColumn("平台細項*", options=PLATFORM_DETAILS),
                    "平台檔數": st.column_config.NumberColumn("平台檔數*", step=1, format="%d"),
                    "秒數": st.column_config.NumberColumn("秒數*", step=1, format="%d"),
                    "製作成本": st.column_config.NumberColumn("製作成本", step=1, format="%d"),
                    "配音員費用": st.column_config.NumberColumn("配音員費用", step=1, format="%d"),
                    "實收金額未稅": st.column_config.NumberColumn("實收金額(未稅)*", step=1, format="%d"),
                    "其他成本": st.column_config.NumberColumn("其他成本", step=1, format="%d"),
                    "公司": st.column_config.SelectboxColumn("公司", options=COMPANY_OPTIONS),
                })
        rows = _clean_income(ed.to_dict("records"))
        out.append(rows)
        tot = sum(int(float(r.get("平台檔數") or 0)) for r in rows if r.get("平台細項") != oc.PROD_LABEL)
        st.caption(f"{'第' + str(i + 1) + '波 ' if len(base_orders) > 1 else ''}{len(rows)} 列｜"
                   f"平台檔數合計 {tot:,}（＝主表 CUE表總檔數；平台、CUE表秒數也依此表）")
    return out


def _ragic_preview(orders, signback, materials, link=None):
    """仿 Ragic 表單畫出每一波會寫入的內容。link：連動欄的預期值（如產業別，取自客戶主檔）。"""
    import ragic_order_preview as rp
    sign_name = getattr(signback, "name", signback) or ""
    mats = [{"廣告篇名": m.get("廣告篇名", ""), "音檔": getattr(m.get("音檔"), "name", ""),
             "文案": getattr(m.get("文案"), "name", "")} for m in materials or []]
    tabs = st.tabs([f"第{d.波段}波" for d in orders]) if len(orders) > 1 else [st.container()]
    for d, tab in zip(orders, tabs):
        with tab:
            st.html(rp.order_html(d, attachments={"cue": "（存檔時產生的 CUE Excel）", "sign": sign_name},
                                  materials=mats, total_waves=len(orders), link=link))


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


@st.cache_data(ttl=3600, show_spinner=False)
def _notify_defaults():
    return rf.notify_defaults()


def _order_extra(p):
    """送出參數 → build_orders 的訂檔補充欄位。"""
    return {"客戶類別": p.get("客戶類別", ""), "客服": p.get("客服") or None, "播證名稱": p.get("播證名稱") or None,
            "需求說明": p.get("需求說明", ""), "notify": _notify_defaults(),
            "現折": p.get("現折"), "退佣": p.get("退佣"), "文案": p.get("文案") or None, "素材走法": p.get("素材走法", ""),
            "素材": [{"廣告篇名": n} for n in p.get("素材") or []],
            "收入": p.get("收入") or None, "電台": p.get("電台") or None}


def _orders(snap, p, applicant):
    """送出參數 → 各波 OrderDraft（帶目前的 CUE號 摘要）。"""
    from ragic_booking import order_from_cue as oc
    fmt = lambda d: d.strftime("%Y/%m/%d") if d else ""   # noqa: E731
    return oc.build_orders(snap, applicant=applicant, company=p.get("公司", ""), category=p.get("類別", "商品"),
                           收款日期=fmt(p.get("收款日期")), 發票開立日=fmt(p.get("發票開立日")),
                           cue_apply=oc.current_cue(snap), **_order_extra(p))


def _order_customer(snap, key_prefix, last, bind_session):
    """① 客戶：沒帶客戶時就地搜尋；連動欄（客戶類別、付款條件…）只顯示；客服每張訂檔可調。回傳 (客戶類別, 客服)。"""
    cust = snap.get("customer") or {}
    st.markdown("**① 客戶**")
    if cust.get("編號"):
        st.caption(f"✅ {cust['編號']} {cust.get('名稱', '')}｜業務 {cust.get('業務') or '—'}｜主管 {cust.get('主管') or '—'}")
    else:
        st.caption("⚠️ 還沒帶入 Ragic 客戶，直接在這裡搜尋（等同頁面最上方「🔎 從 Ragic 帶入客戶」）。")
        q = st.text_input("輸入統一編號、客戶名稱或客戶編號", key=f"{key_prefix}_od_cust_q")
        if q.strip():
            try:
                found = _search(q.strip())
            except Exception as e:  # noqa: BLE001
                found = None
                st.error(f"查詢 Ragic 失敗：{e}")
            if found:
                idx = st.selectbox(f"找到 {len(found)} 筆", range(len(found)), format_func=lambda i: _cust_label(found[i]),
                                   key=f"{key_prefix}_od_cust_pick")
                if st.button("帶入這個客戶", key=f"{key_prefix}_od_cust_apply", type="primary"):
                    st.session_state[f"{key_prefix}_od_cust_val"] = found[idx]
                    if bind_session:
                        st.session_state[SS_CUSTOMER] = found[idx]
                        st.session_state[SS_CUST_FILL] = found[idx]
                    st.rerun()
            elif found is not None:
                st.info("查無此客戶，請到頁面最上方「➕ 新增客戶到 Ragic」。")
    c1, c2 = st.columns(2)
    cat = cust.get("類別") or ""
    if cust.get("編號"):
        c1.caption("🔗 以下由 Ragic 依客戶編號連動帶入（不在這裡改，要改請改客戶主檔）")
        c1.caption(f"客戶類別：{cat or '⚠️ 主檔空白'}｜付款條件：{cust.get('付款條件') or '—'}｜"
                   f"產業別：{cust.get('產業別') or '—'}｜統編：{cust.get('統編') or '—'}")
        if not cat:
            c1.warning(f"客戶主檔 {cust['編號']} 的「客戶類別」空白：請到 Ragic 客戶表補上（直客／廣代…），再重新帶入客戶。")
    base = list(cust.get("客服") or [])
    dcs = list(last.get("客服") or base)
    opts = list(dict.fromkeys(dcs + base + _options("客服")))
    cserv = c2.multiselect("客服（可多選）", opts, default=dcs, key=f"{key_prefix}_od_cs", accept_new_options=True)
    return cat, cserv


def _material_inputs(key_prefix, update=False):
    """素材子表（選填，一支一列）：音檔可多選、篇名預設檔名、文案檔選填；素材後補可只寫篇名。
    回傳 [{"廣告篇名", "音檔": UploadedFile|None, "文案": UploadedFile|None}]（列序＝送出的子表列號）。"""
    st.caption("素材（選填，可多支；還沒拿到素材可先不放，之後再送出更新" + ("，本次放的會往下新增列）" if update else "）"))
    auds = st.file_uploader("素材音檔（可多選，一檔一列）", accept_multiple_files=True, key=f"{key_prefix}_od_aud") or []
    rows = []
    for i, f in enumerate(auds):
        c1, c2 = st.columns([3, 2])
        stem = os.path.splitext(f.name)[0]
        name = c1.text_input(f"第{i + 1}支 廣告篇名", value=stem, key=f"{key_prefix}_od_aud_name_{i}").strip() or stem
        cp = c2.file_uploader(f"第{i + 1}支 文案（選填）", key=f"{key_prefix}_od_aud_cp_{i}")
        rows.append({"廣告篇名": name, "音檔": f, "文案": cp})
    names = st.text_area("只有篇名、素材後補（一行一支，選填）", key=f"{key_prefix}_od_mat_names", height=68)
    rows += [{"廣告篇名": x.strip(), "音檔": None, "文案": None} for x in names.splitlines() if x.strip()]
    return rows


def _cue_box(snap, key_prefix, cue_saver, serial=""):
    """⓪ CUE號：先申請（或沿用已申請的）CUE號，再送出訂檔（spec docs/specs/訂檔流程_兩段式.md）。
    cue_saver(fn)：把 fn(快照副本) 改過的快照寫回 cue/2，回傳有 ok／error 的結果；None＝尚未存檔或有未存修改。"""
    from ragic_booking import order_from_cue as oc
    st.markdown("**⓪ CUE號**（先申請 CUE號，再送出訂檔）")
    ca = oc.current_cue(snap)
    if ca.get("cue_id"):
        info = "｜".join(f"{k} {ca[k]}" for k in ("客戶名稱", "產品名稱", "業務", "主管") if ca.get(k))
        st.success(f"✅ CUE號 **{ca['cue_id']}**" + (f"｜{info}（Ragic 申請表讀回，訂檔以此為準）" if info else ""))
        if oc.cue_mismatch(snap):
            st.error(oc.cue_mismatch(snap))
        if cue_saver and not snap.get("booking") and st.button("放棄這個 CUE號（改申請新的）", key=f"{key_prefix}_cue_drop",
                                                              help="只解除這份 CUE 與該 CUE號 的關聯；Ragic 申請表的紀錄請自己刪除。"):
            _cue_save(cue_saver, lambda s: s.pop("cue_apply", None), f"已放棄 CUE號 {ca['cue_id']}，請到 Ragic 申請表刪除該筆。")
        return
    if not cue_saver:
        st.caption("先按下方「💾 存檔到 Ragic」（且沒有未存的修改），才能申請 CUE號。")
        return
    cust = snap.get("customer") or {}
    miss = oc.missing(snap, [])["CUE號申請"]
    if not write_enabled() or not booking_enabled():
        miss = miss + ["訂檔寫入未開放"]
    c1, c2 = st.columns([1, 2])
    if c1.button("🎫 申請 CUE號", key=f"{key_prefix}_cue_apply", type="primary", disabled=bool(miss),
                 help=("尚缺：" + "、".join(m.split("（")[0] for m in miss)) if miss else
                 f"以客戶 {cust.get('編號', '')} 向 Ragic「新增CUE號申請表」申請；申請完才送出訂檔。"):
        applicant = reg_owner_name(snap) or (current_user() or {}).get("name", "")
        with st.spinner("申請 CUE號中…"):
            r = oc.apply_cue(snap, applicant=applicant, serial=serial)
        if not r["ok"]:
            st.error(f"CUE號申請失敗：{r['error']}")
            return
        _cue_save(cue_saver, lambda s: s.__setitem__("cue_apply", r["cue_apply"]),
                  f"✅ 已申請 CUE號 {r['cue_apply']['cue_id']}" + (f"（{r['warning']}）" if r["warning"] else ""))
    with c2.popover("已在 Ragic 申請過 CUE號？"):
        cid = st.text_input("輸入 CUE號（如 1151108）", key=f"{key_prefix}_cue_exist")
        if st.button("沿用這個 CUE號", key=f"{key_prefix}_cue_use", disabled=not cid.strip()):
            r = oc.use_existing_cue(snap, cid.strip())
            if not r["ok"]:
                st.error(r["error"])
                return
            _cue_save(cue_saver, lambda s: s.__setitem__("cue_apply", r["cue_apply"]), f"✅ 已沿用 CUE號 {cid.strip()}")


def _cue_save(cue_saver, fn, msg):
    res = cue_saver(fn)
    if not res.ok:
        st.error(f"CUE號已處理，但寫回存檔失敗：{res.error}（請記下 CUE號並通知 Jonathan）")
        return
    st.session_state["_cue_msg"] = msg
    st.rerun()


def render_order_preview(snap, key_prefix, prev_review=None, update=False, bind_session=True, cue_saver=None, serial=""):
    """訂檔資料（宜歆 10/21：缺欄要能就地補、寫清楚去哪填；spec docs/specs/訂檔資料補齊.md）。
    ① 客戶（搜尋帶入、客戶類別、客服）② 開票收款 ③ 播證／通知 ④ 子表格（收入、需求說明）＋回簽檔。
    在這裡帶入的客戶會寫進 snap["customer"]（呼叫端送出時用同一份 snap）。
    回傳 {"params", "missing", "signback"} 供「送出訂檔」使用；欄位預設帶上次送出的值。"""
    import cue_store as cs
    from datetime import date as _date

    from ragic_booking import order_from_cue as oc
    last = cs.from_jsonable((prev_review or {}).get("params") or {})
    picked = None if bind_session else st.session_state.get(f"{key_prefix}_od_cust_val")   # 編輯模式改走 SS_CUSTOMER
    if picked and not (snap.get("customer") or {}).get("編號"):
        snap["customer"] = cs.to_jsonable(picked)
    out = {"params": {}, "missing": [], "signback": None}
    title = "🧾 訂檔資料（送出即更新原訂檔）" if update else "🧾 訂檔資料（送出即申請 CUE號、建立訂檔＝成交）"
    if st.session_state.get("_cue_msg"):
        st.info(st.session_state.pop("_cue_msg"))
    with st.expander(title, expanded=not oc.current_cue(snap).get("cue_id")):
        u = current_user() or {}
        _cue_box(snap, key_prefix, cue_saver, serial=serial)
        st.caption("🔄 自動取自 CUE（不用填）：平台、CUE表秒數、CUE表總檔數、執行起迄、產品名稱、波段數、"
                   "收入子表（每平台＋秒數一列：檔數、實收未稅、業績年月、製作費）；通知部門／個人依平台。")
        ccat, cserv = _order_customer(snap, key_prefix, last, bind_session)

        st.markdown("**② 開票收款**")
        c1, c2, c3, c4 = st.columns(4)
        opts = [""] + COMPANY_OPTIONS
        dflt = last.get("公司") or oc.default_company(snap)
        company = c1.selectbox("公司", opts, index=opts.index(dflt) if dflt in opts else 0, key=f"{key_prefix}_od_company")
        cats = oc.INCOME_CATEGORIES
        dcat2 = last.get("類別") if last.get("類別") in cats else oc.default_category(snap)
        category = c2.selectbox("收入類別", cats, index=cats.index(dcat2), key=f"{key_prefix}_od_cat",
                                help="預設：公家機關客戶＝公家、統一相關＝統一、其餘商品；交換合約請改「交換」。")
        pays = oc.wave_pay_dates(snap)
        pay = c3.date_input("收款日期" + ("（空白＝付款兌現日）" if any(pays) else ""), value=last.get("收款日期"),
                            key=f"{key_prefix}_od_pay",
                            help="填了就各波都用這天；空白則各波用 CUE 上的付款兌現日。打完日期請按 Enter 或點選日曆。")
        inv = c4.date_input("發票開立日（選填）", value=last.get("發票開立日"), key=f"{key_prefix}_od_inv")
        cust = snap.get("customer") or {}
        d1, d2, _sp = st.columns([1, 1, 2])
        disc = d1.text_input("現折（小數，2% 填 0.02）", value=str(last.get("現折") or oc.pct(cust.get("現折")) or "0"),
                             key=f"{key_prefix}_od_disc", help="訂檔必填；客戶主檔多半空白，沒有現折就是 0。")
        rebate = d2.text_input("退佣（小數，20% 填 0.2）", value=str(last.get("退佣") or oc.pct(cust.get("退佣")) or "0"),
                               key=f"{key_prefix}_od_rebate", help="訂檔必填；預設帶客戶主檔的退佣%。")
        if not pay and any(pays):
            st.caption("收款日期依 CUE 付款兌現日：" + "；".join(
                (f"第{i}波 " if len(pays) > 1 else "") + (d or "（無）") for i, d in enumerate(pays, 1)))

        st.markdown("**③ 播證／通知**")
        waves = snap.get("waves", [])
        cert_default = oc.default_cert_name(snap)
        last_cert = last.get("播證名稱")
        same = True
        if len(waves) > 1:
            same = st.checkbox("各波播證名稱相同", value=not isinstance(last_cert, list), key=f"{key_prefix}_od_cert_same")
        if same:
            cert = st.text_input("電台播證開立名稱", value=last_cert if isinstance(last_cert, str) else "",
                                 placeholder=cert_default or "廣告主-產品", key=f"{key_prefix}_od_cert",
                                 help=f"留空＝{cert_default or '（客戶名稱、產品都空白，請填寫）'}；廣代案寫廣告主，不是代理商。"
                                 ).strip()
        else:
            cert = []
            for i, _w in enumerate(waves):
                lv = last_cert[i] if isinstance(last_cert, list) and i < len(last_cert) else ""
                cert.append(st.text_input(f"第{i + 1}波 電台播證開立名稱", value=lv, placeholder=cert_default,
                                          key=f"{key_prefix}_od_cert_{i}").strip())
        if same and not cert and cert_default:
            st.caption(f"電台播證開立名稱留空＝{cert_default}")

        fmt = lambda d: d.strftime("%Y/%m/%d") if d else ""   # noqa: E731
        st.markdown("**④ 訂檔收入相關資訊**（照 CUE 預填；可改格、可加列，例如廣播、其他）")
        base = oc.build_orders(snap, applicant=u.get("name", ""), company=company, category=category,
                               收款日期=fmt(pay), 發票開立日=fmt(inv))
        income = _income_editor(base, key_prefix)
        stations = []
        if any(r.get("平台細項") == "廣播" for rows in income for r in rows):
            stations = st.multiselect("電台（平台有廣播才需要）", _order_opts("電台"), key=f"{key_prefix}_od_station",
                                      accept_new_options=True)

        st.markdown("**⑤ 素材及需求**")
        materials = _material_inputs(key_prefix, update)
        has_audio = any(m.get("音檔") for m in materials)
        need_def = f"{_date.today():%m/%d} " + ("更新 CUE 表" if update else "提供訂檔CUE表+回簽") + (
            f"及素材{sum(1 for m in materials if m.get('音檔'))}支" if has_audio else ("" if update else "，素材後補"))
        need = st.text_input("需求或狀況說明（新增一列；可留白）", value=need_def, key=f"{key_prefix}_od_need",
                             help="寫進訂檔「需求或狀況說明」子表；更新訂檔時是往下加一列，不會蓋掉營運寫的。")
        m1, m2 = st.columns(2)
        n_audio = sum(1 for m in materials if m.get("音檔"))
        auto_note = oc.default_material_note(n_audio)
        mat = m1.text_input("素材走法（選填）", value=str(last.get("素材走法") or ""), key=f"{key_prefix}_od_mat",
                            placeholder=auto_note or "例：單支素材無走法／兩支素材平均輪播",
                            help="留空＝依素材支數自動（1 支＝單支素材無走法、多支＝N支素材平均輪播）。")
        mat = mat.strip() or auto_note
        cw_def = list(last.get("文案") or ["無"])
        cw = m2.multiselect("文案人員", list(dict.fromkeys(["無"] + cw_def)), default=cw_def, key=f"{key_prefix}_od_cw",
                            accept_new_options=True, help="有請文案寫稿就選／輸入文案人員，沒有就是「無」。")
        sign = st.file_uploader("客戶回簽檔（送出必附）", type=["pdf", "jpg", "jpeg", "png"], key=f"{key_prefix}_od_sign",
                                help="客戶回簽後的 CUE（PDF 或照片）；已送出過可不重傳，沿用上次的檔案。")
        if (prev_review or {}).get("signback") and not sign:
            st.caption(f"已附客戶回簽檔：{prev_review['signback']}")
        params = {"公司": company, "類別": category, "收款日期": pay, "發票開立日": inv,
                  "客戶類別": ccat, "客服": cserv, "播證名稱": cert, "需求說明": need.strip(),
                  "現折": disc.strip(), "退佣": rebate.strip(), "文案": [x for x in cw if x] or ["無"],
                  "素材走法": mat.strip(), "素材": [m["廣告篇名"] for m in materials],
                  "收入": income, "電台": stations}
        orders = _orders(snap, params, u.get("name", ""))
        if orders:
            st.caption(f"通知（依平台自動）：{orders[0].通知部門}｜{'、'.join(orders[0].通知個人)}")
        _order_lines(orders)
        if st.toggle("👀 預覽送出 Ragic 畫面", key=f"{key_prefix}_od_preview"):
            _ragic_preview(orders, sign or (prev_review or {}).get("signback"), materials,
                           link={"產業別": (snap.get("customer") or {}).get("產業別", "")})
        miss = oc.missing(snap, orders)
        missing = list(dict.fromkeys(miss["CUE號申請"] + miss["訂檔"]))
        if missing:
            st.warning("送出前還缺：\n" + "\n".join(f"- {x}" for x in missing))
        else:
            st.success("訂檔必填欄位齊全。")
        with st.popover("檢視將寫入 Ragic 的欄位"):
            st.json({"CUE號申請（forms13/4）": oc.cue_apply_payload(snap, u.get("name", "")),
                     "訂檔（forms12/17）": [rf.order_payload_json(d) for d in orders]})
        out = {"params": params, "missing": missing, "signback": sign, "materials": materials, "orders": orders}
    return out
