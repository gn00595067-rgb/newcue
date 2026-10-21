"""（2026-10-13 自 cueupload/cueparse/ragic_fields.py 搬入，兩邊修改請同步）
Ragic 三張表的欄位 ID（流水號）對照 + 寫入 payload 組裝（含乾跑）。

欄位 ID 由 scripts/discover_ragic_fields.py 以 `?api&v=3&naming=EID` 挖出，
與中文名逐欄對照而來（非猜測）。詳見 data/ragic_fields/*.json。

寫入 API（Ragic 官方）：
  POST  https://ap16.ragic.com/soundwow/<form>          # 建立新記錄
        https://ap16.ragic.com/soundwow/<form>/<rid>    # 更新既有記錄
  Header: Authorization: Basic <API_KEY>
  Body  : 欄位ID=值（form-encoded），子表用「欄位ID_-列號」
  旗標  : doLinkLoad=true（連結欄自動帶入，如選客戶編號→帶客戶名/統編）
          doFormula=true（重算公式，如 除佣實收、各總計）
          doDefaultValue=true（帶預設值，如 CUE號 由序號依據自動生成）

本模組只負責「組出正確的 payload」；是否真的送出由呼叫端決定（測試階段一律乾跑）。
"""
from __future__ import annotations

import urllib.parse
from dataclasses import dataclass, field
from typing import Any

import requests

SERVER = "https://ap16.ragic.com"
ACCOUNT = "soundwow"

FORM_ORDER = "forms12/17"      # 訂檔(業務填寫)(新客卡)-V3
FORM_CUE_APPLY = "forms13/4"   # 新增CUE號申請表
FORM_CUSTOMER = "forms13/3"    # 客戶管理資料表(成交)


def form_url(form: str, rid: str | None = None) -> str:
    base = f"{SERVER}/{ACCOUNT}/{form}"
    return f"{base}/{rid}" if rid else base


# ------------------------------------------------------------------ 訂檔 forms12/17
class OrderF:
    """訂檔欄位 ID。"""
    訂檔性質 = "1015324"       # 預設「訂檔」
    訂檔單號 = "1015325"       # ⚪ 系統自動 OD… 不設
    建立日期 = "1015326"       # ⚪ 系統
    修改日期 = "1015327"       # ⚪ 系統
    申請人 = "1015328"
    業務開發客戶 = "1015329"
    業務主管 = "1015330"
    公司 = "1015331"
    CUE號 = "1015332"
    波段 = "1015333"
    客服 = "1015334"           # multi
    文案 = "1015335"           # multi
    CUE = "1015336"            # ⚪ 選CUE號後帶入 不設
    總波段 = "1015337"         # ⚪ 選CUE號後帶入 不設
    訂檔人 = "1015338"
    節配 = "1015339"
    客戶編號 = "1015340"       # 🔗 LINK：選此欄→帶客戶名/統編/產業/付款…
    統一編號 = "1015836"       # ⚪ 連動帶入
    結三單 = "1015341"         # ☑️ Yes/No
    回簽 = "1015342"           # ☑️ Yes/No
    客戶 = "1015343"           # 連動帶入（廣代案需人工改代理商）
    個案分配 = "1015344"       # ☑️ Yes/No
    停檔 = "1015345"           # ☑️ Yes/No（截圖標「停權」，實際欄名＝停檔）
    產業別 = "1015346"         # 連動帶入
    客戶類別 = "1015347"       # 🟠 關鍵人工（可取自客戶主檔）
    通知部門 = "1015348"
    產品名稱 = "1015349"
    通知個人 = "1015350"       # multi
    平台 = "1015351"           # multi 🟢 CUE
    執行開始日期 = "1015353"    # 🟢 CUE
    執行結束日期 = "1015354"    # 🟢 CUE
    企頻素材 = "1015355"       # ☑️ Yes/No（截圖標「企銷素材」，實際＝企頻素材）
    個案確認 = "1015566"       # ☑️ Yes/No
    新鮮視素材 = "1015562"     # ☑️ Yes/No
    成本確認 = "1015567"       # ☑️ Yes/No
    CUE表秒數 = "1015356"      # multi 🟢 CUE
    CUE表總檔數 = "1015357"    # 🟢 CUE（建議改用子表逐平台）
    訂檔CUE表 = "1015359"      # 📎 檔案
    電台回簽檔 = "1016084"     # 📎 檔案
    個案狀況 = "1015360"       # 下拉
    客戶回簽檔 = "1015361"     # 📎 就是被解析的 CUE 檔
    電台播證開立名稱 = "1015365"
    平台2 = "1015366"          # 下拉（企頻/廣播…次分類）
    秒數管理 = "1016085"       # ☑️ Yes/No
    素材走法 = "1015367"       # 文字
    素材走法附件 = "1015368"   # 📎 檔案
    付款條件 = "1015370"       # 連動帶入
    現折pct = "1015371"
    退佣加現折pct = "1015377"  # ⚪ 公式
    是否換算除佣實收 = "1015379"  # ☑️ Yes/No 是否將除佣實收換為退佣%+現折%數
    收款日期 = "1015373"
    退佣 = "1015374"
    發票開立日業務 = "1016062"  # 📅 日期
    特殊條件70 = "1016159"     # ☑️ Yes/No 特殊條件-70%
    特殊條件60 = "1016160"     # ☑️ Yes/No 特殊條件-60%
    所有平台 = "1015803"       # ⚪ 系統彙整 不設
    平台檔數總計 = "1015461"    # ⚪ 加總 不設
    實收金額總計 = "1015462"    # ⚪ 加總 不設
    除佣實收總計 = "1015463"    # ⚪ 加總 不設
    # ⚠️ 結案人員/結案平台：Ragic API v3 完全不回傳這兩欄（name_keyed/eid 皆無），
    #    無法取得可寫入的 field ID，故不納入寫入 payload。多為結案階段填、非訂檔階段。

    # 收入子表額外欄（製作成本已在下方）

    # 子表：訂檔收入相關資訊
    SUB_INCOME = "1015394"
    收入_類別 = "1015369"
    收入_業績年月 = "1015389"
    收入_平台細項 = "1015390"    # 🟢 CUE 逐平台
    收入_平台檔數 = "1015411"    # 🟢 CUE
    收入_秒數 = "1015412"        # 🟢 CUE
    收入_製作成本 = "1015391"
    收入_實收金額未稅 = "1015392"  # 🟢 CUE amount÷1.05
    收入_除佣實收未稅 = "1015393"  # ⚪ 公式
    收入_公司 = "1015679"
    收入_配音員費用 = "1016103"   # 成本端；新建列送 0（實際資料 0 居多），更新時不動
    收入_成本 = "1015546"        # 營運填（成本確認），程式不送
    收入_其他成本 = "1015547"    # 新建列送 0，更新時不動

    # 子表：訂檔素材及需求資訊
    SUB_MATERIAL = "1015387"
    素材_音檔 = "1015380"        # 📎
    素材_廣告篇名 = "1015381"    # 🟢 CUE 建議
    素材_文案 = "1015382"        # 📎
    SUB_NEED = "1015388"
    需求_說明 = "1015383"
    需求_建立時間 = "1015384"     # 實際 436/436 有值 → 明送 yyyy/MM/dd HH:mm:ss


