# -*- coding: utf-8 -*-
"""健康視CUE（宜歆 10/29 #6；spec docs/specs/健康視CUE.md）：曝光／定價計算、備註、Excel 值版。"""
import io
from datetime import date

from openpyxl import load_workbook

import health_cue as h
import utils

D = dict(format="鉑霖", client="小檸檬媒體整合行銷有限公司", advertiser="", tax_id="55683289", ad_name="",
         sales="蔡宜歆", seconds=15, start=date(2026, 11, 23), end=date(2026, 12, 22), days="週一至週五",
         budget=300000, sign_deadline=date(2026, 10, 30), billing_month="116/1月", payment_date=date(2027, 2, 22))


def test_calc_matches_reference():
    # 宜歆 11/3 #6-2：基準改 300面直客報價未稅（15秒 30 萬＝38.4 萬次、定價 375,000×30/30）
    assert h.calc(15, 300000) == {"impressions": 384000, "list": 375000, "net": 300000, "vat": 15000, "gross": 315000}
    assert h.calc(10, 50000)["impressions"] == 96000           # 384000/200000*50000
    for s, (_l, direct, _p) in h.DEFAULT_PRICING.items():     # 一個直客報價＝38.4 萬次
        assert h.calc(s, direct)["impressions"] == 384000


def test_calc_uses_given_pricing():
    p = {15: (393750, 500000, 262500)}
    assert h.calc(15, 250000, p)["impressions"] == 192000


def test_remarks_and_defaults():
    rem = h.remarks(date(2026, 10, 30), "116/1月", date(2027, 2, 22))
    assert rem[0] == ("1. 請於 2026/10/30 (五) 下午1500前回簽。", "FF0000")
    assert rem[4][0] == "5. 付款兌現日期：116/2/22前兌現。" and rem[5][1] == "0000FF" and len(rem) == 6
    assert h.default_billing(date(2026, 12, 22)) == "116/1月"
    assert h.default_payment(date(2026, 12, 22)) == date(2027, 1, 31)
    assert h.default_payment(date(2026, 11, 5)) == date(2026, 12, 31)


def test_excel_values():
    ws = load_workbook(io.BytesIO(h.build_excel(D))).active
    assert ws["B1"].value.startswith("鉑霖行動行銷") and ws["C4"].value == "鉑霖行動行銷 - 蔡宜歆"
    assert ws["G9"].value == "11/23-12/22\n執行週一至週五" and ws["F9"].value.startswith("15秒")
    assert (ws["H9"].value, ws["I9"].value, ws["J9"].value) == (384000, 375000, 300000)   # 值版，無公式
    assert (ws["J12"].value, ws["J13"].value) == (15000, 315000)
    assert ws["C11"].value == D["client"] and ws["B20"].value.startswith("6. 若實際曝光次數")
    ws2 = load_workbook(io.BytesIO(h.build_excel(dict(D, format="聲活", advertiser="廣告主乙", days="每日")))).active
    assert ws2["B1"].value.startswith("聲活數位") and ws2["C11"].value == "廣告主乙" and ws2["G9"].value.endswith("執行每日")


def test_platform_text_for_ragic():
    rows = [{"media": "全民健康視", "region": "全台"}]
    assert utils.build_platform_text(rows) == "全民健康視"
    assert utils.build_platform_detail_text(rows, {}) == "全民健康視"


def test_filename():
    assert h.filename("客戶甲", 15, 300000, "宜", today=date(2026, 10, 30)) == "1030 客戶甲 全民健康視(15秒) 30萬-宜.xlsx"


GIFT = dict(seconds=30, start=date(2026, 12, 1), end=date(2026, 12, 31), days="週一至週五")


def test_calc_rows_gift_row_issue9():
    """宜歆 11/4 #9：主列 30秒 10 萬＋加贈列自填 80,000 次、紅字公益贈檔（截圖數字）。"""
    rows = [dict(GIFT, net=100000, impressions=None, label=""),
            dict(GIFT, net=0, impressions=80000, label="公益贈檔")]
    items, tot = h.calc_rows(rows)
    assert (items[0]["impressions"], items[0]["list"], items[0]["label"]) == (64000, 125000, "")
    assert (items[1]["impressions"], items[1]["list"], items[1]["label"]) == (80000, 156250, "公益贈檔")
    assert (tot["impressions"], tot["list"], tot["net"], tot["vat"], tot["gross"]) == (144000, 281250, 100000, 5000, 105000)


def test_calc_row_manual_only_issue10():
    """#10：只填秒數、曝光、實收 0 → 定價＝定價未稅×曝光÷384,000；沒填文字顯示「贈檔」。"""
    it = h.calc_row(dict(GIFT, net=0, impressions=144000, label=""))
    assert it == {"impressions": 144000, "list": 281250, "net": 0, "label": "贈檔"}
    assert h.count_days(date(2026, 12, 1), date(2026, 12, 31), "週一至週五") == 23
    assert h.count_days(date(2026, 12, 1), date(2026, 12, 31), "每日") == 31
    assert h.count_days(date(2026, 12, 2), date(2026, 12, 1), "每日") == 0


def test_excel_multi_rows():
    rows = [dict(GIFT, net=100000, impressions=None, label=""),
            dict(GIFT, net=0, impressions=80000, label="公益贈檔")]
    ws = load_workbook(io.BytesIO(h.build_excel(dict(D, rows=rows)))).active
    assert (ws["H9"].value, ws["I9"].value, ws["J9"].value) == (64000, 125000, 100000)
    assert (ws["H10"].value, ws["I10"].value, ws["J10"].value) == (80000, 156250, "公益贈檔")
    assert ws["J10"].font.color.rgb.endswith("FF0000") and ws["F10"].value.startswith("30秒")
    assert ws["F11"].value == "Total" and (ws["H11"].value, ws["I11"].value, ws["J11"].value) == (144000, 281250, 100000)
    assert (ws["J13"].value, ws["J14"].value) == (5000, 105000)
    assert ws["B15"].value.startswith("Remarks") and ws["B21"].value.startswith("6. 若實際曝光次數")
    assert ws.print_area.endswith("$J$21")
    html = h.preview_html(dict(D, rows=rows))
    assert "公益贈檔" in html and "281,250" in html


def test_filename_zero_budget():
    assert h.filename("客戶甲", 30, 0, "宜", today=date(2026, 11, 4)) == "1104 客戶甲 全民健康視(30秒)-宜.xlsx"
