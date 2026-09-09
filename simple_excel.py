# -*- coding: utf-8 -*-
"""
簡易模式 v2 Excel 渲染（CueModel → xlsx bytes）

三種版型：
  A 子公司 Media Schedule（組合①②③）—— _render_subsidiary（§5）
  B 2008 傳媒（組合④⑤）           —— _render_2008（§6）
  C 凱絡（組合⑥⑦）                —— _render_carat（§7）

render(model, formulas=True)：
  formulas=True  下載用（業務改每日檔次，rate/Total 自動更新）
  formulas=False 轉 PDF 用（寫死值，避免 LibreOffice 未重算）

內部成本（實作價/計價模式）絕不寫入（§1.4）。
"""
import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

import simple_config as sc


# =============================================================================
# 樣式小工具
# =============================================================================
def _side(style):
    return Side(style=style) if style else Side(style=None)


def _bd(t=None, b=None, l=None, r=None):
    return Border(top=_side(t), bottom=_side(b), left=_side(l), right=_side(r))


def _fill(color):
    return PatternFill("solid", fgColor=color) if color else PatternFill()


def _set(ws, r, c, value=None, *, size=22, bold=False, color=None, fill=None,
         nf=None, halign="center", valign="center", wrap=False, border=None):
    cell = ws.cell(row=r, column=c)
    if value is not None:
        cell.value = value
    cell.font = Font(name=sc.FONT, size=size, bold=bold,
                     color=color if color else None)
    if fill:
        cell.fill = _fill(fill)
    if nf:
        cell.number_format = nf
    cell.alignment = Alignment(horizontal=halign, vertical=valign, wrap_text=wrap)
    if border:
        cell.border = border
    return cell


def _merge(ws, r1, c1, r2, c2):
    ws.merge_cells(start_row=r1, start_column=c1, end_row=r2, end_column=c2)


_BORDER_RANK = {None: 0, "hair": 1, "dotted": 1, "thin": 2, "mediumDashed": 3,
                "medium": 3, "thick": 4, "double": 5}


def seal_grid(ws, r1, r2, c1, c2):
    """把 [r1..r2]×[c1..c2] 表格區的『每一條共用格線』同時畫在相鄰兩格上（取較粗者），
    合併格內部邊線清除。這樣不論 Excel 怎麼渲染合併格，格線都連續、不會斷。"""
    # 合併格歸屬
    cell2m = {}
    for rng in ws.merged_cells.ranges:
        key = (rng.min_row, rng.min_col, rng.max_row, rng.max_col)
        for rr in range(rng.min_row, rng.max_row + 1):
            for cc in range(rng.min_col, rng.max_col + 1):
                cell2m[(rr, cc)] = key

    def same_merge(p, q):
        return p in cell2m and cell2m.get(p) == cell2m.get(q)

    def stl(side):
        return side.style if (side and side.style) else None

    # 快照「有效四邊」：合併格構成格的『外框側』一律取左上角(anchor)的框，內側視為無。
    # （openpyxl 只在存檔時把 anchor 樣式套到構成格，記憶體中構成格是空的；
    #   故直接以 anchor 推算，才能把邊線正確畫到相鄰的非合併格上。）
    def eff(r, c):
        b = ws.cell(row=r, column=c).border
        own = (stl(b.top), stl(b.bottom), stl(b.left), stl(b.right))
        key = cell2m.get((r, c))
        if not key:
            return own
        mr1, mc1, mr2, mc2 = key
        ab = ws.cell(row=mr1, column=mc1).border
        return (stl(ab.top) if r == mr1 else None,
                stl(ab.bottom) if r == mr2 else None,
                stl(ab.left) if c == mc1 else None,
                stl(ab.right) if c == mc2 else None)

    orig = {(r, c): eff(r, c) for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)}

    def stronger(a, b):
        return a if _BORDER_RANK.get(a, 0) >= _BORDER_RANK.get(b, 0) else b

    def vedge(r, a, bb):        # a,bb 相鄰兩欄的共用垂直邊
        if same_merge((r, a), (r, bb)):
            return None
        return stronger(orig[(r, a)][3], orig[(r, bb)][2])   # a.right vs bb.left

    def hedge(a, bb, c):        # a,bb 相鄰兩列的共用水平邊
        if same_merge((a, c), (bb, c)):
            return None
        return stronger(orig[(a, c)][1], orig[(bb, c)][0])   # a.bottom vs bb.top

    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            t, b, l, rr = orig[(r, c)]
            left = vedge(r, c - 1, c) if c > c1 else l
            right = vedge(r, c, c + 1) if c < c2 else rr
            top = hedge(r - 1, r, c) if r > r1 else t
            bottom = hedge(r, r + 1, c) if r < r2 else b

            def mk(s):
                return Side(style=s) if s else Side(style=None)
            ws.cell(row=r, column=c).border = Border(top=mk(top), bottom=mk(bottom),
                                                     left=mk(left), right=mk(right))


