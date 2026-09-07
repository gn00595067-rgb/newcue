# -*- coding: utf-8 -*-
"""
簡易模式 v2 HTML 即時預覽（CueModel → HTML 字串，§8）

不用「openpyxl 讀回 xlsx 轉 table」（失真、慢），直接從 CueModel 產 HTML，
與 Excel 同一份資料、同樣視覺語言：合併(rowspan/colspan)、六日底色、紅/藍字、千分位。
外層以 JS 依 iframe 寬度等比縮放（像 PDF 一眼看完）；窄螢幕改可橫向捲動。
"""
import simple_config as sc
from utils import html_escape as esc

_WD = "一二三四五六日"
_CSS = """
<style>
.cue-wrap{font-family:"Microsoft JhengHei","微軟正黑體","Noto Sans TC",sans-serif;
  background:#fff;color:#000;overflow:auto;padding:8px}
.cue-scale{transform-origin:top left;display:inline-block}
.cue-tag{float:right;font-size:13px;background:#111;color:#fff;border-radius:6px;
  padding:4px 10px;margin:2px}
.cue-head{margin:6px 0 10px}
.cue-head .row{font-size:18px;font-weight:700;margin:2px 0}
.cue-title{font-size:34px;font-weight:800;text-align:center;letter-spacing:2px}
table.cue{border-collapse:collapse;table-layout:fixed}
table.cue td,table.cue th{border:1px solid #999;padding:3px 6px;text-align:center;
  font-size:15px;white-space:nowrap;overflow:hidden}
table.cue th{background:#f2f2f2;font-weight:700}
.wknd{background:#FFFF99}
.red{color:#e00}.blue{color:#00f}.b{font-weight:700}
.lbl{text-align:right;font-weight:700}
.station{white-space:pre-line;font-weight:600}
.rmk{font-size:14px;margin:2px 0}.rmk.red{color:#e00}
.fees{margin-top:8px;font-size:15px}
.fees td{border:1px solid #999;padding:3px 10px}
</style>
"""


def _money(v):
    try:
        return f"{int(round(v)):,}"
    except (TypeError, ValueError):
        return esc(str(v))


def _net(v):
    if isinstance(v, (int, float)):
        return _money(v)
    return esc(str(v))


def _wrap(inner, cls, tag, height_px):
    """加上自動縮放外層與右上標籤。"""
    return f"""{_CSS}
<div class="cue-wrap {cls}">
  <div class="cue-tag">{tag}</div>
  <div class="cue-scale" id="sc">{inner}</div>
</div>
<script>
(function(){{
  var el=document.getElementById('sc'); if(!el) return;
  function fit(){{
    var w=el.scrollWidth||1, avail=document.body.clientWidth-24;
    var k=avail/w; if(k>1)k=1;
    if(k<0.45){{el.style.transform='none';}}
    else{{el.style.transform='scale('+k+')';}}
  }}
  fit(); window.addEventListener('resize',fit); setTimeout(fit,60);
}})();
</script>"""


def _head(model, sheet):
    rows = []
    if model.family == "subsidiary":
        rows.append(f'<div class="cue-title">Media Schedule</div>')
        rows.append(f'<div class="row">客戶名稱：{esc(model.client)}</div>')
        prod = f"{model.product} {sheet.seconds}秒".strip() if model.product else f"{sheet.seconds}秒"
        rows.append(f'<div class="row">Product：{esc(prod)}</div>')
        rows.append(f'<div class="row">Period：{model.start:%Y. %m. %d} - {model.end:%Y. %m. %d}</div>')
        rows.append(f'<div class="row">Medium：{esc(model.medium_label)}</div>')
    else:
        rows.append(f'<div class="row">客戶：{esc(model.client)}　產品：{esc(model.product)}</div>')
        rows.append(f'<div class="row">走期：{model.start:%Y.%m.%d} - {model.end:%Y.%m.%d}'
                    f'　{sheet.seconds}秒</div>')
    return '<div class="cue-head">' + "".join(rows) + "</div>"


def _daterow(days):
    cells = []
    for d in days:
        cls = ' class="wknd"' if d.weekend else ""
        cells.append(f'<th{cls}>{d.date.day}</th>')
    wk = []
    for d in days:
        cls = ' class="wknd"' if d.weekend else ""
        wk.append(f'<th{cls}>{_WD[d.date.weekday()]}</th>')
    return cells, wk


