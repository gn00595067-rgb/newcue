# -*- coding: utf-8 -*-
"""全省回饋門檻（主管 2026-11-26 Q1：11/24 回饋比例表正式取代舊表；spec docs/specs/第二階段_主管決策實作.md）。
- 不再看走期月數。兩級之間用「已達到的那一級」（例：40 萬＝30 萬級）。
- 30 萬（全家）／25 萬（萬家福）級回饋 0%：視同未達標，不給回饋列。
- 100 萬以上「專案談」：不給預設回饋，業務自填回饋 % 送主管審核。
- 單區門檻（config.REBATE_RULES_REGION）不變。
獨立模組：Streamlit Cloud 推版後可能沿用舊模組，新規則放新檔才不會 ImportError。"""

PROJECT_THRESHOLD = 1_000_000   # 全家、萬家福皆 100 萬以上專案談

# 全家企頻（依全家預算）：(下限含, 上限不含, 回饋全家%, 改回饋萬家福%)
NAT_RAD_TIERS = [
    (300_000, 500_000, 0, 0),
    (500_000, 900_000, 10, 15),
    (900_000, PROJECT_THRESHOLD, 15, 20),
]
# 萬家福（依萬家福預算）：(下限含, 上限不含, 回饋萬家福%)
NAT_CF_TIERS = [
    (250_000, 500_000, 0),
    (500_000, 750_000, 20),
    (750_000, PROJECT_THRESHOLD, 25),
]


def nat_rad_pct(budget):
    """全家全省預算 → (全家%, 萬家福%)；未達標、0% 級或 100 萬以上 → None。"""
    for lo, hi, p_rad, p_cf in NAT_RAD_TIERS:
        if lo <= budget < hi:
            return (p_rad, p_cf) if (p_rad or p_cf) else None
    return None


def nat_cf_pct(budget):
    """萬家福全省預算 → 回饋%；未達標、0% 級或 100 萬以上 → None。"""
    for lo, hi, p in NAT_CF_TIERS:
        if lo <= budget < hi:
            return p or None
    return None


def project_negotiation_platforms(config, total_budget):
    """預算達 100 萬（專案談）的全省平台顯示名，給畫面提示用。"""
    out = []
    for media, label in (("全家廣播", "全家企頻"), ("家樂福", "萬家福．樂家康")):
        cfg = (config or {}).get(media)
        if not cfg or (media == "全家廣播" and not cfg.get("is_national")):
            continue
        b = total_budget * cfg.get("share", 0) / 100.0 * sum((cfg.get("sec_shares") or {}).values()) / 100.0
        if b >= PROJECT_THRESHOLD:
            out.append(label)
    return out
