import re
import os
import sys

def patch_file(filepath):
    if not os.path.exists(filepath):
        print(f"找不到 {filepath}，請確保此腳本與 app.py 位於同一目錄。")
        return False

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    original_content = content

    # 新增 D. 修正大標題 (V9.9 -> V10)
    print("正在應用修正 D：更新主標題至 V10...")
    content = re.sub(r'st\.title\(.*?V9\.9.*?跨市場機構版.*?\)', 'st.title("📊 股期決策旗艦站 V10 (跨市場機構版)")', content)

    # 新增 E. 修正展開選單文字與版本說明內容
    print("正在應用修正 E：更新版本說明選單與清單...")
    content = re.sub(r'點此查看 【系統現行版本完整功能清單與版本說明 \(V9\.9 旗艦機構研究版\)】', '點此查看 【系統現行版本完整功能清單與版本說明 (V10 旗艦機構研究版)】', content)
    
    # 替換掉從未實作的假功能說明，並加入 V10 新功能
    old_version_notes = """    - 納入限空令與國安基金增益 (政策保護因子)
    - 支援微型那指期貨 (NQ=F)
    - TSM 370 美元鐵底警報功能"""
    new_version_notes = """    - 移除無統計依據之手寫預測，全面升級為 Ridge 迴歸嚴格樣本外殘差驗證模型
    - 優化 10 分鐘局部刷新機制，降低伺服器負擔並阻絕逾時
    - 修正大電子期保證金及動態臺銀匯率防護，確保資料誠實性"""
    if old_version_notes in content:
        content = content.replace(old_version_notes, new_version_notes)
    
    # 新增 F. 修復預測模組消失的問題
    print("正在應用修正 F：掛載 Ridge 模型預測模組...")
    # 1. 確保模組被 import
    if "from next_day_forecast import next_day_forecast_fragment" not in content:
        content = "from next_day_forecast import next_day_forecast_fragment\n" + content
    
    # 2. 找到 render_us_live_dashboard 或是原本呼叫 render_next_day_forecast_panel 的地方
    # 如果原本有 render_next_day_forecast_panel 則直接替換
    if "render_next_day_forecast_panel()" in content and "def render_next_day_forecast_panel" not in content:
         content = content.replace("render_next_day_forecast_panel()", "next_day_forecast_fragment()")
    else:
        # 如果已被刪除導致消失，強制在美股看盤室下方補上
        pattern_us_live = re.compile(r'(def render_us_live_dashboard\(\):.*?)(st\.markdown|st\.subheader)', re.DOTALL)
        if "next_day_forecast_fragment()" not in content:
            # 暴力在 render_us_live_dashboard 開頭加上
             content = re.sub(r'(def render_us_live_dashboard\(\):\n)', r'\1    next_day_forecast_fragment()\n\n', content)

    # 保留原本的 A, B, C 修復
    print("正在應用修正 A, B, C...")
    # A. 修正期貨保證金
    replacement_futures = """FUTURES_MARGIN_UPDATED_AT = "2026-11-01"
TW_FUTURES_SPECS = {
    "WTX": {"point_value": 200, "tick_size": 1.0, "margin": 338000},
    "MTX": {"point_value": 50, "tick_size": 1.0, "margin": 84500},
    "TE": {"point_value": 4000, "tick_size": 0.05, "margin": 368000},
}"""
    if '"TE": {"point_value": 400' in content or "'TE': {'point_value': 400" in content:
         content = re.sub(r'TW_FUTURES_SPECS\s*=\s*\{.*?\}', replacement_futures, content, flags=re.DOTALL)
    
    # B. 臺銀匯率 CSV
    if 'def fetch_bot_forex():' in content and 'idx_spot_buy' not in content:
        new_forex_func = """def fetch_bot_forex():
    import csv, io, logging, requests
    try:
        response = requests.get("https://rate.bot.com.tw/xrt/flcsv/0/day", timeout=5)
        response.encoding = 'utf-8'
        reader = csv.reader(io.StringIO(response.text))
        header = next(reader)
        
        idx_spot_buy = header.index('本行即期買入')
        idx_spot_sell = header.index('本行即期賣出')
        
        for row in reader:
            if row[0] == 'USD':
                buy = float(row[idx_spot_buy])
                sell = float(row[idx_spot_sell])
                return (buy + sell) / 2
    except Exception"""
        content = re.sub(r'def fetch_bot_forex\(\):.*?except Exception', new_forex_func, content, flags=re.DOTALL)

    # C. 管理員鎖
    if 'def save_market_briefing(content):' in content and 'st.secrets.get("ADMIN_PIN"' not in content:
        new_briefing = """def save_market_briefing(content):
    import json
    import streamlit as st
    admin_pin = st.secrets.get("ADMIN_PIN", None)
    if admin_pin and st.session_state.get("user_input_pin") == admin_pin:
        with open("market_briefings.json", "w", encoding="utf-8") as f:
             json.dump({"briefing": content}, f, ensure_ascii=False)
    else:
        st.session_state["local_briefing"] = content"""
        content = re.sub(r'def save_market_briefing\(content\):.*?json\.dump.*?f\)', new_briefing, content, flags=re.DOTALL)

    if content != original_content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ 成功修補 {filepath}！主標題、版本說明與預測模組已全面更新至 V10。")
        return True
    else:
        print(f"⚠️ {filepath} 未發生變更，可能是已經修補過，或者程式碼結構與預期差異過大。")
        return False

if __name__ == "__main__":
    patch_file("app.py")
