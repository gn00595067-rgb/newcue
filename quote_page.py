# -*- coding: utf-8 -*-
"""一頁式報價頁（第二階段 2-4；主管 Q4：單一方案報價卡＋多方案總覽；版型參考小花 1124 範例）。
資料全部來自已算好的 CUE（rows）或已存的方案（plan_compare），不另外輸入。輸出 A4 橫式 PDF bytes。
本模組不 import streamlit；獨立新檔，避免 Streamlit Cloud 舊模組快取造成 ImportError。"""
import io

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

import pdf_render
from pitch import benefit_summary

INK = HexColor("#1d2433")
MUTED = HexColor("#5b6578")
LINE = HexColor("#d9dee7")
TILE = HexColor("#f4f6f9")
ACCENT = HexColor("#0b6fb3")
GREEN = HexColor("#0a7a3d")
GREEN_BG = HexColor("#e8f3ec")
W, H = landscape(A4)
M = 36


def _font(c, size, bold=False):
    c.setFont(pdf_render.FONT_BOLD if bold else pdf_render.FONT_REG, size)


def _platform_specs(rows):
    """各平台秒數、時段（從 rows 取主列）。"""
    out = {}
    for r in rows or []:
        if r.get("is_rebate") or r.get("is_custom_bonus") or r.get("is_bonus_rebate"):
            continue
        e = out.setdefault(r.get("media"), {"secs": set(), "daypart": r.get("daypart", "")})
        if r.get("seconds"):
            e["secs"].add(int(r["seconds"]))
    return out


def _tile(c, x, y, w, h, label, value, sub=""):
    c.setFillColor(TILE); c.setStrokeColor(LINE); c.roundRect(x, y, w, h, 6, fill=1, stroke=1)
    c.setFillColor(MUTED); _font(c, 10); c.drawString(x + 12, y + h - 20, label)
    size = 17
    while size > 10 and c.stringWidth(value, pdf_render.FONT_BOLD, size) > w - 22:   # 長名稱自動縮字
        size -= 1
    c.setFillColor(INK); _font(c, size, True); c.drawString(x + 12, y + h - 44, value)
    if sub:
        c.setFillColor(MUTED); _font(c, 9.5); c.drawString(x + 12, y + 12, sub)


def _wrap(c, text, width, size):
    lines, cur = [], ""
    for ch in text:
        if c.stringWidth(cur + ch, pdf_render.FONT_REG, size) > width:
            lines.append(cur); cur = ch
        else:
            cur += ch
    return lines + ([cur] if cur else [])


def build_quote_pdf(rows, ndays, net_price, grand_total, start, end, client="", product="", company="聲活數位"):
    """單一方案報價卡。grand_total＝含稅總價（含製作費）。"""
    pdf_render._ensure_fonts()
    s = benefit_summary(rows, ndays, net_price, start, end)
    specs = _platform_specs(rows)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))

    # 標題
    names = "＋".join(p["name"] for p in s["platforms"]) or "店內廣告"
    c.setFillColor(GREEN); _font(c, 11, True); c.drawString(M, H - M - 6, "全台零售通路 店內廣告")
    c.setFillColor(INK); _font(c, 24, True); c.drawString(M, H - M - 38, f"{names} 報價")
    c.setFillColor(MUTED); _font(c, 11)
    sub = "　".join(x for x in (f"客戶：{client}" if client else "", f"廣告：{product}" if product else "",
                               f"走期 {start:%Y/%m/%d}～{end:%Y/%m/%d}（{s['total']['days']} 天）") if x)
    c.drawString(M, H - M - 60, sub)

    # 左側：每平台一列資訊磚
    top = H - M - 84
    left_w = W - 2 * M - 250
    plats = s["platforms"][:3]
    row_h = min(92, (top - 150) / max(1, len(plats)) - 8)
    tw = (left_w - 3 * 8) / 4
    for i, p in enumerate(plats):
        y = top - (i + 1) * (row_h + 8)
        sp = specs.get(p["media"], {})
        secs = "、".join(f"{x} 秒" for x in sorted(sp.get("secs") or [])) or "—"
        _tile(c, M, y, tw, row_h, "播放平台", p["name"].replace("全家便利商店", "全家"))
        _tile(c, M + (tw + 8), y, tw, row_h, "通路規模", f"{p['stores']:,} {p['unit']}")
        _tile(c, M + 2 * (tw + 8), y, tw, row_h, "素材秒數／時段", secs, sp.get("daypart", ""))
        freq = f"每天約 {p['per_store_day']:.0f} 檔" if p.get("per_store_day") else f"{p['spots']:,} 檔"
        hours = None
        dp = sp.get("daypart", "")
        try:
            a, b = dp.replace("：", ":").split("-")
            hours = int(b.split(":")[0]) - int(a.split(":")[0])
        except Exception:  # noqa: BLE001
            hours = None
        sub = f"每小時約 {p['per_store_day'] / hours:.0f} 檔" if p.get("per_store_day") and hours else (f"其中加贈 {p['gift_spots']:,} 檔" if p["gift_spots"] else "")
        _tile(c, M + 3 * (tw + 8), y, tw, row_h, f"播出頻次（每{p['unit']}）", freq, sub)

    # 右側：專案價
    bx, by, bw = W - M - 236, 150, 236
    bh = top - by
    c.setFillColor(ACCENT); c.roundRect(bx, by, bw, bh, 10, fill=1, stroke=0)
    c.setFillColor(HexColor("#ffffff")); _font(c, 13, True); c.drawString(bx + 18, by + bh - 30, "專案價（含稅）")
    _font(c, 34, True); c.drawString(bx + 18, by + bh - 80, f"{int(grand_total):,}")
    _font(c, 10); c.drawString(bx + 18, by + bh - 102, f"未稅 {int(net_price):,} 元")
    if s["total"]["gift_spots"]:
        _font(c, 11, True); c.drawString(bx + 18, by + 52, f"加贈 {s['total']['gift_spots']:,} 檔")
        _font(c, 9.5); c.drawString(bx + 18, by + 34, f"額外曝光約 {s['total']['gift_impressions']:,} 次")
    if s["total"].get("cpm"):
        _font(c, 9.5); c.drawString(bx + 18, by + 16, f"每千次曝光成本約 {s['total']['cpm']:,.0f} 元")

    # 下方：曝光、人流
    hw = (W - 2 * M - 12) / 2
    for i, (label, val, unit) in enumerate((("總曝光次數", s["total"]["impressions"], "次"),
                                            ("曝光期間店舖人流", s["total"]["traffic"], "人次"))):
        x = M + i * (hw + 12)
        c.setFillColor(GREEN_BG); c.roundRect(x, 64, hw, 74, 8, fill=1, stroke=0)
        c.setFillColor(INK); _font(c, 11); c.drawString(x + 16, 116, label)
        c.setFillColor(GREEN); _font(c, 26, True); c.drawString(x + 16, 80, f"{val:,} {unit}")

    # 說明
    c.setFillColor(MUTED); _font(c, 8.5)
    note = ("說明：總曝光次數＝各區播出店數 × 檔次；全家店舖人流量以每店每日平均來客 1,000 人換算；"
            "萬家福／樂家康依通路提供之每日來客數換算，皆為預估值，實際以通路結案報告為準。")
    for j, ln in enumerate(_wrap(c, note, W - 2 * M - 90, 8.5)[:2]):
        c.drawString(M, 46 - j * 11, ln)
    c.setFillColor(INK); _font(c, 11, True); c.drawRightString(W - M, 40, company)
    c.showPage(); c.save()
    return buf.getvalue()


