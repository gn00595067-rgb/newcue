# newcue

## 一句話
這個 app 給 聲活科技的業務／同事 用來 產生廣告 CUE 表（七組合：子公司／2008／凱絡）與代理商報價，並輸出 Excel／PDF。

## 現況
- 狀態：🟢 LIVE（簡易模式 v2 已上線，見 `newcue_簡易模式_開發摘要.md`）
- 本機：`C:\dev\newcue`
- push：`gn00595067-rgb/newcue.git` · `main`（push 後 Streamlit Cloud 自動部署）
- **2026-11-24 起只有一個 app、一條分支**：ragic-dev 已合併回 main（`22e5988`），測試 app 停用，Jonathan 直接在正式版測；之後一律推 `main`（ragic-dev 不再使用）。推版後記得提醒 Reboot。Ragic 寫入預設乾跑，Secrets `RAGIC_WRITE_ENABLED="true"` 才寫入（沒開＝存檔鈕灰、同事無法下載）。
- 同事用指南：`docs/guides/newcue登入指南.pdf`（網址、登入、第一次改密碼、存檔才能下載；HTML 原稿同資料夾，改完用 Edge headless 重印）。
- 線上：https://newcue-abjxjcgtl2ticg9hnucixz.streamlit.app/（2026-10-05 重建，舊網址失效）
- Secrets（只列名稱）：`[gcp_service_account]`（同事登入密碼表＝設定檔 Sheet 的「登入密碼」分頁，Sheet 要共用給服務帳號）、`DEV_LOGIN_PASSWORD`／`DEV_LOGIN_NAME`／`DEV_LOGIN_EMAIL`（開發者登入；11-24 起正式 app 也有設，同事側欄會看到入口，指南已註明不用理）、`RAGIC_API_KEY`、`RAGIC_URL`、`SUPERVISOR_PASSWORD`、`AGENCY_PASSWORD`（代理商CUE 密碼，未設時預設 123）（見 `.streamlit/secrets.toml.example`）