# --------------------------------------------------------------------------- #
# 子公司
# --------------------------------------------------------------------------- #
def _sub_table(model, sheet):
    days = sheet.days
    nd = len(days)
    dcells, wcells = _daterow(days)
    total_rows = sum(len(b.rows) for b in sheet.blocks)
    h = ['<table class="cue">']
    # 表頭
    h.append("<tr>"
             "<th>Station</th><th>Location</th><th>Program</th><th>Day-part</th>"
             "<th>Size</th><th>rate (Net)</th><th>Package-cost<br>(Net)</th>"
             + "".join(dcells) + "<th>檔次</th></tr>")
    h.append("<tr><th></th><th></th><th></th><th></th><th></th><th></th><th></th>"
             + "".join(wcells) + "<th></th></tr>")
    first = True
    for blk in sheet.blocks:
        for ri, r in enumerate(blk.rows):
            tds = ["<tr>"]
            if ri == 0:
                tds.append(f'<td class="station" rowspan="{len(blk.rows)}">'
                           f'{esc(sc.STATION_TEXT.get(blk.platform,""))}</td>')
            tds.append(f'<td>{esc(r.location)}</td>')
            tds.append(f'<td>{r.stores:,}店</td>' if r.stores else "<td></td>")
            # Day-part / Size：家樂福逐列，其餘首列合併
            is_cf = blk.platform == "家樂福"
            if is_cf or ri == 0:
                span = "" if is_cf else f' rowspan="{len(blk.rows)}"'
                tds.append(f'<td{span}>{esc(r.daypart)}</td>')
            if ri == 0:
                tds.append(f'<td rowspan="{len(blk.rows)}">{r.seconds}秒</td>')
            # rate
            if r.rate_text:
                tds.append(f'<td>{esc(r.rate_text)}</td>')
            else:
                lst, std, fac = r.rate_num
                tds.append(f'<td>{_money(lst/std*r.spots*fac)}</td>')
            # Package-cost 整段合併
            if first:
                tds.append(f'<td class="b" rowspan="{total_rows}">{_money(sheet.budget)}</td>')
                first = False
            # 每日
            for i in range(nd):
                cls = ' class="wknd"' if days[i].weekend else ""
                tds.append(f'<td{cls}>{r.schedule[i] or ""}</td>')
            tds.append(f'<td class="b">{r.spots:,}</td>')
            tds.append("</tr>")
            h.append("".join(tds))
    h.append("</table>")
    # 費用區
    f = sheet.fees
    h.append('<table class="fees"><tr><td class="lbl">Total (Net)</td>'
             f'<td class="b">{_money(sheet.budget)}</td></tr>'
             f'<tr><td class="lbl">製作</td><td>{_money(f["prod"])}</td></tr>'
             f'<tr><td class="lbl">5% VAT</td><td>{_money(f["vat"])}</td></tr>'
             f'<tr><td class="lbl b">Grand Total</td><td class="b">{_money(f["grand"])}</td></tr>'
             "</table>")
    return "".join(h)


