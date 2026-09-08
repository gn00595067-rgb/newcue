# -*- coding: utf-8 -*-
"""簡易模式「指定投放區域」測試（子公司①②③）：
  - 預設／全選六區 = 全省（行為不變）
  - 指定子集：只出所選區列、預算集中、家樂福不受影響
  - 分區單檔實作價聚合式（Net 加總 / 全省 Std）
"""
from datetime import date

import pytest

import simple_model as sm
import simple_config as sc
from fixtures_simple import sheetdata

S = date(2026, 9, 21)
E = date(2026, 10, 4)  # 2 週


def _region_rows(sheet, platform):
    blk = next(b for b in sheet.blocks if b.platform == platform)
    return [r for r in blk.rows if r.kind == "main"]


def _main_spots(sheet, platform):
    return _region_rows(sheet, platform)[0].spots


# --------------------------------------------------------------------------- #
# _effective_regions
# --------------------------------------------------------------------------- #
def test_effective_regions_none_and_full_are_national():
    assert sm._effective_regions("全家廣播", None) is None
    assert sm._effective_regions("全家廣播", ()) is None
    assert sm._effective_regions("全家廣播", list(sc.REGIONS_ORDER)) is None  # 全選=全省
    assert sm._effective_regions("家樂福", ["北區"]) is None                # 家樂福不分區


def test_effective_regions_subset_sorted_by_order():
    assert sm._effective_regions("新鮮視", ["高屏", "北區"]) == ["北區", "高屏"]


# --------------------------------------------------------------------------- #
# 全省不變性：預設 == 全選六區 == regions=None
# --------------------------------------------------------------------------- #
def test_default_equals_all_regions():
    base = sm.build_model("sub_qp_wjf", 250000, S, E, data=sheetdata())
    full = sm.build_model("sub_qp_wjf", 250000, S, E, data=sheetdata(),
                          regions=list(sc.REGIONS_ORDER))
    for b, f in zip(base.sheets, full.sheets):
        assert _main_spots(b, "全家廣播") == _main_spots(f, "全家廣播")
        assert len(_region_rows(b, "全家廣播")) == len(_region_rows(f, "全家廣播")) == 6


# --------------------------------------------------------------------------- #
# 指定子集：只出所選區列
# --------------------------------------------------------------------------- #
def test_subset_emits_only_selected_region_rows():
    m = sm.build_model("sub_qp_wjf", 250000, S, E, data=sheetdata(),
                       regions=["北區", "桃竹苗"])
    sh = m.sheets[0]
    rows = _region_rows(sh, "全家廣播")
    assert [r.region for r in rows] == ["北區", "桃竹苗"]


def test_carrefour_block_unaffected_by_regions():
    """家樂福（萬家福/樂家康）不分區，指定區域不影響其列數。"""
    base = sm.build_model("sub_qp_wjf", 250000, S, E, data=sheetdata())
    sub = sm.build_model("sub_qp_wjf", 250000, S, E, data=sheetdata(), regions=["北區"])
    b_cf = next(b for b in base.sheets[0].blocks if b.platform == "家樂福")
    s_cf = next(b for b in sub.sheets[0].blocks if b.platform == "家樂福")
    assert [r.region for r in b_cf.rows] == [r.region for r in s_cf.rows]


# --------------------------------------------------------------------------- #
# 聚合式：Net 加總 / 全省 Std
# --------------------------------------------------------------------------- #
def test_unit_net_subset_is_net_sum_over_national_std():
    d = sheetdata()
    f = sm.factor("全家廣播", 30, d)
    nat_std = d.pricing["全家廣播"]["全省"]["Std"]
    net_sum = (d.pricing["全家廣播"]["北區"]["Net"]
               + d.pricing["全家廣播"]["桃竹苗"]["Net"])
    expect = net_sum / nat_std * f
    assert sm.sub_unit_net("全家廣播", 30, d, ["北區", "桃竹苗"]) == pytest.approx(expect)


def test_qp_north_plus_taoyuan_equals_national_spots():
    """全家廣播 北區(200k)+桃竹苗(120k) Net 加總=320k=全省 → 檔次應等於全省。"""
    d = sheetdata()
    full = sm.build_model("sub_qp_wjf", 250000, S, E, data=d)
    sub = sm.build_model("sub_qp_wjf", 250000, S, E, data=d, regions=["北區", "桃竹苗"])
    for a, b in zip(full.sheets, sub.sheets):
        assert _main_spots(a, "全家廣播") == _main_spots(b, "全家廣播")


def test_cheaper_single_region_buys_more_spots():
    """單投北區(Net 200k<全省 320k) → 單價較低 → 檔次多於全省。"""
    d = sheetdata()
    full = sm.build_model("sub_qp_wjf", 250000, S, E, data=d)
    north = sm.build_model("sub_qp_wjf", 250000, S, E, data=d, regions=["北區"])
    assert _main_spots(north.sheets[0], "全家廣播") > _main_spots(full.sheets[0], "全家廣播")


def test_fresh_view_north_equals_national_spots():
    """新鮮視 北區 Net=全省 Net(120k) 且 Std 用全省 504 → 北區單投檔次=全省。"""
    d = sheetdata()
    full = sm.build_model("sub_fv_wjf", 250000, S, E, data=d)
    north = sm.build_model("sub_fv_wjf", 250000, S, E, data=d, regions=["北區"])
    assert _main_spots(north.sheets[0], "新鮮視") == _main_spots(full.sheets[0], "新鮮視")


def test_both_region_blocks_filtered_in_combo1():
    """組合① 全家廣播＋新鮮視 兩區塊都受區域選擇影響。"""
    m = sm.build_model("sub_qp_fv", 250000, S, E, data=sheetdata(),
                       regions=["北區", "高屏"])
    sh = m.sheets[0]
    assert [r.region for r in _region_rows(sh, "全家廣播")] == ["北區", "高屏"]
    assert [r.region for r in _region_rows(sh, "新鮮視")] == ["北區", "高屏"]


def test_reach_only_counts_selected_regions():
    """指定區域後，效益（曝光）只計所選區店數，應少於全省。"""
    d = sheetdata()
    full = sm.build_model("sub_qp_wjf", 250000, S, E, data=d)
    north = sm.build_model("sub_qp_wjf", 250000, S, E, data=d, regions=["北區"])
    assert north.sheets[0].reach["impressions"] < full.sheets[0].reach["impressions"]
