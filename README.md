# 股期決策旗艦站 V10

跨市場量化研究與看盤輔助平台（台股、美股、期貨、ETF、外匯與機構級 AI 研究員模組）。

## 部署與設定重點
- **Python 版本建議**：使用 Python 3.12 部署於 Streamlit Community Cloud。
- **伺服器安全組態**：`.streamlit/config.toml` 已啟用 `enableXsrfProtection = true` 與 `enableCORS = true`。
- **管理員金鑰**：若需開放全域戰情發布，請於 `st.secrets` 設定 `ADMIN_PIN`；一般訪客置頂僅影響個人 Session。
- **風險聲明**：本系統所有指標、回測與機率估計皆為量化研究與輔助參考，不構成投資建議。
