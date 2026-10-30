# -*- coding: utf-8 -*-
"""申請 CUE號／送出訂檔權限：限 RAGIC_REVIEWERS 主管信箱與開發者登入（10-30 開放業務測試，業務只能存檔）。"""
import ragic_ui


def can_book():   # AppTest 外殼會把 ragic_ui.can_book 換成假的（同一 Python 行程），這裡用原版
    return ragic_ui.__dict__.get("_orig_can_book", ragic_ui.can_book)()


def _login(u):
    ragic_ui.st.session_state.clear()
    if u:
        ragic_ui.st.session_state[ragic_ui.SS_USER] = u


def test_reviewer_and_dev_can_book(monkeypatch):
    monkeypatch.setenv("RAGIC_REVIEWERS", "boss@x.com，Boss2@X.com")
    _login({"email": "boss@x.com", "name": "主管", "groups": []})
    assert can_book()
    _login({"email": "boss2@x.com", "name": "主管2", "groups": []})
    assert can_book()
    _login({"email": "jonathan@dev", "name": "Jonathan", "groups": ["開發者"]})
    assert can_book()


def test_sales_and_supervisor_password_cannot_book(monkeypatch):
    monkeypatch.setenv("RAGIC_REVIEWERS", "boss@x.com")
    _login({"email": "a@x.com", "name": "業務", "groups": []})
    assert not can_book()
    ragic_ui.st.session_state["is_supervisor"] = True   # 主管密碼不算（業務可能知道密碼）
    assert not can_book()
    _login(None)
    assert not can_book()
