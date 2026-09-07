# -*- coding: utf-8 -*-
"""
簡易模式 Excel fidelity 測試（§10.2）：七組合逐格對齊 0902 範本。

ALLOWED_DIFF 之外必須零差異。每一條 allowed 都寫明原因與 §規格出處。
數字/公式儲存格只比結構與格式（範本檔次為人工挑選，見 fidelity.py）。
"""
import io
import re
import os
from datetime import date

import pytest
from openpyxl import load_workbook

import simple_model as sm
import simple_excel as se
from fixtures_simple import sheetdata_template
import fidelity

CUE = os.path.join(os.path.dirname(__file__), "..", "cueexample")

# --------------------------------------------------------------------------- #
# 允許差異（每條皆為刻意、依規格；§10.2 / §11）
# --------------------------------------------------------------------------- #
ALLOWED_PATTERNS = [
    # 六日底色：規格 §5.3 要求直接填 FFFF99；範本用條件格式（讀回為無底色）
    (r"^BG [A-Z]+\d+: tmpl=NONE ours=FFFFFF99$", "六日直接填色(§5.3)，範本用條件格式"),
    # 範本錯字，規格 §5.4 要求改正
    (r"^VALUE B\d+: tmpl='中區-中彰投雲'", "範本錯字『中彰投雲』已改正(§5.4)"),
    (r"^VALUE B\d+: tmpl='南區-霊嘉南'", "範本錯字『霊嘉南』已改正(§5.4)"),
    # 含新鮮視時第4條加 mp4（§5.6）；範本未一致套用
    (r"^VALUE A\d+: tmpl='4\.託播方.*mp3\)。' ours='4\.託播方.*mp4\)。'$",
     "含新鮮視補影片素材(§5.6)"),
    # 請款月份、付款日：系統自動填；範本留空白
    (r"^VALUE A\d+: tmpl='5\.雙方同意費用請款月份 : 月", "請款月份自動填(§4.12/§5.6)"),
    (r"^VALUE A\d+: tmpl='6\.付款兌現日期：115\.XX\.XX'", "付款日格式(§4.12)"),
    # 範本表頭 C7 合併格底線 medium（範本瑕疵，合併內不可見）
    (r"^BD C7: ", "範本表頭 C7 合併格底線瑕疵"),
    # 萬家福/樂家康店數：範本存成文字『62店』且用『面』格式；規格 §5.4 改為數字+『店』格式
    (r"^VALUE C\d+: tmpl='\d+店'", "萬家福店數改數字(§5.4)"),
    (r"^NF C\d+: tmpl=#,##0面", "範本萬家福用『面』格式，改『店』(§5.4)"),
    # 2008 全家 30/15 秒 G11 公式抄錯（166,667/333,333）——數字不比，僅結構
    # 2008 萬家福畫整月：我們只畫走期內；以逐 sheet index 對齊，不觸發
]


def _is_allowed(diff):
    return any(re.search(p, diff) for p, _ in ALLOWED_PATTERNS)


def _assert_fidelity(tmpl_path, model, note=""):
    tw = load_workbook(tmpl_path)
    ob = se.render(model, formulas=True)
    ow = load_workbook(io.BytesIO(ob))
    assert len(ow.worksheets) == len(tw.worksheets), \
        f"{note} 分頁數 {len(ow.worksheets)} != 範本 {len(tw.worksheets)}"
    real = []
    for i in range(len(tw.worksheets)):
        for d in fidelity.compare(tw.worksheets[i], ow.worksheets[i]):
            if not _is_allowed(d):
                real.append(f"[sheet{i} {note}] {d}")
    assert not real, "非允許差異：\n" + "\n".join(real)


SUB_CASES = [
    ("sub_qp_fv", "0902  企頻+新鮮視(10.15.20.30秒) 20萬專案-宜.xlsx"),
    ("sub_qp_wjf", "0902  全家+萬家福.樂家康(10.15.20.30秒) 20萬專案-宜.xlsx"),
    ("sub_fv_wjf", "0902  新鮮視+萬家福.樂家康(10.15.20.30秒) 20萬專案-宜.xlsx"),
]


@pytest.mark.parametrize("key,fname", SUB_CASES)
def test_subsidiary_fidelity(key, fname):
    model = sm.build_model(key, 200000, date(2026, 9, 21), date(2026, 10, 4),
                           data=sheetdata_template())
    _assert_fidelity(os.path.join(CUE, fname), model, note=key)
