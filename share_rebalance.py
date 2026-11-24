# -*- coding: utf-8 -*-
"""預算 % 連動（第二階段 A1）。獨立成新模組：Streamlit Cloud 推版後可能沿用記憶體裡舊的 utils，
app.py 從 utils import 新函式會 ImportError（2026-10-13、11-24 都發生過），新模組則一定重新載入。"""


def rebalance_shares(values, changed, manual):
    """預算 % 連動（第二階段 A1，宜歆／業務 11/23 測試：拉桿調第二個平台時第一個會跑掉）。
    values：{key: 目前 %}（依畫面順序）；changed：剛改的 key；manual：之前手填過的 key（先後順序）。
    規則：手填過的保留，沒手填的平均補剩下的（整數，尾差給最後一個）；手填紀錄最多「項目數−1」個，
    滿了丟最早填的、由它吸收差額。回傳 (新 values, 新 manual)。"""
    keys = list(values)
    out = {k: int(values[k] or 0) for k in keys}
    if len(keys) <= 1:
        return {k: 100 for k in keys}, []
    order = [k for k in (manual or []) if k in keys and k != changed] + [changed]
    order = order[-(len(keys) - 1):]
    auto = [k for k in keys if k not in order]
    rest = max(0, 100 - sum(out[k] for k in order))
    each = rest // len(auto)
    for i, k in enumerate(auto):
        out[k] = each if i < len(auto) - 1 else rest - each * (len(auto) - 1)
    return out, order
