# -*- coding: utf-8 -*-
"""登入畫面：預設密碼 123456 登入後必須先改密碼，改完才算登入；之後用新密碼、員工工號登入。"""
import os

import pytest

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

HARNESS = os.path.join(os.path.dirname(__file__), "ui_harness_login.py")


@pytest.fixture(autouse=True)
def _restore_ragic_ui():
    """harness 會換掉 ragic_ui 的密碼表／使用者清單（同一個 Python 行程），測完還原，免得影響其他測試。"""
    import ragic_ui
    saved = (ragic_ui._pw_store, ragic_ui._ragic_users)
    yield
    ragic_ui._pw_store, ragic_ui._ragic_users = saved


def _login(at, acc, pwd):
    at.text_input(key="ragic_login_email").input(acc)
    at.text_input(key="ragic_login_pwd").input(pwd)
    at.button[0].click().run()


def test_first_login_must_change_password():
    at = AppTest.from_file(HARNESS).run()
    _login(at, "cristy@dwm.com.tw", "wrong")
    assert any("帳號或密碼錯誤" in e.value for e in at.error) and "ragic_user" not in at.session_state
    _login(at, "cristy@dwm.com.tw", "123456")
    assert "ragic_user" not in at.session_state and at.session_state["ragic_pending_user"]["name"] == "蔡宜歆"
    assert any("第一次登入" in w.value for w in at.warning)
    at.text_input[0].input("mypass99")      # 新密碼
    at.text_input[1].input("mypass99")      # 再輸入一次
    at.button[0].click().run()
    assert at.session_state["ragic_user"]["email"] == "cristy@dwm.com.tw"
    # 下次（新的瀏覽器工作階段）用員工工號＋新密碼登入，不必再改
    sheet = at.session_state["_sheet"]
    at2 = AppTest.from_file(HARNESS)
    at2.session_state["_sheet"] = sheet
    at2.run()
    _login(at2, "D11001", "mypass99")
    assert at2.session_state["ragic_user"]["name"] == "蔡宜歆" and "ragic_pending_user" not in at2.session_state
    at2.button(key="ragic_logout").click().run()
    assert "ragic_user" not in at2.session_state
