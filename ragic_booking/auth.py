"""Ragic 帳號登入驗證（官方 AUTH API）。

GET {SERVER}/AUTH?u=<email>&p=<password>&login_type=sessionId&json=1&api
成功回 JSON：{"sid": ..., "email": ..., "accounts": {"account": "soundwow", "username": "...",
              "groups": ["EVERYONE", ...]}}（多帳戶時 accounts 可能是 list）；失敗回 -1 或非 JSON。

本模組只驗證身分、取姓名與群組；不保存密碼、寫入 Ragic 仍用共用 API 金鑰。

2026-10-14：Ragic 擋 Streamlit Cloud 發出的 AUTH 登入（同帳密本機成功、Cloud 回 -1）→ 同事改用
app 密碼（app_passwords.py，存 Google Sheet），身分用 API 金鑰讀 Ragic 使用者清單（ragic-setup/1）
取姓名、群組；Ragic 上停用（SUSPENDED）的帳號不能登入。
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
    # 與瀏覽器網址列完全相同的寫法（api 不帶 =、瀏覽器 UA）；GET 失敗再試 POST。
    # 2026-10-14：同事同一組帳密在公司瀏覽器打 AUTH 成功，app（Streamlit Cloud）卻回 -1。
    from urllib.parse import quote
    url = (f"{server}/AUTH?login_type=sessionId&json=1&api"
           f"&u={quote(email, safe='')}&p={quote(password, safe='')}")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
    raw = None
    for attempt in ("get", "post"):
        try:
            if attempt == "get":
                resp = requests.get(url, headers=headers, timeout=_TIMEOUT)
            else:
                resp = requests.post(f"{server}/AUTH?api", headers=headers, timeout=_TIMEOUT, data={
                    "u": email, "p": password, "login_type": "sessionId", "json": "1"})
        except requests.RequestException as e:
            raise RagicAuthError(f"連線 Ragic 失敗：{e}") from e
        if resp.status_code != 200:
            raise RagicAuthError(f"Ragic 回應異常（HTTP {resp.status_code}）")
        try:
            raw = resp.json()
        except ValueError:
            raw = resp.text.strip() or None   # 帳密錯誤時 Ragic 回 -1／純文字（保留原文供判斷）
        if isinstance(raw, dict) and raw.get("sid"):
            break
    return parse_auth_response(raw, account)


# =============================================================================
# Ragic 使用者清單（app 密碼登入用）
# =============================================================================
USER_FORM = "ragic-setup/1"   # Ragic 使用者清單（API 金鑰可讀）


def fetch_ragic_users(api_key: str, server: str = SERVER, account: str = ACCOUNT) -> list[dict]:
    """用 API 金鑰讀 Ragic 使用者清單。"""
    resp = requests.get(f"{server}/{account}/{USER_FORM}?api&v=3&limit=2000",
                        headers={"Authorization": f"Basic {api_key}"}, timeout=_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    return list(data.values()) if isinstance(data, dict) else []


def user_from_list(account_id: str, users: list[dict]) -> RagicUser:
    """在使用者清單找公司信箱或員工工號 → RagicUser；找不到或已停用 → RagicAuthError。"""
    key = (account_id or "").strip().lower()
    rec = next((u for u in users if key and key in (str(u.get("電子郵件信箱", "")).strip().lower(),
                                                    str(u.get("員工工號", "")).strip().lower())), None)
    if rec is None:
        raise RagicAuthError("找不到這個信箱／員工工號（需為公司 Ragic 使用者）")
    if str(rec.get("狀態", "")).upper() == "SUSPENDED":
        raise RagicAuthError("此 Ragic 帳號已停用，無法登入")
    groups = rec.get("群組") or []
    groups = [groups] if isinstance(groups, str) else groups
    email = str(rec.get("電子郵件信箱", "")).strip().lower()
    name = str(rec.get("使用者姓名") or "").strip() or email
    return RagicUser(email=email, name=name, groups=[str(g).strip() for g in groups if str(g).strip()])
