"""CUE 快照 → CUE號申請／訂檔草稿（第 4 期資料轉換；只組資料，不送出）。

對照 Ragic 訂檔表（forms12/17）實際用法（2026-10-13 讀 300 筆統計）：
- 收入子表一個平台一列：平台細項多寫平台層級「全家企頻／新鮮視／家樂福企頻」，製作費另一列「製作收入」；
  未見同平台依月份拆列 → 業績年月取該波開始月。
- 收入類別值：商品／公家／交換／統一（預設商品，交換合約＝交換）。
- 公司值：東吳／聲活／鉑霖／錄音室／聲活(采藝) → 預設取 CUE 格式；代理商（2008／凱絡）以聲活抬頭（Jonathan 2026-10-14）。
平台檔數：全省組合展開的六區列只計一次（Jonathan 2026-10-14），其餘列加總。
"""
from __future__ import annotations

from datetime import date

from ragic_booking import fields as rf

PLATFORM_LABEL = {"全家廣播": "全家企頻", "新鮮視": "新鮮視", "家樂福": "家樂福企頻"}
PROD_LABEL = "製作收入"
INCOME_CATEGORIES = ["商品", "公家", "交換", "統一"]
COMPANY_FROM_FORMAT = {"東吳": "東吳", "聲活": "聲活", "鉑霖": "鉑霖", "2008傳媒": "聲活", "凱絡": "聲活"}
AGENCY_MODES = ("代理商CUE", "代理商一鍵")
REGIONS6 = {"北區", "桃竹苗", "中區", "雲嘉南", "高屏", "東區"}


def default_company(snap):
    """訂檔「公司」預設：子公司格式＝格式名；代理商案（2008／凱絡，含一鍵模板）＝聲活。"""
    h = snap.get("header", {})
    if snap.get("mode") in AGENCY_MODES:
        return "聲活"
    return COMPANY_FROM_FORMAT.get(h.get("format"), "")


def count_spots(rows):
    """檔數：全家／新鮮視全省展開的六區列（同平台、秒數、類型、每日檔次，區域涵蓋六區）只計一次，其餘加總。"""
    groups = {}
    for r in rows:
        k = (r["platform"], r["seconds"], r.get("kind"), tuple(r.get("schedule") or ()), r["spots"])
        groups.setdefault(k, []).append(r)
    total = 0
    for (plat, _s, _k, _sch, spots), members in groups.items():
        regions = {m.get("region") for m in members}
        if plat in ("全家廣播", "新鮮視") and REGIONS6 <= regions:
            total += int(spots or 0) * (len(members) - len(REGIONS6) + 1)   # 六區算一次，多出的列照計
        else:
            total += sum(int(m.get("spots") or 0) for m in members)
    return total


def _d(v):
    """date／ISO 字串／{"__date__"} → yyyy/MM/dd。"""
    if isinstance(v, dict) and "__date__" in v:
        v = v["__date__"]
    if isinstance(v, str) and v:
        v = date.fromisoformat(v[:10])
    return v.strftime("%Y/%m/%d") if isinstance(v, date) else ""


def income_rows(wave, *, category="商品", company="", prod_cost=0):
    """單一波段的收入子表列（平台＋秒數一列）。"""
    ym = _d(wave.get("start"))[:7]
    groups, members = {}, {}
    for r in wave.get("rows", []):
        lbl = PLATFORM_LABEL.get(r["platform"], r["platform"])
        g = groups.setdefault((lbl, r["seconds"]), {"平台細項": lbl, "秒數": r["seconds"], "平台檔數": 0,
                                                    "實收金額未稅": 0, "業績年月": ym, "類別": category,
                                                    "公司": company})
        g["實收金額未稅"] += int(r.get("net") or 0)
        members.setdefault((lbl, r["seconds"]), []).append(r)
    for k, g in groups.items():
        g["平台檔數"] = count_spots(members[k])
    out = list(groups.values())
    if prod_cost:
        out.append({"平台細項": PROD_LABEL, "平台檔數": 0, "秒數": "", "實收金額未稅": int(prod_cost),
                    "業績年月": ym, "類別": category, "公司": company, "製作成本": ""})
    return out