def build_compare_pdf(plans, client="", company="聲活數位"):
    """多方案總覽：每個方案一欄的比較表＋重點。plans＝plan_compare 的方案。"""
    import plan_compare as pc
    pdf_render._ensure_fonts()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setFillColor(GREEN); _font(c, 11, True); c.drawString(M, H - M - 6, f"{client}　" if client else "全台零售通路 店內廣告")
    c.setFillColor(INK); _font(c, 24, True); c.drawString(M, H - M - 38, f"{len(plans)} 方案總覽")

    rows = pc.compare_rows(plans)
    label_w = 130
    col_w = (W - 2 * M - label_w) / max(1, len(plans))
    y = H - M - 70
    rh = 30
    # 表頭
    c.setFillColor(TILE); c.rect(M, y - rh, W - 2 * M, rh, fill=1, stroke=0)
    c.setFillColor(INK); _font(c, 11, True); c.drawString(M + 8, y - 20, "項目")
    for i, p in enumerate(plans):
        c.drawString(M + label_w + i * col_w + 8, y - 20, p["name"])
    y -= rh
    for r in rows:
        c.setStrokeColor(LINE); c.line(M, y - rh, W - M, y - rh)
        c.setFillColor(MUTED); _font(c, 10); c.drawString(M + 8, y - 20, r["項目"])
        c.setFillColor(INK)
        for i, p in enumerate(plans):
            val = str(r.get(p["name"], ""))
            size = 10.5 if r["項目"] not in ("平台",) else 8.5
            _font(c, size, r["項目"] in ("專案價（未稅）", "總曝光次數"))
            lines = _wrap(c, val, col_w - 14, size)[:2]
            for j, ln in enumerate(lines):
                c.drawString(M + label_w + i * col_w + 8, y - 20 + (6 if len(lines) > 1 else 0) - j * 11, ln)
        y -= rh
    # 重點
    notes = pc.best_notes(plans)
    if notes:
        c.setFillColor(GREEN_BG); c.roundRect(M, y - 52, W - 2 * M, 40, 8, fill=1, stroke=0)
        c.setFillColor(GREEN); _font(c, 12, True); c.drawString(M + 14, y - 37, "　｜　".join(notes))
    c.setFillColor(MUTED); _font(c, 8.5)
    c.drawString(M, 40, "曝光、人流為預估值（總曝光＝店數 × 檔次），實際以通路結案報告為準。專案價皆為未稅。")
    c.setFillColor(INK); _font(c, 11, True); c.drawRightString(W - M, 40, company)
    c.showPage(); c.save()
    return buf.getvalue()
