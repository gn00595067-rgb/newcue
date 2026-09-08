# -*- coding: utf-8 -*-
"""
簡易模式 v2 純計算核心（不 import streamlit，可獨立 pytest）

輸入（組合 key + 預算 + 走期）→ CueModel（見 §3.1）。
唯一入口：build_model(...)。所有金額取整用 agency_cue.rhu（round half up）。

檔次邏輯不再呼叫 calculator.calculate_plan_data（原因見 §4.0）：
  範本檔次可為奇數、不超過預算盡量填滿、每日平均餘數放前面。
一般 CUE 的 calculator.py 維持原樣。
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from math import floor

import agency_cue as ac
from agency_cue import rhu
import simple_config as sc

_WEEK_CH = "一二三四五六日"


# =============================================================================
# 資料來源包裝（§3.1）
# =============================================================================
@dataclass
class SheetData:
    """把 Google Sheet（或 fallback）內容包成離線可測的一包。"""
    pricing: dict           # {media: {region: {"List","Net","Std"}}}
    factors: dict           # {media: {sec: factor}}
    stores: dict            # {media: {region: count}}
    agency_pricing: dict = None   # {(agency, platform): {sec: per}} 或 None
    from_fallback: bool = False


def fallback_sheetdata(use_template_factors=False):
    """用 simple_config 的內建備援組一份 SheetData（測試與斷線時用）。"""
    return SheetData(
        pricing={m: {r: dict(v) for r, v in regs.items()}
                 for m, regs in sc.PRICING_FALLBACK.items()},
        factors=sc.FACTORS_TEMPLATE if use_template_factors else {
            m: dict(v) for m, v in sc.FACTORS_FALLBACK.items()},
        stores={m: dict(v) for m, v in sc.STORES_FALLBACK.items()},
        agency_pricing=None,
        from_fallback=True,
    )


# =============================================================================
# 資料類別（§3.1）
# =============================================================================
@dataclass
class DayCol:
    date: date
    weekend: bool
    month_label: str = None    # 該月第一天才有，如 "9月"


@dataclass
class CueRow:
    kind: str = "main"          # main | super | bonus | super_bonus | total
    station: str = ""           # 子公司 Station key / 代理商 媒體型態文字
    region: str = ""            # 區域 key（北區..）或 量販/超市
    location: str = ""          # 顯示名
    stores: int = None
    daypart: str = ""
    seconds: int = 0
    spots: int = 0
    schedule: list = None       # None = 合併顯示總數
    # 子公司 rate(Net)：以公式 ={list}/{std}*V*{factor} 呈現；樂家康用文字
    rate_num: tuple = None      # (list_price, std, factor)
    rate_text: str = None
    # 代理商價格
    list_per: float = None      # 每檔牌價
    list_total: float = None    # 定價合計
    market_per: float = None
    uni_per: float = None
    uni_total: float = None
    net_display: object = None  # 合計/專案價：數字 或 "專案回饋"/"計價於量販"
    material: str = None
    hidden_net: float = 0.0     # 內部：spots × unit_net（僅 UI/測試，不寫 Excel）


@dataclass
class CueBlock:
    platform: str               # 內部 key
    rows: list = field(default_factory=list)


@dataclass
class CueSheet:
    title: str
    seconds: int
    blocks: list = field(default_factory=list)
    days: list = field(default_factory=list)
    budget: int = 0
    prod_cost: int = 0
    fees: dict = field(default_factory=dict)
    hidden_net_total: float = 0.0
    reach: dict = field(default_factory=dict)


@dataclass
class CueModel:
    combo_key: str
    combo_label: str
    family: str                 # subsidiary | 2008 | carat
    client: str = ""
    tax_id: str = ""
    product: str = ""
    sales: str = ""
    campaign: str = ""
    start: date = None
    end: date = None
    made_date: date = None
    medium_label: str = ""
    remarks: list = field(default_factory=list)   # [(文字, 是否紅字)]
    sign_deadline: date = None
    material_due: date = None
    billing_month: str = ""
    payment_date_text: str = ""
    sheets: list = field(default_factory=list)
    filename: str = ""


# =============================================================================
# 分配演算法（§4.4 / §4.5）
# =============================================================================
def distribute(n, days):
    """平均分配 n 到 days 天，餘數放最前面幾天。"""
    if days <= 0:
        return []
    base, rem = divmod(int(n), days)
    return [base + 1] * rem + [base] * (days - rem)


def allocate_spots(budget, platforms):
    """
    子公司檔次分配（§4.4）。
    platforms = [(name, share, unit_net), ...]，share 為百分比或比例（相對即可）。
    回傳 {name: spots}，保證 Σ spots×unit ≤ budget 且盡量填滿。
    """
    units = {p: u for p, _, u in platforms}
    shares = {p: s for p, s, _ in platforms}
    spots = {p: floor(shares[p] / 100.0 * budget / units[p]) for p, _, u in platforms}
    left = budget - sum(spots[p] * units[p] for p in spots)
    eps = 1e-9
    while True:
        cands = [p for p in units if units[p] <= left + eps]
        if not cands:
            break
        # 補「離目標佔比差最多」的平台
        p = max(cands, key=lambda p: shares[p] / 100.0 * budget - spots[p] * units[p])
        spots[p] += 1
        left -= units[p]
    return spots


def super_spots(mag_spots):
    """樂家康(超市)檔次 = rhu(量販 × 720/420)（計價於量販，不另收費）。"""
    a, b = sc.SUPER_RATIO
    return rhu(mag_spots * a / b)


# =============================================================================
# 係數 / 單檔實作價
# =============================================================================
def factor(media, sec, data):
    """秒數係數；FACTOR_OVERRIDE 優先。media 用內部 key（全家廣播/新鮮視/家樂福）。"""
    ov = sc.FACTOR_OVERRIDE.get((media, sec))
    if ov is not None:
        return ov
    return data.factors.get(media, {}).get(sec, 1.0)


def _national(media, data):
    """該媒體『全省』定價列（家樂福用量販_全省）。"""
    if media == "家樂福":
        return data.pricing["家樂福"]["量販_全省"]
    return data.pricing[media]["全省"]


def _effective_regions(media, regions):
    """有效投放區域清單；None＝全省（全部區、走套裝價）。
    家樂福無分區；regions 空、或涵蓋全部六區 → None（視為全省）。"""
    if media == "家樂福" or not regions:
        return None
    sel = [r for r in sc.REGIONS_ORDER if r in regions]
    if not sel or len(sel) == len(sc.REGIONS_ORDER):
        return None
    return sel


def sub_unit_net(media, sec, data, regions=None):
    """子公司單檔實作價（隱藏）。
    全省：全省 Net / 全省 Std × factor（§4.3）。
    指定區域（子集）：Σ(各選定區 Net) / 全省 Std × factor
      —— Net 用各區牌價加總，Std 沿用全省實作基準（§4.6 新鮮視 Std=504 設計）。
      ⚠️ 分區聚合規則待老闆確認（docs/簡易模式_待老闆確認.md §區域）。"""
    f = factor(media, sec, data)
    nat = _national(media, data)
    sel = _effective_regions(media, regions)
    if sel is None:
        return nat["Net"] / nat["Std"] * f
    net_sum = sum(data.pricing[media][r]["Net"] for r in sel)
    return net_sum / nat["Std"] * f


# =============================================================================
# 日期
# =============================================================================
def _daycols(start, end):
    days = []
    cur = start
    seen_month = set()
    while cur <= end:
        ml = None
        if cur.month not in seen_month:
            seen_month.add(cur.month)
            ml = f"{cur.month}月"
        days.append(DayCol(date=cur, weekend=cur.weekday() >= 5, month_label=ml))
        cur += timedelta(days=1)
    return days


def _minguo_month(d):
    return f"{d.year - 1911}年{d.month}月"


# =============================================================================
# 子公司建模（§4.3 / 4.4 / 4.6）
# =============================================================================
def _build_subsidiary(combo, budget, start, end, prod_cost, data, regions=None):
    days = _daycols(start, end)
    ndays = len(days)
    sheets = []
    for sec in combo["seconds"]:
        # 各區塊預算佔比 → 檔次
        plats = []
        for i, media in enumerate(combo["blocks"]):
            plats.append((media, combo["split"][i], sub_unit_net(media, sec, data, regions)))
        alloc = allocate_spots(budget, plats)

        blocks = []
        hidden = 0.0
        reach_spots = reach_imp = reach_traffic = 0.0
        for media in combo["blocks"]:
            n = alloc[media]
            unit = sub_unit_net(media, sec, data, regions)
            hidden += n * unit
            sch = distribute(n, ndays)
            rows = []
            if media == "家樂福":
                # 量販列
                mag_list = data.pricing["家樂福"]["量販_全省"]["List"]
                mag_std = data.pricing["家樂福"]["量販_全省"]["Std"]
                f = factor("家樂福", sec, data)
                stores_mag = data.stores["家樂福"]["量販"]
                rows.append(CueRow(
                    kind="main", station="家樂福", region="量販",
                    location=sc.PLATFORM_DISPLAY["家樂福量販"] + "-量販店",
                    stores=stores_mag, daypart=sc.DAYPART_SUBSIDIARY["家樂福量販"],
                    seconds=sec, spots=n, schedule=sch,
                    rate_num=(mag_list, mag_std, f), hidden_net=n * unit))
                # 超市列（計量販）
                sn = super_spots(n)
                ssch = distribute(sn, ndays)
                stores_super = data.stores["家樂福"]["超市"]
                rows.append(CueRow(
                    kind="super", station="", region="超市",
                    location=sc.PLATFORM_DISPLAY["家樂福超市"] + "-超市",
                    stores=stores_super, daypart=sc.DAYPART_SUBSIDIARY["家樂福超市"],
                    seconds=sec, spots=sn, schedule=ssch,
                    rate_text=sc.TXT_ON_MAG, hidden_net=0.0))
                reach_spots += n + sn
                reach_imp += stores_mag * n + stores_super * sn
                reach_traffic += (stores_mag * n + stores_super * sn) * sc.TRAFFIC_FACTOR
            else:
                f = factor(media, sec, data)
                daypart = sc.DAYPART_SUBSIDIARY[media]
                sel = _effective_regions(media, regions) or sc.REGIONS_ORDER
                for ri, region in enumerate(sel):
                    reg = data.pricing[media][region]           # 各區 Std 依 Pricing 表（§4.6）
                    stores_r = data.stores[media][region]
                    rows.append(CueRow(
                        kind="main",
                        station=media if ri == 0 else "",
                        region=region, location=sc.REGION_LABELS[region],
                        stores=stores_r, daypart=daypart, seconds=sec,
                        spots=n, schedule=sch,
                        rate_num=(reg["List"], reg["Std"], f),
                        hidden_net=(n * unit if ri == 0 else 0.0)))
                    reach_spots += n
                    reach_imp += stores_r * n
                    reach_traffic += stores_r * n * sc.TRAFFIC_FACTOR
            blocks.append(CueBlock(platform=media, rows=rows))

        vat = rhu((budget + prod_cost) * 0.05)
        fees = {"budget": budget, "prod": prod_cost, "vat": vat,
                "grand": budget + prod_cost + vat}
        sheets.append(CueSheet(
            title=_sheet_title_sub(budget, sec), seconds=sec, blocks=blocks,
            days=days, budget=budget, prod_cost=prod_cost, fees=fees,
            hidden_net_total=hidden,
            reach={"total_spots": int(reach_spots), "impressions": int(reach_imp),
                   "traffic": int(reach_traffic)}))
    return sheets


def _sheet_title_sub(budget, sec):
    man = budget / 10000
    man_s = f"{man:.1f}" if abs(man - round(man)) > 1e-9 else f"{int(round(man))}"
    return f"{man_s}萬版-{sec}秒版"


# =============================================================================
# 代理商建模（§4.7–4.11）
# =============================================================================
def _agency_unit_net(platform, sec):
    if platform == "family":
        net, std, base = sc.AGENCY_FAMILY_BASE
    else:
        net, std, base = sc.AGENCY_WJF_BASE
    return net / std / base * sec


def _list_per(agency, platform_disp, sec, data):
    tbl = None
    if data.agency_pricing:
        tbl = data.agency_pricing.get((agency, platform_disp))
    if not tbl:
        tbl = sc.AGENCY_LIST_PRICE.get((agency, platform_disp))
    if not tbl:
        return 0
    if sec in tbl:
        return int(tbl[sec])
    nearest = min(tbl.keys(), key=lambda s: abs(s - sec))
    return rhu(tbl[nearest] / nearest * sec)


def _build_2008(combo, budget, start, end, data):
    days = _daycols(start, end)
    ndays = len(days)
    agency = combo["agency"]
    sheets = []
    for sec in combo["seconds"]:
        if combo["platform"] == "family":
            unit = _agency_unit_net("family", sec)
            n = rhu(budget / unit)
            lp = _list_per(agency, "全家企頻", sec, data)
            rows = [CueRow(
                kind="main", station=ac.AGENCY_LABELS["2008傳媒"]["family"][0],
                region="全省", daypart="07:00-23:00", seconds=sec, spots=n,
                schedule=distribute(n, ndays), list_per=lp, list_total=lp * n,
                material=_mmdd(start - timedelta(days=7)))]
            rows[0].net_display = budget
            for pct in sc.BONUS_2008_FAMILY:
                b = rhu(n * pct / 100.0)
                r = CueRow(kind="bonus", seconds=sec, spots=b, schedule=None,
                           list_per=lp, list_total=lp * b)
                r.net_display = sc.TXT_REBATE
                rows.append(r)
            blocks = [CueBlock(platform="全家企頻", rows=rows)]
            fees = _fees_2008(budget)
        else:
            unit = _agency_unit_net("wjf", sec)
            n = rhu(budget / unit)
            sn = super_spots(n)
            lp = _list_per(agency, "萬家福", sec, data)
            mag = CueRow(kind="main", station=ac.AGENCY_LABELS["2008傳媒"]["mag"][0],
                         region="全省", daypart="0900-2300", seconds=sec, spots=n,
                         schedule=distribute(n, ndays), list_per=lp, list_total=lp * n,
                         material=_mmdd(start - timedelta(days=7)))
            mag.net_display = budget
            sup = CueRow(kind="super", station=ac.AGENCY_LABELS["2008傳媒"]["super"][0],
                         region="全省", daypart="0000-2400", seconds=sec, spots=sn,
                         schedule=distribute(sn, ndays))
            sup.net_display = sc.TXT_2008_ON_MAG
            rb = rhu(n * sc.BONUS_2008_WJF_PCT / 100.0)
            rbs = super_spots(rb)
            reb_mag = CueRow(kind="bonus", seconds=sec, spots=rb, schedule=None,
                             list_per=lp, list_total=lp * rb)
            reb_mag.net_display = sc.TXT_REBATE_SHORT
            reb_sup = CueRow(kind="super_bonus", seconds=sec, spots=rbs, schedule=None)
            reb_sup.net_display = sc.TXT_2008_ON_MAG
            blocks = [CueBlock(platform="萬家福", rows=[mag, sup, reb_mag, reb_sup])]
            fees = _fees_2008(budget)
        sheets.append(CueSheet(title=f"{'全家' if combo['platform']=='family' else '萬家福&樂家康'} {sec}秒",
                               seconds=sec, blocks=blocks, days=days, budget=budget,
                               fees=fees))
    return sheets


def _fees_2008(budget):
    ac_amt = rhu(budget * 0.03)
    tax = rhu((budget + ac_amt) * 0.05)
    return {"type": "2008", "budget": budget, "ac": ac_amt, "tax": tax,
            "total": budget + ac_amt + tax}


def _build_carat(combo, budget, start, end, data):
    days = _daycols(start, end)
    ndays = len(days)
    agency = combo["agency"]
    sheets = []
    for sec in combo["seconds"]:
        if combo["platform"] == "family":
            unit = _agency_unit_net("family", sec)
            n = rhu(budget / unit)
            lp = _list_per(agency, "全家企頻", sec, data)
            mkt = rhu(lp * sc.CARAT_MARKET_RATIO)
            uni = lp * sc.CARAT_UNI_RATIO
            main = CueRow(kind="main", station=ac.AGENCY_LABELS["凱絡"]["family"][0],
                          region="全省\n全家便利商店", daypart="0700-2300", seconds=sec,
                          spots=n, schedule=distribute(n, ndays), list_per=lp,
                          market_per=mkt, uni_per=uni, uni_total=uni * n)
            main.net_display = budget
            rows = [main]
            for pct in sc.BONUS_CARAT_FAMILY:
                b = rhu(n * pct / 100.0)
                r = CueRow(kind="bonus", seconds=sec, spots=b,
                           schedule=distribute(b, ndays), list_per=lp,
                           market_per=mkt, uni_per=uni, uni_total=uni * b)
                r.net_display = sc.TXT_REBATE
                rows.append(r)
            media_value = sum(r.uni_total for r in rows)
            blocks = [CueBlock(platform="全家企頻", rows=rows)]
        else:
            unit = _agency_unit_net("wjf", sec)
            n = rhu(budget / unit)
            sn = super_spots(n)
            lp = _list_per(agency, "萬家福", sec, data)
            mkt = rhu(lp * sc.CARAT_MARKET_RATIO)
            uni = lp * sc.CARAT_UNI_RATIO
            mag = CueRow(kind="main", station=ac.AGENCY_LABELS["凱絡"]["mag"][0],
                         region="萬家福(量販)", daypart="0900-2300 ", seconds=sec,
                         spots=n, schedule=distribute(n, ndays), list_per=lp,
                         market_per=mkt, uni_per=uni, uni_total=uni * n)
            mag.net_display = budget
            sup = CueRow(kind="super", station="", region="樂家康(超市)",
                         daypart="0000-2400 ", seconds=sec, spots=sn,
                         schedule=distribute(sn, ndays), list_per=lp,
                         market_per=mkt, uni_per=uni, uni_total=uni * sn)
            sup.net_display = sc.TXT_CARAT_ON_MAG
            rows = [mag, sup]
            media_value = sum(r.uni_total for r in rows)
            blocks = [CueBlock(platform="萬家福", rows=rows)]
        fees = _fees_carat(budget)
        fees["media_value"] = media_value
        fees["discount_value"] = media_value - budget
        title = f"全家-{sec}秒" if combo["platform"] == "family" else f"萬家福 & 樂家康 {sec}秒"
        sheets.append(CueSheet(title=title, seconds=sec, blocks=blocks, days=days,
                               budget=budget, fees=fees))
    return sheets


def _fees_carat(budget):
    vat = rhu(budget * 0.05)
    return {"type": "carat", "subtotal": budget, "ac_free": sc.CARAT_AC_FREE,
            "ac": 0, "vat": vat, "grand": budget + vat}


def _mmdd(d):
    return f"{d.month}/{d.day}"


# =============================================================================
# 唯一入口
# =============================================================================
def build_model(combo_key, budget, start, end, *, client="", tax_id="", product="",
                sales="", campaign="", prod_cost=0, today=None, data=None, regions=None):
    if combo_key not in sc.COMBOS:
        raise ValueError(f"未知組合：{combo_key}")
    ndays = (end - start).days + 1
    if ndays > sc.MAX_DAYS:
        raise ValueError(
            f"簡易模式單張最多 {sc.MAX_DAYS} 天（{sc.MAX_DAYS // 7} 週）；"
            "更長走期請用一般 CUE 分月製作。")
    combo = sc.COMBOS[combo_key]
    budget = int(budget)
    if data is None:
        data = fallback_sheetdata()
    if today is None:
        today = start

    fam = combo["family"]
    if fam == "subsidiary":
        sheets = _build_subsidiary(combo, budget, start, end, int(prod_cost), data, regions)
    elif fam == "2008":
        sheets = _build_2008(combo, budget, start, end, data)
    else:
        sheets = _build_carat(combo, budget, start, end, data)

    sign = start - timedelta(days=7)
    material_due = start - timedelta(days=7)
    billing = _minguo_month(end)
    pay = f"{start.year - 1911}.XX.XX"

    remarks = _subsidiary_remarks(combo, sign, billing, pay) if fam == "subsidiary" else \
        _agency_remarks(combo, start, end, budget)

    model = CueModel(
        combo_key=combo_key, combo_label=combo["label"], family=fam,
        client=client, tax_id=tax_id, product=product, sales=sales,
        campaign=campaign, start=start, end=end, made_date=today,
        medium_label=combo.get("medium", ""), remarks=remarks,
        sign_deadline=sign, material_due=material_due, billing_month=billing,
        payment_date_text=pay, sheets=sheets)
    model.filename = _filename(combo, budget, sales, client, today)
    return model


def _subsidiary_remarks(combo, sign, billing, pay):
    has_fv = "新鮮視" in combo["blocks"]
    wd = _WEEK_CH[sign.weekday()]
    sign_s = f"{sign.strftime('%Y/%m/%d')} ({wd})"
    out = []
    for tmpl, red in sc.REMARKS_SUBSIDIARY:
        txt = tmpl.format(sign=sign_s, bill=billing, pay=pay,
                          fv=sc.REMARKS_SUB_FV_SUFFIX if has_fv else "")
        out.append((txt, red))
    return out


def _agency_remarks(combo, start, end, budget):
    agency = combo["agency"]
    if agency == "凱絡":
        sign = start - timedelta(days=7)
        pay = _carat_payment(start, end, budget)
        lines = ac.default_remarks("凱絡", sign_date=sign, payment_note=pay)
        return [(t, i == 4) for i, t in enumerate(lines)]  # 第5行(請款)紅字
    lines = sc.REMARKS_2008_WJF if combo["platform"] == "wjf" else sc.REMARKS_2008_FAMILY
    return [(t, False) for t in lines]


def _carat_payment(start, end, budget):
    """凱絡請款說明：依各月天數比例拆分（千元四捨五入、尾月吃餘數），
    格式 {M}月媒體費${x:,}(Net)，多月用「、」串接（§3-2）。"""
    total_days = (end - start).days + 1
    months = []
    cur = start
    while cur <= end:
        if cur.month == 12:
            mlast = date(cur.year, 12, 31)
        else:
            mlast = date(cur.year, cur.month + 1, 1) - timedelta(days=1)
        seg_end = min(mlast, end)
        months.append((cur.month, (seg_end - cur).days + 1))
        cur = seg_end + timedelta(days=1)
    parts, allocated = [], 0
    for i, (m, dcnt) in enumerate(months):
        amt = budget - allocated if i == len(months) - 1 else rhu(budget * dcnt / total_days / 1000) * 1000
        allocated += amt
        parts.append(f"{m}月媒體費${amt:,}(Net)")
    return "、".join(parts)


def _filename(combo, budget, sales, client, today):
    """§3-1 檔名：MMDD 前綴 + 半形組合名 + 業務暱稱。"""
    man = budget // 10000
    secs = ".".join(str(s) for s in sorted(combo["seconds"]))
    mmdd = today.strftime("%m%d")
    if combo["family"] == "subsidiary":
        suffix = f"-{sales}" if sales else ""
        # 例：0907 企頻+新鮮視(10.15.20.30秒) 25萬專案-宜.xlsx
        return f"{mmdd} {combo['fname']}({secs}秒) {man}萬專案{suffix}.xlsx"
    plat = "全家" if combo["platform"] == "family" else "萬家福&樂家康"
    cli = f"-{client}" if client else ""
    # 例：0907 2008傳媒-統一企業 全家單組 (10.15.20.30秒) 25萬專案.xlsx
    return f"{mmdd} {combo['agency']}{cli} {plat}單組 ({secs}秒) {man}萬專案.xlsx"
