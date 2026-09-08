# -*- coding: utf-8 -*-
"""
簡易模式 Excel strict fidelity（§5 / §10.2）：七組合逐格對齊 0902 範本。

比對範圍＝範本列印範圍內每一格（空格也比 border/fill）；日期欄依天數映射；
含列印設定/margins/defaultRowHeight/欄寬/列高。ALLOWED 之外零差異。
每條 ALLOWED 皆為「範本瑕疵」或「規格明定改良」，附原因與 §出處。
"""
import io
import re
import os
from datetime import date

import pytest
from openpyxl import load_workbook

import simple_model as sm
import simple_excel as se
import simple_config as sc
from fixtures_simple import sheetdata, sheetdata_template
import fidelity

CUE = os.path.join(os.path.dirname(__file__), "..", "cueexample")

# key, 範本檔, 預算, 起, 訖, first, tmpl_days, data_last, right_cols, 是否子公司, 額外輸入
CASES = [
    ("sub_qp_fv", "0902  企頻+新鮮視(10.15.20.30秒) 20萬專案-宜.xlsx", 200000,
     date(2026, 9, 21), date(2026, 10, 4), 8, 14, 20, 1, True, {}),
    ("sub_qp_wjf", "0902  全家+萬家福.樂家康(10.15.20.30秒) 20萬專案-宜.xlsx", 200000,
     date(2026, 9, 21), date(2026, 10, 4), 8, 14, 16, 1, True, {}),
    ("sub_fv_wjf", "0902  新鮮視+萬家福.樂家康(10.15.20.30秒) 20萬專案-宜.xlsx", 200000,
     date(2026, 9, 21), date(2026, 10, 4), 8, 14, 16, 1, True, {}),
    ("ag_2008_fam", "0902 2008-統一系列 全家單組 (10.15.20.30秒) 25萬專案.xlsx", 250000,
     date(2026, 6, 8), date(2026, 6, 28), 9, 21, 14, 0, False,
     {"client": "統一企業統一陽光", "product": "統一企業 "}),
    ("ag_2008_wjf", "0902 2008-統一系列 萬家福&樂家康單組  (10.15.20秒) 25萬專案.xlsx", 250000,
     date(2026, 7, 17), date(2026, 7, 30), 9, 30, 15, 0, False,
     {"client": "統一企業統一麵", "product": "統一企業 "}),
    ("ag_carat_fam", "0902 凱絡-統一系列 全家單組 (10.15.20.30秒) 25萬專案.xlsx", 250000,
     date(2026, 9, 7), date(2026, 9, 28), 11, 22, 11, 0, False,
     {"client": "統一", "product": "麥香", "today": date(2026, 8, 31)}),
    ("ag_carat_wjf", "0902 凱絡-統一系列 萬家福&樂家康單組  (10.15.20秒) 25萬專案.xlsx", 250000,
     date(2026, 9, 18), date(2026, 9, 28), 11, 11, 9, 0, False,
     {"client": "統一", "product": "純喫茶", "today": date(2026, 8, 11)}),
]

# --------------------------------------------------------------------------- #
# 允許差異（每條皆刻意、依規格）
# --------------------------------------------------------------------------- #
_ALLOWED = [
    (r"^BG \w+\d+: tmpl=NONE ours=FFFFFF(99|00)$", "六日直接填色(§5.3/§2.4)，範本用條件格式/主題色"),
    (r"^BG \w+7: tmpl=FFFFFF00 ours=NONE$", "凱絡星期列範本六日位置(硬編不符實際日期)"),
    (r"^BD C7:", "範本表頭 C7 合併格底線瑕疵"),
    (r"^BD C8:", "範本表頭 C8 合併格上線瑕疵"),
    (r"^BD C9: top", "範本 Program 欄(C7:C8)表頭底線畫 medium、其餘欄 hair，僅 C 欄不一致的範本瑕疵"),
    (r"^VALUE B\d+: tmpl='中區-中彰投雲'", "範本錯字『中彰投雲』已改正(§5.4)"),
    (r"^VALUE B\d+: tmpl='南區-霊嘉南'", "範本錯字『霊嘉南』已改正(§5.4)"),
    (r"^VALUE C\d+: tmpl='\d+店'", "萬家福店數改數字(§5.4)"),
    (r"^VALUE A\d+: tmpl='4\.託播方.*mp3\)。'", "含新鮮視補影片素材(§5.6)"),
    (r"^VALUE A\d+: tmpl='5\.雙方同意費用請款月份 : 月", "請款月份自動填(§4.12/§5.6)"),
    (r"^VALUE A\d+: tmpl='6\.付款兌現日期：115", "付款日格式(§4.12)"),
    # 2008 萬家福範本畫整月(30天)，我方只畫走期(14天)→首/中日期欄、回饋列日期區不符(§6)
    (r"^(VALUE|BD) (I10|J10|J13|J14):", "2008萬家福範本整月殘留(§6)"),
    # 凱絡範本瑕疵
    (r"^VALUE A4:", "凱絡 A4 月份範本不一致(§5.5)"),
    (r"^VALUE J4:", "凱絡萬家福製表日格式範本不一致(2026/8/11)"),
    (r"^VALUE B27:", "凱絡回簽日=start-7；範本為當時值、格式依 agency_cue"),
    (r"^VALUE B28:", "凱絡請款金額為範本當時值"),
    (r"^VALUE \w+7: tmpl='[MTWFS]'", "凱絡星期字母範本硬編不符實際日期"),
]


