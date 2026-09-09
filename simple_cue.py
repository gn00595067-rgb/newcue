# -*- coding: utf-8 -*-
"""
簡易模式 v2 UI（Streamlit）—— 三步：選組合 → 輸預算 → 選開始日，自動出預覽（§9）

計算走 simple_model.build_model；Excel 走 simple_excel.render；預覽走 simple_html。
內部成本不出現在客戶檔案；Google Sheet 斷線用內建備援並警示，不 crash。
"""
from datetime import date, timedelta

import streamlit as st
import streamlit.components.v1 as components

import simple_config as sc
import simple_model as sm
import simple_excel as se
import simple_html as shtml
import simple_preview as spv
from utils import safe_filename
from pdf_converter import xlsx_bytes_to_pdf_bytes

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# =============================================================================
# 資料來源：把 app 傳入的雲端設定轉成 SheetData；缺漏處以內建備援補
# =============================================================================
def _to_sheetdata(store_counts_num, pricing_db, sec_factors):
    fb = sm.fallback_sheetdata()
    try:
        pricing = {}
        # 全家廣播 / 新鮮視
        for media in ("全家廣播", "新鮮視"):
            md = pricing_db.get(media) if pricing_db else None
            if not md:
                pricing[media] = fb.pricing[media]
                continue
            std_map = md.get("_Region_Std_Spots", {})
            regs = {}
            for region in ["全省"] + list(sc.REGIONS_ORDER):
                cell = md.get(region)
                if isinstance(cell, list) and len(cell) >= 2:
                    regs[region] = {"List": cell[0], "Net": cell[1],
                                    "Std": std_map.get(region, fb.pricing[media][region]["Std"])}
                elif region in fb.pricing[media]:
                    regs[region] = fb.pricing[media][region]
            pricing[media] = regs
        # 家樂福
        cf = pricing_db.get("家樂福") if pricing_db else None
        if cf:
            pricing["家樂福"] = {}
            for k in ("量販_全省", "超市_全省"):
                c = cf.get(k)
                if c:
                    pricing["家樂福"][k] = {"List": c["List"], "Net": c["Net"], "Std": c["Std_Spots"]}
                else:
                    pricing["家樂福"][k] = fb.pricing["家樂福"][k]
        else:
            pricing["家樂福"] = fb.pricing["家樂福"]

        stores = {}
        scn = store_counts_num or {}
        stores["全家廣播"] = {r: int(scn.get(r, fb.stores["全家廣播"][r])) for r in sc.REGIONS_ORDER}
        stores["新鮮視"] = {r: int(scn.get(f"新鮮視_{r}", fb.stores["新鮮視"][r])) for r in sc.REGIONS_ORDER}
        stores["家樂福"] = {"量販": int(scn.get("家樂福_量販", fb.stores["家樂福"]["量販"])),
                          "超市": int(scn.get("家樂福_超市", fb.stores["家樂福"]["超市"]))}

        factors = {m: dict(sec_factors.get(m, fb.factors[m])) for m in ("全家廣播", "新鮮視", "家樂福")} \
            if sec_factors else {m: dict(fb.factors[m]) for m in fb.factors}
        return sm.SheetData(pricing=pricing, factors=factors, stores=stores,
                            agency_pricing=None, from_fallback=False), None
    except Exception as e:  # noqa: BLE001 — 任何轉換失敗都退回備援，不可 crash
        return fb, str(e)


@st.cache_data(ttl=600, show_spinner=False)
def _generate(combo_key, budget, start_iso, end_iso, client, tax_id, product,
              sales, campaign, prod_cost, made_iso, _data, regions=None,
              party_a="", party_a_tax="", payment_date=""):
    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)
    model = sm.build_model(combo_key, budget, start, end, client=client, tax_id=tax_id,
                           product=product, sales=sales, campaign=campaign,
                           prod_cost=prod_cost, today=date.fromisoformat(made_iso), data=_data,
                           regions=list(regions) if regions else None,
                           party_a=party_a, party_a_tax=party_a_tax, payment_date=payment_date)
    xlsx = se.render(model, formulas=True)
    xlsx_val = se.render(model, formulas=False)
    htmls = shtml.render_html(model)
    return model, xlsx, xlsx_val, htmls


