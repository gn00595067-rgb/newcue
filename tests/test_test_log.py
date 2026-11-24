# -*- coding: utf-8 -*-
"""測試期 CUE號紀錄（cue/6）與每月上限。"""
from datetime import datetime

from ragic_booking import test_log as tl
from ragic_booking.write import WriteResult

NOW = datetime(2026, 11, 6, 10, 0, tzinfo=tl._TPE)


def _ts(y, m, d, h=12):
    return datetime(y, m, d, h, tzinfo=tl._TPE).timestamp() * 1000


def test_month_count_uses_taipei_month_and_counts_unknown():
    rows = {"1": {"_dataTimestamp": _ts(2026, 11, 1, 0)},   # 台北 11/1 00:00（UTC 還是 10/31）→ 算本月
            "2": {"_dataTimestamp": _ts(2026, 10, 31, 23)},
            "3": {"_dataTimestamp": _ts(2026, 11, 5)},
            "4": {}}                                          # 讀不到時間 → 寧可多算
    assert tl.month_count(rows, NOW) == 3


def test_quota_block():
    rows = {str(i): {"_dataTimestamp": _ts(2026, 11, 2)} for i in range(15)}
    assert "15 筆上限" in tl.quota_block(15, getter=lambda url: rows, now=NOW)
    assert tl.quota_block(16, getter=lambda url: rows, now=NOW) == ""


def test_log_orders_updates_existing_row_and_merges():
    calls = []
    getter = lambda url: {"7": {"CUE號": "1151101", "訂檔單號": "OD001"}}   # noqa: E731
    tl.log_orders("1151101", ["OD001", "OD002"], getter=getter,
                  creator=lambda *a: calls.append(("c",) + a),
                  updater=lambda *a: calls.append(("u",) + a) or WriteResult(ok=True, form="cue/6"))
    assert calls == [("u", "cue/6", "7", {tl.LogF.訂檔單號: "OD001、OD002"})]


def test_log_orders_creates_row_when_missing():
    calls = []
    tl.log_orders("1151102", ["OD9"], getter=lambda url: {},
                  creator=lambda *a: calls.append(a), updater=lambda *a: None)
    assert calls == [("cue/6", {tl.LogF.CUE號: "1151102", tl.LogF.訂檔單號: "OD9"})]


def test_mark_need_once():
    assert tl.mark_need("") == tl.TEST_MARK
    assert tl.mark_need(tl.mark_need("11/06 提供")) == tl.TEST_MARK + "11/06 提供"
