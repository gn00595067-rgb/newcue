# -*- coding: utf-8 -*-
"""Ragic 帳號登入解析（不打真 API）。"""
import pytest

from ragic_booking import auth


def test_single_account():
    raw = {"sid": "s1", "email": "a@x.com",
           "accounts": {"account": "soundwow", "username": "王小明", "groups": ["EVERYONE", "營運主管"]}}
    u = auth.parse_auth_response(raw)
    assert (u.email, u.name) == ("a@x.com", "王小明")
    assert u.in_any(["營運主管"]) and not u.in_any(["SYSADMIN"])


def test_multi_accounts_picks_company():
    raw = {"sid": "s1", "email": "a@x.com",
           "accounts": [{"account": "other", "username": "X", "groups": []},
                        {"account": "SoundWow", "username": "王小明", "groups": ["EVERYONE"]}]}
    assert auth.parse_auth_response(raw).name == "王小明"


@pytest.mark.parametrize("raw", [-1, None, "-1", {}, {"sid": ""}])
def test_bad_credentials(raw):
    with pytest.raises(auth.RagicAuthError, match="帳號或密碼錯誤"):
        auth.parse_auth_response(raw)


def test_other_company():
    raw = {"sid": "s1", "email": "a@x.com", "accounts": {"account": "demo", "username": "X"}}
    with pytest.raises(auth.RagicAuthError, match="不屬於公司"):
        auth.parse_auth_response(raw)


def test_empty_input_no_network(monkeypatch):
    monkeypatch.setattr(auth.requests, "get", lambda *a, **k: pytest.fail("不應連線"))
    with pytest.raises(auth.RagicAuthError):
        auth.ragic_login("", "")


def test_name_falls_back_to_email():
    raw = {"sid": "s", "email": "a@x.com", "accounts": {"account": "soundwow", "username": ""}}
    assert auth.parse_auth_response(raw).name == "a@x.com"


def test_customer_form_tuples_multi_values():
    from ragic_booking import fields as rf
    d = rf.CustomerDraft(客戶名稱="甲", 客服=["A", "B"], 付款方式=["匯款"])
    t = rf.customer_form_tuples(d)
    assert (rf.CustomerWriteF.客服, "A") in t and (rf.CustomerWriteF.客服, "B") in t
    assert (rf.CustomerWriteF.付款方式, "匯款") in t
    assert not any("#" in k for k, _ in t)


def test_error_shows_ragic_reply_for_diagnosis():
    with pytest.raises(auth.RagicAuthError, match="Ragic 回應：.*two-factor"):
        auth.parse_auth_response({"status": "ERROR", "msg": "two-factor required"})
    with pytest.raises(auth.RagicAuthError) as e:
        auth.parse_auth_response(-1)
    assert str(e.value) == "帳號或密碼錯誤"


USERS = [{"電子郵件信箱": "Cristy@dwm.com.tw", "使用者姓名": "蔡宜歆Cristy", "群組": ["User", "Sales"], "狀態": "NORMAL"},
         {"電子郵件信箱": "old@dwm.com.tw", "使用者姓名": "離職", "群組": "User", "狀態": "SUSPENDED"}]


def test_parse_app_passwords():
    m = auth.parse_app_passwords("Cristy@dwm.com.tw = a1b2，old@dwm.com.tw=x=y\nbad, =nopw")
    assert m == {"cristy@dwm.com.tw": "a1b2", "old@dwm.com.tw": "x=y"}


def test_app_login_uses_ragic_user_list():
    pw = auth.parse_app_passwords("cristy@dwm.com.tw=a1b2, old@dwm.com.tw=zz")
    u = auth.app_login(" cristy@dwm.com.tw ", "a1b2", pw, lambda: USERS)
    assert (u.name, u.groups) == ("蔡宜歆Cristy", ["User", "Sales"])
    with pytest.raises(auth.RagicAuthError, match="帳號或密碼錯誤"):
        auth.app_login("cristy@dwm.com.tw", "wrong", pw, lambda: USERS)
    with pytest.raises(auth.RagicAuthError, match="已停用"):
        auth.app_login("old@dwm.com.tw", "zz", pw, lambda: USERS)
    with pytest.raises(auth.RagicAuthError, match="不在公司 Ragic"):
        auth.app_login("cristy@dwm.com.tw", "a1b2", pw, lambda: USERS[1:])
