# -*- coding: utf-8 -*-
"""
一鍵CUE（簡易模式子公司組合）改用一般 CUE 聲活／鉑霖版面輸出。

簡易模式的 CueModel 每個秒數版一張 CueSheet；這裡把每張轉成一般 CUE 的 rows，
交給 excel_renderer.render_excel_into／html_generator.generate_html_preview，
版面與一般 CUE 選聲活／鉑霖時一模一樣（規格見 docs/specs/格式選擇擴充.md）。
東吳仍走簡易模式原版面（宜歆 0902 範本），不經過這裡。

本模組不 import streamlit，可獨立測試。
"""
import io

import openpyxl

from agency_cue import rhu
from excel_renderer import render_excel_into
from html_generator import generate_html_preview

# 一般 CUE 內部 media key 與簡易模式 block.platform 相同（全家廣播／新鮮視／家樂福）
_REGION_WJF = {"量販": "全省量販", "超市": "全省超市"}


def _block_budgets(sheet):
    """各平台 Package-cost：預算依各平台隱藏實收比例拆分，尾差給最後一個平台，合計恆等於預算。"""
    nets = [sum(r.hidden_net for r in b.rows) for b in sheet.blocks]
    total = sum(nets)
    if total <= 0:
        return [sheet.budget] + [0] * (len(nets) - 1)
    out = [rhu(sheet.budget * n / total) for n in nets[:-1]]
    out.append(sheet.budget - sum(out))
    return out


def sheet_to_rows(sheet):
    """CueSheet → 一般 CUE rows（每平台一個 Package-cost 群組）。"""
    rows = []
    for blk, pkg in zip(sheet.blocks, _block_budgets(sheet)):
        for r in blk.rows:
            if r.rate_num:
                lst, std, f = r.rate_num
                rate = rhu(lst / std * r.spots * f)
            else:
                rate = r.rate_text or ""
            region = _REGION_WJF.get(r.region, r.region) if blk.platform == "家樂福" else r.region
            rows.append({
                "media": blk.platform,
                "region": region,
                "program_num": r.stores or 0,
                "daypart": r.daypart,
                "seconds": r.seconds,
                "spots": r.spots,
                "schedule": list(r.schedule or []),
                "rate_display": rate,
                "pkg_display": rate,
                "is_pkg_member": True,
                "nat_pkg_display": pkg,
            })
    return rows


def _total_list(rows):
    return sum(r["rate_display"] for r in rows if isinstance(r["rate_display"], (int, float)))


def _remarks(model):
    return [t for t, _red in model.remarks]


def render_xlsx(model, format_type, sales_person=""):
    """所有秒數版併成一個活頁簿（每秒數一張；走期超過 31 天跨月時再依月拆），回傳 bytes。"""
    wb = openpyxl.Workbook()
    blank = wb.active
    for sheet in model.sheets:
        rows = sheet_to_rows(sheet)
        render_excel_into(
            format_type, model.start, model.end, model.client, model.tax_id, model.product,
            rows, _remarks(model), sheet.budget, sheet.prod_cost, sales_person,
            _total_list(rows), wb=wb, sheet_prefix=f"{sheet.seconds}秒")
    wb.remove(blank)
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def render_htmls(model, format_type):
    """每個秒數版一份 HTML 預覽（跨月拆頁時為多頁合併）；回傳 [(title, html)]。"""
    ndays = (model.end - model.start).days + 1
    out = []
    for sheet in model.sheets:
        rows = sheet_to_rows(sheet)
        p_str = f"{sheet.seconds}秒 {model.product}".strip()
        grand = sheet.fees.get("grand") or sheet.fees.get("total") or 0
        html = generate_html_preview(
            rows, ndays, model.start, model.end, model.client, model.tax_id, p_str, format_type,
            _remarks(model), _total_list(rows), grand, sheet.budget, sheet.prod_cost)
        if isinstance(html, list):
            html = "<hr>".join(html)
        out.append((sheet.title, html))
    return out
