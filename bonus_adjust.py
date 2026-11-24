# -*- coding: utf-8 -*-
"""
檔次調整（加贈）——Ragic 串接第 3 期。規格：docs/specs/Ragic串接_訂檔流程.md

Jonathan 2026-10-14：調整＝加贈（客戶預算不變、不收費），調整後 Excel／PDF 重新產出；已訂檔的 CUE 調整後更新原訂檔。
做法沿用一般CUE「業務加贈檔次」：選「平台＋秒數＋區域」群組、每日加贈幾檔、加贈日期區間 → 在該群組下方插入「加贈」列。
- 一般 CUE 版面（一般CUE、年約季約子公司格式、專案CUE、一鍵CUE 聲活／鉑霖）：rebate.compute_custom_bonus_rows
- 代理商版面（自訂代理商CUE、年約季約 2008／凱絡）：在該平台工作表加「專案回饋」列（萬家福另加樂家康超市回饋）
加贈列實收為 0，異動紀錄會記到「檔次 a → b」。
"""
from datetime import timedelta

import streamlit as st

from rebate import compute_custom_bonus_rows, get_row_groups, merge_rebate_into_rows

TITLE = "📌 檔次調整（加贈，不收費）"
HELP = "在相同平台、秒數、區域下方加一列「加贈」：設定每日加贈幾檔與日期區間（須在走期內）。預算不變，Excel／PDF 會一併更新。"


def can_adjust():
    """主管，或以 Ragic 帳號登入的同事（異動紀錄會記名）。"""
    return bool(st.session_state.get("is_supervisor") or st.session_state.get("ragic_user"))


def _group_ui(label, skey, start, end, key_prefix):
    st.markdown(f"**{label}**")
    c1, c2, c3, c4 = st.columns([1, 2, 2, 2])
    with c1:
        enabled = st.checkbox("加贈", value=st.session_state.get(f"{key_prefix}cb_en_{skey}", False),
                              key=f"{key_prefix}cb_en_{skey}", label_visibility="collapsed")
    with c2:
        spots = st.number_input("每日加贈檔次", min_value=0, max_value=999,
                                value=st.session_state.get(f"{key_prefix}cb_spots_{skey}", 0) or 0, step=1,
                                key=f"{key_prefix}cb_spots_{skey}")
    with c3:
        b_start = st.date_input("加贈開始日", value=start, min_value=start, max_value=end, key=f"{key_prefix}cb_start_{skey}")
    with c4:
        b_end = st.date_input("加贈結束日", value=end, min_value=start, max_value=end, key=f"{key_prefix}cb_end_{skey}")
    if enabled and spots and b_start and b_end:
        return {"enabled": True, "spots_per_day": int(spots), "date_start": b_start, "date_end": b_end}
    return None


def render_bonus_ui(rows, start, end, regions_order, *, key_prefix=""):
    """一般 CUE rows 的加贈設定（每個 get_row_groups 群組一組）。回傳 {群組key: 設定}。
    key_prefix=""＝一般CUE 原本的 widget key（cb_en_…），讀回舊存檔的 [EXT] 仍可還原。"""
    cfg = {}
    with st.expander(TITLE, expanded=False):
        if not can_adjust():
            st.caption("以 Ragic 帳號登入（或主管登入）後可設定加贈檔次。")
            return cfg
        st.caption(HELP)
        for g in get_row_groups(rows, regions_order):
            media, sec, region_key = g["key"]
            skey = f"cb_{media}_{sec}_{region_key}".replace(" ", "_")   # 與 app._get_ragic_extra_state 相同
            label = f"【{'萬家福．樂家康' if media == '家樂福' else media}】 {sec}秒 - {region_key}"
            one = _group_ui(label, skey, start, end, key_prefix)
            if one:
                cfg[g["key"]] = one
    return cfg


def apply_bonus(rows, cfg, start, end, pricing_db, sec_factors, store_counts_num, regions_order):
    """在 rows 對應群組下方插入加贈列（日期自動限縮在 start～end），回傳新 rows。"""
    if not cfg or not rows:
        return rows
    inserts, _ = compute_custom_bonus_rows(rows, cfg, start, end, pricing_db, sec_factors,
                                           store_counts_num, regions_order)
    return merge_rebate_into_rows(rows, inserts) if inserts else rows