# ------------------------------------------------------------------ CUE申請 forms13/4
class CueApplyF:
    申請人 = "1002615"
    客戶類型 = "1002871"         # 成交客戶 / 開發客戶
    客戶編號成交 = "1002622"     # 🔗 LINK → 帶客戶名/產品/業務/主管
    客戶名稱成交 = "1002623"
    產品名稱成交 = "1002651"
    業務成交 = "1002660"         # multi
    主管成交 = "1002658"
    客戶名稱 = "1002619"         # 🟠* 必填（與「客戶名稱(成交)」同值；API 建檔時 doLinkLoad 不會帶 → 要明送）
    主管 = "1002617"             # 🟠* 必填（同上，＝主管(成交)）
    產品名稱 = "1002652"         # ＝產品名稱(成交)
    起走日期 = "1002661"
    總波段 = "1002662"
    序號依據 = "1002667"         # ⚪ 公式 = 民國年+月 不設
    CUE號 = "1002664"           # ⚪ 公式/預設 = 序號依據+2位流水 不設
    Cue表模擬編號 = "1016043"     # 🟠 來源 CUE 存檔（cue/2）的模擬編號，如 20261021-001。Ragic「更新成交CUE」
                                 #    靠它把 CUE號回寫存檔；空白時整筆回 ERROR（2026-10-21 實測，但申請紀錄仍會建立）


# ------------------------------------------------------------------ 客戶 forms13/3（讀＋寫）
# 讀取走 API v3 name-keyed（用中文名）；寫入走 create（用下面的欄位 ID）。
class CustomerF:
    # 讀取用中文名（_cust_from_raw 以名取值）
    客戶編號 = "1002571"
    客戶名稱 = "1002577"
    統一編號 = "1002578"
    產品名稱 = "1002649"
    客戶類別 = "1015016"
    業務 = "1002574"
    主管 = "1002575"
    產業別 = "1002805"
    付款條件 = "1002592"
    現折pct = "1002594"
    退佣pct = "1002595"


class CustomerWriteF:
    """新增客戶(成交) forms13/3 寫入欄位 ID。⚪ 客戶編號 C013xx 由系統自動編號，不設。"""
    業務 = "1002574"           # 🟠* 使用者選單
    主管 = "1002575"           # 🔗 選業務帶（或人工）
    客服 = "1002791"           # 🟠* 使用者多選
    產業別 = "1002805"         # 🟠*
    客戶類別 = "1015016"       # 🟠*
    客戶名稱 = "1002577"       # 🟠* 🟢CUE client
    統一編號 = "1002578"       # 🟠* 🟢CUE(工商登記)
    產品名稱 = "1002649"       # 🟠* 🟢CUE brand_or_campaign
    初次託播金額 = "1002581"    # 🟠* 🟢CUE amount_value（可帶）
    承辦人 = "1002582"         # 🟠* 🟢CUE(窗口)
    職稱 = "1002583"
    專線分機 = "1002584"       # 🟠*
    電子郵件 = "1002882"
    帳款聯絡人 = "1002585"     # 🟠*
    通訊地址 = "1002589"       # 🟠*
    客戶重要注意事項 = "1002601"  # 🟠*（可帶「無」）
    工商登記公示資料 = "1002603"  # 🟠* 📎 附件
    付款條件 = "1002592"       # 🟠*
    現折pct = "1002594"
    退佣pct = "1002595"
    每月結帳日 = "1002597"     # 🟠*
    每月請款日 = "1002598"     # 🟠*
    付款方式 = "1002599"       # 🟠* multi


# 客戶表受控選項（供下拉；找不到可自由輸入）
CUSTOMER_CATEGORY_OPTIONS = ["直客", "廣代", "廣代-商品", "廣代-建案"]   # Ragic 實際用值（2026-10-21 讀客戶主檔／訂檔）
PAYMENT_TERM_OPTIONS = ["播畢付款", "月結30天", "月結60天", "起播付現", "其他"]
PAYMENT_METHOD_OPTIONS = ["匯款", "支票", "現金", "其他"]


# ================================================================== 受控選項 / 必填清單
# 「公司」下拉：Ragic *必填、且客戶主檔沒有此欄，一定要人選（開票/歸屬的公司別）。
# 值取自訂檔表設計模式「從選單選擇」的提項清單。
COMPANY_OPTIONS = ["聲活", "聲活(來藝)", "來奕(製版)", "瑞迪", "佳聖", "亞台", "錄音室"]

# 收入子表「類別」*必填。多為 公家/一般；其餘照實填。
INCOME_CATEGORY_OPTIONS = ["一般", "公家"]


def guess_income_category(客戶類別: str = "", 產業別: str = "") -> str:
    """依客戶類別/產業別猜收入類別（公家機關→公家，其餘→一般）。人工可改。"""
    blob = f"{客戶類別}{產業別}"
    return "公家" if ("公家" in blob or "政府" in blob or "機關" in blob) else "一般"


# 紅星必填欄位（送出前自我盤點用）。分兩類：
#  hard  = 「送出端」必須自己備妥、否則 Ragic 會擋存檔的欄
#  link  = 也是必填，但由 doLinkLoad 從『客戶編號』連動帶；只要客戶編號有選就算滿足
#  attach= 必填但屬檔案上傳，需走附件上傳流程（不在 form-encoded payload 內）
REQUIRED_ORDER_HARD = [
    ("公司", "從下拉選一家開票公司別（客戶主檔沒有此欄）"),
    ("訂檔人", "使用者選單，多半＝申請人"),
    ("客戶編號", "選客戶後才能連動帶客戶名/統編/付款…"),
    ("客戶類別", "直客／代理商…"),
    ("平台", "CUE 帶入或手選"),
    ("執行開始日期", "CUE 檔期起"),
    ("執行結束日期", "CUE 檔期迄"),
    ("CUE表秒數", "CUE 帶入"),
    ("CUE表總檔數", "CUE 帶入"),
    ("電台播證開立名稱", "可自動組＝廣告主+產品，或人工改"),
    ("收款日期", "依付款條件填"),
    ("現折pct", "小數，無現折填 0"),
    ("退佣", "小數，無退佣填 0"),
]
REQUIRED_ORDER_LINK = ["業務(開發客戶)", "業務主管", "客戶名稱"]
REQUIRED_ORDER_ATTACH = [
    ("訂檔CUE表", "上傳 CUE 的 xlsx 原檔"),
    ("客戶回簽檔/業務回簽檔", "上傳回簽 PDF"),
]
# 收入子表每列必填
REQUIRED_INCOME_ROW = ["平台細項", "平台檔數", "秒數", "實收金額未稅", "業績年月", "類別"]

# CUE號申請表必填
REQUIRED_CUE_APPLY_HARD = [
    ("客戶類型", "成交客戶／開發客戶"),
    ("客戶編號成交", "選成交客戶編號"),
    ("起走日期", "CUE 檔期起"),
    ("總波段", "波段數"),
]
REQUIRED_CUE_APPLY_LINK = ["客戶名稱", "主管", "產品名稱"]


