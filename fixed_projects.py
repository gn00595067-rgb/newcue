"""
固定專案（走期／秒數／檔次／實收皆固定，業務只填客戶資料）
來源：桌面「2027 春節_中元專案 萬家福_樂家康 各30萬專案版.xlsx」，規格見 docs/specs/固定專案_中元限定.md
產出與一般 CUE 相同結構的 rows，直接交給 excel_renderer／html_generator（東吳／聲活／鉑霖共用）。
"""

from datetime import date

# 牌價基準（參考檔公式：量販 300000/420、超市 220000/720，專區 ×2）
_MAG_LIST, _MAG_STD = 300000, 420
_SUP_LIST, _SUP_STD = 220000, 720

FIXED_PROJECTS = {
    "萬家福/樂家康 116年度過年限定專案": {
        "short": "過年限定",
        "start": date(2027, 1, 21),
        "end": date(2027, 2, 10),
        "seconds": 20,
        "budget": 300000,
        "medium": "萬家福/樂家康 116年度過年限定專案",
        "remark": "此為116年度過年專案，限定6席。",
        "lines": [
            ("超市", "00-24 賀歲拜年", 6, ("sup", 0.85), 15),
            ("量販", "09-23 年貨大街專區", 8, ("mag", 2)),
            ("超市", "00-24 年貨大街專區", [14] * 18 + [12] * 3, None),
            ("量販", "09-23", 14, ("mag", 1)),
            ("超市", "00-24", 24, None),
            ("超市", "00-24", 3, ("sup", 1)),
        ],
    },
    "萬家福/樂家康 116年度中元限定專案": {
        "short": "中元限定",
        "start": date(2027, 7, 27),
        "end": date(2027, 8, 16),
        "seconds": 20,
        "budget": 300000,
        "medium": "萬家福/樂家康 116年度中元限定專案",
        "remark": "此為116年度中元專案，限定6席。",
        # (通路, Day-part, 每日檔次 or 每日 list, rate 計算[, 秒數，省略＝專案預設])；順序照參考檔
        "lines": [
            ("量販", "09-23 中元專區", 8, ("mag", 2)),
            ("超市", "00-24 中元專區", [14] * 18 + [12] * 3, None),
            ("量販", "09-23", 14, ("mag", 1)),
            ("超市", "00-24", 24, None),
            ("超市", "00-24", 3, ("sup", 1)),
        ],
    },
}


def project_days(p):
    return (p["end"] - p["start"]).days + 1


def build_project_rows(p, store_counts_num=None):
    """固定專案 → 一般 CUE rows。Package-cost 合併為一格實收；超市列 rate 顯示「計量販」。
    Station／Location 顯示（萬家福／樂家康、量販店／超市）由 utils.cue_station／cue_location 處理。
    同通路第二次出現的列標 skip_store_total，聲活／鉑霖總店數不重複加。"""
    store_counts_num = store_counts_num or {}
    stores = {"量販": store_counts_num.get("家樂福_量販") or 62,
              "超市": store_counts_num.get("家樂福_超市") or 217}
    ndays = project_days(p)
    rows, seen = [], set()
    for kind, daypart, daily, rate_spec, *sec in p["lines"]:
        sch = list(daily) if isinstance(daily, list) else [daily] * ndays
        assert len(sch) == ndays, f"{daypart} 檔次天數 {len(sch)} ≠ 走期 {ndays}"
        spots = sum(sch)
        if rate_spec is None:
            rate = "計量販"
        else:
            base, mult = rate_spec
            lst, std = (_MAG_LIST, _MAG_STD) if base == "mag" else (_SUP_LIST, _SUP_STD)
            rate = round(lst / std * spots * mult)
        rows.append({
            "media": "家樂福",
            "region": f"全省{kind}",
            "program_num": stores[kind],
            "daypart": daypart,
            "seconds": sec[0] if sec else p["seconds"],
            "spots": spots,
            "schedule": sch,
            "rate_display": rate,
            "pkg_display": rate,
            "is_pkg_member": True,
            "nat_pkg_display": p["budget"],
            "skip_store_total": kind in seen,
        })
        seen.add(kind)
    return rows


def project_seconds_text(p):
    """專案內所有秒數，例：「15、20秒」。"""
    secs = sorted({(ln[4] if len(ln) > 4 else p["seconds"]) for ln in p["lines"]})
    return "、".join(str(x) for x in secs) + "秒"


def project_total_list(rows):
    """rate (Net) 合計（「計量販」等文字列不計）。"""
    return sum(r["rate_display"] for r in rows if isinstance(r["rate_display"], (int, float)))
