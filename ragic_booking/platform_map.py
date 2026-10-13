"""（2026-10-13 自 cueupload/cueparse 搬入，兩邊修改請同步）
平台名稱正規化：把 Ragic／CUE 上五花八門的平台寫法，對應到公司標準平台家族與區域。

沿用 fptest 專案的對應邏輯（新鮮視六區、全家廣播頻道→區、企頻不分區），
並補上 fptest 未處理的家樂福（超市／量販）與診所健康視。

刻意用「子字串比對＋NFKC 正規化」而非精確字串，才扛得住全形／半形、
順序不同、以及「家樂福量販、新鮮視」這類一格塞多平台的複合寫法。

這支模組是純函式、無副作用，方便測試，也供之後的播出檔次 parser 共用。
"""
from __future__ import annotations

import unicodedata

# ---- 平台家族（canonical）----
FAM_FRESHVISION = "全家新鮮視"   # 電視／影像（門市螢幕）
FAM_FMRADIO = "全家廣播"        # 廣播（含企頻）
FAM_CARR_HYPER = "家樂福量販"   # 萬家福量販頻道（排程報表檔名 C01…）
FAM_CARR_SUPER = "家樂福超市"   # 樂家康超市頻道（排程報表檔名 CF…）
FAM_CARREFOUR = "家樂福"        # 只寫「家樂福」未分超量時的暫定家族
FAM_CLINIC = "診所健康視"
FAM_OTHER = "其他"

ALL_FAMILIES = [
    FAM_FRESHVISION, FAM_FMRADIO, FAM_CARR_HYPER,
    FAM_CARR_SUPER, FAM_CARREFOUR, FAM_CLINIC, FAM_OTHER,
]

# ---- 新鮮視／廣播六區（canonical，取公司常用寫法）----
REGION_NORTH = "北北基"
REGION_TAOZHU = "桃竹苗"
REGION_CENTRAL = "中彰投"
REGION_YCN = "雲嘉南"
REGION_KP = "高高屏"
REGION_EAST = "宜花東"
ALL_REGIONS = [
    REGION_NORTH, REGION_TAOZHU, REGION_CENTRAL,
    REGION_YCN, REGION_KP, REGION_EAST,
]

# 全家廣播頻道 → 區（沿用 fptest lines 1774-1779）
_RADIO_CHANNEL_TO_REGION = [
    ("北頻", REGION_NORTH),
    ("桃頻", REGION_TAOZHU),
    ("中頻", REGION_CENTRAL),
    ("南頻", REGION_YCN),
    ("高頻", REGION_KP),
    ("宜頻", REGION_EAST),
]


def _norm(s: str) -> str:
    """NFKC 正規化（全形→半形）並去頭尾空白。"""
    return unicodedata.normalize("NFKC", str(s or "")).strip()


def platform_families(text: str) -> list[str]:
    """把平台字串拆成 canonical 家族清單（可能多個，如「家樂福量販、新鮮視」）。

    - 用關鍵字掃整段，一段可命中多個家族。
    - 完全無法辨識回 [FAM_OTHER]；空字串回 []（代表「未填」，與「其他」區分）。
    """
    p = _norm(text)
    if not p:
        return []

    fams: list[str] = []

    # 家樂福：先分超市／量販，兩者皆無再落到通用家族
    has_carr = "家樂福" in p
    is_hyper = ("量販" in p) or ("萬家福" in p)
    is_super = ("超市" in p) or ("樂家康" in p)
    if is_hyper:
        fams.append(FAM_CARR_HYPER)
    if is_super:
        fams.append(FAM_CARR_SUPER)
    if has_carr and not is_hyper and not is_super:
        fams.append(FAM_CARREFOUR)

    # 全家新鮮視（門市電視／影像）。CUE 人為寫法多樣，同一種螢幕常寫成
    # 電子看板／燈箱／電視牆／門市影像 等，一律視為新鮮視。
    if ("新鮮視" in p) or ("電子看板" in p) or ("燈箱" in p) \
            or ("電視牆" in p) or ("門市影像" in p) or ("影音看板" in p):
        fams.append(FAM_FRESHVISION)

    # 全家廣播（企頻／各區頻／全頻／廣播）
    if ("企頻" in p) or ("廣播" in p) or ("全頻" in p) \
            or any(ch in p for ch, _ in _RADIO_CHANNEL_TO_REGION):
        fams.append(FAM_FMRADIO)

    # 診所健康視
    if ("健康視" in p) or ("診所" in p):
        fams.append(FAM_CLINIC)

    # 去重保序；全空落到「其他」
    fams = list(dict.fromkeys(fams))
    return fams or [FAM_OTHER]


def platform_regions(text: str) -> list[str]:
    """從平台字串解析新鮮視／廣播的區域清單。

    - 「全區／全省／全台／全頻」→ 六區全展開。
    - 廣播頻道簡稱（北頻…宜頻）依對應表換算。
    - 地名關鍵字（北北基、桃竹苗…）直接命中。
    - 沒有區域資訊（如企頻、家樂福）回 []。
    """
    p = _norm(text)
    if not p:
        return []

    # 全區展開（企頻雖含「全」意味但不分區，靠下方地名／頻道判斷即可）
    if any(k in p for k in ("全區", "全省", "全台", "全國", "全頻")):
        return list(ALL_REGIONS)

    regions: list[str] = []

    # 廣播頻道簡稱 → 區
    for ch, region in _RADIO_CHANNEL_TO_REGION:
        if ch in p:
            regions.append(region)

    # 地名關鍵字（沿用 fptest 區域判斷，避免「中／南」誤中）
    if "北北基" in p or "北區" in p:
        regions.append(REGION_NORTH)
    if "桃" in p or "竹" in p or "苗" in p:
        regions.append(REGION_TAOZHU)
    if "中" in p and ("區" in p or "彰" in p or "投" in p):
        regions.append(REGION_CENTRAL)
    if "雲" in p or "嘉" in p or ("南" in p and "頻" not in p):
        regions.append(REGION_YCN)
    if "高" in p or "屏" in p:
        regions.append(REGION_KP)
    if "宜" in p or "花" in p or ("東" in p and "區" in p):
        regions.append(REGION_EAST)

    return list(dict.fromkeys(regions))


def normalize(text: str) -> dict[str, list[str]]:
    """一次回傳 {'families': [...], 'regions': [...]}，供研究腳本與 parser 共用。"""
    return {
        "families": platform_families(text),
        "regions": platform_regions(text),
    }
