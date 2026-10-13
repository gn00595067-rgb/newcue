# -*- coding: utf-8 -*-
"""CUE 快照（Ragic 串接第 2 期）：各模式正規化、實收分攤、版本／異動紀錄、details 往返。"""
from datetime import date, datetime

import pytest

import cue_store as cs
import simple_config as sc
import simple_model as sm
from annual_quarter_cue import build_wave_agency_model
from config import RAGIC_MAP
from fixed_projects import FIXED_PROJECTS, build_project_rows
from fixtures_simple import sheetdata


def _simple(key):
    return sm.build_model(key, 250000, date(2026, 10, 19), date(2026, 11, 1), client="客", data=sheetdata())


@pytest.mark.parametrize("key", sc.SUBSIDIARY_COMBOS + sc.AGENCY_COMBOS)
def test_simple_sheet_net_equals_budget(key):
    m = _simple(key)
    rows = cs.norm_simple_sheet(m, m.sheets[0])
    assert rows and all(r["platform"] in ("全家廣播", "新鮮視", "家樂福") for r in rows)
    if m.family == "subsidiary":
        assert sum(r["net"] for r in rows) == m.sheets[0].budget
    assert all(r["net"] == 0 for r in rows if r["kind"] != "main")


def test_project_rows_spread():
    p = next(iter(FIXED_PROJECTS.values()))
    rows = cs.norm_general_rows(build_project_rows(p))
    assert sum(r["net"] for r in rows) == p["budget"]       # 同群組實收依定價分攤，合計＝專案價


def test_general_non_pkg_and_rebate():
    rows = [
        {"media": "新鮮視", "region": "北區", "seconds": 15, "spots": 100, "schedule": [50, 50],
         "rate_display": 9000, "pkg_display": 7000, "is_pkg_member": False},
        {"media": "新鮮視", "region": "北區", "seconds": 15, "spots": 10, "schedule": [5, 5],
         "rate_display": 900, "pkg_display": "回饋", "is_pkg_member": False, "is_rebate": True},
    ]
    n = cs.norm_general_rows(rows)
    assert [r["net"] for r in n] == [7000, 0] and n[1]["kind"] == "rebate"


def test_agency_model_rows():
    combos = [{"media": "全家廣播", "region": "全省", "seconds": 15}, {"media": "家樂福", "region": "全省", "seconds": 20}]
    m = build_wave_agency_model("凱絡", combos, date(2027, 1, 4), date(2027, 1, 31), [800, 300], [100000, 90000])
    rows = cs.norm_agency_model(m)
    assert sum(r["net"] for r in rows) == 190000
    assert {r["region"] for r in rows if r["platform"] == "家樂福"} == {"全省量販", "全省超市"}


def test_scale_net():
    rows = [{"net": 100}, {"net": 300}]
    cs.scale_net(rows, 1000)
    assert sum(r["net"] for r in rows) == 1000 and rows[1]["net"] == 750


def _snap(spots=100, budget=50000):
    rows = [cs._row("全家廣播", "北區", 15, spots, [spots], net=budget, lst=budget * 2)]
    return cs.make_snapshot("一般CUE", {"client": "客", "start": date(2027, 1, 1), "end": date(2027, 1, 1),
                                        "budget": budget}, [{"label": "", "start": date(2027, 1, 1),
                                                             "end": date(2027, 1, 1), "rows": rows}],
                            restore={"aq_waves": [{"start": date(2027, 1, 1)}]}, customer={"編號": "C01399"})


def test_version_and_diff():
    v1 = cs.next_version(None, _snap(), "王小明", datetime(2026, 10, 13, 9, 0))
    assert v1["version"] == 1 and v1["history"][0]["changes"] == ["新建"]
    v2 = cs.next_version(v1, _snap(spots=120, budget=60000), "李主管", datetime(2026, 10, 14, 9, 0))
    assert v2["version"] == 2 and len(v2["history"]) == 2
    ch = v2["history"][-1]["changes"]
    assert any("預算" in c for c in ch) and any("檔次 100 → 120" in c for c in ch)
    v3 = cs.next_version(v2, _snap(spots=120, budget=60000), "李主管")
    assert v3["history"][-1]["changes"] == ["內容無變動（重新存檔）"]


def test_details_roundtrip_and_restore_dates():
    s = cs.next_version(None, _snap(), "王小明")
    txt = cs.details_text(s, legacy="舊文字\n[EXT]{}")
    assert cs.legacy_part(txt) == "舊文字\n[EXT]{}"
    back = cs.parse_snapshot(txt)
    assert back["version"] == 1
    assert cs.from_jsonable(back["restore"])["aq_waves"][0]["start"] == date(2027, 1, 1)
    assert cs.parse_snapshot("沒有快照") is None and cs.parse_snapshot(cs.SNAP_MARK + "{壞掉") is None


def test_ragic_fields():
    s = _snap()
    f = cs.ragic_fields(s, RAGIC_MAP, extra={RAGIC_MAP["format"]: "東吳"})
    assert f[RAGIC_MAP["client"]] == "客" and f[RAGIC_MAP["date_start"]] == "2027-01-01"
    assert f[cs.CUE2_CUSTOMER_ID] == "C01399" and f[cs.CUE2_NET_TOTAL] == 50000 and f[cs.CUE2_WAVES] == 1
    assert f[RAGIC_MAP["platform"]] == "全家企頻" and f[RAGIC_MAP["platform_detail"]] == "全家北頻"
    assert f[RAGIC_MAP["format"]] == "東吳"


def test_legacy_parsers_ignore_snapshot():
    import agency_cue as ac
    txt = cs.details_text(_snap(), legacy='摘要\n' + ac.AGENCY_EXT_MARKER + '{"agency": "凱絡"}')
    assert ac.parse_agency_ext(txt) == {"agency": "凱絡"}


def test_split_waves():
    rows = [cs._row("全家廣播", "北區", 15, 40, [10, 10, 0, 10, 10], net=1001)]
    w = cs.split_waves(rows, date(2027, 1, 1), [(date(2027, 1, 1), date(2027, 1, 2)), (date(2027, 1, 4), date(2027, 1, 5))])
    assert [x["rows"][0]["spots"] for x in w] == [20, 20]
    assert sum(x["rows"][0]["net"] for x in w) == 1001
