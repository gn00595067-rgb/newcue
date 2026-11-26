# -*- coding: utf-8 -*-
"""鉑霖格式「實收價(含稅)」：Grand Total 扣退傭、現折（主管 2026-11-26 Q2，spec docs/specs/第二階段_主管決策實作.md）。
樣張：Grand Total 249,900、15% 退傭＋2% 現折 → 249,900 × 0.85 × 0.98 ＝ 208,167。
獨立模組：Streamlit Cloud 推版後可能沿用舊模組，新函式放新檔才不會 ImportError。"""
from decimal import Decimal, ROUND_HALF_UP


def pct_value(raw):
    """Ragic／畫面上的 % 值 → 百分比數字：'15'、'15%'、15 → 15.0；0.15（小數寫法）→ 15.0；空白／看不懂 → 0。"""
    try:
        v = float(str(raw if raw is not None else "").replace("%", "").replace("％", "").strip() or 0)
    except ValueError:
        return 0.0
    if 0 < v < 1:
        v *= 100
    return max(0.0, min(100.0, v))


def net_after_terms(grand_total, terms):
    """terms＝(退傭%, 現折%)。兩者皆 0／None → None（不顯示該列）。"""
    if not terms:
        return None
    reb, disc = (pct_value(x) for x in terms)
    if reb <= 0 and disc <= 0:
        return None
    val = Decimal(str(grand_total)) * (Decimal(1) - Decimal(str(reb)) / 100) * (Decimal(1) - Decimal(str(disc)) / 100)
    return int(val.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _fmt(p):
    p = pct_value(p)
    return f"{int(p)}" if p == int(p) else f"{p:g}"


def net_terms_label(reb, disc):
    """'15%退傭+2%現折'；只有一項時只寫那一項。"""
    parts = []
    if pct_value(reb) > 0:
        parts.append(f"{_fmt(reb)}%退傭")
    if pct_value(disc) > 0:
        parts.append(f"{_fmt(disc)}%現折")
    return "+".join(parts)


def cash_discount_sentence(disc):
    """備註第 6 點補充（有現折才加）。"""
    return f"，若於廣告上檔前完成匯款方享有{_fmt(disc)}%現金折扣。" if pct_value(disc) > 0 else ""


def apply_cash_discount(lines, disc):
    """備註條列：第 6 點「付款兌現日期」後補現金折扣說明（樣張：116.04.30前，若於廣告上檔前完成匯款方享有2%現金折扣。）。
    已補過或沒有現折就原樣回傳。lines 可為 list 或以換行分隔的字串，回傳同型別。"""
    is_str = isinstance(lines, str)
    items = lines.split("\n") if is_str else list(lines or [])
    tail = cash_discount_sentence(disc)
    if tail:
        for i, t in enumerate(items):
            if "付款兌現日期" in t and "現金折扣" not in t:
                body = t.rstrip("。 ").rstrip()
                items[i] = body + ("" if body.endswith("前") else "前") + tail
                break
    return "\n".join(items) if is_str else items
