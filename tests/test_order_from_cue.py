# -*- coding: utf-8 -*-
"""CUE 快照 → CUE號申請／訂檔草稿（第 4 期資料轉換）。"""
import importlib
import re
from datetime import date

import pytest

import cue_store as cs
from ragic_booking import fields as rf
from ragic_booking import order_from_cue as oc


@pytest.fixture(autouse=True)
def _real_oc():
    """畫面測試外殼（ui_harness_ragic）會把 submit_booking／update_booking 換成假的且不還原；
    先跑畫面測試時本檔會測到假函式 → 每個測試前重新載入模組。"""
    importlib.reload(oc)


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
    assert orders[0].收入明細[0]["業績年月"] == "2027/01/04" and orders[0].收入明細[0]["類別"] == "商品"
    assert orders[0].電台播證開立名稱 == "客戶甲-產品乙" and orders[0].客服 == ["陳客服"]


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


# ---------------------------------------------------------------- 訂檔資料補齊（spec：docs/specs/訂檔資料補齊.md）
def test_missing_says_where_to_fill():
    """宜歆 10/21：只寫缺什麼找不到去哪填 → 每項附上在訂檔區哪一段。"""
    snap = _snap(customer={})
    snap["header"]["client"] = snap["header"]["product"] = ""
    m = oc.missing(snap, oc.build_orders(snap))
    items = m["CUE號申請"] + m["訂檔"]
    assert "客戶編號（① 客戶：搜尋帶入）" in items
    assert "客戶類別（① 客戶）" in items and "電台播證開立名稱（③ 播證）" in items
    assert "收款日期（② 開票收款）" in items and "客服（① 客戶）" in items


def test_payment_date_defaults_from_cue_per_wave():
    snap = _snap()
    snap["waves"][0]["payment_date"] = {"__date__": "2027-02-28"}
    snap["header"]["payment_date"] = {"__date__": "2027-04-30"}
    orders = oc.build_orders(snap, applicant="王小明")
    assert [o.收款日期 for o in orders] == ["2027/02/28", "2027/04/30"]       # 波段自己的優先，沒有用 header
    assert oc.missing(snap, orders)["訂檔"] == []
    assert [o.收款日期 for o in oc.build_orders(snap, 收款日期="2027/05/31")] == ["2027/05/31"] * 2   # 手填覆蓋


def test_partial_wave_missing_marks_wave():
    snap = _snap()
    snap["waves"][0]["payment_date"] = {"__date__": "2027-02-28"}
    assert oc.missing(snap, oc.build_orders(snap, applicant="王小明"))["訂檔"] == ["第2波 收款日期（② 開票收款）"]


def test_overrides_category_service_and_cert_name():
    snap = _snap(customer={"編號": "C1", "名稱": "二零零八傳媒", "類別": "", "主管": "李", "客服": []})
    snap["header"]["client"] = "統一企業股份有限公司"
    o = oc.build_orders(snap, applicant="王小明", 收款日期="2027/02/28", 客戶類別="廣代-商品", 客服=["豐季妍"],
                        播證名稱=["", "統一企業股份有限公司-第二波"])
    assert o[0].客戶類別 == "廣代-商品" and o[0].客服 == ["豐季妍"]
    assert o[0].電台播證開立名稱 == "統一企業股份有限公司-產品乙"            # 廣告主，不是代理商
    assert o[1].電台播證開立名稱 == "統一企業股份有限公司-第二波"
    assert oc.missing(snap, o)["訂檔"] == []
    assert {x.電台播證開立名稱 for x in oc.build_orders(snap, 播證名稱="同名")} == {"同名"}


def test_notify_fields_follow_qp_platform():
    snap = _snap()
    o = oc.build_orders(snap)
    assert o[0].平台2 == "企頻" and "企頻小組" in o[0].通知部門 and len(o[0].通知個人) == 7   # 全家企頻
    assert o[1].平台2 == "" and o[1].通知部門 == "財務處+媒體處" and len(o[1].通知個人) == 5  # 只有新鮮視
    p = rf.order_payload_json(o[0])
    assert p[rf.OrderF.通知部門] == "財務處+媒體處+企頻小組" and len(p[rf.OrderF.通知個人]) == 7


def test_need_row_created_and_appended_on_update():
    snap = _snap(prod_cost=0)
    o = oc.build_orders(snap, 需求說明="10/21 提供訂檔CUE表+回簽")
    need_key = f"_subtable_{rf.OrderF.SUB_NEED}"
    row = rf.order_payload_json(o[0])[need_key]["-1"]
    assert row[rf.OrderF.需求_說明] == "10/21 提供訂檔CUE表+回簽"
    assert re.fullmatch(r"\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}", row[rf.OrderF.需求_建立時間])   # 實際資料 436/436 有建立時間
    rec = {need_key: {"700": {"需求或狀況說明": "營運寫的"}}}
    p = oc.update_payload(o[0], rec)
    assert set(p[need_key]) == {"-1"}                                                # 新增一列，700 不動
    assert need_key not in oc.update_payload(oc.build_orders(snap)[0], rec)            # 留白不送


