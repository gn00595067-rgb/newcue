# newcue

## 一句話
這個 app 給 聲活科技的業務／同事 用來 產生廣告 CUE 表（七組合：子公司／2008／凱絡）與代理商報價，並輸出 Excel／PDF。

## 現況
- 狀態：🟢 LIVE（簡易模式 v2 已上線，見 `newcue_簡易模式_開發摘要.md`）
- 本機：`C:\dev\newcue`
- push：`gn00595067-rgb/newcue.git` · `main`（push 後 Streamlit Cloud 自動部署）
- 線上：https://newcue-uxlbmxtahmsegh4c6cbysb.streamlit.app/
- Secrets（只列名稱）：`RAGIC_API_KEY`、`RAGIC_URL`、`SUPERVISOR_PASSWORD`（見 `.streamlit/secrets.toml.example`）

## 地雷（踩過的坑，改 code 前先看）
- Excel 產出一律用「值版」下載；openpyxl 公式版在受保護檢視會空白。
- strict fidelity：樣式對齊母版 `simple_style_master.py`，改樣式必跑 `tests/fidelity.py`／`tests/visual_check.py`。
- 家樂福已改名「萬家福．樂家康」（台灣通路改名，commit 73615cd）。
- <其他地雷待補>

## 架構速覽
- 入口：`app.py`
- 簡易模式：`simple_cue.py`／`simple_model.py`／`simple_excel.py`／`simple_html.py`／`simple_style_master.py`／`simple_reach.py`（預估曝光／人流）／`simple_preview.py`
- 代理商：`agency_cue.py`／`agency_excel.py`／`agency_ui.py`／`rebate.py`（牌價／折讓）
- 產出渲染：`excel_renderer.py`／`html_generator.py`／`pdf_render.py`／`pdf_converter.py`／`xlsx_numfmt.py`
- 資料／設定：`data_loader.py`／`config.py`／`simple_config.py`／`各平台人流計算方式.xlsx`／`AgencyPricing範本.csv`
- 外部：Ragic（`ragic_api.py`）
- 測試：`tests/`（含 fidelity／visual_check／各模式 smoke）

## 下次續做
- （由 /wrap 維護）