# ================================================================== 序號 / CUE號 邏輯
def minguo_year(gregorian_year: int) -> int:
    return gregorian_year - 1911


def serial_base(start_year: int, start_month: int) -> str:
    """序號依據 = 民國年 + 兩位月，如 2026/10 → '11510'。"""
    return f"{minguo_year(start_year)}{start_month:02d}"


def preview_cue_id(start_year: int, start_month: int, running_no: int) -> str:
    """CUE號預覽 = 序號依據 + 兩位流水。真正流水號由 Ragic 產生，這裡僅供顯示。"""
    return f"{serial_base(start_year, start_month)}{running_no:02d}"


def latest_running_no(start_year: int, start_month: int,
                      limit: int = 500) -> dict[str, Any]:
    """去 Ragic『新增CUE號申請表』查這個序號依據目前已申請到第幾號。

    流水號綁『序號依據』(＝民國年+起走月，如 2026/10→'11510')，非綁日曆日。
    掃 forms13/4 近期紀錄，篩出同序號依據者，取 CUE號後綴流水的最大值。

    回傳 {base, max_no, next_no, count, samples}：
      base    ＝序號依據字串
      max_no  ＝目前最大流水（查無＝0）
      next_no ＝建議下一號＝max_no+1
      count   ＝該序號依據已存在幾筆
      samples ＝最近幾筆 CUE號（供人工核對）
    純讀取，失敗不拋（回 max_no=0），呼叫端自行決定要不要提示。
    """
    base = serial_base(start_year, start_month)
    url = f"{form_url(FORM_CUE_APPLY)}?api&v=3&limit={max(1, limit)}"
    data = _get_json(url)
    nos: list[int] = []
    samples: list[str] = []
    for r in data.values():
        if not isinstance(r, dict):
            continue
        cue = str(r.get("CUE號", "")).strip()
        sb = str(r.get("序號依據", "")).strip()
        # 以序號依據優先；沒有就用 CUE號前綴回推，兩者都要對得上 base。
        if sb and sb != base:
            continue
        if not cue.startswith(base):
            continue
        tail = cue[len(base):]
        if tail.isdigit():
            nos.append(int(tail))
            samples.append(cue)
    max_no = max(nos) if nos else 0
    samples = sorted(set(samples), reverse=True)[:5]
    return {"base": base, "max_no": max_no, "next_no": max_no + 1,
            "count": len(nos), "samples": samples}


# ================================================================== payload 組裝
@dataclass
class OrderDraft:
    """一張訂檔的最小必要輸入（多數來自 CUE 解析與客戶主檔）。"""
    客戶編號: str = ""
    客戶類別: str = ""
    客戶名稱: str = ""          # 客戶主檔名稱 → 訂檔「客戶」＋CUE號申請「客戶名稱」（必填，要明送）
    CUE號: str = ""
    波段: str = "1"
    申請人: str = ""             # Ragic 使用者/員工選單（多半＝登入建立者）
    訂檔人: str = ""             # 同上；真實記錄與申請人常為同一人
    公司: str = ""              # 🟠*必填 開票公司別（客戶主檔沒有，一定要選）
    產品名稱: str = ""
    客服: list[str] = field(default_factory=list)   # 🟠*必填 使用者多選
    文案: list[str] = field(default_factory=lambda: ["無"])  # 🟠*必填 預設「無」
    節配: str = "無"            # 預設「無」
    平台: list[str] = field(default_factory=list)
    執行開始日期: str = ""        # yyyy/MM/dd
    執行結束日期: str = ""
    CUE表秒數: list[int] = field(default_factory=list)
    CUE表總檔數: int | None = None
    電台播證開立名稱: str = ""    # 🟠*必填 開播證抬頭＝廣告主+產品
    現折pct: str = ""           # 🔗 客戶主檔帶（*必填）
    退佣: str = ""             # 🔗 客戶主檔帶（*必填）
    收款日期: str = ""          # 🟠*必填 依付款條件
    統一編號: str = ""          # 連動欄；API 建檔 doLinkLoad 不一定帶 → 有就明送
    付款條件: str = ""          # 同上
    需求建立時間: str = ""       # 需求或狀況說明子表的建立時間
    # --- C 類：截圖有、原本 UI 缺的欄位（多為連動/勾選/次要，非送出硬必填）---
    業務開發客戶: str = ""       # 👤 使用者選單（🔗 亦可由客戶主檔連動）
    業務主管: str = ""          # 👤/🔗
    通知部門: str = ""          # 下拉（如 財務處+媒體處+企頻小組）
    通知個人: list[str] = field(default_factory=list)  # 👤 多選
    個案狀況: str = ""          # 下拉
    平台2: str = ""            # 下拉（企頻/廣播…次分類）
    素材走法: str = ""          # 文字（如 素材A、B兩支平均輪播）
    發票開立日業務: str = ""     # 📅
    # 勾選旗標（Ragic 存 "Yes"/"No"）
    結三單: bool = False
    回簽: bool = False
    個案分配: bool = False
    停檔: bool = False
    企頻素材: bool = False
    新鮮視素材: bool = False
    個案確認: bool = False
    成本確認: bool = False
    秒數管理: bool = False
    是否換算除佣實收: bool = False
    特殊條件70: bool = False
    特殊條件60: bool = False
    收入明細: list[dict[str, Any]] = field(default_factory=list)
    # 每筆：{平台細項, 平台檔數, 秒數, 實收金額未稅, 業績年月, 類別, 製作成本}
    素材明細: list[dict[str, Any]] = field(default_factory=list)
    # 每筆：{廣告篇名, 音檔, 文案}   ← CUE 解析出的素材/篇名
    需求說明: str = ""


def _order_flags(d: OrderDraft) -> list[tuple[str, bool]]:
    """訂檔的勾選旗標欄位 → (欄位ID, 是否勾)。Ragic 存 'Yes'/'No'。"""
    return [
        (OrderF.結三單, d.結三單), (OrderF.回簽, d.回簽),
        (OrderF.個案分配, d.個案分配), (OrderF.停檔, d.停檔),
        (OrderF.企頻素材, d.企頻素材), (OrderF.新鮮視素材, d.新鮮視素材),
        (OrderF.個案確認, d.個案確認), (OrderF.成本確認, d.成本確認),
        (OrderF.秒數管理, d.秒數管理), (OrderF.是否換算除佣實收, d.是否換算除佣實收),
        (OrderF.特殊條件70, d.特殊條件70), (OrderF.特殊條件60, d.特殊條件60),
    ]


