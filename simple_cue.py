# -*- coding: utf-8 -*-
"""
簡易模式 (Simple / 一鍵 CUE)

目標：業務只需「選平台組合 + 輸入預算」，系統以聰明預設（全省、標準走期、
各秒數各出一版）自動產出對應 CUE，讓業務先看到範本、再回頭調走期與細節。

Phase 1：重用既有已驗證的計算與渲染管線
  - 子公司三組  → calculator.calculate_plan_data → excel_renderer.generate_excel_from_scratch
  - 代理商 2008/凱絡 → agency_cue.build_agency_model → agency_excel.generate_agency_excel
  對每個秒數各產一張 CUE（子公司 10/15/20/30；代理商依平台），提供逐張下載與 ZIP。

Phase 2（未做）：子公司改「一檔四分頁」+ 範本加強欄、家樂福→萬家福/樂家康改名、全面美化。
"""
import io
import zipfile
from datetime import date, timedelta

import streamlit as st

import config
from utils import get_remarks_text, safe_filename
from calculator import calculate_plan_data
from excel_renderer import generate_excel_from_scratch
from html_generator import generate_html_preview

import agency_cue as ac
from agency_excel import generate_agency_excel
from data_loader import load_agency_pricing_from_cloud


# =============================================================================
# 平台組合定義
# =============================================================================
# 子公司組合：media = calculator 用的媒體 key（"全家廣播"/"新鮮視"/"家樂福"）
#   註：範本中「企頻」與「全家」皆指全家店內廣播＝內部 key "全家廣播"。
#   家樂福已改名萬家福/樂家康，Phase 2 會改內部 key，Phase 1 先只改顯示。
SUB_COMBOS = {
    "sub_qp_fv":  {"label": "① 企頻 ＋ 新鮮視",
                   "media": ["全家廣播", "新鮮視"], "seconds": [10, 15, 20, 30]},
    "sub_qp_wjf": {"label": "② 全家 ＋ 萬家福．樂家康",
                   "media": ["全家廣播", "家樂福"], "seconds": [10, 15, 20, 30]},
    "sub_fv_wjf": {"label": "③ 新鮮視 ＋ 萬家福．樂家康",
                   "media": ["新鮮視", "家樂福"], "seconds": [10, 15, 20, 30]},
}

# 代理商組合：platform = "family"（全家單組）或 "wjf"（萬家福.樂家康單組）
AGENCY_COMBOS = {
    "ag_2008_fam":   {"label": "④ 2008傳媒 － 全家單組",
                      "agency": "2008傳媒", "platform": "family", "seconds": [10, 15, 20, 30]},
    "ag_2008_wjf":   {"label": "⑤ 2008傳媒 － 萬家福．樂家康單組",
                      "agency": "2008傳媒", "platform": "wjf", "seconds": [10, 15, 20]},
    "ag_carat_fam":  {"label": "⑥ 凱絡 － 全家單組",
                      "agency": "凱絡", "platform": "family", "seconds": [10, 15, 20, 30]},
    "ag_carat_wjf":  {"label": "⑦ 凱絡 － 萬家福．樂家康單組",
                      "agency": "凱絡", "platform": "wjf", "seconds": [10, 15, 20]},
}

BUDGET_PRESETS = [200000, 250000, 300000, 400000]   # 常用預算快捷（20/25/30/40萬）


# =============================================================================
# 子公司：組 config + 逐秒數產表
# =============================================================================
def _build_sub_config(media_keys, second, share_first):
    """組出 calculate_plan_data 需要的 config：全省、單一秒數 100%、兩平台預算佔比。"""
    shares = {media_keys[0]: share_first, media_keys[1]: 100 - share_first} if len(media_keys) == 2 \
        else {media_keys[0]: 100}
    cfg = {}
    for m in media_keys:
        cfg[m] = {
            "share": shares[m],
            "is_national": True,
            "regions": list(config.REGIONS_ORDER),
            "sec_shares": {second: 100},
        }
    return cfg


