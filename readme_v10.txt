股期決策旗艦站 V10 升級說明 (含 Altair 相容性修復)

這個 ZIP 包含了修復 Streamlit Cloud 上 Python 3.13+ `altair` 崩潰問題的 requirements.txt，以及 V10 的所有更新模組與自動修補腳本。

【升級步驟】
1. 將此 ZIP 解壓縮，並將裡面的所有檔案（包含 .py 與 .txt）複製到您的 `stock-analyzer` 專案根目錄，覆蓋舊檔。
   - 確認 `requirements.txt` 內已被替換為 `altair>=5.5.1`。
2. 開啟您的終端機 (Terminal)，確認您位於專案根目錄下。
3. 執行指令： `python patch_app.py`
4. 該腳本會自動尋找您的 `app.py`，並完美將以下三點邏輯寫入：
   A. 期貨保證金 (大電子期契約乘數修正為 4000)
   B. 臺銀匯率 CSV 防禦定位 (動態找尋 Header)
   C. 戰情室管理員存取控制 (加入 ADMIN_PIN 驗證)
5. 腳本顯示「✅ 成功修補」後，將所有檔案推上 GitHub (Push)。
6. Streamlit Cloud 會自動重新建置，拉取最新版的 `altair`，崩潰問題即告解除。