def build_order_payload(d: OrderDraft) -> dict[str, str]:
    """把 OrderDraft 組成 Ragic create 的 form 參數（欄位ID=值）。

    只填「工具能自動帶或最少人工」的欄位；系統/公式欄（CUE、總波段、各總計、
    除佣實收、統編、客戶名、產業…）交給 doLinkLoad/doFormula 產生，不硬塞。
    """
    p: dict[str, str] = {}

    def put(fid: str, val: Any) -> None:
        if val not in (None, "", []):
            p[fid] = str(val)

    put(OrderF.訂檔性質, "訂檔")
    put(OrderF.申請人, d.申請人)             # 使用者/員工選單（Ragic 多半自動帶登入建立者）
    put(OrderF.訂檔人, d.訂檔人 or d.申請人)  # 真實記錄與申請人同一人；未填則沿用申請人
    put(OrderF.公司, d.公司)                 # 🟠*必填 開票公司別
    put(OrderF.客戶編號, d.客戶編號)          # 🔗 doLinkLoad 會帶客戶名/統編/付款…
    put(OrderF.客戶類別, d.客戶類別)
    put(OrderF.客戶, d.客戶名稱)            # 必填；API 建檔 doLinkLoad 不一定帶（CUE號申請已實測不帶）
    put(OrderF.節配, d.節配)
    put(OrderF.CUE號, d.CUE號)              # 選單/連結；Ragic 帶 CUE、總波段
    put(OrderF.波段, d.波段)
    put(OrderF.產品名稱, d.產品名稱)
    put(OrderF.執行開始日期, d.執行開始日期)
    put(OrderF.執行結束日期, d.執行結束日期)
    put(OrderF.CUE表總檔數, d.CUE表總檔數)
    put(OrderF.電台播證開立名稱, d.電台播證開立名稱)
    put(OrderF.現折pct, d.現折pct)          # 若客戶主檔沒自動帶，這裡補送
    put(OrderF.退佣, d.退佣)
    put(OrderF.收款日期, d.收款日期)
    put(OrderF.統一編號, d.統一編號)
    put(OrderF.付款條件, d.付款條件)
    # C 類欄位（截圖有、原缺）：只在有值時送
    put(OrderF.業務開發客戶, d.業務開發客戶)
    put(OrderF.業務主管, d.業務主管)
    put(OrderF.通知部門, d.通知部門)
    put(OrderF.個案狀況, d.個案狀況)
    put(OrderF.平台2, d.平台2)
    put(OrderF.素材走法, d.素材走法)
    put(OrderF.發票開立日業務, d.發票開立日業務)
    for fid, on in _order_flags(d):
        put(fid, "Yes" if on else "No")

    # 多值欄：平台、客服、文案、CUE表秒數、通知個人（Ragic 多值＝同 ID 重複參數；
    # 此處以 #n 示意，實送用 requests 的 list 形式。乾跑預覽用可讀字串。）
    for i, plat in enumerate(d.平台):
        p[f"{OrderF.平台}#{i}"] = plat
    for i, v in enumerate(d.客服):
        p[f"{OrderF.客服}#{i}"] = v
    for i, v in enumerate(d.文案 or ["無"]):
        p[f"{OrderF.文案}#{i}"] = v
    for i, sec in enumerate(d.CUE表秒數):
        p[f"{OrderF.CUE表秒數}#{i}"] = str(sec)
    for i, v in enumerate(d.通知個人):
        p[f"{OrderF.通知個人}#{i}"] = v

    # 子表：訂檔收入相關資訊（逐平台一列）
    for n, row in enumerate(d.收入明細, 1):
        put(f"{OrderF.收入_類別}_-{n}", row.get("類別"))
        put(f"{OrderF.收入_平台細項}_-{n}", row.get("平台細項"))
        put(f"{OrderF.收入_平台檔數}_-{n}", row.get("平台檔數"))
        put(f"{OrderF.收入_秒數}_-{n}", row.get("秒數"))
        put(f"{OrderF.收入_製作成本}_-{n}", row.get("製作成本"))
        put(f"{OrderF.收入_配音員費用}_-{n}", row.get("配音員費用"))
        put(f"{OrderF.收入_其他成本}_-{n}", row.get("其他成本"))
        put(f"{OrderF.收入_實收金額未稅}_-{n}", row.get("實收金額未稅"))
        put(f"{OrderF.收入_業績年月}_-{n}", row.get("業績年月"))
        put(f"{OrderF.收入_公司}_-{n}", row.get("公司") or d.公司)

    # 子表：訂檔素材及需求資訊（CUE 解析出的篇名逐支一列）
    for n, row in enumerate(d.素材明細, 1):
        put(f"{OrderF.素材_廣告篇名}_-{n}", row.get("廣告篇名"))
        put(f"{OrderF.素材_文案}_-{n}", row.get("文案"))
        # 素材_音檔 是檔案上傳欄，走附件流程，不放 form-encoded payload
    if d.需求說明:
        put(f"{OrderF.需求_說明}_-1", d.需求說明)
        put(f"{OrderF.需求_建立時間}_-1", d.需求建立時間)
    return p


def order_form_tuples(d: OrderDraft) -> list[tuple[str, str]]:
    """把訂檔組成 Ragic『multipart/form-encoded』欄位 (key, value) 清單（供帶附件一次建檔）。

    與 build_order_payload 同來源，只把多值欄的 `id#n` 還原成「重複同一個 key」
    （Ragic 表單多值的正確送法），子表 `id_-n` 原樣保留。
    """
    out: list[tuple[str, str]] = []
    for k, v in build_order_payload(d).items():
        out.append((k.split("#")[0], v))   # id#n → 重複 id；子表 id_-n 不含 # 原樣
    return out


