"""Ragic 帳號登入驗證（官方 AUTH API）。

GET {SERVER}/AUTH?u=<email>&p=<password>&login_type=sessionId&json=1&api
成功回 JSON：{"sid": ..., "email": ..., "accounts": {"account": "soundwow", "username": "...",
              "groups": ["EVERYONE", ...]}}（多帳戶時 accounts 可能是 list）；失敗回 -1 或非 JSON。

本模組只驗證身分、取姓名與群組；不保存密碼、寫入 Ragic 仍用共用 API 金鑰。
不 import streamlit，可獨立測試。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import requests

from ragic_booking.fields import ACCOUNT, SERVER

_TIMEOUT = 30


class RagicAuthError(RuntimeError):
    """登入失敗（帳密錯、非本公司帳戶、連線問題）。訊息可直接顯示給使用者。"""


@dataclass
class RagicUser:
    email: str
    name: str
    groups: list[str] = field(default_factory=list)

    def in_any(self, groups) -> bool:
        want = {g.strip() for g in groups if g and g.strip()}
        return bool(want & set(self.groups))


def _pick_account(accounts, account: str) -> dict | None:
    if isinstance(accounts, dict):
        accounts = [accounts]
    if not isinstance(accounts, list):
        return None
    for a in accounts:
        if isinstance(a, dict) and str(a.get("account", "")).lower() == account.lower():
            return a
    return None


def _detail(raw) -> str:
    """Ragic 原始回應摘要（不含密碼），附在錯誤訊息後方便判斷是帳密錯、兩步驟驗證或 Google 登入帳號。"""
    if raw in (None, "", -1, "-1"):
        return ""
    text = " ".join(str(raw).split())
    return f"（Ragic 回應：{text[:120]}）"


def parse_auth_response(raw, account: str = ACCOUNT) -> RagicUser:
    """AUTH 回傳 → RagicUser；不是本公司帳戶或帳密錯 → RagicAuthError。"""
    if not isinstance(raw, dict) or not raw.get("sid"):
        raise RagicAuthError("帳號或密碼錯誤" + _detail(raw))
    acc = _pick_account(raw.get("accounts"), account)
    if acc is None:
        raise RagicAuthError("此帳號不屬於公司 Ragic，無法登入")
    email = str(raw.get("email") or "").strip()
    name = str(acc.get("username") or "").strip() or email
    groups = [str(g).strip() for g in (acc.get("groups") or []) if str(g).strip()]
    return RagicUser(email=email, name=name, groups=groups)


def ragic_login(email: str, password: str, server: str = SERVER, account: str = ACCOUNT) -> RagicUser:
    """以 Ragic Email／密碼驗證；成功回 RagicUser，失敗丟 RagicAuthError。"""
    email = (email or "").strip()
    if not email or not password:
        raise RagicAuthError("請輸入 Email 與密碼")
    try:
        resp = requests.get(f"{server}/AUTH", params={
            "u": email, "p": password, "login_type": "sessionId", "json": "1", "api": "",
        }, timeout=_TIMEOUT)
    except requests.RequestException as e:
        raise RagicAuthError(f"連線 Ragic 失敗：{e}") from e
    if resp.status_code != 200:
        raise RagicAuthError(f"Ragic 回應異常（HTTP {resp.status_code}）")
    try:
        raw = resp.json()
    except ValueError:
        raw = resp.text.strip() or None   # 帳密錯誤時 Ragic 回 -1／純文字（保留原文供判斷）
    return parse_auth_response(raw, account)