def bonus_keys(key_prefix):
    """該前綴的加贈 widget key（快照 restore 用）。"""
    return [k for k in st.session_state.keys()
            if any(str(k).startswith(f"{key_prefix}cb_{t}_") for t in ("en", "spots", "start", "end"))]


# =============================================================================
# 代理商版面
# =============================================================================
def agency_groups(combos):
    """年約季約代理商組合 → [(平台, 秒數)]（全家企頻／萬家福）。"""
    import agency_cue as ac
    out = []
    for c in combos:
        plat = ac.PLATFORM_FAMILY if c["media"] == "全家廣播" else ac.PLATFORM_WJF
        k = (plat, int(c["seconds"]))
        if c["media"] in ("全家廣播", "家樂福") and k not in out:
            out.append(k)
    return out


def render_agency_bonus_ui(groups, start, end, *, key_prefix):
    """代理商工作表（平台＋秒數）的加贈設定。回傳 {(平台, 秒數): 設定}。"""
    import agency_cue as ac
    cfg = {}
    with st.expander(TITLE, expanded=False):
        if not can_adjust():
            st.caption("以 Ragic 帳號登入（或主管登入）後可設定加贈檔次。")
            return cfg
        st.caption(HELP + " 萬家福加贈量販檔次，樂家康超市依 720/420 自動換算。2008 版面的回饋列以總檔數顯示。")
        for plat, sec in groups:
            label = f"【{'全家企頻' if plat == ac.PLATFORM_FAMILY else '萬家福．樂家康'}】 {sec}秒"
            one = _group_ui(label, f"{plat}_{sec}", start, end, key_prefix)
            if one:
                cfg[(plat, sec)] = one
    return cfg


def _sched(start, end, cfg):
    days = (end - start).days + 1
    b0, b1 = max(cfg["date_start"], start), min(cfg["date_end"], end)
    return [cfg["spots_per_day"] if b0 <= start + timedelta(days=d) <= b1 else 0 for d in range(days)]


def apply_agency_bonus(model, cfg):
    """在代理商 model 的對應工作表加「專案回饋」列（就地修改，回傳 model）。實收、費用不變。"""
    import agency_cue as ac
    if not cfg:
        return model
    start, end = model["start_date"], model["end_date"]
    agency = model["agency"]
    for sh in model["sheets"]:
        one = cfg.get((sh["platform"], int(sh["seconds"])))
        main = next((r for r in sh["rows"] if r["kind"] == ac.KIND_MAIN), None)
        if not one or main is None:
            continue
        sch = _sched(start, end, one)
        n = sum(sch)
        if n <= 0:
            continue
        lp = main.get("list_per") or 0

        def _row(kind, label, region, daypart, spots, schedule, list_total, net):
            r = ac._new_row(kind, label, region, daypart, sh["seconds"], spots,
                            None if agency == "2008傳媒" else schedule,   # 2008 回饋列一律合併顯示總數
                            list_per=lp, list_total=list_total, market_per=main.get("market_per") or 0,
                            uni_per=main.get("uni_per") or 0, uni_total=(main.get("uni_per") or 0) * spots,
                            net_display=net)
            r["is_adjust_bonus"] = True
            return r

        if sh["platform"] == ac.PLATFORM_FAMILY:
            sh["rows"].append(_row(ac.KIND_REBATE, "", "", "", n, sch, lp * n, ac.NET_REBATE))
        else:
            mag_l, mag_r, mag_d = ac._labels(agency, "mag")
            sup_l, sup_r, sup_d = ac._labels(agency, "super")
            sup_sch = [ac.super_spots_from_mag(x) if x else 0 for x in sch]
            sh["rows"].append(_row(ac.KIND_REBATE, mag_l, mag_r, mag_d, n, sch, lp * n, ac.NET_REBATE))
            sh["rows"].append(_row(ac.KIND_SUPER_REBATE, sup_l, sup_r, sup_d, sum(sup_sch), sup_sch, 0,
                                   ac.NET_ON_MAG))
    return model