def thicken_hairlines(ws):
    """把 hair(極細)內線升級成 simple_config.INNER_GRID_STYLE。
    預設 INNER_GRID_STYLE="hair" → 不升級（保留範本原樣，客戶 Excel 與老闆範本一致）。
    老闆若要內線粗一號，把常數改 "thin" 即可全升級。
    註：hair 在 PDF「看起來連不起來」的根因是渲染器畫太淡，已在 pdf_render._BORDER_PT 調整。"""
    target = getattr(sc, "INNER_GRID_STYLE", "hair")
    if target == "hair":
        return
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
        for cell in row:
            b = cell.border
            if "hair" not in (getattr(b.top, "style", None), getattr(b.bottom, "style", None),
                              getattr(b.left, "style", None), getattr(b.right, "style", None)):
                continue

            def _fix(side):
                if side is not None and side.style == "hair":
                    return Side(style=target, color=side.color)
                return side
            cell.border = Border(top=_fix(b.top), bottom=_fix(b.bottom),
                                 left=_fix(b.left), right=_fix(b.right))


def _col(idx):
    return get_column_letter(idx)


# =============================================================================
# 版型 A：子公司 Media Schedule（§5）
# =============================================================================
def _render_subsidiary(wb, model, formulas):
    for si, sheet in enumerate(model.sheets):
        title = sheet.title
        ws = wb.create_sheet(title) if (si or wb.active.title != "Sheet") else wb.active
        if ws.title == "Sheet":
            ws.title = title
        _subsidiary_sheet(ws, model, sheet, formulas)


