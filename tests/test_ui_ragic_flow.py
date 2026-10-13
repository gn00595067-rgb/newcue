# -*- coding: utf-8 -*-
"""Ragic 存檔流程的畫面測試（AppTest；假 Ragic，不連線寫入）。
需要讀 Google 試算表設定檔（與正式 app 相同）；讀不到時略過。"""
import io
import os
from datetime import date

import pytest
from openpyxl import load_workbook

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

HARNESS = os.path.join(os.path.dirname(__file__), "ui_harness_ragic.py")
USER = {"email": "a@x.com", "name": "王小明", "groups": []}
COMBOS = [{"media": "全家廣播", "region": "全省", "seconds": 15}, {"media": "家樂福", "region": "全省", "seconds": 20}]


def _app(mode, **state):
    at = AppTest.from_file(HARNESS, default_timeout=600)
    at.session_state["ragic_user"] = USER
    at.session_state["cue_mode"] = mode
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    if any("設定檔載入失敗" in e.value for e in at.error):
        pytest.skip("讀不到 Google 試算表設定檔")
    return at


def _ok(at):
    assert not at.exception, at.exception[0].value
    assert not [e.value for e in at.error], [e.value for e in at.error]


def _rec(at):
    return at.session_state["cue_record"]


def test_simple_save_update_dirty_reopen():
    at = _app("簡易模式")
    at.text_input(key="simple_client").input("客戶A").run()
    at.button(key="simple_save_btn").click().run()
    _ok(at)
    assert _rec(at)["snap"]["version"] == 1
    assert not any("尚未存檔" in w.value for w in at.warning)
    at.session_state["simple_budget2"] = 300000
    at.run()
    assert any("尚未存檔" in w.value for w in at.warning)                  # 改了沒存要提醒
    at.button(key="simple_save_btn").click().run()
    _ok(at)
    assert _rec(at)["snap"]["version"] == 2 and list(at.session_state["_fake_db"]) == ["100"]   # 更新同一筆
    assert any("預算" in c for c in _rec(at)["snap"]["history"][-1]["changes"])
    # 換模式、弄亂欄位後從「我的 CUE」開啟
    at.session_state["cue_mode"] = "一般CUE"
    at.session_state["simple_client"] = "zzz"
    at.run()
    at.button(key="mycue_open").click().run()
    _ok(at)
    assert at.session_state["cue_mode"] == "簡易模式"
    assert at.text_input(key="simple_client").value == "客戶A" and at.session_state["simple_budget2"] == 300000
    assert not any("尚未存檔" in w.value for w in at.warning)              # 剛開啟＝與存檔一致


def test_fixed_project_save():
    at = _app("專案CUE")
    at.button(key="fp_save_btn").click().run()
    _ok(at)
    assert _rec(at)["snap"]["waves"][0]["rows"][0]["platform"] == "家樂福"


def test_annual_save_merges_wave_files_and_restores():
    waves = [{"start": date(2027, 1, 4), "end": date(2027, 1, 31), "combo_spots": [800, 300], "combo_net": [100000, 90000]},
             {"start": date(2027, 3, 1), "end": date(2027, 3, 31), "combo_spots": [800, 0], "combo_net": [100000, 0]}]
    at = _app("年約季約細CUE", aq_combos=COMBOS, aq_waves=waves)
    at.text_input(key="aq_client").input("年約客戶").run()
    at.button(key="aq_save_btn").click().run()
    _ok(at)
    snap = _rec(at)["snap"]
    assert len(snap["waves"]) == 2 and sum(r["net"] for w in snap["waves"] for r in w["rows"]) == 290000
    xl = at.session_state["_fake_last_files"]["1015320"][1]
    assert load_workbook(io.BytesIO(xl)).sheetnames == ["波段1", "波段2"]   # 各波合成一檔
    at.session_state["cue_mode"] = "簡易模式"
    at.session_state["aq_waves"] = []
    at.run()
    at.button(key="mycue_open").click().run()
    _ok(at)
    assert at.text_input(key="aq_client").value == "年約客戶"
    assert at.number_input(key="aq_tbl_net_0_1").value == 90000


def test_annual_agency_wave_settings_persist():
    waves = [{"start": date(2027, 1, 4), "end": date(2027, 1, 31), "combo_spots": [800, 300], "combo_net": [100000, 90000]}]
    at = _app("年約季約細CUE", aq_combos=COMBOS, aq_waves=waves, agency_unlocked=True)
    at.radio(key="aq_format").set_value("凱絡").run()
    rem = next(t for t in at.text_area if t.key.startswith("aq_ag_rem_0_"))
    rem.input("自訂備註一行").run()
    at.text_input(key="aq_ag_pay_0").input("自訂請款").run()
    at.button(key="aq_save_btn").click().run()
    _ok(at)
    assert _rec(at)["snap"]["header"]["format"] == "凱絡"
    at.session_state["cue_mode"] = "簡易模式"
    at.session_state["aq_waves"] = []
    at.run()
    at.button(key="mycue_open").click().run()
    _ok(at)
    rem = next(t for t in at.text_area if t.key.startswith("aq_ag_rem_0_"))
    assert rem.value == "自訂備註一行" and at.text_input(key="aq_ag_pay_0").value == "自訂請款"


def test_general_cue_save_and_reopen():
    at = _app("一般CUE")
    at.button(key="gen_save_btn").click().run()
    _ok(at)
    snap = _rec(at)["snap"]
    assert sum(r["net"] for r in snap["waves"][0]["rows"]) == int(snap["header"]["final"])
    at.button(key="mycue_open").click().run()
    _ok(at)
    assert at.session_state["cue_mode"] == "一般CUE"


@pytest.mark.parametrize("sub,btn,mode", [("自訂代理商CUE", "ag_save_btn", "代理商CUE"),
                                          ("一鍵CUE（模板）", "agsimple_save_btn", "代理商一鍵")])
def test_agency_save(sub, btn, mode):
    at = _app("代理商CUE", agency_unlocked=True, agency_sub_mode=sub)
    at.button(key=btn).click().run()
    _ok(at)
    assert _rec(at)["snap"]["mode"] == mode


def test_not_logged_in_no_save_button():
    at = AppTest.from_file(HARNESS, default_timeout=600)
    at.session_state["cue_mode"] = "簡易模式"
    at.run()
    assert not any(b.key == "simple_save_btn" for b in at.button)
