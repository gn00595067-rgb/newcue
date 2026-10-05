# -*- coding: utf-8 -*-
"""
簡易模式 v2 —— 預估曝光／人流純計算（不 import streamlit，可獨立 pytest）

公式來源：公司提供「各平台人流計算方式.xlsx」，已逐格反推並用 Python 重算 100% 吻合。
  全家企頻／新鮮視（逐區）
      總曝光次數  Y = Σ_區 (店數_r × 檔次_r)
      店舖總人流  Z = Σ_區 1000*(店數_r/24/6)*檔次_r = 總曝光 × TRAFFIC_FACTOR
  萬家福（量販）／樂家康（超市）——固定人流常數，與店數無關
      總曝光次數  = 660000 + 200000 = 860000（固定）
      店舖總人流  = 660000/14×量販檔次 + 200000/24×0.75×超市檔次

唯一入口 compute_reach(blocks, data, ndays)：子公司與代理商共用。
  - 子公司家族列（全家廣播）為逐區列 → Σ 店數×檔次
  - 代理商家族列（全家企頻）為單一「全省」列 → 全省店數(六區加總) × 檔次
  - 家樂福/萬家福：impressions 固定 860000，traffic 依量販/超市檔次
  - 代理商回饋(bonus)/補償(super_bonus)列依 REACH_INCLUDE_BONUS 開關計入
"""
import simple_config as sc
from agency_cue import rhu

# 內部平台 key → 曝光文字用語 key（REACH_LABEL）
_FAMILY_PLATFORMS = ("全家廣播", "全家企頻")   # 全家企頻廣播（子公司逐區 / 代理商全省）
_TV_PLATFORMS = ("新鮮視",)                    # 新鮮視（僅子公司）
_CARREFOUR_PLATFORMS = ("家樂福", "萬家福")    # 萬家福量販＋樂家康超市


def _wjf_hours(kind):
    """量販/超市營業時數；優先由 DAYPART_SUBSIDIARY 的 "HH-HH" 解析，失敗回退常數表。
    "09-23"→14、"00-24"→24。常數表(REACH_WJF[...]['hours'])為 fallback 與交叉驗證用。"""
    daypart = sc.DAYPART_SUBSIDIARY.get("家樂福量販" if kind == "量販" else "家樂福超市", "")
    try:
        a, b = daypart.split("-")
        h = int(b) - int(a)
        if h > 0:
            return h
    except (ValueError, AttributeError):
        pass
    return sc.REACH_WJF[kind]["hours"]


def _factor():
    return sc.TRAFFIC_FACTOR


def _region_entry(label, stores, spots):
    """單一地區列：曝光＝店數×檔次、人流＝曝光×係數（列不取整，存浮點）。"""
    imp = stores * spots
    return {"label": label, "stores": stores, "spots": spots,
            "impressions": int(imp), "traffic": imp * _factor()}


def _reach_family_like(blk, data, include_bonus, media_key, reach_key):
    """全家企頻／新鮮視共用：子公司＝逐區列；代理商全家企頻＝單一全省列。
    回傳含逐區明細 regions 的平台 dict。"""
    region_rows = [r for r in blk.rows if r.region in sc.REGIONS_ORDER]
    stores_map = data.stores.get(media_key, {})
    if region_rows:
        # 子公司：每區一列各算 店數×檔次；指定投放區域(子集)時自然只列所選區
        regions = [_region_entry(sc.REGION_LABELS.get(r.region, r.region),
                                 stores_map.get(r.region, 0), r.spots)
                   for r in region_rows]
    else:
        # 代理商：單一全省列，店數＝六區加總；檔次＝主列(＋回饋列，依開關)
        counted = [r for r in blk.rows
                   if r.kind == "main" or (include_bonus and r.kind == "bonus")]
        regions = [_region_entry("全省", sum(stores_map.values()),
                                 sum(r.spots for r in counted))]
    stores = sum(x["stores"] for x in regions)
    impressions = sum(x["impressions"] for x in regions)
    traffic = sum(x["traffic"] for x in regions)
    spots = sum(x["spots"] for x in regions)
    return {
        "platform": reach_key, "label": sc.REACH_LABEL[reach_key],
        "stores": stores, "spots": spots,
        "impressions": int(impressions), "traffic": traffic,
        "regions": regions,
    }


