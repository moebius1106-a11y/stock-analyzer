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

    # A. 修正期貨保證金與大電子期契約乘數
    print("正在應用修正 A：期貨保證金與大電子期契約乘數...")
    pattern_futures = re.compile(r'TW_FUTURES_SPECS\s*=\s*\{.*?"TE"\s*:\s*\{.*?\}\s*,?.*?\}', re.DOTALL)
    replacement_futures = """FUTURES_MARGIN_UPDATED_AT = "2026-11-01"
TW_FUTURES_SPECS = {
    "WTX": {"point_value": 200, "tick_size": 1.0, "margin": 338000},
    "MTX": {"point_value": 50, "tick_size": 1.0, "margin": 84500},
    "TE": {"point_value": 4000, "tick_size": 0.05, "margin": 368000},
}"""
    if 'TW_FUTURES_SPECS' in content:
        # 尋找舊的字典定義並取代，這裡使用較暴力的字串取代以確保覆蓋
        # 為了安全，我們假設使用者的代碼結構沒有偏離太多
        if '"TE": {"point_value": 400' in content or "'TE': {'point_value': 400" in content:
             content = re.sub(r'TW_FUTURES_SPECS\s*=\s*\{.*?\}', replacement_futures, content, flags=re.DOTALL)
        elif 'TW_FUTURES_SPECS' in content and 'FUTURES_MARGIN_UPDATED_AT' not in content:
             content = re.sub(r'TW_FUTURES_SPECS\s*=\s*\{.*?\}', replacement_futures, content, flags=re.DOTALL)
    
    # B. 臺銀匯率 CSV 防禦定位
    print("正在應用修正 B：臺銀匯率 CSV 防禦定位...")
    pattern_forex = re.compile(r'def fetch_bot_forex\(\):.*?except Exception', re.DOTALL)
    
    if 'def fetch_bot_forex():' in content and 'idx_spot_buy' not in content:
        # 直接取代整個 fetch_bot_forex 函數直到 except
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


    # C. 戰情室管理員存取控制
    print("正在應用修正 C：戰情室管理員存取控制...")
    if 'def save_market_briefing(content):' in content and 'st.secrets.get("ADMIN_PIN"' not in content:
        old_briefing = """def save_market_briefing(content):
    with open("market_briefings.json", "w") as f:
         json.dump({"briefing": content}, f)"""
        old_briefing_2 = """def save_market_briefing(content):
    with open('market_briefings.json', 'w') as f:
        json.dump({'briefing': content}, f)"""
        
        new_briefing = """def save_market_briefing(content):
    import json
    import streamlit as st
    admin_pin = st.secrets.get("ADMIN_PIN", None)
    if admin_pin and st.session_state.get("user_input_pin") == admin_pin:
        with open("market_briefings.json", "w", encoding="utf-8") as f:
             json.dump({"briefing": content}, f, ensure_ascii=False)
    else:
        st.session_state["local_briefing"] = content"""
        
        if old_briefing in content:
            content = content.replace(old_briefing, new_briefing)
        elif old_briefing_2 in content:
            content = content.replace(old_briefing_2, new_briefing)
        else:
             # 如果找不到完全匹配的，就用正則替換函數內容
             content = re.sub(r'def save_market_briefing\(content\):.*?json\.dump.*?f\)', new_briefing, content, flags=re.DOTALL)

    if content != original_content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ 成功修補 {filepath}！A, B, C 三點邏輯已寫入。")
        return True
    else:
        print(f"⚠️ {filepath} 未發生變更，可能是已經修補過，或者程式碼結構與預期差異過大。")
        return False

if __name__ == "__main__":
    patch_file("app.py")