def build_orders(snap, *, applicant="", company="", category="商品", 收款日期="", 發票開立日="", cue_no=""):
    """快照各波 → OrderDraft 清單（製作費只算在第 1 波）。客戶相關欄位取快照 customer。"""
    h = snap.get("header", {})
    cust = snap.get("customer") or {}
    company = company or default_company(snap)
    out = []
    for i, w in enumerate(snap.get("waves", [])):
        rows = w.get("rows", [])
        d = rf.OrderDraft()
        d.客戶編號 = cust.get("編號", "")
        d.客戶類別 = cust.get("類別", "")
        d.CUE號 = cue_no
        d.波段 = str(i + 1)
        d.申請人 = d.訂檔人 = applicant
        d.公司 = company
        d.產品名稱 = h.get("product") or cust.get("產品", "")
        d.客服 = list(cust.get("客服") or [])
        d.業務開發客戶 = cust.get("業務", "")
        d.業務主管 = cust.get("主管", "")
        d.平台 = list(dict.fromkeys(PLATFORM_LABEL.get(r["platform"], r["platform"]) for r in rows))
        d.執行開始日期 = _d(w.get("start"))
        d.執行結束日期 = _d(w.get("end"))
        d.CUE表秒數 = sorted({r["seconds"] for r in rows if r.get("seconds")})
        d.CUE表總檔數 = count_spots(rows) or None
        d.電台播證開立名稱 = f"{h.get('client') or cust.get('名稱', '')} {d.產品名稱}".strip()
        d.現折pct = cust.get("現折", "")
        d.退佣 = cust.get("退佣", "")
        d.收款日期 = 收款日期
        d.發票開立日業務 = 發票開立日
        d.收入明細 = income_rows(w, category=category, company=company,
                             prod_cost=(h.get("prod_cost") or 0) if i == 0 else 0)
        out.append(d)
    return out


def cue_apply_payload(snap, applicant=""):
    """CUE號申請表（forms13/4）建立內容：起走日＝第 1 波開始日、總波段＝波段數。"""
    cust = snap.get("customer") or {}
    waves = snap.get("waves", [])
    start = _d(waves[0].get("start")) if waves else ""
    return rf.cue_apply_payload_json(cust.get("編號", ""), start, str(len(waves)), applicant,
                                     snap.get("header", {}).get("product", ""))


def missing(snap, orders):
    """送出前必填盤點：{"CUE號申請": [...], "訂檔": [...]}（附件另計）。"""
    cust = snap.get("customer") or {}
    out = {"CUE號申請": [], "訂檔": []}
    if not cust.get("編號"):
        out["CUE號申請"].append("客戶編號（請先從 Ragic 帶入客戶）")
    for d in orders[:1]:
        m = rf.missing_required_order(d)
        # CUE號在核准時才申請，這裡不算缺
        # 製作收入列沒有檔數／秒數（實際訂檔亦然），不算缺
        prod = {f"收入第{i}列.{k}" for i, r in enumerate(d.收入明細, 1) if r["平台細項"] == PROD_LABEL
                for k in ("平台檔數", "秒數")}
        out["訂檔"] = [x for x in m.get("blocking", []) if not x.startswith("CUE號") and x not in prod]
    return out


def submit_booking(snap, orders, *, applicant="", attachments=None, submit=None):
    """依序送出各波訂檔（寫入正式 Ragic，呼叫端須先確認已開放寫入）。
    第 1 波：申請 CUE號 → 建訂檔；之後各波沿用同一 CUE號、各自建訂檔（波段 = 2, 3 …）。
    attachments：{波段索引 或 "all": {欄位ID: 檔案路徑}}，如 訂檔CUE表、客戶回簽檔。
    任一波失敗即停，回傳已完成結果（含 cueupload 的殘留 rid 偵測）。"""
    if submit is None:
        from ragic_booking.write import submit_full_order as submit
    attachments = attachments or {}
    waves = snap.get("waves", [])
    start = _d(waves[0].get("start")) if waves else ""
    cue_id, results = "", []
    for i, d in enumerate(orders):
        if cue_id:
            d.CUE號 = cue_id
        files = {**attachments.get("all", {}), **attachments.get(i, {})}
        r = submit(d, apply_cue=not d.CUE號, 起走日期=start, 總波段=str(len(orders)),
                   申請人=applicant, 產品名稱=d.產品名稱, attachments=files)
        results.append(r)
        cue_id = r.get("cue_id") or cue_id
        if not r.get("ok"):
            return {"ok": False, "cue_id": cue_id, "results": results, "error": f"第 {i + 1} 波：{r.get('error')}"}
    return {"ok": True, "cue_id": cue_id, "results": results, "error": "",
            "orders": [{"wave": i + 1, "rid": r.get("order_rid", ""), "action": "新增"} for i, r in enumerate(results)]}