def test_update_zeroes_income_rows_removed_from_cue():
    snap = _snap(prod_cost=0)
    o = oc.build_orders(snap)[1]                                       # 第 2 波只剩新鮮視
    rec = {"_subtable_1015394": {"901": {"平台細項": "新鮮視", "秒數": "15"},
                                 "902": {"平台細項": "全家企頻", "秒數": "15"},
                                 "903": {"平台細項": "廣播", "秒數": "30"}}}   # 營運手加
    sub = oc.update_payload(o, rec)["_subtable_1015394"]
    assert sub["902"] == {rf.OrderF.收入_平台檔數: "0", rf.OrderF.收入_實收金額未稅: "0"}
    assert "903" not in sub and sub["901"][rf.OrderF.收入_平台檔數] == "100"


def test_customer_category_options_match_ragic():
    assert rf.CUSTOMER_CATEGORY_OPTIONS == ["直客", "廣代", "廣代-商品", "廣代-建案"]


def test_cue_apply_carries_save_serial():
    """10-21 實測：CUE號申請表「Cue表模擬編號」空白 → Ragic ERROR（更新成交CUE 靠它回寫存檔）。"""
    snap = _snap()
    assert oc.cue_apply_payload(snap, "王小明", serial="20261021-001")[rf.CueApplyF.Cue表模擬編號] == "20261021-001"
    got = []
    oc.submit_booking(snap, oc.build_orders(snap), serial="20261021-001",
                      submit=lambda d, **kw: (got.append(kw["模擬編號"]), {"ok": True, "cue_id": "1", "order_rid": "9"})[1])
    assert got == ["20261021-001", "20261021-001"]


def test_submit_full_order_reports_leaked_cue_apply(monkeypatch):
    from ragic_booking import write as rw
    sent = {}

    def fake_create(form, payload, flags=None):
        sent[form] = payload
        return rw.WriteResult(ok=False, form=form, rid="88", error="Ragic 拒絕（status=ERROR）：條件欄位值不可為空")

    monkeypatch.setattr(rw, "create_record", fake_create)
    d = oc.build_orders(_snap())[0]
    res = rw.submit_full_order(d, apply_cue=True, 起走日期="2027/01/04", 模擬編號="20261021-001")
    assert not res["ok"] and res["leaked_rid"] == "88" and "#88" in res["error"]
    assert sent[rf.FORM_CUE_APPLY][rf.CueApplyF.Cue表模擬編號] == "20261021-001"



def test_discount_rebate_default_zero_and_required():
    """訂檔表現折／退佣紅星必填；客戶主檔現折 481/500 空白 → 預設 0，畫面可改（小數，2%＝0.02）。"""
    snap = _snap(customer={"編號": "C1", "名稱": "甲", "主管": "李", "類別": "直客", "客服": ["陳"],
                           "現折": "", "退佣": "0.15", "統編": "12345678", "付款條件": "播畢付款"})
    o = oc.build_orders(snap, applicant="王", 收款日期="2027/02/28")[0]
    assert (o.現折pct, o.退佣) == ("0", "0.15")
    p = rf.order_payload_json(o)
    assert p[rf.OrderF.現折pct] == "0" and p[rf.OrderF.統一編號] == "12345678" and p[rf.OrderF.付款條件] == "播畢付款"
    assert oc.build_orders(snap, 現折="2%", 退佣="20")[0].現折pct == "0.02"
    assert [oc.pct(x) for x in ("0.02", "2%", "2", "", "0", "10％")] == ["0.02", "0.02", "0.02", "", "0", "0.1"]
    o.現折pct = ""
    assert "現折" in rf.missing_required_order(o)["blocking"][0]


def test_income_cost_columns_zero_on_create_untouched_on_update():
    snap = _snap(prod_cost=5000)
    o = oc.build_orders(snap)[0]
    rows = rf.order_payload_json(o)[f"_subtable_{rf.OrderF.SUB_INCOME}"]
    for r in rows.values():
        assert r[rf.OrderF.收入_製作成本] == r[rf.OrderF.收入_配音員費用] == r[rf.OrderF.收入_其他成本] == "0"
        assert rf.OrderF.收入_成本 not in r                                   # 成本由營運填
    rec = {"_subtable_1015394": {"901": {"平台細項": "全家企頻", "秒數": "15"}}}
    sub = oc.update_payload(o, rec)["_subtable_1015394"]
    assert rf.OrderF.收入_製作成本 not in sub["901"] and rf.OrderF.收入_配音員費用 not in sub["901"]
    new = [v for k, v in sub.items() if k.startswith("-")]
    assert new and all(v[rf.OrderF.收入_其他成本] == "0" for v in new)       # 新加的列照送 0