def order_payload_json(d: OrderDraft) -> dict[str, Any]:
    """把 OrderDraft 組成 Ragic 建立 API 的『JSON 原生 body』（真送用）。

    選欄規則與 build_order_payload 完全一致，差別只在序列化格式：
      多值欄（平台/客服/文案/秒數）→ 陣列；
      子表 → {"_subtable_<容器ID>": {"-1": {欄ID: 值}}}（負號列＝新增列）。
    系統/公式欄（CUE/總波段/各總計/統編…）一律不送，交給 doLinkLoad/doFormula。
    """
    p: dict[str, Any] = {}

    def put(fid: str, val: Any) -> None:
        if val not in (None, "", []):
            p[fid] = str(val)

    put(OrderF.訂檔性質, "訂檔")
    put(OrderF.申請人, d.申請人)
    put(OrderF.訂檔人, d.訂檔人 or d.申請人)
    put(OrderF.公司, d.公司)
    put(OrderF.客戶編號, d.客戶編號)
    put(OrderF.客戶類別, d.客戶類別)
    put(OrderF.客戶, d.客戶名稱)            # 必填；API 建檔 doLinkLoad 不一定帶（CUE號申請已實測不帶）
    put(OrderF.節配, d.節配)
    put(OrderF.CUE號, d.CUE號)
    put(OrderF.波段, d.波段)
    put(OrderF.產品名稱, d.產品名稱)
    put(OrderF.執行開始日期, d.執行開始日期)
    put(OrderF.執行結束日期, d.執行結束日期)
    put(OrderF.CUE表總檔數, d.CUE表總檔數)
    put(OrderF.電台播證開立名稱, d.電台播證開立名稱)
    put(OrderF.現折pct, d.現折pct)
    put(OrderF.退佣, d.退佣)
    put(OrderF.收款日期, d.收款日期)
    put(OrderF.統一編號, d.統一編號)
    put(OrderF.付款條件, d.付款條件)
    # C 類欄位
    put(OrderF.業務開發客戶, d.業務開發客戶)
    put(OrderF.業務主管, d.業務主管)
    put(OrderF.通知部門, d.通知部門)
    put(OrderF.個案狀況, d.個案狀況)
    put(OrderF.平台2, d.平台2)
    put(OrderF.素材走法, d.素材走法)
    put(OrderF.發票開立日業務, d.發票開立日業務)
    for fid, on in _order_flags(d):
        p[fid] = "Yes" if on else "No"

    # 多值欄 → 陣列（Ragic JSON create 的多值格式）
    if d.平台:
        p[OrderF.平台] = [str(x) for x in d.平台]
    if d.客服:
        p[OrderF.客服] = [str(x) for x in d.客服]
    p[OrderF.文案] = [str(x) for x in (d.文案 or ["無"])]
    if d.CUE表秒數:
        p[OrderF.CUE表秒數] = [str(x) for x in d.CUE表秒數]
    if d.通知個人:
        p[OrderF.通知個人] = [str(x) for x in d.通知個人]

    # 子表：訂檔收入相關資訊（逐平台一列）。收入_公司列自帶時用列值，否則退回主檔公司。
    inc = _subrows(d.收入明細, {
        OrderF.收入_類別: "類別", OrderF.收入_平台細項: "平台細項",
        OrderF.收入_平台檔數: "平台檔數", OrderF.收入_秒數: "秒數",
        OrderF.收入_製作成本: "製作成本", OrderF.收入_配音員費用: "配音員費用", OrderF.收入_其他成本: "其他成本",
        OrderF.收入_實收金額未稅: "實收金額未稅", OrderF.收入_業績年月: "業績年月",
        OrderF.收入_公司: "公司",
    }, fallbacks={OrderF.收入_公司: d.公司})
    if inc:
        p[f"_subtable_{OrderF.SUB_INCOME}"] = inc

    # 子表：訂檔素材（CUE 解析出的篇名逐支一列；素材_音檔走附件流程，不放這）
    mat = _subrows(d.素材明細, {
        OrderF.素材_廣告篇名: "廣告篇名", OrderF.素材_文案: "文案",
    })
    if mat:
        p[f"_subtable_{OrderF.SUB_MATERIAL}"] = mat

    if d.需求說明:
        need = {OrderF.需求_說明: str(d.需求說明)}
        if d.需求建立時間:
            need[OrderF.需求_建立時間] = d.需求建立時間
        p[f"_subtable_{OrderF.SUB_NEED}"] = {"-1": need}
    return p


def _subrows(rows: list[dict[str, Any]], colmap: dict[str, str],
             fallbacks: dict[str, Any] | None = None) -> dict[str, dict[str, str]]:
    """把子表列組成 Ragic JSON 子表格式 {"-1": {欄ID: 值}, ...}。

    colmap：欄位ID → 來源 dict 的 key（列自身有值就用）。
    fallbacks：某欄 colmap 取不到值時的補值（如公司退回主檔）。
    空值不送；整列皆空則不建該列。
    """
    out: dict[str, dict[str, str]] = {}
    for n, row in enumerate(rows, 1):
        r: dict[str, str] = {}
        for fid, key in colmap.items():
            v = row.get(key)
            if v not in (None, "", []):
                r[fid] = str(v)
        for fid, dv in (fallbacks or {}).items():
            if fid not in r and dv not in (None, "", []):
                r[fid] = str(dv)
        if r:
            out[f"-{n}"] = r
    return out


# ================================================================== 送出前必填盤點
def _draft_val(d: OrderDraft, name: str) -> Any:
    """把中文欄名對到 draft 屬性（含少數別名）。"""
    alias = {"客戶名稱": "客戶編號", "業務(開發客戶)": "客戶編號", "業務主管": "客戶編號"}
    return getattr(d, alias.get(name, name), "")


def missing_required_order(d: OrderDraft) -> dict[str, list[str]]:
    """回傳送出前的必填缺口。

    keys：
      blocking → 送出端沒備妥、Ragic 會擋存檔的必填（含子表列）
      link     → 靠 doLinkLoad 連動的必填；客戶編號沒選才算缺
      attach   → 必填但要走附件上傳（提醒，非 payload 缺）
    """
    blocking: list[str] = []
    for name, hint in REQUIRED_ORDER_HARD:
        if not _draft_val(d, name):
            blocking.append(f"{name}（{hint}）")

    if not d.收入明細:
        blocking.append("收入子表（至少一列：平台/檔數/秒數/金額）")
    for i, row in enumerate(d.收入明細, 1):
        for k in REQUIRED_INCOME_ROW:
            if k == "類別" and not row.get("類別"):
                blocking.append(f"收入第{i}列.類別")
            elif k != "類別" and row.get(k) in (None, "", 0):
                blocking.append(f"收入第{i}列.{k}")

    link: list[str] = []
    if not d.客戶編號:
        link = [f"{n}（靠連動；請先選客戶編號）" for n in REQUIRED_ORDER_LINK]

    attach = [f"{n}（{hint}）" for n, hint in REQUIRED_ORDER_ATTACH]
    return {"blocking": blocking, "link": link, "attach": attach}


def missing_required_cue_apply(payload: dict[str, str], 客戶編號: str) -> dict[str, list[str]]:
    """CUE號申請表送出前必填盤點（payload 用 build_cue_apply_payload 產）。"""
    id_by_name = {
        "客戶類型": CueApplyF.客戶類型, "客戶編號成交": CueApplyF.客戶編號成交,
        "起走日期": CueApplyF.起走日期, "總波段": CueApplyF.總波段,
    }
    blocking = [f"{name}（{hint}）"
                for name, hint in REQUIRED_CUE_APPLY_HARD
                if not payload.get(id_by_name[name])]
    link = ([f"{n}（靠連動；請先選客戶編號）" for n in REQUIRED_CUE_APPLY_LINK]
            if not 客戶編號 else [])
    return {"blocking": blocking, "link": link, "attach": []}


def build_cue_apply_payload(客戶編號: str, 起走日期: str, 總波段: str,
                            申請人: str, 產品名稱: str = "", *, 客戶名稱: str = "",
                            主管: str = "", 業務: str = "", 模擬編號: str = "") -> dict[str, Any]:
    """CUE號申請表 create 參數。序號依據/CUE號 交給 Ragic 公式產生。

    2026-10-16 實測：只送客戶編號時 Ragic 回 INVALID「客戶名稱、主管為必填」——API 建檔的
    doLinkLoad 沒帶出這兩欄，故客戶名稱／主管／業務／產品（成交與通用欄）一律由客戶主檔明送。
    """
    p: dict[str, Any] = {}
    if 申請人:
        p[CueApplyF.申請人] = 申請人
    p[CueApplyF.客戶類型] = "成交客戶"
    p[CueApplyF.客戶編號成交] = 客戶編號
    p[CueApplyF.起走日期] = 起走日期
    p[CueApplyF.總波段] = 總波段
    if 模擬編號:
        p[CueApplyF.Cue表模擬編號] = 模擬編號
    for fids, val in (((CueApplyF.產品名稱成交, CueApplyF.產品名稱), 產品名稱),
                      ((CueApplyF.客戶名稱成交, CueApplyF.客戶名稱), 客戶名稱),
                      ((CueApplyF.主管成交, CueApplyF.主管), 主管)):
        if val:
            for fid in fids:
                p[fid] = val
    sales = [x.strip() for x in str(業務 or "").replace("、", ",").split(",") if x.strip()]
    if sales:
        p[CueApplyF.業務成交] = sales            # 多值欄
    return p


