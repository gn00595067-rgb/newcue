"""Ragic 寫入層測試（全 mock，不連網）：

- JSON 原生 payload 形狀（多值陣列 / _subtable_ 子表）
- 建立回傳容錯解析
- 刪除安全閘：只准刪本次執行親手建立的 rid，且拒絕時不發任何請求
- submit_full_order 端到端呼叫順序與 CUE 號回填
"""
import pytest

from ragic_booking import fields as rf
from ragic_booking import write as rw
from ragic_booking.fields import CustomerDraft, OrderDraft


# ---------------- JSON payload 形狀 ----------------
def _full_order() -> OrderDraft:
    d = OrderDraft(
        客戶編號="C01316", 客戶類別="直客", 公司="鉑霖", 申請人="A", 訂檔人="A",
        產品名稱="X", 平台=["全家企頻", "家樂福"], 執行開始日期="2026/10/01",
        執行結束日期="2026/10/31", CUE表秒數=[20, 30], CUE表總檔數=700,
        電台播證開立名稱="桃園衛生局 X", 現折pct="0", 退佣="0", 收款日期="2026/12/10",
    )
    d.收入明細 = [{"平台細項": "全家企頻", "平台檔數": 700, "秒數": 20,
                "實收金額未稅": 141525, "業績年月": "2026/10/01", "類別": "公家"}]
    d.素材明細 = [{"廣告篇名": "福利篇", "文案": ""}]
    return d


def test_order_payload_json_multivalue_are_lists():
    p = rf.order_payload_json(_full_order())
    assert p[rf.OrderF.平台] == ["全家企頻", "家樂福"]
    assert p[rf.OrderF.CUE表秒數] == ["20", "30"]
    assert p[rf.OrderF.文案] == ["無"]              # 預設「無」


def test_order_payload_json_subtable_shape():
    p = rf.order_payload_json(_full_order())
    inc = p[f"_subtable_{rf.OrderF.SUB_INCOME}"]
    assert inc["-1"][rf.OrderF.收入_類別] == "公家"
    assert inc["-1"][rf.OrderF.收入_平台細項] == "全家企頻"
    assert inc["-1"][rf.OrderF.收入_公司] == "鉑霖"        # 列沒帶 → 退回主檔公司
    mat = p[f"_subtable_{rf.OrderF.SUB_MATERIAL}"]
    assert mat["-1"][rf.OrderF.素材_廣告篇名] == "福利篇"
    assert rf.OrderF.素材_文案 not in mat["-1"]           # 空文案不送


def test_order_payload_json_omits_system_formula_fields():
    p = rf.order_payload_json(_full_order())
    for fid in (rf.OrderF.訂檔單號, rf.OrderF.CUE, rf.OrderF.總波段,
                rf.OrderF.統一編號, rf.OrderF.所有平台, rf.OrderF.平台檔數總計):
        assert fid not in p


def test_order_payload_json_income_row_uses_own_company():
    d = _full_order()
    d.收入明細[0]["公司"] = "瑞迪"                        # 列自帶公司優先
    p = rf.order_payload_json(d)
    assert p[f"_subtable_{rf.OrderF.SUB_INCOME}"]["-1"][rf.OrderF.收入_公司] == "瑞迪"


def test_cue_apply_payload_json_matches_flat():
    j = rf.cue_apply_payload_json("C01316", "2026/10/01", "1", "A", "X")
    assert j[rf.CueApplyF.客戶編號成交] == "C01316"
    assert j[rf.CueApplyF.客戶類型] == "成交客戶"
    assert rf.CueApplyF.CUE號 not in j and rf.CueApplyF.序號依據 not in j


def test_customer_payload_json_multivalue_are_lists():
    d = CustomerDraft(客戶名稱="新客戶", 產品名稱="P", 統一編號="12345678",
                      客戶類別="直客", 客服=["A", "B"], 付款方式=["匯款"])
    p = rf.customer_payload_json(d)
    assert p[rf.CustomerWriteF.客戶名稱] == "新客戶"
    assert p[rf.CustomerWriteF.客服] == ["A", "B"]
    assert p[rf.CustomerWriteF.付款方式] == ["匯款"]
    assert "1002571" not in p                            # 客戶編號系統編號不送


