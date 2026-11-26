# -*- coding: utf-8 -*-
"""業務成交輔助（第二階段 2-1、2-2；spec docs/specs/第二階段_主管決策實作.md）。
- upsell_hints：預算接近下一個回饋級距時，提示「再加 X 萬可回饋 Y%」（主管 LINE：加碼優惠提示）。
- benefit_summary：算好的 CUE → 效益數字＋可複製的說明話術（主管 LINE：產出媒體效益分析／效益說明）。
本模組不 import streamlit；獨立新檔，避免 Streamlit Cloud 舊模組快取造成 ImportError。"""
import rebate_rules as rr
from simple_reach import compute_reach_from_rows

UPSELL_GAP_RATIO = 0.3   # 差距在下一級門檻 30% 以內才提示（例：35 萬起提示 50 萬級）

_UNIT = {"全家廣播": "店", "新鮮視": "面", "家樂福": "店"}
_NAME = {"全家廣播": "全家便利商店店內廣播", "新鮮視": "全家新鮮視螢幕", "家樂福": "萬家福．樂家康賣場廣播"}


def _wan(v):
    w = v / 10000
    return f"{w:.1f}".rstrip("0").rstrip(".") + "萬"


def _platform_budget(cfg, total_budget):
    return total_budget * cfg.get("share", 0) / 100.0 * sum((cfg.get("sec_shares") or {}).values()) / 100.0


def upsell_hints(config, total_budget):
    """回傳提示文字 list。只看全省（全家需勾全省聯播）；已達最高級（100 萬以上專案談）不提示。"""
    out = []
    cfg = (config or {}).get("全家廣播")
    if cfg and cfg.get("is_national"):
        b = _platform_budget(cfg, total_budget)
        cur = rr.nat_rad_pct(b) or (0, 0)
        for lo, hi, p_rad, p_cf in rr.NAT_RAD_TIERS:
            if lo > b and (p_rad, p_cf) > cur and lo - b <= lo * UPSELL_GAP_RATIO:
                out.append(f"全家企頻全省目前 {_wan(b)}，再加 {_wan(lo - b)}達 {_wan(lo)}，可回饋全家 {p_rad}%"
                           f"（價值約 {_wan(lo * p_rad / 100)}元檔次）或改回饋萬家福 {p_cf}%（約 {_wan(lo * p_cf / 100)}元）。")
                break
    cfg = (config or {}).get("家樂福")
    if cfg:
        b = _platform_budget(cfg, total_budget)
        cur = rr.nat_cf_pct(b) or 0
        for lo, hi, p in rr.NAT_CF_TIERS:
            if lo > b and p > cur and lo - b <= lo * UPSELL_GAP_RATIO:
                out.append(f"萬家福．樂家康目前 {_wan(b)}，再加 {_wan(lo - b)}達 {_wan(lo)}，可回饋 {p}%（價值約 {_wan(lo * p / 100)}元檔次）。")
                break
    return out


def _is_gift(r):
    return bool(r.get("is_rebate") or r.get("is_custom_bonus") or r.get("is_bonus_rebate"))


def _spots(r):
    sch = r.get("schedule")
    if isinstance(sch, (list, tuple)):
        return int(sum(x for x in sch if isinstance(x, (int, float)) and not isinstance(x, bool)))
    return int(r.get("spots") or 0)


def benefit_summary(rows, ndays, net_price, start=None, end=None):
    """rows＝一般 CUE 算好的列（含回饋／加贈列）；ndays＝實際播出天數；net_price＝專案價（未稅）。
    回傳 {"platforms": [...], "total": {...}, "text": [話術句子]}。"""
    ndays = max(1, int(ndays or 1))
    all_r = compute_reach_from_rows(rows, ndays)
    paid_r = compute_reach_from_rows([r for r in rows or [] if not _is_gift(r)], ndays)
    paid_by = {e["platform"]: e for e in paid_r["by_platform"]}

    platforms = []
    for e in all_r["by_platform"]:
        media = e["platform"]
        mrows = [r for r in rows if r.get("media") == media]
        gift = sum(_spots(r) for r in mrows if _is_gift(r))
        n_regions = max(1, len(e.get("regions") or []) or 1)
        per_store_day = e["spots"] / n_regions / ndays if media != "家樂福" else None
        p = paid_by.get(media, {"impressions": 0, "traffic": 0})
        platforms.append({
            "media": media, "name": _NAME.get(media, media), "stores": int(e.get("stores") or 0),
            "unit": _UNIT.get(media, "店"), "spots": int(e["spots"]), "gift_spots": int(gift),
            "per_store_day": per_store_day, "impressions": int(e["impressions"]), "traffic": int(e["traffic"]),
            "gift_impressions": int(e["impressions"] - p["impressions"]),
        })

    imp = sum(p["impressions"] for p in platforms)
    traffic = sum(p["traffic"] for p in platforms)
    spots = sum(_spots(r) for r in rows or [])
    gift_spots = sum(_spots(r) for r in rows or [] if _is_gift(r))
    gift_imp = sum(p["gift_impressions"] for p in platforms)
    total = {
        "net": int(net_price or 0), "days": ndays, "spots": spots, "gift_spots": gift_spots,
        "impressions": imp, "traffic": traffic, "gift_impressions": gift_imp,
        "unit_price": (net_price / spots) if spots else None,
        "cpm": (net_price / imp * 1000) if imp else None,
    }

    text = []
    period = f"{start:%Y/%m/%d}～{end:%Y/%m/%d} 共 {ndays} 天" if start and end else f"共 {ndays} 天"
    parts = []
    for p in platforms:
        s = f"{p['name']} {p['stores']:,} {p['unit']}"
        if p["per_store_day"]:
            s += f"（每{p['unit']}每天約 {p['per_store_day']:.0f} 檔）"
        parts.append(s)
    if parts:
        text.append(f"本方案於 {period}，在" + "、".join(parts) + "播出。")
    if imp:
        text.append(f"預估總曝光 {imp:,} 次，曝光期間店舖人流約 {traffic:,} 人次。")
    if net_price and imp:
        # 不寫「平均每檔」：全省聯播一檔同時在六區播，CUE 合計檔次是六區加總，除出來會誤導
        text.append(f"專案價 {int(net_price):,} 元（未稅），平均每千次曝光成本約 {total['cpm']:,.0f} 元。")
    if gift_spots:
        text.append(f"其中加贈 {gift_spots:,} 檔（不另收費），額外增加曝光約 {gift_imp:,} 次。")
    total["text"] = text
    return {"platforms": platforms, "total": total, "text": text}
