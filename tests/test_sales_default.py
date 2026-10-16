# -*- coding: utf-8 -*-
"""業務下拉預設＝登入者本人（10/14 實測：簡易模式業務留「—」→ 存檔表業務人員空白）。"""
import ragic_ui


def test_match_sales_exact_and_with_english_name():
    opts = ["洪佳琪", "楊心瑀", "蔡宜歆"]
    assert ragic_ui.match_sales("蔡宜歆", opts) == "蔡宜歆"
    assert ragic_ui.match_sales("楊心瑀 Alison", opts) == "楊心瑀"
    assert ragic_ui.match_sales("開發者", opts) is None
    assert ragic_ui.match_sales("", opts) is None
