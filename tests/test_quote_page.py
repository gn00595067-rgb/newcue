# -*- coding: utf-8 -*-
"""一頁式報價頁（第二階段 2-4）：能產出 PDF、內容含關鍵數字。"""
from datetime import date

import fitz

import plan_compare as pc
import quote_page as qp

ROWS = [{"media": "全家廣播", "region": "中區", "program_num": 850, "daypart": "07:00-23:00", "seconds": 30,
         "spots": 920, "schedule": [30] * 26 + [28] * 5}]


def _text(b):
    return "".join(p.get_text() for p in fitz.open(stream=b, filetype="pdf"))


def test_單一方案報價卡():
    t = _text(qp.build_quote_pdf(ROWS, 31, 230_000, 249_900, date(2027, 3, 1), date(2027, 3, 31), client="共享行銷"))
    assert "249,900" in t and "782,000" in t and "850 店" in t and "共享行銷" in t


def test_多方案總覽():
    a = pc.make_plan("方案 A", ROWS, 31, 230_000)
    b = pc.make_plan("方案 B", ROWS * 2, 31, 400_000)
    t = _text(qp.build_compare_pdf([a, b], client="共享行銷"))
    assert "2 方案總覽" in t and "方案 B" in t and "曝光最多" in t