def test_copywriter_and_material_note():
    o = oc.build_orders(_snap(), 文案=["玉琳"], 素材走法="兩支素材平均輪播")[0]
    p = rf.order_payload_json(o)
    assert p[rf.OrderF.文案] == ["玉琳"] and p[rf.OrderF.素材走法] == "兩支素材平均輪播"
    assert rf.order_payload_json(oc.build_orders(_snap())[0])[rf.OrderF.文案] == ["無"]


# ---------------------------------------------------------------- 素材子表（Jonathan 10-21：業務送訂檔時上傳，選填）
def test_material_rows_payload_and_file_keys():
    o = oc.build_orders(_snap(), 素材=[{"廣告篇名": "A篇.30秒"}, {"廣告篇名": "B篇(後補)"}])
    assert len(o) == 2 and all(x.素材明細 == [{"廣告篇名": "A篇.30秒"}, {"廣告篇名": "B篇(後補)"}] for x in o)
    t = dict(rf.order_form_tuples(o[0]))
    assert t[f"{rf.OrderF.素材_廣告篇名}_-1"] == "A篇.30秒" and t[f"{rf.OrderF.素材_廣告篇名}_-2"] == "B篇(後補)"
    assert f"{rf.OrderF.素材_文案}_-1" not in t                                     # 文案是檔案欄，不送文字
    assert rf.material_file_keys(2) == (f"{rf.OrderF.素材_音檔}_-2", f"{rf.OrderF.素材_文案}_-2")
    assert not oc.build_orders(_snap())[0].素材明細                                  # 選填：沒放就沒有素材列


def test_submit_full_order_sends_material_files(monkeypatch):
    from ragic_booking import write as rw
    got = {}

    def fake_files(form, tuples, files_map, flags=None):
        got.update(tuples=tuples, files=files_map)
        return rw.WriteResult(ok=True, form=form, rid="70")

    monkeypatch.setattr(rw, "create_record_with_files", fake_files)
    d = oc.build_orders(_snap(), 素材=[{"廣告篇名": "A篇"}])[0]
    d.CUE號 = "1160101"
    aud, cp = rf.material_file_keys(1)
    res = rw.submit_full_order(d, apply_cue=False, attachments={rf.OrderF.訂檔CUE表: "c.xlsx", aud: "a.mp3", cp: "c.docx"})
    assert res["ok"] and got["files"] == {rf.OrderF.訂檔CUE表: "c.xlsx", aud: "a.mp3", cp: "c.docx"}
    assert (f"{rf.OrderF.素材_廣告篇名}_-1", "A篇") in got["tuples"]


def test_update_booking_appends_material_rows():
    snap = _snap(prod_cost=0)
    orders = oc.build_orders(snap, 素材=[{"廣告篇名": "新篇"}])
    aud, _cp = rf.material_file_keys(1)
    added = []

    class R:
        ok, error = True, ""

    res = oc.update_booking(
        snap, orders, booking={"cue_id": "1160101", "orders": [{"wave": 1, "rid": "55"}, {"wave": 2, "rid": "56"}]},
        attachments={"all": {rf.OrderF.訂檔CUE表: "cue.xlsx", aud: "new.mp3"}},
        reader=lambda f, r: {}, updater=lambda f, r, p: R(), uploader=lambda *a: R(),
        adder=lambda form, rid, tuples, files: (added.append((rid, tuples, files)), R())[1])
    assert res["ok"]
    assert added == [(rid, [(f"{rf.OrderF.素材_廣告篇名}_-1", "新篇")], {aud: "new.mp3"}) for rid in ("55", "56")]
    # 沒放素材 → 不追加
    added.clear()
    oc.update_booking(snap, oc.build_orders(snap), booking={"cue_id": "1", "orders": [{"wave": 1, "rid": "55"}]},
                      reader=lambda f, r: {}, updater=lambda f, r, p: R(), uploader=lambda *a: R(),
                      submit=lambda d, **k: {"ok": True, "order_rid": "9"},
                      adder=lambda *a: (added.append(a), R())[1])
    assert added == []


def test_defaults_derived_from_cue_and_customer():
    """Jonathan 10-21：能從 CUE／客戶判斷的就自動帶。"""
    snap = _snap()
    o = oc.build_orders(snap)
    assert (o[0].平台, o[0].CUE表秒數, o[0].CUE表總檔數) == (["全家企頻", "家樂福企頻"], [15, 20], 1600 + 814)
    assert (o[1].平台, o[1].CUE表秒數, o[1].執行結束日期) == (["新鮮視"], [15], "2027/03/31")
    assert oc.default_category(snap) == "商品"
    snap["customer"]["產業別"] = "公家機關"
    assert oc.default_category(snap) == "公家"
    assert oc.default_category(_snap(customer={"名稱": "二零零八傳媒", "產品": "統一陽光"})) == "統一"
    assert [oc.default_material_note(n) for n in (0, 1, 2, 4)] == ["", "單支素材無走法", "兩支素材平均輪播", "四支素材平均輪播"]
