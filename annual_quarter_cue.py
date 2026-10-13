"""
年約／季約細 CUE 模組 (Annual / Quarterly Contract -> Fixed-Wave CUE)
將已知總檔次與實收金額分配至各波段走期，每波段產出獨立 Excel/PDF。
"""

import math
from datetime import datetime, timedelta
from utils import calculate_schedule, get_sec_factor


def round_to_even(x):
    """將數值進位為最接近的偶數整數；小數或奇數時進位。"""
    n = int(math.ceil(float(x)))
    if n % 2 != 0:
        n += 1
    return n


def distribute_by_wave_days(total_spots, total_net, waves):
    """
    依各波段天數比例，將總檔次與總實收分配至各波。
    waves: list of (start_date, end_date) (date 或 datetime)
    回傳: list of (spots, net) 每個波一組，spots/net 為偶數/整數。
    """
    if not waves:
        return []
    total_days = 0
    days_per_wave = []
    for s, e in waves:
        d = (e - s).days + 1
        total_days += d
        days_per_wave.append(d)
    if total_days <= 0:
        return [(0, 0)] * len(waves)
    result = []
    spots_used = 0
    net_used = 0
    for i, days in enumerate(days_per_wave):
        ratio = days / total_days
        if i < len(waves) - 1:
            sp = round_to_even(total_spots * ratio)
            nt = int(round(total_net * ratio))
            spots_used += sp
            net_used += nt
        else:
            sp = round_to_even(total_spots - spots_used)
            nt = int(total_net - net_used)
        result.append((max(0, sp), max(0, nt)))
    return result


def build_wave_rows(combos, wave_start, wave_end, wave_spots_list, wave_net_list, pricing_db, sec_factors, store_counts_num, regions_order=None):
    """
    為單一波段產出 CUE 表所需的 rows（與 calculator 產出結構一致）。
    combos: list of dict {"media": str, "region": str, "seconds": int}
    wave_spots_list: list of int，與 combos 對應，該波每組合的檔次
    wave_net_list: list of int，與 combos 對應，該波每組合的實收(未稅)
    regions_order: 六區順序，用於全省時展開為六列；若為 None 則使用預設六區。
    """
    if regions_order is None:
        regions_order = ["北區", "桃竹苗", "中區", "雲嘉南", "高屏", "東區"]
    rows = []
    days_count = (wave_end - wave_start).days + 1
    if days_count <= 0:
        return rows
    for idx, combo in enumerate(combos):
        media = combo["media"]
        region = combo["region"]
        seconds = combo["seconds"]
        spots = wave_spots_list[idx] if idx < len(wave_spots_list) else 0
        net_val = wave_net_list[idx] if idx < len(wave_net_list) else 0
        if spots <= 0:
            continue
        spots = round_to_even(spots)
        factor = get_sec_factor(media, seconds, sec_factors)
        if media in ["全家廣播", "新鮮視"] and media in pricing_db:
            db = pricing_db[media]
            std_spots_ref = db["Std_Spots"]
            if region == "全省":
                # 仿照一般 CUE：全省時展開為六區各一列
                calc_std = std_spots_ref
                sch = calculate_schedule(spots, days_count)
                daypart = db.get("Day_Part", "")
                for r in regions_order:
                    if r not in db:
                        continue
                    list_price_region = db[r][0]
                    unit_rate_display = (list_price_region / calc_std) * factor
                    total_rate_display = int(unit_rate_display * spots)
                    program_num = store_counts_num.get(f"新鮮視_{r}" if media == "新鮮視" else r, 0)
                    rows.append({
                        "media": media,
                        "region": r,
                        "program_num": program_num,
                        "daypart": daypart,
                        "seconds": seconds,
                        "spots": spots,
                        "schedule": sch,
                        "rate_display": total_rate_display,
                        "pkg_display": total_rate_display,
                        "is_pkg_member": True,
                        "nat_pkg_display": net_val,
                    })
                continue
            if region not in db:
                continue
            list_price = db[region][0]
            net_price = db[region][1]
            # 依 Pricing 表各區 Std_Spots（新鮮視不再 *2）
            calc_std = (db.get("_Region_Std_Spots") or {}).get(region) or std_spots_ref
            unit_list = (list_price / calc_std) * factor
            unit_net = (net_price / calc_std) * factor
            rate_display = int(unit_list * spots)
            pkg_display = net_val if net_val > 0 else int(unit_net * spots)
            sch = calculate_schedule(spots, days_count)
            program_num = store_counts_num.get(f"新鮮視_{region}" if media == "新鮮視" else region, 0)
            daypart = db.get("Day_Part", "")
            rows.append({
                "media": media,
                "region": region,
                "program_num": program_num,
                "daypart": daypart,
                "seconds": seconds,
                "spots": spots,
                "schedule": sch,
                "rate_display": rate_display,
                "pkg_display": pkg_display,
                "is_pkg_member": False,
                "nat_pkg_display": 0,
            })
        elif media == "家樂福" and media in pricing_db:
            db = pricing_db["家樂福"]
            if "量販_全省" not in db:
                continue
            base_std = db["量販_全省"]["Std_Spots"]
            base_list = db["量販_全省"]["List"]
            base_net = db["量販_全省"]["Net"]
            unit_list = (base_list / base_std) * factor
            unit_net = (base_net / base_std) * factor
            rate_display = int(unit_list * spots)
            pkg_display = net_val if net_val > 0 else int(unit_net * spots)
            sch = calculate_schedule(spots, days_count)
            rows.append({
                "media": media,
                "region": "全省量販",
                "program_num": store_counts_num.get("家樂福_量販", 0),
                "daypart": db["量販_全省"]["Day_Part"],
                "seconds": seconds,
                "spots": spots,
                "schedule": sch,
                "rate_display": rate_display,
                "pkg_display": pkg_display,
                "is_pkg_member": False,
            })
    return rows


