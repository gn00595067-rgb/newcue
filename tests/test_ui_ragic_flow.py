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


# ---------------------------------------------------------------- 第 3 期：檔次調整（加贈）
def _enable_bonus(at, prefix, spots=3):
    at.run()   # AppTest：存檔觸發 st.rerun 後的下一次操作可能沒送進去，先補跑一次（瀏覽器操作無此問題）
    cb = next(c for c in at.checkbox if str(c.key).startswith(f"{prefix}cb_en_"))
    skey = cb.key[len(f"{prefix}cb_en_"):]
    cb.check()
    at.number_input(key=f"{prefix}cb_spots_{skey}").set_value(spots)
    at.run()
    return skey


def _xlsx_text(at):
    wb = load_workbook(io.BytesIO(at.session_state["_fake_last_files"]["1015320"][1]))
    return " ".join(str(c.value) for ws in wb.worksheets for r in ws.iter_rows() for c in r if c.value is not None)


def _totals(snap):
    rows = [r for w in snap["waves"] for r in w["rows"]]
    return sum(r["spots"] for r in rows), sum(r["net"] for r in rows), [r["kind"] for r in rows]


@pytest.mark.parametrize("mode,prefix,btn,state", [
    ("專案CUE", "fp_", "fp_save_btn", {}),
    ("簡易模式", "simple_", "simple_save_btn", {}),
    ("一般CUE", "", "gen_save_btn", {}),
    ("年約季約細CUE", "aq_", "aq_save_btn",
     {"aq_combos": COMBOS, "aq_waves": [{"start": date(2027, 1, 4), "end": date(2027, 1, 31),
                                         "combo_spots": [800, 300], "combo_net": [100000, 90000]}]}),
])
def test_bonus_adds_spots_keeps_net(mode, prefix, btn, state):
    at = _app(mode, **state)
    at.button(key=btn).click().run()
    _ok(at)
    s1, n1, _ = _totals(_rec(at)["snap"])
    _enable_bonus(at, prefix)
    assert any("尚未存檔" in w.value for w in at.warning)
    at.button(key=btn).click().run()
    _ok(at)
    snap = _rec(at)["snap"]
    s2, n2, kinds = _totals(snap)
    assert s2 > s1 and n2 == n1 and "bonus" in kinds                  # 加贈：檔次增加、實收不變
    assert snap["version"] == 2 and any("檔次" in c for c in snap["history"][-1]["changes"])
    assert "加贈" in _xlsx_text(at)                                    # Excel 重新產出含加贈列
    # 開啟還原後加贈設定仍在
    at.session_state["cue_mode"] = "專案CUE" if mode != "專案CUE" else "簡易模式"
    at.run()
    at.button(key="mycue_open").click().run()
    _ok(at)
    assert any(str(c.key).startswith(f"{prefix}cb_en_") and c.value for c in at.checkbox)
    assert not any("尚未存檔" in w.value for w in at.warning)


@pytest.mark.parametrize("fmt", ["2008傳媒", "凱絡"])
def test_bonus_agency_annual(fmt):
    waves = [{"start": date(2027, 1, 4), "end": date(2027, 1, 31), "combo_spots": [800, 300], "combo_net": [100000, 90000]}]
    at = _app("年約季約細CUE", aq_combos=COMBOS, aq_waves=waves, agency_unlocked=True)
    at.radio(key="aq_format").set_value(fmt).run()
    at.button(key="aq_save_btn").click().run()
    s1, n1, _ = _totals(_rec(at)["snap"])
    _enable_bonus(at, "aqag_", spots=4)
    at.button(key="aq_save_btn").click().run()
    _ok(at)
    s2, n2, _ = _totals(_rec(at)["snap"])
    assert s2 > s1 and n2 == n1


def test_bonus_agency_custom():
    at = _app("代理商CUE", agency_unlocked=True, agency_sub_mode="自訂代理商CUE")
    at.button(key="ag_save_btn").click().run()
    s1, n1, _ = _totals(_rec(at)["snap"])
    _enable_bonus(at, "ag_", spots=5)
    at.button(key="ag_save_btn").click().run()
    _ok(at)
    s2, n2, _ = _totals(_rec(at)["snap"])
    assert s2 == s1 + 5 * 28 and n2 == n1          # 預設走期 8/5～9/1 共 28 天，每日 +5


