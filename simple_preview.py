# -*- coding: utf-8 -*-
"""
簡易模式 v2 預覽（§4）：Excel(值版) → 純 Python PDF → PyMuPDF 每頁 PNG。

業務看到的就是客戶會拿到的 PDF 版面。PDF 以純 Python 渲染（不需 LibreOffice），
故一律可用；PyMuPDF 缺失時回傳 None，由 UI 退回 simple_html 預覽。
"""
import streamlit as st

from pdf_converter import xlsx_bytes_to_pdf_bytes, pdf_available


def has_soffice():
    # 名稱保留向後相容；PDF 現以純 Python 渲染，一律可用（不需 LibreOffice）。
    return pdf_available()


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
