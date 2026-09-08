"""
PDF 轉檔模組 (PDF Converter)

主要路徑：純 Python 渲染器 pdf_render（openpyxl + reportlab），不需 LibreOffice，
        可在 Streamlit Cloud（無 apt）運作，並內嵌繁中字型。
後備路徑：若本機裝有 LibreOffice(soffice) 且純 Python 渲染失敗，改用 soffice。
"""

import os
import shutil
import tempfile
import subprocess
import gc
import requests
import streamlit as st
from config import BOLIN_LOGO_URL


def pdf_available():
    """PDF 產出是否可用。純 Python 渲染器一律可用（不需 LibreOffice）。"""
    return True


def find_soffice_path():
    """尋找系統中的 LibreOffice 執行檔路徑 (支援 Linux 與 Windows)。"""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        return soffice
    if os.name == "nt":  # Windows fallback
        candidates = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
    return None


@st.cache_data(show_spinner="正在下載 Logo...", ttl=3600)
def get_cloud_logo_bytes():
    """下載鉑霖 Logo 圖片檔 (快取 1 小時)。"""
    try:
        response = requests.get(BOLIN_LOGO_URL, timeout=10)
        return response.content if response.status_code == 200 else None
    except:
        return None


@st.cache_data(show_spinner="正在生成 PDF...", ttl=3600)
def xlsx_bytes_to_pdf_bytes(xlsx_bytes: bytes, filename: str = ""):
    """
    Excel(值版) bytes -> PDF bytes。
    優先用純 Python 渲染器（不需 LibreOffice）；失敗才退回 soffice。
    filename：頁尾 &F 顯示的檔名。回傳 (pdf_bytes, method, err_msg)。
    """
    # 主要：純 Python 渲染器
    try:
        import pdf_render
        pdf = pdf_render.render_xlsx_to_pdf(xlsx_bytes, filename=filename)
        if pdf:
            return pdf, "reportlab", ""
    except Exception as e:
        py_err = str(e)
    else:
        py_err = "純 Python 渲染回傳空值"

    # 後備：LibreOffice（僅本機可能有）
    pdf, tag, err = _soffice_convert(xlsx_bytes)
    if pdf:
        return pdf, tag, err
    return None, "Fail", f"PDF 產生失敗（reportlab: {py_err}；soffice: {err}）"


def _soffice_convert(xlsx_bytes: bytes):
    soffice = find_soffice_path()
    if not soffice:
        return None, "Fail", "無 LibreOffice"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            xlsx_path = os.path.join(tmp, "cue.xlsx")
            with open(xlsx_path, "wb") as f:
                f.write(xlsx_bytes)
            # 呼叫 LibreOffice 轉檔指令
            subprocess.run(
                [soffice, "--headless", "--nologo", "--convert-to", "pdf:calc_pdf_Export", "--outdir", tmp, xlsx_path],
                capture_output=True,
                timeout=60
            )
            pdf_path = os.path.join(tmp, "cue.pdf")
            if not os.path.exists(pdf_path):
                # 嘗試尋找任何產出的 pdf
                for fn in os.listdir(tmp):
                    if fn.endswith(".pdf"):
                        pdf_path = os.path.join(tmp, fn)
                        break
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    return f.read(), "LibreOffice", ""
            return None, "Fail", "LibreOffice 未產出檔案"
    except Exception as e:
        return None, "Fail", str(e)
    finally:
        gc.collect()
