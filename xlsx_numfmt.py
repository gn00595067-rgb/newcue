# -*- coding: utf-8 -*-
"""
Excel 數字格式 → 顯示字串引擎（供純 Python PDF 渲染器使用）。

只需覆蓋 newcue 各建構器實際輸出的格式：
  #,##0 / #,##0.00 / 0 / 0.00 / 0% / #,##0"店" 之類後綴 /
  #,##0_);[Red](#,##0)（千分位、負數紅字括號）/
  會計格式 _("$"* #,##0_);... /
  日期 d dd m mm yyyy m"月"d"日" / 中文星期 [$-404]aaa、aaaa / @（文字）/ General

回傳 (text, is_red)。is_red 供渲染器把負數／[Red] 段落套紅字。
"""
import datetime
import re
from decimal import Decimal, ROUND_HALF_UP

_WD_SHORT = "一二三四五六日"   # Mon..Sun  (Python weekday(): Mon=0)


def _is_datelike(fmt):
    # 去掉引號字面、色碼、locale 後，判斷是否含日期/時間 token
    s = re.sub(r'"[^"]*"', "", fmt)
    s = re.sub(r'\[[^\]]*\]', "", s)
    s = re.sub(r'\\.', "", s)
    return bool(re.search(r'[yYmMdDhHsS]', s)) or "aaa" in fmt


def _excel_serial_to_dt(v):
    # Excel 1900 序列值 → datetime（含 1900 閏年 bug 補償）
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    base = datetime.datetime(1899, 12, 30)
    return base + datetime.timedelta(days=n)


def _fmt_date(dt, fmt):
    """處理日期區段（可能夾雜 "月" 等字面與 [$-404]）。"""
    out = []
    i = 0
    n = len(fmt)
    while i < n:
        ch = fmt[i]
        if ch == '"':
            j = fmt.find('"', i + 1)
            if j == -1:
                j = n
            out.append(fmt[i + 1:j])
            i = j + 1
            continue
        if ch == '\\':
            if i + 1 < n:
                out.append(fmt[i + 1])
            i += 2
            continue
        if ch == '[':
            j = fmt.find(']', i)
            i = (j + 1) if j != -1 else n            # 忽略 locale/顏色碼
            continue
        # aaaa / aaa 星期
        if fmt.startswith("aaaa", i):
            out.append("星期" + _WD_SHORT[dt.weekday()])
            i += 4
            continue
        if fmt.startswith("aaa", i):
            out.append(_WD_SHORT[dt.weekday()])
            i += 3
            continue
        if fmt.startswith("yyyy", i):
            out.append("%04d" % dt.year); i += 4; continue
        if fmt.startswith("yy", i):
            out.append("%02d" % (dt.year % 100)); i += 2; continue
        if fmt.startswith("mmmm", i):
            out.append(dt.strftime("%B")); i += 4; continue
        if fmt.startswith("mmm", i):
            out.append(dt.strftime("%b")); i += 3; continue
        if fmt.startswith("mm", i):
            out.append("%02d" % dt.month); i += 2; continue
        if fmt.startswith("m", i):
            out.append(str(dt.month)); i += 1; continue
        if fmt.startswith("dd", i):
            out.append("%02d" % dt.day); i += 2; continue
        if fmt.startswith("d", i):
            out.append(str(dt.day)); i += 1; continue
        if fmt.startswith("hh", i):
            out.append("%02d" % dt.hour); i += 2; continue
        if fmt.startswith("h", i):
            out.append(str(dt.hour)); i += 1; continue
        if fmt.startswith("ss", i):
            out.append("%02d" % dt.second); i += 2; continue
        if ch in "s":
            out.append(str(dt.second)); i += 1; continue
        if ch in ";":
            break
        out.append(ch)
        i += 1
    return "".join(out)


def _decimals_from(numpat):
    if "." in numpat:
        dec = numpat.split(".", 1)[1]
        return len(re.findall(r"[0#]", dec))
    return 0


