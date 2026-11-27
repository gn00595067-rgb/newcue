# -*- coding: utf-8 -*-
"""CUE 曝光結論的「其中加贈帶來曝光」一行（主管 2026-11-27 勾選：回饋 #6 購買／贈送效益）。
加贈列＝門檻回饋、主管／業務加贈、業務手填加贈（is_rebate／is_bonus_rebate／is_custom_bonus）。
獨立新檔：Streamlit Cloud 推版後可能沿用舊模組，新函式放新檔才不會 ImportError。"""
from simple_reach import compute_reach_from_rows


def is_gift_row(r):
    return bool(r.get("is_rebate") or r.get("is_custom_bonus") or r.get("is_bonus_rebate"))


def gift_impressions(rows, ndays):
    all_imp = compute_reach_from_rows(rows, ndays)["total"]["impressions"]
    paid_imp = compute_reach_from_rows([r for r in rows or [] if not is_gift_row(r)], ndays)["total"]["impressions"]
    return max(0, int(all_imp - paid_imp))


def gift_reach_line(rows, ndays):
    """有加贈才回傳一行文字，否則 None。"""
    n = gift_impressions(rows, ndays)
    return f"【其中加贈帶來曝光次數 : {n:,}】" if n > 0 else None
