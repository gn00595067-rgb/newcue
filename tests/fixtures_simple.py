# -*- coding: utf-8 -*-
"""簡易模式測試 fixture（§10.0）：離線 SheetData，所有測試不連 Google Sheet。"""
import simple_model as sm


def sheetdata():
    """Google Sheet 值版（家樂福 30 秒係數 1.5）。"""
    return sm.fallback_sheetdata(use_template_factors=False)


def sheetdata_template():
    """0902 範本值版（家樂福 30 秒係數 1.65），供 fidelity 測試。"""
    return sm.fallback_sheetdata(use_template_factors=True)
