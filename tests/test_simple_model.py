# -*- coding: utf-8 -*-
"""簡易模式 model 測試（§10.1）：數字規則精確驗證，全離線。"""
from datetime import date

import pytest

import simple_model as sm
import simple_config as sc
from fixtures_simple import sheetdata

S = date(2026, 9, 21)


def _spots_by_platform(sheet):
    """回傳 {platform: 該區塊主列每列檔次}（子公司主列同檔次）。"""
    out = {}
    for blk in sheet.blocks:
        main = next(r for r in blk.rows if r.kind == "main")
        out[blk.platform] = main.spots
    return out


# --------------------------------------------------------------------------- #
# distribute（§4.5）
# --------------------------------------------------------------------------- #
def test_distribute_basic():
    assert sm.distribute(147, 14) == [11] * 7 + [10] * 7
    assert sm.distribute(191, 14) == [14] * 9 + [13] * 5
    assert sm.distribute(348, 14) == [25] * 12 + [24] * 2
    assert sm.distribute(480, 21) == [23] * 18 + [22] * 3
    assert sm.distribute(72, 22) == [4] * 6 + [3] * 16
    assert sm.distribute(1440, 11) == [131] * 10 + [130]


@pytest.mark.parametrize("n,d", [(147, 14), (191, 14), (0, 7), (5, 7), (100, 1)])
def test_distribute_sum_preserved(n, d):
    sch = sm.distribute(n, d)
    assert len(sch) == d
    assert sum(sch) == n
    # 前 rem 天比後面多 1
    assert max(sch) - min(sch) <= 1


# --------------------------------------------------------------------------- #
# 子公司 allocate_spots 參考向量（§4.4）—— 精確相等
# --------------------------------------------------------------------------- #
SUB_VECTORS = {
    # combo, budget: {sec: (block1_spots, block2_spots)}  (block 順序同 COMBOS["blocks"])
    ("sub_qp_fv", 200000): {30: (120, 168), 20: (141, 252), 15: (184, 336), 10: (240, 504)},
    ("sub_qp_fv", 250000): {30: (150, 210), 20: (176, 315), 15: (230, 420), 10: (300, 630)},
    ("sub_qp_wjf", 250000): {30: (112, 225), 20: (168, 264), 15: (197, 346), 10: (258, 450)},
    ("sub_fv_wjf", 250000): {30: (112, 210), 20: (168, 315), 15: (197, 420), 10: (258, 630)},
}


@pytest.mark.parametrize("key,budget", list(SUB_VECTORS.keys()))
def test_subsidiary_reference_vectors(key, budget):
    model = sm.build_model(key, budget, S, date(2026, 10, 4), data=sheetdata())
    blocks = sc.COMBOS[key]["blocks"]
    for sheet in model.sheets:
        b1, b2 = SUB_VECTORS[(key, budget)][sheet.seconds]
        got = _spots_by_platform(sheet)
        assert got[blocks[0]] == b1, f"{key} {budget} {sheet.seconds}s block1"
        assert got[blocks[1]] == b2, f"{key} {budget} {sheet.seconds}s block2"


# --------------------------------------------------------------------------- #
# 子公司填滿度與不超預算（§4.4 / §12.4）
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("key", sc.SUBSIDIARY_COMBOS)
@pytest.mark.parametrize("budget", [125000, 200000, 250000, 300000, 400000, 1000000])
@pytest.mark.parametrize("days", [7, 14, 21, 28, 56])
def test_subsidiary_fill_and_cap(key, budget, days):
    from datetime import timedelta
    model = sm.build_model(key, budget, S, S + timedelta(days=days - 1), data=sheetdata())
    for sheet in model.sheets:
        assert sheet.hidden_net_total <= budget + 1e-6, "實收不得超過預算"
        assert sheet.hidden_net_total >= 0.99 * budget, "填滿度需 ≥ 99%"
        for blk in sheet.blocks:
            main = next(r for r in blk.rows if r.kind == "main")
            assert main.spots > 0
            # 樂家康 = rhu(量販 × 720/420)
            if blk.platform == "家樂福":
                sup = next(r for r in blk.rows if r.kind == "super")
                assert sup.spots == sm.rhu(main.spots * 720 / 420)


# --------------------------------------------------------------------------- #
# 子公司費用（§4.6 / §10.1）
# --------------------------------------------------------------------------- #
def test_subsidiary_fees():
    m0 = sm.build_model("sub_qp_fv", 200000, S, date(2026, 10, 4), data=sheetdata())
    f0 = m0.sheets[0].fees
    assert f0["vat"] == 10000 and f0["grand"] == 210000
    m1 = sm.build_model("sub_qp_fv", 200000, S, date(2026, 10, 4),
                        prod_cost=20000, data=sheetdata())
    f1 = m1.sheets[0].fees
    assert f1["vat"] == 11000 and f1["grand"] == 231000