# 更新既有訂檔時只改 CUE 帶來的欄位；勾選旗標、申請人、素材等營運端可能改過的欄位不動
_UPDATE_FIELDS = (rf.OrderF.平台, rf.OrderF.執行開始日期, rf.OrderF.執行結束日期, rf.OrderF.CUE表秒數,
                  rf.OrderF.CUE表總檔數, rf.OrderF.收款日期, rf.OrderF.發票開立日業務)


def _income_rowids(record):
    """讀回的訂檔紀錄 → {(平台細項, 秒數字串): 子表 row id}。"""
    out = {}
    for k, sub in (record or {}).items():
        if not str(k).startswith("_subtable_") or not isinstance(sub, dict):
            continue
        for rowid, row in sub.items():
            if isinstance(row, dict) and "平台細項" in row:
                out[(str(row.get("平台細項")), str(row.get("秒數") or ""))] = str(rowid)
    return out


def update_payload(d, record):
    """已訂檔波段的更新內容：CUE 相關欄位＋收入子表（同平台＋秒數更新原列，新的平台加新列）。"""
    full = rf.order_payload_json(d)
    p = {k: v for k, v in full.items() if k in _UPDATE_FIELDS}
    rowids = _income_rowids(record)
    sub_key = f"_subtable_{rf.OrderF.SUB_INCOME}"
    new_rows, n = {}, 0
    for _neg, row in (full.get(sub_key) or {}).items():
        key = (str(row.get(rf.OrderF.收入_平台細項, "")), str(row.get(rf.OrderF.收入_秒數, "")))
        if key in rowids:
            new_rows[rowids[key]] = row
        else:
            n += 1
            new_rows[f"-{n}"] = row
    if new_rows:
        p[sub_key] = new_rows
    return p


def update_booking(snap, orders, *, booking, attachments=None, applicant="",
                   reader=None, updater=None, uploader=None, submit=None):
    """已訂檔 CUE 調整後更新原訂檔（Jonathan 2026-10-14：不另開異動訂檔）。
    已有訂檔的波段：更新該筆（CUE 欄位＋收入子表）並重傳訂檔CUE表；新增的波段：以原 CUE號建新訂檔。
    回傳 {ok, cue_id, orders:[{wave, rid, action}], error}。"""
    from ragic_booking import write as rw
    reader = reader or rw.read_record
    updater = updater or rw.update_record
    uploader = uploader or rw.upload_file
    if submit is None:
        submit = rw.submit_full_order
    attachments = attachments or {}
    cue_id = booking.get("cue_id", "")
    by_wave = {int(o["wave"]): str(o["rid"]) for o in booking.get("orders", []) if o.get("rid")}
    start = _d((snap.get("waves") or [{}])[0].get("start"))
    out = []
    for i, d in enumerate(orders):
        d.CUE號 = cue_id
        files = {**attachments.get("all", {}), **attachments.get(i, {})}
        rid = by_wave.get(i + 1)
        if rid:
            res = updater(rf.FORM_ORDER, rid, update_payload(d, reader(rf.FORM_ORDER, rid)))
            if not res.ok:
                return {"ok": False, "cue_id": cue_id, "orders": out, "error": f"第 {i + 1} 波更新失敗：{res.error}"}
            cue_file = files.get(rf.OrderF.訂檔CUE表)
            if cue_file:
                up = uploader(rf.FORM_ORDER, rid, rf.OrderF.訂檔CUE表, cue_file)
                if not up.ok:
                    return {"ok": False, "cue_id": cue_id, "orders": out,
                            "error": f"第 {i + 1} 波訂檔CUE表上傳失敗：{up.error}"}
            out.append({"wave": i + 1, "rid": rid, "action": "更新"})
        else:
            r = submit(d, apply_cue=False, 起走日期=start, 總波段=str(len(orders)), 申請人=applicant,
                       產品名稱=d.產品名稱, attachments=files)
            if not r.get("ok"):
                return {"ok": False, "cue_id": cue_id, "orders": out, "error": f"第 {i + 1} 波新增失敗：{r.get('error')}"}
            out.append({"wave": i + 1, "rid": r.get("order_rid", ""), "action": "新增"})
    return {"ok": True, "cue_id": cue_id, "orders": out, "error": ""}