def cue_apply_payload_json(客戶編號: str, 起走日期: str, 總波段: str,
                           申請人: str, 產品名稱: str = "", **cust: str) -> dict[str, Any]:
    """CUE號申請表建立 API 的 JSON body。無多值/子表，形狀同扁平版。

    序號依據/CUE號 是公式欄，不送，由 Ragic 於建立當下產生。
    """
    return {k: v for k, v in
            build_cue_apply_payload(客戶編號, 起走日期, 總波段, 申請人, 產品名稱, **cust).items()}


# ================================================================== 新增客戶 payload
@dataclass
class CustomerDraft:
    """新增成交客戶最小輸入。🟢 標記者可由 CUE 帶入，其餘多為業務手填。"""
    客戶名稱: str = ""          # 🟢*
    產品名稱: str = ""          # 🟢*
    統一編號: str = ""          # 🟢*
    客戶類別: str = "直客"       # 🟠*
    產業別: str = ""            # 🟠*
    業務: str = ""             # 🟠* 使用者選單
    主管: str = ""             # 🔗/🟠
    客服: list[str] = field(default_factory=list)  # 🟠*
    初次託播金額: str = ""       # 🟢/🟠*（含稅原始金額）
    承辦人: str = ""            # 🟠*
    職稱: str = ""
    專線分機: str = ""          # 🟠*
    電子郵件: str = ""
    帳款聯絡人: str = ""        # 🟠*
    通訊地址: str = ""          # 🟠*
    客戶重要注意事項: str = "無"  # 🟠*
    付款條件: str = ""          # 🟠*
    現折pct: str = ""
    退佣pct: str = "0"
    每月結帳日: str = ""        # 🟠* yyyy/MM/dd
    每月請款日: str = ""        # 🟠*
    付款方式: list[str] = field(default_factory=list)  # 🟠*


def build_customer_payload(d: CustomerDraft) -> dict[str, str]:
    """組新增客戶 create 參數。客戶編號 C013xx 由系統自動編號，不設。"""
    p: dict[str, str] = {}

    def put(fid: str, val: Any) -> None:
        if val not in (None, "", []):
            p[fid] = str(val)

    C = CustomerWriteF
    put(C.客戶名稱, d.客戶名稱)
    put(C.產品名稱, d.產品名稱)
    put(C.統一編號, d.統一編號)
    put(C.客戶類別, d.客戶類別)
    put(C.產業別, d.產業別)
    put(C.業務, d.業務)
    put(C.主管, d.主管)
    put(C.初次託播金額, d.初次託播金額)
    put(C.承辦人, d.承辦人)
    put(C.職稱, d.職稱)
    put(C.專線分機, d.專線分機)
    put(C.電子郵件, d.電子郵件)
    put(C.帳款聯絡人, d.帳款聯絡人)
    put(C.通訊地址, d.通訊地址)
    put(C.客戶重要注意事項, d.客戶重要注意事項)
    put(C.付款條件, d.付款條件)
    put(C.現折pct, d.現折pct)
    put(C.退佣pct, d.退佣pct)
    put(C.每月結帳日, d.每月結帳日)
    put(C.每月請款日, d.每月請款日)
    for i, v in enumerate(d.客服):
        p[f"{C.客服}#{i}"] = v
    for i, v in enumerate(d.付款方式):
        p[f"{C.付款方式}#{i}"] = v
    return p


def customer_form_tuples(d: CustomerDraft) -> list[tuple[str, str]]:
    """新增客戶的 multipart 欄位清單（附件『工商登記公示資料』必填，須與建檔同一請求送出）。
    多值欄 `id#n` 還原成重複同一個 key（同 order_form_tuples）。newcue 新增。"""
    return [(k.split("#")[0], v) for k, v in build_customer_payload(d).items()]


def customer_payload_json(d: CustomerDraft) -> dict[str, Any]:
    """新增客戶建立 API 的 JSON body。客服/付款方式 → 陣列；客戶編號系統自動編號不送。"""
    p: dict[str, Any] = {}

    def put(fid: str, val: Any) -> None:
        if val not in (None, "", []):
            p[fid] = str(val)

    C = CustomerWriteF
    put(C.客戶名稱, d.客戶名稱)
    put(C.產品名稱, d.產品名稱)
    put(C.統一編號, d.統一編號)
    put(C.客戶類別, d.客戶類別)
    put(C.產業別, d.產業別)
    put(C.業務, d.業務)
    put(C.主管, d.主管)
    put(C.初次託播金額, d.初次託播金額)
    put(C.承辦人, d.承辦人)
    put(C.職稱, d.職稱)
    put(C.專線分機, d.專線分機)
    put(C.電子郵件, d.電子郵件)
    put(C.帳款聯絡人, d.帳款聯絡人)
    put(C.通訊地址, d.通訊地址)
    put(C.客戶重要注意事項, d.客戶重要注意事項)
    put(C.付款條件, d.付款條件)
    put(C.現折pct, d.現折pct)
    put(C.退佣pct, d.退佣pct)
    put(C.每月結帳日, d.每月結帳日)
    put(C.每月請款日, d.每月請款日)
    if d.客服:
        p[C.客服] = [str(x) for x in d.客服]
    if d.付款方式:
        p[C.付款方式] = [str(x) for x in d.付款方式]
    return p


# 客戶表紅星必填（客戶編號＝系統編號、主管＝連動，故不列入 hard）
REQUIRED_CUSTOMER_HARD = [
    ("客戶名稱", "🟢 CUE 廣告主"), ("產品名稱", "🟢 CUE 品牌/活動"),
    ("統一編號", "🟢 CUE 工商登記/回簽"), ("客戶類別", "直客/代理商"),
    ("產業別", "手選"), ("業務", "使用者選單"), ("客服", "使用者多選"),
    ("初次託播金額", "首單託播金額"), ("承辦人", "客戶窗口"),
    ("專線分機", "窗口電話"), ("帳款聯絡人", "請款窗口"),
    ("通訊地址", "寄送地址"), ("客戶重要注意事項", "可填「無」"),
    ("付款條件", "播畢付款/月結…"), ("每月結帳日", "yyyy/MM/dd"),
    ("每月請款日", "yyyy/MM/dd"), ("付款方式", "匯款/支票…"),
]
REQUIRED_CUSTOMER_ATTACH = [("工商登記公示資料", "上傳工商登記 PDF")]