def _subsidiary_sheet(ws, model, sheet, formulas):
    days = sheet.days
    nd = len(days)
    C_H = 8                 # 第一個日期欄 = H
    C_LAST_DAY = 7 + nd     # 最後日期欄
    C_V = 8 + nd            # 檔次欄
    budget = sheet.budget

    # ---- 欄寬（§5.1）----
    ws.column_dimensions["A"].width = 31.2
    ws.column_dimensions["B"].width = 43.9
    ws.column_dimensions["C"].width = 20.9
    ws.column_dimensions["D"].width = 27.8
    ws.column_dimensions["E"].width = 19.3
    ws.column_dimensions["F"].width = 25.9
    ws.column_dimensions["G"].width = 30.5
    for c in range(C_H, C_LAST_DAY + 1):
        ws.column_dimensions[_col(c)].width = 16.4
    ws.column_dimensions[_col(C_V)].width = 14.0

    # ---- 列印設定（§5.1）----
    ws.sheet_view.showGridLines = False
    ws.sheet_view.zoomScale = 40
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = 8   # A3
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.sheet_format.defaultRowHeight = 27.7
    ws.print_options.horizontalCentered = True
    ws.print_options.verticalCentered = True
    ws.page_margins.left = 0.2
    ws.page_margins.right = 0.12
    ws.page_margins.top = 0.2
    ws.page_margins.bottom = 0.04
    ws.print_title_rows = "6:8"
    ws.oddFooter.left.text = "&F  &A"
    ws.oddFooter.right.text = "&D  &T"

    total_data = sum(len(b.rows) for b in sheet.blocks)
    r_first = 9
    r_last = r_first + total_data - 1
    r_total = r_last + 1
    r_prod = r_total + 1
    r_vat = r_prod + 1
    r_grand = r_vat + 1
    r_remark_hd = r_grand + 1
    r_remark0 = r_remark_hd + 1
    r_sign0 = r_remark0 + 6 + 1   # 六行備註 + 一空列
    r_end = r_sign0 + 2

    ws.print_area = f"A1:{_col(C_V)}{r_end}"

    # ---- 列高（§5.1）----
    hset = {1: 107.1, 2: 47.35, 3: 49.45, 4: 49.45, 5: 49.45, 6: 49.45,
            7: 47.0, 8: 47.0, r_total: 52.0, r_prod: 43.7, r_vat: 43.7,
            r_grand: 43.7, r_remark_hd: 46.35}
    for r in range(r_first, r_total):
        hset[r] = 54.0
    for r in range(r_remark0, r_remark0 + 6):
        hset[r] = 41.45
    hset[r_remark0 + 6] = 11.7           # 空白間隔列
    for r in range(r_sign0, r_sign0 + 3):
        hset[r] = 41.45
    for r, h in hset.items():
        ws.row_dimensions[r].height = h

    # ---- 抬頭（§5.2）----
    _merge(ws, 1, 1, 1, C_V)
    _set(ws, 1, 1, "Media Schedule", size=48, bold=True)
    # 第 2 列底線 medium（A..U，V 除外；V3 上緣 medium，對齊範本 §1.6）
    for c in range(1, C_V):
        _set(ws, 2, c, border=_bd(b="medium"))
    _set(ws, 3, C_V, border=_bd(t="medium"))
    _set(ws, 3, 1, "客戶名稱：", size=26, bold=True, halign="left")
    _set(ws, 3, 2, model.client or "", size=26, bold=True, halign="left")
    _set(ws, 4, 1, "Product：", size=26, bold=True, halign="left")
    prod = f"{model.product} {sheet.seconds}秒".strip() if model.product else f"{sheet.seconds}秒"
    _set(ws, 4, 2, prod, size=26, bold=True, halign=None)   # 範本 Product 值用預設對齊
    _set(ws, 5, 1, "Period : ", size=26, bold=True, halign="left")
    _set(ws, 5, 2, f"{model.start.strftime('%Y. %m. %d')} - {model.end.strftime('%Y. %m. %d')}",
         size=26, bold=True, halign="left")
    _set(ws, 6, 1, "Medium : ", size=26, bold=True, halign="left")
    _set(ws, 6, 2, model.medium_label, size=26, bold=True, halign="left")
    _merge(ws, 4, C_H, 4, C_LAST_DAY)   # 範本 H4:U4 合併（空白）
    # 月份標籤（每月第一天的欄位，第 6 列）
    for i, d in enumerate(days):
        if d.month_label:
            _set(ws, 6, C_H + i, d.month_label, size=20, bold=True)

    # ---- 表頭（第 7、8 列，§5.3）----
    hdr = [("Station", 1), ("Location", 2), ("Program", 3), ("Day-part", 4),
           ("Size", 5), ("rate   (Net)", 6), ("Package-cost\n(Net)", 7)]
    for text, c in hdr:
        _merge(ws, 7, c, 8, c)
        bold = (c == 7)
        _set(ws, 7, c, text, size=22, bold=bold, wrap=(c in (3, 6, 7)),
             border=_hdr_border(c, C_V))
    _merge(ws, 7, C_V, 8, C_V)
    _set(ws, 7, C_V, "檔次", size=22, border=_bd(t="medium", b="medium", l="medium", r="medium"))
    # 日期 + 星期
    for i, d in enumerate(days):
        c = C_H + i
        _set(ws, 7, c, datetime(d.date.year, d.date.month, d.date.day), size=22,
             bold=True, nf=sc.NF_DAY, border=_bd(t="medium", b="hair", l="hair", r="hair"))
        wd = "一二三四五六日"[d.date.weekday()]
        _set(ws, 8, c, wd, size=22, bold=True, nf=sc.NF_WEEKDAY,
             fill=sc.COLOR_WEEKEND if d.weekend else None,
             border=_bd(t="hair", b="medium", l="hair", r="hair"))

    # ---- 資料列（§5.4）----
    # G（Package-cost）整段合併 = 預算；上緣隨第一區塊（家樂福 medium，其餘 none）
    _merge(ws, r_first, 7, r_last, 7)
    g_top = "medium" if sheet.blocks[0].platform == "家樂福" else None
    _set(ws, r_first, 7, budget, size=22, bold=True, nf=sc.NF_MONEY, wrap=True,
         border=_bd(t=g_top, b="medium", l="thin", r="medium"))

    row = r_first
    for bi, blk in enumerate(sheet.blocks):
        b_first = row
        b_last = row + len(blk.rows) - 1
        # Station 合併（A）
        _merge(ws, b_first, 1, b_last, 1)
        # 家樂福 2 列小區塊：上緣 medium、下緣 thin（對齊範本手繪風格）；6 區塊上緣 thin
        # 非家樂福區塊：Station 合併格下緣 medium，讓區塊底線與 B/C/F 一致連續粗線（範本 A/D/E 誤用 hair）
        is_cf = blk.platform == "家樂福"
        _set(ws, b_first, 1, sc.STATION_TEXT.get(blk.platform, ""), size=22, wrap=True,
             border=_bd(t="medium" if is_cf else "thin", b="thin" if is_cf else "medium",
                        l="medium", r="thin"))
        # 家樂福 block：D 不合併（量販/超市各自），E 合併
        if not is_cf:
            _merge(ws, b_first, 4, b_last, 4)   # Day-part
        _merge(ws, b_first, 5, b_last, 5)       # Size
        _set(ws, b_first, 5, f"{blk.rows[0].seconds}秒", size=22, nf=sc.NF_SEC)

        for ri, r in enumerate(blk.rows):
            _subsidiary_data_row(ws, r, row, ri, b_first, b_last, blk, C_H, nd, C_V,
                                 formulas, is_cf)
            row += 1

    # ---- Total 與費用區（§5.5）----
    _subsidiary_totals(ws, sheet, r_first, r_last, r_total, r_prod, r_vat, r_grand,
                       C_H, nd, C_V, budget, formulas)

    # ---- 備註與簽章（§5.6）----
    _subsidiary_remarks(ws, model, r_remark_hd, r_remark0, r_sign0, formulas, C_V)

    # ---- 內部 hair 格線升級 thin + 格線密封（相鄰兩格共畫、合併格內邊清除）----
    thicken_hairlines(ws)
    seal_grid(ws, 7, r_grand, 1, C_V)


