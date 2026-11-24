# -*- coding: utf-8 -*-
"""預算 % 連動（第二階段 A1，spec docs/specs/第二階段A批小修.md）。"""
from share_rebalance import rebalance_shares


def test_三平台依序填_先填的不會跑掉():
    v, m = rebalance_shares({"rad": 30, "fv": 34, "cf": 33}, "rad", [])
    assert v == {"rad": 30, "fv": 35, "cf": 35} and m == ["rad"]
    v["fv"] = 30
    v, m = rebalance_shares(v, "fv", m)
    assert v == {"rad": 30, "fv": 30, "cf": 40} and m == ["rad", "fv"]


def test_手填滿了_最早填的吸收差額():
    v, m = rebalance_shares({"rad": 30, "fv": 30, "cf": 50}, "cf", ["rad", "fv"])
    assert m == ["fv", "cf"]
    assert v == {"rad": 20, "fv": 30, "cf": 50}


def test_兩平台_另一個自動補():
    v, m = rebalance_shares({"a": 60, "b": 50}, "a", [])
    assert v == {"a": 60, "b": 40}
    v["b"] = 25
    v, m = rebalance_shares(v, "b", m)
    assert v == {"a": 75, "b": 25} and m == ["b"]


def test_單一項目固定100():
    assert rebalance_shares({"a": 40}, "a", ["a"]) == ({"a": 100}, [])


def test_尾差給最後一個_總和100():
    v, _ = rebalance_shares({"a": 1, "b": 0, "c": 0, "d": 0}, "a", [])
    assert v == {"a": 1, "b": 33, "c": 33, "d": 33}
    assert sum(v.values()) == 100


def test_手填超過100_其他歸0():
    v, _ = rebalance_shares({"a": 70, "b": 50, "c": 0}, "b", ["a"])
    assert v["c"] == 0 and sum(v.values()) == 120