def _gen_subsidiary(combo, budget, start_dt, end_dt, share_first,
                    client, tax_id, product, sales, prod_cost, fmt,
                    pricing_db, sec_factors, store_counts_num):
    """回傳 [{sec, bytes, fname, html}]，每個秒數一張。"""
    days = (end_dt - start_dt).days + 1
    remarks = get_remarks_text(start_dt - timedelta(days=5),
                               f"{start_dt.year - 1911}年{start_dt.month}月", end_dt)
    outputs = []
    for sec in combo["seconds"]:
        cfg = _build_sub_config(combo["media"], sec, share_first)
        rows, total_list_accum, _logs = calculate_plan_data(
            cfg, float(budget), days, pricing_db, sec_factors,
            store_counts_num, list(config.REGIONS_ORDER),
        )
        xlsx = generate_excel_from_scratch(
            fmt, start_dt, end_dt, client, tax_id, product,
            rows, remarks, float(budget), float(prod_cost), sales, total_list_accum,
        )
        xlsx_bytes = xlsx.getvalue() if hasattr(xlsx, "getvalue") else xlsx
        html = None
        try:
            grand = round((float(budget) + float(prod_cost)) * 1.05)
            html = generate_html_preview(
                rows, days, start_dt, end_dt, client, tax_id, product,
                fmt, remarks, total_list_accum, grand, float(budget), float(prod_cost),
            )
        except Exception:
            html = None
        fname = safe_filename(f"{combo['label']}_{sec}秒_{int(budget)//10000}萬.xlsx")
        outputs.append({"sec": sec, "bytes": xlsx_bytes, "fname": fname, "html": html})
    return outputs


# =============================================================================
# 代理商：組 fam/wjf cfg + 逐秒數產表
# =============================================================================
def _gen_agency(combo, budget, start_dt, end_dt, client, product, campaign, agency_pricing):
    days = (end_dt - start_dt).days + 1
    material_due = start_dt - timedelta(days=7)
    made = date.today()
    ac_pct = config.AGENCY_AC_DEFAULT.get(combo["agency"]) or 0
    outputs = []
    for sec in combo["seconds"]:
        if combo["platform"] == "family":
            fam_cfg = {"enabled": True, "seconds": sec, "share": 100,
                       "rebate_pct": 0, "spots_override": 0, "auto_rebate": True}
            wjf_cfg = {"enabled": False}
        else:
            fam_cfg = {"enabled": False}
            wjf_cfg = {"enabled": True, "seconds": sec, "share": 100,
                       "rebate_pct": 0, "mag_override": 0, "is_rebate_wave": False}
        model = ac.build_agency_model(
            combo["agency"], client, product, campaign,
            start_dt, end_dt, float(budget),
            fam_cfg, wjf_cfg, ac.COMP_MOVE50, material_due, ac_pct,
            agency_pricing=agency_pricing,
        )
        xlsx = generate_agency_excel(model, made)
        xlsx_bytes = xlsx.getvalue() if hasattr(xlsx, "getvalue") else xlsx
        fname = safe_filename(f"{combo['label']}_{sec}秒_{int(budget)//10000}萬.xlsx")
        outputs.append({"sec": sec, "bytes": xlsx_bytes, "fname": fname, "html": None})
    return outputs


def _zip_outputs(outputs):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for o in outputs:
            zf.writestr(o["fname"], o["bytes"])
    return buf.getvalue()


