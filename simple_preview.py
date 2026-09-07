# -*- coding: utf-8 -*-
"""
簡易模式 v2 預覽（§4）：Excel(值版) → LibreOffice PDF → PyMuPDF 每頁 PNG。

業務看到的就是客戶會拿到的 PDF 版面。沒有 LibreOffice(soffice) 時回傳 None，
由 UI 退回 simple_html 預覽。
"""
import streamlit as st

from pdf_converter import find_soffice_path, xlsx_bytes_to_pdf_bytes


def has_soffice():
    return bool(find_soffice_path())


@st.cache_data(ttl=600, show_spinner=False)
def xlsx_to_page_pngs(xlsx_val_bytes):
    """值版 xlsx → PDF → 每頁 PNG bytes（約 150dpi）。失敗回 None。"""
    try:
        import fitz  # PyMuPDF
    except Exception:
        return None
    pdf, _tag, _msg = xlsx_bytes_to_pdf_bytes(xlsx_val_bytes)
    if not pdf:
        return None
    try:
        doc = fitz.open(stream=pdf, filetype="pdf")
        mat = fitz.Matrix(1.6, 1.6)
        pngs = [page.get_pixmap(matrix=mat).tobytes("png") for page in doc]
        doc.close()
        return pngs
    except Exception:
        return None
