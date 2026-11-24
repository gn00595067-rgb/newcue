# -*- coding: utf-8 -*-
"""開發者登入：只在設了 DEV_LOGIN_PASSWORD 時可用，且可列入審核者名單。"""
import ragic_ui


def test_disabled_without_secret(monkeypatch):
    monkeypatch.delenv("DEV_LOGIN_PASSWORD", raising=False)
    assert ragic_ui.dev_login_user("") is None
    assert ragic_ui.dev_login_user("任何密碼") is None


def test_password_check_and_identity(monkeypatch):
    monkeypatch.setenv("DEV_LOGIN_PASSWORD", "pw")
    monkeypatch.setenv("DEV_LOGIN_NAME", "Jonathan")
    monkeypatch.setenv("DEV_LOGIN_EMAIL", "jonathan@dev")
    assert ragic_ui.dev_login_user("wrong") is None
    u = ragic_ui.dev_login_user("pw")
    assert u == {"email": "jonathan@dev", "name": "Jonathan", "groups": ["開發者"]}


def test_dev_user_can_be_reviewer(monkeypatch):
    monkeypatch.setenv("DEV_LOGIN_PASSWORD", "pw")
    monkeypatch.setenv("DEV_LOGIN_EMAIL", "jonathan@dev")
    monkeypatch.setenv("RAGIC_REVIEWERS", "boss@x.com, Jonathan@dev")
    ragic_ui.st.session_state.clear()
    ragic_ui.st.session_state[ragic_ui.SS_USER] = ragic_ui.dev_login_user("pw")
    assert ragic_ui.is_reviewer()
