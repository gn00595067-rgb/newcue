# -*- coding: utf-8 -*-
"""兩版效益比較（第二階段 2-3）。"""
from datetime import date

import plan_compare as pc


def _rows(spots, gift=0):
    r = [{"media": "全家廣播", "region": "中區", "program_num": 850, "spots": spots, "schedule": [spots]}]
    if gift:
        r.append({"media": "全家廣播", "region": "中區", "program_num": "", "spots": gift, "schedule": [gift], "is_rebate": True})
    return r


def test_存方案與比較():
    a = pc.make_plan("方案 A", _rows(900), 30, 300_000, date(2027, 3, 1), date(2027, 3, 30))
    b = pc.make_plan("方案 B", _rows(1500, gift=150), 30, 500_000, date(2027, 3, 1), date(2027, 3, 30))
    plans = pc.add_plan(pc.add_plan([], a), b)
    assert [p["name"] for p in plans] == ["方案 A", "方案 B"] and pc.next_name(plans) == "方案 C"
    rows = {r["項目"]: r for r in pc.compare_rows(plans)}
    assert rows["總曝光次數"]["方案 A"] == "765,000"
    assert rows["總曝光次數"]["方案 B"] == "1,402,500（+83%）"
    assert rows["其中加贈檔次"]["方案 B"].startswith("150")
    notes = pc.best_notes(plans)
    assert notes[0] == "曝光最多：方案 B（1,402,500 次）" and any("加贈最多：方案 B" in n for n in notes)


def test_同名覆蓋與上限():
    plans = []
    for i in range(6):
        plans = pc.add_plan(plans, pc.make_plan(f"P{i}", _rows(100 + i), 10, 1000))
    assert [p["name"] for p in plans] == ["P2", "P3", "P4", "P5"]
    plans = pc.add_plan(plans, pc.make_plan("P3", _rows(999), 10, 1000))
    assert [p["name"] for p in plans] == ["P2", "P4", "P5", "P3"] and plans[-1]["spots"] == 999