def _reach_family(blk, data, include_bonus):
    return _reach_family_like(blk, data, include_bonus, "全家廣播", "全家廣播")


def _reach_tv(blk, data, include_bonus):
    return _reach_family_like(blk, data, include_bonus, "新鮮視", "新鮮視")


def _reach_carrefour(blk, data, ndays, include_bonus):
    """萬家福（量販）＋樂家康（超市）。曝光固定 860000；人流依量販/超市檔次。"""
    mag_spots = sum(r.spots for r in blk.rows
                    if r.kind == "main" or (include_bonus and r.kind == "bonus"))
    sup_spots = sum(r.spots for r in blk.rows
                    if r.kind == "super" or (include_bonus and r.kind == "super_bonus"))

    wjf = sc.REACH_WJF
    use_days = (sc.REACH_WJF_DIVISOR == "days")
    div_mag = ndays if use_days else _wjf_hours("量販")
    div_sup = ndays if use_days else _wjf_hours("超市")

    traffic_mag = wjf["量販"]["daily_traffic"] / div_mag * wjf["量販"]["coef"] * mag_spots
    traffic_sup = wjf["超市"]["daily_traffic"] / div_sup * wjf["超市"]["coef"] * sup_spots

    imp_mag = wjf["量販"]["daily_traffic"]      # 660000（固定）
    imp_sup = wjf["超市"]["daily_traffic"]      # 200000（固定）
    mag_stores = data.stores.get("家樂福", {}).get("量販", 0)
    sup_stores = data.stores.get("家樂福", {}).get("超市", 0)
    # 逐「區」明細（家樂福不分地區，改列量販／超市兩通路；曝光為固定常數）
    regions = [
        {"label": f"{sc.PLATFORM_DISPLAY['家樂福量販']}（量販）", "stores": mag_stores,
         "spots": mag_spots, "impressions": int(imp_mag), "traffic": traffic_mag},
        {"label": f"{sc.PLATFORM_DISPLAY['家樂福超市']}（超市）", "stores": sup_stores,
         "spots": sup_spots, "impressions": int(imp_sup), "traffic": traffic_sup},
    ]
    return {
        "platform": "家樂福", "label": sc.REACH_LABEL["家樂福"],
        "stores": mag_stores + sup_stores, "spots": mag_spots + sup_spots,
        "impressions": int(imp_mag + imp_sup), "traffic": traffic_mag + traffic_sup,
        "regions": regions,
        "detail": {   # 保留舊 key（測試/相容）
            "量販": {"spots": mag_spots, "traffic": traffic_mag},
            "超市": {"spots": sup_spots, "traffic": traffic_sup},
        },
    }


def _client_line(entry):
    """客戶用文字（源自範本 A24～A26 格式）：
    【{label}總曝光次數 : {曝光}     曝光期間店舖總人流量 : {人流}】
    數字加千分位、人流四捨五入取整；範本原有結尾「 .」無意義，依同事回饋移除。"""
    return (f"【{entry['label']}總曝光次數 : {entry['impressions']:,}"
            f"     曝光期間店舖總人流量 : {rhu(entry['traffic']):,}】")


