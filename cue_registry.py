# -*- coding: utf-8 -*-
"""
存檔編號、業務代碼、CUE 統計（Ragic 串接第 5 期）。規格：docs/specs/Ragic串接_第5期_存檔編號與統計.md

存檔編號 `P2610-023`：業務代碼＋存檔年(西元後兩碼)月＋該業務當年度第幾張；成交（已訂檔）顯示 `★P2610-023`。
本模組不 import streamlit。
"""
import re
from datetime import datetime

import cue_store as cs

NO_RE = re.compile(r"^([A-Z]{1,3})(\d{2})(\d{2})-(\d{3,})$")
STAR = "★"


def sales_code(name, email="", overrides=None):
    """業務代碼：overrides（信箱→代碼）優先；否則取名稱中英文名的首字母；沒有英文名取信箱首字母。"""
    ov = {k.strip().lower(): v.strip().upper() for k, v in (overrides or {}).items() if k and v}
    if email and email.lower() in ov:
        return ov[email.lower()]
    m = re.search(r"[A-Za-z]", name or "")
    if m:
        return m.group(0).upper()
    m = re.search(r"[A-Za-z]", email or "")
    return m.group(0).upper() if m else "X"


def parse_overrides(text):
    """Secrets 字串「a@x.com=AL, b@x.com=B」→ dict。"""
    out = {}
    for part in re.split(r"[,，;\n]", text or ""):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def parse_no(no):
    """'P2610-023' → (代碼, 年兩碼, 月, 流水)；格式不符回 None。"""
    m = NO_RE.match((no or "").lstrip(STAR))
    return (m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))) if m else None


def next_no(code, existing_nos, now=None):
    """同代碼、同年的最大流水號 +1。existing_nos：既有存檔編號（可含 ★）。"""
    now = now or datetime.now()
    yy = now.year % 100
    top = 0
    for no in existing_nos:
        p = parse_no(no)
        if p and p[0] == code and p[1] == yy:
            top = max(top, p[3])
    return f"{code}{yy:02d}{now.month:02d}-{top + 1:03d}"


def is_deal(snap):
    """成交＝已送訂檔（有 booking 且沒被退回）。"""
    return bool((snap or {}).get("booking")) and cs.status_of(snap) != cs.REJECTED


def display_no(snap):
    no = (snap or {}).get("save_no") or ""
    return (STAR + no) if no and is_deal(snap) else no


def owner_of(snap):
    return (snap or {}).get("owner") or {}


def net_total(snap):
    return sum(r.get("net", 0) for w in (snap or {}).get("waves", []) for r in w.get("rows", []))


def stats(snaps, year=None, months=None):
    """依存檔編號年月統計：{業務名: {"code","saved","deals","rate","deal_net"}}。
    year：西元年（None＝全部）；months：月份集合（None＝全部）。只算有編號的新存檔。"""
    out = {}
    for s in snaps:
        p = parse_no(s.get("save_no"))
        if not p:
            continue
        code, yy, mm, _seq = p
        if year is not None and yy != year % 100:
            continue
        if months and mm not in months:
            continue
        o = owner_of(s)
        k = o.get("name") or code
        row = out.setdefault(k, {"code": o.get("code") or code, "saved": 0, "deals": 0, "deal_net": 0})
        row["saved"] += 1
        if is_deal(s):
            row["deals"] += 1
            row["deal_net"] += net_total(s)
    for row in out.values():
        row["rate"] = row["deals"] / row["saved"] if row["saved"] else 0.0
    return out


def code_conflicts(snaps):
    """同一代碼出現在不同業務 → {代碼: [姓名…]}（提醒用 Secrets 覆寫）。"""
    seen = {}
    for s in snaps:
        o = owner_of(s)
        if o.get("code") and o.get("email"):
            seen.setdefault(o["code"], set()).add(o.get("name") or o["email"])
    return {c: sorted(n) for c, n in seen.items() if len(n) > 1}
