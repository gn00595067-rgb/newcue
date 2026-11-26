# -*- coding: utf-8 -*-
"""全省回饋門檻（主管 11/26 Q1：11/24 新表取代舊表，不看走期）。"""
import pytest

import rebate
import rebate_rules as rr


@pytest.mark.parametrize("budget,expect", [
    (299_999, None), (300_000, None), (450_000, None),      # 30 萬級 0%＝不給
    (500_000, (10, 15)), (899_999, (10, 15)),
    (900_000, (15, 20)), (999_999, (15, 20)),
    (1_000_000, None), (3_000_000, None),                   # 100 萬以上專案談
])
def test_全家企頻(budget, expect):
    assert rr.nat_rad_pct(budget) == expect


@pytest.mark.parametrize("budget,expect", [
    (249_999, None), (250_000, None), (499_999, None),
    (500_000, 20), (750_000, 25), (999_999, 25), (1_000_000, None),
])
def test_萬家福(budget, expect):
    assert rr.nat_cf_pct(budget) == expect


def _cfg(rad=None, cf=None):
    c = {}
    if rad is not None:
        c["全家廣播"] = {"share": rad, "sec_shares": {15: 100}, "is_national": True, "regions": ["全省"]}
    if cf is not None:
        c["家樂福"] = {"share": cf, "sec_shares": {15: 100}, "is_national": True, "regions": ["全省"]}
    return c


def test_不看走期_半年以上也照給():
    q = rebate.get_rebate_qualification_detail(_cfg(rad=100), 600_000, 200)
    assert q["nat_rad"] is True
    assert rebate._build_rebate_pct_map(_cfg(rad=100), 600_000, 200)[("全家廣播", "全省")] == 10


def test_專案談提示():
    assert rr.project_negotiation_platforms(_cfg(rad=60, cf=40), 2_000_000) == ["全家企頻"]
    assert rr.project_negotiation_platforms(_cfg(rad=100), 999_999) == []