def missing_required_customer(d: CustomerDraft) -> dict[str, list[str]]:
    """新增客戶送出前必填盤點。"""
    blocking: list[str] = []
    for name, hint in REQUIRED_CUSTOMER_HARD:
        v = getattr(d, name, "")
        if v in (None, "", []) or (isinstance(v, list) and not v):
            blocking.append(f"{name}（{hint}）")
    attach = [f"{n}（{hint}）" for n, hint in REQUIRED_CUSTOMER_ATTACH]
    return {"blocking": blocking, "link": [], "attach": attach}


def customer_draft_from_cue(res: dict[str, Any]) -> CustomerDraft:
    """從一份已辨識 CUE 預填新客戶草稿（best-effort，其餘留白待業務補）。"""
    d = CustomerDraft()
    d.客戶名稱 = (res.get("client") or "").strip()
    d.產品名稱 = (res.get("brand_or_campaign") or res.get("product") or "").strip()
    d.承辦人 = (res.get("sales_rep") or "").strip()  # 有時 CUE 只有業務，供參
    amt = res.get("amount_value")
    if amt:
        try:
            d.初次託播金額 = str(int(float(amt)))
        except (TypeError, ValueError):
            pass
    # 統編：CUE 標準欄沒有，掃 extra_fields 找「統一編號/統編」
    for kv in (res.get("extra_fields") or []):
        label = str(kv.get("label", ""))
        if "統一編號" in label or "統編" in label:
            d.統一編號 = str(kv.get("value", "")).strip()
            break
    return d


# create 時要一起帶的旗標（讓連結/公式/預設值生效）
WRITE_FLAGS = {"doLinkLoad": "true", "doFormula": "true", "doDefaultValue": "true"}


# ================================================================== 唯讀查詢（客戶）
def _headers() -> dict[str, str]:
    # newcue：金鑰讀 st.secrets／環境變數 RAGIC_API_KEY（config._secret）
    from config import DEFAULT_RAGIC_KEY as RAGIC_API_KEY
    return {"Authorization": f"Basic {RAGIC_API_KEY}"}


def _get_json(url: str) -> dict[str, Any]:
    resp = requests.get(url, headers=_headers(), timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, dict) else {}


@dataclass
class Customer:
    rid: str
    編號: str
    名稱: str
    統編: str
    產品: str
    類別: str
    業務: str
    主管: str
    產業別: str
    客服: list[str]
    付款條件: str
    現折pct: str
    退佣pct: str
    raw: dict = field(repr=False, default_factory=dict)


def _cust_from_raw(rid: str, r: dict) -> Customer:
    def g(k: str) -> str:
        v = r.get(k, "")
        if isinstance(v, list):
            return "、".join(str(x) for x in v)
        return str(v).strip()

    def gl(k: str) -> list[str]:
        v = r.get(k, "")
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return [g(k)] if g(k) else []
    return Customer(
        rid=str(rid), 編號=g("客戶編號"), 名稱=g("客戶名稱"), 統編=g("統一編號"),
        產品=g("產品名稱"), 類別=g("客戶類別"), 業務=g("業務"), 主管=g("主管"),
        產業別=g("產業別"), 客服=gl("客服"),
        付款條件=g("付款條件"), 現折pct=g("現折%"), 退佣pct=g("退佣%"), raw=r,
    )


def order_defaults_for_customer(客戶編號: str, scan: int = 200) -> dict[str, str]:
    """從該客戶『過往訂單』推慣用值（探勘證實：公司 39/40、付款條件 40/40 家穩定）。

    回傳可帶入訂檔的預設：{公司, 客服, 付款條件}（取該客戶最近一筆訂單的值）。
    純讀取；查不到就回空 dict。
    """
    if not 客戶編號:
        return {}
    url = f"{form_url(FORM_ORDER)}?api&v=3&limit={max(1, scan)}"
    data = _get_json(url)

    def g(rec: dict, k: str) -> str:
        v = rec.get(k, "")
        return "、".join(map(str, v)) if isinstance(v, list) else str(v).strip()

    best_ts, best = -1.0, None
    for rec in data.values():
        if not isinstance(rec, dict) or g(rec, "客戶編號") != 客戶編號:
            continue
        ts = float(rec.get("_dataTimestamp") or 0)
        if ts >= best_ts:
            best_ts, best = ts, rec
    if not best:
        return {}
    out = {}
    for name in ("公司", "客服", "付款條件"):
        val = g(best, name)
        if val:
            out[name] = val
    return out


# 通知部門／通知個人／平台2 依「平台含企頻與否」完全連動（2026-10-21 讀訂檔 300 筆無例外）。
# 名單以最近訂檔為準（notify_defaults），讀不到時用這份當時的名單。
NOTIFY_FALLBACK = {
    False: {"平台2": "", "通知部門": "財務處+媒體處",
            "通知個人": ["陳秀鈴", "潘鈺今", "蔡宜歆", "李佳陵", "俞楹琦"]},
    True: {"平台2": "企頻", "通知部門": "財務處+媒體處+企頻小組",
           "通知個人": ["陳秀鈴", "潘鈺今", "蔡宜歆", "李佳陵", "俞楹琦", "leah@swd.com.tw", "何玉琳"]},
}
QP_PLATFORMS = ("全家企頻", "家樂福企頻")


def has_qp(平台: list[str]) -> bool:
    """訂檔平台是否含企頻（全家企頻／家樂福企頻）。"""
    return any(p in QP_PLATFORMS for p in 平台 or [])


def notify_defaults(limit: int = 60) -> dict[bool, dict[str, Any]]:
    """最近訂檔中「含企頻／不含企頻」各取最新一筆的 平台2／通知部門／通知個人；缺的類別用 NOTIFY_FALLBACK。"""
    out = {k: dict(v) for k, v in NOTIFY_FALLBACK.items()}
    try:
        data = _get_json(f"{form_url(FORM_ORDER)}?api&v=3&limit={max(1, limit)}")
    except Exception:  # noqa: BLE001
        return out
    best: dict[bool, float] = {}
    for rec in data.values():
        if not isinstance(rec, dict) or not rec.get("通知個人") or not rec.get("通知部門"):
            continue
        plats = rec.get("平台") or []
        qp = has_qp(plats if isinstance(plats, list) else [plats])
        ts = float(rec.get("_dataTimestamp") or 0)
        if ts < best.get(qp, -1):
            continue
        best[qp] = ts
        ppl = rec["通知個人"]
        out[qp] = {"平台2": str(rec.get("平台2") or ""), "通知部門": str(rec["通知部門"]),
                   "通知個人": [str(x) for x in (ppl if isinstance(ppl, list) else [ppl])]}
    return out


def customer_field_options(field_name: str, limit: int = 200) -> list[str]:
    """客戶主檔某欄的不重複值（供新增客戶時下拉：業務/主管/產業別/客服/客戶類別）。"""
    return _distinct_field_values(FORM_CUSTOMER, field_name, limit)


