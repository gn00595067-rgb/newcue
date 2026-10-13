# -*- coding: utf-8 -*-
"""CUE 快照 → CUE號申請／訂檔草稿（第 4 期資料轉換）。"""
from datetime import date

import cue_store as cs
from ragic_booking import fields as rf
from ragic_booking import order_from_cue as oc


def _snap(prod_cost=5000, customer=None):
    w1 = [cs._row("全家廣播", r, 15, 800, [800], net=n, lst=1) for r, n in (("北區", 60000), ("中區", 40000))]
    w1.append(cs._row("家樂福", "全省量販", 20, 300, [300], net=90000))
    w1.append(cs._row("家樂福", "全省超市", 20, 514, [514], net=0, kind="super"))
    w2 = [cs._row("新鮮視", "北區", 15, 100, [100], net=30000)]
    return cs.make_snapshot("年約季約細CUE",
                            {"client": "客戶甲", "product": "產品乙", "format": "聲活", "prod_cost": prod_cost},
                            [{"start": date(2027, 1, 4), "end": date(2027, 1, 31), "rows": w1},
                             {"start": date(2027, 3, 1), "end": date(2027, 3, 31), "rows": w2}],
                            customer=customer if customer is not None else
                            {"編號": "C01399", "類別": "直客", "業務": "王小明", "主管": "李主管",
                             "客服": ["陳客服"], "現折": "5", "退佣": "0", "名稱": "客戶甲股份有限公司"})


def test_income_rows_grouped_by_platform():
    snap = _snap()
    orders = oc.build_orders(snap, applicant="王小明")
    assert len(orders) == 2
    inc = {(r["平台細項"], r["秒數"]): r for r in orders[0].收入明細}
    assert inc[("全家企頻", 15)]["實收金額未稅"] == 100000 and inc[("全家企頻", 15)]["平台檔數"] == 1600
    assert inc[("家樂福企頻", 20)]["實收金額未稅"] == 90000 and inc[("家樂福企頻", 20)]["平台檔數"] == 814
    assert inc[("製作收入", "")]["實收金額未稅"] == 5000           # 製作費只在第 1 波
    assert all(r["平台細項"] != "製作收入" for r in orders[1].收入明細)
    o = orders[1]
    assert (o.波段, o.執行開始日期, o.公司, o.平台, o.CUE表秒數) == ("2", "2027/03/01", "聲活", ["新鮮視"], [15])
    assert orders[0].收入明細[0]["業績年月"] == "2027/01" and orders[0].收入明細[0]["類別"] == "商品"
    assert orders[0].電台播證開立名稱 == "客戶甲 產品乙" and orders[0].客服 == ["陳客服"]


def test_payloads_and_missing():
    snap = _snap()
    orders = oc.build_orders(snap, applicant="王小明", 收款日期="2027/02/28")
    p = rf.order_payload_json(orders[0])
    assert p[rf.OrderF.客戶編號] == "C01399" and p[rf.OrderF.公司] == "聲活"
    assert len(p[f"_subtable_{rf.OrderF.SUB_INCOME}"]) == 3
    ap = oc.cue_apply_payload(snap, "王小明")
    assert ap[rf.CueApplyF.起走日期] == "2027/01/04" and ap[rf.CueApplyF.總波段] == "2"
    assert oc.missing(snap, orders) == {"CUE號申請": [], "訂檔": []}


def test_missing_without_customer():
    snap = _snap(customer={})
    orders = oc.build_orders(snap)
    m = oc.missing(snap, orders)
    assert m["CUE號申請"] and any("客戶編號" in x for x in m["訂檔"])


def test_submit_booking_applies_cue_once():
    snap = _snap()
    orders = oc.build_orders(snap, applicant="王小明")
    calls = []

    def fake_submit(d, *, apply_cue, attachments, **kw):
        calls.append((d.波段, apply_cue, d.CUE號, sorted(attachments), kw["總波段"], kw["起走日期"]))
        return {"ok": True, "cue_id": d.CUE號 or "1160101", "order_rid": str(len(calls)), "error": ""}

    res = oc.submit_booking(snap, orders, applicant="王小明", submit=fake_submit,
                            attachments={"all": {"回簽": "a.pdf"}, 0: {"CUE表": "w1.xlsx"}, 1: {"CUE表": "w2.xlsx"}})
    assert res["ok"] and res["cue_id"] == "1160101"
    assert calls == [("1", True, "", ["CUE表", "回簽"], "2", "2027/01/04"),
                     ("2", False, "1160101", ["CUE表", "回簽"], "2", "2027/01/04")]


def test_submit_booking_stops_on_failure():
    snap = _snap()
    orders = oc.build_orders(snap)
    res = oc.submit_booking(snap, orders, submit=lambda d, **kw: {"ok": False, "cue_id": "", "error": "INVALID"})
    assert not res["ok"] and len(res["results"]) == 1 and "第 1 波" in res["error"]
