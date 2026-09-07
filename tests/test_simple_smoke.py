# -*- coding: utf-8 -*-
"""
簡易模式 smoke（§10.3）：七組合 × 多預算 × 多走期，全部能產出且結構正確。
"""
import io
from datetime import date, timedelta

import pytest
from openpyxl import load_workbook

import simple_model as sm
import simple_excel as se
import simple_config as sc
from fixtures_simple import sheetdata

BUDGETS = [100000, 125000, 250000, 333000, 1000000]
# (開始日, 天數)：含跨月 28 天（9/21 起）
PERIODS = [(date(2026, 9, 21), 7), (date(2026, 9, 21), 14),
           (date(2026, 9, 21), 28), (date(2026, 9, 21), 56)]
KEYS = sc.SUBSIDIARY_COMBOS + sc.AGENCY_COMBOS


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("budget", BUDGETS)
@pytest.mark.parametrize("start,days", PERIODS)
def test_smoke_all(key, budget, start, days):
    end = start + timedelta(days=days - 1)
    model = sm.build_model(key, budget, start, end, client="客戶", product="產品",
                           campaign="C", data=sheetdata())
    # 分頁數 = 秒數版本數
    assert len(model.sheets) == len(sc.COMBOS[key]["seconds"])

    for formulas in (True, False):
        b = se.render(model, formulas=formulas)
        wb = load_workbook(io.BytesIO(b))
        # 分頁名唯一、≤31 字
        names = wb.sheetnames
        assert len(names) == len(set(names)), f"{key} 分頁名重複"
        for n in names:
            assert len(n) <= 31, f"{key} 分頁名過長: {n}"
        assert len(wb.worksheets) == len(model.sheets)

    # 每張表：日期欄數 = 天數；每列 schedule 長度 = 天數
    for s in model.sheets:
        assert len(s.days) == days
        for blk in s.blocks:
            for r in blk.rows:
                if r.schedule is not None:
                    assert len(r.schedule) == days
                    assert sum(r.schedule) == r.spots     # 排檔加總 = 檔次
                    assert all(isinstance(x, int) for x in r.schedule)


@pytest.mark.parametrize("key", sc.SUBSIDIARY_COMBOS)
@pytest.mark.parametrize("budget", BUDGETS)
def test_smoke_subsidiary_budget_invariants(key, budget):
    model = sm.build_model(key, budget, date(2026, 9, 21), date(2026, 10, 4), data=sheetdata())
    for s in model.sheets:
        assert s.hidden_net_total <= budget + 1e-6
        assert s.hidden_net_total >= 0.99 * budget
        assert s.fees["grand"] == budget + s.fees["prod"] + s.fees["vat"]


FORBIDDEN = ["320000/480", "120000/504", "250000/420", "計價模式", "格蘭英語"]


@pytest.mark.parametrize("key", KEYS)
def test_no_internal_cost_leak(key):
    """客戶 Excel 不得出現內部實作價／計價模式（§1.4 / §12.6）。"""
    from fixtures_simple import sheetdata_template
    start = date(2026, 9, 21)
    model = sm.build_model(key, 250000, start, start + timedelta(days=13),
                           data=sheetdata_template())
    for formulas in (True, False):
        wb = load_workbook(io.BytesIO(se.render(model, formulas=formulas)))
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for c in row:
                    if c.value is None:
                        continue
                    sval = str(c.value)
                    for f in FORBIDDEN:
                        assert f not in sval, f"{key}/{ws.title}/{c.coordinate} 洩漏 {f}"


@pytest.mark.parametrize("key", KEYS)
def test_value_version_all_numbers(key):
    """值版（下載給客戶，開啟即見數字）：不得殘留任何公式，rate/檔次/合計皆為數值。

    公式版在 Excel 受保護檢視/未重算時公式格會空白（rate(Net) 空白 bug 的根因），
    故下載主檔用值版；本測試確保值版沒有公式格。"""
    m = sm.build_model(key, 250000, date(2026, 9, 21), date(2026, 10, 4), data=sheetdata())
    wb = load_workbook(io.BytesIO(se.render(m, formulas=False)))
    for ws in wb.worksheets:
        bad = [c.coordinate for row in ws.iter_rows() for c in row
               if isinstance(c.value, str) and c.value.startswith("=")]
        assert not bad, f"{key}/{ws.title} 值版殘留公式 {bad[:5]}"
    # 子公司：首張表 rate(Net) F9 必為數字且 > 0
    if key.startswith("sub"):
        ws0 = wb.worksheets[0]
        assert isinstance(ws0["F9"].value, (int, float)) and ws0["F9"].value > 0


def test_style_masters_no_values():
    """母版檔只有樣式、無值、無圖片（§7-6）。"""
    import os
    d = os.path.join(os.path.dirname(__file__), "..", "assets", "style_masters")
    for key in ["ag_2008_fam", "ag_2008_wjf", "ag_carat_fam", "ag_carat_wjf"]:
        wb = load_workbook(os.path.join(d, f"{key}.xlsx"))
        for ws in wb.worksheets:
            vals = [c.value for row in ws.iter_rows() for c in row if c.value is not None]
            assert not vals, f"{key} 母版含殘值 {vals[:3]}"
            assert not ws._images, f"{key} 母版含圖片"


def test_smoke_filenames():
    for key in KEYS:
        model = sm.build_model(key, 250000, date(2026, 9, 21), date(2026, 10, 4),
                               client="統一", sales="宜", data=sheetdata())
        assert model.filename.endswith(".xlsx")
        assert "萬專案" in model.filename
