# -*- coding: utf-8 -*-
"""贈檔申請 Email 通知（主管 11/27）。"""
import mail_notify as mn


def _secret(d):
    return lambda name, default="": d.get(name, default)


SNAP = {"gift": {"pct": 5, "by": "王小明", "reason": "年底掃單", "status": "待核准"},
        "header": {"client": "客戶A", "product": "布丁", "start": "2027-01-01", "end": "2027-01-31"},
        "waves": [{"rows": [{"net": 450000}]}]}


def test_未設定不寄():
    ok, msg = mn.send(_secret({}), "s", "b")
    assert not ok and "尚未設定" in msg
    ok, msg = mn.send(_secret({"MAIL_USER": "a@x.com", "MAIL_PASSWORD": "p"}), "s", "b")
    assert not ok and "沒有收件人" in msg


def test_收件人預設用主管名單():
    assert mn.recipients(_secret({"RAGIC_REVIEWERS": "boss@x.com， ops@x.com"})) == ["boss@x.com", "ops@x.com"]
    assert mn.recipients(_secret({"RAGIC_REVIEWERS": "boss@x.com", "MAIL_TO": "only@x.com"})) == ["only@x.com"]


def test_寄信(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent["host"] = (host, port)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, u, p):
            sent["login"] = (u, p)

        def send_message(self, m):
            sent["msg"] = m

    monkeypatch.setattr(mn.smtplib, "SMTP_SSL", FakeSMTP)
    subj, body = mn.gift_request_mail(SNAP, "W2611-001", "https://app.example")
    ok, msg = mn.send(_secret({"MAIL_USER": "cue@x.com", "MAIL_PASSWORD": "app-pw", "RAGIC_REVIEWERS": "boss@x.com"}), subj, body)
    assert ok and "boss@x.com" in msg
    assert sent["host"] == ("smtp.gmail.com", 465) and sent["login"] == ("cue@x.com", "app-pw")
    assert sent["msg"]["Subject"] == "【CUE 加贈申請】王小明｜客戶A｜加贈回饋 5%"
    text = sent["msg"].get_content()
    assert "W2611-001" in text and "450,000" in text and "年底掃單" in text and "https://app.example" in text


def test_寄信失敗不丟例外(monkeypatch):
    def boom(*a, **k):
        raise OSError("連不上")
    monkeypatch.setattr(mn.smtplib, "SMTP_SSL", boom)
    ok, msg = mn.send(_secret({"MAIL_USER": "a@x.com", "MAIL_PASSWORD": "p", "MAIL_TO": "b@x.com"}), "s", "b")
    assert not ok and "連不上" in msg
