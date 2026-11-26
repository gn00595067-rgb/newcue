# -*- coding: utf-8 -*-
"""鉑霖實收價(含稅)列＋備註現金折扣（主管 11/26 Q2，樣張：共享行銷 中彰投 30 秒）。"""
import io
from datetime import date

from openpyxl import load_workbook

from excel_renderer import generate_excel_from_scratch
from html_generator import generate_html_preview
from net_terms import apply_cash_discount, net_after_terms, net_terms_label, pct_value
from utils import get_remarks_text

ROWS = [{"media": "全家廣播", "region": "中區", "program_num": 850, "daypart": "07:00-23:00", "seconds": 30,
         "spots": 920, "schedule": [30] * 26 + [28] * 5, "rate_display": 287040, "pkg_display": 230000,
         "is_pkg_member": False, "nat_pkg_display": 0}]


def _values(terms):
    rem = apply_cash_discount(get_remarks_text(date(2027, 2, 18), "2027年2月", date(2027, 4, 30)), terms[1] if terms else 0)
    b = generate_excel_from_scratch("鉑霖", date(2027, 3, 1), date(2027, 3, 31), "共享行銷有限公司", "24842636",
                                    "(暫定) 台中市就服處銀髮人才服務據點", ROWS, rem, 230000, 8000, "許詠婕", 287040,
                                    net_terms=terms)
    ws = load_workbook(io.BytesIO(b)).worksheets[0]
    return [c.value for row in ws.iter_rows() for c in row if c.value is not None], ws


def test_樣張金額():
    vals, _ = _values((15, 2))
    assert 11900 in vals and 249900 in vals          # 製作費也課稅
    assert 208167 in vals                            # 249,900 × 0.85 × 0.98
    assert "實收價(含稅)\n已計15%退傭+2%現折" in vals
    assert any(isinstance(v, str) and v.startswith("6.付款兌現日期：116.04.30前，若於廣告上檔前完成匯款方享有2%現金折扣") for v in vals)
    assert any(isinstance(v, str) and v.startswith("7.曝光次數與店舖人流量為預估值") for v in vals)


def test_沒有退傭現折不加列():
    vals, _ = _values((0, 0))
    assert not any(isinstance(v, str) and v.startswith("實收價") for v in vals)
    vals, _ = _values(None)
    assert not any(isinstance(v, str) and "現金折扣" in v for v in vals)


def test_工具函式():
    assert net_after_terms(249900, (15, 2)) == 208167
    assert net_after_terms(249900, (0, 0)) is None
    assert pct_value("15%") == 15 and pct_value(0.02) == 2 and pct_value("") == 0
    assert net_terms_label(15, 0) == "15%退傭" and net_terms_label(0, 2.5) == "2.5%現折"
    assert apply_cash_discount(["6.付款兌現日期：116.04.30前"], 2) == ["6.付款兌現日期：116.04.30前，若於廣告上檔前完成匯款方享有2%現金折扣。"]


def test_html預覽():
    html = generate_html_preview(ROWS, 31, date(2027, 3, 1), date(2027, 3, 31), "共享行銷", "24842636", "x", "鉑霖",
                                 [], 287040, 249900, 230000, 8000, net_terms=(15, 2))
    html = "".join(html) if isinstance(html, list) else html
    assert "實收價(含稅) 已計15%退傭+2%現折：$208,167" in html