## 地雷（踩過的坑，改 code 前先看）
- Excel 產出一律用「值版」下載；openpyxl 公式版在受保護檢視會空白。
- strict fidelity：樣式對齊母版 `simple_style_master.py`，改樣式必跑 `tests/fidelity.py`／`tests/visual_check.py`。
- 家樂福已改名「萬家福．樂家康」（台灣通路改名，commit 73615cd）。
- Streamlit Cloud 的 Python 版本以「App settings → General → Python version」為準（runtime.txt 不生效），必須設 3.12；3.14 會裝不起來（pyarrow 無 wheel）。requirements 已鎖上限，升版前先用 `uv pip compile --python-version 3.12 --only-binary :all:` 驗證。
- requirements.txt 是全套件鎖死版（頂層來源在 requirements.in）。2026-10-05 Cloud 重新佈機抓到 9/30 後新版套件（疑 gitpython 3.2.0）→ 伺服器卡死一直轉圈、log 空白；鎖回 9/29 版本後恢復。升版務必用 `uv pip compile requirements.in --python-version 3.12 --only-binary :all: --exclude-newer <日期>` 重產並本機跑過。
- 線上 app 網址已變更（刪除重建）：https://newcue-abjxjcgtl2ticg9hnucixz.streamlit.app/
- 一般 CUE 備註來源是 `utils.get_remarks_text`（年約季約共用）；簡易模式子公司組合也共用同一份（2026-10-08 起）；改備註要同步更新 `tests/test_simple_excel.py` 的允許差異。備註字色看內容（`utils.remark_color`），不看編號。
- 萬家福．樂家康在 CUE 上逐列顯示萬家福／樂家康、量販店／超市，是渲染時 `utils.cue_station／cue_location` 轉的；rows 的 region 仍是「全省量販／全省超市」（回饋、Ragic 靠它比對），不要改 region。
- Streamlit Cloud 推版後若 app.py 改為 import 其他模組「新增」的函式，Cloud 可能沿用記憶體裡的舊模組 → `ImportError`（2026-10-13 正式＋測試版同時發生）。程式本身沒壞，到 Manage app → ⋮ → Reboot app 即恢復；推這類改動後要提醒 Jonathan 重啟。2026-11-24 正式版又發生（utils.rebalance_shares）→ **app.py 要用的新函式優先放新模組**（如 `share_rebalance.py`），新模組必定重新載入，不必靠 Reboot。
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
- 11-26 主管回覆第二階段決策（DECISIONS 11-26）：第 1 批已上線（新回饋表 `rebate_rules.py`、鉑霖實收價列 `net_terms.py`、含離島、備註第 7 點、一般CUE VAT 含製作費）；2-1 加碼提示、2-2 媒體效益說明（`pitch.py`）接續上線。2-3 方案比較、2-4 報價頁（`plan_compare.py`、`quote_page.py`）、2-5 贈檔權限申請（`gift_review.py`；CUE 管理「加贈待核准」）同批上線（spec `docs/specs/第二階段_主管決策實作.md`）。剩 2-6 各平台不同走期、購買／贈送分開列。請業務用 1123／1124 題目重測、主管試核准流程。
- 11-24 正式版合併上線、Jonathan 已 Reboot 並實測登入正常。下一步：把 `docs/guides/newcue登入指南.pdf` 發給同事；先前各則「待 Reboot 後請宜歆重測」現在都在正式版，可請宜歆／業務一起重測。訂檔仍是測試期（`RAGIC_TEST_MODE` 未設＝CUE號記 cue/6、每月 15 筆），正式訂檔時設 `RAGIC_TEST_MODE="false"`。
- 11-24 第二階段 A 批先做三項已上線：預算 % 拉桿改數字輸入（手填保留、沒填的補剩下，`utils.rebalance_shares`）、TV→全家新鮮視、分段執行改名「分段執行／跳週」加提示（spec `docs/specs/第二階段A批小修.md`）。需 Reboot（app.py 新 import）；請業務用 1123 第 2、4 題重測。
- 11-24 總經理＋業務排CUE測試回饋 → 第二階段規劃 `docs/plans/2026-11-24_業務排CUE測試回饋_第二階段規劃.md`。待總經理／Peggy 回 §4 六題（11/24 回饋比例表、專案價顯示、加碼上限、報價頁版型、離島寫法、流量說明文字），再依 §5 分批：A 小修 → B 彈性 → C 報價頁／方案比較 → 權限請示。
- 11-13 宜歆 11/12 #12／#13：2008 萬家福定價 20秒 4,000（15秒 3,400、10秒 2,600）；代理商 Excel 定價格改「=單價*檔次」公式（補快取值，`xlsx_formula_cache.py`）。待 Reboot 後請宜歆重測；#14 只寫「另請問」沒內容，待補。
- 11-11 宜歆 #11：代理商一鍵CUE 加 ⑤／⑥ 佳聖（spec `docs/specs/佳聖一鍵CUE.md`）。待 Reboot 後請宜歆試；待確認佳聖全家定價（暫用 15 秒 1,300）、素材日（開始日前 4 個工作天）。
- 11-06 測試期 CUE號上限：申請 CUE號／送出訂檔記到 Ragic cue/6「CUE系統訂檔測試」，每月 15 筆（`RAGIC_TEST_CUE_LIMIT`）、訂檔需求說明加【newcue 系統測試】；正式上線設 `RAGIC_TEST_MODE="false"`（spec `docs/specs/測試期CUE號上限.md`）。cue/6 有一筆欄位測試資料「TEST-欄位測試」佔本月 1 筆，Jonathan 確認後刪。
- 11-04 宜歆 #9／#10：健康視CUE 可加「加贈／其他列」、每列可自行填入曝光（🧮 檔次試算）、專案價欄紅字自填（公益贈檔等）；spec `docs/specs/健康視CUE.md` §6-1。待 Reboot 後請宜歆重測，並回覆 #10 定價應以 750,000 算（281,250）。
（2026-10-16 停在這裡；ragic-dev 最新 `47fcb5d`，完整測試 615 綠；main 最新 `44867dd`）
- 11-02 一般CUE 新增「📅 各區走期不同」（spec `docs/specs/各區不同走期.md`；Emily／宜歆：北區走整月、桃區只走半月同一張 CUE）。同日依宜歆 8-2 加「自訂區域比例」每區 % ｜ 金額擇一填、自動換算。待 Reboot 後請 Emily／宜歆試用。
- 10-30 宜歆 10/29 #6／#7：新增「健康視CUE」模式（`health_cue.py`，spec `docs/specs/健康視CUE.md`；價格讀設定表 HealthPricing 分頁、不提供訂檔）、表單前「① 這次的客戶」關卡＋「🆕 開新的 CUE」（spec `docs/specs/客戶先確認與開新CUE.md`）；另：申請 CUE號／送出訂檔限 RAGIC_REVIEWERS 與開發者（業務測試期只能存檔）。健康視存檔已實測：Ragic 平台欄可存「全民健康視」（10-30）。待宜歆重測 #6／#7。
- 10-27 依宜歆 #4-2＋10/14 測試報告修：元朗＝交換合約依定價算檔次、cue/2 總檔數全省只計一次（#12）、送出鈕灰時列出缺項（#13）、CUE 管理主管說明（#14／#15）。待 Reboot 後宜歆重測；#1-2（app 密碼與 Ragic 不同步）為設計如此。
- 10-22 訂檔改兩段式：⓪ 先申請（或沿用）CUE號，再送出訂檔（spec `docs/specs/訂檔流程_兩段式.md`）。10-21 另完成：訂檔欄位逐欄核對、收入子表可編、仿 Ragic 預覽、素材上傳、宜歆 #3～#5（2008 回饋 ×40%、元朗格式、地區北北基）。下一步：Reboot 測試 app 後實測 存檔→申請 CUE號→送出訂檔。
- 10-21 依宜歆 #11-2（送出訂檔缺欄找不到去哪填）實作「訂檔資料補齊」（spec `docs/specs/訂檔資料補齊.md`）：訂檔區分四段可就地帶客戶／補類別客服／改播證名稱、收款日期帶付款兌現日、通知欄自動、需求說明子表追加列。待宜歆重測 #11-2；素材子表下期。
- 10-16 依宜歆 10/14 測試報告修：#11 CUE號申請被拒（改明送客戶名稱／主管）、業務預設登入者、簡易模式存檔必填回簽截止日／請款月份／付款兌現日；另加年約 2008／凱絡「統一贈檔規則」（spec `docs/specs/統一贈檔規則.md`）。待宜歆重測 #4-2、#11→#15、#10 後半（開別人的 CUE）及統一方案一／二。
- 待 Jonathan 決定：CUE 管理主管預設「待審」空清單改提示／預設全部；營運加贈提示補「已訂檔記得送出更新」。
- Ragic 串接第 1～5 期已於 11-24 合併上線（spec：`docs/specs/Ragic串接_訂檔流程.md`、`docs/specs/Ragic串接_第5期_存檔編號與統計.md`）。登入／存檔／下載已在正式版實測通過，訂檔與主管功能尚待實測（下列 2、3）。
- （舊）原規劃在測試 app 實測；測試 app 已於 2026-11-24 刪除，以下項目改在正式版實測，推版後先 Reboot：
  1. Ragic 帳號登入（含開兩步驟驗證的同事）、客戶帶入、存檔給編號、存檔後下載 → Secrets `RAGIC_WRITE_ENABLED="true"`
  2. 送出訂檔：真的申請 CUE號＋建訂檔 → 加贈後送出更新原訂檔（`update_record` 子表 row id 就地更新尚未在真 Ragic 驗證）→ `RAGIC_BOOKING_ENABLED="true"`；試完刪測試 CUE號／訂檔
  3. 主管：`RAGIC_REVIEWERS` 設信箱 → CUE 管理資料夾、統計、營運加贈、抽查退回
- 待 Jonathan：是否在 cue/2 加「存檔編號」欄（給欄位 ID）；業務代碼撞號時在 `RAGIC_SALES_CODES` 指定。
- 已知限制：退回不自動刪訂檔、不寄通知；統計只算新程式存檔；待審／我的 CUE 清單掃全部紀錄（量大再優化）；代理商一鍵模板不支援加贈。
