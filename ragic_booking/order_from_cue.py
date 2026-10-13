"""CUE 快照 → CUE號申請／訂檔草稿（第 4 期資料轉換；只組資料，不送出）。

對照 Ragic 訂檔表（forms12/17）實際用法（2026-10-13 讀 300 筆統計）：
- 收入子表一個平台一列：平台細項多寫平台層級「全家企頻／新鮮視／家樂福企頻」，製作費另一列「製作收入」；
  未見同平台依月份拆列 → 業績年月取該波開始月。
- 收入類別值：商品／公家／交換／統一（預設商品，交換合約＝交換）。
- 公司值：東吳／聲活／鉑霖／錄音室／聲活(采藝) → 預設取 CUE 格式。
平台檔數＝該平台各列檔次加總（全省展開的六區列各自計入，與 cue/2「總檔數」同口徑；待營運確認）。
"""
from __future__ import annotations

from datetime import date

from ragic_booking import fields as rf

PLATFORM_LABEL = {"全家廣播": "全家企頻", "新鮮視": "新鮮視", "家樂福": "家樂福企頻"}
PROD_LABEL = "製作收入"
INCOME_CATEGORIES = ["商品", "公家", "交換", "統一"]
COMPANY_FROM_FORMAT = {"東吳": "東吳", "聲活": "聲活", "鉑霖": "鉑霖"}


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
    groups = {}
    for r in wave.get("rows", []):
        lbl = PLATFORM_LABEL.get(r["platform"], r["platform"])
        g = groups.setdefault((lbl, r["seconds"]), {"平台細項": lbl, "秒數": r["seconds"], "平台檔數": 0,
                                                    "實收金額未稅": 0, "業績年月": ym, "類別": category,
                                                    "公司": company})
        g["平台檔數"] += int(r.get("spots") or 0)
        g["實收金額未稅"] += int(r.get("net") or 0)
    out = list(groups.values())
    if prod_cost:
        out.append({"平台細項": PROD_LABEL, "平台檔數": 0, "秒數": "", "實收金額未稅": int(prod_cost),
                    "業績年月": ym, "類別": category, "公司": company, "製作成本": ""})
    return out


def build_orders(snap, *, applicant="", company="", category="商品", 收款日期="", 發票開立日="", cue_no=""):
    """快照各波 → OrderDraft 清單（製作費只算在第 1 波）。客戶相關欄位取快照 customer。"""
    h = snap.get("header", {})
    cust = snap.get("customer") or {}
    company = company or COMPANY_FROM_FORMAT.get(h.get("format"), "")
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
        d.CUE表總檔數 = sum(int(r.get("spots") or 0) for r in rows) or None
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
