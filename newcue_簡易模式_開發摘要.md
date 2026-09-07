# newcue 簡易模式 開發摘要 v2

## 一句話
業務「選 1 個平台組合 ＋ 輸入預算 ＋ 選開始日」，網頁立即顯示與公司範本一致的 CUE 預覽
（每個秒數一個分頁），並可下載一個 Excel（一檔多分頁）與 PDF。

## 檔案分工（純邏輯與 UI 分離，計算不 import streamlit）
| 檔案 | 職責 |
|---|---|
| `simple_config.py` | 所有常數（七組合、40/60 比例、秒數係數、代理商牌價、備註模板、樣式），每條標來源與 §11 |
| `simple_model.py` | 純計算：`build_model` 唯一入口、`allocate_spots`（貪婪填滿不超預算）、`distribute`（餘數放前）、子公司/2008/凱絡建模 → `CueModel` |
| `simple_excel.py` | 版型 A 子公司 Media Schedule（①②③）；`render(model, formulas=)` 對外入口 |
| `simple_excel_agency.py` | 版型 B 2008（④⑤）、版型 C 凱絡（⑥⑦） |
| `simple_html.py` | `CueModel` → HTML 即時預覽（自動等比縮放、六日底色、紅/藍字） |
| `simple_cue.py` | Streamlit UI（三步、自動產生、下載 Excel/PDF、秒數分頁預覽） |
| `tools/dump_template.py` | 範本逐格傾印（開發輔助） |

## 商業規則重點
- 檔次自己算（不呼叫 `calculator.calculate_plan_data`）：可為奇數、不超預算盡量填滿（≥99%）、每日平均餘數放前。
- 內部實作價／計價模式**絕不寫進客戶檔案**；rate(Net) 公式內嵌係數（不引用隱藏欄）。
- 子公司 40/60、樂家康＝rhu(量販×720/420) 計價於量販；VAT 含製作費。
- 代理商牌價、回饋列（2008 15%+46%／萬家福 10%；凱絡 15/40/6%）、凱絡三層價與 A.C 免收，皆依 0902 範本，見 `docs/簡易模式_待老闆確認.md`。

## 測試
- `tests/test_simple_model.py`：112 條數字規則（§4.4 參考向量精確相等、代理商 25 萬七組、費用、日期）。
- `tests/test_simple_excel.py` + `tests/fidelity.py`：子公司三組合×4 分頁逐格對齊範本，`ALLOWED_DIFF` 之外零差異。
- `tests/test_simple_excel_agency.py`：代理商版型結構＋商業數值（分頁/標籤/費用/回饋/媒體總價值）。
- `tests/test_simple_smoke.py`：七組合×5 預算×4 走期全部能產出、排檔加總＝檔次、分頁名唯一 ≤31 字。

## 已知後續（見驗收回報）
- 代理商（2008/凱絡）版型目前為「結構＋數值正確」，逐格像素 fidelity 仍在收斂（子公司已嚴格對齊）。
- 視覺 PDF 對照（`visual_check_simple.py`）需環境有 LibreOffice（本機 Windows 無 `soffice`，Streamlit Cloud/devcontainer 的 `packages.txt` 已含）。