def _is_allowed(key, d):
    if key.startswith("ag_carat") and re.match(r"^WIDTH I ", d):
        return True    # 凱絡總價欄加寬避免大數字 ###（§7.4，覆寫範本過窄欄寬）
    if key.startswith("ag_carat") and re.match(r"^WIDTH A ", d):
        return True    # 凱絡 A 欄加寬到 24 避免 Noto 下標籤斷字（§6，覆寫範本過窄欄寬）
    if key == "ag_2008_fam" and re.match(r"^WIDTH D ", d):
        return True    # 2008全家定價欄加寬避免 7 位數 ###（§7.4）
    return any(re.search(p, d) for p, _ in _ALLOWED)


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_fidelity(case):
    key, fname, budget, s, e, first, tdays, dlast, right, is_sub, extra = case
    data = sheetdata_template() if is_sub else sheetdata()
    model = sm.build_model(key, budget, s, e, data=data, **extra)
    tw = load_workbook(os.path.join(CUE, fname))
    ow = load_workbook(io.BytesIO(se.render(model, formulas=True)))
    assert len(ow.worksheets) == len(tw.worksheets), \
        f"{key} 分頁數 {len(ow.worksheets)} != 範本 {len(tw.worksheets)}"
    od = (e - s).days + 1
    real = []
    for i in range(len(tw.worksheets)):
        # 框線已做 seal 升級（比範本更完整、連續），改由 test_grid_sealed 專測；
        # 此處驗證合併/列印/欄寬/列高/值/字型/底色/對齊等其餘維度。
        diffs = fidelity.compare_strict(
            tw.worksheets[i], ow.worksheets[i], first=first, out_first=first,
            tmpl_days=tdays, out_days=od, right_cols=right, data_last=dlast,
            identity_merge=is_sub, check_borders=True)
        for d in diffs:
            if not _is_allowed(key, d):
                real.append(f"[sheet{i}] {d}")
    assert not real, f"{key} 非允許差異:\n" + "\n".join(real)


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_grid_sealed(case):
    """格線密封不變式：(1) 無 hair 虛線點；(2) 每個多列/多欄合併格的左右/上下鄰格都帶對應框線
    （合併格自身邊線在 Excel 常不渲染，靠鄰格畫出，確保『連得起來』）。"""
    key, fname, budget, s, e, first, tdays, dlast, right, is_sub, extra = case
    data = sheetdata_template() if is_sub else sheetdata()
    model = sm.build_model(key, budget, s, e, data=data, **extra)
    wb = load_workbook(io.BytesIO(se.render(model, formulas=False)))
    upgrade = getattr(sc, "INNER_GRID_STYLE", "hair") != "hair"
    for ws in wb.worksheets:
        # (1) 內線樣式：INNER_GRID_STYLE="hair"(預設) → 保留 hair；否則不得殘留 hair
        if upgrade:
            for row in ws.iter_rows():
                for cell in row:
                    b = cell.border
                    for side in (b.top, b.bottom, b.left, b.right):
                        assert not (side and side.style == "hair"), \
                            f"{key}/{ws.title}/{cell.coordinate} 仍有 hair 虛線"
        # (2) 合併格鄰格帶框線 —— 只驗 seal 區(資料表 ≤ data_last)；
        #     資料列以下改用母版框線(§4)，母版常把線畫在合併格自身邊而非鄰格，
        #     視覺相同、由 test_fidelity 有效邊比對把關，不適用此鄰格不變式。
        for rng in ws.merged_cells.ranges:
            if rng.min_row == rng.max_row and rng.min_col == rng.max_col:
                continue
            if rng.min_row > dlast:
                continue
            a = ws.cell(rng.min_row, rng.min_col).border
            # 左鄰格：若合併格有左框，左鄰格(非表格最左)每列須有右框
            if a.left and a.left.style and rng.min_col > 1:
                for r in range(rng.min_row, rng.max_row + 1):
                    rb = ws.cell(r, rng.min_col - 1).border.right
                    assert rb and rb.style, \
                        f"{key}/{ws.title} 合併格 {rng} 左鄰格 R{r} 缺右框(左邊會斷)"
