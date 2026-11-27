# -*- coding: utf-8 -*-
"""CUE 曝光結論「其中加贈帶來曝光次數」一行（主管 11/27）。"""
import io
from datetime import date

import pytest
from openpyxl import load_workbook

from excel_renderer import generate_excel_from_scratch
from html_generator import generate_html_preview
from reach_gift import gift_impressions, gift_reach_line

D = 31


def _r(media, region, stores, spots, gift=False):
    r = {"media": media, "region": region, "program_num": stores, "daypart": "07:00-23:00", "seconds": 15,
         "spots": spots, "schedule": [spots // D] * D, "rate_display": 1000, "pkg_display": 1000,
         "is_pkg_member": False, "nat_pkg_display": 0}
    if gift:
        r.update({"is_rebate": True, "program_num": "", "pkg_display": "回饋"})
    return r


PAID = [_r("全家廣播", "中區", 850, 930)]
GIFT = PAID + [_r("全家廣播", "中區", 850, 93, gift=True)]
THREE = GIFT + [_r("新鮮視", "北區", 1209, 310), _r("家樂福", "全省量販", 62, 62), _r("家樂福", "全省超市", 217, 124)]


def _cells(rows, fmt):
    b = generate_excel_from_scratch(fmt, date(2027, 3, 1), date(2027, 3, 31), "客", "", "品", rows, ["1.x"], 230000, 0, "業務", 287040)
    ws = load_workbook(io.BytesIO(b)).worksheets[0]
    return {c.coordinate: c.value for row in ws.iter_rows() for c in row if isinstance(c.value, str)}


def test_計算():
    assert gift_impressions(PAID, D) == 0 and gift_reach_line(PAID, D) is None
    assert gift_impressions(GIFT, D) == 850 * (93 // D) * D
    assert gift_reach_line(GIFT, D) == f"【其中加贈帶來曝光次數 : {850 * (93 // D) * D:,}】"


@pytest.mark.parametrize("fmt", ["東吳", "聲活", "鉑霖"])
def test_CUE有加贈才多一行(fmt):
    assert not any("其中加贈" in v for v in _cells(PAID, fmt).values())
    assert any(v.startswith("【其中加贈帶來曝光次數") for v in _cells(GIFT, fmt).values())


@pytest.mark.parametrize("fmt", ["東吳", "聲活", "鉑霖"])
def test_三平台時寫在費用區下一列(fmt):
    cells = _cells(THREE, fmt)
    reach = sorted((int("".join(ch for ch in k if ch.isdigit())), v) for k, v in cells.items()
                   if k.startswith("A") and v.startswith("【"))
    assert len(reach) == 4 and reach[-1][1].startswith("【其中加贈")
    assert reach[-1][0] == reach[-2][0] + 1


def test_html預覽():
    html = generate_html_preview(GIFT, D, date(2027, 3, 1), date(2027, 3, 31), "客", "", "x", "聲活", [], 1, 1, 1, 0)
    html = "".join(html) if isinstance(html, list) else html
    assert "其中加贈帶來曝光次數" in html
