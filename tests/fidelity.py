# -*- coding: utf-8 -*-
"""
範本 fidelity 比對工具（§10.2）—— 供 test_simple_excel 使用。

比對「我方輸出 sheet」vs「cueexample 範本 sheet」，回傳差異清單。
等價正規化（視覺無差異者視為相同）：
  - 字色：theme1 / 純黑 / 無 → 一律「預設黑」
  - 底色：theme0 / 純白 / 無 → 一律「無底色」（只保留有意義填色，如六日 FFFF99）
  - 數字格式：去除引號逸出差異（"店" == ""店""）；文字型儲存格不比格式
  - 文字值：忽略空白差異（範本常有多餘換行/尾空白）
數字/公式儲存格只比「有無值 + 格式」，不比數值（範本檔次為人工挑選）。
內部欄（檔次欄 V 右側）不比對。
"""
import re
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter, column_index_from_string


def _fontcolor(c):
    if c is None:
        return "BLACK"
    rgb = getattr(c, "rgb", None)
    if isinstance(rgb, str) and rgb not in ("00000000", "FF000000"):
        return rgb
    t = getattr(c, "theme", None)
    if t == 1:
        return "BLACK"
    return f"theme{t}" if t is not None else "BLACK"


def _fillc(cell):
    f = cell.fill
    if f is None or f.patternType != "solid":
        return "NONE"
    fg = f.fgColor
    rgb = getattr(fg, "rgb", None)
    if isinstance(rgb, str) and rgb not in ("00000000", "FFFFFFFF"):
        return rgb
    t = getattr(fg, "theme", None)
    if t == 0:
        return "NONE"
    return f"theme{t}" if t is not None else "NONE"


def _bd(cell):
    b = cell.border
    def s(x):
        return x.style if (x and x.style) else "."
    return f"{s(b.top)},{s(b.bottom)},{s(b.left)},{s(b.right)}"


def _norm_nf(s):
    return (s or "General").replace('"', "")


def _norm_ws(v):
    return re.sub(r"\s", "", str(v))


def _attrs(cell):
    a = cell.alignment
    return dict(sz=cell.font.size, bold=bool(cell.font.bold),
                fc=_fontcolor(cell.font.color), bg=_fillc(cell),
                nf=_norm_nf(cell.number_format),
                al=f"{a.horizontal}/{a.vertical}/{'W' if a.wrap_text else '.'}",
                bd=_bd(cell))


def _is_text(v):
    return isinstance(v, str) and not v.startswith("=")


def _find_cv(tw):
    """檔次欄索引（找表頭『檔次』）；找不到用最大欄。"""
    for c in range(1, tw.max_column + 1):
        if tw.cell(row=7, column=c).value == "檔次":
            return c
    return tw.max_column


def compare(tmpl_ws, out_ws, cv=None):
    diffs = []
    tm = {str(r) for r in tmpl_ws.merged_cells.ranges}
    om = {str(r) for r in out_ws.merged_cells.ranges}
    for m in sorted(tm - om):
        diffs.append(f"MERGED-MISSING {m}")
    for m in sorted(om - tm):
        diffs.append(f"MERGED-EXTRA {m}")
    def _range_only(pa):
        # 去掉工作表名前綴（範本 10 秒分頁名尾帶空白），只比列印範圍
        return str(pa).split("!")[-1] if pa else pa
    for attr, tv, ov in [
        ("orientation", tmpl_ws.page_setup.orientation, out_ws.page_setup.orientation),
        ("paper", tmpl_ws.page_setup.paperSize, out_ws.page_setup.paperSize),
        ("print_area", _range_only(tmpl_ws.print_area), _range_only(out_ws.print_area)),
    ]:
        if str(tv) != str(ov):
            diffs.append(f"PRINT-{attr} tmpl={tv} ours={ov}")
    cv = cv or _find_cv(tmpl_ws)
    for letter, dim in tmpl_ws.column_dimensions.items():
        if dim.width and column_index_from_string(letter) <= cv:
            ov = out_ws.column_dimensions[letter].width
            if ov is None or abs(ov - dim.width) > 0.5:
                diffs.append(f"WIDTH {letter} tmpl={dim.width:.1f} ours={ov}")
    for idx, dim in tmpl_ws.row_dimensions.items():
        if dim.height:
            ov = out_ws.row_dimensions[idx].height
            if ov is None or abs(ov - dim.height) > 0.5:
                diffs.append(f"HEIGHT {idx} tmpl={dim.height:.1f} ours={ov}")
    for r in range(1, tmpl_ws.max_row + 1):
        for c in range(1, cv + 1):
            tc = tmpl_ws.cell(row=r, column=c)
            if tc.value is None or tc.value == "":
                continue
            oc = out_ws.cell(row=r, column=c)
            loc = f"{get_column_letter(c)}{r}"
            ta, oa = _attrs(tc), _attrs(oc)
            txt = _is_text(tc.value)
            if txt:
                if _norm_ws(tc.value) != _norm_ws(oc.value):
                    diffs.append(f"VALUE {loc}: tmpl={tc.value!r} ours={oc.value!r}")
            elif oc.value is None or oc.value == "":
                diffs.append(f"EMPTY {loc}: tmpl has {tc.value!r}")
            keys = ("sz", "bold", "fc", "bg", "al", "bd") if txt else \
                   ("sz", "bold", "fc", "bg", "nf", "al", "bd")
            for k in keys:
                if ta[k] != oa[k]:
                    diffs.append(f"{k.upper()} {loc}: tmpl={ta[k]} ours={oa[k]}")
    return diffs


def load(path):
    return load_workbook(path)
