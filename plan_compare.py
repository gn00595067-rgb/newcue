# -*- coding: utf-8 -*-
"""兩版（多方案）效益比較（第二階段 2-3；主管 LINE：兩版效益比較；小花 1124-3：客戶想比較總檔數、單價、播出次數、接觸人次）。
業務把目前算好的 CUE「存成方案」（只存在本次工作階段），≥2 個方案時並排比較。
本模組不 import streamlit；獨立新檔，避免 Streamlit Cloud 舊模組快取造成 ImportError。"""
from pitch import benefit_summary

MAX_PLANS = 4
LETTERS = "ABCD"

# (欄位, 顯示名, 格式, 越大越好？)
METRICS = [
    ("net", "專案價（未稅）", "${:,.0f}", False),
    ("days", "走期天數", "{:,.0f} 天", None),
    ("spots", "總檔次（含加贈）", "{:,.0f}", True),
    ("gift_spots", "其中加贈檔次", "{:,.0f}", True),
    ("impressions", "總曝光次數", "{:,.0f}", True),
    ("gift_impressions", "加贈帶來曝光", "{:,.0f}", True),
    ("traffic", "店舖人流（人次）", "{:,.0f}", True),
    ("cpm", "每千次曝光成本", "${:,.0f}", False),
]


def make_plan(name, rows, ndays, net_price, start=None, end=None, desc=""):
    """把目前 CUE 的結果濃縮成一個方案（不存 rows，只存比較要用的數字）。"""
    s = benefit_summary(rows, ndays, net_price, start, end)
    plan = {k: s["total"].get(k) for k, *_ in METRICS}
    plan.update({"name": name, "desc": desc,
                 "period": f"{start:%m/%d}～{end:%m/%d}" if start and end else "",
                 "platforms": "、".join(f"{p['name']} {p['stores']:,}{p['unit']}" for p in s["platforms"]),
                 "text": s["text"]})
    return plan


def next_name(plans):
    used = {p["name"] for p in plans}
    return next((f"方案 {c}" for c in LETTERS if f"方案 {c}" not in used), f"方案 {len(plans) + 1}")


def add_plan(plans, plan):
    """加到清單（同名覆蓋），最多 MAX_PLANS 個；超過時丟最早的。回傳新清單。"""
    out = [p for p in plans or [] if p["name"] != plan["name"]] + [plan]
    return out[-MAX_PLANS:]


def _fmt(fmt, v):
    return "—" if v is None else fmt.format(v)


def compare_rows(plans):
    """比較表：每個指標一列，欄＝各方案；第 2 個方案起附與第 1 個方案的差異（+／−）。"""
    if not plans:
        return []
    base = plans[0]
    out = [{"項目": "平台", **{p["name"]: p.get("platforms", "") for p in plans}},
           {"項目": "走期", **{p["name"]: p.get("period", "") for p in plans}}]
    for key, label, fmt, _ in METRICS:
        row = {"項目": label}
        for i, p in enumerate(plans):
            v = p.get(key)
            cell = _fmt(fmt, v)
            b = base.get(key)
            if i and v is not None and b not in (None, 0) and v != b:
                pct = (v - b) / b * 100
                if abs(pct) >= 0.5:   # 四捨五入後 0% 不標
                    cell += f"（{'+' if pct > 0 else '−'}{abs(pct):.0f}%）"
            row[p["name"]] = cell
        out.append(row)
    return out


def best_notes(plans):
    """一句話重點：哪個方案曝光最多、哪個每千次曝光成本最低。"""
    if len(plans) < 2:
        return []
    notes = []
    top = max(plans, key=lambda p: p.get("impressions") or 0)
    notes.append(f"曝光最多：{top['name']}（{top['impressions']:,} 次）")
    cpms = [p for p in plans if p.get("cpm")]
    if cpms:
        low = min(cpms, key=lambda p: p["cpm"])
        notes.append(f"每千次曝光成本最低：{low['name']}（${low['cpm']:,.0f}）")
    gifts = [p for p in plans if p.get("gift_spots")]
    if gifts:
        g = max(gifts, key=lambda p: p["gift_spots"])
        notes.append(f"加贈最多：{g['name']}（{g['gift_spots']:,} 檔）")
    return notes
