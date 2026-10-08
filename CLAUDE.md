# newcue

## 一句話
這個 app 給 聲活科技的業務／同事 用來 產生廣告 CUE 表（七組合：子公司／2008／凱絡）與代理商報價，並輸出 Excel／PDF。

## 現況
- 狀態：🟢 LIVE（簡易模式 v2 已上線，見 `newcue_簡易模式_開發摘要.md`）
- 本機：`C:\dev\newcue`
- push：`gn00595067-rgb/newcue.git` · `main`（push 後 Streamlit Cloud 自動部署）
- 線上：https://newcue-abjxjcgtl2ticg9hnucixz.streamlit.app/（2026-10-05 重建，舊網址失效）
- Secrets（只列名稱）：`RAGIC_API_KEY`、`RAGIC_URL`、`SUPERVISOR_PASSWORD`、`AGENCY_PASSWORD`（代理商CUE 密碼，未設時預設 123）（見 `.streamlit/secrets.toml.example`）

## 地雷（踩過的坑，改 code 前先看）
- Excel 產出一律用「值版」下載；openpyxl 公式版在受保護檢視會空白。
- strict fidelity：樣式對齊母版 `simple_style_master.py`，改樣式必跑 `tests/fidelity.py`／`tests/visual_check.py`。
- 家樂福已改名「萬家福．樂家康」（台灣通路改名，commit 73615cd）。
- Streamlit Cloud 的 Python 版本以「App settings → General → Python version」為準（runtime.txt 不生效），必須設 3.12；3.14 會裝不起來（pyarrow 無 wheel）。requirements 已鎖上限，升版前先用 `uv pip compile --python-version 3.12 --only-binary :all:` 驗證。
- requirements.txt 是全套件鎖死版（頂層來源在 requirements.in）。2026-10-05 Cloud 重新佈機抓到 9/30 後新版套件（疑 gitpython 3.2.0）→ 伺服器卡死一直轉圈、log 空白；鎖回 9/29 版本後恢復。升版務必用 `uv pip compile requirements.in --python-version 3.12 --only-binary :all: --exclude-newer <日期>` 重產並本機跑過。
- 線上 app 網址已變更（刪除重建）：https://newcue-abjxjcgtl2ticg9hnucixz.streamlit.app/
- 一般 CUE 備註來源是 `utils.get_remarks_text`（年約季約共用）；簡易模式子公司組合也共用同一份（2026-10-08 起）；改備註要同步更新 `tests/test_simple_excel.py` 的允許差異。備註字色看內容（`utils.remark_color`），不看編號。
- 萬家福．樂家康在 CUE 上逐列顯示萬家福／樂家康、量販店／超市，是渲染時 `utils.cue_station／cue_location` 轉的；rows 的 region 仍是「全省量販／全省超市」（回饋、Ragic 靠它比對），不要改 region。
- <其他地雷待補>

## 架構速覽
- 入口：`app.py`
- 簡易模式：`simple_cue.py`／`simple_model.py`／`simple_excel.py`／`simple_html.py`／`simple_style_master.py`／`simple_reach.py`（預估曝光／人流）／`simple_preview.py`
- 固定專案：`fixed_projects.py`（製作模式「專案CUE」，目前：萬家福/樂家康 116年度過年、中元限定專案；新增專案只加資料）
- 代理商：`agency_cue.py`／`agency_excel.py`／`agency_ui.py`／`rebate.py`（牌價／折讓）
- 產出渲染：`excel_renderer.py`／`html_generator.py`／`pdf_render.py`／`pdf_converter.py`／`xlsx_numfmt.py`
- 資料／設定：`data_loader.py`／`config.py`／`simple_config.py`／`各平台人流計算方式.xlsx`／`AgencyPricing範本.csv`
- 外部：Ragic（`ragic_api.py`）
- 測試：`tests/`（含 fidelity／visual_check／各模式 smoke）

## 下次續做
- （由 /wrap 維護）
