# -*- coding: utf-8 -*-
"""佳聖一鍵CUE（宜歆 #11，spec docs/specs/佳聖一鍵CUE.md）：數字對齊宜歆範例。"""
import io
from datetime import date

from openpyxl import load_workbook

import simple_config as sc
import simple_excel as se
import simple_html as shtml
import simple_model as sm

START, END = date(2026, 12, 22), date(2026, 12, 31)


def _sheet(model, sec):
    return next(s for s in model.sheets if s.seconds == sec)


def test_ddrive_combos_in_agency_list():
    assert "ag_ddrive_fam" in sc.AGENCY_COMBOS and "ag_ddrive_wjf" in sc.AGENCY_COMBOS
    assert "ag_ddrive_fam" not in sc.SUBSIDIARY_COMBOS


def test_ddrive_wjf_matches_example():
    # 萬家福 10 萬、15 秒：100000/(29.76×15)=224 檔；樂家康 224×24/14=384
    m = sm.build_model("ag_ddrive_wjf", 100000, START, END, client="統一", product="寶多福")
    sh = _sheet(m, 15)
    mag, sup = sh.blocks[0].rows
    assert (mag.spots, sup.spots) == (224, 384)
    assert mag.schedule == [23] * 4 + [22] * 6 and sup.schedule == [39] * 4 + [38] * 6
    assert (mag.list_total, sup.list_total) == (672_000, 1_152_000)   # 每檔 3,000，兩列都計
    assert mag.net_display == 100000 and sup.net_display == "計於萬家福"
    assert mag.station == '萬家福-15"量販店' and sup.station == '樂家康-15"超市'
    assert mag.material == "12/16\n1200前"
    assert len(sh.blocks[0].rows) == 2                                # 不附回饋列
    assert sh.fees == {"type": "ddrive", "net": 100000, "vat": 5000, "gross": 105000, "grand": 105000}
    assert m.remarks == [("* 請款金額：12月份Net$100,000元(未稅)。", False)]


def test_ddrive_family_matches_example():
    # 全家 5 萬、15 秒：50000/(17.36×15)=192 檔
    m = sm.build_model("ag_ddrive_fam", 50000, START, END)
    rows = _sheet(m, 15).blocks[0].rows
    assert len(rows) == 1 and rows[0].spots == 192


def test_ddrive_excel_layout():
    m = sm.build_model("ag_ddrive_wjf", 100000, START, END, client="統一", product="寶多福")
    wb = load_workbook(io.BytesIO(se.render(m, formulas=False)))
    assert len(wb.worksheets) == 3
    ws = next(w for w in wb.worksheets if "15秒" in w.title)
    assert "佳聖媒體" in ws.oddHeader.center.text
    # 欄位自 B 起：媒體 B／地區 C／…／定價 H／專案執行價 I；資料列 12、13，小計 14
    assert ws["B12"].value == '萬家福-15"量販店' and ws["B13"].value == '樂家康-15"超市'
    assert ws["H12"].value == 672000 and ws["H13"].value == 1152000 and ws["H14"].value == 1824000
    assert ws["I12"].value == 100000 and ws["I13"].value == "計於萬家福" and ws["I14"].value == 100000
    merged = {str(r) for r in ws.merged_cells.ranges}
    assert "C12:C13" in merged          # 地區「全台」合併
    assert "I12:I13" not in merged      # 專案執行價逐列


def test_ddrive_html_preview():
    m = sm.build_model("ag_ddrive_wjf", 100000, START, END)
    html = shtml.render_html(m)[0][1]
    assert "Total Gross Cost" in html and "計於萬家福" in html
