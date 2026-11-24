# -*- coding: utf-8 -*-
"""業務下拉預設＝登入者本人（10/14 實測：簡易模式業務留「—」→ 存檔表業務人員空白）。"""
import ragic_ui


def test_match_sales_exact_and_with_english_name():
    opts = ["洪佳琪", "楊心瑀", "蔡宜歆"]
    assert ragic_ui.match_sales("蔡宜歆", opts) == "蔡宜歆"
    assert ragic_ui.match_sales("楊心瑀 Alison", opts) == "楊心瑀"
    assert ragic_ui.match_sales("開發者", opts) is None
    assert ragic_ui.match_sales("", opts) is None


def test_parse_roc_date():
    from datetime import date
    import simple_cue
    assert simple_cue.parse_roc_date("115.11.30") == date(2026, 11, 30)
    assert simple_cue.parse_roc_date("2026-11-30") == date(2026, 11, 30)
    assert simple_cue.parse_roc_date("115.XX.XX") is None      # 佔位＝未填，存檔擋下
    assert simple_cue.parse_roc_date("115.13.01") is None


def test_simple_model_uses_given_sign_and_billing():
    """簡易模式收合區填的回簽截止日／請款月份要出現在 CUE 備註（與寫入 Ragic 的一致）。"""
    from datetime import date
    import simple_model as sm
    m = sm.build_model("sub_qp_fv", 250000, date(2026, 11, 2), date(2026, 11, 15), data=sm.fallback_sheetdata(),
                       sign_deadline=date(2026, 10, 20), billing_month="115年12月", payment_date="116.01.31")
    text = "\n".join(t for t, _ in m.remarks)
    assert m.sign_deadline == date(2026, 10, 20) and m.billing_month == "115年12月"
    assert "116.01.31" in text