def _hdr_border(c, C_V):
    if c == 1:
        return _bd(t="medium", b="hair", l="medium", r="thin")
    if c == 7:
        return _bd(t="medium", b="hair", r="medium")
    return _bd(t="medium", b="hair", l="thin", r="thin")


def _subsidiary_data_row(ws, r, row, ri, b_first, b_last, blk, C_H, nd, C_V,
                         formulas, is_cf):
    vcol = _col(C_V)
    is_block_last = (row == b_last)
    # 家樂福 2 列小區塊下緣用 hair（不封 medium）；6 區塊末列封 medium（對齊範本）
    if is_block_last:
        hb = "hair" if is_cf else "medium"
    else:
        hb = "hair"
    tb = ("medium" if is_cf else "thin") if ri == 0 else "hair"

    # B Location
    _set(ws, row, 2, r.location, size=22, wrap=True,
         border=_bd(t=tb, b=hb, l="thin", r="thin"))
    # C Program（店數，數字）
    _set(ws, row, 3, r.stores, size=22, wrap=True, nf=sc.NF_STORE,
         border=_bd(t=tb, b=hb, l="thin", r="thin"))
    # D Day-part（家樂福才逐列寫；非家樂福由合併格於 first row 呈現）
    if is_cf:
        _set(ws, row, 4, r.daypart, size=22, nf="@",
             border=_bd(t=tb, b=hb, l="thin", r="thin"))
    elif ri == 0:
        # 非家樂福 Day-part 合併格下緣 medium（與 Station/B/C/F 一致連續粗線）
        _set(ws, b_first, 4, r.daypart, size=22, nf="@",
             border=_bd(t=tb, b="medium", l="thin", r="thin"))
    # E Size 邊框（合併格）；非家樂福下緣 medium，家樂福維持 hair
    if ri == 0:
        e_bot = "hair" if is_cf else "medium"
        ws.cell(row=b_first, column=5).border = _bd(t=tb, b=e_bot, l="thin", r="thin")
    # F rate(Net)
    if r.rate_text is not None:
        _set(ws, row, 6, r.rate_text, size=22, wrap=True,
             border=_bd(t=tb, b=hb, l="thin", r="thin"))
    else:
        lst, std, fac = r.rate_num
        if formulas:
            val = f"={lst}/{std}*{vcol}{row}*{fac:g}"    # 係數 *0.85 不寫 *0.85… (§1.5)
        else:
            val = round(lst / std * r.spots * fac)       # 值版取整，開啟即見數字（無浮點尾數）
        _set(ws, row, 6, val, size=22, wrap=True, nf=sc.NF_MONEY,
             border=_bd(t=tb, b=hb, l="thin", r="thin"))
    # 每日欄
    for i in range(nd):
        c = C_H + i
        lb = "medium" if c == C_H else None
        if ri == 0 or is_cf:
            val = r.schedule[i]
        else:
            val = f"={_col(c)}{b_first}" if formulas else r.schedule[i]
        _set(ws, row, c, val, size=22, nf="General",
             border=_bd(t=tb, b=hb, l=lb, r="hair"))
    # V 檔次
    if formulas:
        vval = f"=SUM({_col(C_H)}{row}:{_col(7+nd)}{row})"
    else:
        vval = sum(r.schedule)
    _set(ws, row, C_V, vval, size=22, nf=sc.NF_MONEY,
         border=_bd(t=tb, b=hb, l="medium", r="medium"))


