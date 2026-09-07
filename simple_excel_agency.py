# -*- coding: utf-8 -*-
"""
簡易模式 v2 代理商 Excel 版型（由 simple_excel.render 呼叫）

  版型 B：2008 傳媒（組合④⑤）—— render_2008（§6）
  版型 C：凱絡（組合⑥⑦）      —— render_carat（§7）

結構、抬頭、表頭、逐日排檔、回饋列、合計、費用、備註對齊 0902 範本；
只畫走期內日期（範本殘留整月不模仿）；內部實作價不寫入。
"""
from datetime import datetime

from openpyxl.styles import Alignment

import simple_config as sc
import agency_cue as ac
from simple_excel import _set, _bd, _merge, _col

NF_ACCT_D = sc.NF_ACCT_DOLLAR      # 會計 $ 格式
NF_CARAT = r'_-"$"* #,##0_-;\-"$"* #,##0_-;_-"$"* "-"??_-;_-@_-'
_WD = "一二三四五六日"
_WD_EN = ["M", "T", "W", "T", "F", "S", "S"]
_MON_EN = ["", "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
           "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


# =============================================================================
# 版型 B：2008 傳媒（§6）
# =============================================================================
def render_2008(wb, model, formulas):
    first = True
    for sheet in model.sheets:
        ws = wb.active if (first and wb.active.title == "Sheet") else wb.create_sheet(sheet.title)
        if first and ws.title == "Sheet":
            ws.title = sheet.title
        first = False
        _sheet_2008(ws, model, sheet, formulas)


def _sheet_2008(ws, model, sheet, formulas):
    days = sheet.days
    nd = len(days)
    C_D0 = 9                 # 第一個日期欄 = I
    C_DL = 8 + nd            # 最後日期欄
    budget = sheet.budget
    is_wjf = model.combo_key.endswith("wjf")

    # 欄寬（§6）
    for letter, w in dict(A=43.9, B=22.0, C=38.8, D=25.8, E=23.1, F=22.6,
                          G=30.6, H=26.6).items():
        ws.column_dimensions[letter].width = w
    for c in range(C_D0, C_DL + 1):
        ws.column_dimensions[_col(c)].width = 10.4

    ws.sheet_view.showGridLines = False
    ws.sheet_view.zoomScale = 40
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = 9   # A4
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_margins.left = ws.page_margins.right = 0.31
    ws.page_margins.top = ws.page_margins.bottom = 0.75

    # 抬頭 A1..A6 / 值在 C:H
    heads = ["Client", "Media Agency", "Advertising Agency", "Product", "Campaign", "Period"]
    vals = [model.client, sc.COMPANY_2008, "", model.product, model.campaign,
            f"{model.start.strftime('%Y.%m.%d')}-{model.end.strftime('%Y.%m.%d')}"]
    for i, (h, v) in enumerate(zip(heads, vals)):
        r = i + 1
        _set(ws, r, 1, h, size=24, bold=True, halign=None)
        _set(ws, r, 3, v, size=24, bold=True, halign="left")   # 範本值不合併，僅置於 C

    # 表頭 8:10
    hdr = ["媒體型態", "地區", "播出時段", "定價", "單位", "次數", "合計", "素材\n提供時間"]
    for c, text in enumerate(hdr, start=1):
        _merge(ws, 8, c, 10, c)
        _set(ws, 8, c, text, size=22, wrap=(c in (7, 8)),
             border=_bd(t="double", b="double", l="double" if c == 1 else "thin", r="thin"))
    _merge(ws, 7, 4, 7, 7)
    # 日期區：月/日/星期
    for i, d in enumerate(days):
        c = C_D0 + i
        if d.month_label:
            _set(ws, 8, c, _MON_EN[d.date.month], size=22, bold=True, nf="0_ ",
                 border=_bd(t="double"))
        _set(ws, 9, c, d.date.day, size=20, bold=True, nf=r"0_);[Red]\(0\)",
             border=_bd(b="hair"))
        _set(ws, 10, c, _WD[d.date.weekday()], size=20, bold=True,
             fill=sc.COLOR_WEEKEND if d.weekend else None, border=_bd(t="hair", b="double"))

    blk = sheet.blocks[0]
    r0 = 11
    if is_wjf:
        r_tot = _rows_2008_wjf(ws, blk, r0, nd, C_D0, C_DL, budget, formulas)
    else:
        r_tot = _rows_2008_family(ws, blk, r0, nd, C_D0, C_DL, budget, formulas)

    # 費用區（§4.8）
    f = sheet.fees
    r_fee = r_tot + 3
    fee_rows = [("Budget (net)：", budget), ("AC %：", f["ac"]),
                ("5% Tax ：", f["tax"]), ("TOTAL ：", f["total"])]
    for i, (lab, val) in enumerate(fee_rows):
        r = r_fee + i
        _set(ws, r, 6, lab, size=24, bold=True, halign="right",
             border=_bd(t="thin", b="thin"))
        _set(ws, r, 7, val, size=24, bold=True, nf=NF_ACCT_D,
             border=_bd(t="thin", b="thin"))

    # 備註（§4.8）
    remarks = [t for t, _ in model.remarks]
    r_rem = r_fee + 5
    for i, txt in enumerate(remarks):
        _set(ws, r_rem + i, 1, txt, size=24, bold=True, halign="left")

    # 列高
    for r in range(1, 8):
        ws.row_dimensions[r].height = 39.95
    for r in (8, 9, 10):
        ws.row_dimensions[r].height = 41.7
    ws.row_dimensions[r0].height = 105.6
    for r in range(r0 + 1, r_tot):
        ws.row_dimensions[r].height = 88.7
    ws.row_dimensions[r_tot].height = 80.1
    for r in range(r_fee, r_fee + 4):
        ws.row_dimensions[r].height = 60.0
    for r in range(r_rem, r_rem + len(remarks)):
        ws.row_dimensions[r].height = 55.7

    ws.print_area = f"A1:{_col(C_DL)}{r_rem + len(remarks) - 1}"


def _rows_2008_family(ws, blk, r0, nd, C_D0, C_DL, budget, formulas):
    rows = blk.rows
    main = rows[0]
    bonus = [r for r in rows if r.kind == "bonus"]
    r_last_data = r0 + len(rows) - 1
    r_tot = r_last_data + 1
    fam_label, fam_region, fam_daypart = ac.AGENCY_LABELS["2008傳媒"]["family"]

    _merge(ws, r0, 1, r_tot, 1)
    _set(ws, r0, 1, fam_label, size=22, wrap=True, border=_bd(l="double"))
    _merge(ws, r0, 2, r_last_data, 2)
    _set(ws, r0, 2, fam_region, size=22)
    _merge(ws, r0, 3, r_last_data, 3)
    _set(ws, r0, 3, fam_daypart, size=22, wrap=True)
    _merge(ws, r0, 5, r_last_data, 5)
    _set(ws, r0, 5, f"{main.seconds}秒", size=22, color=sc.COLOR_RED)
    _merge(ws, r0, 8, r_last_data, 8)
    _set(ws, r0, 8, main.material, size=22, nf="@", wrap=True)

    # 主列
    _drow_2008_main(ws, r0, main, nd, C_D0, budget, formulas)
    # 回饋列
    for i, b in enumerate(bonus):
        r = r0 + 1 + i
        _set(ws, r, 4, f"={b.list_per}*F{r}" if formulas else b.list_total,
             size=22, nf=NF_ACCT_D)
        _set(ws, r, 6, b.spots, size=22, nf="0_ ")
        _set(ws, r, 7, sc.TXT_REBATE, size=22, color=sc.COLOR_RED, nf=NF_ACCT_D, wrap=True)
        _merge(ws, r, C_D0, r, C_DL)
        _set(ws, r, C_D0, f"{b.spots}(走期內執行完畢)", size=22)
    _totrow_2008(ws, r_tot, r0, r_last_data, nd, C_D0, budget, formulas)
    return r_tot


def _rows_2008_wjf(ws, blk, r0, nd, C_D0, C_DL, budget, formulas):
    rows = blk.rows       # mag, super, bonus_mag, bonus_super
    mag, sup = rows[0], rows[1]
    bm = next(r for r in rows if r.kind == "bonus")
    bs = next(r for r in rows if r.kind == "super_bonus")
    r_last_data = r0 + 3
    r_tot = r_last_data + 1
    mag_l = ac.AGENCY_LABELS["2008傳媒"]["mag"][0]
    sup_l = ac.AGENCY_LABELS["2008傳媒"]["super"][0]

    # 量販主列
    _set(ws, r0, 1, mag_l, size=22, wrap=True, border=_bd(l="double"))
    _merge(ws, r0, 2, r_last_data, 2)
    _set(ws, r0, 2, "全省", size=22)
    _set(ws, r0, 3, mag.daypart, size=22)
    _drow_2008_main(ws, r0, mag, nd, C_D0, budget, formulas)
    _merge(ws, r0, 5, r_last_data, 5)
    _set(ws, r0, 5, f"{mag.seconds}秒", size=22, color=sc.COLOR_RED)
    _merge(ws, r0, 7, r0 + 1, 7)   # G 量販+超市合併 = 預算
    _set(ws, r0, 7, budget, size=22, nf=NF_ACCT_D, wrap=True)
    _merge(ws, r0, 8, r_last_data, 8)
    _set(ws, r0, 8, mag.material, size=22, nf="@", wrap=True)
    # 超市列
    _set(ws, r0 + 1, 1, sup_l, size=22, wrap=True, border=_bd(l="double"))
    _set(ws, r0 + 1, 3, sup.daypart, size=22)
    _set(ws, r0 + 1, 4, sc.TXT_2008_ON_MAG, size=22)
    _schedule_2008(ws, r0 + 1, sup, nd, C_D0)
    _set(ws, r0 + 1, 6, f"=SUM({_col(C_D0)}{r0+1}:{_col(C_D0+nd-1)}{r0+1})"
         if formulas else sup.spots, size=22, nf="0_ ")
    # 回饋量販列
    r = r0 + 2
    _set(ws, r, 1, mag_l, size=22, wrap=True, border=_bd(l="double"))
    _set(ws, r, 3, mag.daypart, size=22)
    _set(ws, r, 4, f"={bm.list_per}*F{r}" if formulas else bm.list_total, size=22, nf=NF_ACCT_D)
    _set(ws, r, 6, bm.spots, size=22, nf="0_ ")
    _merge(ws, r, 7, r + 1, 7)
    _set(ws, r, 7, sc.TXT_REBATE_SHORT, size=22, color=sc.COLOR_RED, wrap=True)
    _merge(ws, r, C_D0, r, C_DL)
    _set(ws, r, C_D0, f"{bm.spots}(走期內執行完畢)", size=22)
    # 回饋超市列
    r = r0 + 3
    _set(ws, r, 1, sup_l, size=22, wrap=True, border=_bd(l="double"))
    _set(ws, r, 3, sup.daypart, size=22)
    _set(ws, r, 4, sc.TXT_2008_ON_MAG, size=22)
    _merge(ws, r, C_D0, r, C_DL)
    _set(ws, r, C_D0, f"{bs.spots}(走期內執行完畢)", size=22)
    _totrow_2008(ws, r_tot, r0, r_last_data, nd, C_D0, budget, formulas, wjf=True)
    return r_tot


def _drow_2008_main(ws, r, row, nd, C_D0, budget, formulas):
    _set(ws, r, 4, f"={row.list_per}*F{r}" if formulas else row.list_total,
         size=22, nf=NF_ACCT_D)
    _set(ws, r, 6, f"=SUM({_col(C_D0)}{r}:{_col(C_D0+nd-1)}{r})" if formulas else row.spots,
         size=22, nf="0_ ")
    _set(ws, r, 7, budget, size=22, nf=NF_ACCT_D, wrap=True)
    _schedule_2008(ws, r, row, nd, C_D0)


def _schedule_2008(ws, r, row, nd, C_D0):
    for i in range(nd):
        _set(ws, r, C_D0 + i, row.schedule[i], size=22, nf="0_ ")


def _totrow_2008(ws, r_tot, r0, r_last, nd, C_D0, budget, formulas, wjf=False):
    _merge(ws, r_tot, 2, r_tot, 3)
    _set(ws, r_tot, 2, "合計", size=22, wrap=True, border=_bd(t="thin", b="double"))
    _set(ws, r_tot, 4, f"=SUM(D{r0}:D{r_last})" if formulas else "", size=22, nf=NF_ACCT_D,
         border=_bd(t="thin", b="double"))
    _set(ws, r_tot, 6, f"=SUM(F{r0}:F{r_last})" if formulas else "", size=22,
         nf="#,##0_);(#,##0)", border=_bd(t="thin", b="double"))
    _set(ws, r_tot, 7, budget, size=22, nf=NF_ACCT_D, border=_bd(t="thin", b="double"))
    for i in range(nd):
        c = C_D0 + i
        _set(ws, r_tot, c, f"=SUM({_col(c)}{r0}:{_col(c)}{r_last})" if formulas else "",
             size=22, bold=True, nf=sc.NF_MONEY, border=_bd(t="thin", b="double"))


# =============================================================================
# 版型 C：凱絡（§7）
# =============================================================================
def render_carat(wb, model, formulas):
    first = True
    for sheet in model.sheets:
        ws = wb.active if (first and wb.active.title == "Sheet") else wb.create_sheet(sheet.title)
        if first and ws.title == "Sheet":
            ws.title = sheet.title
        first = False
        _sheet_carat(ws, model, sheet, formulas)


def _sheet_carat(ws, model, sheet, formulas):
    days = sheet.days
    nd = len(days)
    C_D0 = 11                # 第一個日期欄 = K
    C_DL = 10 + nd
    budget = sheet.budget
    is_wjf = model.combo_key.endswith("wjf")

    for letter, w in dict(A=21.5, B=20.3, C=15.3, D=9.5, E=11.3, F=11.5, G=11.5,
                          H=10.4, I=14.5, J=14.1).items():
        ws.column_dimensions[letter].width = w
    for c in range(C_D0, C_DL + 1):
        ws.column_dimensions[_col(c)].width = 4.8

    ws.sheet_view.showGridLines = False
    ws.sheet_view.zoomScale = 60
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = 9
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_options.horizontalCentered = True
    ws.page_margins.left = ws.page_margins.right = 0.0
    ws.page_margins.top = 0.59
    ws.page_margins.bottom = 0.04

    _set(ws, 1, 1, "凱絡媒體服務(股)公司廣播媒體排期表", size=16, bold=True, halign=None, valign=None)
    _set(ws, 4, 1, f"{model.start.year}年{model.start.month}月", size=14, halign=None, valign=None)
    _set(ws, 2, 9, "客   戶：", size=14, halign=None, valign=None)
    _set(ws, 2, 10, model.client, size=14, halign=None, valign=None)
    _set(ws, 3, 9, "產   品：", size=14, halign=None, valign=None)
    _set(ws, 3, 10, model.product, size=14, halign=None, valign=None)
    _set(ws, 4, 9, "日   期：", size=14, halign=None, valign=None)
    _set(ws, 4, 10, model.made_date.strftime("%Y/%m/%d"), size=14, halign=None, valign=None)

    # 表頭 5:7
    hdr = ["媒體別", "地區", "時段", "素材", "定價\n(檔/Net)", "市場價\n(檔/Net)",
           "統一價\n(檔/Net)", "檔數", "總價", "專案價\n(Net)"]
    for c, text in enumerate(hdr, start=1):
        _merge(ws, 5, c, 7, c)
        _set(ws, 5, c, text, size=12, bold=True, wrap=True,
             border=_bd(t="medium", b="medium", l="medium" if c == 1 else "thin",
                        r="medium" if c == 10 else "thin"))
    for i, d in enumerate(days):
        c = C_D0 + i
        if d.month_label:
            _set(ws, 5, c, _MON_EN[d.date.month][:1] + _MON_EN[d.date.month][1:].lower(),
                 size=12, halign="left", border=_bd(t="medium"))
        _set(ws, 6, c, d.date.day, size=12, nf=sc.NF_MONEY,
             fill=sc.COLOR_WEEKEND if d.weekend else None)
        _set(ws, 7, c, _WD_EN[d.date.weekday()], size=12,
             fill=sc.COLOR_WEEKEND if d.weekend else None)

    blk = sheet.blocks[0]
    rows = blk.rows
    r0 = 8
    r_last = r0 + len(rows) - 1

    if is_wjf:
        mag, sup = rows[0], rows[1]
        _merge(ws, r0, 1, r_last, 1)
        _set(ws, r0, 1, ac.AGENCY_LABELS["凱絡"]["mag"][0], size=12, wrap=True,
             border=_bd(t="thin", b="medium", l="medium", r="thin"))
        _set(ws, r0, 2, "萬家福(量販)", size=12)
        _set(ws, r0 + 1, 2, "樂家康(超市)", size=12)
        _set(ws, r0, 3, "0900-2300 ", size=12)
        _set(ws, r0 + 1, 3, "0000-2400 ", size=12)
    else:
        _merge(ws, r0, 1, r_last, 1)
        _set(ws, r0, 1, ac.AGENCY_LABELS["凱絡"]["family"][0], size=12, wrap=True,
             border=_bd(t="thin", b="medium", l="medium", r="thin"))
        _merge(ws, r0, 2, r_last, 2)
        _set(ws, r0, 2, "全台\n全家便利商店", size=12, wrap=True)
        _merge(ws, r0, 3, r_last, 3)
        _set(ws, r0, 3, "0700-2300", size=12, wrap=True)

    for i, row in enumerate(rows):
        r = r0 + i
        _set(ws, r, 4, f'{row.seconds}"CM', size=12, nf="@")
        _set(ws, r, 5, row.list_per, size=12, nf=NF_CARAT)
        _set(ws, r, 6, f"=E{r}*0.8" if formulas else row.market_per, size=12, nf=NF_CARAT)
        _set(ws, r, 7, f"=E{r}*0.75" if formulas else row.uni_per, size=12, nf=NF_CARAT)
        _set(ws, r, 8, f"=SUM({_col(C_D0)}{r}:{_col(C_DL)}{r})" if formulas else row.spots,
             size=12, nf=r"0_);[Red]\(0\)")
        _set(ws, r, 9, f"=G{r}*H{r}" if formulas else row.uni_total, size=12, nf=NF_CARAT)
        if row.schedule:
            for j in range(nd):
                _set(ws, r, C_D0 + j, row.schedule[j], size=12, nf="0_ ")

    # 專案價 J
    _set(ws, r0, 10, budget, size=12, bold=True, nf=NF_CARAT,
         border=_bd(t="thin", r="medium"))
    if is_wjf:
        _set(ws, r0 + 1, 10, sc.TXT_CARAT_ON_MAG, size=12, border=_bd(r="medium"))
    elif len(rows) > 1:
        _merge(ws, r0 + 1, 10, r_last, 10)
        _set(ws, r0 + 1, 10, sc.TXT_REBATE, size=12, color=sc.COLOR_BLUE,
             border=_bd(r="medium"))

    # 媒體/優惠總價值 + 費用 + 備註
    r_val = r_last + 2
    f = sheet.fees
    _set(ws, r_val, 1, "媒體總價值(NET)", size=12, bold=True, border=_bd(t="medium", l="medium"))
    _set(ws, r_val, 2, f["media_value"], size=12, nf=sc.FMT_MONEY if False else "#,##0",
         border=_bd(t="medium"))
    _set(ws, r_val + 1, 1, "優惠總價值(NET)", size=12, bold=True, border=_bd(b="medium", l="medium"))
    _set(ws, r_val + 1, 2, f["discount_value"], size=12, nf="#,##0", border=_bd(b="medium"))

    fee_rows = [("Sub-Total", budget), ("A.C     3%", "-"),
                ("VAT    5%", f["vat"]), ("Grand-Total", f["grand"])]
    for i, (lab, val) in enumerate(fee_rows):
        r = r_val + i
        _set(ws, r, 9, lab, size=12, halign="right")
        _set(ws, r, 10, val, size=12, nf="#,##0")

    r_rem = r_val + 5
    remarks = [t for t, _ in model.remarks]
    _merge(ws, r_rem, 1, r_rem + max(len(remarks) - 1, 0), 1)
    _set(ws, r_rem, 1, "備     註", size=12, bold=True, valign="top",
         border=_bd(t="medium", b="medium", l="medium", r="medium"))
    for i, (txt, red) in enumerate(model.remarks):
        _set(ws, r_rem + i, 2, txt, size=11, halign="left",
             color=sc.COLOR_RED if red else None)

    ws.print_area = f"A1:{_col(C_DL)}{r_rem + len(remarks)}"
