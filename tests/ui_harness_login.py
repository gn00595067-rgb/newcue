# -*- coding: utf-8 -*-
"""AppTest 用：登入側欄（假密碼表、假 Ragic 使用者清單）。"""
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app_passwords as ap  # noqa: E402
import ragic_ui  # noqa: E402
from test_app_passwords import FakeSheet  # noqa: E402

if "_sheet" not in st.session_state:
    st.session_state["_sheet"] = FakeSheet()
ragic_ui._pw_store = lambda: ap.PasswordStore("sid", st.session_state["_sheet"])
ragic_ui._ragic_users = lambda: [{"電子郵件信箱": "cristy@dwm.com.tw", "員工工號": "D11001",
                                  "使用者姓名": "蔡宜歆", "群組": ["User"], "狀態": "NORMAL"}]
ragic_ui.render_login_sidebar()