# =============================================================================
# 年約季約 → 代理商格式（2008傳媒／凱絡），規格見 docs/specs/格式選擇擴充.md 需求 2
# =============================================================================
AGENCY_MEDIA = ("全家廣播", "家樂福")   # 代理商格式只有全家企頻、萬家福．樂家康（全省）


def agency_combo_ok(combo):
    """組合能否出代理商格式：限全家廣播（全省）／萬家福．樂家康。"""
    return combo["media"] in AGENCY_MEDIA and (combo["media"] == "家樂福" or combo["region"] == "全省")


def build_wave_agency_model(agency, combos, wave_start, wave_end, wave_spots_list, wave_net_list, *,
                            client_name="", product_name="", campaign="", comp_mode=None,
                            fam_auto_rebate=True, fam_rebate_pct=0.0, wjf_rebate_pct=0.0,
                            ac_pct=None, material_due=None, agency_pricing=None,
                            remarks=None, payment_note=""):
    """
    單一波段 → 代理商 CUE model（交給 agency_excel.generate_agency_excel／agency_ui.build_agency_html）。
    每個組合各建一張表（同平台不同秒數各一張），檔次＝業務填的檔次、實收＝業務填的實收；
    回饋列、凌晨補償、AC 沿用代理商CUE 規則。不支援的組合（新鮮視、分區）略過。
    """
    import agency_cue as ac

    if comp_mode is None:
        comp_mode = ac.COMP_PLAN1
    if material_due is None:
        material_due = ac.minus_business_days(wave_start, 5)
    sheets, logs = [], []
    net_total = 0
    for idx, combo in enumerate(combos):
        spots = int(wave_spots_list[idx]) if idx < len(wave_spots_list) else 0
        net = int(wave_net_list[idx]) if idx < len(wave_net_list) else 0
        if spots <= 0 or not agency_combo_ok(combo):
            continue
        sec = int(combo["seconds"])
        if combo["media"] == "全家廣播":
            fam_cfg = {"enabled": True, "seconds": sec, "share": 100, "rebate_pct": float(fam_rebate_pct),
                       "spots_override": spots, "auto_rebate": bool(fam_auto_rebate)}
            wjf_cfg = None
        else:
            fam_cfg = None
            wjf_cfg = {"enabled": True, "seconds": sec, "share": 100, "rebate_pct": float(wjf_rebate_pct),
                       "mag_override": spots, "is_rebate_wave": False}
        m = ac.build_agency_model(agency, client_name, product_name, campaign, wave_start, wave_end,
                                  net, fam_cfg, wjf_cfg, comp_mode, material_due, ac_pct,
                                  agency_pricing=agency_pricing, payment_note="x", remarks=[])
        for sh in m["sheets"]:
            if sh["platform"] == ac.PLATFORM_FAMILY and agency == "2008傳媒":
                # 2008 全家「合計」原為 單檔實作價×檔次；年約以業務填的實收為準
                for r in sh["rows"]:
                    if r["kind"] == ac.KIND_MAIN:
                        r["net_display"] = net
                sh["fees"] = ac._build_fees(agency, net, ac_pct)
        sheets.extend(m["sheets"])
        logs.extend(m["logs"])
        net_total += net
    if remarks is None:
        remarks = ac.default_remarks(agency)
    if not payment_note:
        payment_note = ac.default_payment_note(wave_start, wave_end, net_total)
    return {
        "agency": agency, "client_name": client_name, "product_name": product_name,
        "campaign": campaign, "start_date": wave_start, "end_date": wave_end,
        "budget_total": net_total, "material_due": material_due, "payment_note": payment_note,
        "remarks": remarks, "sheets": sheets, "logs": logs,
    }
