# stock-analyzer-dev (測試環境 V9.9 旗艦機構研究版)

## 測試環境專屬配置
- 於 Streamlit Cloud Secrets 設定 `APP_ENV = "dev"` 即可在標題自動顯示 `[DEV 測試環境]` 識別徽章，避免與正式站混淆。
- GitHub Actions 保活腳本優先讀取 `STREAMLIT_DEV_URL` 並執行真實 HTTP 200 健康檢查。

## 快速啟動
```bash
pip install -r requirements.txt
APP_ENV=dev streamlit run app.py
```