# =============================================================================
# Streamlit UI
# =============================================================================
def render_simple_cue(store_counts_num, pricing_db, sec_factors, regions_order, sales_map=None):
    st.title("⚡ 簡易模式（一鍵產 CUE）")
    st.caption("只要選平台組合＋輸入預算，系統以標準走期與全省投放自動產出各秒數版本 CUE；先看範本，再回頭調走期與細節。")

    # --- 平台組合 ---
    all_combos = {**{k: v["label"] for k, v in SUB_COMBOS.items()},
                  **{k: v["label"] for k, v in AGENCY_COMBOS.items()}}
    combo_key = st.radio("平台組合", list(all_combos.keys()),
                         format_func=lambda k: all_combos[k])
    is_sub = combo_key in SUB_COMBOS

    # --- 預算：自由輸入 + 常用快捷 ---
    st.markdown("**預算（未稅 Net）**")
    if "simple_budget" not in st.session_state:
        st.session_state["simple_budget"] = 250000
    pcols = st.columns(len(BUDGET_PRESETS) + 1)
    for i, amt in enumerate(BUDGET_PRESETS):
        if pcols[i].button(f"{amt // 10000}萬", key=f"preset_{amt}"):
            st.session_state["simple_budget"] = amt
    budget = pcols[-1].number_input("自訂金額", min_value=0,
                                    value=int(st.session_state["simple_budget"]), step=10000,
                                    label_visibility="collapsed")
    st.session_state["simple_budget"] = int(budget)

    # --- 走期：開始日 + 週數 ---
    c1, c2, c3 = st.columns(3)
    with c1:
        start_dt = st.date_input("開始日", value=date.today())
    with c2:
        weeks = st.number_input("走期（週）", min_value=1, max_value=12, value=2, step=1)
    end_dt = start_dt + timedelta(days=int(weeks) * 7 - 1)
    with c3:
        st.text_input("結束日（自動）", value=end_dt.strftime("%Y-%m-%d"), disabled=True)

    # --- 客戶/產品/業務（可留白，先產範本）---
    with st.expander("客戶／產品資訊（可留白，先產範本再補）", expanded=False):
        cc1, cc2, cc3 = st.columns(3)
        client = cc1.text_input("客戶名稱", "")
        product = cc2.text_input("產品名稱", "")
        sales_options = list(sales_map.keys()) if sales_map else []
        sales = cc3.selectbox("業務", ["—"] + sales_options) if sales_options else ""
        sales = "" if sales == "—" else sales
        tax_id = cc1.text_input("統一編號", "")
        prod_cost = cc2.number_input("製作費（未稅）", min_value=0, value=0, step=1000)
        campaign = cc3.text_input("Campaign（2008 用）", "")

    # 子公司專屬：格式 + 預算佔比
    fmt = "東吳"
    share_first = 50
    if is_sub:
        media_keys = SUB_COMBOS[combo_key]["media"]
        s1, s2 = st.columns(2)
        fmt = s1.radio("報表格式", ["東吳", "聲活", "鉑霖"], horizontal=True)
        share_first = s2.slider(f"預算佔比：{media_keys[0]} ％（其餘給 {media_keys[1]}）",
                                0, 100, 50, step=5)

    st.divider()
    if not st.button("🚀 產生 CUE", type="primary"):
        return

    if budget <= 0:
        st.error("請先輸入預算金額。")
        return

    with st.spinner("計算並產生各秒數 CUE 中…"):
        try:
            if is_sub:
                outputs = _gen_subsidiary(
                    SUB_COMBOS[combo_key], budget, start_dt, end_dt, int(share_first),
                    client or "　", tax_id, product or "　", sales, prod_cost, fmt,
                    pricing_db, sec_factors, store_counts_num,
                )
            else:
                agency_pricing = load_agency_pricing_from_cloud(config.GSHEET_SHARE_URL)
                outputs = _gen_agency(
                    AGENCY_COMBOS[combo_key], budget, start_dt, end_dt,
                    client or "　", product or "　", campaign, agency_pricing,
                )
        except Exception as e:
            st.error(f"產生失敗：{e}")
            st.exception(e)
            return

    st.success(f"已產生 {len(outputs)} 張 CUE（{all_combos[combo_key]}，預算 {int(budget)//10000}萬，走期 {start_dt}~{end_dt}）")

    # ZIP 一次下載
    st.download_button("📦 下載全部（ZIP）", data=_zip_outputs(outputs),
                       file_name=safe_filename(f"{all_combos[combo_key]}_{int(budget)//10000}萬.zip"),
                       mime="application/zip")

    # 逐張下載 + 第一張 HTML 預覽
    dcols = st.columns(len(outputs))
    for i, o in enumerate(outputs):
        dcols[i].download_button(f"⬇ {o['sec']}秒", data=o["bytes"], file_name=o["fname"],
                                 mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 key=f"dl_{combo_key}_{o['sec']}")

    first_html = next((o["html"] for o in outputs if o.get("html")), None)
    if first_html:
        st.markdown(f"**預覽（{outputs[0]['sec']}秒版）**")
        import streamlit.components.v1 as components
        components.html(first_html, height=560, scrolling=True)
