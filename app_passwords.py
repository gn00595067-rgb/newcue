# -*- coding: utf-8 -*-
"""
同事登入密碼（存在 Google Sheet）。規格：docs/specs/Ragic串接_訂檔流程.md「登入方式變更」。

- 帳號＝公司信箱或 Ragic 員工工號（身分取 Ragic 使用者清單）；密碼存在 Google Sheet。
- Sheet 沒有這個人的列＝還沒改過密碼，預設密碼 123456，登入後必須先改密碼。
- Sheet 只存雜湊（PBKDF2），不存明碼；忘記密碼＝刪掉該列，回到預設 123456。
- 存在 newcue 設定檔 Google Sheet 的「登入密碼」分頁（沒有就自動建立，不動其他分頁），
  A:C＝信箱｜密碼雜湊｜更新時間（第 1 列為表頭）。
- 以服務帳號（Secrets [gcp_service_account]）呼叫 Sheets API；Sheet 要共用給該服務帳號（編輯者）。
不 import streamlit，可獨立測試。
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
from datetime import datetime

DEFAULT_PASSWORD = "123456"
MIN_LEN = 6
_ITER = 200_000
_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_API = "https://sheets.googleapis.com/v4/spreadsheets"
HEADER = ["信箱", "密碼雜湊", "更新時間"]
TAB = "登入密碼"
_RANGE = f"'{TAB}'!A:C"


class PasswordError(RuntimeError):
    """訊息可直接顯示給使用者。"""


def hash_password(pwd: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), salt, _ITER)
    return f"pbkdf2${_ITER}${salt.hex()}${dk.hex()}"


def verify_password(pwd: str, stored: str) -> bool:
    try:
        _algo, it, salt, digest = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", (pwd or "").encode("utf-8"), bytes.fromhex(salt), int(it))
        return hmac.compare_digest(dk.hex(), digest)
    except (ValueError, AttributeError):
        return False


def check_new_password(new: str, again: str) -> None:
    if new != again:
        raise PasswordError("兩次輸入的新密碼不一致")
    if len(new or "") < MIN_LEN:
        raise PasswordError(f"新密碼至少 {MIN_LEN} 個字")
    if new == DEFAULT_PASSWORD:
        raise PasswordError("新密碼不能是預設密碼 123456")


def sheet_id(url_or_id: str) -> str:
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", url_or_id or "")
    return m.group(1) if m else (url_or_id or "").strip()


class PasswordStore:
    """Google Sheet 密碼表。session：有 get/put/post 的 HTTP 物件（正式用 google AuthorizedSession，測試用假的）。"""

    def __init__(self, sid: str, session):
        self.sid = sid
        self.s = session

    @classmethod
    def from_service_account(cls, sheet_url: str, sa_info: dict) -> "PasswordStore":
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2.service_account import Credentials
        creds = Credentials.from_service_account_info(dict(sa_info), scopes=_SCOPES)
        return cls(sheet_id(sheet_url), AuthorizedSession(creds))

    def _add_tab(self) -> None:
        r = self.s.post(f"{_API}/{self.sid}:batchUpdate",
                        json={"requests": [{"addSheet": {"properties": {"title": TAB}}}]}, timeout=30)
        if r.status_code != 200:
            raise PasswordError(f"建立「{TAB}」分頁失敗（HTTP {r.status_code}），請確認 Sheet 已共用給服務帳號（編輯者）")

    def _rows(self) -> list[list[str]]:
        r = self.s.get(f"{_API}/{self.sid}/values/{_RANGE}", timeout=30)
        if r.status_code == 400:   # 分頁還不存在 → 建立後重讀
            self._add_tab()
            r = self.s.get(f"{_API}/{self.sid}/values/{_RANGE}", timeout=30)
        if r.status_code != 200:
            raise PasswordError(f"讀取密碼表失敗（HTTP {r.status_code}），請確認 Sheet 已共用給服務帳號")
        return r.json().get("values", [])

    @staticmethod
    def _find(rows, email) -> int | None:
        """回傳列號（1 起算）；第 1 列是表頭。"""
        for i, row in enumerate(rows):
            if i == 0 and row[:1] == HEADER[:1]:
                continue
            if row and row[0].strip().lower() == email.lower():
                return i + 1
        return None

    def get_hash(self, email: str) -> str:
        rows = self._rows()
        n = self._find(rows, email)
        if n is None:
            return ""
        row = rows[n - 1]
        return row[1].strip() if len(row) > 1 else ""

    def set_password(self, email: str, new: str, now: datetime | None = None) -> None:
        now = now or datetime.now()
        vals = [[email.lower(), hash_password(new), now.strftime("%Y-%m-%d %H:%M")]]
        rows = self._rows()
        n = self._find(rows, email)
        if n is None:
            if not rows:
                vals = [HEADER] + vals
            r = self.s.post(f"{_API}/{self.sid}/values/{_RANGE}:append",
                            params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
                            json={"values": vals}, timeout=30)
        else:
            r = self.s.put(f"{_API}/{self.sid}/values/'{TAB}'!A{n}:C{n}", params={"valueInputOption": "RAW"},
                           json={"values": vals}, timeout=30)
        if r.status_code != 200:
            raise PasswordError(f"寫入密碼表失敗（HTTP {r.status_code}）")

    def check(self, email: str, pwd: str) -> tuple[bool, bool]:
        """→ (密碼正確, 還在用預設密碼需先改)。"""
        stored = self.get_hash(email)
        if not stored:
            return hmac.compare_digest(pwd or "", DEFAULT_PASSWORD), True
        return verify_password(pwd, stored), False
