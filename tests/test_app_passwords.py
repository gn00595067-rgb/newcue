# -*- coding: utf-8 -*-
"""同事登入密碼（Google Sheet）：預設 123456、改密碼、只存雜湊。以假的 Sheets API 測，不連線。"""
import pytest

import app_passwords as ap


class _Resp:
    def __init__(self, code=200, data=None):
        self.status_code, self._d = code, data or {}

    def json(self):
        return self._d


class FakeSheet:
    """模擬 Sheets API values get／put／append。"""

    def __init__(self, rows=None, has_tab=True):
        self.rows = rows if rows is not None else []
        self.has_tab = has_tab

    def get(self, url, timeout=None):
        assert "'登入密碼'!A:C" in url                       # 只讀獨立分頁，不碰其他分頁
        if not self.has_tab:
            return _Resp(400)
        return _Resp(data={"values": [list(r) for r in self.rows]} if self.rows else {})

    def put(self, url, params=None, json=None, timeout=None):
        n = int(url.rsplit("!A", 1)[1].split(":")[0])
        self.rows[n - 1] = json["values"][0]
        return _Resp()

    def post(self, url, params=None, json=None, timeout=None):
        if url.endswith(":batchUpdate"):
            assert json["requests"][0]["addSheet"]["properties"]["title"] == "登入密碼"
            self.has_tab = True
            return _Resp()
        self.rows.extend(json["values"])
        return _Resp()


def test_default_password_then_change():
    sheet = FakeSheet()
    store = ap.PasswordStore("sid", sheet)
    assert store.check("a@x.com", "123456") == (True, True)          # 沒列 → 預設密碼、需先改
    assert store.check("a@x.com", "654321") == (False, True)
    store.set_password("A@x.com", "newpass1")
    assert sheet.rows[0] == ap.HEADER and sheet.rows[1][0] == "a@x.com"
    assert "newpass1" not in sheet.rows[1][1]                         # 只存雜湊
    assert store.check("a@x.com", "newpass1") == (True, False)
    assert store.check("a@x.com", "123456") == (False, False)         # 改過後預設密碼失效
    store.set_password("a@x.com", "another2")                         # 再改：更新同一列
    assert len(sheet.rows) == 2 and store.check("a@x.com", "another2")[0]


def test_reset_by_deleting_row():
    sheet = FakeSheet()
    store = ap.PasswordStore("sid", sheet)
    store.set_password("a@x.com", "newpass1")
    del sheet.rows[1]
    assert store.check("a@x.com", "123456") == (True, True)


@pytest.mark.parametrize("new,again,msg", [("abcdef", "abcdeg", "不一致"), ("abc", "abc", "至少"),
                                           ("123456", "123456", "預設")])
def test_new_password_rules(new, again, msg):
    with pytest.raises(ap.PasswordError, match=msg):
        ap.check_new_password(new, again)


def test_sheet_error_message():
    class Denied(FakeSheet):
        def get(self, url, timeout=None):
            return _Resp(403)
    with pytest.raises(ap.PasswordError, match="共用給服務帳號"):
        ap.PasswordStore("sid", Denied()).check("a@x.com", "123456")


def test_sheet_id():
    assert ap.sheet_id("https://docs.google.com/spreadsheets/d/1AbC_d-9/edit#gid=0") == "1AbC_d-9"
    assert ap.sheet_id("1AbC_d-9") == "1AbC_d-9"


def test_creates_tab_when_missing():
    sheet = FakeSheet(has_tab=False)
    store = ap.PasswordStore("sid", sheet)
    assert store.check("a@x.com", "123456") == (True, True)
    assert sheet.has_tab