# --------------------------------------------------------------------------- #
# 代理商（2008 / 凱絡）通用簡表
# --------------------------------------------------------------------------- #
def _agency_table(model, sheet):
    days = sheet.days
    nd = len(days)
    dcells, wcells = _daterow(days)
    carat = model.family == "carat"
    h = ['<table class="cue"><tr>']
    if carat:
        h.append("<th>媒體別</th><th>地區</th><th>時段</th><th>素材</th><th>定價</th>"
                 "<th>市場價</th><th>統一價</th><th>檔數</th><th>總價</th><th>專案價</th>"
                 + "".join(dcells) + "</tr>")
    else:
        h.append("<th>媒體型態</th><th>地區</th><th>時段</th><th>定價</th><th>單位</th>"
                 "<th>次數</th><th>合計</th>" + "".join(dcells) + "</tr>")
    h.append("<tr>" + ("<th></th>" * (10 if carat else 7)) + "".join(wcells) + "</tr>")
    for blk in sheet.blocks:
        for r in blk.rows:
            tds = ["<tr>"]
            tds.append(f'<td class="station">{esc((r.station or "").splitlines()[0] if r.station else "")}</td>')
            tds.append(f'<td>{esc(r.region.splitlines()[0] if r.region else "")}</td>')
            tds.append(f'<td>{esc(r.daypart)}</td>')
            if carat:
                tds.append(f'<td>{r.seconds}"CM</td>')
                tds.append(f'<td>{_money(r.list_per)}</td>')
                tds.append(f'<td>{_money(r.market_per)}</td>')
                tds.append(f'<td>{_money(r.uni_per)}</td>')
                tds.append(f'<td>{r.spots:,}</td>')
                tds.append(f'<td>{_money(r.uni_total)}</td>')
                nd_cls = "blue" if r.net_display == sc.TXT_REBATE else ""
                tds.append(f'<td class="{nd_cls}">{_net(r.net_display)}</td>')
            else:
                tds.append(f'<td>{_money(r.list_total) if r.list_total else ""}</td>')
                tds.append(f'<td class="red">{r.seconds}秒</td>')
                tds.append(f'<td>{r.spots:,}</td>')
                nd_cls = "red" if isinstance(r.net_display, str) else ""
                tds.append(f'<td class="{nd_cls}">{_net(r.net_display)}</td>')
            for i in range(nd):
                cls = ' class="wknd"' if days[i].weekend else ""
                v = r.schedule[i] if r.schedule else ""
                tds.append(f'<td{cls}>{v or ""}</td>')
            tds.append("</tr>")
            h.append("".join(tds))
    h.append("</table>")
    # 費用
    f = sheet.fees
    if carat:
        h.append('<table class="fees">'
                 f'<tr><td class="lbl">媒體總價值(NET)</td><td>{_money(f["media_value"])}</td></tr>'
                 f'<tr><td class="lbl">優惠總價值(NET)</td><td>{_money(f["discount_value"])}</td></tr>'
                 f'<tr><td class="lbl">Sub-Total</td><td>{_money(f["subtotal"])}</td></tr>'
                 f'<tr><td class="lbl">A.C 3%</td><td>-</td></tr>'
                 f'<tr><td class="lbl">VAT 5%</td><td>{_money(f["vat"])}</td></tr>'
                 f'<tr><td class="lbl b">Grand-Total</td><td class="b">{_money(f["grand"])}</td></tr>'
                 "</table>")
    else:
        h.append('<table class="fees">'
                 f'<tr><td class="lbl">Budget (net)</td><td>{_money(f["budget"])}</td></tr>'
                 f'<tr><td class="lbl">AC %</td><td>{_money(f["ac"])}</td></tr>'
                 f'<tr><td class="lbl">5% Tax</td><td>{_money(f["tax"])}</td></tr>'
                 f'<tr><td class="lbl b">TOTAL</td><td class="b">{_money(f["total"])}</td></tr>'
                 "</table>")
    return "".join(h)


def _remarks_html(model):
    if not model.remarks:
        return ""
    out = ['<div style="margin-top:8px">']
    for txt, red in model.remarks:
        out.append(f'<div class="rmk {"red" if red else ""}">{esc(txt)}</div>')
    out.append("</div>")
    return "".join(out)


def sheet_html(model, sheet):
    if model.family == "subsidiary":
        body = _head(model, sheet) + _sub_table(model, sheet)
        cls, grand = "cue-subsidiary", sheet.fees["grand"]
    else:
        body = _head(model, sheet) + _agency_table(model, sheet)
        cls = "cue-2008" if model.family == "2008" else "cue-carat"
        grand = sheet.fees.get("total") or sheet.fees.get("grand")
    body += _remarks_html(model)
    total_spots = sum(r.spots for b in sheet.blocks for r in b.rows)
    tag = f"{sheet.seconds}秒版 ｜ 總檔次 {total_spots:,} ｜ Grand Total ${_money(grand)}"
    return _wrap(body, cls, tag, 0)


def render_html(model):
    """回傳 [(分頁標題, html字串), ...]。"""
    return [(s.title, sheet_html(model, s)) for s in model.sheets]


def estimate_height(sheet):
    """依列數估算 iframe 高度（§8）。"""
    rows = sum(len(b.rows) for b in sheet.blocks) + len(sheet.remarks) if hasattr(sheet, "remarks") \
        else sum(len(b.rows) for b in sheet.blocks)
    return min(1100, 360 + rows * 34 + 220)