def _subsidiary_totals(ws, sheet, r_first, r_last, r_total, r_prod, r_vat, r_grand,
                       C_H, nd, C_V, budget, formulas):
    # A:B 合併空白（Total 列）；左緣 medium（費用區外框起點）
    _merge(ws, r_total, 1, r_total, 2)
    _set(ws, r_total, 1, border=_bd(b="medium", l="medium"))
    _set(ws, r_total, 5, "Total", size=22, border=_bd(b="medium", l="hair", r="hair"))
    # F Total
    if formulas:
        fsum = f"=SUM(F{r_first}:F{r_last})"
    else:
        fsum = sum(round(lst / std * rr.spots * fac)
                   for b in sheet.blocks for rr in b.rows
                   if rr.rate_num for (lst, std, fac) in [rr.rate_num])
    _set(ws, r_total, 6, fsum, size=22, nf=sc.NF_MONEY_TOTAL, wrap=True,
         border=_bd(b="medium", l="hair", r="hair"))
    _set(ws, r_total, 7, budget, size=22, bold=True, nf=sc.NF_MONEY_TOTAL, wrap=True,
         border=_bd(b="medium", l="hair", r="medium"))
    # 每日 Total
    for i in range(nd):
        c = C_H + i
        if formulas:
            v = f"=SUM({_col(c)}{r_first}:{_col(c)}{r_last})"
        else:
            v = sum(rr.schedule[i] for b in sheet.blocks for rr in b.rows if rr.schedule)
        _set(ws, r_total, c, v, size=22, nf=sc.NF_MONEY, wrap=True,
             border=_bd(b="medium", l="hair", r="hair"))
    # V Total
    if formulas:
        vt = f"=SUM({_col(C_V)}{r_first}:{_col(C_V)}{r_last})"
    else:
        vt = sum(rr.spots for b in sheet.blocks for rr in b.rows)
    _set(ws, r_total, C_V, vt, size=22, nf=sc.NF_MONEY, wrap=True,
         border=_bd(b="medium", l="medium", r="medium"))

    # 製作 / VAT / Grand（§5.5）
    _set(ws, r_prod, 6, "製作", size=22, border=_bd(t="medium", l="medium"))
    _set(ws, r_prod, 7, sheet.prod_cost, size=22, bold=True, nf=sc.NF_MONEY_TOTAL,
         wrap=True, border=_bd(l="hair", r="medium"))
    _set(ws, r_vat, 6, "5% VAT", size=22, border=_bd(t="thin", b="thin", l="medium", r="hair"))
    if formulas:
        vat_val = f"=SUM(G{r_total}:G{r_prod})*5%"
    else:
        vat_val = sheet.fees["vat"]
    _set(ws, r_vat, 7, vat_val, size=22, bold=True, nf=sc.NF_MONEY_TOTAL, wrap=True,
         border=_bd(t="thin", b="thin", r="medium"))
    _set(ws, r_grand, 6, "Grand Total", size=22, border=_bd(b="medium", l="medium", r="hair"))
    grand = f"=SUM(G{r_total}:G{r_vat})" if formulas else sheet.fees["grand"]
    _set(ws, r_grand, 7, grand, size=22, bold=True, nf=sc.NF_MONEY,
         border=_bd(b="medium", r="medium"))

    # 費用區外框（§1.1）：左緣 A、右緣 V、Total 列下緣補 C/D、製作列上緣 A..E、Grand 下緣
    _set(ws, r_total, 3, border=_bd(b="medium"))            # C21
    _set(ws, r_total, 4, border=_bd(b="medium", r="hair"))  # D21
    for c in range(1, 6):        # 製作列上緣 A..E（A 另加左緣）
        _set(ws, r_prod, c, border=_bd(t="medium", l="medium") if c == 1 else _bd(t="medium"))
    _set(ws, r_vat, 1, border=_bd(l="medium"))
    for c in range(1, 6):        # A..E 下緣（A 另加左緣）
        _set(ws, r_grand, c, border=_bd(b="medium", l="medium") if c == 1 else _bd(b="medium"))
    for c in range(C_H, C_V):    # H..U 下緣
        _set(ws, r_grand, c, border=_bd(b="medium"))
    _set(ws, r_prod, C_V, border=_bd(r="medium"))
    _set(ws, r_vat, C_V, border=_bd(r="medium"))
    _set(ws, r_grand, C_V, border=_bd(b="medium", r="medium"))


