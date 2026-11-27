# -*- coding: utf-8 -*-
"""Email 通知（主管 2026-11-27 勾選：贈檔申請改 Email 通知主管）。
Secrets（未設 MAIL_USER／MAIL_PASSWORD＝不寄，回傳原因，畫面改提示業務自行通知）：
  MAIL_USER       寄件 Gmail 帳號（建議公司專用信箱）
  MAIL_PASSWORD   該帳號的「應用程式密碼」（Google 帳戶 → 安全性 → 兩步驟驗證 → 應用程式密碼），不是登入密碼
  MAIL_TO         收件人，逗號分隔；未設時用 RAGIC_REVIEWERS
  MAIL_SMTP_HOST／MAIL_SMTP_PORT  預設 smtp.gmail.com／465
  APP_URL         信中附的系統網址（選填）
本模組不 import streamlit 以外的 app 模組；獨立新檔，避免 Streamlit Cloud 舊模組快取造成 ImportError。"""
import smtplib
from email.message import EmailMessage


def _get(secret, name, default=""):
    return str(secret(name, default) or default).strip()


def recipients(secret):
    raw = _get(secret, "MAIL_TO") or _get(secret, "RAGIC_REVIEWERS")
    return [x.strip() for x in raw.replace("，", ",").split(",") if "@" in x]


def send(secret, subject, body, to=None):
    """寄信。回傳 (成功與否, 說明)。secret＝讀設定的函式 (name, default) → 值。"""
    user, pwd = _get(secret, "MAIL_USER"), _get(secret, "MAIL_PASSWORD")
    to = to or recipients(secret)
    if not (user and pwd):
        return False, "尚未設定寄信帳號"
    if not to:
        return False, "沒有收件人（MAIL_TO／RAGIC_REVIEWERS）"
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, user, ", ".join(to)
    msg.set_content(body)
    try:
        host = _get(secret, "MAIL_SMTP_HOST", "smtp.gmail.com")
        port = int(_get(secret, "MAIL_SMTP_PORT", "465") or 465)
        with smtplib.SMTP_SSL(host, port, timeout=15) as s:
            s.login(user, pwd)
            s.send_message(msg)
    except Exception as e:  # noqa: BLE001  寄信失敗不能影響存檔
        return False, f"寄信失敗：{e}"
    return True, "已寄 Email 通知主管（" + "、".join(to) + "）"


def gift_request_mail(snap, display_no, app_url=""):
    """贈檔申請通知信的 (主旨, 內文)。"""
    g = snap.get("gift") or {}
    h = snap.get("header") or {}
    net = sum(r.get("net", 0) or 0 for w in snap.get("waves", []) for r in w.get("rows", []))
    subject = f"【CUE 加贈申請】{g.get('by', '')}｜{h.get('client', '')}｜加贈回饋 {g.get('pct')}%"
    lines = [
        f"{g.get('by', '')} 申請加贈回饋 {g.get('pct')}%，請主管核准。",
        "",
        f"存檔編號：{display_no}",
        f"客戶／產品：{h.get('client', '')}／{h.get('product', '')}",
        f"走期：{h.get('start', '')}～{h.get('end', '')}",
        f"實收合計：{int(net):,} 元",
        f"申請理由：{g.get('reason') or '（未填）'}",
        "",
        "核准方式：進入 CUE 系統 →「CUE 管理」→ 狀態選「加贈待核准」→ 選這一份 → 核准或退回。",
    ]
    if app_url:
        lines.append(f"系統網址：{app_url}")
    lines.append("（此信由 CUE 系統自動寄出）")
    return subject, "\n".join(lines)