def _fmt_number(value, section):
    """把一個數字套用單一數值區段（不含色碼）。回傳字串。"""
    # 百分比
    is_pct = "%" in section
    v = float(value)
    if is_pct:
        v *= 100.0
    thousands = "#,##" in section or "#,#" in section or (
        "," in re.sub(r'"[^"]*"', "", section))
    decimals = _decimals_from(section)
    # 主數字：round-half-up 對齊 Excel（Python 預設 float 格式化是 banker's rounding，
    # 會把 1912.5 進成 1912、Excel 顯示 1913；凱絡統一價 .5 尾數即中招）。
    num = abs(v)
    q = Decimal(1).scaleb(-decimals)   # decimals=0 → 1；=2 → 0.01
    d = Decimal(str(num)).quantize(q, rounding=ROUND_HALF_UP)
    spec = (",.%df" if thousands else ".%df") % decimals
    body = format(d, spec)

    # 逐字掃描區段，把 0/#/., 換成 body，其餘（字面/引號/_/*/\\/$ 等）保留
    out = []
    i = 0
    n = len(section)
    consumed = False
    while i < n:
        ch = section[i]
        if ch == '"':
            j = section.find('"', i + 1)
            if j == -1:
                j = n
            out.append(section[i + 1:j]); i = j + 1; continue
        if ch == '\\':
            if i + 1 < n:
                out.append(section[i + 1])
            i += 2; continue
        if ch == '[':
            j = section.find(']', i)
            i = (j + 1) if j != -1 else n; continue
        if ch == '_':          # 下一字元寬度的空白
            out.append(' '); i += 2; continue
        if ch == '*':          # 填滿字元：標記為左右對齊分隔（會計格式 $ 靠左、數字靠右）
            out.append('\x00'); i += 2; continue
        if ch in '#0?,.':
            if not consumed:
                out.append(body)
                consumed = True
            # 跳過整段連續的數字占位符（含千分位逗號與小數）
            while i < n and section[i] in '#0?,.':
                i += 1
            continue
        if ch == '%':
            out.append('%'); i += 1; continue
        if ch == '$':
            out.append('$'); i += 1; continue
        out.append(ch); i += 1
    text = "".join(out)
    return text.strip()


def format_value(value, fmt):
    """value + Excel number_format → (顯示字串, is_red)。"""
    if value is None:
        return "", False
    if fmt is None:
        fmt = "General"

    # 文字值：數值格式對文字原樣輸出（Excel 行為）；若某區段含 @ 文字占位符則套用之
    if isinstance(value, str):
        if fmt in ("@", "General"):
            return value, False
        for sec in _split_sections(fmt):
            if "@" in sec:
                return _apply_text_section(sec, value), False
        return value, False   # 純數值格式套在文字 → 原樣

    # 布林
    if isinstance(value, bool):
        return ("TRUE" if value else "FALSE"), False

    # 日期
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
            value = datetime.datetime(value.year, value.month, value.day)
        if isinstance(value, datetime.time):
            value = datetime.datetime(1899, 12, 30, value.hour, value.minute, value.second)
        if fmt in ("General",):
            return value.strftime("%Y-%m-%d"), False
        return _fmt_date(value, _pick_section(fmt, 0)[0]), False

    # 數字
    if fmt == "General" or fmt == "":
        return _general_number(value), False
    if _is_datelike(fmt):
        dt = _excel_serial_to_dt(value)
        if dt is not None:
            return _fmt_date(dt, _pick_section(fmt, 0)[0]), False

    section, is_red = _pick_section(fmt, value)
    try:
        return _fmt_number(value, section), is_red
    except (ValueError, TypeError):
        return _general_number(value), False


def _general_number(value):
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if f == int(f):
        return str(int(f))
    return repr(round(f, 10)).rstrip("0").rstrip(".")


def _split_sections(fmt):
    # 依未被引號/中括號包住的 ';' 切段
    out = []
    buf = []
    i = 0
    n = len(fmt)
    while i < n:
        ch = fmt[i]
        if ch == '"':
            j = fmt.find('"', i + 1)
            if j == -1:
                j = n
            buf.append(fmt[i:j + 1]); i = j + 1; continue
        if ch == '[':
            j = fmt.find(']', i)
            j = j if j != -1 else n
            buf.append(fmt[i:j + 1]); i = j + 1; continue
        if ch == '\\':
            buf.append(fmt[i:i + 2]); i += 2; continue
        if ch == ';':
            out.append("".join(buf)); buf = []; i += 1; continue
        buf.append(ch); i += 1
    out.append("".join(buf))
    return out


_RED_RE = re.compile(r'\[(red|紅)\]', re.I)


def _strip_color(section):
    is_red = bool(_RED_RE.search(section))
    section = re.sub(r'\[[A-Za-z一-鿿]+\]', "", section)  # 具名顏色
    section = re.sub(r'\[color\s*\d+\]', "", section, flags=re.I)
    return section, is_red


def _pick_section(fmt, value):
    """依數值正負零挑選區段，回傳 (section_without_color, is_red)。"""
    sections = _split_sections(fmt)
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 0
    if len(sections) == 1:
        sec = sections[0]
    elif len(sections) == 2:
        sec = sections[0] if v >= 0 else sections[1]
    else:
        if v > 0:
            sec = sections[0]
        elif v < 0:
            sec = sections[1]
        else:
            sec = sections[2]
    sec, is_red = _strip_color(sec)
    return sec, is_red


def _apply_text_section(section, value):
    section, _ = _strip_color(section)
    out = []
    i = 0
    n = len(section)
    while i < n:
        ch = section[i]
        if ch == '"':
            j = section.find('"', i + 1)
            if j == -1:
                j = n
            out.append(section[i + 1:j]); i = j + 1; continue
        if ch == '\\':
            if i + 1 < n:
                out.append(section[i + 1])
            i += 2; continue
        if ch == '_':
            out.append(' '); i += 2; continue
        if ch == '@':
            out.append(value); i += 1; continue
        out.append(ch); i += 1
    return "".join(out)
