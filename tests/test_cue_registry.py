# -*- coding: utf-8 -*-
"""存檔編號、業務代碼、統計（第 5 期）。"""
from datetime import datetime

import cue_registry as reg
import cue_store as cs


def test_sales_code():
    assert reg.sales_code("楊心瑀 Alison", "x@y.com") == "A"
    assert reg.sales_code("王小明", "peggy@soundwow.com") == "P"
    assert reg.sales_code("楊心瑀 Alison", "a@x.com", {"A@X.com": "al"}) == "AL"
    assert reg.parse_overrides("a@x.com=AL，b@x.com = B") == {"a@x.com": "AL", "b@x.com": "B"}


def test_next_no_per_code_and_year():
    now = datetime(2026, 10, 14)
    assert reg.next_no("P", [], now) == "P2610-001"
    nos = ["P2601-001", "★P2609-022", "A2610-005", "P2512-099", "亂碼"]
    assert reg.next_no("P", nos, now) == "P2610-023"            # 同代碼同年最大 22 → 23；去年的不算
    assert reg.next_no("P", nos, datetime(2027, 1, 2)) == "P2701-001"   # 每年重算
    assert reg.parse_no("★P2610-023") == ("P", 26, 10, 23)


def _s(no, name, booked=False, net=1000, status=None):
    s = {"save_no": no, "owner": {"name": name, "code": no[0], "email": f"{name}@x"},
         "waves": [{"rows": [{"net": net}]}]}
    if booked:
        s["booking"] = {"cue_id": "1"}
        s["status"] = cs.BOOKED
    if status:
        s["status"] = status
    return s


def test_display_and_stats():
    snaps = [_s("P2609-001", "Peggy"), _s("P2610-002", "Peggy", booked=True, net=5000),
             _s("P2610-003", "Peggy", booked=True, status=cs.REJECTED), _s("A2610-001", "Alison"),
             _s("A2510-009", "Alison", booked=True), {"save_no": ""}]
    assert reg.display_no(snaps[1]) == "★P2610-002" and reg.display_no(snaps[0]) == "P2609-001"
    assert reg.display_no(snaps[2]) == "P2610-003"                      # 退回不算成交
    st = reg.stats(snaps, year=2026)
    assert st["Peggy"] == {"code": "P", "saved": 3, "deals": 1, "deal_net": 5000, "rate": 1 / 3}
    assert st["Alison"]["saved"] == 1 and st["Alison"]["deals"] == 0     # 2025 年的不算
    assert reg.stats(snaps, year=2026, months={10})["Peggy"]["saved"] == 2


def test_code_conflicts():
    a = {"owner": {"code": "A", "email": "a1@x", "name": "Alison"}}
    b = {"owner": {"code": "A", "email": "a2@x", "name": "Amy"}}
    assert reg.code_conflicts([a, b]) == {"A": ["Alison", "Amy"]}
