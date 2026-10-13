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
SS_RECORD = "cue_record"   # 目前編輯中的 Ragic 存檔 {"rid","serial","mode","snap"}

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


def render_save_panel(snap, *, files=None, legacy_details="", extra_fields=None, key_prefix="save",
                      allow_style_excel=True):
    """存檔到 Ragic（cue/2）。同一份 CUE 再存＝更新同一筆、版本 +1，異動寫進快照 history。
    files：{"xlsx": (檔名, bytes), "pdf": (檔名, bytes)}，或回傳該 dict 的函式（存檔時才產生）。
    未開 RAGIC_WRITE_ENABLED 時只乾跑。"""
    import cue_store as cs
    from config import RAGIC_MAP
    from ragic_booking import cue2

    st.markdown("---")
    st.markdown("#### ☁️ 存檔到 Ragic")
    msg_key = f"{key_prefix}_saved_msg"
    rec = st.session_state.get(SS_RECORD)
    linked = rec if rec and rec.get("mode") == snap.get("mode") else None
    pv = ((linked or {}).get("snap") or {}).get("version", 0)
    # 「改了還沒存」：與已存版本比對（側欄「我的 CUE」也讀這個旗標）
    dirty = bool(linked) and cs.has_changes(linked.get("snap"), snap)
    st.session_state["_cue_dirty"] = dirty
    if dirty:
        st.warning(f"⚠️ 內容已修改，尚未存檔（Ragic 上目前是 v{pv}）")
    elif st.session_state.get(msg_key):
        st.success(st.session_state[msg_key])

    u = current_user()
    if not u:
        st.caption("以 Ragic 帳號登入後可存檔；存檔後可在左側「📂 我的 CUE」找回、修改。")
        return

    as_new = True
    if linked:
        choice = st.radio("存檔方式", [f"更新 #{linked.get('serial') or linked['rid']}（v{pv} → v{pv + 1}）",
                                       "另存為新的一筆"], key=f"{key_prefix}_how", horizontal=True)
        as_new = choice.startswith("另存")
        if not as_new:
            st.caption("本次異動：" + "；".join(cs.diff_summary(linked.get("snap"), snap)))
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

    prev = None if as_new else linked.get("snap")
    final = cs.next_version(prev, json_copy(snap), u["name"])
    fields = cs.ragic_fields(final, RAGIC_MAP, extra_fields)
    fields[RAGIC_MAP["details"]] = cs.details_text(final, legacy_details)

    live = write_enabled()
    with st.popover("👀 預覽將寫入 Ragic 的內容"):
        st.json({"動作": "新建" if as_new else f"更新紀錄 {linked['rid']}",
                 "欄位": {k: (v if k != RAGIC_MAP["details"] else f"（{len(v):,} 字，含快照 v{final['version']}）")
                        for k, v in fields.items()},
                 "附件": (["（存檔時合併各波 Excel／PDF）"] if callable(files) else
                        [f[0] for f in (files or {}).values() if f]) + ([style.name] if style else []),
                 "異動紀錄": final["history"][-1]})
    if not live:
        st.info("目前為**乾跑模式**：只預覽、不會寫入 Ragic。")
    render_order_preview(final, key_prefix)
    if not st.button("💾 存檔到 Ragic", key=f"{key_prefix}_btn", type="primary", disabled=not live):
        return
    up = {}
    if callable(files):   # 合併多波附件較耗時，只在按下存檔時才產生
        with st.spinner("合併附件中…"):
            files = files()
    xl, pdf = (files or {}).get("xlsx"), (files or {}).get("pdf")
    if xl:
        up[RAGIC_MAP["file_xls"]] = (xl[0], xl[1], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if pdf and pdf[1]:
        up[RAGIC_MAP["file_pdf"]] = (pdf[0], pdf[1], "application/pdf")
    if style and RAGIC_MAP.get("file_style_xls"):
        up[RAGIC_MAP["file_style_xls"]] = (style.name, style.getvalue(), "application/octet-stream")
    url, key = _ragic_conn()
    with st.spinner("存檔中…"):
        res = cue2.save_record(url, key, fields, up, rid=None if as_new else linked["rid"])
    if not res.ok:
        st.error(f"存檔失敗：{res.error}")
        return
    st.session_state[SS_RECORD] = {"rid": res.rid, "serial": res.serial, "mode": snap.get("mode"), "snap": final}
    st.session_state[msg_key] = f"✅ 已存檔 #{res.serial or res.rid}（v{final['version']}）"
    st.cache_data.clear()
    st.rerun()


def clear_loaded():
    """解除與 Ragic 存檔的關聯，並清掉讀回時設定的覆寫值。"""
    for k in (SS_RECORD, "_simple_restore", "_cue_dirty"):
        st.session_state.pop(k, None)


def _rec_label(rec, snap):
    from config import RAGIC_FIELD_SERIAL, RAGIC_MAP
    h = snap.get("header", {})
    last = (snap.get("history") or [{}])[-1]
    return (f"#{rec.get(RAGIC_FIELD_SERIAL) or rec['_ragicId']} {h.get('client') or rec.get(RAGIC_MAP['client'], '')}"
            f" {h.get('product') or ''}｜{snap.get('mode')}｜v{snap.get('version')}｜{last.get('by', '')} {last.get('at', '')}")


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
    st.session_state["cue_mode"] = nav[0]
    if nav[1]:
        st.session_state["agency_sub_mode"] = nav[1]
    st.session_state[SS_RECORD] = {"rid": rec["_ragicId"], "serial": str(rec.get(RAGIC_FIELD_SERIAL) or ""),
                                   "mode": mode, "snap": snap}
    st.rerun()


# =============================================================================
# 第 4 期（預覽）：訂檔／CUE號申請內容
# =============================================================================
COMPANY_OPTIONS = ["東吳", "聲活", "鉑霖", "錄音室", "聲活(采藝)"]   # 訂檔表實際使用值


def render_order_preview(snap, key_prefix):
    """依目前 CUE 組出「CUE號申請」與各波「訂檔」將寫入的內容，只預覽、不送出。"""
    from ragic_booking import fields as rf
    from ragic_booking import order_from_cue as oc
    with st.expander("🧾 訂檔預覽（將來核准後會自動申請 CUE號、建訂檔；目前只預覽）", expanded=False):
        u = current_user() or {}
        h = snap.get("header", {})
        c1, c2, c3, c4 = st.columns(4)
        dflt = oc.COMPANY_FROM_FORMAT.get(h.get("format"), "")
        company = c1.selectbox("公司", [""] + COMPANY_OPTIONS,
                               index=([""] + COMPANY_OPTIONS).index(dflt) if dflt else 0, key=f"{key_prefix}_od_company")
        category = c2.selectbox("收入類別", oc.INCOME_CATEGORIES, key=f"{key_prefix}_od_cat")
        pay = c3.date_input("收款日期", value=None, key=f"{key_prefix}_od_pay")
        inv = c4.date_input("發票開立日", value=None, key=f"{key_prefix}_od_inv")
        orders = oc.build_orders(snap, applicant=u.get("name", ""), company=company, category=category,
                                 收款日期=pay.strftime("%Y/%m/%d") if pay else "",
                                 發票開立日=inv.strftime("%Y/%m/%d") if inv else "")
        miss = oc.missing(snap, orders)
        if miss["CUE號申請"] or miss["訂檔"]:
            st.warning("送訂檔前還缺：" + "、".join(x.split("（")[0] for x in miss["CUE號申請"] + miss["訂檔"]))
        else:
            st.success("訂檔必填欄位齊全（另需附：訂檔CUE表＝本 CUE Excel、客戶回簽檔）。")
        for i, d in enumerate(orders, 1):
            st.caption(f"第 {i} 波｜{d.執行開始日期}～{d.執行結束日期}｜" + "；".join(
                f"{r['平台細項']}{(' ' + str(r['秒數']) + '秒') if r['秒數'] else ''} "
                f"{r['平台檔數']:,}檔 ${r['實收金額未稅']:,}" for r in d.收入明細))
        st.button("📤 送出訂檔（申請 CUE號＋建立各波訂檔）", key=f"{key_prefix}_od_submit", disabled=True,
                  help="送出程式已備妥（order_from_cue.submit_booking）；審核方式（Ragic 原生簽核或 app 內審核）確定後開放。")
        with st.popover("檢視將寫入 Ragic 的欄位"):
            st.json({"CUE號申請（forms13/4）": oc.cue_apply_payload(snap, u.get("name", "")),
                     "訂檔（forms12/17）": [rf.order_payload_json(d) for d in orders]})
