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


def test_cue_apply_sends_customer_name_and_supervisor():
    """10/16 實測 INVALID：CUE號申請表的「客戶名稱」「主管」必填，API 建檔 doLinkLoad 不帶 → 要明送。"""
    snap = _snap()
    ap = oc.cue_apply_payload(snap, "王小明")
    F = rf.CueApplyF
    assert ap[F.客戶名稱] == ap[F.客戶名稱成交] == "客戶甲股份有限公司"
    assert ap[F.主管] == ap[F.主管成交] == "李主管"
    assert ap[F.業務成交] == ["王小明"] and ap[F.產品名稱] == "產品乙"
    p = rf.order_payload_json(oc.build_orders(snap)[0])
    assert p[rf.OrderF.客戶] == "客戶甲股份有限公司" and p[rf.OrderF.業務主管] == "李主管"


def test_submit_full_order_passes_customer_to_cue_apply(monkeypatch):
    from ragic_booking import write as rw
    sent = {}

    def fake_create(form, payload, flags=None):
        sent[form] = payload
        return rw.WriteResult(ok=True, form=form, rid="9", raw={"data": {rf.CueApplyF.CUE號: "1151099"}})

    monkeypatch.setattr(rw, "create_record", fake_create)
    d = oc.build_orders(_snap())[0]
    res = rw.submit_full_order(d, apply_cue=True, 起走日期="2027/01/04", 申請人="王小明", 產品名稱=d.產品名稱)
    assert res["ok"] and res["cue_id"] == "1151099"
    ap = sent[rf.FORM_CUE_APPLY]
    assert ap[rf.CueApplyF.客戶名稱] == "客戶甲股份有限公司" and ap[rf.CueApplyF.主管] == "李主管"


def test_missing_flags_customer_master_without_supervisor():
    snap = _snap(customer={"編號": "C01399", "名稱": "客戶甲", "主管": ""})
    m = oc.missing(snap, oc.build_orders(snap))
    assert any("主管" in x for x in m["CUE號申請"])


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


def test_national_spots_counted_once():
    regs = ["北區", "桃竹苗", "中區", "雲嘉南", "高屏", "東區"]
    rows = [cs._row("全家廣播", r, 15, 800, [400, 400], net=10) for r in regs]
    rows.append(cs._row("新鮮視", "北區", 15, 100, [50, 50], net=5))
    rows.append(cs._row("新鮮視", "中區", 15, 100, [50, 50], net=5))       # 非全省兩區：加總
    assert oc.count_spots(rows) == 800 + 200
    w = {"start": date(2027, 1, 4), "rows": rows}
    inc = {r["平台細項"]: r["平台檔數"] for r in oc.income_rows(w)}
    assert inc == {"全家企頻": 800, "新鮮視": 200}


def test_agency_company_is_shenghuo():
    for mode, fmt in (("代理商CUE", "凱絡"), ("代理商一鍵", "2008 全家單組"), ("年約季約細CUE", "2008傳媒")):
        snap = cs.make_snapshot(mode, {"format": fmt}, [])
        assert oc.default_company(snap) == "聲活"
    assert oc.default_company(cs.make_snapshot("一般CUE", {"format": "鉑霖"}, [])) == "鉑霖"


def test_update_booking_updates_existing_rows():
    snap = _snap(prod_cost=0)
    orders = oc.build_orders(snap, applicant="王小明")
    rec = {"_subtable_1015394": {"901": {"平台細項": "全家企頻", "秒數": "15", "平台檔數": "100"},
                                 "902": {"平台細項": "家樂福企頻", "秒數": "20", "平台檔數": "50"}}}
    sent, uploads, created = [], [], []

    class R:
        def __init__(self, ok=True): self.ok, self.error = ok, ""

    res = oc.update_booking(
        snap, orders, booking={"cue_id": "1160101", "orders": [{"wave": 1, "rid": "55"}]},
        attachments={"all": {rf.OrderF.訂檔CUE表: "cue.xlsx"}},
        reader=lambda form, rid: rec,
        updater=lambda form, rid, p: (sent.append((rid, p)), R())[1],
        uploader=lambda form, rid, fid, path: (uploads.append((rid, fid, path)), R())[1],
        submit=lambda d, **kw: (created.append((d.波段, d.CUE號, kw["apply_cue"])), {"ok": True, "order_rid": "77"})[1])
    assert res["ok"] and res["orders"] == [{"wave": 1, "rid": "55", "action": "更新"},
                                           {"wave": 2, "rid": "77", "action": "新增"}]
    rid, p = sent[0]
    sub = p["_subtable_1015394"]
    assert set(sub) == {"901", "902"}                                   # 既有列就地更新，不新增重複列
    assert sub["901"][rf.OrderF.收入_平台檔數] == "1600"
    assert rf.OrderF.回簽 not in p and rf.OrderF.申請人 not in p          # 營運端欄位不覆蓋
    assert uploads == [("55", rf.OrderF.訂檔CUE表, "cue.xlsx")]
    assert created == [("2", "1160101", False)]                         # 新增波段沿用原 CUE號


def test_update_booking_stops_on_error():
    snap = _snap()
    orders = oc.build_orders(snap)

    class R:
        ok, error = False, "INVALID"

    res = oc.update_booking(snap, orders, booking={"cue_id": "X", "orders": [{"wave": 1, "rid": "55"}]},
                            reader=lambda f, r: {}, updater=lambda f, r, p: R())
    assert not res["ok"] and "第 1 波更新失敗" in res["error"]