def _next_monday_after(days_ahead=10):
    d = date.today() + timedelta(days=days_ahead)
    while d.weekday() != 0:
        d += timedelta(days=1)
    return d


def _pills(label, options, fmt, key, default_index=0):
    """st.pills（Streamlit≥1.40）；不支援時退回 radio。"""
    try:
        val = st.pills(label, options, format_func=fmt, key=key,
                       default=options[default_index], selection_mode="single")
        return val if val is not None else options[default_index]
    except Exception:
        return st.radio(label, options, format_func=fmt, key=key + "_r",
                        index=default_index, horizontal=True)


# =============================================================================
# 主 UI
# =============================================================================
def render_simple_cue(store_counts_num=None, pricing_db=None, sec_factors=None,
                      regions_order=None, sales_map=None):
    st.title("⚡ 一鍵 CUE")
    st.caption("選平台組合 → 輸入預算 → 選開始日，立即顯示與公司範本一致的預覽，可下載 Excel／PDF。")

    data, err = _to_sheetdata(store_counts_num, pricing_db, sec_factors)
    if err or data.from_fallback:
        st.warning(f"設定檔讀取異常，改用內建備援價格（{sc.SHEET_FALLBACK_DATE}）。"
                   + (f"（{err}）" if err else ""))

    # 【1】平台組合
    st.markdown("**【1】平台組合**")
    all_keys = sc.SUBSIDIARY_COMBOS + sc.AGENCY_COMBOS
    combo_key = _pills("平台組合", all_keys, lambda k: sc.COMBOS[k]["label"],
                       key="simple_combo")
    st.caption("　" + sc.COMBOS[combo_key]["hint"])

    # 【2】預算
    st.markdown("**【2】預算（未稅 Net）**")
    if "simple_budget2" not in st.session_state:
        st.session_state["simple_budget2"] = 250000
    try:
        pick = st.pills("常用預算", sc.BUDGET_PRESETS,
                        format_func=lambda a: f"{a // 10000}萬",
                        selection_mode="single", key="budget_pills")
        if pick:
            st.session_state["simple_budget2"] = pick
    except Exception:
        bc0 = st.columns(len(sc.BUDGET_PRESETS))
        for i, amt in enumerate(sc.BUDGET_PRESETS):
            if bc0[i].button(f"{amt // 10000}萬", key=f"bp_{amt}"):
                st.session_state["simple_budget2"] = amt
    bc = st.columns([2, 3])
    budget = bc[0].number_input(
        "金額", min_value=10000, step=10000,
        value=int(st.session_state["simple_budget2"]), format="%d",
        label_visibility="collapsed")
    st.session_state["simple_budget2"] = int(budget)
    bc[1].markdown(f"含 5% 稅約 **${int(round(budget * 1.05)):,}**")

    # 【3】走期
    st.markdown("**【3】走期**")
    d1, d2, d3 = st.columns([2, 2, 2])
    with d1:
        start = st.date_input("開始日", value=_next_monday_after(), format="YYYY-MM-DD")
    with d2:
        weeks = st.select_slider("週數", options=list(range(1, sc.MAX_WEEKS + 1)), value=2)
    default_end = start + timedelta(days=weeks * 7 - 1)
    with d3:
        end = st.date_input("結束日", value=default_end, format="YYYY-MM-DD")
    if end < start:
        end = default_end
    ndays = (end - start).days + 1
    sign = start - timedelta(days=7)
    st.caption(f"　共 {ndays} 天，回簽 {sign:%m/%d}、素材 {sign:%m/%d} 前")
    if ndays > sc.MAX_DAYS:
        st.error(f"簡易模式單張最多 {sc.MAX_WEEKS} 週（{sc.MAX_DAYS} 天）；"
                 "更長走期請用一般 CUE 分月製作。")
        return
    if start < date.today() + timedelta(days=7):
        st.warning("距上檔不足 7 天，回簽／素材時程可能來不及。")

    # 甲乙方／付款／其他（收合）
    with st.expander("甲乙方／付款／產品／其他（可留白）"):
        st.caption("甲方＝我方（供應商）、乙方＝客戶；付款兌現日期預設為佔位，可直接改成實際日期。")
        pcol = st.columns(2)
        party_a = pcol[0].text_input("甲方名稱（我方）", "")
        party_a_tax = pcol[0].text_input("甲方統一編號", "")
        client = pcol[1].text_input("乙方／客戶名稱", "")
        tax_id = pcol[1].text_input("乙方統一編號", "")

        default_pay = f"{start.year - 1911}.XX.XX"
        e1, e2, e3 = st.columns(3)
        payment_date = e1.text_input("付款兌現日期（民國，可留白）", default_pay)
        product = e2.text_input("產品名稱", "")
        sales_options = list(sales_map.keys()) if sales_map else []
        sales_name = e2.selectbox("業務", ["—"] + sales_options) if sales_options else "—"
        # 下拉顯示姓名、傳暱稱給 model（檔名用暱稱，§3-1）
        sales = "" if sales_name == "—" else (sales_map.get(sales_name) or sales_name)
        prod_cost = e3.number_input("製作費（未稅）", min_value=0, value=0, step=1000)
        campaign = e3.text_input("Campaign（2008 用）", "")

    # 進階：指定投放區域（僅子公司；含全家企頻／新鮮視的區塊才有分區）
    regions = ()
    combo_def = sc.COMBOS[combo_key]
    region_medias = [m for m in combo_def.get("blocks", []) if m in ("全家廣播", "新鮮視")]
    if region_medias and combo_def["family"] == "subsidiary":
        disp = "／".join(sc.PLATFORM_DISPLAY[m] for m in region_medias)
        with st.expander("🌏 進階：指定投放區域（預設全省）"):
            st.caption(f"僅影響 {disp} 區塊。留空＝全省（套裝價）；勾選特定區域＝只投該區，"
                       "預算集中、以各區牌價加總試算檔次。（家樂福不分區，不受影響）")
            picked = st.multiselect(
                "投放區域", options=list(sc.REGIONS_ORDER),
                format_func=lambda r: sc.REGION_LABELS.get(r, r),
                default=[], key="simple_regions")
            regions = tuple(r for r in sc.REGIONS_ORDER if r in picked)
            if regions and len(regions) < len(sc.REGIONS_ORDER):
                st.info("已指定 " + "、".join(sc.REGION_LABELS[r] for r in regions)
                        + f"（共 {len(regions)} 區）—— 非全省，分區聚合規則待老闆確認。")

    st.divider()
    if budget <= 0 or ndays <= 0:
        st.error("請輸入正確的預算與走期。")
        return

    try:
        with st.spinner("產生中…"):
            model, xlsx, xlsx_val, htmls = _generate(
                combo_key, int(budget), start.isoformat(), end.isoformat(),
                client, tax_id, product, sales, campaign, int(prod_cost),
                date.today().isoformat(), data, regions,
                party_a=party_a, party_a_tax=party_a_tax, payment_date=payment_date)
    except Exception as e:  # noqa: BLE001
        st.error(f"產生失敗：{e}")
        st.exception(e)
        return

    # 摘要
    s0 = model.sheets[0]
    grand = s0.fees.get("grand") or s0.fees.get("total")
    total_spots0 = sum(r.spots for b in s0.blocks for r in b.rows)
    m = st.columns(5)
    m[0].metric("秒數版本", f"{len(model.sheets)}")
    m[1].metric("走期天數", f"{ndays}")
    m[2].metric("Package (Net)", f"${int(budget):,}")
    m[3].metric("Grand Total", f"${int(grand):,}")
    m[4].metric("總檔次（首版）", f"{total_spots0:,}")

    # 下載
    #   主要：值版 —— 開啟即見數字（公式版在 Excel 受保護檢視/未重算時 rate 會空白）
    #   次要：公式版 —— 業務可改每日檔次讓 rate/Total 自動更新
    fname = safe_filename(model.filename)
    # edit_fname = safe_filename(fname.replace(".xlsx", "-可編輯.xlsx"))  # 可編輯版隱藏中
    dc = st.columns(4)
    dc[0].download_button("⬇ 下載 Excel（開啟即見數字）", data=xlsx_val, file_name=fname,
                          mime=_XLSX_MIME, type="primary")
    # 「可編輯版（改檔次自動加總）」先隱藏（保留產出與程式碼，恢復即取消註解）
    # dc[1].download_button("⬇ 可編輯版（改檔次自動加總）", data=xlsx, file_name=edit_fname,
    #                       mime=_XLSX_MIME)
    if spv.has_soffice():
        pdf, _tag, _msg = xlsx_bytes_to_pdf_bytes(xlsx_val, fname)
        if pdf:
            dc[2].download_button("⬇ 下載 PDF", data=pdf,
                                  file_name=safe_filename(fname.replace(".xlsx", ".pdf")),
                                  mime="application/pdf")
        else:
            dc[2].caption(f"（PDF 產生失敗：{_msg}）")
    if dc[3].button("🔁 重新整理設定檔"):
        st.cache_data.clear()
        st.rerun()

    # 預覽（每秒數一個 tab）：優先 PDF 頁面影像，否則退回 HTML
    pngs = None
    if spv.has_soffice():
        with st.spinner("產生預覽…"):
            pngs = spv.xlsx_to_page_pngs(xlsx_val)
        if pngs is not None and len(pngs) != len(model.sheets):
            st.info(f"PDF 頁數（{len(pngs)}）與分頁數（{len(model.sheets)}）不符，改用網頁預覽。")
            pngs = None

    tabs = st.tabs([f"{s.seconds}秒版" for s in model.sheets])
    for idx, (tab, (title, html), sheet) in enumerate(zip(tabs, htmls, model.sheets)):
        with tab:
            total_spots = sum(r.spots for b in sheet.blocks for r in b.rows)
            g = sheet.fees.get("grand") or sheet.fees.get("total")
            st.caption(f"{sheet.seconds}秒版 ｜ 總檔次 {total_spots:,} ｜ Grand Total ${int(g):,}")
            if pngs is not None:
                st.image(pngs[idx], use_container_width=True)
            else:
                components.html(html, height=shtml.estimate_height(sheet), scrolling=True)
            with st.expander("檔次明細（僅供業務/主管，不進客戶檔案）"):
                for blk in sheet.blocks:
                    disp = sc.PLATFORM_DISPLAY.get(
                        {"全家廣播": "全家廣播", "新鮮視": "新鮮視", "家樂福": "家樂福量販"}
                        .get(blk.platform, blk.platform), blk.platform)
                    main = next((r for r in blk.rows if r.kind == "main"), blk.rows[0])
                    st.write(f"**{disp}**：主檔次 {main.spots:,}／每日 {main.schedule[0] if main.schedule else 0}")
                if model.family == "subsidiary":
                    fill = sheet.hidden_net_total / sheet.budget * 100 if sheet.budget else 0
                    st.caption(f"隱藏實收 ${int(sheet.hidden_net_total):,}／填滿率 {fill:.1f}%"
                               f"｜總曝光 {sheet.reach['impressions']:,}"
                               f"｜預估人流 {sheet.reach['traffic']:,}")
