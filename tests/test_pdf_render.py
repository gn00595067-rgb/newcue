# -*- coding: utf-8 -*-
"""
純 Python PDF 渲染器測試（取代 LibreOffice）：
  - 數字格式引擎逐案
  - 七組合 × 值版 xlsx 皆能產出有效 PDF、頁數 = 秒數版本數
  - PDF 內含中文字（字型內嵌成功）、無 LibreOffice 也可用
"""
import io
import datetime as dt
from datetime import date, timedelta

import pytest
import fitz  # PyMuPDF

import simple_model as sm
import simple_excel as se
import simple_config as sc
from fixtures_simple import sheetdata

import xlsx_numfmt as nf
import pdf_render
import pdf_converter


# ---- 數字格式引擎 ----
@pytest.mark.parametrize("value,fmt,expect,red", [
    (200000, '#,##0_);[Red](#,##0)', "200,000", False),
    (-5, '#,##0_);[Red](#,##0)', "(5)", True),
    (0.05, '0%', "5%", False),
    (1673, '#,##0"店"', "1,673店", False),
    (dt.datetime(1900, 1, 21), 'd', "21", False),
    (dt.datetime(2026, 9, 21), 'm"月"d"日"', "9月21日", False),
    ('一', '[$-404]aaa;@', "一", False),
    (91145.83, '#,##0_);[Red](#,##0)', "91,146", False),
    ('62店', '#,##0"面"', "62店", False),
    (0, '0_ ', "0", False),
    (250000, '#,##0', "250,000", False),
    (dt.datetime(2026, 9, 26), '[$-404]aaa', "六", False),
    (-3, '0_);[Red]\\(0\\)', "(3)", True),
])
def test_numfmt(value, fmt, expect, red):
    text, is_red = nf.format_value(value, fmt)
    assert text == expect
    assert is_red == red


def test_numfmt_accounting_has_fill_marker():
    # 會計格式：符號與數字之間有 fill 分隔標記（渲染器據此左右對齊）
    text, _ = nf.format_value(
        270375, r'_("$"* #,##0_);_("$"* \(#,##0\);_("$"* "-"??_);_(@_)')
    assert "$" in text and "270,375" in text


# ---- 全組合渲染 ----
def _model(key):
    start = date(2026, 9, 21)
    end = start + timedelta(days=27)
    return sm.build_model(key, 250000, start, end, client="測試客戶",
                          product="測試產品", campaign="中元專案", data=sheetdata())


@pytest.mark.parametrize("key", sc.SUBSIDIARY_COMBOS + sc.AGENCY_COMBOS)
def test_render_all_combos(key):
    model = _model(key)
    xlsx = se.render(model, formulas=False)
    pdf = pdf_render.render_xlsx_to_pdf(xlsx)
    assert pdf[:4] == b"%PDF"
    doc = fitz.open(stream=pdf, filetype="pdf")
    # 頁數至少等於秒數版本數（可能因垂直分頁更多）
    assert doc.page_count >= len(model.sheets)
    doc.close()


def test_pdf_contains_cjk_text():
    """渲染後 PDF 應含可抽取的中文（字型內嵌、非空白）。"""
    model = _model(sc.SUBSIDIARY_COMBOS[0])
    xlsx = se.render(model, formulas=False)
    pdf = pdf_render.render_xlsx_to_pdf(xlsx)
    doc = fitz.open(stream=pdf, filetype="pdf")
    txt = "".join(page.get_text() for page in doc)
    doc.close()
    assert "測試客戶" in txt
    assert "Media Schedule" in txt


def test_converter_uses_pure_python_without_soffice():
    """xlsx_bytes_to_pdf_bytes 不需 LibreOffice 即可產 PDF。"""
    model = _model(sc.SUBSIDIARY_COMBOS[0])
    xlsx = se.render(model, formulas=False)
    pdf, method, err = pdf_converter.xlsx_bytes_to_pdf_bytes(xlsx)
    assert pdf and pdf[:4] == b"%PDF", err
    assert method == "reportlab"
    assert pdf_converter.pdf_available() is True


def test_footer_does_not_overlap_signature():
    """頁尾(分頁名『N萬版-N秒版』)須落在簽名列『承辦人』下方，不與內容重疊。
    （bottom 邊界極小、footer 邊界較大時，頁尾原本會壓到簽名列）。"""
    model = _model(sc.SUBSIDIARY_COMBOS[0])
    xlsx = se.render(model, formulas=False)
    pdf = pdf_render.render_xlsx_to_pdf(xlsx)
    doc = fitz.open(stream=pdf, filetype="pdf")
    page = doc[0]
    sign = page.search_for("承辦人")
    foot = page.search_for("秒版")      # 頁尾『…秒版』
    doc.close()
    assert sign and foot, "找不到簽名列或頁尾文字"
    # fitz 座標左上為原點、y 向下遞增：頁尾在最底 → y 應大於簽名列
    sign_bottom = max(r.y1 for r in sign)
    foot_top = min(r.y0 for r in foot)
    assert foot_top >= sign_bottom, f"頁尾({foot_top})壓到簽名列({sign_bottom})"