def manager_for_sales(業務: str, limit: int = 200) -> str:
    """從客戶主檔推某業務『最常搭配的主管』（新客戶主管預設，可改）。

    探勘：9/13 位業務對應單一主管；少數業務跨主管，故取眾數當建議、非硬填。
    查無或未指定業務回空字串。
    """
    if not 業務:
        return ""
    from collections import Counter
    data = _get_json(f"{form_url(FORM_CUSTOMER)}?api&v=3&limit={max(1, limit)}")
    votes: Counter[str] = Counter()
    for r in data.values():
        if not isinstance(r, dict):
            continue
        s = r.get("業務", "")
        s = "、".join(map(str, s)) if isinstance(s, list) else str(s).strip()
        mg = str(r.get("主管", "")).strip()
        if s == 業務 and mg:
            votes[mg] += 1
    return votes.most_common(1)[0][0] if votes else ""


def search_customers(query: str, limit: int = 30) -> list[Customer]:
    """以客戶名稱／編號／統編搜尋客戶主檔（唯讀）。同客戶多產品＝多筆。"""
    q = urllib.parse.quote(query.strip())
    url = f"{form_url(FORM_CUSTOMER)}?api&v=3&fts={q}&limit={max(1, limit)}"
    data = _get_json(url)
    return [_cust_from_raw(rid, r) for rid, r in data.items() if isinstance(r, dict)]


def recent_customers(limit: int = 20) -> list[Customer]:
    url = f"{form_url(FORM_CUSTOMER)}?api&v=3&limit={max(1, limit)}"
    data = _get_json(url)
    return [_cust_from_raw(rid, r) for rid, r in data.items() if isinstance(r, dict)]


def _distinct_field_values(form: str, field_name: str, limit: int) -> list[str]:
    """掃某表近期紀錄，取某欄不重複值（供 Streamlit 下拉用）。"""
    url = f"{form_url(form)}?api&v=3&limit={max(1, limit)}"
    data = _get_json(url)
    seen: dict[str, None] = {}
    for r in data.values():
        if not isinstance(r, dict):
            continue
        v = r.get(field_name, "")
        for one in (v if isinstance(v, list) else [v]):
            s = str(one).strip()
            if s:
                seen.setdefault(s, None)
    return sorted(seen)


_CORP_SUFFIX = ("股份有限公司", "有限公司", "股份公司", "企業社", "公司")


def _core_name(s: str) -> str:
    """把名稱化簡成核心：去公司後綴、去『-產品』尾綴與括號、去空白與引號。"""
    s = str(s or "").strip()
    for sep in ("-", "－", "—", "｜", "/", "(", "（"):
        if sep in s:
            s = s.split(sep)[0].strip()
    for suf in _CORP_SUFFIX:
        if s.endswith(suf):
            s = s[: -len(suf)].strip()
    return s.replace(" ", "").replace('"', "").replace("　", "")


def _probes_from_cue(res: dict[str, Any]) -> list[str]:
    """由一份 CUE 組出反查探針（依優先序，去重）。"""
    client = str(res.get("client") or "").strip()
    brand = str(res.get("brand_or_campaign") or "").strip()
    agency = str(res.get("agency") or "").strip()
    raw = [client, _core_name(client), _core_name(brand), _core_name(agency)]
    out: list[str] = []
    for p in raw:
        p = p.strip()
        if len(p) >= 2 and p not in out:
            out.append(p)
    return out


def find_customers_for_cue(res: dict[str, Any], limit: int = 6) -> list[dict[str, Any]]:
    """從一份已辨識 CUE 反查客戶主檔候選，依相符度排序。

    多探針（client / 去尾綴 / 品牌 / 代理商）搜尋 → 合併去重 → 評分：
      客戶名相符最高、產品相符次之、代理商名相符(代理商案)再次；『製作費用』雜訊扣分。
    回傳 [{customer, score, reason}]，score>0 才收，最多 limit 筆。
    """
    client_c = _core_name(res.get("client"))
    brand_c = _core_name(res.get("brand_or_campaign"))
    agency_c = _core_name(res.get("agency"))

    found: dict[str, Customer] = {}
    for probe in _probes_from_cue(res):
        try:
            for c in search_customers(probe, limit=8):
                found.setdefault(c.rid, c)
        except Exception:  # noqa: BLE001
            continue

    def contains(a: str, b: str) -> bool:
        a, b = a.replace(" ", ""), b.replace(" ", "")
        return bool(a) and bool(b) and (a in b or b in a)

    scored: list[dict[str, Any]] = []
    for c in found.values():
        name_c = _core_name(c.名稱)
        prod = str(c.產品 or "")
        score, why = 0, []
        if client_c and contains(client_c, name_c):
            score += 5; why.append("客戶名相符")
        if brand_c and prod and contains(brand_c, _core_name(prod)):
            score += 4; why.append("產品相符")
        if agency_c and contains(agency_c, name_c):
            score += 3; why.append("代理商名相符（代理商案）")
        if client_c and prod and contains(client_c, _core_name(prod)):
            score += 2; why.append("產品含客戶名")
        if "製作費" in prod:
            score -= 3
        if score > 0:
            scored.append({"customer": c, "score": score, "reason": "、".join(why)})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


def order_field_options(field_name: str, limit: int = 300) -> list[str]:
    """訂檔表某欄的不重複既有值（供 🚀 頁下拉：公司/平台/CUE表秒數/節配/文案/
    客戶類別/通知部門/通知個人/個案狀況/平台2/業務(開發客戶)/業務主管…）。

    效果＝跟 Ragic 一樣「用選的」，且選項來自真實紀錄、不寫死（修正原本 COMPANY_OPTIONS
    寫死漏『東吳』等實際公司別的問題）。純讀取，失敗由呼叫端 try 包住回空。
    """
    return _distinct_field_values(FORM_ORDER, field_name, limit)


def order_field_options_bulk(field_names: list[str], limit: int = 300) -> dict[str, list[str]]:
    """一次 GET 訂檔表，抽出多個欄位各自的不重複既有值（省配額）。

    供 🚀 頁一鍵載入所有下拉選項：公司/平台/秒數/節配/文案/客戶類別/通知部門/
    通知個人/個案狀況/平台2/業務(開發客戶)/業務主管…全部只打一次 API。
    """
    url = f"{form_url(FORM_ORDER)}?api&v=3&limit={max(1, limit)}"
    data = _get_json(url)
    acc: dict[str, dict[str, None]] = {n: {} for n in field_names}
    for r in data.values():
        if not isinstance(r, dict):
            continue
        for n in field_names:
            v = r.get(n, "")
            for one in (v if isinstance(v, list) else [v]):
                s = str(one).strip()
                if s and s not in ("No", "Yes"):
                    acc[n].setdefault(s, None)
    return {n: sorted(vals) for n, vals in acc.items()}


def applicant_options(limit: int = 200) -> list[str]:
    """申請人選項＝CUE申請表近期紀錄裡出現過的『申請人』值（去重排序）。

    Ragic 的『申請人』是使用者/員工選單欄；此處以實際紀錄還原可選清單，
    在 Streamlit 以 selectbox 呈現＝『跟 Ragic 一樣用選的』。
    """
    return _distinct_field_values(FORM_CUE_APPLY, "申請人", limit)
