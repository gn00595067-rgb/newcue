"""送出前預覽：把一張 OrderDraft 畫成仿 Ragic「訂檔(業務填寫)-V3」表單的 HTML（Jonathan 2026-10-21）。

版面依訂檔表實際排列：訂檔資訊（主表）→ 訂檔收入相關資訊（子表＋總計）→ 訂檔素材及需求資訊（兩個子表）。
值＝實際會送進 Ragic 的值；Ragic 自己產生／連動的欄位以灰字「Ragic 自動」標示；紅星＝必填，空白必填標紅底。
純函式（不依賴 streamlit），方便測試。
"""
from __future__ import annotations

from html import escape

from ragic_booking.fields import OrderDraft

AUTO = "（Ragic 自動）"

# 主表四欄排列（照 Ragic 版面）：(欄名, 取值, 必填, 底色群組)
# 取值：OrderDraft 屬性名、callable(d)、或 AUTO
_MAIN = [
    [("訂檔性質", lambda d: "訂檔", False, "o"), ("訂檔單號", AUTO, False, "o"),
     ("建立日期", AUTO, False, "o"), ("修改日期", AUTO, False, "o")],
    [("申請人", "申請人", True, "o"), ("業務(開發客戶)", "業務開發客戶", True, "o"),
     ("業務主管", "業務主管", False, "o"), ("公司", "公司", True, "o")],
    [("CUE號", lambda d: d.CUE號 or "（送出時申請）", True, "p"), ("波段", "波段", True, "p"),
     ("客服", "客服", True, "o"), ("文案", "文案", True, "o")],
    [("CUE", AUTO, False, "p"), ("總波段", AUTO, False, "p"),
     ("訂檔人", "訂檔人", True, "o"), ("節配", "節配", False, "o")],
    [("客戶編號", "客戶編號", True, "c"), ("統一編號", "統一編號", False, "c"),
     ("結三單", "結三單", False, "r"), ("回簽", "回簽", False, "r")],
    [("客戶", "客戶名稱", False, "c"), ("產業別", AUTO, False, "c"),
     ("個案分配", "個案分配", False, "r"), ("停檔", "停檔", False, "r")],
    [("客戶類別", "客戶類別", True, "c"), ("產品名稱", "產品名稱", False, "c"),
     ("通知部門", "通知部門", False, "v"), ("通知個人", "通知個人", False, "v")],
    [("平台", "平台", True, "o"), ("電台", "電台", False, "o"),
     ("平台2", "平台2", False, "o"), ("距上檔時數", AUTO, False, "o")],
    [("執行開始日期", "執行開始日期", True, "o"), ("執行結束日期", "執行結束日期", True, "o"),
     ("企頻素材", "企頻素材", False, "r"), ("個案確認", "個案確認", False, "r")],
    [("CUE表秒數", "CUE表秒數", True, "o"), ("CUE表總檔數", "CUE表總檔數", True, "o"),
     ("新鮮視素材", "新鮮視素材", False, "r"), ("成本確認", "成本確認", False, "r")],
    [("訂檔CUE表", lambda d: d.__dict__.get("_att_cue", ""), True, "o"),
     ("客戶回簽檔/業務回簽檔", lambda d: d.__dict__.get("_att_sign", ""), True, "o"),
     ("電台播證開立名稱", "電台播證開立名稱", True, "o"), ("個案狀況", "個案狀況", False, "r")],
    [("素材走法", "素材走法", False, "o"), ("付款條件", "付款條件", False, "p"),
     ("現折%", "現折pct", True, "p"), ("退佣", "退佣", True, "p")],
    [("收款日期", "收款日期", True, "p"), ("發票開立日(業務)", "發票開立日業務", False, "p"),
     ("退佣%+現折%", AUTO, False, "p"), ("特殊條件-70%／60%", lambda d: _yn(d.特殊條件70) + "／" + _yn(d.特殊條件60), False, "r")],
]
_INCOME_COLS = [("類別", True), ("業績年月", True), ("平台細項", True), ("平台檔數", True), ("秒數", True),
                ("製作成本", True), ("配音員費用", True), ("實收金額未稅", True), ("除佣實收", False),
                ("其他成本", True), ("公司", False)]
_BG = {"o": "#ffd9a8", "p": "#f9b3f0", "c": "#a8f0f5", "r": "#ffc9c9", "v": "#c9c4f5"}

_CSS = """
<style>
.rg{font-family:'Noto Sans TC','Microsoft JhengHei',sans-serif;font-size:13px;color:#222;background:#fff;
    border:1px solid #c8c8c8;max-width:100%;overflow-x:auto}
.rg h4{background:#1f5fbf;color:#fff;text-align:center;margin:0;padding:6px;font-size:16px;font-weight:600}
.rg table{border-collapse:collapse;width:100%;table-layout:fixed}
.rg td,.rg th{border:1px solid #dcdcdc;padding:4px 6px;vertical-align:top;word-break:break-all}
.rg td.l{text-align:right;font-weight:600;width:11%}
.rg td.v{background:#fff;width:14%}
.rg .req{color:#d00}
.rg .auto{color:#999}
.rg td.miss{background:#ffe5e5}
.rg th{background:#ffd9a8;font-weight:600;text-align:left}
.rg td.n{text-align:right}
.rg tr.tot td{background:#f3f3f3;font-weight:600}
.rg .note{color:#666;font-size:12px;padding:4px 8px}
</style>
"""


