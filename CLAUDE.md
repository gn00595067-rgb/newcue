# newcue

## 一句話
這個 app 給 聲活科技的業務／同事 用來 產生廣告 CUE 表（七組合：子公司／2008／凱絡）與代理商報價，並輸出 Excel／PDF。

## 現況
- 狀態：🟢 LIVE（簡易模式 v2 已上線，見 `newcue_簡易模式_開發摘要.md`）
- 本機：`C:\dev\newcue`
- push：`gn00595067-rgb/newcue.git` · `main`（push 後 Streamlit Cloud 自動部署）
- 開發分支：`ragic-dev`（Ragic 串接／訂檔流程，spec `docs/specs/Ragic串接_訂檔流程.md`）→ 只推此分支，另有 Streamlit 測試 app 指向它；全部確認後才 merge 回 main。Ragic 寫入預設乾跑，Secrets `RAGIC_WRITE_ENABLED="true"` 才寫入。
- 線上：https://newcue-abjxjcgtl2ticg9hnucixz.streamlit.app/（2026-10-05 重建，舊網址失效）
- Secrets（只列名稱）：`[gcp_service_account]`（同事登入密碼表＝設定檔 Sheet 的「登入密碼」分頁，Sheet 要共用給服務帳號）、`DEV_LOGIN_PASSWORD`／`DEV_LOGIN_NAME`／`DEV_LOGIN_EMAIL`（開發者登入，只設在測試 app）、`RAGIC_API_KEY`、`RAGIC_URL`、`SUPERVISOR_PASSWORD`、`AGENCY_PASSWORD`（代理商CUE 密碼，未設時預設 123）（見 `.streamlit/secrets.toml.example`）

## 地雷（踩過的坑，改 code 前先看）
- Excel 產出一律用「值版」下載；openpyxl 公式版在受保護檢視會空白。
- strict fidelity：樣式對齊母版 `simple_style_master.py`，改樣式必跑 `tests/fidelity.py`／`tests/visual_check.py`。
- 家樂福已改名「萬家福．樂家康」（台灣通路改名，commit 73615cd）。
- Streamlit Cloud 的 Python 版本以「App settings → General → Python version」為準（runtime.txt 不生效），必須設 3.12；3.14 會裝不起來（pyarrow 無 wheel）。requirements 已鎖上限，升版前先用 `uv pip compile --python-version 3.12 --only-binary :all:` 驗證。
- requirements.txt 是全套件鎖死版（頂層來源在 requirements.in）。2026-10-05 Cloud 重新佈機抓到 9/30 後新版套件（疑 gitpython 3.2.0）→ 伺服器卡死一直轉圈、log 空白；鎖回 9/29 版本後恢復。升版務必用 `uv pip compile requirements.in --python-version 3.12 --only-binary :all: --exclude-newer <日期>` 重產並本機跑過。
- 線上 app 網址已變更（刪除重建）：https://newcue-abjxjcgtl2ticg9hnucixz.streamlit.app/
- 一般 CUE 備註來源是 `utils.get_remarks_text`（年約季約共用）；簡易模式子公司組合也共用同一份（2026-10-08 起）；改備註要同步更新 `tests/test_simple_excel.py` 的允許差異。備註字色看內容（`utils.remark_color`），不看編號。
- 萬家福．樂家康在 CUE 上逐列顯示萬家福／樂家康、量販店／超市，是渲染時 `utils.cue_station／cue_location` 轉的；rows 的 region 仍是「全省量販／全省超市」（回饋、Ragic 靠它比對），不要改 region。
- Streamlit Cloud 推版後若 app.py 改為 import 其他模組「新增」的函式，Cloud 可能沿用記憶體裡的舊模組 → `ImportError`（2026-10-13 正式＋測試版同時發生）。程式本身沒壞，到 Manage app → ⋮ → Reboot app 即恢復；推這類改動後要提醒 Jonathan 重啟。
- Ragic 會擋 Streamlit Cloud 發出的帳密登入（AUTH 回 -1；同帳密本機／公司瀏覽器都成功，2026-10-14 實測）→ 同事改用信箱或員工工號＋app 密碼登入（預設 123456、首次必改，雜湊存 Google Sheet，`app_passwords.py`），身分取 Ragic 使用者清單 `ragic-setup/1`（API 金鑰可讀）。API 金鑰讀寫不受影響。
- <其他地雷待補>

## 架構速覽
- 入口：`app.py`
- 簡易模式：`simple_cue.py`／`simple_model.py`／`simple_excel.py`／`simple_html.py`／`simple_style_master.py`／`simple_reach.py`（預估曝光／人流）／`simple_preview.py`
- 固定專案：`fixed_projects.py`（製作模式「專案CUE」，目前：萬家福/樂家康 116年度過年、中元限定專案；新增專案只加資料）
- 代理商：`agency_cue.py`／`agency_excel.py`／`agency_ui.py`／`rebate.py`（牌價／折讓）
- 產出渲染：`excel_renderer.py`／`html_generator.py`／`pdf_render.py`／`pdf_converter.py`／`xlsx_numfmt.py`
- 資料／設定：`data_loader.py`／`config.py`／`simple_config.py`／`各平台人流計算方式.xlsx`／`AgencyPricing範本.csv`
- 外部：Ragic（`ragic_api.py`；ragic-dev 另有 `ragic_booking/`（客戶、CUE號、訂檔，自 cueupload 搬入）、`ragic_ui.py`（登入、客戶帶入、存檔面板、送出訂檔）、`cue_store.py`（快照／版本／狀態）、`cue_registry.py`（存檔編號、統計）、`cue_admin.py`（CUE 管理、統計頁）、`bonus_adjust.py`（加贈）、`xlsx_merge.py`）
- 測試：`tests/`（含 fidelity／visual_check／各模式 smoke）

## 下次續做
（2026-10-14 停在這裡；ragic-dev 最新 `b50790e`，完整測試 579 綠；main 最新 `44867dd`）
- **Ragic 串接第 1～5 期程式全部完成，只在 ragic-dev**（spec：`docs/specs/Ragic串接_訂檔流程.md`、`docs/specs/Ragic串接_第5期_存檔編號與統計.md`）。正式版 main 未合併。
- 下一步＝陪 Jonathan 在測試 app（https://newcue-gffrnqkzgd52wysftlnwyu.streamlit.app/ ，指向 ragic-dev）實測，推版後先 Reboot：
  1. Ragic 帳號登入（含開兩步驟驗證的同事）、客戶帶入、存檔給編號、存檔後下載 → Secrets `RAGIC_WRITE_ENABLED="true"`
  2. 送出訂檔：真的申請 CUE號＋建訂檔 → 加贈後送出更新原訂檔（`update_record` 子表 row id 就地更新尚未在真 Ragic 驗證）→ `RAGIC_BOOKING_ENABLED="true"`；試完刪測試 CUE號／訂檔
  3. 主管：`RAGIC_REVIEWERS` 設信箱 → CUE 管理資料夾、統計、營運加贈、抽查退回
- 實測通過後：通知同事「沒 Ragic 帳號不能下載」→ ragic-dev 一般 merge 回 main（不 force）→ Reboot 正式 app。
- 待 Jonathan：是否在 cue/2 加「存檔編號」欄（給欄位 ID）；業務代碼撞號時在 `RAGIC_SALES_CODES` 指定。
- 已知限制：退回不自動刪訂檔、不寄通知；統計只算新程式存檔；待審／我的 CUE 清單掃全部紀錄（量大再優化）；代理商一鍵模板不支援加贈。
