# -*- coding: utf-8 -*-
"""贈檔權限申請（第二階段 2-5；主管 11/26 Q3：業務可對任意平台／區域寫回饋 %，送主管審核；100 萬以上專案談也走這裡）。
快照 snap["gift"] = {"pct", "reason", "by", "at", "status": 待核准／核准／退回, "reviewed_by", "reviewed_at", "reject_reason"}
- 主管自己設定的加贈＝直接核准。
- 業務申請：與上一版同 % 且已核准 → 沿用核准；% 改了 → 重新待核准。
- 待核准時：不能送出訂檔、CUE 備註加紅字「尚待主管核准」。
本模組不 import streamlit；獨立新檔，避免 Streamlit Cloud 舊模組快取造成 ImportError。"""
from datetime import datetime

PENDING = "待核准"
APPROVED = "核准"
REJECTED = "退回"
BLOCK_TEXT = "加贈回饋待主管核准"


def _now(now=None):
    return (now or datetime.now()).strftime("%Y-%m-%d %H:%M")


def gift_of(snap):
    return (snap or {}).get("gift") or {}


def is_pending(snap):
    return gift_of(snap).get("status") == PENDING


def build_gift(pct, reason, user_name, *, by_supervisor, prev_snap=None, now=None):
    """這次存檔的 gift 欄位；pct 為 0／None → None（沒有加贈）。"""
    pct = int(pct or 0)
    if pct <= 0:
        return None
    prev = gift_of(prev_snap)
    if prev.get("pct") == pct and prev.get("status") in (APPROVED, PENDING):
        # 同 % 沿用上一版（主管開啟業務的待核准申請時也不會自動變核准，要按「核准加贈」留下紀錄）
        return dict(prev, reason=reason or prev.get("reason", ""))
    if by_supervisor:
        return {"pct": pct, "reason": reason or "", "by": user_name, "at": _now(now), "status": APPROVED,
                "reviewed_by": user_name, "reviewed_at": _now(now)}
    return {"pct": pct, "reason": reason or "", "by": user_name, "at": _now(now), "status": PENDING}


def mark_gift_reviewed(snap, user_name, approved, *, reason="", now=None):
    """主管核准／退回加贈申請（就地修改並回傳 snap）。"""
    g = dict(gift_of(snap))
    g.update({"status": APPROVED if approved else REJECTED, "reviewed_by": user_name, "reviewed_at": _now(now),
              "reject_reason": "" if approved else reason})
    snap["gift"] = g
    msg = f"主管核准加贈回饋 {g.get('pct')}%" if approved else f"主管退回加贈回饋 {g.get('pct')}%：{reason}"
    snap.setdefault("history", []).append({"v": snap.get("version", 0), "at": _now(now), "by": user_name,
                                           "changes": [msg]})
    return snap


def pending_remark(gift):
    """待核准（或被退回）時加在 CUE 備註最後的紅字；其他情況回 None。"""
    st = (gift or {}).get("status")
    if st == PENDING:
        return f"※本排程含加贈回饋 {gift.get('pct')}%，尚待主管核准，核准前僅供內部參考。"
    if st == REJECTED:
        return f"※本排程之加贈回饋 {gift.get('pct')}% 主管未核准，請調整後再存檔。"
    return None


def status_label(snap):
    g = gift_of(snap)
    return f"🎁加贈{g.get('pct')}%{g.get('status')}" if g else ""