# ---------------- 建立回傳解析 ----------------
def test_parse_create_response_success():
    assert rw._parse_create_response({"status": "SUCCESS", "ragicId": 123}) == (True, "123", "")


def test_parse_create_response_rid_from_data_keys():
    ok, rid, err = rw._parse_create_response({"data": {"456": {"x": 1}}})
    assert ok and rid == "456" and err == ""


def test_parse_create_response_invalid():
    ok, rid, err = rw._parse_create_response({"status": "INVALID", "msg": "缺必填"})
    assert not ok and "INVALID" in err


def test_parse_create_response_non_dict():
    ok, rid, err = rw._parse_create_response("boom")
    assert not ok and rid == "" and "非預期" in err


# ---------------- 刪除安全閘 ----------------
def test_delete_rejects_untracked_without_network(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(rw.requests, "delete",
                        lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    with pytest.raises(rw.RagicWriteError):
        rw.delete_record("forms12/17", "999999")        # 未建立
    assert called["n"] == 0                              # 根本沒發請求


def test_delete_rejects_non_digit(monkeypatch):
    monkeypatch.setattr(rw.requests, "delete",
                        lambda *a, **k: pytest.fail("不該發請求"))
    with pytest.raises(rw.RagicWriteError):
        rw.delete_record("forms12/17", "abc")


def test_delete_allows_tracked_rid(monkeypatch):
    class _Resp:
        status_code = 200

        @staticmethod
        def json():
            return {"status": "SUCCESS"}

    sent = {}
    monkeypatch.setattr(rw.requests, "delete",
                        lambda url, **k: (sent.update(url=url), _Resp())[1])
    rw._CREATED_THIS_RUN.add(("forms12/17", "77"))       # 模擬本次剛建立
    res = rw.delete_record("forms12/17", "77")
    assert res.ok and "forms12/17/77" in sent["url"]
    assert ("forms12/17", "77") not in rw._CREATED_THIS_RUN  # 刪後移出白名單


# ---------------- submit_full_order 編排順序 ----------------
def test_submit_full_order_with_attachments_uses_multipart_create(monkeypatch):
    """有附件時：申請 CUE → 取號 → multipart『一次建檔＋帶附件』（不先建後補）。

    這正是修掉『Ragic 附件必填、先建後補被 INVALID 擋』的關鍵路徑。
    """
    calls: list[str] = []

    def fake_create(form, payload, flags=None):
        calls.append(f"create:{form}")
        return rw.WriteResult(ok=True, form=form, rid="900", raw={})

    def fake_extract(form, rid, raw):
        calls.append("extract_cue")
        return "1151003"

    def fake_create_files(form, form_fields, files_map, flags=None):
        calls.append(f"create_files:{form}:{sorted(files_map)}")
        return rw.WriteResult(ok=True, form=form, rid="901", raw={})

    def fake_upload(form, rid, field_id, path, filename=None):
        calls.append(f"upload:{field_id}")           # 不該被呼叫
        return rw.WriteResult(ok=True, form=form, rid=rid)

    monkeypatch.setattr(rw, "create_record", fake_create)
    monkeypatch.setattr(rw, "_extract_cue_id", fake_extract)
    monkeypatch.setattr(rw, "create_record_with_files", fake_create_files)
    monkeypatch.setattr(rw, "upload_file", fake_upload)

    order = _full_order()
    order.CUE號 = ""                                     # 逼它先申請
    out = rw.submit_full_order(
        order, apply_cue=True, 起走日期="2026/10/01", 總波段="1",
        申請人="A", 產品名稱="X",
        attachments={rf.OrderF.訂檔CUE表: "/x/a.pdf", rf.OrderF.客戶回簽檔: "/x/b.pdf"},
    )
    assert out["ok"] is True
    assert out["cue_id"] == "1151003" and out["order_rid"] == "901"
    assert order.CUE號 == "1151003"                      # 真實 CUE 號已回填進訂檔
    assert calls == [
        f"create:{rf.FORM_CUE_APPLY}", "extract_cue",
        f"create_files:{rf.FORM_ORDER}:"
        f"{sorted([rf.OrderF.訂檔CUE表, rf.OrderF.客戶回簽檔])}",
    ]
    assert not any(c.startswith("upload:") for c in calls)   # 不再走先建後補


def test_submit_full_order_without_attachments_uses_json_create(monkeypatch):
    """無附件時：仍走既有 JSON 建檔（子表/多值 JSON 原生格式）。"""
    calls: list[str] = []

    def fake_create(form, payload, flags=None):
        calls.append(f"create:{form}")
        return rw.WriteResult(ok=True, form=form, rid="902", raw={})

    monkeypatch.setattr(rw, "create_record", fake_create)
    monkeypatch.setattr(rw, "create_record_with_files",
                        lambda *a, **k: pytest.fail("無附件不該走 multipart"))

    order = _full_order()
    out = rw.submit_full_order(order, apply_cue=False, attachments={})
    assert out["ok"] is True and out["order_rid"] == "902"
    assert calls == [f"create:{rf.FORM_ORDER}"]


def test_find_leaked_order_rid_matches_recent_signature(monkeypatch):
    """建檔回 ERROR 時，用 產品名稱+播證抬頭+近期 回搜殘留 rid。"""
    import time
    now = time.time() * 1000.0

    class _Resp:
        status_code = 200

        @staticmethod
        def json():
            return {
                "678": {"產品名稱": "__CLAUDE_FIELD_TEST__ 忽略",
                        "電台播證開立名稱": "X", "_dataTimestamp": now - 1000},
                "500": {"產品名稱": "別的單", "_dataTimestamp": now},          # 不同名
                "300": {"產品名稱": "__CLAUDE_FIELD_TEST__ 忽略",
                        "電台播證開立名稱": "X", "_dataTimestamp": now - 999999},  # 太舊
            }

    monkeypatch.setattr(rw.requests, "get", lambda *a, **k: _Resp())
    order = _full_order()
    order.產品名稱 = "__CLAUDE_FIELD_TEST__ 忽略"
    order.電台播證開立名稱 = "X"
    assert rw._find_leaked_order_rid(order) == "678"       # 取近期相符最新一筆


def test_submit_full_order_surfaces_leaked_rid_on_error(monkeypatch):
    """建檔回 ERROR 且找到疑似紀錄、但讀回不完整 → 失敗並回報 rid 請人確認；
    10-22 起不再登記白名單、不提示刪除（Post-workflow 錯誤時紀錄常是好的，見 test_order_from_cue）。"""
    monkeypatch.setattr(rw, "create_record",
                        lambda *a, **k: rw.WriteResult(ok=False, form=rf.FORM_ORDER,
                                                       error="status=ERROR post-workflow"))
    monkeypatch.setattr(rw, "_find_leaked_order_rid", lambda order: "678")
    monkeypatch.setattr(rw, "read_record", lambda form, rid: {})
    order = _full_order()
    out = rw.submit_full_order(order, apply_cue=False, attachments={})
    assert out["ok"] is False and out["leaked_rid"] == "678" and "#678" in out["error"]
    assert (rf.FORM_ORDER, "678") not in rw._CREATED_THIS_RUN


def test_submit_full_order_stops_on_cue_failure(monkeypatch):
    def fake_create(form, payload, flags=None):
        return rw.WriteResult(ok=False, form=form, error="被擋")

    monkeypatch.setattr(rw, "create_record", fake_create)
    order = _full_order()
    order.CUE號 = ""
    out = rw.submit_full_order(order, apply_cue=True, 起走日期="2026/10/01")
    assert out["ok"] is False and out["order_rid"] == ""
    assert "CUE" in out["error"]