# ---------------------------------------------------------------- 第 4 期：送審 → 主管審核 → 訂檔
CUSTOMER = {"rid": "9", "編號": "C01399", "名稱": "客戶甲股份有限公司", "統編": "12345678", "產品": "產品乙",
            "類別": "直客", "業務": "王小明", "主管": "李主管", "客服": ["陳客服"], "付款條件": "月結30天",
            "現折": "5", "退佣": "0"}


def _settle(at, prefix):
    """AppTest：審核按鈕觸發 st.rerun 後，舊畫面的「退回原因」欄已不存在，先補值再重跑（瀏覽器無此問題）。"""
    key = f"{prefix}_rv_reason"
    at.session_state[key] = at.session_state[key] if key in at.session_state else ""
    at.run()


def _submit(at, prefix):
    at.run()
    at.date_input(key=f"{prefix}_od_pay").set_value(date(2027, 2, 28)).run()
    btn = at.button(key=f"{prefix}_submit")
    assert not btn.disabled, btn.help
    btn.click().run()
    at.run()   # AppTest：st.rerun 後補跑一次，避免沿用舊元件
    _ok(at)


def test_submit_review_approve_then_adjust_updates_booking():
    at = _app("簡易模式", ragic_customer=CUSTOMER, simple_client="客戶甲", _fake_sign=True)
    _submit(at, "simple_save")
    snap = _rec(at)["snap"]
    assert snap["status"] == "待審" and snap["review"]["signback"] == "回簽.pdf"
    assert at.session_state["_fake_files"][_rec(at)["rid"]]["1015884"][0] == "回簽.pdf"   # 回簽檔附到 cue/2
    # 一般業務看不到審核區
    assert not any(b.key == "simple_save_rv_ok" for b in at.button)
    # 主管：從待審清單開啟 → 核准
    at.session_state["is_supervisor"] = True
    at.session_state["cue_mode"] = "一般CUE"
    at.run()
    at.button(key="review_open").click().run()
    _ok(at)
    at.button(key="simple_save_rv_ok").click().run()
    _settle(at, "simple_save")
    _ok(at)
    snap = _rec(at)["snap"]
    assert snap["status"] == "已訂檔" and snap["booking"]["cue_id"] == "1160101"
    call = at.session_state["_fake_booking_calls"][-1]
    assert call[0] == "submit" and len(call[2]) == 2                      # 訂檔CUE表＋客戶回簽檔
    # 業務調整（加贈）→ 已訂檔－有異動未送審 → 送審 → 核准＝更新原訂檔
    at.session_state["is_supervisor"] = False
    _enable_bonus(at, "simple_")
    at.button(key="simple_save_btn").click().run()
    at.run()
    assert _rec(at)["snap"]["status"] == "已訂檔－有異動未送審"
    at.session_state["_fake_sign"] = False                                # 沿用上次回簽檔
    _submit(at, "simple_save")
    assert _rec(at)["snap"]["status"] == "異動待審"
    at.session_state["is_supervisor"] = True
    at.run()
    at.button(key="simple_save_rv_ok").click().run()
    _settle(at, "simple_save")
    _ok(at)
    assert at.session_state["_fake_booking_calls"][-1] == ("update", "1160101", ["500"])
    assert _rec(at)["snap"]["status"] == "已訂檔"


def test_reject_with_reason():
    at = _app("專案CUE", ragic_customer=CUSTOMER, fp_client="客戶甲", _fake_sign=True)
    _submit(at, "fp_save")
    at.session_state["is_supervisor"] = True
    at.run()
    assert at.button(key="fp_save_rv_no").disabled                       # 沒填原因不能退回
    at.text_input(key="fp_save_rv_reason").input("收款日期不對").run()
    at.button(key="fp_save_rv_no").click().run()
    _settle(at, "fp_save")
    assert not at.exception
    snap = _rec(at)["snap"]
    assert snap["status"] == "退回" and snap["review"]["reason"] == "收款日期不對"
    assert any("退回原因" in e.value for e in at.error)                  # 業務看得到退回原因


def test_submit_blocked_without_customer_or_signback():
    at = _app("簡易模式", simple_client="客戶甲")
    at.run()
    btn = at.button(key="simple_save_submit")
    assert btn.disabled and "客戶回簽檔" in btn.help and "客戶編號" in btn.help


def test_approve_disabled_when_booking_off():
    at = _app("簡易模式", ragic_customer=CUSTOMER, simple_client="客戶甲", _fake_sign=True, _fake_booking_on=False)
    _submit(at, "simple_save")
    at.session_state["is_supervisor"] = True
    at.run()
    assert at.button(key="simple_save_rv_ok").disabled
    assert any("RAGIC_BOOKING_ENABLED" in i.value for i in at.info)
