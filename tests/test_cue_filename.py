from datetime import date
from utils import build_cue_filename


def _rows():
    return [{"media": "全家廣播", "seconds": 20}, {"media": "新鮮視", "seconds": 10},
            {"media": "家樂福", "seconds": 20}]


def test_general_cue_filename():
    fn = build_cue_filename("萬國通路", _rows(), 250000, "宜", today=date(2026, 10, 5))
    assert fn == "1005 萬國通路 全家+新鮮視+萬家福.樂家康(10.20秒) 25萬專案-宜.xlsx"


def test_general_cue_filename_segment_pdf_and_odd_budget():
    fn = build_cue_filename("萬國通路", _rows()[:1], 255000, "", today=date(2026, 10, 5),
                            ext="pdf", seg_label="波段2")
    assert fn == "1005 萬國通路 全家(20秒) 25.5萬專案-波段2.pdf"


def test_agency_sheet_name_uses_full_wjf_name():
    import agency_cue as ac
    from agency_excel import _sheet_name
    m = {"agency": "凱絡", "start_date": date(2026, 10, 15), "end_date": date(2026, 11, 5)}
    assert _sheet_name(m, {"platform": ac.PLATFORM_WJF, "seconds": 15}) == "萬家福樂家康 1015-1105 15秒"
    m["agency"] = "2008傳媒"
    assert "萬家福樂家康" in _sheet_name(m, {"platform": ac.PLATFORM_WJF, "seconds": 15, "budget": 250000})


def test_simple_subsidiary_filename_has_client():
    import simple_model as sm
    import simple_config as sc
    fn = sm._filename(sc.COMBOS["sub_qp_fv"], 250000, "宜", "萬國通路", date(2026, 10, 5))
    assert fn.startswith("1005 萬國通路 企頻+新鮮視(")
    assert fn.endswith(" 25萬專案-宜.xlsx")


def test_agency_channel_text():
    import agency_cue as ac
    assert ac.agency_channel_text({"sheets": [{"platform": ac.PLATFORM_WJF}]}) == "萬家福樂家康廣播"
    m = {"sheets": [{"platform": ac.PLATFORM_FAMILY}, {"platform": ac.PLATFORM_WJF},
                    {"platform": ac.PLATFORM_WJF}]}
    assert ac.agency_channel_text(m) == "全家廣播+萬家福樂家康廣播"
