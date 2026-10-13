# -*- coding: utf-8 -*-
"""年約季約細CUE 套 2008／凱絡格式（docs/specs/格式選擇擴充.md 需求 2）。"""
import io
from datetime import date

import pytest
from openpyxl import load_workbook

import agency_cue as ac
from agency_excel import generate_agency_excel
from agency_ui import build_agency_html
from annual_quarter_cue import agency_combo_ok, build_wave_agency_model

COMBOS = [
    {"media": "全家廣播", "region": "全省", "seconds": 15},
    {"media": "全家廣播", "region": "全省", "seconds": 20},
    {"media": "家樂福", "region": "全省", "seconds": 20},
    {"media": "新鮮視", "region": "全省", "seconds": 15},     # 不支援 → 略過
    {"media": "全家廣播", "region": "北區", "seconds": 15},   # 分區 → 略過
]
S, E = date(2027, 1, 4), date(2027, 1, 31)


def test_combo_ok():
    assert [agency_combo_ok(c) for c in COMBOS] == [True, True, True, False, False]


@pytest.mark.parametrize("agency", ["2008傳媒", "凱絡"])
@pytest.mark.parametrize("comp", ac.COMP_OPTIONS)
def test_wave_model(agency, comp):
    spots = [1000, 600, 400, 500, 500]
    nets = [120000, 80000, 100000, 50000, 50000]
    m = build_wave_agency_model(agency, COMBOS, S, E, spots, nets, client_name="客", product_name="品",
                                comp_mode=comp, ac_pct=3.0)
    main = [s for s in m["sheets"] if s["budget"]]
    assert len(main) == 3                     # 新鮮視／分區不出
    assert m["budget_total"] == 300000
    for sh, sp, nt in zip(main, spots, nets):
        mrow = next(r for r in sh["rows"] if r["kind"] == ac.KIND_MAIN)
        if sh["platform"] == ac.PLATFORM_FAMILY:
            if agency == "2008傳媒":
                assert mrow["spots"] == sp and mrow["net_display"] == nt
                assert sh["fees"]["budget_net"] == nt
            else:
                assert mrow["net_display"] == nt
        else:
            assert mrow["net_display"] == nt
    wb = load_workbook(io.BytesIO(generate_agency_excel(m, date(2026, 10, 13))))
    assert len(wb.sheetnames) == len(m["sheets"])
    assert "客" in build_agency_html(m, date(2026, 10, 13))


def test_zero_spots_skipped():
    m = build_wave_agency_model("凱絡", COMBOS, S, E, [0, 0, 300, 0, 0], [0, 0, 90000, 0, 0])
    assert len(m["sheets"]) == 1 and m["sheets"][0]["platform"] == ac.PLATFORM_WJF