def _yn(v):
    return "✓" if v else ""


def _fmt(v):
    if isinstance(v, bool):
        return _yn(v)
    if isinstance(v, (list, tuple)):
        return "、".join(str(x) for x in v)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"{v:,.0f}" if float(v).is_integer() else str(v)
    return "" if v is None else str(v)


def _num(v):
    try:
        return float(str(v).replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return 0.0


def _value(d, src):
    if src == AUTO:
        return None
    return src(d) if callable(src) else getattr(d, src, "")


def order_html(d: OrderDraft, *, title="訂檔(業務填寫)-V3", attachments=None, materials=None) -> str:
    """一張訂檔 → 仿 Ragic HTML。attachments：{"cue": 檔名, "sign": 檔名}；materials：[{"廣告篇名","音檔","文案"}] 檔名字串。"""
    d.__dict__["_att_cue"] = (attachments or {}).get("cue", "")
    d.__dict__["_att_sign"] = (attachments or {}).get("sign", "")
    out = [_CSS, f'<div class="rg"><div class="note">{escape(title)}　第 {escape(str(d.波段))} 波預覽（送出後 Ragic 實際畫面以 Ragic 為準）</div>',
           "<h4>訂檔資訊</h4><table>"]
    for row in _MAIN:
        out.append("<tr>")
        for name, src, req, grp in row:
            v = _value(d, src)
            star = '<span class="req">*</span>' if req else ""
            out.append(f'<td class="l" style="background:{_BG[grp]}">{star}{escape(name)}</td>')
            if v is None:
                out.append(f'<td class="v auto">{AUTO}</td>')
            else:
                txt = _fmt(v)
                miss = " miss" if req and not txt else ""
                out.append(f'<td class="v{miss}">{escape(txt)}</td>')
        out.append("</tr>")
    out.append("</table>")

    # 收入子表
    disc, reb = _num(d.現折pct), _num(d.退佣)
    out.append("<h4>訂檔收入相關資訊</h4><table><tr>")
    for c, req in _INCOME_COLS:
        label = {"實收金額未稅": "實收金額(未稅)", "除佣實收": "除佣實收(未稅)"}.get(c, c)
        out.append(f'<th>{"<span class=req>*</span>" if req else ""}{escape(label)}</th>')
    out.append("</tr>")
    tot_spots = tot_net = tot_after = 0.0
    for r in d.收入明細:
        net = _num(r.get("實收金額未稅"))
        after = net * (1 - disc) * (1 - reb) * (0.3 if r.get("類別") == "交換" else 1)
        tot_spots += _num(r.get("平台檔數"))
        tot_net += net
        tot_after += after
        out.append("<tr>")
        for c, _req in _INCOME_COLS:
            if c == "除佣實收":
                out.append(f'<td class="n auto">{after:,.0f}</td>')
                continue
            v = r.get(c, "")
            if c == "公司" and not v:
                v = d.公司
            num = c in ("平台檔數", "製作成本", "配音員費用", "實收金額未稅", "其他成本")
            txt = (f"{_num(v):,.0f}" if num and str(v) != "" else _fmt(v))
            out.append(f'<td class="{"n" if num else ""}">{escape(txt)}</td>')
        out.append("</tr>")
    if not d.收入明細:
        out.append(f'<tr><td class="miss" colspan="{len(_INCOME_COLS)}">（沒有收入列）</td></tr>')
    out.append(f'<tr class="tot"><td colspan="3">平台檔數總計 {tot_spots:,.0f}</td>'
               f'<td colspan="4">實收金額總計(未稅) ${tot_net:,.0f}</td>'
               f'<td colspan="4">除佣實收總計(未稅) ${tot_after:,.0f}</td></tr></table>')

    # 素材＋需求
    out.append("<h4>訂檔素材及需求資訊</h4><table><tr><th>素材音檔</th><th>廣告篇名</th><th>文案</th></tr>")
    mats = materials if materials is not None else [{"廣告篇名": m.get("廣告篇名", "")} for m in d.素材明細]
    for m in mats:
        out.append(f'<tr><td>{escape(str(m.get("音檔") or ""))}</td><td>{escape(str(m.get("廣告篇名") or ""))}</td>'
                   f'<td>{escape(str(m.get("文案") or ""))}</td></tr>')
    if not mats:
        out.append('<tr><td colspan="3" class="auto">（無，素材後補）</td></tr>')
    out.append("</table><table><tr><th>需求或狀況說明</th><th style='width:22%'>建立時間</th></tr>")
    if d.需求說明:
        out.append(f"<tr><td>{escape(d.需求說明)}</td><td>{escape(d.需求建立時間 or '（送出時間）')}</td></tr>")
    else:
        out.append('<tr><td colspan="2" class="auto">（本次不新增）</td></tr>')
    out.append("</table></div>")
    return "".join(out)
