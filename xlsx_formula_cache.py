# -*- coding: utf-8 -*-
"""
openpyxl 寫的公式格沒有快取值（<v></v>），Excel 受保護檢視／PDF 渲染（data_only）會看到空白。
這裡在存檔後替「純數字算式」公式（如 =4000*420）補上計算結果，
讓檔案一開就有數字、點進儲存格又看得到算法（宜歆 11/12 #13：代理商定價要看得到列計方式）。
只處理只含數字與 + - * / ( ) 的算式；引用其他儲存格的公式不動。
"""
import io
import re
import zipfile

_CELL = re.compile(r'(<c r="[A-Z]+\d+"[^>]*>)<f>([^<]*)</f><v\s*(?:/>|></v>)(</c>)')
_ARITH = re.compile(r'^[\d\.\s\+\-\*/\(\)]+$')


def _fmt(v):
    return str(int(v)) if float(v).is_integer() else repr(float(v))


def _fill(xml):
    def rep(m):
        expr = m.group(2)
        if not _ARITH.match(expr):
            return m.group(0)
        try:
            val = eval(expr, {"__builtins__": {}}, {})  # 已限定只含數字與運算符
        except Exception:
            return m.group(0)
        return f"{m.group(1)}<f>{expr}</f><v>{_fmt(val)}</v>{m.group(3)}"
    return _CELL.sub(rep, xml)


def fill_formula_cache(xlsx_bytes):
    """回傳補好公式快取值的 xlsx bytes。"""
    src = zipfile.ZipFile(io.BytesIO(xlsx_bytes))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename.startswith("xl/worksheets/") and info.filename.endswith(".xml"):
                data = _fill(data.decode("utf-8")).encode("utf-8")
            dst.writestr(info, data)
    return out.getvalue()


def price_formula(per, total):
    """定價格：能整除時寫成 =單價*檔次（看得到算法），否則照原值。"""
    if (isinstance(per, (int, float)) and isinstance(total, (int, float))
            and per > 0 and total > 0 and total % per == 0):
        return f"={int(per)}*{int(total // per)}"
    return total
