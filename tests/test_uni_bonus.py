# -*- coding: utf-8 -*-
"""統一贈檔規則（docs/specs/統一贈檔規則.md）：檔次對照宜歆《1150316 全家-統一凌晨檔次轉換說明》。"""
from datetime import date

import pytest

import agency_cue as ac
from agency_excel import generate_agency_excel
from annual_quarter_cue import UNI_NONE, UNI_PLAN1, UNI_PLAN2, build_wave_agency_model

S, E = date(2026, 12, 11), date(2026, 12, 31)
FAM20 = [{"media": "全家廣播", "region": "全省", "seconds": 20}]


def _spots(m):
    return {(sh["platform"], r["kind"]): r["spots"] for sh in m["sheets"] for r in sh["rows"]}


def _fam_total(m):
    return sum(r["spots"] for sh in m["sheets"] if sh["platform"] == ac.PLATFORM_FAMILY for r in sh["rows"])


@pytest.mark.parametrize("agency", ["2008傳媒", "凱絡"])
def test_plan1_20s_one_set(agency):
    m = build_wave_agency_model(agency, FAM20, S, E, [720], [250000], uni_plan=UNI_PLAN1)
    assert _fam_total(m) == 720 + 108 + 331                         # Excel 方案一 20 秒＝1159
    sp = _spots(m)
    assert sp[(ac.PLATFORM_FAMILY, ac.KIND_REBATE)] == 331
    if agency == "2008傳媒":                                         # 2008 贈檔一另立一列（樣張 720／108／331）
        assert sp[(ac.PLATFORM_FAMILY, ac.KIND_MAIN)] == 720 and sp[(ac.PLATFORM_FAMILY, ac.KIND_COMP)] == 108


@pytest.mark.parametrize("agency", ["2008傳媒", "凱絡"])
def test_plan2_20s_one_set(agency):
    m = build_wave_agency_model(agency, FAM20, S, E, [720], [250000], uni_plan=UNI_PLAN2)
    sp = _spots(m)
    assert _fam_total(m) == 720 + 288                               # 全家 1008
    wjf = [r for sh in m["sheets"] if sh["platform"] == ac.PLATFORM_WJF for r in sh["rows"]]
    assert sorted(r["spots"] for r in wjf) == [84, 144]             # 萬家福 84＋樂家康 144（以 20 秒計）
    assert all(sh["seconds"] == 20 for sh in m["sheets"])
    assert sp[(ac.PLATFORM_FAMILY, ac.KIND_REBATE)] == 288


def test_plan1_15s_and_two_sets_scale():
    fam15 = [{"media": "全家廣播", "region": "全省", "seconds": 15}]
    m = build_wave_agency_model("2008傳媒", fam15, S, E, [960], [250000], uni_plan=UNI_PLAN1)
    assert _spots(m)[(ac.PLATFORM_FAMILY, ac.KIND_COMP)] == 144     # Excel：15 秒 144 檔
    m2 = build_wave_agency_model("2008傳媒", FAM20, S, E, [1440], [500000], uni_plan=UNI_PLAN1)
    assert _fam_total(m2) == 1440 + 216 + 662                       # 2 組檔次加倍


def test_bonus_follows_spots_not_net():
    """年約實收可能是折扣後金額，贈檔依購買檔數算（Excel：1 組＝720 檔 20 秒）。"""
    m = build_wave_agency_model("2008傳媒", FAM20, S, E, [720], [196000], uni_plan=UNI_PLAN1)
    assert _fam_total(m) == 1159


def test_none_unchanged_and_wjf_combo_untouched():
    combos = FAM20 + [{"media": "家樂福", "region": "全省", "seconds": 20}]
    base = build_wave_agency_model("2008傳媒", combos, S, E, [720, 300], [250000, 90000])
    none = build_wave_agency_model("2008傳媒", combos, S, E, [720, 300], [250000, 90000], uni_plan=UNI_NONE)
    assert _spots(base) == _spots(none)
    p1 = build_wave_agency_model("2008傳媒", combos, S, E, [720, 300], [250000, 90000], uni_plan=UNI_PLAN1)
    wjf_main = [r["spots"] for sh in p1["sheets"] if sh["platform"] == ac.PLATFORM_WJF
                for r in sh["rows"] if r["kind"] == ac.KIND_MAIN]
    assert wjf_main == [300]                                        # 萬家福組合不受統一規則影響


@pytest.mark.parametrize("plan", [UNI_PLAN1, UNI_PLAN2])
def test_excel_renders(plan):
    m = build_wave_agency_model("凱絡", FAM20, S, E, [720], [250000], uni_plan=plan)
    assert generate_agency_excel(m)


def test_agency_plan2_without_wjf_cfg_uses_family_seconds():
    """沒有萬家福設定時，方案二萬家福贈檔以全家秒數換算（20 秒 84／144，原本固定 15 秒得 112／192）。
    代理商CUE 自訂畫面的「方案二 萬家福轉換秒數」預設也改為全家秒數。"""
    m = ac.build_agency_model("2008傳媒", "統一", "x", "", S, E, 250000,
                              {"enabled": True, "seconds": 20, "share": 100, "rebate_pct": 40,
                               "spots_override": 0, "auto_rebate": False},
                              None, ac.COMP_PLAN2, date(2026, 12, 4), 3.0)
    wjf = [r["spots"] for sh in m["sheets"] if sh["platform"] == ac.PLATFORM_WJF for r in sh["rows"]]
    assert sorted(wjf) == [84, 144]
