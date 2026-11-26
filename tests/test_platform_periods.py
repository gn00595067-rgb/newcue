# -*- coding: utf-8 -*-
"""各平台不同走期（小花 1124-4：12/1–14 走新鮮視、12/15–28 走萬家福，同一張 CUE）。AppTest＋假 Ragic。"""
import os
from datetime import date

import pytest

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

HARNESS = os.path.join(os.path.dirname(__file__), "ui_harness_ragic.py")


def test_新鮮視前半月_萬家福後半月():
    at = AppTest.from_file(HARNESS, default_timeout=600)
    at.session_state["ragic_user"] = {"email": "a@x.com", "name": "王小明", "groups": []}
    at.session_state["cue_mode"] = "一般CUE"
    at.session_state["一般CUE_gate"] = "先估價，暫不指定"
    at.session_state["temp_budget"] = 250000
    at.session_state["temp_start_date"] = date(2026, 12, 1)
    at.session_state["temp_end_date"] = date(2026, 12, 28)
    at.run()
    if any("設定檔載入失敗" in e.value for e in at.error):
        pytest.skip("讀不到 Google 試算表設定檔")

    def cb(label):
        return next(c for c in at.checkbox if c.label == label)

    cb("全家廣播").uncheck(); at.run()
    cb("新鮮視").check(); at.run()
    cb("萬家福．樂家康").check(); at.run()
    cb("啟用各平台走期").check(); at.run()
    at.date_input(key="plat_period_e_新鮮視").set_value(date(2026, 12, 14)); at.run()
    at.date_input(key="plat_period_s_家樂福").set_value(date(2026, 12, 15)); at.run()
    at.button(key="gen_save_btn").click().run()
    assert not at.exception
    rows = at.session_state["cue_record"]["snap"]["waves"][0]["rows"]
    assert len(rows) >= 3
    for r in rows:
        nz = [i for i, v in enumerate(r["schedule"]) if v]
        if "全省" in str(r.get("region")):        # 萬家福量販／樂家康超市
            assert nz[0] == 14 and nz[-1] == 27
        else:                                       # 新鮮視
            assert nz[0] == 0 and nz[-1] == 13
