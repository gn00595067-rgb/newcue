# -*- coding: utf-8 -*-
"""贈檔權限申請（第二階段 2-5）。"""
import gift_review as gr


def test_業務申請待核准_主管直接核准():
    g = gr.build_gift(10, "年底掃單", "小花", by_supervisor=False)
    assert g["status"] == gr.PENDING and g["pct"] == 10
    assert gr.build_gift(10, "", "主管", by_supervisor=True)["status"] == gr.APPROVED
    assert gr.build_gift(0, "", "小花", by_supervisor=False) is None


def test_同百分比沿用核准_改了重新送審():
    prev = {"gift": {"pct": 10, "status": gr.APPROVED, "by": "小花"}}
    assert gr.build_gift(10, "x", "小花", by_supervisor=False, prev_snap=prev)["status"] == gr.APPROVED
    assert gr.build_gift(15, "x", "小花", by_supervisor=False, prev_snap=prev)["status"] == gr.PENDING
    rej = {"gift": {"pct": 10, "status": gr.REJECTED}}
    assert gr.build_gift(10, "x", "小花", by_supervisor=False, prev_snap=rej)["status"] == gr.PENDING


def test_主管審核與備註():
    snap = {"gift": gr.build_gift(10, "掃單", "小花", by_supervisor=False), "version": 2}
    assert gr.is_pending(snap) and "尚待主管核准" in gr.pending_remark(snap["gift"])
    gr.mark_gift_reviewed(snap, "主管", False, reason="太多")
    assert snap["gift"]["status"] == gr.REJECTED and "未核准" in gr.pending_remark(snap["gift"])
    gr.mark_gift_reviewed(snap, "主管", True)
    assert snap["gift"]["status"] == gr.APPROVED and gr.pending_remark(snap["gift"]) is None
    assert snap["history"][-1]["changes"] == ["主管核准加贈回饋 10%"]


def test_主管開啟待核准申請不會自動核准():
    prev = {"gift": {"pct": 10, "status": gr.PENDING, "by": "小花"}}
    assert gr.build_gift(10, "", "主管", by_supervisor=True, prev_snap=prev)["status"] == gr.PENDING
    assert gr.build_gift(12, "", "主管", by_supervisor=True, prev_snap=prev)["status"] == gr.APPROVED