# --------------------------------------------------------------------------- #
# 代理商主檔次（§10.1）
# --------------------------------------------------------------------------- #
def test_agency_main_spots_250k():
    fam2008 = sm.build_model("ag_2008_fam", 250000, date(2026, 6, 8),
                             date(2026, 6, 28), data=sheetdata())
    got = {s.seconds: s.blocks[0].rows[0].spots for s in fam2008.sheets}
    assert got == {30: 480, 20: 720, 15: 960, 10: 1440}

    wjf2008 = sm.build_model("ag_2008_wjf", 250000, date(2026, 7, 17),
                             date(2026, 7, 30), data=sheetdata())
    gotw = {s.seconds: s.blocks[0].rows[0].spots for s in wjf2008.sheets}
    assert gotw == {10: 840, 15: 560, 20: 420}


# --------------------------------------------------------------------------- #
# 2008 回饋列（§4.8 / 4.9 / §10.1）
# --------------------------------------------------------------------------- #
def test_2008_family_bonus_rows():
    m = sm.build_model("ag_2008_fam", 250000, date(2026, 6, 8),
                       date(2026, 6, 28), data=sheetdata())
    exp = {30: (72, 221), 20: (108, 331), 15: (144, 442), 10: (216, 662)}
    for s in m.sheets:
        bonus = [r.spots for r in s.blocks[0].rows if r.kind == "bonus"]
        assert tuple(bonus) == exp[s.seconds]


def test_2008_wjf_bonus_rows():
    m = sm.build_model("ag_2008_wjf", 250000, date(2026, 7, 17),
                       date(2026, 7, 30), data=sheetdata())
    exp = {10: (84, 144), 15: (56, 96), 20: (42, 72)}
    for s in m.sheets:
        rb = next(r for r in s.blocks[0].rows if r.kind == "bonus")
        rbs = next(r for r in s.blocks[0].rows if r.kind == "super_bonus")
        assert (rb.spots, rbs.spots) == exp[s.seconds]


# --------------------------------------------------------------------------- #
# 凱絡回饋列與價值（§4.10 / 4.11 / §10.1）
# --------------------------------------------------------------------------- #
def test_carat_family_bonus_rows():
    m = sm.build_model("ag_carat_fam", 250000, date(2026, 9, 7),
                       date(2026, 9, 28), data=sheetdata())
    exp = {30: (72, 192, 29), 20: (108, 288, 43), 15: (144, 384, 58), 10: (216, 576, 86)}
    for s in m.sheets:
        bonus = tuple(r.spots for r in s.blocks[0].rows if r.kind == "bonus")
        assert bonus == exp[s.seconds]


def test_carat_family_media_value_30s():
    m = sm.build_model("ag_carat_fam", 250000, date(2026, 9, 7),
                       date(2026, 9, 28), data=sheetdata())
    s30 = next(s for s in m.sheets if s.seconds == 30)
    assert s30.fees["media_value"] == 1739250
    assert s30.fees["discount_value"] == 1489250


def test_carat_wjf_no_bonus():
    m = sm.build_model("ag_carat_wjf", 250000, date(2026, 9, 18),
                       date(2026, 9, 28), data=sheetdata())
    for s in m.sheets:
        kinds = [r.kind for r in s.blocks[0].rows]
        assert "bonus" not in kinds
        assert kinds == ["main", "super"]


# --------------------------------------------------------------------------- #
# 代理商費用（§4.8 / 4.10 / §10.1）
# --------------------------------------------------------------------------- #
def test_2008_fees():
    m = sm.build_model("ag_2008_fam", 250000, date(2026, 6, 8),
                       date(2026, 6, 28), data=sheetdata())
    f = m.sheets[0].fees
    assert (f["ac"], f["tax"], f["total"]) == (7500, 12875, 270375)


def test_carat_fees():
    m = sm.build_model("ag_carat_fam", 250000, date(2026, 9, 7),
                       date(2026, 9, 28), data=sheetdata())
    f = m.sheets[0].fees
    assert f["ac_free"] is True
    assert (f["vat"], f["grand"]) == (12500, 262500)


# --------------------------------------------------------------------------- #
# 牌價表（§4.7）
# --------------------------------------------------------------------------- #
def test_list_prices():
    d = sheetdata()
    assert sm._list_per("2008傳媒", "全家企頻", 30, d) == 3000
    assert sm._list_per("2008傳媒", "全家企頻", 10, d) == 1500
    assert sm._list_per("2008傳媒", "萬家福", 10, d) == 2600
    assert sm._list_per("凱絡", "全家企頻", 20, d) == 2550
    assert sm._list_per("凱絡", "萬家福", 20, d) == 4000


# --------------------------------------------------------------------------- #
# 日期（§4.12）
# --------------------------------------------------------------------------- #
def test_dates():
    m = sm.build_model("sub_qp_fv", 200000, S, date(2026, 10, 4), data=sheetdata())
    assert m.sign_deadline == date(2026, 9, 14)
    assert m.material_due == date(2026, 9, 14)
    assert m.billing_month == "115年10月"     # 結束日 10/4 → 民國115年10月


def test_days_count():
    m = sm.build_model("sub_qp_fv", 200000, S, date(2026, 10, 4), data=sheetdata())
    for s in m.sheets:
        assert len(s.days) == 14
        for blk in s.blocks:
            for r in blk.rows:
                if r.schedule is not None:
                    assert len(r.schedule) == 14