def compute_reach(blocks, data, ndays, *, include_bonus=None):
    """由已建好的 blocks 計算三平台曝光／人流。traffic 存浮點、顯示時才取整。"""
    if include_bonus is None:
        include_bonus = sc.REACH_INCLUDE_BONUS

    by_platform = []
    for blk in blocks:
        if blk.platform in _FAMILY_PLATFORMS:
            by_platform.append(_reach_family(blk, data, include_bonus))
        elif blk.platform in _TV_PLATFORMS:
            by_platform.append(_reach_tv(blk, data, include_bonus))
        elif blk.platform in _CARREFOUR_PLATFORMS:
            by_platform.append(_reach_carrefour(blk, data, ndays, include_bonus))

    total_imp = sum(e["impressions"] for e in by_platform)
    total_traffic = sum(e["traffic"] for e in by_platform)
    lines = [_client_line(e) for e in by_platform]
    return {
        "by_platform": by_platform,
        "total": {"impressions": int(total_imp), "traffic": total_traffic},
        "lines": lines,
    }


# =============================================================================
# 一般 CUE（excel_renderer / html_generator 的 rows dict）共用入口
# =============================================================================
def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else 0


def _row_spots(r):
    """該表內實際檔次＝schedule 數字加總（分月切表時 row["spots"] 仍是全期，不可用）。"""
    sch = r.get("schedule")
    if isinstance(sch, (list, tuple)):
        return int(sum(_num(x) for x in sch))
    return int(_num(r.get("spots")))


def compute_reach_from_rows(rows, ndays):
    """一般 CUE 的 rows（dict 列）→ 與 compute_reach 相同結構的曝光／人流。
    全家廣播／新鮮視逐列 店數×檔次；加贈列店數非數字時沿用同平台同區域的店數。
    家樂福沿用 _reach_carrefour（region 含「超市」算超市，其餘算量販）。"""
    from types import SimpleNamespace as NS

    by_media = {}
    for r in rows or []:
        by_media.setdefault(r.get("media"), []).append(r)

    by_platform = []
    for media in ("全家廣播", "新鮮視"):
        mrows = by_media.get(media)
        if not mrows:
            continue
        stores_map = {r.get("region"): r["program_num"] for r in mrows if _num(r.get("program_num"))}
        agg = {}   # region → [stores, spots]（同區多列：秒數／回饋／加贈，檔次加總）
        for r in mrows:
            reg = r.get("region")
            stores = _num(r.get("program_num")) or stores_map.get(reg, 0)
            e = agg.setdefault(reg, [stores, 0])
            e[0] = e[0] or stores
            e[1] += _row_spots(r)
        regions = [_region_entry(sc.REGION_LABELS.get(reg, reg), st, sp)
                   for reg, (st, sp) in agg.items() if sp]
        if not regions:
            continue
        by_platform.append({
            "platform": media, "label": sc.REACH_LABEL[media],
            "stores": sum(x["stores"] for x in regions), "spots": sum(x["spots"] for x in regions),
            "impressions": int(sum(x["impressions"] for x in regions)),
            "traffic": sum(x["traffic"] for x in regions), "regions": regions,
        })

    cf_rows = by_media.get("家樂福")
    if cf_rows:
        mag = [r for r in cf_rows if "超市" not in str(r.get("region", ""))]
        sup = [r for r in cf_rows if "超市" in str(r.get("region", ""))]
        blk = NS(rows=[NS(kind="main", spots=_row_spots(r)) for r in mag]
                 + [NS(kind="super", spots=_row_spots(r)) for r in sup])
        stores = {"量販": next((_num(r.get("program_num")) for r in mag if _num(r.get("program_num"))), 0),
                  "超市": next((_num(r.get("program_num")) for r in sup if _num(r.get("program_num"))), 0)}
        if any(x.spots for x in blk.rows):
            by_platform.append(_reach_carrefour(blk, NS(stores={"家樂福": stores}), ndays, True))

    return {
        "by_platform": by_platform,
        "total": {"impressions": int(sum(e["impressions"] for e in by_platform)),
                  "traffic": sum(e["traffic"] for e in by_platform)},
        "lines": [_client_line(e) for e in by_platform],
    }