def _subsidiary_remarks(ws, model, r_hd, r0, r_sign, formulas, C_V):
    _set(ws, r_hd, 1, "Remarks：", size=26, bold=True, halign=None)   # 範本用預設對齊
    for i, (txt, red) in enumerate(model.remarks):
        _set(ws, r0 + i, 1, txt, size=26, bold=True,
             color=sc.COLOR_RED if red else None, halign="left")
    # 簽章上方空白列（r_sign-1）A..V 下框線 thin（§1.2）
    for c in range(1, C_V + 1):
        _set(ws, r_sign - 1, c, border=_bd(b="thin"))
    # 簽章三列（§5.6）—— 甲/乙方公司名緊接標籤（併入同一格、左對齊，比照「統一編號：」列，無空格）
    # 甲方（我方）：標籤格 A:C 夠寬，名稱直接接在標籤後
    _merge(ws, r_sign, 1, r_sign, 3)
    _set(ws, r_sign, 1, f"甲       方 ：{model.party_a}" if model.party_a else "甲       方 ：",
         size=26, halign="left", wrap=True)
    # 乙方（客戶）：合併 I:O 成單格，名稱接在標籤後、左對齊；wrap=False 免長名折行觸發 PDF 縮放跑版
    _merge(ws, r_sign, 9, r_sign, 15)
    _set(ws, r_sign, 9, f"乙    方：{model.client}" if model.client else "乙    方：",
         size=26, halign="left", wrap=False, border=_bd(t="thin"))
    _merge(ws, r_sign + 1, 1, r_sign + 1, 3)
    _set(ws, r_sign + 1, 1, f"統一編號：{model.party_a_tax}" if model.party_a_tax else "統一編號：",
         size=26, halign="left", wrap=True)
    _merge(ws, r_sign + 1, 9, r_sign + 1, 14)
    _set(ws, r_sign + 1, 9, f"統一編號：{model.tax_id}" if model.tax_id else "統一編號：",
         size=26, halign="left")
    _merge(ws, r_sign + 2, 1, r_sign + 2, 3)
    _set(ws, r_sign + 2, 1, f"承辦人：{model.sales}" if model.sales else "承辦人：",
         size=26, halign="left", wrap=True)
    _merge(ws, r_sign + 2, 9, r_sign + 2, 14)
    _set(ws, r_sign + 2, 9, "客戶簽章：", size=26, halign="left")


# =============================================================================
# 對外入口
# =============================================================================
def render(model, formulas=True):
    wb = Workbook()
    if model.family == "subsidiary":
        _render_subsidiary(wb, model, formulas)
    elif model.family == "2008":
        from simple_excel_agency import render_2008
        render_2008(wb, model, formulas)
    elif model.family == "carat":
        from simple_excel_agency import render_carat
        render_carat(wb, model, formulas)
    else:
        raise ValueError(model.family)
    # 移除預設空白分頁
    if "Sheet" in wb.sheetnames and len(wb.sheetnames) > 1:
        del wb["Sheet"]
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()
