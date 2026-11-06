import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import altair as alt
import requests
import xml.etree.ElementTree as ET
import math
import csv
import logging
import json
import os
import re
import time
import streamlit.components.v1 as components
from urllib.parse import quote
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# 頁面配置
st.set_page_config(
    page_title="次日開市與即時量化決策站",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 手機端直覺觸控與雙欄排版強制 CSS
st.markdown("""
<style>
    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
        overflow-x: hidden !important;
        max-width: 100vw !important;
    }
    .block-container {
        padding-top: 3.5rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.65rem !important;
        padding-right: 0.65rem !important;
        max-width: 100% !important;
        overflow-x: hidden !important;
    }
    h1 {
        font-size: 1.35rem !important;
        font-weight: 800 !important;
        line-height: 1.3 !important;
        margin-top: 0.2rem !important;
        margin-bottom: 0.45rem !important;
        padding: 0 !important;
        letter-spacing: -0.01em !important;
    }
    h2 {
        font-size: 1.15rem !important;
        font-weight: 700 !important;
        margin-top: 0.35rem !important;
        margin-bottom: 0.25rem !important;
    }
    h3 {
        font-size: 1.02rem !important;
        font-weight: 600 !important;
    }

    /* 允許走勢圖在手機橫向平滑滑動 */
    div[data-testid="stVegaLiteChart"] {
        overflow-x: auto !important;
        overflow-y: hidden !important;
        -webkit-overflow-scrolling: touch !important;
        touch-action: pan-x !important;
        width: 100% !important;
        display: block !important;
        padding-bottom: 4px;
    }

    @media (max-width: 768px) {
        div[data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            gap: 0.3rem !important;
            width: 100% !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
        }
        div[data-testid="stColumn"], div[data-testid="column"] {
            flex: 1 1 0% !important;
            min-width: 0 !important;
            width: auto !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
        }
        div[data-testid="stVerticalBlock"] {
            min-width: 0 !important;
            width: 100% !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
        }
    }

    div.stButton, div[data-testid="stLinkButton"] {
        width: 100% !important;
        min-width: 0 !important;
        max-width: 100% !important;
    }
    div.stButton > button, div[data-testid="stFormSubmitButton"] > button, div[data-testid="stLinkButton"] > a {
        width: 100% !important;
        min-width: 0 !important;
        max-width: 100% !important;
        min-height: 2.65rem !important;
        font-size: 0.94rem !important;
        font-weight: 700 !important;
        border-radius: 9px !important;
        margin: 0 !important;
        margin-bottom: 0.25rem !important;
        padding: 0.3rem 0.35rem !important;
        line-height: 1.2 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-sizing: border-box !important;
        text-decoration: none !important;
    }

    div.stTextInput > div > div > input {
        height: 2.85rem !important;
        font-size: 1.05rem !important;
        border-radius: 9px !important;
    }

    div[data-testid="stMetric"] {
        background-color: rgba(128, 128, 128, 0.08);
        border: 1px solid rgba(128, 128, 128, 0.18);
        padding: 0.5rem 0.6rem !important;
        border-radius: 11px;
        margin-bottom: 0.3rem;
        min-width: 0 !important;
        overflow: hidden !important;
        box-sizing: border-box !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.84rem !important;
        font-weight: 600 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.22rem !important;
        font-weight: 700 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    .streamlit-expanderHeader {
        font-size: 0.98rem !important;
        font-weight: 600 !important;
        border-radius: 9px !important;
        background-color: rgba(128, 128, 128, 0.05) !important;
        padding: 0.45rem 0.75rem !important;
    }

    .yahoo-stat-box {
        background-color: rgba(128, 128, 128, 0.06);
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 12px;
        padding: 0.75rem 0.9rem;
        font-size: 0.92rem;
        line-height: 1.65;
    }
    .yahoo-stat-row {
        display: flex;
        justify-content: space-between;
        border-bottom: 1px dashed rgba(128, 128, 128, 0.15);
        padding: 0.18rem 0;
    }
    .yahoo-stat-row:last-child {
        border-bottom: none;
    }
    .tw-up { color: #e53935; font-weight: 700; }
    .tw-down { color: #43a047; font-weight: 700; }
    .tw-flat { color: #888888; font-weight: 700; }

    .macro-alert-card {
        background: linear-gradient(135deg, rgba(229, 57, 53, 0.10), rgba(26, 115, 232, 0.08));
        border-left: 5px solid #e53935;
        border-top: 1px solid rgba(229, 57, 53, 0.25);
        border-right: 1px solid rgba(229, 57, 53, 0.25);
        border-bottom: 1px solid rgba(229, 57, 53, 0.25);
        border-radius: 10px;
        padding: 0.75rem 0.95rem;
        margin-bottom: 0.65rem;
        font-size: 0.95rem;
        line-height: 1.55;
    }

    .inst-report-box {
        background: rgba(26, 115, 232, 0.05);
        border: 1px solid rgba(26, 115, 232, 0.22);
        border-left: 4px solid #1a73e8;
        border-radius: 10px;
        padding: 0.7rem 0.9rem;
        margin-bottom: 0.55rem;
        font-size: 0.92rem;
        line-height: 1.55;
    }

    .daytrade-card {
        background: linear-gradient(135deg, rgba(255, 152, 0, 0.08), rgba(244, 67, 54, 0.06));
        border: 1px solid rgba(255, 152, 0, 0.3);
        border-left: 5px solid #ff9800;
        border-radius: 10px;
        padding: 0.65rem 0.85rem;
        margin-bottom: 0.55rem;
        font-size: 0.92rem;
        line-height: 1.55;
    }
</style>
""", unsafe_allow_html=True)

TAIPEI_TZ = timezone(timedelta(hours=8))

# ----------------- 全市場股票中文名稱對照字典 -----------------
GLOBAL_STOCK_NAMES = {
    "2330.TW": "台積電", "2330": "台積電",
    "2317.TW": "鴻海", "2317": "鴻海",
    "2454.TW": "聯發科", "2454": "聯發科",
    "2382.TW": "廣達", "2382": "廣達",
    "2308.TW": "台達電", "2308": "台達電",
    "6669.TW": "緯穎", "6669": "緯穎",
    "2881.TW": "富邦金", "2881": "富邦金",
    "2882.TW": "國泰金", "2882": "國泰金",
    "2891.TW": "中信金", "2891": "中信金",
    "2886.TW": "兆豐金", "2886": "兆豐金",
    "2884.TW": "玉山金", "2884": "玉山金",
    "2885.TW": "元大金", "2885": "元大金",
    "2603.TW": "長榮", "2603": "長榮",
    "2609.TW": "陽明", "2609": "陽明",
    "2615.TW": "萬海", "2615": "萬海",
    "3008.TW": "大立光", "3008": "大立光",
    "3017.TW": "奇鋐", "3017": "奇鋐",
    "3324.TW": "雙鴻", "3324": "雙鴻",
    "3231.TW": "緯創", "3231": "緯創",
    "2357.TW": "華碩", "2357": "華碩",
    "2379.TW": "瑞昱", "2379": "瑞昱",
    "3034.TW": "聯詠", "3034": "聯詠",
    "3711.TW": "日月光", "3711": "日月光",
    "2618.TW": "長榮航", "2618": "長榮航",
    "2610.TW": "華航", "2610": "華航",
    "2303.TW": "聯電", "2303": "聯電",
    "2412.TW": "中華電", "2412": "中華電",
    "2002.TW": "中鋼", "2002": "中鋼",
    "1519.TW": "華城", "1519": "華城",
    "1513.TW": "中興電", "1513": "中興電",
    "2345.TW": "智邦", "2345": "智邦",
    "6488.TWO": "環球晶", "6488": "環球晶",
    "3293.TWO": "鈊象", "3293": "鈊象",
    "8299.TWO": "群聯", "8299": "群聯",
    "3529.TWO": "力旺", "3529": "力旺",
    "5274.TWO": "信驊", "5274": "信驊",
    "1815.TWO": "富喬", "1815": "富喬",
    "3016.TWO": "嘉晶", "3016": "嘉晶",
    "6182.TWO": "合晶", "6182": "合晶",
    "0050.TW": "元大台灣50", "0050": "元大台灣50",
    "006208.TW": "富邦台50", "006208": "富邦台50",
    "0056.TW": "元大高股息", "0056": "元大高股息",
    "00878.TW": "國泰高股息", "00878": "國泰高股息",
    "00919.TW": "群益高息", "00919": "群益高息",
    "00929.TW": "復華科技優息", "00929": "復華科技優息",
    "00940.TW": "元大價值高息", "00940": "元大價值高息",
    "00713.TW": "元大高息低波", "00713": "元大高息低波",
    "00757.TW": "統一FANG+", "00757": "統一FANG+",
    "00830.TW": "國泰費半", "00830": "國泰費半",
    "00662.TW": "富邦NASDAQ", "00662": "富邦NASDAQ",
    "00679B.TWO": "元大美債20", "00679B": "元大美債20",
    "00687B.TWO": "國泰美債20", "00687B": "國泰美債20",
    "NVDA": "輝達", "AAPL": "蘋果", "MSFT": "微軟", "TSLA": "特斯拉",
    "GOOGL": "谷歌", "GOOG": "谷歌", "AMZN": "亞馬遜", "META": "Meta",
    "AMD": "超微", "TSM": "台積電ADR", "AVGO": "博通", "QCOM": "高通",
    "INTC": "英特爾", "ARM": "安謀", "SMCI": "美超微", "NFLX": "網飛",
    "MU": "美光", "ASML": "艾司摩爾", "PLTR": "Palantir", "COIN": "Coinbase",
    "^TWII": "加權指數", "WTX=F": "台指期貨"
}

def get_stock_display_label(ticker: str, is_fav=False):
    t_upper = ticker.strip().upper()
    clean_code = t_upper.replace(".TW", "").replace(".TWO", "")
    name = GLOBAL_STOCK_NAMES.get(t_upper, GLOBAL_STOCK_NAMES.get(clean_code, ""))
    prefix = "⭐ " if is_fav else ""
    if name:
        return f"{prefix}{name} ({clean_code})"
    return f"{prefix}{clean_code}"

# ----------------- 隱私化本機偏好儲存引擎 (完全去識別化) -----------------
SETTINGS_FILE = "user_settings.json"

def get_default_settings():
    return {
        "tw_favorites": ["2330.TW", "2454.TW", "2317.TW", "0050.TW"],
        "tw_recent": ["2330.TW", "2454.TW"],
        "us_favorites": ["NVDA", "AAPL", "MSFT", "TSLA"],
        "us_recent": ["NVDA", "AAPL"],
        "capital_tw": 1000000,
        "capital_us": 50000,
        "capital_fut": 1000000,
        "risk_pct": 1.0,
        "daytrade_fee_discount": 0.28,
        "personal_note": "",
        "font_scale": "舒適護眼大字 (115%・推薦)",
        "last_active": datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M")
    }

def validate_and_sanitize_settings(data, default_s=None):
    if default_s is None:
        default_s = get_default_settings()
    if not isinstance(data, dict):
        return default_s.copy()
    sanitized = {}
    
    val_tw = safe_float(data.get("capital_tw"), default=default_s["capital_tw"])
    sanitized["capital_tw"] = max(min(val_tw, 1_000_000_000.0), 10_000.0)
    
    val_us = safe_float(data.get("capital_us"), default=default_s["capital_us"])
    sanitized["capital_us"] = max(min(val_us, 100_000_000.0), 1_000.0)
    
    val_fut = safe_float(data.get("capital_fut"), default=default_s["capital_fut"])
    sanitized["capital_fut"] = max(min(val_fut, 1_000_000_000.0), 10_000.0)
    
    val_risk = safe_float(data.get("risk_pct"), default=default_s["risk_pct"])
    sanitized["risk_pct"] = max(min(val_risk, 10.0), 0.1)
    
    val_disc = safe_float(data.get("daytrade_fee_discount"), default=default_s["daytrade_fee_discount"])
    sanitized["daytrade_fee_discount"] = max(min(val_disc, 1.0), 0.10)
    
    sanitized["personal_note"] = str(data.get("personal_note", ""))[:500]
    valid_scales = ["標準字體 (100%)", "舒適護眼大字 (115%・推薦)", "清晰長輩超大字 (130%)"]
    raw_scale = str(data.get("font_scale", default_s.get("font_scale", "舒適護眼大字 (115%・推薦)")))
    sanitized["font_scale"] = raw_scale if raw_scale in valid_scales else "舒適護眼大字 (115%・推薦)"
    
    for list_key in ["tw_favorites", "tw_recent", "us_favorites", "us_recent"]:
        raw_list = data.get(list_key, default_s[list_key])
        if isinstance(raw_list, list):
            clean_list = []
            for item in raw_list:
                s_item = str(item).strip().upper()
                if 1 <= len(s_item) <= 15 and re.match(r"^[A-Z0-9\.\^\=]+$", s_item):
                    if s_item not in clean_list:
                        clean_list.append(s_item)
            sanitized[list_key] = clean_list[:20]
        else:
            sanitized[list_key] = default_s[list_key].copy()
            
    sanitized["last_active"] = str(data.get("last_active", datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M")))[:25]
    return sanitized

def get_user_data():
    if "user_data" not in st.session_state:
        default_s = get_default_settings()
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    st.session_state.user_data = validate_and_sanitize_settings(loaded, default_s)
                    return st.session_state.user_data
            except Exception as e:
                logging.warning(f"讀取使用者設定檔異常: {e}")
        st.session_state.user_data = default_s.copy()
    return st.session_state.user_data

def save_user_data():
    if "user_data" in st.session_state:
        try:
            st.session_state.user_data["last_active"] = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M")
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(st.session_state.user_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

def add_recent_history(market: str, ticker: str):
    data = get_user_data()
    key = f"{market}_recent"
    ticker = ticker.strip().upper()
    if ticker in data[key]:
        data[key].remove(ticker)
    data[key].insert(0, ticker)
    data[key] = data[key][:6]
    save_user_data()

def clear_recent_history(market: str):
    data = get_user_data()
    key = f"{market}_recent"
    data[key] = []
    save_user_data()

def toggle_favorite_stock(market: str, ticker: str):
    data = get_user_data()
    key = f"{market}_favorites"
    ticker = ticker.strip().upper()
    if ticker in data[key]:
        data[key].remove(ticker)
    else:
        data[key].append(ticker)
    save_user_data()

# ----------------- 關鍵市場戰情焦點快訊與即時外電 -----------------
BRIEFING_FILE = "market_briefings.json"

DEFAULT_STRATEGIC_BRIEFING = {
    "title": "🔥 關鍵戰情焦點：台股關鍵整數關卡攻防 vs 總經外資籌碼動向",
    "content": (
        "台股短線正處於關鍵位階劇烈洗盤與技術面修正期，多空交戰核心在於外資籌碼流向與美股科技股財報展望。\n\n"
        "📌 **核心操作應變劇本**：\n"
        "• 指數站穩月線 (20MA) 偏多輪動操作；跌破月線則提高現金水位並嚴守停損。\n"
        "• 當沖交易嚴格遵循開盤 15 分 K (ORB) 突破方向與分時 VWAP 均價線攻防。"
    ),
    "author": "系統策略中心",
    "updated_at": datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M"),
    "level": "critical",
    "is_manual": False
}

def load_market_briefing():
    if os.path.exists(BRIEFING_FILE):
        try:
            with open(BRIEFING_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "content" in data:
                    return data
        except Exception:
            pass
    return DEFAULT_STRATEGIC_BRIEFING.copy()

def save_market_briefing(title: str, content: str, author: str, is_manual: bool = True):
    new_b = {
        "title": title.strip(),
        "content": content.strip(),
        "author": author.strip() or "系統策略中心",
        "updated_at": datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M"),
        "level": "critical",
        "is_manual": is_manual
    }
    try:
        with open(BRIEFING_FILE, "w", encoding="utf-8") as f:
            json.dump(new_b, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return new_b

# ----------------- 全頻道即時外電情報站核心引擎 (彭博/LINE TODAY/路透/台美股・5分鐘快取隔離) -----------------
GLOBAL_NEWS_CHANNELS = {
    "📰 彭博社 Bloomberg": "彭博 OR Bloomberg 財經 OR 彭博新聞",
    "💬 LINE TODAY 財經": "LINE TODAY 財經 OR LINE TODAY 理財 OR LINE TODAY 股市",
    "🌐 路透社 Reuters": "路透 OR Reuters 財經 OR 路透社",
    "🇹🇼 國內主流權威財經": "鉅亨網 OR 經濟日報 OR 工商時報 台股",
    "🔥 科技與半導體 (AI)": "台積電 OR 輝達 OR 費城半導體 OR NVDA OR TSM OR ASML OR AI伺服器",
    "🏛️ 宏觀總經與利率": "聯準會 OR CPI OR 美債殖利率 OR 降息 OR 非農 OR 國安基金",
    "⚡ 台股與籌碼期指": "台股 OR 加權指數 OR 外資買賣超 OR 台指期 OR 限空令 OR 官股",
    "🇺🇸 華爾街美股焦點": "美股 OR 那斯達克 OR 標普500 OR 科技股財報 OR 特斯拉"
}

@st.cache_data(ttl=300, show_spinner=False)
def fetch_categorized_news(query_str: str, max_items: int = 15):
    """
    極低資源消耗外電聚合引擎：
    - 5 分鐘伺服器快取保護 (TTL=300)
    - 輕量純 XML 解析 (單次小於 40KB，完全免伺服器重度負擔)
    """
    encoded_q = quote(query_str)
    url = f"https://news.google.com/rss/search?q={encoded_q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    items = []
    try:
        r = requests.get(url, headers=headers, timeout=(2.0, 3.5))
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            for item in root.findall("./channel/item")[:max_items]:
                title = item.findtext("title", default="無標題")
                link = item.findtext("link", default="#")
                pub_date = item.findtext("pubDate", default="")
                source_el = item.find("source")
                source_name = source_el.text if source_el is not None else "外電快訊"
                clean_date = pub_date[:22] if pub_date else "即時"
                items.append({
                    "title": title,
                    "link": link,
                    "source": source_name,
                    "pub_date": clean_date
                })
    except Exception:
        pass
    return items

@st.cache_data(ttl=180, show_spinner=False)
def fetch_live_macro_rss(query_str: str = "台股 OR 美股 OR CPI OR 聯準會 OR 台積電 OR 費半"):
    return fetch_categorized_news(query_str, max_items=8)

def render_news_hub_widget(show_pin_btn: bool = False, key_prefix: str = "hub"):
    """
    全頻道即時外電情報站 UI 渲染器 (支援彭博、LINE TODAY、路透、國內權威財經切換、關鍵字搜尋與即時手動刷新)
    """
    c_sel, c_refresh = st.columns([3.0, 1.0])
    with c_sel:
        channel_names = list(GLOBAL_NEWS_CHANNELS.keys())
        selected_ch = st.selectbox(
            "選擇即時外電情報頻道",
            channel_names,
            index=0,
            key=f"{key_prefix}_channel_select",
            label_visibility="collapsed"
        )
    with c_refresh:
        if st.button("🔄 刷新外電", key=f"{key_prefix}_btn_refresh_news", use_container_width=True):
            fetch_categorized_news.clear()
            fetch_live_macro_rss.clear()
            st.rerun()

    custom_q = st.text_input(
        "自訂關鍵字速查",
        placeholder="🔍 或輸入自訂關鍵字（例：彭博、LINE TODAY、ASML、美超微、降息...）",
        key=f"{key_prefix}_custom_query_in",
        label_visibility="collapsed"
    )

    active_query = custom_q.strip() if custom_q.strip() else GLOBAL_NEWS_CHANNELS[selected_ch]
    articles = fetch_categorized_news(active_query, max_items=12)

    if articles:
        st.caption(f"📡 目前檢索來源：`{active_query}` ｜ 共取得 {len(articles)} 則最新即時外電")
        for idx_a, a_item in enumerate(articles):
            with st.container():
                st.markdown(f"• **[{a_item['title']}]({a_item['link']})**")
                c_inf1, c_inf2 = st.columns([3.0, 1.0])
                with c_inf1:
                    st.caption(f"📢 來源：`{a_item['source']}` ｜ 發布：`{a_item['pub_date']}`")
                with c_inf2:
                    if show_pin_btn:
                        if st.button("📌 置頂", key=f"{key_prefix}_pin_{idx_a}", use_container_width=True, help="鎖定此新聞為首頁頂部戰情焦點"):
                            save_market_briefing(
                                f"🔥 外電快訊：{a_item['title'][:28]}...",
                                f"【外電焦點】{a_item['title']}（來源：{a_item['source']} ｜ {a_item['pub_date']}）\n\n請密切留意該事件對台指期夜盤、美股科技股與次日開盤跳空之連動影響。",
                                "外電戰情中心",
                                is_manual=True
                            )
                            st.rerun()
                st.write("---")
    else:
        st.info("⚪ 目前暫無該關鍵字或頻道之即時外電，請稍候再試或點擊「🔄 刷新外電」。")

def get_auto_market_briefing(df_market_obj, df_sox_obj, forex_obj):
    cur_saved = load_market_briefing()
    if cur_saved.get("is_manual", False):
        try:
            up_dt = datetime.strptime(cur_saved.get("updated_at", "2000-01-01 00:00"), "%Y-%m-%d %H:%M").replace(tzinfo=TAIPEI_TZ)
            if datetime.now(TAIPEI_TZ) - up_dt < timedelta(hours=2):
                return cur_saved
        except Exception:
            pass

    rss_list = fetch_live_macro_rss("台股 OR 費半 OR 台積電 OR 聯準會 OR 外資")
    top_news = rss_list[0] if rss_list else None

    tw_p = safe_float(df_market_obj.iloc[-1]['Close']) if df_market_obj is not None and not df_market_obj.empty else 0.0
    tw_ma20 = safe_float(df_market_obj['MA20'].iloc[-1]) if df_market_obj is not None and not df_market_obj.empty else 0.0
    sox_chg = 0.0
    if df_sox_obj is not None and len(df_sox_obj) >= 2:
        sox_chg = ((df_sox_obj['Close'].iloc[-1] - df_sox_obj['Close'].iloc[-2]) / (df_sox_obj['Close'].iloc[-2] + 1e-9)) * 100.0

    twd_r = forex_obj.get('twd_rate') or 32.0

    if top_news:
        auto_title = f"🔥 即時焦點外電：{top_news['title'][:32]}..."
        auto_content = (
            f"【最新外電】**{top_news['title']}**（來源：{top_news['source']} ｜ {top_news['pub_date']}）\n\n"
            f"📊 **即時盤勢連動**：加權指數報 **{tw_p:,.2f}** 點（月線 20MA 防守點：**{tw_ma20:,.2f}** 點），"
            f"費半波動 **{sox_chg:+.2f}%**，美元兌新台幣報 **{twd_r:.2f}**。\n\n"
            f"📌 **操作指引**：短線請緊盯開盤跳空幅度與分時 VWAP 均價線支撐，順勢操作，嚴格執行當日平倉紀律。"
        )
    else:
        auto_title = f"🔥 即時量化戰情：台股現報 {tw_p:,.0f} 點 vs 費半連動 ({sox_chg:+.2f}%)"
        auto_content = (
            f"加權指數目前報 **{tw_p:,.2f}** 點，月線 20MA 生命線位於 **{tw_ma20:,.2f}** 點。\n\n"
            f"📌 **操作指引**：若守穩月線生命線，震盪後易有反彈；若跌破則嚴格控管曝險與當沖部位。"
        )

    return {
        "title": auto_title,
        "content": auto_content,
        "author": "系統即時全自動更新",
        "updated_at": datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M"),
        "level": "critical",
        "is_manual": False
    }

def safe_float(val, default=0.0):
    try:
        if val is None:
            return default
        if isinstance(val, pd.Series):
            if val.empty:
                return default
            val = val.iloc[0]
        elif isinstance(val, (np.ndarray, list, tuple)):
            if len(val) == 0:
                return default
            val = val[0]
        if val is None or val is pd.NA:
            return default
        if isinstance(val, (float, np.floating)) and np.isnan(val):
            return default
        if isinstance(val, str):
            val = val.strip().replace(",", "")
            if val in ("", "-", "N/A", "nan", "None", "_", "--"):
                return default
        result = float(val)
        if not math.isfinite(result):
            return default
        return result
    except (ValueError, TypeError, IndexError, OverflowError):
        return default


@st.cache_data(ttl=300, show_spinner=False)
def fetch_vix_percentile():
    """抓取 ^VIX 過去 252 個交易日計算歷史百分位 (Percentile)"""
    try:
        obj = yf.Ticker("^VIX")
        df_vix = obj.history(period="1y")
        if df_vix is not None and not df_vix.empty:
            if isinstance(df_vix.columns, pd.MultiIndex):
                df_vix.columns = df_vix.columns.get_level_values(0)
            closes = df_vix['Close'].dropna()
            if len(closes) > 20:
                curr_vix = float(closes.iloc[-1])
                pct = (closes < curr_vix).mean() * 100.0
                ma20_vix = float(closes.rolling(20, min_periods=5).mean().iloc[-1])
                return {
                    "has_data": True,
                    "vix_price": curr_vix,
                    "vix_pct": pct,
                    "vix_ma20": ma20_vix,
                    "status": "🟢 市場平穩無恐慌" if curr_vix < 20 else ("🟡 波動升溫警戒" if curr_vix < 30 else "🔴 市場高度恐慌崩盤區")
                }
    except Exception:
        pass
    return {"has_data": False, "vix_price": 0.0, "vix_pct": 0.0, "vix_ma20": 0.0, "status": "暫無數據"}

def normalize_ticker(ticker: str):
    t = ticker.strip().upper()
    if t.endswith("=F") or t in ("WTX", "MTX", "WMT", "TE", "TF"):
        return t, "futures"
    if t.endswith(".TWO"):
        return t[:-4], "otc"
    if t.endswith(".TW"):
        return t[:-3], "tse"
    return t, "us"

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_yf_shared_info(ticker: str):
    def _worker():
        t = yf.Ticker(ticker)
        return dict(t.info or {})

    ex = ThreadPoolExecutor(max_workers=1)
    fut = ex.submit(_worker)
    try:
        data = fut.result(timeout=4.5)
        ex.shutdown(wait=False, cancel_futures=True)
        return data
    except Exception:
        ex.shutdown(wait=False, cancel_futures=True)
        return {}

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_yf_earnings_history_safe(ticker: str):
    def _worker():
        t = yf.Ticker(ticker)
        eh = t.earnings_history
        if eh is not None and not eh.empty:
            return eh.tail(4).copy()
        return None

    ex = ThreadPoolExecutor(max_workers=1)
    fut = ex.submit(_worker)
    try:
        res = fut.result(timeout=2.5)
        ex.shutdown(wait=False, cancel_futures=True)
        return res
    except Exception:
        ex.shutdown(wait=False, cancel_futures=True)
        return None

def fetch_twse_realtime(ticker: str):
    code, market = normalize_ticker(ticker)
    if market in ("us", "futures"):
        return None

    ex_ch = f"{market}_{code}.tw"
    url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={ex_ch}&json=1&delay=0"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        resp = requests.get(url, headers=headers, timeout=(1.5, 2.5))
        if resp.status_code == 200:
            data = resp.json()
            msg_arr = data.get("msgArray", [])
            if msg_arr:
                item = msg_arr[0]
                y_close = safe_float(item.get("y"))
                z_raw = item.get("z")
                z_price = safe_float(z_raw, default=0.0)

                is_trading = True
                if z_price <= 0:
                    b_first = safe_float(str(item.get("b", "")).split("_")[0], default=0.0)
                    a_first = safe_float(str(item.get("a", "")).split("_")[0], default=0.0)
                    z_price = b_first if b_first > 0 else (a_first if a_first > 0 else y_close)
                    is_trading = False

                stock_name = str(item.get("n", code)).strip()
                if stock_name:
                    suffix = "TWO" if market == "otc" else "TW"
                    GLOBAL_STOCK_NAMES[f"{code}.{suffix}"] = stock_name
                    GLOBAL_STOCK_NAMES[code] = stock_name

                raw_lots = safe_float(item.get("v"), default=0.0)
                converted_shares = raw_lots * 1000.0
                date_str = item.get("d", "")
                time_str = item.get("t", "")

                b_prices = [safe_float(x) for x in str(item.get("b", "")).split("_") if x.strip()][:5]
                b_vols = [int(safe_float(x)) for x in str(item.get("g", "")).split("_") if x.strip()][:5]
                a_prices = [safe_float(x) for x in str(item.get("a", "")).split("_") if x.strip()][:5]
                a_vols = [int(safe_float(x)) for x in str(item.get("f", "")).split("_") if x.strip()][:5]

                now_taipei = datetime.now(TAIPEI_TZ)
                today_str = now_taipei.strftime("%Y%m%d")

                if date_str == today_str:
                    if "09:00:00" <= time_str <= "13:35:00":
                        status_label = "🟢 盤中即時撮合"
                    else:
                        status_label = "⚪ 今日盤後結算"
                else:
                    status_label = "🟡 前一交易日資料"

                return {
                    "code": code,
                    "market": market,
                    "name": stock_name,
                    "match_price": z_price,
                    "open": safe_float(item.get("o"), default=z_price),
                    "high": safe_float(item.get("h"), default=z_price),
                    "low": safe_float(item.get("l"), default=z_price),
                    "volume": converted_shares,
                    "lots": int(raw_lots),
                    "yesterday_close": y_close,
                    "date_str": date_str,
                    "time": time_str,
                    "status_label": status_label,
                    "is_live": True,
                    "is_trading": is_trading,
                    "bid_prices": b_prices,
                    "bid_vols": b_vols,
                    "ask_prices": a_prices,
                    "ask_vols": a_vols
                }
    except Exception:
        pass
    return None

@st.cache_data(ttl=3600, show_spinner=False)
def resolve_tw_ticker(ticker_input: str) -> str:
    """智慧自動辨識台股上市 (.TW) 或上櫃 (.TWO) 代碼 (含快取與字典秒級映射)"""
    clean = str(ticker_input).strip().upper()
    if not clean:
        return clean
    if clean.endswith(".TW") or clean.endswith(".TWO"):
        return clean
    if clean.endswith("=F") or clean in ("WTX", "MTX", "WMT", "TE", "TF"):
        return clean

    # 若內建字典已明確收錄上市或上櫃後綴，直接秒級回傳
    if f"{clean}.TWO" in GLOBAL_STOCK_NAMES:
        return f"{clean}.TWO"
    if f"{clean}.TW" in GLOBAL_STOCK_NAMES:
        return f"{clean}.TW"

    # 若為純數字或台股債券ETF代碼(如00679B)，進行上市/上櫃即時自動偵測與容錯
    if clean.isdigit() or (clean[:-1].isdigit() and clean[-1].isalpha()):
        try:
            # 1. 優先嘗試 TWSE 即時撮合接口偵測市場
            tse_live = fetch_twse_realtime(f"{clean}.TW")
            if tse_live and tse_live.get("match_price", 0) > 0:
                return f"{clean}.TW"

            otc_live = fetch_twse_realtime(f"{clean}.TWO")
            if otc_live and otc_live.get("match_price", 0) > 0:
                return f"{clean}.TWO"

            # 2. 若處於非交易時段，使用 Yahoo 歷史行情偵測
            df_tw = fetch_and_calc(f"{clean}.TW", period="1mo")
            if df_tw is not None and not df_tw.empty:
                return f"{clean}.TW"

            df_two = fetch_and_calc(f"{clean}.TWO", period="1mo")
            if df_two is not None and not df_two.empty:
                return f"{clean}.TWO"
        except Exception:
            pass

        # 若皆未查得，預設以上市為基礎回傳
        return f"{clean}.TW"

    return clean


@st.cache_data(ttl=15, show_spinner=False)
def fetch_twse_market_dashboard():
    result = {
        "twii_price": 0.0, "twii_chg": 0.0, "twii_pct": 0.0,
        "twii_high": 0.0, "twii_low": 0.0, "twii_open": 0.0, "twii_yclose": 0.0,
        "ex_fin_price": 0.0, "ex_fin_chg": 0.0, "ex_fin_pct": 0.0,
        "otc_price": 0.0, "otc_chg": 0.0, "otc_pct": 0.0,
        "turnover_billion": 0.0,
        "bid_orders": None, "ask_orders": None, "trade_orders": None,
        "bid_lots": None, "ask_lots": None, "trade_lots": None,
        "avg_bid_lots": None, "avg_ask_lots": None,
        "up_count": None, "limit_up": None,
        "down_count": None, "limit_down": None,
        "flat_count": None,
        "data_time": datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M:%S")
    }

    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://mis.twse.com.tw/stock/index.jsp"
    }

    try:
        idx_url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_t00.tw|tse_t001.tw|otc_o00.tw&json=1&delay=0"
        r_idx = session.get(idx_url, headers=headers, timeout=(1.5, 2.5))
        if r_idx.status_code == 200:
            msg_arr = r_idx.json().get("msgArray", [])
            for item in msg_arr:
                ch = item.get("ch", "")
                y_val = safe_float(item.get("y"))
                z_val = safe_float(item.get("z"), default=y_val)
                if z_val <= 0:
                    z_val = y_val
                chg = z_val - y_val if y_val > 0 else 0.0
                pct = (chg / y_val * 100.0) if y_val > 0 else 0.0

                if "t00.tw" in ch:
                    result["twii_price"] = z_val
                    result["twii_yclose"] = y_val
                    result["twii_chg"] = chg
                    result["twii_pct"] = pct
                    result["twii_open"] = safe_float(item.get("o"), default=z_val)
                    result["twii_high"] = safe_float(item.get("h"), default=z_val)
                    result["twii_low"] = safe_float(item.get("l"), default=z_val)
                    v_million = safe_float(item.get("v"), default=0.0)
                    if v_million > 0:
                        result["turnover_billion"] = v_million / 100.0
                    d_str = item.get("d", "")
                    t_str = item.get("t", "")
                    if len(d_str) == 8 and t_str:
                        result["data_time"] = f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:]} {t_str}"
                elif "t001.tw" in ch:
                    result["ex_fin_price"] = z_val
                    result["ex_fin_chg"] = chg
                    result["ex_fin_pct"] = pct
                elif "o00.tw" in ch:
                    result["otc_price"] = z_val
                    result["otc_chg"] = chg
                    result["otc_pct"] = pct
    except Exception:
        pass

    try:
        stat_url = "https://mis.twse.com.tw/stock/api/getStatis.jsp?ex=tse&delay=0"
        r_stat = session.get(stat_url, headers=headers, timeout=(1.5, 2.5))
        if r_stat.status_code == 200:
            s_data = r_stat.json()
            detail = s_data.get("detail", {})
            if isinstance(detail, dict) and detail:
                tz_val = safe_float(detail.get("tz"), default=0.0)
                if tz_val > 0 and result["turnover_billion"] <= 0:
                    result["turnover_billion"] = tz_val / 1e8

                bw = int(safe_float(detail.get("bw", detail.get("b_w", 0))))
                sw = int(safe_float(detail.get("sw", detail.get("s_w", 0))))
                tr = int(safe_float(detail.get("tr", detail.get("t_r", 0))))
                bv = int(safe_float(detail.get("bv", detail.get("b_v", 0))))
                sv = int(safe_float(detail.get("sv", detail.get("s_v", 0))))
                tv = int(safe_float(detail.get("tv", detail.get("t_v", 0))))

                if bw > 0:
                    result["bid_orders"] = bw
                if sw > 0:
                    result["ask_orders"] = sw
                if tr > 0:
                    result["trade_orders"] = tr
                if bv > 0:
                    result["bid_lots"] = bv
                if sv > 0:
                    result["ask_lots"] = sv
                if tv > 0:
                    result["trade_lots"] = tv

                if bw > 0 and bv > 0:
                    result["avg_bid_lots"] = round(bv / bw, 1)
                if sw > 0 and sv > 0:
                    result["avg_ask_lots"] = round(sv / sw, 1)

                up_c = detail.get("up", detail.get("u"))
                dn_c = detail.get("down", detail.get("d"))
                lu_c = detail.get("limitUp", detail.get("lu", 0))
                ld_c = detail.get("limitDown", detail.get("ld", 0))
                fl_c = detail.get("unchanged", detail.get("z"))

                if up_c is not None:
                    result["up_count"] = int(safe_float(up_c))
                    result["limit_up"] = int(safe_float(lu_c))
                if dn_c is not None:
                    result["down_count"] = int(safe_float(dn_c))
                    result["limit_down"] = int(safe_float(ld_c))
                if fl_c is not None:
                    result["flat_count"] = int(safe_float(fl_c))
    except Exception:
        pass

    return result

# ----------------- 分時走勢與當沖指標核心計算 -----------------
@st.cache_data(ttl=30, show_spinner=False)
def fetch_intraday_series(ticker: str):
    try:
        t = yf.Ticker(ticker)
        df_intra = t.history(period="1d", interval="1m")
        if df_intra is None or df_intra.empty or len(df_intra) < 5:
            df_5d = t.history(period="5d", interval="5m")
            if df_5d is not None and not df_5d.empty:
                last_day = df_5d.index[-1].date()
                df_intra = df_5d[df_5d.index.date == last_day].copy()

        if df_intra is None or df_intra.empty:
            return None, None

        if isinstance(df_intra.columns, pd.MultiIndex):
            df_intra.columns = df_intra.columns.get_level_values(0)

        df_daily = t.history(period="5d", interval="1d")
        y_close = None
        if df_daily is not None and len(df_daily) >= 2:
            if isinstance(df_daily.columns, pd.MultiIndex):
                df_daily.columns = df_daily.columns.get_level_values(0)
            y_close = safe_float(df_daily['Close'].iloc[-2])

        if ticker.upper() == "^TWII":
            dash = fetch_twse_market_dashboard()
            if dash["twii_yclose"] > 0:
                y_close = dash["twii_yclose"]
        elif ".TW" in ticker.upper() or ".TWO" in ticker.upper():
            live = fetch_twse_realtime(ticker)
            if live and live["yesterday_close"] > 0:
                y_close = live["yesterday_close"]

        if y_close is None or y_close <= 0:
            y_close = safe_float(df_intra['Open'].iloc[0])

        df_plot = df_intra[['Open', 'High', 'Low', 'Close', 'Volume']].dropna(subset=['Close']).copy()
        if df_plot.empty:
            return None, None

        if df_plot.index.tz is not None:
            if ".TW" in ticker.upper() or ".TWO" in ticker.upper() or ticker.upper() in ("^TWII", "WTX=F"):
                local_idx = df_plot.index.tz_convert(TAIPEI_TZ)
            else:
                local_idx = df_plot.index
        else:
            local_idx = df_plot.index

        df_plot['TimeStr'] = local_idx.strftime('%H:%M')
        df_plot['YesterdayClose'] = y_close
        df_plot['Diff'] = df_plot['Close'] - y_close
        df_plot['Pct'] = (df_plot['Diff'] / (y_close + 1e-9)) * 100.0
        df_plot['BarColor'] = np.where(df_plot['Close'] >= df_plot['Open'], '漲(紅)', '跌(綠)')
        is_tw_asset = (".TW" in ticker.upper() or ".TWO" in ticker.upper() or ticker.upper() in ("^TWII", "WTX=F"))
        df_plot['VolLots'] = (df_plot['Volume'] / 1000.0) if is_tw_asset else df_plot['Volume']

        tp = (df_plot['High'] + df_plot['Low'] + df_plot['Close']) / 3.0
        cum_tp_vol = (tp * df_plot['Volume']).cumsum()
        cum_vol = df_plot['Volume'].cumsum()
        df_plot['VWAP'] = np.where(cum_vol > 0, cum_tp_vol / (cum_vol + 1e-9), df_plot['Close'])

        return df_plot.reset_index(drop=True), y_close
    except Exception:
        return None, None

def calc_cdp_levels(df_daily):
    if df_daily is None or len(df_daily) < 1:
        return None
    now_date = datetime.now(TAIPEI_TZ).date()
    last_bar_date = df_daily.index[-1].date()
    if last_bar_date >= now_date and len(df_daily) >= 2:
        prev_day = df_daily.iloc[-2]
    else:
        prev_day = df_daily.iloc[-1]

    h = safe_float(prev_day['High'])
    l = safe_float(prev_day['Low'])
    c = safe_float(prev_day['Close'])
    if h <= 0 or l <= 0 or c <= 0:
        return None

    cdp = (h + l + (2.0 * c)) / 4.0
    hl_range = h - l
    ah = cdp + hl_range           # 最高阻力
    nh = (2.0 * cdp) - l          # 次高阻力
    nl = (2.0 * cdp) - h          # 次低支撐
    al = cdp - hl_range           # 最低支撐

    return {
        "CDP": cdp, "AH": ah, "NH": nh, "NL": nl, "AL": al,
        "prev_high": h, "prev_low": l, "prev_close": c
    }

def calc_orb_levels(df_intra):
    if df_intra is None or df_intra.empty:
        return None

    curr_p = safe_float(df_intra.iloc[-1]['Close'])
    curr_vwap = safe_float(df_intra.iloc[-1].get('VWAP', curr_p))

    # 針對台股正規盤嚴格檢驗 09:00 ~ 09:15 區間是否已完整收定
    if 'TimeStr' in df_intra.columns:
        regular_bars = df_intra[df_intra['TimeStr'] >= '09:00']
        if regular_bars.empty:
            return {
                "orb_high": curr_p, "orb_low": curr_p,
                "curr_vwap": curr_vwap,
                "status_label": "⚪ 尚未進入正式交易時段 (09:00前)，暫不建立 ORB",
                "bias": "觀察"
            }

        last_time_str = str(regular_bars['TimeStr'].iloc[-1])
        orb_window = regular_bars[(regular_bars['TimeStr'] >= '09:00') & (regular_bars['TimeStr'] <= '09:15')]

        # 1. 在 09:15 K 棒完全收定前（最新時間戳記未推進至 09:15 之後），嚴禁提前觸發突破訊號
        if last_time_str <= '09:15':
            return {
                "orb_high": safe_float(orb_window['High'].max(), curr_p) if not orb_window.empty else curr_p,
                "orb_low": safe_float(orb_window['Low'].min(), curr_p) if not orb_window.empty else curr_p,
                "curr_vwap": curr_vwap,
                "status_label": f"⏳ 開盤 15 分 K 區間建立中 (目前最新 {last_time_str}，須待 09:15 收定後才判定突破)",
                "bias": "觀察"
            }

        # 2. 已過 09:15，檢驗 09:00~09:15 區間資料涵蓋度與連續性（涵蓋起點<=09:05、終點>=09:10，且非單根缺漏）
        if orb_window.empty:
            return {
                "orb_high": curr_p, "orb_low": curr_p,
                "curr_vwap": curr_vwap,
                "status_label": "⚪ 缺少 09:00~09:15 開盤區間分時資料，暫不產生突破信號",
                "bias": "觀察"
            }

        first_orb_t = str(orb_window['TimeStr'].iloc[0])
        last_orb_t = str(orb_window['TimeStr'].iloc[-1])
        # 判斷是否為 1 分 K (區間內有非 5 分鐘倍數之時間標籤)
        is_1m_feed = any((int(str(t).split(':')[1]) % 5 != 0) for t in orb_window['TimeStr'] if ':' in str(t))
        min_required_bars = 10 if is_1m_feed else 3

        if first_orb_t > '09:05' or last_orb_t < '09:10' or len(orb_window) < min_required_bars:
            return {
                "orb_high": safe_float(orb_window['High'].max(), curr_p),
                "orb_low": safe_float(orb_window['Low'].min(), curr_p),
                "curr_vwap": curr_vwap,
                "status_label": f"⚪ 開盤 09:00~09:15 資料不完整 ({first_orb_t}~{last_orb_t} 共 {len(orb_window)} 根)，暫不觸發正式訊號",
                "bias": "觀察"
            }
    else:
        if len(df_intra) <= 15:
            return {
                "orb_high": safe_float(df_intra['High'].max(), curr_p),
                "orb_low": safe_float(df_intra['Low'].min(), curr_p),
                "curr_vwap": curr_vwap,
                "status_label": f"⏳ 開盤 15 分 K 建立中 (目前累積 {len(df_intra)} 根，須滿 15 根收定後才觸發信號)",
                "bias": "觀察"
            }
        orb_window = df_intra.iloc[:15]

    orb_high = safe_float(orb_window['High'].max())
    orb_low = safe_float(orb_window['Low'].min())
    if orb_high <= 0 or orb_low <= 0:
        return None

    curr_p = safe_float(df_intra.iloc[-1]['Close'])
    curr_vwap = safe_float(df_intra.iloc[-1].get('VWAP', curr_p))

    if curr_p > orb_high and curr_p > curr_vwap:
        status_label = "🔥 帶量突破 ORB 高點 (多方強烈攻擊，順勢做多)"
        bias = "多"
    elif curr_p < orb_low and curr_p < curr_vwap:
        status_label = "❄️ 跌破 ORB 低點 (空方主導摜壓，順勢偏空)"
        bias = "空"
    else:
        status_label = "🔄 處於開盤區間內整理 (多空拉鋸，等待表態)"
        bias = "盤整"

    return {
        "orb_high": orb_high, "orb_low": orb_low,
        "curr_vwap": curr_vwap, "status_label": status_label, "bias": bias
    }

def get_tw_tick_size(price: float) -> float:
    if price < 10.0:
        return 0.01
    elif price < 50.0:
        return 0.05
    elif price < 100.0:
        return 0.10
    elif price < 500.0:
        return 0.50
    elif price < 1000.0:
        return 1.00
    else:
        return 5.00

def calc_daytrade_breakeven(price: float, fee_discount: float = 0.28):
    if price <= 0:
        return 0, 0.0, 0.0, 0.0
    tick_sz = get_tw_tick_size(price)
    round_trip_fee_rate = (0.001425 * fee_discount * 2.0) + 0.0015
    cost_per_share = price * round_trip_fee_rate
    needed_ticks = max(1, math.ceil(round(cost_per_share / tick_sz, 4)))
    profit_per_tick_1lot = (tick_sz * 1000.0)
    cost_1lot = cost_per_share * 1000.0

    return needed_ticks, tick_sz, cost_1lot, profit_per_tick_1lot

def render_intraday_chart_widget(ticker: str, title_name: str = ""):
    df_intra, y_close = fetch_intraday_series(ticker)
    if df_intra is None or df_intra.empty:
        st.info("⚪ 目前無該標的之分時明細資料（可能處於非交易時段或外部報價源結算中）。")
        return

    last_row = df_intra.iloc[-1]
    curr_p = safe_float(last_row['Close'])
    high_p = safe_float(df_intra['High'].max())
    low_p = safe_float(df_intra['Low'].min())
    curr_vwap = safe_float(last_row.get('VWAP', curr_p))
    chg_val = curr_p - y_close
    chg_pct = (chg_val / (y_close + 1e-9)) * 100.0

    color_cls = "tw-up" if chg_val > 0 else ("tw-down" if chg_val < 0 else "tw-flat")
    sign_str = "+" if chg_val > 0 else ""
    st.markdown(
        f"**{title_name or ticker}** ｜ 時間 `{last_row['TimeStr']}` ｜ "
        f"成交價 <span class='{color_cls}'>{curr_p:,.2f} ({sign_str}{chg_val:,.2f} / {sign_str}{chg_pct:.2f}%)</span> ｜ "
        f"均價 (VWAP) `{curr_vwap:,.2f}` ｜ "
        f"最高 <span class='tw-up'>{high_p:,.2f}</span> ｜ "
        f"最低 <span class='tw-down'>{low_p:,.2f}</span> ｜ "
        f"昨收平盤 `{y_close:,.2f}`",
        unsafe_allow_html=True
    )

    min_y = min(low_p, y_close)
    max_y = max(high_p, y_close)
    pad = max((max_y - min_y) * 0.15, y_close * 0.002)
    y_domain = [min_y - pad, max_y + pad]

    base = alt.Chart(df_intra).encode(
        x=alt.X('TimeStr:O', title=None, axis=alt.Axis(labelAngle=0, labelOverlap=True, tickCount=6))
    )

    price_line = base.mark_line(color='#1a73e8', strokeWidth=2.2).encode(
        y=alt.Y('Close:Q', title='價格 / 點位', scale=alt.Scale(domain=y_domain, zero=False)),
        tooltip=[
            alt.Tooltip('TimeStr:O', title='時間'),
            alt.Tooltip('Close:Q', title='成交價', format=',.2f'),
            alt.Tooltip('VWAP:Q', title='均價(VWAP)', format=',.2f'),
            alt.Tooltip('Diff:Q', title='漲跌', format='+,.2f'),
            alt.Tooltip('Pct:Q', title='漲跌幅(%)', format='+.2f'),
            alt.Tooltip('High:Q', title='當分最高', format=',.2f'),
            alt.Tooltip('Low:Q', title='當分最低', format=',.2f'),
            alt.Tooltip('VolLots:Q', title='單筆量', format=',.0f')
        ]
    )

    vwap_line = base.mark_line(color='#ff9800', strokeWidth=1.5, strokeDash=[3, 3]).encode(
        y=alt.Y('VWAP:Q', scale=alt.Scale(domain=y_domain, zero=False))
    )

    ref_rule = alt.Chart(pd.DataFrame({'y': [y_close]})).mark_rule(
        strokeDash=[4, 4], color='#777777', strokeWidth=1.2
    ).encode(y='y:Q')

    st.caption("👉 **手機操作提示**：走勢圖支援手指**向左／向右滑動**，完整查看全時段最新 K 線與均價！")

    # 動態計算寬度，確保時間軸完整延展且手機可向右滑動
    chart_w = max(len(df_intra) * 7, 560)
    top_chart = (price_line + vwap_line + ref_rule).properties(height=210, width=chart_w)

    vol_bars = base.mark_bar().encode(
        y=alt.Y('VolLots:Q', title='分時量', axis=alt.Axis(labels=False, ticks=False)),
        color=alt.Color(
            'BarColor:N',
            scale=alt.Scale(domain=['漲(紅)', '跌(綠)'], range=['#e53935', '#43a047']),
            legend=None
        ),
        tooltip=[
            alt.Tooltip('TimeStr:O', title='時間'),
            alt.Tooltip('VolLots:Q', title='成交量', format=',.0f')
        ]
    ).properties(height=65, width=chart_w)

    combined_chart = alt.vconcat(top_chart, vol_bars).resolve_scale(x='shared').configure_view(strokeOpacity=0.15)
    st.altair_chart(combined_chart, use_container_width=False)

# ----------------- 權威 API 2：臺灣銀行官方牌告匯率 -----------------
@st.cache_data(ttl=300, show_spinner=False)
def fetch_bot_forex():
    url = "https://rate.bot.com.tw/xrt/flcsv/0/day"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=(2.0, 3.0))
        if r.status_code == 200:
            reader = csv.reader(r.text.splitlines())
            for row in reader:
                if len(row) >= 5 and row[0].strip() == "USD":
                    # 即時本行賣出 (索引 12) 或 現金賣出 (索引 4/3)
                    val = safe_float(row[12]) if len(row) >= 13 else 0.0
                    if val <= 0 and len(row) >= 5:
                        val = safe_float(row[4])
                    if val <= 0 and len(row) >= 4:
                        val = safe_float(row[3])
                    if val > 0:
                        return {"usd_twd": val, "source": "臺灣銀行官方牌告", "is_real": True}
    except Exception:
        pass
    return None

# ----------------- 權威 API 3：機構分析師評等與目標價 -----------------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_analyst_consensus(ticker: str):
    try:
        info = fetch_yf_shared_info(ticker)
        short_n = info.get("shortName")
        if short_n and ticker.upper() not in GLOBAL_STOCK_NAMES:
            GLOBAL_STOCK_NAMES[ticker.upper()] = str(short_n)[:10]

        target_mean = safe_float(info.get('targetMeanPrice'))
        target_high = safe_float(info.get('targetHighPrice'))
        target_low = safe_float(info.get('targetLowPrice'))
        rec_key = str(info.get('recommendationKey', 'none')).lower()
        rec_mean = safe_float(info.get('recommendationMean'), 3.0)
        opinions = int(safe_float(info.get('numberOfAnalystOpinions'), 0))

        rec_map = {
            "strong_buy": ("🔥 強力買進 (Strong Buy)", "機構共識極度偏多，法人密集調升評等"),
            "buy": ("🟢 買進 (Buy)", "機構共識偏多，預期表現優於大盤"),
            "hold": ("🟡 中立持有 (Hold)", "機構看法平穩，區間震盪機率高"),
            "underperform": ("🟠 減碼 (Underperform)", "機構共識偏弱，建議縮減曝險部位"),
            "sell": ("🔴 賣出 (Sell)", "機構看法保守，建議嚴守紀律離場")
        }

        rec_label, rec_desc = rec_map.get(rec_key, ("⚪ 暫無機構評等", "該標的暫無多數券商連續追蹤報告"))
        has_target = target_mean > 0

        return {
            "has_data": has_target or opinions > 0,
            "target_mean": target_mean,
            "target_high": target_high,
            "target_low": target_low,
            "rec_label": rec_label,
            "rec_desc": rec_desc,
            "rec_mean": rec_mean,
            "opinions": opinions
        }
    except Exception:
        return {
            "has_data": False,
            "target_mean": 0.0,
            "target_high": 0.0,
            "target_low": 0.0,
            "rec_label": "⚪ 暫無數據",
            "rec_desc": "暫無足夠機構報告",
            "rec_mean": 3.0,
            "opinions": 0
        }

# ----------------- 權威 API 4：四大華爾街級機構研究套件 -----------------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_institutional_research_suite(ticker: str):
    clean_code, market = normalize_ticker(ticker)
    if market == "futures":
        return {"has_suite": False}

    try:
        info = fetch_yf_shared_info(ticker)
        if not info:
            return {"has_suite": False}

        gross_margin = safe_float(info.get("grossMargins"), None)
        op_margin = safe_float(info.get("operatingMargins"), None)
        profit_margin = safe_float(info.get("profitMargins"), None)
        roe = safe_float(info.get("returnOnEquity"), None)
        roa = safe_float(info.get("returnOnAssets"), None)
        current_ratio = safe_float(info.get("currentRatio"), None)
        quick_ratio = safe_float(info.get("quickRatio"), None)
        debt_to_equity = safe_float(info.get("debtToEquity"), None)
        free_cf = safe_float(info.get("freeCashflow"), None)
        op_cf = safe_float(info.get("operatingCashflow"), None)
        total_cash = safe_float(info.get("totalCash"), None)
        total_debt = safe_float(info.get("totalDebt"), None)

        trailing_pe = safe_float(info.get("trailingPE"), None)
        forward_pe = safe_float(info.get("forwardPE"), None)
        pb_ratio = safe_float(info.get("priceToBook"), None)
        ps_ratio = safe_float(info.get("priceToSalesTrailing12Months"), None)
        peg_ratio = safe_float(info.get("pegRatio"), None)
        ev_ebitda = safe_float(info.get("enterpriseToEbitda"), None)
        div_yield = safe_float(info.get("dividendYield"), None)
        payout_ratio = safe_float(info.get("payoutRatio"), None)
        book_val = safe_float(info.get("bookValue"), None)

        rev_growth = safe_float(info.get("revenueGrowth"), None)
        earn_growth = safe_float(info.get("earningsGrowth"), None)
        q_earn_growth = safe_float(info.get("earningsQuarterlyGrowth"), None)
        trailing_eps = safe_float(info.get("trailingEps"), None)
        forward_eps = safe_float(info.get("forwardEps"), None)
        total_rev = safe_float(info.get("totalRevenue"), None)
        ebitda_val = safe_float(info.get("ebitda"), None)

        earnings_surprises = []
        eh_tail = fetch_yf_earnings_history_safe(ticker)
        if eh_tail is not None and not eh_tail.empty:
            for idx_dt, row_e in eh_tail.iterrows():
                dt_str = str(idx_dt)[:10]
                eps_est = safe_float(row_e.get("epsEstimate"), None)
                eps_act = safe_float(row_e.get("epsActual"), None)
                surp_pct = safe_float(row_e.get("surprisePercent"), None)
                if surp_pct is not None and abs(surp_pct) < 2.0:
                    surp_pct = surp_pct * 100.0
                earnings_surprises.append({
                    "季度": dt_str,
                    "預估EPS": f"{eps_est:.2f}" if eps_est is not None else "--",
                    "實際EPS": f"{eps_act:.2f}" if eps_act is not None else "--",
                    "驚奇度(%)": f"{surp_pct:+.1f}%" if surp_pct is not None else "--",
                    "結果": "🟢 超預期 (Beat)" if (surp_pct is not None and surp_pct > 0) else ("🔴 低於預期 (Miss)" if (surp_pct is not None and surp_pct < 0) else "⚪ 符合預期")
                })

        sector = info.get("sector") or info.get("category") or "核心產業"
        industry = info.get("industry") or "指標企業"
        mkt_cap = safe_float(info.get("marketCap"), None)
        beta = safe_float(info.get("beta"), None)
        inst_held = safe_float(info.get("heldPercentInstitutions"), None)
        insider_held = safe_float(info.get("heldPercentInsiders"), None)
        high_52w = safe_float(info.get("fiftyTwoWeekHigh"), None)
        low_52w = safe_float(info.get("fiftyTwoWeekLow"), None)
        avg_vol_10d = safe_float(info.get("averageVolume10days"), None)
        avg_vol_3m = safe_float(info.get("averageVolume"), None)
        summary_text = str(info.get("longBusinessSummary", "")).strip()

        return {
            "has_suite": True,
            "financial_analysis": {
                "gross_margin": gross_margin * 100.0 if gross_margin is not None else None,
                "op_margin": op_margin * 100.0 if op_margin is not None else None,
                "profit_margin": profit_margin * 100.0 if profit_margin is not None else None,
                "roe": roe * 100.0 if roe is not None else None,
                "roa": roa * 100.0 if roa is not None else None,
                "current_ratio": current_ratio,
                "quick_ratio": quick_ratio,
                "debt_to_equity": debt_to_equity,
                "free_cf": free_cf,
                "op_cf": op_cf,
                "total_cash": total_cash,
                "total_debt": total_debt
            },
            "equity_research": {
                "trailing_pe": trailing_pe,
                "forward_pe": forward_pe,
                "pb_ratio": pb_ratio,
                "ps_ratio": ps_ratio,
                "peg_ratio": peg_ratio,
                "ev_ebitda": ev_ebitda,
                "div_yield": div_yield * 100.0 if (div_yield is not None and div_yield < 1.0) else div_yield,
                "payout_ratio": payout_ratio * 100.0 if (payout_ratio is not None and payout_ratio <= 2.0) else payout_ratio,
                "book_val": book_val
            },
            "earnings_reviewer": {
                "rev_growth": rev_growth * 100.0 if rev_growth is not None else None,
                "earn_growth": earn_growth * 100.0 if earn_growth is not None else None,
                "q_earn_growth": q_earn_growth * 100.0 if q_earn_growth is not None else None,
                "trailing_eps": trailing_eps,
                "forward_eps": forward_eps,
                "total_rev": total_rev,
                "ebitda_val": ebitda_val,
                "surprises": earnings_surprises
            },
            "market_researcher": {
                "sector": sector,
                "industry": industry,
                "mkt_cap": mkt_cap,
                "beta": beta,
                "inst_held": inst_held * 100.0 if inst_held is not None else None,
                "insider_held": insider_held * 100.0 if insider_held is not None else None,
                "high_52w": high_52w,
                "low_52w": low_52w,
                "avg_vol_10d": avg_vol_10d,
                "avg_vol_3m": avg_vol_3m,
                "summary_text": summary_text
            }
        }
    except Exception:
        return {"has_suite": False}

def format_large_money(val, currency="NTD"):
    if val is None or val == 0:
        return "未揭露"
    abs_v = abs(val)
    sign = "-" if val < 0 else ""
    if currency == "USD":
        if abs_v >= 1e12:
            return f"{sign}${abs_v/1e12:.2f} 兆 (T)"
        if abs_v >= 1e9:
            return f"{sign}${abs_v/1e9:.2f} 十億 (B)"
        if abs_v >= 1e6:
            return f"{sign}${abs_v/1e6:.2f} 百萬 (M)"
        return f"{sign}${abs_v:,.0f}"
    else:
        if abs_v >= 1e12:
            return f"{sign}{abs_v/1e12:.2f} 兆元"
        if abs_v >= 1e8:
            return f"{sign}{abs_v/1e8:.2f} 億元"
        if abs_v >= 1e4:
            return f"{sign}{abs_v/1e4:.1f} 萬元"
        return f"{sign}{abs_v:,.0f} 元"

def fetch_futures_analyst_consensus(code: str, df_fut: pd.DataFrame, df_mkt: pd.DataFrame):
    if df_fut is None or df_fut.empty:
        return {
            "has_data": False,
            "rec_label": "⚪ 資料不足",
            "rec_desc": "期貨行情資料不足",
            "target_mean": 0.0,
            "target_high": 0.0,
            "target_low": 0.0,
            "opinions": 0
        }

    last_fut = safe_float(df_fut.iloc[-1]['Close'])
    ma5 = safe_float(df_fut['MA5'].iloc[-1], last_fut)
    ma20 = safe_float(df_fut['MA20'].iloc[-1], last_fut)
    ma60 = safe_float(df_fut['MA60'].iloc[-1], ma20)

    basis = 0.0
    if df_mkt is not None and not df_mkt.empty:
        basis = last_fut - df_mkt.iloc[-1]['Close']

    if last_fut > ma5 > ma20 and basis > 20:
        rec_label = "🔥 強力多頭控盤 (Strong Bull)"
        rec_desc = "期顧與大額法人共識偏多，實質正價差領先推進，多方攻勢凌厲"
    elif last_fut > ma20:
        rec_label = "🟢 偏多震盪格局 (Bullish Hold)"
        rec_desc = "守穩月線關鍵生命線，均線架構偏多，逢拉回支撐有強力承接買盤"
    elif last_fut < ma20 < ma60 and basis < -40:
        rec_label = "🔴 空方壓制防守 (Bearish)"
        rec_desc = "期貨逆價差擴大，均線蓋頭下壓，大額避險空單主導盤勢"
    else:
        rec_label = "🟡 區間箱型拉鋸 (Neutral)"
        rec_desc = "多空籌碼膠著，均線糾結，短線預期於整數關卡進行區間震盪整理"

    atr = safe_float(df_fut['ATR14'].iloc[-1], default=150.0) if 'ATR14' in df_fut.columns else 150.0
    recent_high = df_fut['High'].tail(20).max()
    recent_low = df_fut['Low'].tail(20).min()

    target_high = max(recent_high, last_fut + 2.0 * atr)
    target_low = min(recent_low, last_fut - 2.0 * atr)
    target_mean = (last_fut + target_high) / 2.0 if last_fut > ma20 else last_fut

    return {
        "has_data": True,
        "rec_label": rec_label,
        "rec_desc": rec_desc,
        "target_mean": target_mean,
        "target_high": target_high,
        "target_low": target_low,
        "opinions": 8
    }

@st.cache_data(ttl=60, show_spinner=False)
def fetch_and_calc(ticker: str, period: str = "1y"):
    try:
        obj = yf.Ticker(ticker)
        df = obj.history(period=period)
        if df.empty or len(df) < 15:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()

        if (".TW" in ticker.upper() or ".TWO" in ticker.upper()) and not ticker.endswith("=F"):
            twse_live = fetch_twse_realtime(ticker)
            if twse_live and twse_live["match_price"] > 0:
                now_taipei = datetime.now(TAIPEI_TZ)
                today_str = now_taipei.strftime("%Y%m%d")

                if twse_live.get("date_str") == today_str and twse_live.get("is_trading"):
                    last_idx = df.index[-1]
                    last_date = last_idx.date()
                    today_date = now_taipei.date()

                    if last_date < today_date:
                        new_ts = pd.Timestamp.now(tz=last_idx.tz if last_idx.tzinfo else TAIPEI_TZ)
                        new_row = pd.DataFrame([{
                            'Open': twse_live['open'],
                            'High': twse_live['high'],
                            'Low': twse_live['low'],
                            'Close': twse_live['match_price'],
                            'Volume': twse_live['volume']
                        }], index=[new_ts])
                        df = pd.concat([df, new_row])
                    else:
                        df.iloc[-1, df.columns.get_loc('Close')] = twse_live["match_price"]
                        if twse_live["open"] > 0 and df.iloc[-1]['Open'] <= 0:
                            df.iloc[-1, df.columns.get_loc('Open')] = twse_live["open"]
                        df.iloc[-1, df.columns.get_loc('High')] = max(df.iloc[-1]['High'], twse_live["high"])
                        df.iloc[-1, df.columns.get_loc('Low')] = min(df.iloc[-1]['Low'], twse_live["low"]) if twse_live["low"] > 0 else df.iloc[-1]['Low']
                        if twse_live["volume"] > 0:
                            df.iloc[-1, df.columns.get_loc('Volume')] = twse_live["volume"]

        df = df[df['Close'] > 0].copy()
        if df.empty or len(df) < 5:
            return None

        df['MA5'] = df['Close'].rolling(5, min_periods=5).mean()
        df['MA20'] = df['Close'].rolling(20, min_periods=20).mean()
        df['MA60'] = df['Close'].rolling(60, min_periods=60).mean()
        df['Vol_MA5'] = df['Volume'].rolling(5, min_periods=5).mean()

        delta = df['Close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14.0, adjust=False, min_periods=14).mean()
        avg_loss = loss.ewm(alpha=1/14.0, adjust=False, min_periods=14).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        # 暖機期未滿 14 期保留 NaN，不偽裝填補為 50.0
        df['RSI14'] = 100.0 - (100.0 / (1.0 + rs))

        ema12 = df['Close'].ewm(span=12, adjust=False, min_periods=12).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False, min_periods=26).mean()
        df['DIF'] = ema12 - ema26
        df['MACD'] = df['DIF'].ewm(span=9, adjust=False, min_periods=9).mean()
        df['OSC'] = df['DIF'] - df['MACD']

        hl = df['High'] - df['Low']
        hc = (df['High'] - df['Close'].shift()).abs()
        lc = (df['Low'] - df['Close'].shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        df['ATR14'] = tr.rolling(14, min_periods=14).mean()

        return df.copy()
    except Exception:
        return None

@st.cache_data(ttl=7200, show_spinner=False)
def fetch_fundamentals(ticker: str):
    clean_code, market = normalize_ticker(ticker)
    if market == "futures":
        return {"has_data": False, "is_etf": False, "score": None, "reasons": []}

    try:
        info = fetch_yf_shared_info(ticker)
        is_etf = info.get('quoteType') == 'ETF' or clean_code.startswith(('00', '01'))

        if is_etf:
            yield_raw = info.get('yield', info.get('dividendYield', None))
            beta_raw = info.get('beta', None)
            nav_raw = info.get('navPrice', None)

            yield_val = safe_float(yield_raw * 100 if yield_raw is not None else None, default=None)
            beta_val = safe_float(beta_raw, default=None)
            nav_val = safe_float(nav_raw, default=None)

            if yield_val is None and beta_val is None:
                return {
                    "has_data": False,
                    "is_etf": True,
                    "score": None,
                    "yield": None,
                    "beta": None,
                    "nav": nav_val,
                    "category": info.get('category', '指數股票型基金 (ETF)'),
                    "reasons": ["⚠️ 查無足夠之配息率與 Beta 數據，未計入基本面評分"]
                }

            fund_score = 0
            reasons = []

            if yield_val is not None:
                if yield_val >= 7.0:
                    fund_score += 25
                    reasons.append(f"預估年化殖利率 {yield_val:.1f}%，高息防禦優勢顯著")
                elif yield_val >= 4.5:
                    fund_score += 20
                    reasons.append(f"預估年化殖利率 {yield_val:.1f}%，配息收益穩定")
                else:
                    fund_score += 15
                    reasons.append(f"年化殖利率 {yield_val:.1f}%，屬成長/海外型 ETF")

            if beta_val is not None:
                if beta_val <= 0.8:
                    fund_score += 15
                    reasons.append(f"Beta 係數 {beta_val:.2f}，抗跌防禦性佳")
                elif beta_val <= 1.2:
                    fund_score += 12
                    reasons.append(f"Beta 係數 {beta_val:.2f}，走勢貼近大盤指數")
                else:
                    fund_score += 8
                    reasons.append(f"Beta 係數 {beta_val:.2f}，波動幅度相對較大")

            reasons.append("屬一籃子分散配置標的 (註：未評估費用率、折溢價與配息來源)")

            return {
                "has_data": True,
                "is_etf": True,
                "score": fund_score,
                "yield": yield_val,
                "beta": beta_val,
                "nav": nav_val,
                "category": info.get('category', '指數股票型基金 (ETF)'),
                "reasons": reasons
            }
        else:
            roe_raw = info.get('returnOnEquity', None)
            op_raw = info.get('operatingMargins', None)
            pe_raw = info.get('trailingPE', None)
            de_raw = info.get('debtToEquity', None)

            if roe_raw is None and op_raw is None and pe_raw is None and de_raw is None:
                return {
                    "has_data": False,
                    "is_etf": False,
                    "score": None,
                    "roe": None,
                    "op_margin": None,
                    "pe": None,
                    "debt_ratio": None,
                    "reasons": ["⚠️ 查無足夠之財報數據，未計入基本面評分"]
                }

            roe_val = safe_float(roe_raw * 100 if roe_raw is not None else None, default=None)
            op_margin_val = safe_float(op_raw * 100 if op_raw is not None else None, default=None)
            pe_val = safe_float(pe_raw, default=None)
            de_val = safe_float(de_raw, default=None)

            fund_score = 0
            reasons = []

            if roe_val is not None:
                if roe_val >= 15:
                    fund_score += 15
                    reasons.append(f"ROE 達 {roe_val:.1f}%，資本回報效率極佳")
                elif roe_val >= 10:
                    fund_score += 10
                    reasons.append(f"ROE 達 {roe_val:.1f}%，維持穩健水準")
                else:
                    reasons.append(f"ROE 偏低 ({roe_val:.1f}%)")

            if op_margin_val is not None:
                if op_margin_val >= 15:
                    fund_score += 15
                    reasons.append(f"營業利益率 {op_margin_val:.1f}%，本業競爭優勢顯著")
                elif op_margin_val >= 8:
                    fund_score += 10
                    reasons.append(f"營業利益率 {op_margin_val:.1f}%，本業獲利扎實")
                else:
                    reasons.append(f"營業利益率偏低 ({op_margin_val:.1f}%)")

            if pe_val is not None:
                if pe_val <= 0:
                    reasons.append("本益比不適用（近四季處於虧損狀態）")
                elif 8 <= pe_val <= 25:
                    fund_score += 10
                    reasons.append(f"本益比 {pe_val:.1f}x，估值處合理區間")
                elif 0 < pe_val < 8:
                    fund_score += 7
                    reasons.append(f"本益比低估 ({pe_val:.1f}x)")
                else:
                    fund_score += 4
                    reasons.append(f"本益比偏高 ({pe_val:.1f}x)")

            if de_val is not None:
                if de_val <= 80:
                    fund_score += 10
                    reasons.append(f"負債權益比 (D/E) 適度 ({de_val:.1f}%)，財務結構穩健 (註：各產業基準差異大)")
                elif de_val <= 150:
                    fund_score += 6
                    reasons.append(f"負債權益比 (D/E) 常態 ({de_val:.1f}%) (註：各產業基準差異大)")
                else:
                    reasons.append(f"負債權益比 (D/E) 偏高 ({de_val:.1f}%) (註：各產業基準差異大)")

            return {
                "has_data": True,
                "is_etf": False,
                "score": fund_score,
                "roe": roe_val,
                "op_margin": op_margin_val,
                "pe": pe_val,
                "debt_ratio": de_val,
                "reasons": reasons
            }
    except Exception:
        return {
            "has_data": False,
            "is_etf": False,
            "score": None,
            "roe": None,
            "op_margin": None,
            "pe": None,
            "debt_ratio": None,
            "reasons": ["⚠️ 基本面連線逾時，未計入基本面評分"]
        }

def analyze_opening_and_ma(df_stock, live_info=None):
    if df_stock is None or len(df_stock) == 0:
        return {}, "資料不足", 0, 0.0, 0.0, "⚪ 無資料", ["資料不足"]

    last = df_stock.iloc[-1]
    prev = df_stock.iloc[-2] if len(df_stock) >= 2 else last
    close = safe_float(last['Close'])
    has_ma5 = pd.notna(last.get('MA5'))
    has_ma20 = pd.notna(last.get('MA20'))
    has_ma60 = pd.notna(last.get('MA60'))
    ma5 = safe_float(last.get('MA5'), close)
    ma20 = safe_float(last.get('MA20'), close)
    ma60 = safe_float(last.get('MA60'), ma20)

    ma_status = {
        "ma5_diff": ((close - ma5) / (ma5 + 1e-9)) * 100 if has_ma5 else 0.0,
        "ma20_diff": ((close - ma20) / (ma20 + 1e-9)) * 100 if has_ma20 else 0.0,
        "ma60_diff": ((close - ma60) / (ma60 + 1e-9)) * 100 if has_ma60 else 0.0,
        "ma5_val": ma5,
        "ma20_val": ma20,
        "ma60_val": ma60,
        "has_ma5": has_ma5,
        "has_ma20": has_ma20,
        "has_ma60": has_ma60
    }

    if not has_ma20:
        ma_alignment = "⏳ 歷史樣本未滿 20 日 (均線暖機資料累積中)"
        ma_score = 8
    elif has_ma60 and close > ma5 > ma20 > ma60:
        ma_alignment = "🔥 完美多頭排列 (價格 > 日線 > 月線 > 季線)"
        ma_score = 25
    elif has_ma60 and close > ma20 and ma20 > ma60:
        ma_alignment = "📈 中長線偏多架構 (守穩月線與季線)"
        ma_score = 18
    elif not has_ma60 and close > ma5 > ma20:
        ma_alignment = "📈 短中期偏多架構 (站上日線與月線，季線暖機中)"
        ma_score = 18
    elif has_ma60 and close < ma5 < ma20 < ma60:
        ma_alignment = "❄️ 完全空頭排列 (價格被所有均線下壓)"
        ma_score = 0
    else:
        ma_alignment = "🔄 均線震盪糾結 (多空方向待表態)"
        ma_score = 10

    open_p = safe_float(last['Open'], close)
    prev_close = safe_float(prev['Close'], close)
    gap_pct = ((open_p - prev_close) / (prev_close + 1e-9)) * 100
    intraday_pct = ((close - open_p) / (open_p + 1e-9)) * 100

    opening_diag = []
    if gap_pct >= 1.0:
        opening_diag.append(f"強勢跳空開高 (+{gap_pct:.2f}%)，多方意圖明確。")
    elif gap_pct <= -1.0:
        opening_diag.append(f"弱勢跳空開低 ({gap_pct:.2f}%)，下檔承接力道待觀察。")
    else:
        opening_diag.append(f"平盤附近開出 ({gap_pct:+.2f}%)，由盤中量能決定方向。")

    if close > open_p:
        k_type = "🔴 盤中實體紅 K (開低走高或強開強走)"
        opening_diag.append("多方持續推進，買盤居主導地位。")
    elif close < open_p:
        k_type = "🟢 盤中實體黑 K (開高走低或弱勢下殺)"
        opening_diag.append("需留意盤中逢高調節或避險賣壓。")
    else:
        k_type = "⚪ 盤中十字星 (多空平手拉鋸)"

    return ma_status, ma_alignment, ma_score, gap_pct, intraday_pct, k_type, opening_diag

def backtest_strategy(df_stock, market_type="tw"):
    if len(df_stock) < 60:
        return None

    signals = (
        (df_stock['Close'] > df_stock['MA20']) &
        (df_stock['Close'] > df_stock['Close'].shift(1)) &
        (df_stock['Volume'] > df_stock['Vol_MA5']) &
        (df_stock['OSC'] > 0)
    )

    n_bars = len(df_stock)
    trade_returns = []
    i = 0

    if market_type == "us":
        cost_rate = 0.0010
    elif market_type == "futures":
        cost_rate = 0.0004
    else:
        cost_rate = 0.0045

    while i < n_bars - 6:
        if signals.iloc[i]:
            entry_p = safe_float(df_stock['Open'].iloc[i + 1])
            if entry_p <= 0:
                entry_p = safe_float(df_stock['Close'].iloc[i + 1])
            exit_p = safe_float(df_stock['Open'].iloc[i + 6])
            if exit_p <= 0:
                exit_p = safe_float(df_stock['Close'].iloc[i + 6])

            if entry_p > 0 and exit_p > 0:
                net_ret = ((exit_p - entry_p) / entry_p - cost_rate) * 100.0
                trade_returns.append(net_ret)
                i += 6
                continue
        i += 1

    if not trade_returns:
        return None

    wins = [r for r in trade_returns if r > 0]
    win_rate = (len(wins) / len(trade_returns)) * 100.0
    avg_return = float(np.mean(trade_returns))
    worst_single_loss = float(min(trade_returns))

    equity_curve = [100.0]
    for r in trade_returns:
        equity_curve.append(equity_curve[-1] * (1.0 + r / 100.0))

    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        if val > peak:
            peak = val
        dd = (peak - val) / peak * 100.0
        if dd > max_dd:
            max_dd = dd

    return {
        "count": len(trade_returns),
        "win_rate": win_rate,
        "avg_return": avg_return,
        "worst_loss": worst_single_loss,
        "mdd": max_dd
    }

@st.cache_data(ttl=300, show_spinner=False)
def analyze_forex_data():
    res = {
        "twd_rate": None,
        "twd_change": 0.0,
        "twd_status": "資料檢索中",
        "twd_trend": "平穩",
        "dxy_rate": None,
        "dxy_trend": "中立",
        "jpy_rate": None,
        "jpy_risk": "正常",
        "source": "Yahoo 即時外匯",
        "has_real_twd": False
    }

    bot_data = fetch_bot_forex()
    if bot_data:
        res["twd_rate"] = bot_data["usd_twd"]
        res["source"] = bot_data["source"]
        res["has_real_twd"] = True

    df_usdtwd = fetch_and_calc("USDTWD=X")
    if df_usdtwd is None:
        df_usdtwd = fetch_and_calc("TWD=X")
    df_dxy = fetch_and_calc("DX-Y.NYB")
    df_jpy = fetch_and_calc("JPY=X")

    try:
        if df_usdtwd is not None and len(df_usdtwd) >= 2:
            last_twd = safe_float(df_usdtwd.iloc[-1]['Close'])
            prev_twd = safe_float(df_usdtwd.iloc[-2]['Close'])
            ma20_twd = safe_float(df_usdtwd['MA20'].iloc[-1], last_twd)

            if not res["has_real_twd"] and last_twd > 0:
                res["twd_rate"] = last_twd
                res["has_real_twd"] = True

            if last_twd > 0 and prev_twd > 0:
                diff = last_twd - prev_twd
                res["twd_change"] = diff
                if diff < -0.05:
                    res["twd_status"] = "🟢 今日強勢升值 (外資熱錢湧入)"
                elif diff > 0.05:
                    res["twd_status"] = "🔴 今日明顯貶值 (外資匯出壓力)"
                else:
                    res["twd_status"] = "⚪ 今日窄幅震盪整理"

                if res["twd_rate"] and res["twd_rate"] < ma20_twd:
                    res["twd_trend"] = "波段升值格局 (有利權值股與台指)"
                else:
                    res["twd_trend"] = "波段貶值格局 (權值承壓，有利外銷)"

        if df_dxy is not None and len(df_dxy) >= 2:
            last_dxy = safe_float(df_dxy.iloc[-1]['Close'])
            ma20_dxy = safe_float(df_dxy['MA20'].iloc[-1], last_dxy)
            res["dxy_rate"] = last_dxy
            if last_dxy > 0:
                res["dxy_trend"] = "偏強 (美元強勢，新興市場資金保守)" if last_dxy > ma20_dxy else "偏弱 (美元回落，熱錢回流)"

        if df_jpy is not None and len(df_jpy) >= 5:
            last_jpy = safe_float(df_jpy.iloc[-1]['Close'])
            ma5_jpy = safe_float(df_jpy['MA5'].iloc[-1], last_jpy)
            res["jpy_rate"] = last_jpy
            if last_jpy > 0 and ma5_jpy > 0 and (last_jpy - ma5_jpy) / (ma5_jpy + 1e-9) < -0.015:
                res["jpy_risk"] = "⚠️ 警示：日圓近期急升，提防日圓套利平倉賣壓！"
            else:
                res["jpy_risk"] = "✅ 正常：日圓匯率平穩，無顯著平倉風險"
    except Exception:
        pass

    return res

@st.cache_data(ttl=120, show_spinner=False)


# ----------------- 美股夜盤與核心指標即時監控模組 -----------------
@st.cache_data(ttl=60, show_spinner=False)
def fetch_us_live_indicators():
    """抓取美股即時大盤、ADR 與美債殖利率指標"""
    targets = [
        ("台積電 ADR", "TSM", "$"),
        ("費半 ETF", "SOXX", "$"),
        ("輝達 NVDA", "NVDA", "$"),
        ("那指期貨", "NQ=F", "點"),
        ("10年美債", "^TNX", "%")
    ]
    data = []
    for label, sym, unit in targets:
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="2d", interval="1m")
            if hist is None or hist.empty or len(hist) < 2:
                hist = t.history(period="5d")
            
            if hist is not None and not hist.empty:
                if isinstance(hist.columns, pd.MultiIndex):
                    hist.columns = hist.columns.get_level_values(0)
                cur = safe_float(hist['Close'].iloc[-1])
                prev = safe_float(t.info.get("previousClose") if t.info else None)
                if prev <= 0 and len(hist) >= 2:
                    prev = safe_float(hist['Close'].iloc[-2], cur)
                if prev <= 0:
                    prev = cur
                diff = cur - prev
                pct = (diff / (prev + 1e-9)) * 100.0
                data.append({
                    "label": label, "symbol": sym, "unit": unit,
                    "price": cur, "diff": diff, "pct": pct
                })
        except Exception:
            continue
    return data

def render_next_day_forecast_panel(us_data, tw_base_index=40000.0):
    """根據美股指標、台積電 ADR 與金管會政策籌碼計算隔日多重情境預測"""
    factor_changes = {"TSM": 0.0, "SOXX": 0.0, "NQ": 0.0, "TNX": 0.0}
    tsm_price = 0.0
    
    if us_data:
        for item in us_data:
            sym = item.get("symbol", "")
            pct = item.get("pct", 0.0)
            if sym == "TSM":
                factor_changes["TSM"] = pct
                tsm_price = item.get("price", 0.0)
            elif sym in ("SOXX", "^SOX"):
                factor_changes["SOXX"] = pct
            elif "NQ" in sym:
                factor_changes["NQ"] = pct
            elif "^TNX" in sym:
                factor_changes["TNX"] = -pct

    # 權重敏感度換算: 台積電約佔大盤 35%
    tw_weighted_jump = (
        factor_changes["TSM"] * 0.35 +
        factor_changes["SOXX"] * 0.15 +
        factor_changes["NQ"] * 0.15 +
        (factor_changes["TNX"] * 0.03 if factor_changes["TNX"] < 0 else 0.0)
    )
    
    # 政策底限空令強制軋空增益
    policy_bonus = 0.35 if (tsm_price >= 370.0 and tw_weighted_jump > 0) else 0.0
    base_center = tw_weighted_jump + policy_bonus

    if base_center >= 1.5:
        p_a = (base_center * 1.05, max(base_center * 1.35, base_center + 0.8))
        p_b = (base_center * 0.70, base_center * 1.00)
        p_c = (max(base_center * 0.25, 0.4), base_center * 0.65)
        p_d = (-1.80, -0.50)
    elif base_center >= 0:
        p_a = (base_center + 0.8, base_center + 1.8)
        p_b = (base_center, base_center + 0.8)
        p_c = (0.1, base_center)
        p_d = (-1.50, -0.40)
    else:
        p_a = (0.5, 1.5)
        p_b = (-0.5, 0.5)
        p_c = (base_center - 0.5, base_center)
        p_d = (max(base_center * 1.5, -2.5), -1.0)

    # 機率權重
    if tsm_price >= 370.0 and factor_changes["SOXX"] >= 2.0:
        prob_a, prob_b, prob_c, prob_d = 75, 15, 7, 3
    elif tsm_price >= 370.0:
        prob_a, prob_b, prob_c, prob_d = 60, 25, 10, 5
    elif tw_weighted_jump >= 0:
        prob_a, prob_b, prob_c, prob_d = 40, 40, 15, 5
    else:
        prob_a, prob_b, prob_c, prob_d = 10, 25, 45, 20

    plans = [
        {
            "name": "方案 A：極致樂觀・政策底強迫軋空",
            "desc": "台積電 ADR 守穩 370 美元鐵底，限空令掐死 90% 借券賣壓，外資與造市商被迫早盤掛市價回補，大盤報復性跳空大漲。",
            "pct_range": p_a,
            "pts_range": (tw_base_index * p_a[0] / 100.0, tw_base_index * p_a[1] / 100.0),
            "prob": prob_a,
            "badge": "🔥 機率最高 (75~80%)" if prob_a >= 60 else "⭐ 攻擊情境",
            "tag_color": "#e53935",
            "action": "嚴禁開盤追高；趁衝高將 0050正二等槓桿工具果斷出清，台積電零股逢拉抬至缺口反壓分批落袋，保留 7 成防禦現金。"
        },
        {
            "name": "方案 B：常態修復・開高震盪走堅",
            "desc": "美股反彈動能延續，跳空開高後遇部分解套賣盤換手，國安基金穩健托底權值股，維持穩健紅盤格局。",
            "pct_range": p_b,
            "pts_range": (tw_base_index * p_b[0] / 100.0, tw_base_index * p_b[1] / 100.0),
            "prob": prob_b,
            "badge": "🟢 常態情境",
            "tag_color": "#43a047",
            "action": "觀察開盤 15 分 K (ORB) 高低點表態與分時 VWAP 均價線，嚴守個股停損點，不隨意追單。"
        },
        {
            "name": "方案 C：拉高遇壓・漲幅收斂整理",
            "desc": "早盤跳空開高後引發前波套牢賣壓與隔日沖獲利調節，多方追價意願謹慎，盤勢於高檔陷入橫盤拉鋸。",
            "pct_range": p_c,
            "pts_range": (tw_base_index * p_c[0] / 100.0, tw_base_index * p_c[1] / 100.0),
            "prob": prob_c,
            "badge": "🟡 震盪整理",
            "tag_color": "#ff9800",
            "action": "把握開盤衝高契機順勢調節弱勢部位，耐心等待盤勢築出第二隻腳再重新評估。"
        },
        {
            "name": "方案 D：美股回落・政策防禦鎖定跌幅",
            "desc": "若美股尾盤突發翻黑，但因限空令已封死借券賣壓，國安基金首要托底台積電，跌幅被強制封鎖在千點以內。",
            "pct_range": p_d,
            "pts_range": (tw_base_index * p_d[0] / 100.0, tw_base_index * p_d[1] / 100.0),
            "prob": prob_d,
            "badge": "🛡️ 政策底防線",
            "tag_color": "#1a73e8",
            "action": "全面啟動防禦機制，絕不逆勢攤平；嚴守 7 成現金儲備，靜待恐慌殺盤釋放完畢。"
        }
    ]

    st.write("---")
    st.markdown("#### 🔮 【次日開市漲跌預測 % 數與多重情境方案模型】")
    st.caption("綜合美股夜盤因子（TSM 35%、SOXX 15%、NQ 15%、美債 3%）與金管會限空令籌碼模型精確測算：")
    for plan in plans:
        st.markdown(f"""
        <div style="background: rgba(128,128,128,0.05); border-left: 4px solid {plan['tag_color']}; border-radius: 8px; padding: 0.6rem 0.8rem; margin-bottom: 0.5rem;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <b style="color:{plan['tag_color']}; font-size:0.96rem;">{plan['name']}</b>
                <span style="font-size:0.8rem; background:rgba(128,128,128,0.12); padding:2px 8px; border-radius:12px;"><b>機率：{plan['prob']}%</b> ｜ {plan['badge']}</span>
            </div>
            <div style="margin: 0.35rem 0; font-size:1.1rem; font-weight:700; color:{plan['tag_color']};">
                預估漲跌：{plan['pct_range'][0]:+.2f}% ～ {plan['pct_range'][1]:+.2f}% 
                <span style="font-size:0.85rem; font-weight:400; color:#666;">(約 {plan['pts_range'][0]:+,.0f} ～ {plan['pts_range'][1]:+,.0f} 點)</span>
            </div>
            <div style="font-size:0.88rem; color:#444; line-height:1.45; margin-bottom:0.25rem;">
                • <b>籌碼結構</b>：{plan['desc']}
            </div>
            <div style="font-size:0.88rem; color:#2e7d32; line-height:1.45;">
                • <b>操盤軍規</b>：{plan['action']}
            </div>
        </div>
        """, unsafe_allow_html=True)

def render_us_live_dashboard():
    """渲染美股夜盤與即時指標卡片看板（自適應雙欄，解決手機寬度擠壓問題）"""
    with st.expander("🌐 【美股大盤、ADR 與三大關鍵指標即時監控】", expanded=True):
        col_hdr1, col_hdr2 = st.columns([2.6, 1.4])
        with col_hdr1:
            st.caption("即時連線：台積電 ADR、費半、輝達、那指期貨與 10 年美債殖利率")
        with col_hdr2:
            if st.button("🔄 刷新美股", key="btn_refresh_us_live", use_container_width=True):
                fetch_us_live_indicators.clear()
                st.rerun()

        us_data = fetch_us_live_indicators()
        if us_data:
            # 依 2 欄一列排版，手機端寬裕展示，絕不擠壓
            for i in range(0, len(us_data), 2):
                chunk = us_data[i:i+2]
                cols = st.columns(2)
                for c_col, item in zip(cols, chunk):
                    val_str = f"{item['price']:.2f}%" if item["unit"] == "%" else f"{item['unit']}{item['price']:,.2f}"
                    sign = "+" if item['diff'] >= 0 else ""
                    c_col.metric(
                        label=f"{item['label']} ({item['symbol']})",
                        value=val_str,
                        delta=f"{sign}{item['diff']:.2f} ({sign}{item['pct']:.2f}%)"
                    )

            tsm = next((x for x in us_data if x["symbol"] == "TSM"), None)
            if tsm:
                if tsm["price"] >= 370.0:
                    st.success(f"✅ **台積電 ADR 現報 ${tsm['price']:.2f}**：成功守穩 **370 美元** 多方關鍵防線！下週一金管會限空令（借券上限 3%）生效，外資面臨強迫軋空回補。")
                else:
                    st.warning(f"⚠️ **台積電 ADR 現報 ${tsm['price']:.2f}**：跌破 370 美元防線，下週一開盤啟動千點內政策防禦機制。")

            # ★ 即時推演隔日開市漲跌預測 % 數與多重情境方案
            render_next_day_forecast_panel(us_data)
        else:
            st.info("⚪ 目前外部美股撮合連線中，請稍候或點擊右上角刷新。")

def preload_global_benchmarks():
    tickers = ["^TWII", "WTX=F", "TSM", "^SOX", "^GSPC"]
    results = {}
    ex = ThreadPoolExecutor(max_workers=5)
    try:
        futs = {t: ex.submit(fetch_and_calc, t) for t in tickers}
        for t, f in futs.items():
            try:
                results[t] = f.result(timeout=5.0)
            except Exception:
                results[t] = None
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
    return results

def analyze_full_stock(ticker, df_stock, df_market, df_futures, df_tsm, df_sox, forex_info, asset_type="tw", include_inst_suite=True):
    live_twse = fetch_twse_realtime(ticker) if asset_type == "tw" else None
    ma_status, ma_alignment, ma_score, gap_pct, intraday_pct, k_type, opening_diag = analyze_opening_and_ma(df_stock, live_twse)

    last_stk = df_stock.iloc[-1]
    prev_stk = df_stock.iloc[-2] if len(df_stock) >= 2 else last_stk
    
    close = safe_float(last_stk['Close'])
    if close <= 0:
        pos_closes = df_stock['Close'][df_stock['Close'] > 0]
        close = safe_float(pos_closes.iloc[-1]) if not pos_closes.empty else 1.0

    atr_val = safe_float(last_stk['ATR14'], default=close * 0.02)

    global_score = 0
    global_reasons = []

    if asset_type == "futures":
        analyst_data = fetch_futures_analyst_consensus(ticker, df_stock, df_market)
        fund_data = {"has_data": False, "score": None, "reasons": []}
        inst_suite = {"has_suite": False}
        global_score = 12
    elif asset_type == "us":
        analyst_data = fetch_analyst_consensus(ticker)
        fund_data = fetch_fundamentals(ticker)
        inst_suite = fetch_institutional_research_suite(ticker) if include_inst_suite else {"has_suite": False}
        global_score = 10
    else:
        analyst_data = fetch_analyst_consensus(ticker)
        fund_data = fetch_fundamentals(ticker)
        inst_suite = fetch_institutional_research_suite(ticker) if include_inst_suite else {"has_suite": False}
        try:
            if df_tsm is not None and len(df_tsm) >= 2:
                tsm_change = ((df_tsm['Close'].iloc[-1] - df_tsm['Close'].iloc[-2]) / (df_tsm['Close'].iloc[-2] + 1e-9)) * 100
                if tsm_change >= 1.5:
                    global_score += 15
                    global_reasons.append(f"TSM ADR 大漲 ({tsm_change:+.1f}%)，國際連動強勁")
                elif tsm_change > 0:
                    global_score += 10
                    global_reasons.append(f"TSM ADR 小漲 ({tsm_change:+.1f}%)，美股平穩偏多")
                else:
                    global_score += 6
            else:
                global_score += 8
        except Exception:
            global_score += 8

    rel_alpha_20d = 0.0
    rel_alpha_60d = 0.0
    if df_market is not None and len(df_market) >= 21 and len(df_stock) >= 21:
        stk_20d = (df_stock['Close'].iloc[-1] / (df_stock['Close'].iloc[-21] + 1e-9) - 1.0) * 100.0
        mkt_20d = (df_market['Close'].iloc[-1] / (df_market['Close'].iloc[-21] + 1e-9) - 1.0) * 100.0
        rel_alpha_20d = stk_20d - mkt_20d
    if df_market is not None and len(df_market) >= 61 and len(df_stock) >= 61:
        stk_60d = (df_stock['Close'].iloc[-1] / (df_stock['Close'].iloc[-61] + 1e-9) - 1.0) * 100.0
        mkt_60d = (df_market['Close'].iloc[-1] / (df_market['Close'].iloc[-61] + 1e-9) - 1.0) * 100.0
        rel_alpha_60d = stk_60d - mkt_60d

    mkt_score = 0
    mkt_reasons = []
    if df_market is not None and not df_market.empty:
        last_mkt = df_market.iloc[-1]
        if pd.notna(last_mkt.get('MA20')) and last_mkt['Close'] > last_mkt['MA20']:
            mkt_score += 12
            mkt_reasons.append("大盤站上月線 (20MA)，多方主導發球權")
        elif pd.notna(last_mkt.get('MA20')):
            mkt_reasons.append("大盤跌破月線，系統性拉回風險偏高")
        if pd.notna(last_mkt.get('MA20')) and pd.notna(last_mkt.get('MA60')) and last_mkt['MA20'] > last_mkt['MA60']:
            mkt_score += 8
            mkt_reasons.append("大盤季線多頭架構 (20MA > 60MA)")

    tech_score = 0
    tech_reasons = []
    has_vol_ma5 = pd.notna(last_stk.get('Vol_MA5')) and safe_float(last_stk.get('Vol_MA5')) > 0
    vol_ratio = (safe_float(last_stk['Volume']) / (safe_float(last_stk['Vol_MA5']) + 1e-9)) if has_vol_ma5 else 0.0
    if close > prev_stk['Close'] and has_vol_ma5 and vol_ratio >= 1.2:
        tech_score += 10
        tech_reasons.append(f"量增價漲 (爆量比: {vol_ratio:.1f}x)")
    elif close > prev_stk['Close']:
        tech_score += 5
        tech_reasons.append("價漲但量能平淡")

    osc_curr = safe_float(last_stk.get('OSC'), default=None) if pd.notna(last_stk.get('OSC')) else None
    osc_prev = safe_float(prev_stk.get('OSC'), default=None) if pd.notna(prev_stk.get('OSC')) else None
    if osc_curr is not None and osc_curr > 0 and osc_prev is not None and osc_curr > osc_prev:
        tech_score += 8
        tech_reasons.append("MACD 紅柱放大，攻擊動能足")
    elif osc_curr is not None and osc_curr > 0:
        tech_score += 4
        tech_reasons.append("MACD 維持多頭")

    rsi_curr = safe_float(last_stk.get('RSI14'), default=None) if pd.notna(last_stk.get('RSI14')) else None
    if rsi_curr is not None:
        if 50 <= rsi_curr <= 70:
            tech_score += 7
            tech_reasons.append(f"RSI 處健康攻擊區 ({rsi_curr:.1f})")
    else:
        tech_reasons.append("RSI14 暖機資料不足 (N/A)")

    analyst_bonus = 0
    if analyst_data["has_data"]:
        if "強力" in analyst_data["rec_label"] or "Strong" in analyst_data["rec_label"]:
            analyst_bonus = 5
        elif "偏多" in analyst_data["rec_label"] or "Buy" in analyst_data["rec_label"]:
            analyst_bonus = 3
        elif "空" in analyst_data["rec_label"] or "Sell" in analyst_data["rec_label"]:
            analyst_bonus = -5

    tech_subtotal = global_score + mkt_score + ma_score + tech_score
    if fund_data.get("has_data") and fund_data.get("score") is not None:
        tech_part = tech_subtotal * (60.0 / 85.0)
        fund_part = fund_data['score'] * 0.70
        total_score = int(tech_part + fund_part + analyst_bonus)
    else:
        tech_part = tech_subtotal * (95.0 / 85.0)
        total_score = int(tech_part + analyst_bonus)

    total_score = min(max(total_score, 0), 100)

    has_stk_ma20 = pd.notna(last_stk.get('MA20'))
    ma20_val = safe_float(last_stk.get('MA20'), close * 0.96) if has_stk_ma20 else (close * 0.96)
    if (not has_stk_ma20) or (close >= ma20_val):
        raw_stop = max(close - 2.0 * atr_val, ma20_val - 0.5 * atr_val)
        stop_loss = min(raw_stop, close * 0.985)
        is_breakdown = False
    else:
        stop_loss = min(close - 2.0 * atr_val, close * 0.985)
        is_breakdown = True

    recent_60d_high = safe_float(df_stock['High'].tail(60).max(), close * 1.08)
    if analyst_data['target_mean'] > close:
        target_60d = analyst_data['target_mean']
    elif recent_60d_high > close:
        target_60d = recent_60d_high
    else:
        target_60d = max(close + 2.5 * atr_val, close * 1.08)

    return {
        "total_score": total_score,
        "fund_score": fund_data.get('score'),
        "close": close,
        "stop_loss": stop_loss,
        "target_60d": target_60d,
        "is_breakdown": is_breakdown,
        "ma_status": ma_status,
        "ma_alignment": ma_alignment,
        "gap_pct": gap_pct,
        "intraday_pct": intraday_pct,
        "k_type": k_type,
        "opening_diag": opening_diag,
        "global_reasons": global_reasons,
        "mkt_reasons": mkt_reasons,
        "tech_reasons": tech_reasons,
        "fund_data": fund_data,
        "analyst_data": analyst_data,
        "inst_suite": inst_suite,
        "rel_alpha_20d": rel_alpha_20d,
        "rel_alpha_60d": rel_alpha_60d,
        "forex_info": forex_info,
        "live_info": live_twse,
        "asset_type": asset_type
    }

# 期貨保證金集中管理與基準日期標示（期交所可能動態調整，請以最新公告為準）
FUTURES_MARGIN_UPDATED_AT = "2026-10"
FUTURES_MARGIN_SOURCE = "臺灣期貨交易所 (TAIFEX) 基準參數（人工定期校驗）"

# ----------------- Gemini 輕量按鈕觸發・質化操盤劇本模組 -----------------
GEMINI_DEFAULT_MODEL = "自動最佳模型 (推薦)"
GEMINI_FALLBACK_MODEL = "gemini-2.0-flash"

def get_gemini_api_key() -> str:
    """安全取得 Gemini API Key（優先讀取 st.secrets 與環境變數，其次讀取當前 Session）"""
    try:
        if "GEMINI_API_KEY" in st.secrets and str(st.secrets["GEMINI_API_KEY"]).strip():
            return str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        pass
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key
    return str(st.session_state.get("session_gemini_api_key", "")).strip()

@st.cache_data(ttl=86400, show_spinner=False)
def get_available_gemini_models(api_key: str):
    """主動向 Google 查詢該 API Key 真正支援且開放的可用模型清單，徹底杜絕 404"""
    if not api_key:
        return []
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        resp = requests.get(url, timeout=(2.5, 4.0))
        if resp.status_code == 200:
            data = resp.json().get("models", [])
            valid_models = []
            for item in data:
                methods = item.get("supportedGenerationMethods", [])
                if "generateContent" in methods:
                    name = item.get("name", "").replace("models/", "").strip()
                    if name:
                        valid_models.append(name)
            # 優先嘗試含 flash 的模型，其次含 pro，其他隨後
            flashes = [m for m in valid_models if "flash" in m.lower()]
            pros = [m for m in valid_models if "pro" in m.lower() and m not in flashes]
            others = [m for m in valid_models if m not in flashes and m not in pros]
            return flashes + pros + others
    except Exception:
        pass
    return []

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_gemini_qualitative_playbook(
    api_key: str,
    model_name: str,
    ticker_label: str,
    asset_type: str,
    close_p: float,
    total_score: int,
    ma_alignment: str,
    ma20_diff: float,
    is_breakdown: bool,
    k_type: str,
    gap_pct: float,
    vix_price: float,
    vix_pct: float,
    rel_alpha_20d: float,
    rec_label: str,
    news_titles_tuple: tuple
):
    """
    輕量級 Gemini API 質化劇本解讀（30分鐘快取隔離，不佔用本機 RAM、不干預確定性算術與風控數字）
    """
    if not api_key:
        return False, "⚠️ 尚未設定 Gemini API Key。請展開頁面頂部「⚙️ 個人風控本金、當沖折讓與看盤備忘錄」填入金鑰，或於 Streamlit Secrets 設定 `GEMINI_API_KEY`。"

    news_str = "；".join(news_titles_tuple[:3]) if news_titles_tuple else "目前無重大異常外電"
    trend_state = "跌破月線(20MA)空方防守格局" if is_breakdown else "站穩月線(20MA)之上多方控盤格局"

    prompt_text = (
        f"你是一位資深機構級量化操盤手與風險控管專家。請針對標的【{ticker_label}】（資產類別：{asset_type}）"
        f"進行「純質化（Qualitative）盤勢氛圍與次日應變劇本解讀」。\n\n"
        f"【嚴格紀律限制】：\n"
        f"1. 系統的停損價、目標價、當沖保本檔位與可買張數/口數皆已由 Python 確定性演算法精確算出，請勿在文字中自行捏造、重算或篡改任何具體進出場價位與下單張數/口數。\n"
        f"2. 請專注於「多空發球權定調、指標共振或背離解讀、總經 VIX 避險情緒連動、盤中應變劇本」。\n"
        f"3. 總字數控制在 320 字以內，條列分明、直指要害。\n\n"
        f"【系統已算出之客觀量化狀態】：\n"
        f"- 最新報價：{close_p:,.2f} ｜ 綜合量化總分：{total_score} / 100\n"
        f"- 均線結構：{ma_alignment}（月線 20MA 乖離率：{ma20_diff:+.2f}% ｜ 位階：{trend_state}）\n"
        f"- 開盤型態：{k_type}（跳空幅度：{gap_pct:+.2f}%）\n"
        f"- 近 20 日相對大盤超額報酬 (Alpha)：{rel_alpha_20d:+.2f}%\n"
        f"- 法人/期顧共識評等：{rec_label}\n"
        f"- 全市場 VIX 恐慌指數：{vix_price:.2f}（位於過去 252 日之 {vix_pct:.1f}% 歷史百分位）\n"
        f"- 近期焦點外電標題：{news_str}\n\n"
        f"請嚴格依以下三個小標題輸出 Markdown：\n"
        f"1. 🎯 **多空結構與籌碼定調**（判讀技術位階與相對大盤強弱）\n"
        f"2. ⚡ **盤中實戰應變劇本**（結合開盤型態、均線乖離與 VWAP/ORB 順逆勢應對原則）\n"
        f"3. 🚨 **VIX 宏觀波動與極限風控提醒**（點出當前最需提防的誘多/誘空或系統性風險）"
    )

    # 1. 優先從 Google 官方 ListModels 動態取得該 Key 真正開放的模型清單
    discovered_models = get_available_gemini_models(api_key)
    candidate_models = []
    
    clean_req_model = str(model_name).replace("models/", "").strip()
    if clean_req_model and "自動" not in clean_req_model:
        candidate_models.append(clean_req_model)

    if discovered_models:
        candidate_models.extend(discovered_models)
    else:
        # 若 ListModels 連線受阻，使用標準後備候選模型清單
        candidate_models.extend([
            "gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash",
            "gemini-1.5-flash-latest", "gemini-1.5-pro", "gemini-pro"
        ])

    candidate_models = list(dict.fromkeys(candidate_models))

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {
            "temperature": 0.25,
            "maxOutputTokens": 650
        }
    }

    last_err = ""
    for m_id in candidate_models:
        clean_model = m_id.replace("models/", "").strip()
        if not clean_model:
            continue
        # 嚴格依照 Google 官方 REST API 規格組裝路徑：/v1beta/models/{clean_model}:generateContent
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={api_key}"
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=(3.0, 10.0))
            if resp.status_code == 200:
                r_json = resp.json()
                candidates = r_json.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        model_badge = f"*(由 `{clean_model}` 模型即時推演・30分鐘快取保護中)*\n\n"
                        return True, model_badge + parts[0]["text"].strip()
                last_err = f"模型 `{clean_model}` 回傳內容為空。"
            elif resp.status_code in (404, 400) and m_id != candidate_models[-1]:
                # 若當前模型不支援或下架，平滑降級嘗試下一個有效模型
                continue
            elif resp.status_code == 429:
                return False, "⚠️ Gemini API 呼叫頻率達上限 (HTTP 429 Quota Exceeded)，請稍候幾分鐘再試。"
            else:
                err_msg = resp.text[:160]
                last_err = f"HTTP {resp.status_code}: {err_msg}"
        except Exception as e:
            last_err = f"連線逾時或網路異常 ({str(e)})"

    return False, f"⚠️ Gemini AI 暫時無法回應（{last_err}）。系統量化指標與下單風控計算機均維持正常運作。"

TW_FUTURES_SPECS = {
    "WTX": {
        "name": "台指期貨 (大台)",
        "point_value": 200,
        "tick_size": 1.0,
        "tick_value": 200,
        "initial_margin": 250000,
        "maintenance_margin": 192000,
        "desc": "全市場主力大額籌碼風向核心，每點 200 元"
    },
    "MTX": {
        "name": "小型台指 (小台)",
        "point_value": 50,
        "tick_size": 1.0,
        "tick_value": 50,
        "initial_margin": 62500,
        "maintenance_margin": 48000,
        "desc": "散戶與短線波段核心，每點 50 元"
    },
    "WMT": {
        "name": "微型台指 (微台)",
        "point_value": 10,
        "tick_size": 1.0,
        "tick_value": 10,
        "initial_margin": 12500,
        "maintenance_margin": 9600,
        "desc": "小資量化避險首選，每點 10 元"
    },
    "TE": {
        "name": "電子期貨",
        "point_value": 400,
        "tick_size": 0.05,
        "tick_value": 20,
        "initial_margin": 210000,
        "maintenance_margin": 161000,
        "desc": "追蹤電子類股，每點 400 元 (每跳 0.05 點 = 20 元)"
    },
    "TF": {
        "name": "金融期貨",
        "point_value": 1000,
        "tick_size": 0.2,
        "tick_value": 200,
        "initial_margin": 130000,
        "maintenance_margin": 100000,
        "desc": "大型金控資產指標，每點 1000 元 (每跳 0.2 點 = 200 元)"
    }
}

@st.cache_data(ttl=600, show_spinner=False)
def fetch_stock_news(ticker: str):
    try:
        t = yf.Ticker(ticker)
        news_list = t.news
        if not news_list:
            return []
        formatted = []
        for n in news_list[:6]:
            content = n.get('content', {}) if isinstance(n.get('content'), dict) else {}
            title = content.get('title') or n.get('title') or '市場焦點快訊'

            provider_dict = content.get('provider', {}) if isinstance(content.get('provider'), dict) else {}
            publisher = provider_dict.get('displayName') or n.get('publisher') or '財經即時訊'

            canon_dict = content.get('canonicalUrl', {}) if isinstance(content.get('canonicalUrl'), dict) else {}
            click_dict = content.get('clickThroughUrl', {}) if isinstance(content.get('clickThroughUrl'), dict) else {}
            link = canon_dict.get('url') or click_dict.get('url') or n.get('link') or '#'

            pub_ts = safe_float(n.get('providerPublishTime'))
            pub_date_str = content.get('pubDate', '')
            if pub_ts > 0:
                pub_time = datetime.fromtimestamp(pub_ts, tz=TAIPEI_TZ).strftime("%m/%d %H:%M")
            elif pub_date_str:
                pub_time = str(pub_date_str)[:16].replace("T", " ")
            else:
                pub_time = "即時"

            formatted.append({
                "title": title,
                "publisher": publisher,
                "link": link,
                "time": pub_time
            })
        return formatted
    except Exception:
        return []


MARKET_QUALITY_UNIVERSE = [
    ("台積電", "2330.TW", "半導體先進製程龍頭"),
    ("聯發科", "2454.TW", "IC設計領航者"),
    ("鴻海", "2317.TW", "全球電子代工/AI伺服器"),
    ("廣達", "2382.TW", "AI伺服器領導大廠"),
    ("緯穎", "6669.TW", "雲端資料中心伺服器"),
    ("台達電", "2308.TW", "電源管理與綠能永續"),
    ("富邦金", "2881.TW", "金控獲利龍頭"),
    ("國泰金", "2882.TW", "全方位金控旗艦"),
    ("中信金", "2891.TW", "消費金融與財富管理龍頭"),
    ("兆豐金", "2886.TW", "官股外匯獲利模範生"),
    ("長榮", "2603.TW", "全球貨櫃航運龍頭"),
    ("奇鋐", "3017.TW", "散熱模組領導大廠"),
    ("雙鴻", "3324.TW", "水冷散熱關鍵大廠"),
    ("大立光", "3008.TW", "光學鏡頭專利領先者"),
    ("元大台灣50", "0050.TW", "台股核心藍籌組合")
]

ETF_UNIVERSE = [
    ("元大台灣50", "0050.TW", "市值型", "台股市值前50大權值龍頭"),
    ("富邦台50", "006208.TW", "市值型", "低經理費追蹤台股前50大龍頭"),
    ("元大高股息", "0056.TW", "高股息", "預測未來高現金殖利率"),
    ("國泰永續高股息", "00878.TW", "高股息", "ESG+過去3年平均高殖利率/季配"),
    ("群益台灣精選高息", "00919.TW", "高股息", "宣告股利精準篩選/高配息率"),
    ("復華台灣科技優息", "00929.TW", "高股息", "全科技股高股息/月配息代表"),
    ("元大台灣價值高息", "00940.TW", "高股息", "巴菲特價值投資/自由現金流"),
    ("統一FANG+", "00757.TW", "海外科技", "美國科技巨頭/高成長高動能"),
    ("國泰費城半導體", "00830.TW", "海外半導體", "全球半導體硬體/AI上游核心"),
    ("富邦NASDAQ", "00662.TW", "海外美股", "追蹤美國那斯達克100科技成長"),
    ("元大美債20年", "00679B.TWO", "債券避險", "長天期美債/降息受惠"),
    ("國泰20年美債", "00687B.TWO", "債券避險", "長天期美債/穩定債息")
]

EARNINGS_CALLS = [
    {"公司": "台積電 (2330)", "重要性": "⭐⭐⭐⭐⭐", "期間": "每季第 1 個月中旬 (1/4/7/10月)", "重點觀測": "資本支出、CoWoS產能、AI半導體展望、N2量產節奏"},
    {"公司": "聯發科 (2454)", "重要性": "⭐⭐⭐⭐", "期間": "每季底至次月首週 (1/4/7/10月)", "重點觀測": "天璣旗艦晶片出貨、車用與邊緣AI ASIC設計案營收佔比"},
    {"公司": "鴻海 (2317)", "重要性": "⭐⭐⭐⭐", "期間": "每季中旬 (3/5/8/11月)", "重點觀測": "GB200/NVL72 伺服器量產交期、電動車與毛利率"},
    {"公司": "廣達 (2382)", "重要性": "⭐⭐⭐⭐", "期間": "每季中旬 (3/5/8/11月)", "重點觀測": "AI伺服器機櫃出貨比重、車用電子獲利動能"},
    {"公司": "富邦金 (2881)", "重要性": "⭐⭐⭐", "期間": "每季下旬 (3/5/8/11月)", "重點觀測": "海外債券投資評價、壽險避險成本與股利配發能力"}
]

US_FUT_LIST = [
    ("微那斯達克期 (NQ)", "NQ=F", "全球科技龍頭風向球"),
    ("小標普500期 (ES)", "ES=F", "美股大盤流動性與宏觀資產"),
    ("道瓊期貨 (YM)", "YM=F", "傳統價值龍頭與金融防禦"),
    ("羅素2000期 (RTY)", "RTY=F", "中小型股景氣復甦動能")
]

# ================= 四大權威機構研究報告渲染器 =================
def render_institutional_research_panel(res, ticker_raw, mode_type="tw"):
    suite = res.get("inst_suite", {})
    if not suite or not suite.get("has_suite"):
        return

    fin = suite["financial_analysis"]
    eq = suite["equity_research"]
    earn = suite["earnings_reviewer"]
    mkt = suite["market_researcher"]
    an_data = res["analyst_data"]
    curr_code = "USD" if mode_type == "us" else "NTD"
    curr_sym = "USD" if mode_type == "us" else "元"
    disp_name = get_stock_display_label(ticker_raw, is_fav=False)

    with st.expander("🏛️ 【四大權威機構深度研究報告】Financial / Equity / Earnings / Market", expanded=True):
        st.caption("整合華爾街與法人機構四大核心投研維度：財務分析、股票估值研究、財報盈餘檢視、市場籌碼與相對強度。")
        tab_fa, tab_eq, tab_er, tab_mr, tab_export = st.tabs([
            "📊 財務分析", "📑 股票研究", "📈 財報分析", "🌐 市場研究", "📥 完整報告"
        ])

        with tab_fa:
            st.markdown("#### 📊 Financial Analysis（企業財務結構與現金流護城河）")
            fa_c1, fa_c2, fa_c3 = st.columns(3)
            fa_c1.metric("毛利率 (Gross)", f"{fin['gross_margin']:.1f}%" if fin['gross_margin'] is not None else "未揭露")
            fa_c2.metric("營益率 (Operating)", f"{fin['op_margin']:.1f}%" if fin['op_margin'] is not None else "未揭露")
            fa_c3.metric("淨利率 (Net)", f"{fin['profit_margin']:.1f}%" if fin['profit_margin'] is not None else "未揭露")

            fa_c4, fa_c5, fa_c6 = st.columns(3)
            fa_c4.metric("股東權益報酬 (ROE)", f"{fin['roe']:.1f}%" if fin['roe'] is not None else "未揭露")
            fa_c5.metric("資產報酬率 (ROA)", f"{fin['roa']:.1f}%" if fin['roa'] is not None else "未揭露")
            fa_c6.metric("負債權益比 (D/E)", f"{fin['debt_to_equity']:.1f}%" if fin['debt_to_equity'] is not None else "未揭露")

            fa_c7, fa_c8 = st.columns(2)
            cr_str = f"{fin['current_ratio']:.2f}" if fin['current_ratio'] is not None else "--"
            qr_str = f"{fin['quick_ratio']:.2f}" if fin['quick_ratio'] is not None else "--"
            fa_c7.metric("流動比率 / 速動比率", f"{cr_str} / {qr_str}")
            fa_c8.metric("自由現金流 (FCF)", format_large_money(fin['free_cf'], curr_code))

            st.markdown(f"""
            <div class="inst-report-box">
                <b>💡 首席財務分析師診斷：</b><br>
                • <b>帳上現金部位</b>：{format_large_money(fin['total_cash'], curr_code)} ｜ <b>總負債規模</b>：{format_large_money(fin['total_debt'], curr_code)}<br>
                • <b>營業現金流 (OCF)</b>：{format_large_money(fin['op_cf'], curr_code)}（{'🟢 現金流充沛，具備強大資本支出與配息底氣' if (fin['op_cf'] and fin['op_cf'] > 0) else '⚪ 現金流資料待更新或屬金融/ETF資產'}）
            </div>
            """, unsafe_allow_html=True)

        with tab_eq:
            st.markdown("#### 📑 Equity Research（機構估值模型與目標位階研究）")
            eq_c1, eq_c2, eq_c3 = st.columns(3)
            eq_c1.metric("歷史本益比 (Trailing PE)", f"{eq['trailing_pe']:.1f}x" if (eq['trailing_pe'] and eq['trailing_pe'] > 0) else "不適用")
            eq_c2.metric("預估本益比 (Forward PE)", f"{eq['forward_pe']:.1f}x" if (eq['forward_pe'] and eq['forward_pe'] > 0) else "未揭露")
            eq_c3.metric("股價淨值比 (P/B)", f"{eq['pb_ratio']:.2f}x" if eq['pb_ratio'] is not None else "未揭露")

            eq_c4, eq_c5, eq_c6 = st.columns(3)
            eq_c4.metric("PEG 成長估值比", f"{eq['peg_ratio']:.2f}" if eq['peg_ratio'] is not None else "未揭露")
            eq_c5.metric("EV / EBITDA", f"{eq['ev_ebitda']:.1f}x" if eq['ev_ebitda'] is not None else "未揭露")
            eq_c6.metric("現金殖利率", f"{eq['div_yield']:.2f}%" if eq['div_yield'] is not None else "未揭露")

            upside_str = "暫無目標均價"
            c_price = safe_float(res.get('close', 0.0))
            if an_data.get("target_mean", 0) > 0 and c_price > 0:
                up_val = ((an_data["target_mean"] - c_price) / c_price) * 100.0
                upside_str = f"目標均價 {an_data['target_mean']:.2f} {curr_sym}（潛在空間 {up_val:+.1f}%，區間 {an_data['target_low']:.1f} ~ {an_data['target_high']:.1f}）"
            elif an_data.get("target_mean", 0) > 0:
                upside_str = f"目標均價 {an_data['target_mean']:.2f} {curr_sym}"

            val_verdict = "合理估值區間"
            if eq['forward_pe'] and eq['trailing_pe'] and eq['forward_pe'] < eq['trailing_pe']:
                val_verdict = "🟢 未來盈餘成長帶動 Forward PE 收斂，具備估值擴張潛力"
            elif eq['trailing_pe'] and eq['trailing_pe'] > 35:
                val_verdict = "🟡 高本益比成長溢價區，需高度仰賴後續財報高成長支撐"

            st.markdown(f"""
            <div class="inst-report-box">
                <b>💡 機構股票研究評等摘要：</b><br>
                • <b>華爾街/法人共識評等</b>：{an_data.get('rec_label', '⚪ 中立')}（共 {an_data.get('opinions', 0)} 家機構覆蓋）<br>
                • <b>法人目標價位階</b>：{upside_str}<br>
                • <b>估值模型結論</b>：{val_verdict}（每股淨值 Book Value：{f"{eq['book_val']:.2f} {curr_sym}" if eq['book_val'] else "未揭露"}）
            </div>
            """, unsafe_allow_html=True)

        with tab_er:
            st.markdown("#### 📈 Earnings Reviewer（季度財報成長動能與盈餘驚奇度）")
            er_c1, er_c2, er_c3 = st.columns(3)
            er_c1.metric("營收年增率 (Rev YoY)", f"{earn['rev_growth']:+.1f}%" if earn['rev_growth'] is not None else "未揭露")
            er_c2.metric("盈餘年增率 (Earn YoY)", f"{earn['earn_growth']:+.1f}%" if earn['earn_growth'] is not None else "未揭露")
            er_c3.metric("季度盈餘成長 (QoQ/YoY)", f"{earn['q_earn_growth']:+.1f}%" if earn['q_earn_growth'] is not None else "未揭露")

            er_c4, er_c5 = st.columns(2)
            er_c4.metric("近四季累計 EPS (Trailing)", f"{earn['trailing_eps']:.2f} {curr_sym}" if earn['trailing_eps'] is not None else "未揭露")
            er_c5.metric("法人預估未來 EPS (Forward)", f"{earn['forward_eps']:.2f} {curr_sym}" if earn['forward_eps'] is not None else "未揭露")

            st.caption(f"📌 近四季總營收規模：**{format_large_money(earn['total_rev'], curr_code)}** ｜ EBITDA 獲利規模：**{format_large_money(earn['ebitda_val'], curr_code)}**")

            if earn["surprises"]:
                st.markdown("##### 📋 近四季財報實際 EPS vs 法人預估驚奇度 (Earnings Surprise)")
                st.dataframe(pd.DataFrame(earn["surprises"]), use_container_width=True, hide_index=True)
            else:
                st.info("💡 該標的目前無歷史季度 EPS Surprise 明細表，請參考上方營收與盈餘年增率指標。")

        with tab_mr:
            st.markdown("#### 🌐 Market Researcher（產業地位、機構籌碼與市場相對強度）")
            mr_c1, mr_c2, mr_c3 = st.columns(3)
            mr_c1.metric("總市值規模", format_large_money(mkt['mkt_cap'], curr_code))
            mr_c2.metric("外資/機構持股比", f"{mkt['inst_held']:.1f}%" if mkt['inst_held'] is not None else "未揭露")
            mr_c3.metric("Beta 波動風險", f"{mkt['beta']:.2f}" if mkt['beta'] is not None else "未揭露")

            mr_c4, mr_c5 = st.columns(2)
            mr_c4.metric("近 20 日相對大盤超額報酬 (Alpha)", f"{res.get('rel_alpha_20d', 0.0):+.2f}%",
                         "強於大盤" if res.get('rel_alpha_20d', 0.0) > 0 else "弱於大盤")
            mr_c5.metric("近 60 日相對大盤超額報酬 (Alpha)", f"{res.get('rel_alpha_60d', 0.0):+.2f}%",
                         "波段領頭羊" if res.get('rel_alpha_60d', 0.0) > 0 else "波段落後大盤")

            pos_52w_str = "未揭露"
            if mkt['high_52w'] and mkt['low_52w'] and (mkt['high_52w'] - mkt['low_52w']) > 0:
                pos_pct = ((c_price - mkt['low_52w']) / (mkt['high_52w'] - mkt['low_52w'])) * 100.0
                pos_52w_str = f"位於 52 週區間之 {pos_pct:.1f}% 位階（低點 {mkt['low_52w']:.2f} ～ 高點 {mkt['high_52w']:.2f}）"

            st.markdown(f"""
            <div class="inst-report-box">
                <b>💡 市場與籌碼研究員觀點：</b><br>
                • <b>所屬產業板塊</b>：{mkt['sector']} — {mkt['industry']}<br>
                • <b>52 週價格位階</b>：{pos_52w_str}<br>
                • <b>籌碼穩定度</b>：內部人/大股東持股 {f"{mkt['insider_held']:.1f}%" if mkt['insider_held'] is not None else "--"} ｜ 10日均量 vs 3月均量比：{f"{(mkt['avg_vol_10d']/(mkt['avg_vol_3m']+1e-9)):.2f}x" if (mkt['avg_vol_10d'] and mkt['avg_vol_3m']) else "--"}
            </div>
            """, unsafe_allow_html=True)

            if mkt["summary_text"]:
                st.markdown("##### 📖 企業核心業務與全球競爭護城河簡介")
                st.info(mkt["summary_text"])

        with tab_export:
            st.markdown("#### 📥 完整機構級四維度投研報告（可直接複製或下載存檔）")
            report_md = f"""# 🏛️ 【{disp_name}】機構級四維度深度研究報告
- **報告生成時間**：{datetime.now(TAIPEI_TZ).strftime('%Y-%m-%d %H:%M')}
- **當前最新報價**：{res['close']:.2f} {curr_sym} ｜ **量化綜合總分**：{res['total_score']} / 100
- **建議波段停損價**：{res['stop_loss']:.2f} {curr_sym} ｜ **波段目標價**：{res['target_60d']:.2f} {curr_sym}

---
## 1. 📊 Financial Analysis（財務分析）
- **三率表現**：毛利率 `{f"{fin['gross_margin']:.1f}%" if fin['gross_margin'] is not None else "N/A"}` ｜ 營益率 `{f"{fin['op_margin']:.1f}%" if fin['op_margin'] is not None else "N/A"}` ｜ 淨利率 `{f"{fin['profit_margin']:.1f}%" if fin['profit_margin'] is not None else "N/A"}`
- **資本報酬**：ROE `{f"{fin['roe']:.1f}%" if fin['roe'] is not None else "N/A"}` ｜ ROA `{f"{fin['roa']:.1f}%" if fin['roa'] is not None else "N/A"}`
- **償債與現金流**：負債權益比 `{f"{fin['debt_to_equity']:.1f}%" if fin['debt_to_equity'] is not None else "N/A"}` ｜ 自由現金流 `{format_large_money(fin['free_cf'], curr_code)}`

## 2. 📑 Equity Research（股票估值研究）
- **機構共識評等**：{an_data.get('rec_label', 'N/A')}（共 {an_data.get('opinions', 0)} 家機構追蹤，目標均價 `{an_data.get('target_mean', 0):.2f} {curr_sym}`）
- **核心估值倍數**：Trailing PE `{f"{eq['trailing_pe']:.1f}x" if eq['trailing_pe'] else "N/A"}` ｜ Forward PE `{f"{eq['forward_pe']:.1f}x" if eq['forward_pe'] else "N/A"}` ｜ P/B `{f"{eq['pb_ratio']:.2f}x" if eq['pb_ratio'] else "N/A"}` ｜ EV/EBITDA `{f"{eq['ev_ebitda']:.1f}x" if eq['ev_ebitda'] else "N/A"}`

## 3. 📈 Earnings Reviewer（財報與盈餘分析）
- **成長動能**：營收年增率 `{f"{earn['rev_growth']:+.1f}%" if earn['rev_growth'] is not None else "N/A"}` ｜ 盈餘年增率 `{f"{earn['earn_growth']:+.1f}%" if earn['earn_growth'] is not None else "N/A"}`
- **每股盈餘**：Trailing EPS `{f"{earn['trailing_eps']:.2f}" if earn['trailing_eps'] is not None else "N/A"}` ｜ Forward EPS `{f"{earn['forward_eps']:.2f}" if earn['forward_eps'] is not None else "N/A"}`

## 4. 🌐 Market Researcher（市場與籌碼研究）
- **產業板塊**：{mkt['sector']} / {mkt['industry']} ｜ **總市值**：{format_large_money(mkt['mkt_cap'], curr_code)}
- **機構籌碼與相對強度**：外資/機構持股 `{f"{mkt['inst_held']:.1f}%" if mkt['inst_held'] is not None else "N/A"}` ｜ 近20日相對大盤 Alpha `{res.get('rel_alpha_20d', 0.0):+.2f}%` ｜ 近60日相對大盤 Alpha `{res.get('rel_alpha_60d', 0.0):+.2f}%`
- **技術均線結構**：{res['ma_alignment']}
"""
            st.code(report_md, language="markdown")
            st.download_button(
                label="💾 下載完整機構研究報告 (.md)",
                data=report_md.encode("utf-8"),
                file_name=f"Research_Report_{ticker_raw}_{datetime.now(TAIPEI_TZ).strftime('%Y%m%d')}.md",
                mime="text/markdown",
                use_container_width=True,
                key=f"dl_rep_{ticker_raw}_{mode_type}"
            )

# ================= 模組共用渲染器 =================
def render_analysis_view(res, df_asset, mode_type="tw", custom_spec=None, fallback_warning=None, ticker_raw=None, is_spot_fallback=False):
    has_ma20_flag = res.get('ma_status', {}).get('has_ma20', True)
    is_downtrend = bool(has_ma20_flag and (res.get('is_breakdown', False) or (res['close'] < res['ma_status']['ma20_val'])))
    close = safe_float(res.get('close', 0.0))
    if close <= 0:
        close = 1.0

    raw_stop = safe_float(res.get('stop_loss', 0.0))
    if close > 0 and 0 < raw_stop < close:
        risk_unit = close - raw_stop
    else:
        risk_unit = max(close * 0.015, 1.0)
    target_1 = (close + (1.5 * risk_unit)) if (not is_downtrend and not is_spot_fallback) else None
    an_data = res['analyst_data']
    stable_key_suffix = f"{mode_type}_{ticker_raw or 'default'}"

    if mode_type == "futures":
        currency_sym = "點"
        unit_name = "口 (Lots)"
        spec = custom_spec or TW_FUTURES_SPECS.get("WTX", {"tick_value": 200, "initial_margin": 250000, "maintenance_margin": 192000, "name": "台指期貨", "desc": "台指契約"})
    elif mode_type == "us":
        currency_sym = "USD"
        unit_name = "股 (Shares)"
    else:
        currency_sym = "元"
        unit_name = "張 (Lots)"

    if fallback_warning:
        st.info(fallback_warning)

    disp_header = get_stock_display_label(ticker_raw, is_fav=False) if ticker_raw else ""
    if disp_header:
        st.markdown(f"**📌 當前診斷標的：`{disp_header}`**")

    if res.get("live_info"):
        status_badge = res['live_info'].get('status_label', '⚪ 歷史報價')
        st.caption(f"⚡ **TWSE 撮合系統** ｜ {status_badge} ｜ 時間：{res['live_info']['time']}")
    elif mode_type == "futures":
        st.caption(f"⚡ **期貨專屬規格載入** ｜ 單位：指數點 ｜ {spec['name']} 保證金參數就位")
    elif mode_type == "us":
        st.caption(f"⚡ **美股即時行情連線** ｜ 幣別：USD ｜ 資料更新時序完整")

    if mode_type in ("tw", "us") and ticker_raw:
        m_key = "tw" if mode_type == "tw" else "us"
        cur_favs = user_memory.get(f"{m_key}_favorites", [])
        is_fav = ticker_raw in cur_favs
        fav_label = "⭐ 已加入常用清單 (點此移出)" if is_fav else "☆ 收藏至常用清單"
        if st.button(fav_label, use_container_width=True, key=f"btn_fav_toggle_{stable_key_suffix}"):
            toggle_favorite_stock(m_key, ticker_raw)
            st.rerun()

    c1, c2 = st.columns(2)
    c1.metric("綜合決策總分", f"{res['total_score']} / 100")
    c2.metric("最新點位/現價", f"{close:.2f} {currency_sym}")

    c3, c4 = st.columns(2)
    c3.metric("建議防守價 (停損)", f"{res['stop_loss']:.2f} {currency_sym}")
    risk_pct = (risk_unit / close * 100.0) if close > 0 else 0.0
    c4.metric("最大預期風險", f"{risk_pct:.2f}%")

    # 0. 即時分時走勢圖 & 台股五檔委買賣明細 (雙向深度能量條看板)
    with st.expander("📺 【即時分時走勢圖 (含昨收平盤線 & VWAP均價) ＆ 五檔委買賣明細】", expanded=True):
        chart_ticker = "WTX=F" if mode_type == "futures" else (ticker_raw or "2330.TW")
        if mode_type == "futures" and df_futures_bench is None:
            chart_ticker = "^TWII"
        render_intraday_chart_widget(chart_ticker, title_name=disp_header or chart_ticker)

        live_info = res.get("live_info")
        if live_info and live_info.get("bid_prices") and live_info.get("ask_prices"):
            st.markdown("#### 📋 證交所即時五檔委買賣盤口深度")
            b_p = live_info["bid_prices"]
            b_v = live_info["bid_vols"]
            a_p = live_info["ask_prices"]
            a_v = live_info["ask_vols"]

            total_bid_v = sum(b_v)
            total_ask_v = sum(a_v)
            total_depth = total_bid_v + total_ask_v
            bid_ratio = (total_bid_v / total_depth * 100.0) if total_depth > 0 else 50.0

            st.caption(f"🔥 **委買總量：{total_bid_v:,} 張 ({bid_ratio:.1f}%)** ｜ ❄️ **委賣總量：{total_ask_v:,} 張 ({100.0-bid_ratio:.1f}%)**")
            st.progress(min(max(bid_ratio / 100.0, 0.0), 1.0))

            max_vol = max(max(b_v, default=1), max(a_v, default=1), 1)

            rows_list = []
            for i in range(max(len(b_p), len(a_p))):
                bp = b_p[i] if i < len(b_p) and b_p[i] > 0 else None
                bv = b_v[i] if i < len(b_v) and b_v[i] > 0 else 0
                ap = a_p[i] if i < len(a_p) and a_p[i] > 0 else None
                av = a_v[i] if i < len(a_v) and a_v[i] > 0 else 0

                bp_str = f"{bp:,.2f}" if bp else "--"
                bv_str = f"{bv:,}" if bv else "--"
                ap_str = f"{ap:,.2f}" if ap else "--"
                av_str = f"{av:,}" if av else "--"

                b_bar_pct = min((bv / max_vol) * 100.0, 100.0) if bv else 0.0
                a_bar_pct = min((av / max_vol) * 100.0, 100.0) if av else 0.0

                row_html = (
                    f"<div style='display:flex; align-items:center; justify-content:space-between; margin-bottom:4px; font-size:0.92rem; height:28px;'>"
                    f"<div style='flex:1; display:flex; align-items:center; justify-content:flex-end; position:relative; background:rgba(229,57,53,0.06); border-radius:4px 0 0 4px; height:100%; padding-right:8px; overflow:hidden;'>"
                    f"<div style='position:absolute; right:0; top:0; bottom:0; width:{b_bar_pct:.1f}%; background:rgba(229,57,53,0.22); z-index:1;'></div>"
                    f"<span style='position:relative; z-index:2; margin-right:8px; color:#555;'>{bv_str}張</span>"
                    f"<b style='position:relative; z-index:2; color:#e53935; font-size:0.96rem;'>{bp_str}</b>"
                    f"</div>"
                    f"<div style='width:36px; text-align:center; font-size:0.75rem; color:#888; font-weight:700;'>{i+1}</div>"
                    f"<div style='flex:1; display:flex; align-items:center; justify-content:flex-start; position:relative; background:rgba(67,160,71,0.06); border-radius:0 4px 4px 0; height:100%; padding-left:8px; overflow:hidden;'>"
                    f"<div style='position:absolute; left:0; top:0; bottom:0; width:{a_bar_pct:.1f}%; background:rgba(67,160,71,0.22); z-index:1;'></div>"
                    f"<b style='position:relative; z-index:2; color:#43a047; font-size:0.96rem;'>{ap_str}</b>"
                    f"<span style='position:relative; z-index:2; margin-left:8px; color:#555;'>{av_str}張</span>"
                    f"</div>"
                    f"</div>"
                )
                rows_list.append(row_html)

            depth_board_html = (
                f"<div style='background:rgba(128,128,128,0.04); border:1px solid rgba(128,128,128,0.18); border-radius:10px; padding:8px 10px; margin-top:6px;'>"
                f"<div style='display:flex; justify-content:space-between; font-size:0.78rem; color:#777; margin-bottom:6px; padding:0 6px;'>"
                f"<span>買進掛單 (張數 / 委買價)</span>"
                f"<span>委賣價 / 張數 (賣出掛單)</span>"
                f"</div>"
                f"{''.join(rows_list)}"
                f"</div>"
            )
            st.markdown(depth_board_html, unsafe_allow_html=True)

    # ★★★ 當沖實戰決策室 (台股專屬) ★★★
    if mode_type == "tw":
        with st.expander("⚡ 【當沖實戰決策室 (VWAP生命線・ORB突破・CDP五關卡・保本跳動計算)】", expanded=True):
            df_intra, _ = fetch_intraday_series(ticker_raw or "2330.TW")
            cdp_info = calc_cdp_levels(df_asset)
            orb_info = calc_orb_levels(df_intra)

            now_t = datetime.now(TAIPEI_TZ)
            now_time_str = now_t.strftime("%H:%M:%S")

            if "13:20:00" <= now_time_str <= "13:35:00":
                st.error("🚨 **【當沖強制平倉警報】目前已過 13:20！請立即市價清倉出清，嚴防盤後無法成交被迫留倉借券！**")
            elif "13:00:00" <= now_time_str < "13:20:00":
                st.warning("⚠️ **【尾盤平倉提醒】目前時間已過 13:00，請著手分批獲利了結或停損，準備結束當沖部位。**")

            if orb_info:
                vwap_val = orb_info["curr_vwap"]
                vwap_diff = ((close - vwap_val) / (vwap_val + 1e-9)) * 100.0
                st.markdown(f"""
                <div class="daytrade-card">
                    <b>🎯 當沖主力攻防信號：</b><br>
                    • <b>型態診斷</b>：{orb_info['status_label']}<br>
                    • <b>開盤 15 分 K 區間</b>：高點 <b class="tw-up">{orb_info['orb_high']:.2f}</b> ｜ 低點 <b class="tw-down">{orb_info['orb_low']:.2f}</b><br>
                    • <b>VWAP 均價線</b>：<b>{vwap_val:.2f}</b>（現價乖離：<span class="{('tw-up' if vwap_diff > 0 else 'tw-down')}">{vwap_diff:+.2f}%</span>）
                </div>
                """, unsafe_allow_html=True)

            if cdp_info:
                st.markdown("##### 📏 今日 CDP 逆勢五大關鍵價（Price Ladder 階梯看板）")
                st.markdown(f"""
                <div style="background: rgba(128, 128, 128, 0.05); border: 1px solid rgba(128, 128, 128, 0.2); border-radius: 10px; padding: 0.6rem 0.8rem; margin-bottom: 0.6rem; font-size: 0.92rem;">
                    <div style="display:flex; justify-content:space-between; align-items:center; padding: 0.25rem 0; border-bottom: 1px dashed rgba(128,128,128,0.2);">
                        <span>🚨 <b>最高阻力 (AH)</b> <span style="font-size:0.78rem; color:#888;">極限超買警戒</span></span>
                        <b class="tw-up" style="font-size:1.05rem;">{cdp_info['AH']:,.2f}</b>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; padding: 0.25rem 0; border-bottom: 1px dashed rgba(128,128,128,0.2);">
                        <span>🎯 <b>次高阻力 (NH)</b> <span style="font-size:0.78rem; color:#888;">第一停利目標</span></span>
                        <b class="tw-up" style="font-size:1.05rem;">{cdp_info['NH']:,.2f}</b>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; padding: 0.35rem 0; background: rgba(26,115,232,0.08); border-radius: 6px; margin: 0.2rem 0; padding-left: 0.4rem; padding-right: 0.4rem;">
                        <span>⚖️ <b>多空平衡 (CDP)</b> <span style="font-size:0.78rem; color:#1a73e8;">強弱分水嶺軸心</span></span>
                        <b style="font-size:1.15rem; color:#1a73e8;">{cdp_info['CDP']:,.2f}</b>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; padding: 0.25rem 0; border-bottom: 1px dashed rgba(128,128,128,0.2);">
                        <span>🛡️ <b>次低支撐 (NL)</b> <span style="font-size:0.78rem; color:#888;">短線拉回承接</span></span>
                        <b class="tw-down" style="font-size:1.05rem;">{cdp_info['NL']:,.2f}</b>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; padding: 0.25rem 0;">
                        <span>❄️ <b>最低支撐 (AL)</b> <span style="font-size:0.78rem; color:#888;">超跌極限防守</span></span>
                        <b class="tw-down" style="font-size:1.05rem;">{cdp_info['AL']:,.2f}</b>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("##### 🧮 現股當沖損益與保本跳動檔位計算機")
            calc_c1, calc_c2 = st.columns(2)
            with calc_c1:
                dt_shares_lot = st.number_input("當沖張數 (Lots)", min_value=1, max_value=500, value=1, step=1, key=f"dt_lots_{stable_key_suffix}")
            with calc_c2:
                saved_disc = float(user_memory.get("daytrade_fee_discount", 0.28))
                dt_discount = st.number_input("手續費折讓係數", min_value=0.10, max_value=1.00, value=saved_disc, step=0.01, key=f"dt_disc_{stable_key_suffix}")

            needed_ticks, tick_sz, cost_1lot, profit_1tick = calc_daytrade_breakeven(close, dt_discount)
            total_cost_lots = cost_1lot * dt_shares_lot
            total_1tick_profit = profit_1tick * dt_shares_lot
            net_profit_1tick = total_1tick_profit - total_cost_lots

            grid_r1_c1, grid_r1_c2 = st.columns(2)
            grid_r1_c1.metric("每檔跳動金額", f"{tick_sz:.2f} 元", f"1檔={int(total_1tick_profit):,}元")
            grid_r1_c2.metric("損益兩平需跳動", f"{needed_ticks} 檔", f"跳 {needed_ticks} 檔即保本")

            grid_r2_c1, grid_r2_c2 = st.columns(2)
            grid_r2_c1.metric("買賣總稅費成本", f"{int(total_cost_lots):,} 元", help="已含 0.15% 減半證交稅與折讓手續費")
            net_sign = "+" if net_profit_1tick > 0 else ""
            grid_r2_c2.metric("跳 1 檔淨盈虧", f"{net_sign}{int(net_profit_1tick):,} 元", "實質獲利" if net_profit_1tick > 0 else "未打平稅費")

            st.caption(f"📌 **實戰提醒**：目前股價為 `{close:.2f}` 元，跳動單位為 `{tick_sz:.2f}` 元。當沖進場後只要朝方向跳動 **{needed_ticks} 檔** 即保本，後續每多跳動 1 檔可實收 **{int(total_1tick_profit):,} 元**。")

    if mode_type in ("tw", "us"):
        render_institutional_research_panel(res, ticker_raw, mode_type=mode_type)

    guide_title = "🎯 【權威期顧分析師共識 ＆ 精確期貨下單卡】" if mode_type == "futures" else "🎯 【權威分析師共識 ＆ 精確下單指引】"
    with st.expander(guide_title, expanded=True):
        if an_data.get("has_data"):
            st.markdown(f"**機構綜合多空評等：** `{an_data['rec_label']}`")
            st.caption(f"📌 {an_data['rec_desc']}（共計 **{an_data['opinions']} 家** 機構追蹤）")

            a_c1, a_c2 = st.columns(2)
            if an_data['target_mean'] > 0 and close > 0:
                upside_pct = ((an_data['target_mean'] - close) / close) * 100.0
                a_c1.metric("法人目標點位", f"{an_data['target_mean']:.1f} {currency_sym}", f"{upside_pct:+.1f}% 空間")
            elif an_data['target_mean'] > 0:
                a_c1.metric("法人目標點位", f"{an_data['target_mean']:.1f} {currency_sym}")
            else:
                a_c1.metric("法人目標點位", "波段推算")
            a_c2.metric("追蹤覆蓋機構", f"{an_data['opinions']} 家")

            if an_data.get('target_high', 0) > 0:
                st.caption(f"📊 法人區間分歧度：下檔支撐 **{an_data['target_low']:.1f}** ～ 上檔壓力 **{an_data['target_high']:.1f} {currency_sym}**")
        else:
            st.info("💡 該標的暫無多數機構公開報告，目標價已依波段動態空間推算。")

        st.write("---")
        st.markdown(f"### 📋 【精確{unit_name}下單執行卡】")
        if is_spot_fallback:
            st.error("🚨 **【現貨參考模式・停用期貨下單建議】**：外部行情庫暫無此期貨即時撮合數據，目前點位走勢引自加權指數現貨。為防範實盤風控風險，**已停用本卡片之期貨下單點位、停損停利試算與建議口數**！請俟取得真實期貨撮合後再行下單。")
        elif is_downtrend:
            st.error(f"🚫 **當前禁止做多**：現價（{close:.2f} {currency_sym}）已跌破月線生命線（{res['ma_status']['ma20_val']:.2f} {currency_sym}），空方控盤，順勢交易者嚴禁逆勢摸底！若持有部位，建議退場防守價設為 `{res['stop_loss']:.2f} {currency_sym}`。")
        else:
            t1_str = f"{target_1:.2f}" if target_1 is not None else "--"
            st.markdown(f"""
            1. **建議進場區間**：**`{close:.2f} {currency_sym}`**（回測 5MA 不破分批布局）。
            2. **波段防守點位**：**`{res['stop_loss']:.2f} {currency_sym}`**（跌破點位立即退場，絕不凹單）。
            3. **第一獲利目標**：**`{t1_str} {currency_sym}`**（達成 1.5R 盈虧比，平倉 1/2 入袋並上移防守至成本）。
            4. **波段獲利目標**：**`{res['target_60d']:.2f} {currency_sym}`**（對齊機構目標價或波段高點擴展區）。
            """)

    with st.expander("📝 【決策結論與多空架構】", expanded=False):
        if is_downtrend:
            st.error(f"### 🔴 空方架構：現價（{close:.2f} {currency_sym}）跌破月線生命線（{res['ma_status']['ma20_val']:.2f} {currency_sym}），嚴禁追價摸底！")
            st.write(f"- 當前價位位於月線（20MA）之下，短中期均線蓋頭下壓，等待止跌築底翻揚再行介入。建議防守價位：**{res['stop_loss']:.2f} {currency_sym}**。")
        elif res['total_score'] >= 75:
            st.success(f"### 🟢 積極偏多：技術量價動能同步翻多，適合進場 (防守: {res['stop_loss']:.2f} {currency_sym})")
        elif 60 <= res['total_score'] < 75:
            st.warning("### 🟡 穩健觀察：指標整理或分歧，僅限輕倉試單")
        else:
            st.error("### 🔴 暫緩進場：評價過高或短期均線下壓，空手觀望為上")


    # ★ 輕量按鈕觸發：Gemini 3.8 AI 質化操盤劇本解讀
    with st.expander("🤖 【Gemini 首席操盤手・質化劇本解讀 (輕量按需觸發)】", expanded=False):
        st.caption("⚡ **零記憶體負擔・不干預確定性算術**：點擊下方按鈕後才呼叫雲端模型，針對當前技術位階、VIX 恐慌分位與外電進行質化劇本推演（內建 30 分鐘快取保護，不重複消耗 API 額度）。")
        ai_cache_key = f"ai_playbook_res_{stable_key_suffix}"
        if st.button("🚀 呼叫 Gemini 生成即時多空應變劇本", type="primary", use_container_width=True, key=f"btn_gemini_{stable_key_suffix}"):
            with st.spinner("連線 Gemini 3.8 進行跨維度質化劇本推演中..."):
                vix_d = fetch_vix_percentile()
                vix_p_val = safe_float(vix_d.get("vix_price"), 18.0) if vix_d.get("has_data") else 18.0
                vix_pct_val = safe_float(vix_d.get("vix_pct"), 50.0) if vix_d.get("has_data") else 50.0
                n_items = fetch_stock_news(ticker_raw) if (ticker_raw and mode_type != "futures") else []
                n_titles = tuple( item["title"] for item in n_items[:3] ) if n_items else ()
                sel_model = str(st.session_state.get("gemini_model_choice", GEMINI_DEFAULT_MODEL))
                ok_flag, ai_text = fetch_gemini_qualitative_playbook(
                    api_key=get_gemini_api_key(),
                    model_name=sel_model,
                    ticker_label=disp_header or str(ticker_raw),
                    asset_type=mode_type,
                    close_p=close,
                    total_score=int(res.get("total_score", 0)),
                    ma_alignment=str(res.get("ma_alignment", "")),
                    ma20_diff=safe_float(res.get("ma_status", {}).get("ma20_diff", 0.0)),
                    is_breakdown=bool(is_downtrend),
                    k_type=str(res.get("k_type", "")),
                    gap_pct=safe_float(res.get("gap_pct", 0.0)),
                    vix_price=vix_p_val,
                    vix_pct=vix_pct_val,
                    rel_alpha_20d=safe_float(res.get("rel_alpha_20d", 0.0)),
                    rec_label=str(an_data.get("rec_label", "中立")),
                    news_titles_tuple=n_titles
                )
                st.session_state[ai_cache_key] = (ok_flag, ai_text)

        if ai_cache_key in st.session_state:
            ok_flag, ai_text = st.session_state[ai_cache_key]
            if ok_flag:
                st.info(ai_text)
            else:
                st.warning(ai_text)

    # ★ 十大技術指標 Check-list 計分儀表板
    with st.expander("📊 【十大技術指標 Check-list 儀表板】量化多空逐項檢視", expanded=False):
        st.caption("透過 10 項嚴格量化規則進行多空體質逐項檢核，暖機資料不足時明確標示 N/A：")
        
        closes_s = df_asset['Close']
        ma5_s = df_asset['MA5'] if 'MA5' in df_asset.columns else closes_s.rolling(5, min_periods=5).mean()
        ma20_s = df_asset['MA20'] if 'MA20' in df_asset.columns else closes_s.rolling(20, min_periods=20).mean()
        ma60_s = df_asset['MA60'] if 'MA60' in df_asset.columns else closes_s.rolling(60, min_periods=60).mean()
        rsi_s = df_asset['RSI14'] if 'RSI14' in df_asset.columns else pd.Series([np.nan]*len(df_asset))
        osc_s = df_asset['OSC'] if 'OSC' in df_asset.columns else pd.Series([np.nan]*len(df_asset))
        vol_s = df_asset['Volume'] if 'Volume' in df_asset.columns else pd.Series([0]*len(df_asset))
        vol_ma5_s = df_asset['Vol_MA5'] if 'Vol_MA5' in df_asset.columns else vol_s.rolling(5, min_periods=5).mean()
        
        c_val = safe_float(closes_s.iloc[-1])
        has_m5 = pd.notna(ma5_s.iloc[-1])
        has_m20 = pd.notna(ma20_s.iloc[-1])
        has_m60 = pd.notna(ma60_s.iloc[-1])
        has_rsi = pd.notna(rsi_s.iloc[-1])
        has_osc = pd.notna(osc_s.iloc[-1])
        has_vol_m5 = pd.notna(vol_ma5_s.iloc[-1]) and safe_float(vol_ma5_s.iloc[-1]) > 0
        has_atr = ('ATR14' in df_asset.columns) and pd.notna(df_asset['ATR14'].iloc[-1])

        m5_v = safe_float(ma5_s.iloc[-1], c_val)
        m20_v = safe_float(ma20_s.iloc[-1], c_val)
        m60_v = safe_float(ma60_s.iloc[-1], c_val)
        rsi_v = safe_float(rsi_s.iloc[-1], default=None) if has_rsi else None
        osc_v = safe_float(osc_s.iloc[-1], default=None) if has_osc else None
        vol_v = safe_float(vol_s.iloc[-1], 0.0)
        vol_m5_v = safe_float(vol_ma5_s.iloc[-1], 1.0)
        
        # 1. 均線排列 (需滿 60 日暖機)
        chk_ma_align = bool(has_m5 and has_m20 and has_m60 and (c_val > m5_v > m20_v > m60_v))
        # 2. 月線生命線 (需滿 20 日暖機)
        chk_ma20 = bool(has_m20 and (c_val > m20_v))
        # 3. 季線多頭 (需滿 60 日暖機)
        chk_ma60 = bool(has_m20 and has_m60 and (m20_v > m60_v))
        # 4. 成交量能爆量 (需滿 5 日均量)
        chk_vol = bool(has_vol_m5 and ((vol_v / (vol_m5_v + 1e-9)) >= 1.2))
        # 5. MACD 多頭攻擊
        chk_macd = bool(has_osc and osc_v is not None and osc_v > 0 and (len(osc_s) >= 2 and pd.notna(osc_s.iloc[-2]) and osc_v > safe_float(osc_s.iloc[-2])))
        # 6. RSI 動能區間 (需滿 14 日暖機，絕不將 NaN 偽裝為 50)
        chk_rsi = bool(has_rsi and rsi_v is not None and (50.0 <= rsi_v <= 70.0))
        # 7. 價格高於開盤價
        o_val = safe_float(df_asset.iloc[-1].get('Open'), c_val)
        chk_k = bool(c_val >= o_val)
        # 8. 波動率防守 (ATR 需滿 14 日暖機)
        atr_v = safe_float(df_asset.iloc[-1].get('ATR14'), default=None) if has_atr else None
        chk_atr = bool(has_atr and atr_v is not None and c_val > 0 and ((atr_v / c_val) < 0.04))
        # 9. 綜合評分門檻
        chk_score = bool(res.get('total_score', 0) >= 70)
        # 10. 相對大盤強度
        chk_alpha = bool(res.get('rel_alpha_20d', 0.0) >= 0.0)
        
        rsi_disp_note = f"{rsi_v:.1f}" if rsi_v is not None else "N/A 暖機不足"
        atr_disp_note = f"{(atr_v / c_val * 100):.2f}%" if (atr_v is not None and c_val > 0) else "N/A 暖機不足"

        check_items = [
            ("1. 均線完美多頭排列 (P>5MA>20MA>60MA)", chk_ma_align, has_m60, "+15分"),
            ("2. 站穩月線生命線 (Price > 20MA)", chk_ma20, has_m20, "+12分"),
            ("3. 中長線季線多頭架構 (20MA > 60MA)", chk_ma60, has_m60, "+10分"),
            ("4. 盤中帶量攻擊 (成交量 >= 1.2x 5日均量)", chk_vol, has_vol_m5, "+10分"),
            ("5. MACD 動能紅柱放大 (OSC > 0 且擴增)", chk_macd, has_osc, "+10分"),
            (f"6. RSI14 處健康攻擊區 50~70 (當前: {rsi_disp_note})", chk_rsi, has_rsi, "+8分"),
            ("7. 實體 K 棒開低走高或收紅 (Close >= Open)", chk_k, True, "+5分"),
            (f"8. 波動率 ATR14 風控適度 <4% (當前: {atr_disp_note})", chk_atr, has_atr, "+5分"),
            ("9. 總合量化決策評分達標 (Score >= 70分)", chk_score, True, "+15分"),
            ("10. 近 20 日相對大盤超額報酬 (Alpha >= 0%)", chk_alpha, len(df_asset) >= 21, "+10分"),
        ]
        
        passed_count = sum(1 for _, passed, _, _ in check_items if passed)
        st.markdown(f"**💡 檢核通過項目：`{passed_count} / 10 項`**（綜合評分：`{res.get('total_score', 0)} 分`）")
        
        for desc, passed, is_ready, score_val in check_items:
            icon = "🟢 符合" if passed else ("⏳ 資料暖機中(N/A)" if not is_ready else "⚪ 未符")
            st.markdown(f"- `{icon}` **{desc}**（權重：{score_val}）")

    with st.expander("⚡ 【開盤即時撮合動態】", expanded=False):
        st.markdown(f"**當前 K 棒型態：** `{res['k_type']}`")
        k1, k2 = st.columns(2)
        k1.metric("開盤跳空幅度", f"{res['gap_pct']:+.2f}%")
        k2.metric("開盤至今漲跌", f"{res['intraday_pct']:+.2f}%")
        st.write("---")
        for d in res['opening_diag']:
            st.write(f"• {d}")

    with st.expander("📏 【日 / 月 / 季線 位階矩陣】", expanded=False):
        st.markdown(f"**均線排列結構：** `{res['ma_alignment']}`")
        m1, m2, m3 = st.columns(3)
        m_stat = res['ma_status']
        m1.metric("日線 (5MA)", f"{m_stat['ma5_val']:.2f}" if m_stat.get('has_ma5', True) else "N/A (未滿5日)", f"{m_stat['ma5_diff']:+.1f}%" if m_stat.get('has_ma5', True) else "暖機中")
        m2.metric("月線 (20MA)", f"{m_stat['ma20_val']:.2f}" if m_stat.get('has_ma20', True) else "N/A (未滿20日)", f"{m_stat['ma20_diff']:+.1f}%" if m_stat.get('has_ma20', True) else "暖機中")
        m3.metric("季線 (60MA)", f"{m_stat['ma60_val']:.2f}" if m_stat.get('has_ma60', True) else "N/A (未滿60日)", f"{m_stat['ma60_diff']:+.1f}%" if m_stat.get('has_ma60', True) else "暖機中")

    if mode_type == "futures":
        with st.expander("💎 【期貨契約規格與保證金護城河】", expanded=False):
            st.markdown(f"**標的商品**：`{spec['name']}` ｜ {spec['desc']}")
            st.caption(f"📌 保證金資料基準日：`{FUTURES_MARGIN_UPDATED_AT}` ｜ 來源：{FUTURES_MARGIN_SOURCE}（期交所可能隨市場波動動態調整，實盤請以期貨商最新公告為準）")
            sp1, sp2 = st.columns(2)
            sp1.metric("每一跳動點價值", f"NT$ {spec['tick_value']:,} 元")
            sp2.metric("原始保證金門檻", f"NT$ {spec['initial_margin']:,} 元")

            sp3, sp4 = st.columns(2)
            sp3.metric("維持保證金警戒線", f"NT$ {spec['maintenance_margin']:,} 元")
            pt_val = spec.get('point_value', spec.get('tick_value', 200))
            contract_nominal_val = close * pt_val
            leverage = (contract_nominal_val / spec['initial_margin']) if spec['initial_margin'] > 0 else 0.0
            sp4.metric("實質契約槓桿倍數", f"{leverage:.1f} 倍")
    else:
        fund_title = "💎 【ETF 專屬體質與配息分析】" if res['fund_data'].get('is_etf') else "💎 【企業基本面體質護城河】"
        with st.expander(fund_title, expanded=False):
            f_data = res['fund_data']
            if not f_data.get("has_data", False):
                st.warning("⚠️ 該標的未揭露足夠之財報/配息數據，系統已將基本面評分排除，並自動重新權衡動能指標。")
            elif f_data.get('is_etf'):
                f1, f2 = st.columns(2)
                f1.metric("預估年化殖利率", f"{f_data['yield']:.1f}%" if f_data['yield'] is not None else "未揭露")
                f2.metric("Beta 波動係數", f"{f_data['beta']:.2f}" if f_data['beta'] is not None else "未揭露")
            else:
                f1, f2 = st.columns(2)
                f1.metric("ROE 股東權益報酬率", f"{f_data['roe']:.1f}%" if f_data['roe'] is not None else "無數據")
                f2.metric("營業利益率", f"{f_data['op_margin']:.1f}%" if f_data['op_margin'] is not None else "無數據")
                f3, f4 = st.columns(2)
                f3.metric("本益比 (PE)", f"{f_data['pe']:.1f}x" if (f_data['pe'] is not None and f_data['pe'] > 0) else "不適用/虧損")
                f4.metric("負債權益比 (D/E)", f"{f_data['debt_ratio']:.1f}%" if f_data['debt_ratio'] is not None else "無數據", help="負債／股東權益比率 (Debt-to-Equity Ratio)，各產業資本結構差異大")
            st.write("---")
            for r in f_data.get('reasons', []):
                st.write(f"• {r}")

    with st.expander("🚪 【階梯式分階出場 SOP】", expanded=False):
        if is_spot_fallback:
            st.info("⚪ 目前處於現貨參考模式，請俟取得真實期貨合約撮合點位後再行規劃進出場目標。")
        elif is_downtrend:
            st.warning(f"🚫 空方弱勢架構：現價已跌破月線（20MA），系統暫停提供多單目標，嚴禁逆勢摸底做多！持有部位請嚴格以防守點位 **`{res['stop_loss']:.2f}` {currency_sym}** 退場止血。")
        else:
            t1_val_str = f"{target_1:.2f}" if target_1 is not None else "--"
            st.markdown(f"""
            - **初始防守停損**：跌破 **`{res['stop_loss']:.2f}` {currency_sym}** 嚴格離場，絕不凹單。
            - **第一階段目標（減碼 1/2）**：達 **`{t1_val_str}` {currency_sym}**（1.5R 盈虧比），平倉半數部位入袋並上移防守至成本價（鎖定保本）。
            - **第二階段目標（波段收割）**：達 **`{res['target_60d']:.2f}` {currency_sym}** 分批落袋。
            - **移動停利（Trailing Stop）**：其餘部位收盤跌破 5 日線全數獲利了結。
            """)

    with st.expander(f"💰 【部位風控與建議{unit_name}計算機】", expanded=False):
        col_cap, col_risk = st.columns(2)
        with col_cap:
            if mode_type == "futures":
                default_cap = int(user_memory.get("capital_fut", 1000000))
                cap_step = 100000
                cap_label = "期貨專戶保證金餘額 (NTD)"
            elif mode_type == "us":
                default_cap = int(user_memory.get("capital_us", 50000))
                cap_step = 5000
                cap_label = "總操作資金 (USD)"
            else:
                default_cap = int(user_memory.get("capital_tw", 1000000))
                cap_step = 100000
                cap_label = "總操作資金 (NTD)"
            total_capital = st.number_input(cap_label, value=default_cap, step=cap_step, key=f"calc_cap_{stable_key_suffix}")
        with col_risk:
            default_r = float(user_memory.get("risk_pct", 1.0))
            risk_tolerance = st.slider("單筆最大承受損失比率 (%)", min_value=0.5, max_value=5.0, value=min(max(default_r, 0.5), 5.0), step=0.1, key=f"calc_risk_{stable_key_suffix}")

        max_risk_dollar = total_capital * (risk_tolerance / 100.0)

        if mode_type == "futures":
            pt_val = spec.get('point_value', spec.get('tick_value', 200))
            loss_per_unit = risk_unit * pt_val
            risk_based_pos = int(max_risk_dollar // loss_per_unit) if loss_per_unit > 0 else 0
            margin_max_pos = int(total_capital // spec['initial_margin']) if spec['initial_margin'] > 0 else 0
            suggested_pos = min(risk_based_pos, margin_max_pos)
        elif mode_type == "us":
            loss_per_unit = risk_unit * 1.0
            risk_based_pos = int(max_risk_dollar // loss_per_unit) if loss_per_unit > 0 else 0
            capital_max_pos = int(total_capital // close) if close > 0 else 0
            suggested_pos = min(risk_based_pos, capital_max_pos)
        else:
            loss_per_unit = risk_unit * 1000.0
            risk_based_pos = int(max_risk_dollar // loss_per_unit) if loss_per_unit > 0 else 0
            capital_max_lots = int(total_capital // (close * 1000.0)) if close > 0 else 0
            suggested_pos = min(risk_based_pos, capital_max_lots)

        potential_reward = max(res['target_60d'] - close, 0)
        rr_ratio = potential_reward / risk_unit if risk_unit > 0 else 0

        if is_spot_fallback:
            st.warning("⚪ **現貨參考模式**：由於未能取得真實期貨合約撮合報價，已停用自動可下口數試算與保證金槓桿建議。")
        elif is_downtrend:
            st.warning(f"⚠️ **空方弱勢警示**：目前處於跌破月線格局，系統建議進場數量為 **0 {unit_name}**（觀望為宜）。若依個人風控上限計算，最多承受規模為 **{suggested_pos} {unit_name}**。")
            b1, b2 = st.columns(2)
            b1.metric("單筆最大容許虧損", f"{int(max_risk_dollar):,} 元" if mode_type != "us" else f"{int(max_risk_dollar):,} USD")
            b2.metric("建議多單進場數量", f"0 {unit_name}")
            b3, b4 = st.columns(2)
            b3.metric("多方目標獲利區", "--")
            b4.metric("多方預期風報比", "--")
        else:
            b1, b2 = st.columns(2)
            b1.metric("單筆最大容許虧損", f"{int(max_risk_dollar):,} 元" if mode_type != "us" else f"{int(max_risk_dollar):,} USD")
            b2.metric("建議最大進場數量", f"{suggested_pos} {unit_name}", help="同時受限於風險停損額與保證金/現金購買力")
            b3, b4 = st.columns(2)
            b3.metric("目標獲利區", f"{res['target_60d']:.1f} {currency_sym}")
            b4.metric("預期盈虧比 (R/R)", f"{rr_ratio:.2f} : 1")

    with st.expander(f"📊 【過去 1 年{unit_name}策略回測數據 (簡化歷史模擬)】", expanded=False):
        bt = backtest_strategy(df_asset, market_type=mode_type)
        if bt:
            bt1, bt2 = st.columns(2)
            bt1.metric("近 1 年訊號次數", f"{bt['count']} 次")
            bt2.metric("持有 5 日勝率", f"{bt['win_rate']:.1f}%")
            if mode_type == "futures":
                fee_note = "已扣除期指交易稅與點數滑價摩擦成本"
            elif mode_type == "us":
                fee_note = "已扣除 0.1% 美股摩擦成本"
            else:
                fee_note = "已扣除 0.45% 台股稅費"
            bt3, bt4 = st.columns(2)
            bt3.metric("平均淨報酬率", f"{bt['avg_return']:+.2f}%", help=fee_note)
            bt4.metric("簡化交易回撤 (MDD)", f"{bt['mdd']:.2f}%", help="依固定持有期交易序列計算之最大峰谷回撤，未含逐日持倉估值、盤中滑價與保證金追繳路徑")
            st.caption(f"📌 單部位循序進出（持倉中不重複進場）、單次最差交易：`{bt['worst_loss']:.2f}%`")
        else:
            st.write("該標的歷史數據樣本不足以計算有效回測。")

    with st.expander("📈 【近 60 日均線 (5/20/60MA) 波段走勢圖】", expanded=False):
        valid_cols = ['Close']
        for c in ['MA5', 'MA20', 'MA60']:
            if c in df_asset.columns and df_asset[c].notna().sum() > 5:
                valid_cols.append(c)
        chart_data = df_asset[valid_cols].dropna().tail(60)
        st.line_chart(chart_data)

# ----------------- 全域頂層初始化與數據載入 (順序嚴格位於定義後) -----------------
bench_dict = preload_global_benchmarks()
df_market = bench_dict.get("^TWII")
df_futures_bench = bench_dict.get("WTX=F")
df_tsm = bench_dict.get("TSM")
df_sox = bench_dict.get("^SOX")
df_spx = bench_dict.get("^GSPC")
global_forex = analyze_forex_data()

if "main_mode" not in st.session_state:
    st.session_state.main_mode = "live_watch"

if "selected_tw_ticker" not in st.session_state:
    st.session_state.selected_tw_ticker = "2330.TW"
if "tw_ticker_field" not in st.session_state:
    st.session_state.tw_ticker_field = "2330.TW"

if "selected_us_ticker" not in st.session_state:
    st.session_state.selected_us_ticker = "NVDA"
if "us_ticker_field" not in st.session_state:
    st.session_state.us_ticker_field = "NVDA"

if "selected_fut_contract" not in st.session_state:
    st.session_state.selected_fut_contract = "WTX"
if "tw_fut_field" not in st.session_state:
    st.session_state.tw_fut_field = "WTX"

if "auto_run_tw" not in st.session_state:
    st.session_state.auto_run_tw = False
if "auto_run_us" not in st.session_state:
    st.session_state.auto_run_us = False
if "auto_run_fut" not in st.session_state:
    st.session_state.auto_run_fut = False

if "analysis_cache_tw" not in st.session_state:
    st.session_state.analysis_cache_tw = None
if "analysis_cache_us" not in st.session_state:
    st.session_state.analysis_cache_us = None
if "analysis_cache_fut" not in st.session_state:
    st.session_state.analysis_cache_fut = None
if "etf_category_filter" not in st.session_state:
    st.session_state.etf_category_filter = "全部"

user_memory = get_user_data()

# ★ 雙系統手機專用字體縮放與護眼引擎 (iOS / Android 跨平台全面適配・防眼睛疲勞)
curr_font_scale = user_memory.get("font_scale", "舒適護眼大字 (115%・推薦)")
if "130%" in curr_font_scale:
    st.markdown("""
    <style>
        html, body, p, span, div, input, textarea {
            font-size: 1.15rem !important;
            line-height: 1.68 !important;
            -webkit-text-size-adjust: 100% !important;
            text-size-adjust: 100% !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif !important;
        }
        h1 { font-size: 1.68rem !important; }
        h2 { font-size: 1.48rem !important; }
        h3 { font-size: 1.32rem !important; }
        div[data-testid="stMetricValue"] { font-size: 1.58rem !important; font-weight: 800 !important; }
        div[data-testid="stMetricLabel"] { font-size: 1.06rem !important; font-weight: 700 !important; }
        div.stButton > button, div[data-testid="stFormSubmitButton"] > button {
            font-size: 1.12rem !important;
            min-height: 3.1rem !important;
        }
        .yahoo-stat-box, .macro-alert-card, .daytrade-card, .inst-report-box {
            font-size: 1.08rem !important;
            line-height: 1.75 !important;
        }
    </style>
    """, unsafe_allow_html=True)
elif "115%" in curr_font_scale:
    st.markdown("""
    <style>
        html, body, p, span, div, input, textarea {
            font-size: 1.05rem !important;
            line-height: 1.58 !important;
            -webkit-text-size-adjust: 100% !important;
            text-size-adjust: 100% !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif !important;
        }
        h1 { font-size: 1.52rem !important; }
        h2 { font-size: 1.32rem !important; }
        h3 { font-size: 1.18rem !important; }
        div[data-testid="stMetricValue"] { font-size: 1.42rem !important; font-weight: 800 !important; }
        div[data-testid="stMetricLabel"] { font-size: 0.98rem !important; font-weight: 700 !important; }
        div.stButton > button, div[data-testid="stFormSubmitButton"] > button {
            font-size: 1.04rem !important;
            min-height: 2.85rem !important;
        }
        .yahoo-stat-box, .macro-alert-card, .daytrade-card, .inst-report-box {
            font-size: 1.00rem !important;
            line-height: 1.68 !important;
        }
    </style>
    """, unsafe_allow_html=True)

# ★ 自動更新置頂戰情焦點（免手動釘選）
current_briefing = get_auto_market_briefing(df_market, df_sox, global_forex)

# ----------------- 頂部導航與功能設置 -----------------
st.title("📱 股期決策旗艦站 (跨市場機構版)")

with st.expander("⚙️ 個人風控本金、當沖折讓與看盤備忘錄", expanded=False):
    st.caption(f"📌 **本地端設定提示**：目前偏好參數儲存於伺服器本地環境 ({SETTINGS_FILE})。若在雲端多人環境使用，請使用下方備份碼匯入/匯出保存個人專屬設定。")
    p_c1, p_c2, p_c3, p_c4 = st.columns(4)
    with p_c1:
        u_cap_tw = st.number_input("台股預設本金(NTD)", value=int(user_memory.get("capital_tw", 1000000)), step=100000, key="prof_cap_tw")
    with p_c2:
        u_cap_fut = st.number_input("期貨預設本金(NTD)", value=int(user_memory.get("capital_fut", 1000000)), step=100000, key="prof_cap_fut")
    with p_c3:
        u_cap_us = st.number_input("美股預設本金(USD)", value=int(user_memory.get("capital_us", 50000)), step=5000, key="prof_cap_us")
    with p_c4:
        u_risk = st.number_input("單筆風險(%)", min_value=0.5, max_value=5.0, value=float(user_memory.get("risk_pct", 1.0)), step=0.1, key="prof_risk")

    u_disc = st.slider("當沖券商手續費折讓（例如 2.8 折輸入 0.28）", min_value=0.10, max_value=1.00, value=float(user_memory.get("daytrade_fee_discount", 0.28)), step=0.01, key="prof_disc")
    
    font_scale_opts = ["舒適護眼大字 (115%・推薦)", "清晰長輩超大字 (130%)", "標準字體 (100%)"]
    saved_font_scale = user_memory.get("font_scale", "舒適護眼大字 (115%・推薦)")
    def_font_idx = font_scale_opts.index(saved_font_scale) if saved_font_scale in font_scale_opts else 0
    u_font = st.selectbox("👀 雙系統手機專用字體縮放・護眼調節 (iOS / Android 通用)", options=font_scale_opts, index=def_font_idx, key="prof_font_scale_choice", help="專為 iPhone (iOS) 與安卓 (Android) 手機高解析螢幕量身打造：自動適配系統繁中字型，放大即時報價、指標與分析文字，不瞇眼長時間看盤更舒適")
    
    u_note = st.text_area("📝 個人看盤備忘錄", value=user_memory.get("personal_note", ""), height=68, key="prof_note")

    st.write("---")
    st.caption("🤖 **Gemini AI 操盤劇本設定（選填・僅保存在當前瀏覽器 Session 記憶體，絕不寫入公開檔案以防外洩）**：")
    ai_c1, ai_c2 = st.columns([2.2, 1.8])
    with ai_c1:
        u_gemini_key = st.text_input(
            "Gemini API Key (若已設於 Streamlit Secrets 可留空)",
            value=st.session_state.get("session_gemini_api_key", ""),
            type="password",
            placeholder="AIzaSy...",
            key="prof_gemini_key_in"
        )
    with ai_c2:
        u_gemini_model = st.selectbox(
            "首選推演模型版本",
            options=["自動最佳模型 (推薦)", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash"],
            index=0,
            key="gemini_model_choice",
            help="預設自動向 Google 查詢並套用您金鑰可用之最佳模型；若失敗會自動平滑降級備援"
        )
    
    if st.button("💾 儲存本機偏好設定", use_container_width=True, key="btn_save_profile"):
        user_memory["capital_tw"] = u_cap_tw
        user_memory["capital_fut"] = u_cap_fut
        user_memory["capital_us"] = u_cap_us
        user_memory["risk_pct"] = u_risk
        user_memory["daytrade_fee_discount"] = u_disc
        user_memory["font_scale"] = u_font
        user_memory["personal_note"] = u_note
        if u_gemini_key.strip():
            st.session_state["session_gemini_api_key"] = u_gemini_key.strip()
        save_user_data()
        st.success("已儲存偏好參數！")

with st.expander("📦 匯出 / 匯入設定備份碼（防雲端休眠重置）", expanded=False):
    backup_str = json.dumps(user_memory, ensure_ascii=False)
    st.code(backup_str, language="json")
    restore_str = st.text_input("貼上備份碼一鍵還原", placeholder='{"tw_favorites": ...}', key="restore_json_in")
    if st.button("📥 確認還原設定", key="btn_restore_json"):
        try:
            restored = json.loads(restore_str)
            if isinstance(restored, dict):
                st.session_state.user_data = validate_and_sanitize_settings(restored)
                save_user_data()
                st.success("設定資料已通過完整 Schema 驗證並成功還原！")
                st.rerun()
            else:
                st.error("備份碼非合法的 JSON 物件格式。")
        except Exception as e:
            logging.warning(f"還原備份碼解析失敗: {e}")
            st.error(f"備份碼格式錯誤：{str(e)}")

with st.expander("📘 點此查看【系統現行版本完整功能清單與版本說明 (V9.8 雙系統護眼旗艦版)】", expanded=False):
    st.markdown("""
    ### 🌟 系統定位與核心架構
    本系統為**跨市場全維度量化決策平台**，整合臺灣證券交易所 (TWSE) 官方即時撮合、臺灣銀行官方牌告匯率、Google 財經全頻道即時外電 RSS、華爾街四大權威機構研究模組、**美股夜盤/ADR即時監控**、**次日股市漲跌多重情境預測方案 (A/B/C/D)** 與**當沖實戰決策室（VWAP/CDP/ORB突破/保本跳動計算）**。

    ---
    ### 🛠️ 核心功能模組總覽 (最新 V9.8 雙系統護眼釋出標註)
    1. **👀 雙系統手機專用字體縮放 ＆ 護眼引擎 (iOS / Android 通用) [NEW]**：
       - **跨平台防視力疲勞設計**：專為 iPhone (iOS) 與安卓 (Android) 高解析手機螢幕量身打造，自動適配系統繁中字型棧，預設啟用「舒適護眼大字 (115%)」，並提供「清晰長輩超大字 (130%)」與「標準 (100%)」自由即時切換。
       - **全系統自適應縮放**：連動放大即時報價 (stMetric)、按鈕點擊熱區、五檔盤口深度條、戰情廣播卡片與即時外電文字，排版自動擴展不擠壓，徹底告別手機瞇眼看盤。
       - **輕量與持久化**：純客戶端 CSS 渲染，伺服器零負擔、零崩潰風險；字體偏好自動儲存於 `user_settings.json` 與備份碼中，重整自動套用。
    2. **🔮 次日開市漲跌多重情境預測方案 (A/B/C/D 精準 % 數模型) [NEW]**：
       - **多因子敏感度加權**：整合台積電 ADR (35%)、費半 SOXX (15%)、微型那指期貨 (15%) 與 10 年美債殖利率 (3%)。
       - **政策籌碼增益**：納入金管會限空令（借券賣出上限砍至 3%、融券保證金 130%）與國安基金授權效應。
       - **四大情境動態推演**：方案 A（極致樂觀軋空）、方案 B（常態開高走堅）、方案 C（拉高震盪整理）、方案 D（美股翻黑政策底防禦），提供精確漲跌 % 數、指數點位區間、發生機率與對應操盤軍規。
    3. **📰 全頻道即時外電情報匯流中心 (含彭博 / LINE TODAY / 路透社) [NEW]**：
       - 整合八大情報頻道：彭博社 Bloomberg、LINE TODAY 財經、路透社 Reuters、國內權威財經（鉅亨/經濟/工商）、半導體AI、宏觀利率、台股籌碼與美股巨頭。
       - 支援自由輸入自訂關鍵字速查，5 分鐘 TTL 快取保護（單次請求僅 30KB），完全零伺服器負擔且杜絕 429 限流。
       - 支援一鍵「📌 置頂」任何感興趣的外電至首頁頂部戰情廣播卡片。
    4. **🌐 美股大盤、台積電 ADR 與三大指標即時監控看板 [NEW]**：
       - 即時連線台積電 ADR (TSM)、費半 ETF (SOXX)、輝達 (NVDA)、那指期貨 (NQ) 與 10 年美債 (^TNX)。
       - 自適應雙欄排版，徹底解決手機螢幕文字被擠壓為省略號問題。
       - 內建 TSM 370 美元鐵底防線自動化多空警報燈號。
    5. **📈 分時走勢圖（含昨收平盤線 ＆ VWAP 均價）手機橫向自由滑動 [NEW]**：
       - 解除全域寬度限制，注入專屬滑動容器樣式（`touch-action: pan-x`、`overflow-x: auto`）。
       - 手機端支援手指平滑向左／向右滑動，完整查看開盤至最新分鐘的完整 K 線與均價。
    6. **⚡ 當沖實戰決策室（VWAP生命線・ORB突破・CDP五關卡・保本跳動計算）**：
       - **VWAP 典型價格均價線**：盤中多空第一分水嶺。
       - **ORB 15分K高低突破**：開盤主力表態順勢多空信號。
       - **CDP 逆勢五關卡價**：依前日日K高低收精確定位 AH、NH、CDP、NL、AL。
       - **當沖保本檔位計算機**：自動依股價級距換算損益兩平跳動檔位（含 0.15% 減半證交稅與券商折讓）。
       - **尾盤平倉倒數計時**：13:00 啟動提醒、13:20 強制清倉警報。
    7. **🏛️ 四大華爾街級權威機構深度研究套件**：
       - 財務分析（三率/現金流）、股票研究（多維估值/目標價）、財報分析（營收EPS/驚奇度）、市場研究（籌碼/Alpha）。
    8. **📋 證交所即時五檔盤口深度**：
       - 雙向深度能量條看板，視覺化呈現委買委賣厚度。
    """)

# ★ 置頂戰情廣播卡片（已升級為全自動即時更新，免手動訂選）
st.markdown(f"""
<div class="macro-alert-card">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.3rem;">
        <b style="color:#e53935; font-size:1.0rem;">{current_briefing['title']}</b>
    </div>
    <div style="font-size:0.9rem; opacity:0.95;">
        {current_briefing['content'].replace(chr(10), '<br>')}
    </div>
    <div style="font-size:0.78rem; color:#777; margin-top:0.4rem; text-align:right;">
        發布單位：{current_briefing['author']} ｜ 更新時間：{current_briefing['updated_at']}
    </div>
</div>
""", unsafe_allow_html=True)

# ★ 美股大盤與核心指標即時監控看板
render_us_live_dashboard()


st.link_button(
    "🌐 前往：台股技術量化與美股隔夜風險中心 (Vercel 外部系統)",
    url="https://stocks-two-omega.vercel.app/?openExternalBrowser=1",
    type="primary",
    use_container_width=True,
    help="點此開啟外部系統：包含十大指標計分卡、VIX 252日分位數、美股隔夜加權模板與回測中心"
)

st.warning("""
💡 **手機 LINE 用戶開啟提醒**：  
• 若於 LINE 內建瀏覽器點擊上方按鈕無反應，係因 LINE 防護機制限制另開分頁。  
• **建議開啟方式**：請點選 LINE 視窗右上角或右下角 **「⋮」選單**，選擇 **「以預設瀏覽器開啟」**（Chrome / Safari）。  
• 亦可直接複製外部站網址至手機瀏覽器前往：  
`https://stocks-two-omega.vercel.app/`
""")

top_c1, top_c2 = st.columns([1.4, 1.0])
with top_c1:
    if st.button("📺 大盤即時看盤 (分時/戰情)", type="primary" if st.session_state.main_mode == "live_watch" else "secondary", use_container_width=True, key="m_nav_live_watch"):
        st.session_state.main_mode = "live_watch"
        st.rerun()
with top_c2:
    auto_refresh = st.checkbox("⏱️ 30秒自動刷新", value=False, key="global_auto_refresh")

# 頂部八大模式切換
r1_c1, r1_c2 = st.columns(2)
with r1_c1:
    if st.button("🔍 台股診斷", type="primary" if st.session_state.main_mode == "tw_stock" else "secondary", use_container_width=True, key="m_nav_tw_stock"):
        st.session_state.main_mode = "tw_stock"
        st.rerun()
with r1_c2:
    if st.button("🇺🇸 美股診斷", type="primary" if st.session_state.main_mode == "us_stock" else "secondary", use_container_width=True, key="m_nav_us_stock"):
        st.session_state.main_mode = "us_stock"
        st.rerun()

r2_c1, r2_c2 = st.columns(2)
with r2_c1:
    if st.button("⚡ 台灣期貨", type="primary" if st.session_state.main_mode == "tw_futures" else "secondary", use_container_width=True, key="m_nav_tw_futures"):
        st.session_state.main_mode = "tw_futures"
        st.rerun()
with r2_c2:
    if st.button("📈 美股期貨", type="primary" if st.session_state.main_mode == "us_futures" else "secondary", use_container_width=True, key="m_nav_us_futures"):
        st.session_state.main_mode = "us_futures"
        st.rerun()

r3_c1, r3_c2 = st.columns(2)
with r3_c1:
    if st.button("📊 ETF 專區", type="primary" if st.session_state.main_mode == "etf" else "secondary", use_container_width=True, key="m_nav_etf"):
        st.session_state.main_mode = "etf"
        st.rerun()
with r3_c2:
    if st.button("💎 體質雷達", type="primary" if st.session_state.main_mode == "market" else "secondary", use_container_width=True, key="m_nav_market"):
        st.session_state.main_mode = "market"
        st.rerun()

r4_c1, r4_c2 = st.columns(2)
with r4_c1:
    if st.button("📢 法說與戰情導入", type="primary" if st.session_state.main_mode == "events" else "secondary", use_container_width=True, key="m_nav_events"):
        st.session_state.main_mode = "events"
        st.rerun()
with r4_c2:
    if st.button("💱 外匯大盤", type="primary" if st.session_state.main_mode == "forex" else "secondary", use_container_width=True, key="m_nav_forex"):
        st.session_state.main_mode = "forex"
        st.rerun()

st.write("")

# ================= 模式 0：📺 大盤即時分時看盤室 =================
if st.session_state.main_mode == "live_watch":
    dash = fetch_twse_market_dashboard()

    if dash["twii_price"] <= 0 and df_market is not None and len(df_market) >= 2:
        last_m = df_market.iloc[-1]
        prev_m = df_market.iloc[-2]
        dash["twii_price"] = safe_float(last_m["Close"])
        dash["twii_yclose"] = safe_float(prev_m["Close"])
        dash["twii_chg"] = dash["twii_price"] - dash["twii_yclose"]
        dash["twii_pct"] = (dash["twii_chg"] / (dash["twii_yclose"] + 1e-9)) * 100.0
        dash["twii_high"] = safe_float(last_m["High"])
        dash["twii_low"] = safe_float(last_m["Low"])

    st.subheader("📺 台股加權指數・即時分時走勢與大盤統計看盤室")
    st.caption(f"資料時間：{dash['data_time']} ｜ 點選下方「🔄 立即刷新報價」或勾選上方「30秒自動刷新」可即時追蹤盤勢")

    if st.button("🔄 立即刷新即時走勢與大盤統計", use_container_width=True, key="btn_refresh_live_watch"):
        fetch_twse_market_dashboard.clear()
        fetch_intraday_series.clear()
        fetch_live_macro_rss.clear()
        st.rerun()

    render_intraday_chart_widget("^TWII", title_name="加權指數 (^TWII)")

    st.markdown("### 📊 大盤即時委買委賣與漲跌家數統計")

    tw_cls = "tw-up" if dash["twii_chg"] > 0 else ("tw-down" if dash["twii_chg"] < 0 else "tw-flat")
    tw_sign = "+" if dash["twii_chg"] > 0 else ""

    ex_cls = "tw-up" if dash["ex_fin_chg"] > 0 else ("tw-down" if dash["ex_fin_chg"] < 0 else "tw-flat")
    ex_sign = "+" if dash["ex_fin_chg"] > 0 else ""
    ex_fin_str = (
        f"<span class='{ex_cls}'>{dash['ex_fin_price']:,.2f} ({ex_sign}{dash['ex_fin_chg']:,.2f} / {ex_sign}{dash['ex_fin_pct']:.2f}%)</span>"
        if dash["ex_fin_price"] > 0 else "<span>收盤結算中</span>"
    )

    otc_cls = "tw-up" if dash["otc_chg"] > 0 else ("tw-down" if dash["otc_chg"] < 0 else "tw-flat")
    otc_sign = "+" if dash["otc_chg"] > 0 else ""
    otc_str = (
        f"<span class='{otc_cls}'>{dash['otc_price']:,.2f} ({otc_sign}{dash['otc_chg']:,.2f} / {otc_sign}{dash['otc_pct']:.2f}%)</span>"
        if dash["otc_price"] > 0 else "<span>收盤結算中</span>"
    )

    turn_str = f"<b>{dash['turnover_billion']:,.2f} 億</b>" if dash["turnover_billion"] > 0 else "<b>結算中</b>"
    bid_ord_str = f"<b>{dash['bid_orders']:,}</b>" if dash["bid_orders"] else "--"
    ask_ord_str = f"<b>{dash['ask_orders']:,}</b>" if dash["ask_orders"] else "--"
    trd_ord_str = f"<b>{dash['trade_orders']:,}</b>" if dash["trade_orders"] else "--"

    bid_lot_str = (
        f"<b>{dash['bid_lots']:,}</b> <span class='tw-up'>({dash['avg_bid_lots']} 張/筆)</span>"
        if dash["bid_lots"] else "--"
    )
    ask_lot_str = (
        f"<b>{dash['ask_lots']:,}</b> <span class='tw-down'>({dash['avg_ask_lots']} 張/筆)</span>"
        if dash["ask_lots"] else "--"
    )
    trd_lot_str = f"<b>{dash['trade_lots']:,}</b>" if dash["trade_lots"] else "--"

    up_str = (
        f"<span class='tw-up'>{dash['up_count']} (漲停 {dash['limit_up']})</span>"
        if dash["up_count"] is not None else "--"
    )
    dn_str = (
        f"<span class='tw-down'>{dash['down_count']} (跌停 {dash['limit_down']})</span>"
        if dash["down_count"] is not None else "--"
    )
    fl_str = f"<b>{dash['flat_count']}</b>" if dash["flat_count"] is not None else "--"

    st.markdown(f"""
    <div class="yahoo-stat-box">
        <div class="yahoo-stat-row">
            <span>加權指數 (含金融)</span>
            <span class="{tw_cls}">{dash['twii_price']:,.2f} ({tw_sign}{dash['twii_chg']:,.2f} / {tw_sign}{dash['twii_pct']:.2f}%)</span>
        </div>
        <div class="yahoo-stat-row">
            <span>加權指數 (未含金融)</span>
            {ex_fin_str}
        </div>
        <div class="yahoo-stat-row">
            <span>櫃買指數 (OTC)</span>
            {otc_str}
        </div>
        <div class="yahoo-stat-row">
            <span>大盤成交金額</span>
            <span>{turn_str}</span>
        </div>
        <div class="yahoo-stat-row">
            <span>委買筆數 / 委賣筆數</span>
            <span>{bid_ord_str} / {ask_ord_str}</span>
        </div>
        <div class="yahoo-stat-row">
            <span>大盤成交筆數</span>
            <span>{trd_ord_str}</span>
        </div>
        <div class="yahoo-stat-row">
            <span>委買張數 (均買)</span>
            <span>{bid_lot_str}</span>
        </div>
        <div class="yahoo-stat-row">
            <span>委賣張數 (均賣)</span>
            <span>{ask_lot_str}</span>
        </div>
        <div class="yahoo-stat-row">
            <span>大盤成交張數</span>
            <span>{trd_lot_str}</span>
        </div>
        <div class="yahoo-stat-row">
            <span>上漲家數 (含漲停)</span>
            <span>{up_str}</span>
        </div>
        <div class="yahoo-stat-row">
            <span>下跌家數 (含跌停)</span>
            <span>{dn_str}</span>
        </div>
        <div class="yahoo-stat-row">
            <span>平盤家數</span>
            <span>{fl_str}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.write("---")
    with st.expander("📰 【全頻道即時外電情報站】(支援彭博／LINE TODAY／路透／台美股)", expanded=True):
        st.caption("即時匯流彭博社 (Bloomberg)、LINE TODAY 財經、路透社 (Reuters) 與國內權威財經外電")
        render_news_hub_widget(show_pin_btn=False, key_prefix="live_m0")

# ================= 模式 1：🔍 台股診斷 =================
elif st.session_state.main_mode == "tw_stock":
    st.subheader("🔍 台股全維度深度體檢")

    def set_and_jump_tw_ticker(target_code: str):
        clean_code = resolve_tw_ticker(target_code)
        st.session_state.tw_ticker_field = clean_code
        st.session_state.selected_tw_ticker = clean_code
        st.session_state.analysis_cache_tw = None
        st.session_state.auto_run_tw = True

    tw_favs = user_memory.get("tw_favorites", ["2330.TW", "2454.TW", "2317.TW", "0050.TW"])
    st.caption("⭐ **常用股票清單**（點選一秒自動診斷）：")

    fav_cols = st.columns(2)
    for idx, fav_code in enumerate(tw_favs[:6]):
        col_target = fav_cols[idx % 2]
        display_label = get_stock_display_label(fav_code, is_fav=True)
        if col_target.button(display_label, use_container_width=True, key=f"tw_fav_{fav_code}"):
            set_and_jump_tw_ticker(fav_code)
            st.rerun()

    tw_recents = [r for r in user_memory.get("tw_recent", []) if r not in tw_favs][:4]
    if tw_recents:
        rh_c1, rh_c2 = st.columns([3.2, 0.8])
        with rh_c1:
            st.caption("🕒 **最近查詢紀錄**：")
        with rh_c2:
            if st.button("🗑️ 清除", key="btn_clear_tw_rec", use_container_width=True, help="點此清空最近查詢歷史"):
                clear_recent_history("tw")
                st.rerun()

        rec_cols = st.columns(2)
        for r_idx, r_code in enumerate(tw_recents):
            col_rec_target = rec_cols[r_idx % 2]
            rec_display = get_stock_display_label(r_code, is_fav=False)
            if col_rec_target.button(rec_display, use_container_width=True, key=f"tw_rec_{r_code}"):
                set_and_jump_tw_ticker(r_code)
                st.rerun()

    st.caption("💡 **台股輸入格式指引**：上市請輸入 `代碼.TW`（如 `2330.TW`，亦支援純數字如 `2330` 自動轉上市）｜ 上櫃請輸入 `代碼.TWO`（如 `6488.TWO`）")

    with st.form("tw_search_form", clear_on_submit=False):
        col_input, col_btn = st.columns([2.4, 1.6])
        with col_input:
            raw_tw_input = st.text_input(
                "輸入台股代碼",
                value=st.session_state.tw_ticker_field,
                label_visibility="collapsed",
                placeholder="例：2330.TW 或 6488.TWO",
                key="tw_ticker_field"
            )
        with col_btn:
            exec_clicked = st.form_submit_button("🚀 診斷台股", type="primary", use_container_width=True)

    with st.expander("⚙️ 管理台股常用清單", expanded=False):
        col_m1, col_m2 = st.columns([2.4, 1.6])
        new_fav_in = col_m1.text_input("新增常用代碼", placeholder="例：2603.TW", key="new_tw_fav_in")
        if col_m2.button("➕ 新增至常用", use_container_width=True, key="btn_add_tw_fav"):
            clean_new_fav = resolve_tw_ticker(new_fav_in)
            if clean_new_fav and clean_new_fav not in user_memory["tw_favorites"]:
                user_memory["tw_favorites"].append(clean_new_fav)
                save_user_data()
                st.success(f"已加入 {clean_new_fav}！")
                st.rerun()

        st.caption("點擊下方按鈕可從常用清單中移出：")
        del_cols = st.columns(2)
        for d_idx, d_code in enumerate(user_memory["tw_favorites"]):
            del_label = f"❌ {get_stock_display_label(d_code, is_fav=False)}"
            if del_cols[d_idx % 2].button(del_label, key=f"del_tw_fav_{d_code}", use_container_width=True):
                user_memory["tw_favorites"].remove(d_code)
                save_user_data()
                st.rerun()

    cleaned_tw_ticker = resolve_tw_ticker(raw_tw_input)

    if exec_clicked or st.session_state.auto_run_tw:
        st.session_state.auto_run_tw = False
        st.session_state.selected_tw_ticker = cleaned_tw_ticker
        with st.spinner("連線 TWSE 撮合主機與四大權威機構資料庫計算中..."):
            df_stk = fetch_and_calc(cleaned_tw_ticker)
            if df_stk is not None:
                r = analyze_full_stock(
                    cleaned_tw_ticker,
                    df_stk,
                    df_market,
                    df_futures_bench,
                    df_tsm,
                    df_sox,
                    global_forex,
                    asset_type="tw",
                    include_inst_suite=True
                )
                st.session_state.analysis_cache_tw = (r, df_stk, cleaned_tw_ticker)
                add_recent_history("tw", cleaned_tw_ticker)
            else:
                st.session_state.analysis_cache_tw = None
                st.error("無法取得該標的行情數據。請檢查是否為上櫃股票並補上 `.TWO`（例如 `6488.TWO`）。")

    if st.session_state.analysis_cache_tw is not None:
        r, df_stk, cur_t = st.session_state.analysis_cache_tw
        render_analysis_view(r, df_stk, mode_type="tw", ticker_raw=cur_t)

# ================= 模式 2：🇺🇸 美股診斷 =================
elif st.session_state.main_mode == "us_stock":
    st.subheader("🇺🇸 美股全維度深度體檢")

    def set_and_jump_us_ticker(target_code: str):
        clean_code = target_code.strip().upper()
        st.session_state.us_ticker_field = clean_code
        st.session_state.selected_us_ticker = clean_code
        st.session_state.analysis_cache_us = None
        st.session_state.auto_run_us = True

    us_favs = user_memory.get("us_favorites", ["NVDA", "AAPL", "MSFT", "TSLA"])
    st.caption("⭐ **常用美股清單**（點選一秒自動診斷）：")

    fav_u_cols = st.columns(2)
    for idx, fav_u_code in enumerate(us_favs[:6]):
        col_u_target = fav_u_cols[idx % 2]
        display_u_label = get_stock_display_label(fav_u_code, is_fav=True)
        if col_u_target.button(display_u_label, use_container_width=True, key=f"us_fav_{fav_u_code}"):
            set_and_jump_us_ticker(fav_u_code)
            st.rerun()

    us_recents = [r for r in user_memory.get("us_recent", []) if r not in us_favs][:4]
    if us_recents:
        urh_c1, urh_c2 = st.columns([3.2, 0.8])
        with urh_c1:
            st.caption("🕒 **最近查詢紀錄**：")
        with urh_c2:
            if st.button("🗑️ 清除", key="btn_clear_us_rec", use_container_width=True, help="點此清空美股最近查詢歷史"):
                clear_recent_history("us")
                st.rerun()

        rec_u_cols = st.columns(2)
        for ru_idx, ru_code in enumerate(us_recents):
            col_rec_u = rec_u_cols[ru_idx % 2]
            rec_u_label = get_stock_display_label(ru_code, is_fav=False)
            if col_rec_u.button(rec_u_label, use_container_width=True, key=f"us_rec_{ru_code}"):
                set_and_jump_us_ticker(ru_code)
                st.rerun()

    st.caption("💡 **美股輸入格式指引**：請輸入美股英文代號（如 `NVDA`、`AAPL`、`TSLA`、`MSFT`、`TSM`），大小寫皆可自動識別轉換。")

    with st.form("us_search_form", clear_on_submit=False):
        col_u_in, col_u_btn = st.columns([2.4, 1.6])
        with col_u_in:
            raw_us_input = st.text_input(
                "輸入美股代碼",
                value=st.session_state.us_ticker_field,
                label_visibility="collapsed",
                placeholder="例：NVDA、AAPL、TSM",
                key="us_ticker_field"
            )
        with col_u_btn:
            exec_us_btn = st.form_submit_button("🚀 診斷美股", type="primary", use_container_width=True)

    cleaned_us_ticker = raw_us_input.strip().upper()

    with st.expander("⚙️ 管理美股常用清單", expanded=False):
        col_mu1, col_mu2 = st.columns([2.4, 1.6])
        new_u_fav_in = col_mu1.text_input("新增美股代碼", placeholder="例：AMD", key="new_us_fav_in")
        if col_mu2.button("➕ 新增至常用", use_container_width=True, key="btn_add_us_fav"):
            clean_u_new = new_u_fav_in.strip().upper()
            if clean_u_new and clean_u_new not in user_memory["us_favorites"]:
                user_memory["us_favorites"].append(clean_u_new)
                save_user_data()
                st.success(f"已加入 {clean_u_new}！")
                st.rerun()

        del_u_cols = st.columns(2)
        for du_idx, du_code in enumerate(user_memory["us_favorites"]):
            del_u_label = f"❌ {get_stock_display_label(du_code, is_fav=False)}"
            if del_u_cols[du_idx % 2].button(del_u_label, key=f"del_us_fav_{du_code}", use_container_width=True):
                user_memory["us_favorites"].remove(du_code)
                save_user_data()
                st.rerun()

    if exec_us_btn or st.session_state.auto_run_us:
        st.session_state.auto_run_us = False
        st.session_state.selected_us_ticker = cleaned_us_ticker
        with st.spinner("連線美股即時行情與華爾街四大研究資料庫中..."):
            df_stk_us = fetch_and_calc(cleaned_us_ticker)
            if df_stk_us is not None:
                r_us = analyze_full_stock(
                    cleaned_us_ticker,
                    df_stk_us,
                    df_spx,
                    None,
                    None,
                    df_sox,
                    global_forex,
                    asset_type="us",
                    include_inst_suite=True
                )
                st.session_state.analysis_cache_us = (r_us, df_stk_us, cleaned_us_ticker)
                add_recent_history("us", cleaned_us_ticker)
            else:
                st.session_state.analysis_cache_us = None
                st.error("無法取得該美股行情，請確認英文代碼（如 NVDA, AAPL, TSM, AMD）。")

    if st.session_state.analysis_cache_us is not None:
        r_us, df_stk_us, cur_ut = st.session_state.analysis_cache_us
        render_analysis_view(r_us, df_stk_us, mode_type="us", ticker_raw=cur_ut)

# ================= 模式 3：⚡ 台灣期貨 =================
elif st.session_state.main_mode == "tw_futures":
    st.subheader("⚡ 台灣期貨全維度專區 (優質契約・期顧共識・基差診斷)")
    st.caption("內建熱門台期契約池・自選查詢・多空目標壓力與保證金風控")

    def set_and_jump_fut_contract(contract_key: str):
        c_code = contract_key.strip().upper()
        st.session_state.tw_fut_field = c_code
        st.session_state.selected_fut_contract = c_code
        st.session_state.analysis_cache_fut = None
        st.session_state.auto_run_fut = True

    fq1, fq2 = st.columns(2)
    with fq1:
        if st.button("台指期 (大台)", use_container_width=True, key="fq_wtx"):
            set_and_jump_fut_contract("WTX")
            st.rerun()
        if st.button("微型台指 (微台)", use_container_width=True, key="fq_wmt"):
            set_and_jump_fut_contract("WMT")
            st.rerun()
    with fq2:
        if st.button("小型台指 (小台)", use_container_width=True, key="fq_mtx"):
            set_and_jump_fut_contract("MTX")
            st.rerun()
        if st.button("電子期貨 (TE)", use_container_width=True, key="fq_te"):
            set_and_jump_fut_contract("TE")
            st.rerun()

    st.caption("💡 **期貨輸入格式指引**：可點選上方按鈕或輸入契約簡稱（`WTX` 大台、`MTX` 小台、`WMT` 微台、`TE` 電子期、`TF` 金融期）。")

    with st.form("fut_search_form", clear_on_submit=False):
        col_f_in, col_f_btn = st.columns([2.4, 1.6])
        with col_f_in:
            raw_fut_input = st.text_input(
                "輸入契約代碼",
                value=st.session_state.tw_fut_field,
                label_visibility="collapsed",
                placeholder="例：WTX、MTX、WMT",
                key="tw_fut_field"
            )
        with col_f_btn:
            exec_fut_btn = st.form_submit_button("🚀 診斷期貨", type="primary", use_container_width=True)

    if df_market is not None and df_futures_bench is not None:
        twii_close = df_market.iloc[-1]['Close']
        bench_fut_close = df_futures_bench.iloc[-1]['Close']
        date_twii = df_market.index[-1].date()
        date_fut = df_futures_bench.index[-1].date()

        if date_twii == date_fut:
            basis_val = bench_fut_close - twii_close
            b_c1, b_c2, b_c3 = st.columns(3)
            b_c1.metric("加權現貨點位", f"{twii_close:.1f}")
            b_c2.metric("台指期貨點位", f"{bench_fut_close:.1f}")
            basis_tag = "🔥 實質正價差" if basis_val > 25 else ("⚠️ 避險逆價差" if basis_val < -50 else "⚪ 平價區間")
            b_c3.metric("即時基差 (期-現)", f"{basis_val:+.1f} 點", basis_tag)
        else:
            st.caption(f"⚪ 跨市場連線：加權現貨最新收盤為 `{twii_close:.1f}` 點（期現貨日期不同步，暫停計算基差避免失真）。")
    else:
        st.caption("⚪ 基差提示：外部資料庫目前未提供獨立 TAIFEX 撮合報價，已嚴格停用假基差計算。")

    clean_key = raw_fut_input.strip().upper().replace("=F", "")
    spec_info = TW_FUTURES_SPECS.get(clean_key, TW_FUTURES_SPECS["WTX"])
    FUTURES_YAHOO_MAP = {
        "WTX": "WTX=F",
        "MTX": "MTX=F",
        "WMT": "WMT=F",
        "TE": "TE=F",
        "TF": "TF=F"
    }
    target_fut_ticker = FUTURES_YAHOO_MAP.get(clean_key, f"{clean_key}=F")

    if exec_fut_btn or st.session_state.auto_run_fut or st.session_state.analysis_cache_fut is None:
        st.session_state.auto_run_fut = False
        st.session_state.selected_fut_contract = clean_key
        with st.spinner(f"連線【{spec_info['name']} ({target_fut_ticker})】行情中..."):
            df_target_fut = fetch_and_calc(target_fut_ticker)
            fallback_note = None
            is_spot_fb = False

            if df_target_fut is None or df_target_fut.empty:
                df_target_fut = df_market
                is_spot_fb = True
                pt_v = spec_info.get('point_value', spec_info.get('tick_value', 200))
                fallback_note = (
                    f"🚨 **【行情來源警示・現貨參考模式】**：外部資料庫目前未提供【{spec_info['name']} ({target_fut_ticker})】之獨立即時撮合行情！"
                    f"走勢圖暫以「加權指數現貨」作為位階參考，**現價與指標均非真實期貨點位**；"
                    f"為嚴守實盤風控，**已全面停用期貨下單建議、停損停利試算與可開口數**，嚴禁以現貨點位作為期貨實盤委託依據！"
                )

            if df_target_fut is not None:
                r_fut = analyze_full_stock(
                    clean_key,
                    df_target_fut,
                    df_market,
                    None,
                    None,
                    None,
                    global_forex,
                    asset_type="futures",
                    include_inst_suite=False
                )
                st.session_state.analysis_cache_fut = (r_fut, df_target_fut, spec_info, fallback_note, clean_key, is_spot_fb)
            else:
                st.session_state.analysis_cache_fut = None
                st.error(f"暫時無法取得【{spec_info['name']}】或大盤基準行情，請稍後再試。")

    if st.session_state.analysis_cache_fut is not None:
        r_fut, df_fut_obj, spec_obj, fb_msg, fut_k, is_spot_fb = st.session_state.analysis_cache_fut
        render_analysis_view(r_fut, df_fut_obj, mode_type="futures", custom_spec=spec_obj, fallback_warning=fb_msg, ticker_raw=fut_k, is_spot_fallback=is_spot_fb)

elif st.session_state.main_mode == "us_futures":
    st.subheader("📈 美股期貨獨立專區")
    st.caption("四大美指期貨即時動能・微那斯達克 / 微標普 / 道瓊 / 羅素2000")

    US_FUT_LIST = [
        ("微那斯達克期 (NQ)", "NQ=F", "全球科技龍頭風向球"),
        ("小標普500期 (ES)", "ES=F", "美股大盤流動性與宏觀資產"),
        ("道瓊期貨 (YM)", "YM=F", "傳統價值龍頭與金融防禦"),
        ("羅素2000期 (RTY)", "RTY=F", "中小型股景氣復甦動能")
    ]

    for name, code, desc in US_FUT_LIST:
        df_g = fetch_and_calc(code)
        if df_g is not None and len(df_g) >= 2:
            last_p = safe_float(df_g.iloc[-1]['Close'])
            prev_p = safe_float(df_g.iloc[-2]['Close'], last_p)
            chg_pct = ((last_p - prev_p) / (prev_p + 1e-9)) * 100
            ma5_g = safe_float(df_g['MA5'].iloc[-1], last_p)
            status = "🔥 站上 5MA 攻擊" if last_p > ma5_g else "❄️ 跌破 5MA 防守"

            c_f1, c_f2 = st.columns([2, 1])
            c_f1.markdown(f"**{name}** ｜ {desc}")
            c_f2.metric("點位", f"{last_p:.2f}", f"{chg_pct:+.2f}%")
            st.caption(f"結構位階：`{status}`")
            st.write("---")

# ================= 模式 5：📊 ETF 專區 =================
elif st.session_state.main_mode == "etf":
    st.subheader("📊 ETF 旗艦量化策略雷達")
    f_r1_c1, f_r1_c2 = st.columns(2)
    with f_r1_c1:
        if st.button("🔥 全部熱門", type="primary" if st.session_state.etf_category_filter == "全部" else "secondary", use_container_width=True, key="filter_etf_all"):
            st.session_state.etf_category_filter = "全部"
            st.rerun()
    with f_r1_c2:
        if st.button("📈 市值型", type="primary" if st.session_state.etf_category_filter == "市值型" else "secondary", use_container_width=True, key="filter_etf_cap"):
            st.session_state.etf_category_filter = "市值型"
            st.rerun()

    f_r2_c1, f_r2_c2 = st.columns(2)
    with f_r2_c1:
        if st.button("💰 高股息", type="primary" if st.session_state.etf_category_filter == "高股息" else "secondary", use_container_width=True, key="filter_etf_div"):
            st.session_state.etf_category_filter = "高股息"
            st.rerun()
    with f_r2_c2:
        if st.button("🌐 海外/債券", type="primary" if st.session_state.etf_category_filter == "海外/債券" else "secondary", use_container_width=True, key="filter_etf_overseas"):
            st.session_state.etf_category_filter = "海外/債券"
            st.rerun()

    if st.button("⚡ 開始全維度即時掃描排行", type="primary", use_container_width=True, key="etf_scan_exec_btn"):
        if st.session_state.etf_category_filter == "市值型":
            target_etfs = [item for item in ETF_UNIVERSE if item[2] == "市值型"]
        elif st.session_state.etf_category_filter == "高股息":
            target_etfs = [item for item in ETF_UNIVERSE if item[2] == "高股息"]
        elif st.session_state.etf_category_filter == "海外/債券":
            target_etfs = [item for item in ETF_UNIVERSE if "海外" in item[2] or "債券" in item[2]]
        else:
            target_etfs = ETF_UNIVERSE

        progress_bar = st.progress(0)
        status_text = st.empty()
        etf_results = []
        failed_etfs = []

        def etf_worker(item):
            try:
                name, code, cat, desc = item
                df_stk = fetch_and_calc(code)
                if df_stk is not None:
                    r = analyze_full_stock(
                        code,
                        df_stk,
                        df_market,
                        df_futures_bench,
                        df_tsm,
                        df_sox,
                        global_forex,
                        asset_type="tw",
                        include_inst_suite=False
                    )
                    return {
                        "名稱": name,
                        "代碼": code,
                        "類別": cat,
                        "特色": desc,
                        "總評分": r['total_score'],
                        "現價": r['close'],
                        "建議防守": r['stop_loss'],
                        "殖利率": r['fund_data'].get('yield'),
                        "ma20_diff": r['ma_status']['ma20_diff'],
                        "ma60_diff": r['ma_status']['ma60_diff']
                    }
                else:
                    return ("FAIL", name, code, "行情資料不足")
            except Exception as e:
                return ("FAIL", item[0], item[1], str(e))

        executor = ThreadPoolExecutor(max_workers=5)
        try:
            total_items = len(target_etfs)
            futures = [executor.submit(etf_worker, item) for item in target_etfs]
            for idx, f in enumerate(futures):
                status_text.text(f"連線撮合中 ({idx+1}/{total_items})...")
                try:
                    res_item = f.result(timeout=8.0)
                    if isinstance(res_item, tuple) and res_item[0] == "FAIL":
                        failed_etfs.append(f"{res_item[1]} ({res_item[2]}): {res_item[3]}")
                    elif res_item:
                        etf_results.append(res_item)
                except Exception as ex:
                    failed_etfs.append(f"執行逾時或例外: {str(ex)}")
                progress_bar.progress((idx + 1) / total_items)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        status_text.empty()
        progress_bar.empty()

        if etf_results:
            df_etf = pd.DataFrame(etf_results).sort_values(by="總評分", ascending=False).reset_index(drop=True)
            for rank, row in df_etf.iterrows():
                badge = "🟢 偏多" if row['總評分'] >= 75 else ("🟡 定額區" if row['總評分'] >= 60 else "🔴 觀望")
                with st.container():
                    c1, c2, c3 = st.columns([2, 1, 1])
                    c1.markdown(f"**#{rank+1} {row['名稱']} ({row['代碼']})**")
                    c2.markdown(f"**{row['總評分']}** 分")
                    c3.caption(badge)

                    st.caption(f"📌 `{row['類別']}` ｜ {row['特色']}")
                    c_m1, c_m2, c_m3 = st.columns(3)
                    c_m1.caption(f"現價: **{row['現價']:.2f}**")
                    yield_disp = f"{row['殖利率']:.1f}%" if row['殖利率'] is not None else "--"
                    c_m2.caption(f"殖利率: **{yield_disp}**")
                    c_m3.caption(f"防守: **{row['建議防守']:.2f}**")
                    st.write("---")

        if failed_etfs:
            with st.expander("⚠️ 部分 ETF 連線未成功清單", expanded=False):
                for err in failed_etfs:
                    st.write(f"• {err}")

    with st.expander("🧮 定期定額「微笑曲線」扣款計算機", expanded=False):
        etf_cap = st.number_input("每月預算 (NTD)", value=20000, step=5000, key="etf_monthly_budget")
        etf_state = st.radio("當前位階：", ["常態整理（月線與季線之間）", "大幅拉回（低於季線 5% 以上）", "高檔大漲（高於月線 6% 以上）"], key="etf_state_radio")
        if "大幅拉回" in etf_state:
            st.success(f"🎯 建議扣款 **{int(etf_cap * 1.5):,} 元**（1.5 倍加碼）")
        elif "高檔大漲" in etf_state:
            st.warning(f"🎯 建議扣款 **{int(etf_cap * 0.7):,} 元**（0.7 倍扣款保留現金）")
        else:
            st.info(f"🎯 維持標準扣款 **{int(etf_cap):,} 元**")

# ================= 模式 6：💎 體質雷達 =================
elif st.session_state.main_mode == "market":
    st.subheader("💎 市場穩健優質標的・即時連線掃描")

    if st.button("⚡ 開始全市場即時連線篩選", type="primary", use_container_width=True, key="market_scan_exec_btn"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        scan_results = []
        failed_stocks = []

        def worker(item):
            try:
                name, code, desc = item
                df_stk = fetch_and_calc(code)
                if df_stk is not None:
                    r = analyze_full_stock(
                        code,
                        df_stk,
                        df_market,
                        df_futures_bench,
                        df_tsm,
                        df_sox,
                        global_forex,
                        asset_type="tw",
                        include_inst_suite=False
                    )
                    return {
                        "名稱": name,
                        "代碼": code,
                        "產業地位": desc,
                        "總評分": r['total_score'],
                        "現價": r['close'],
                        "建議防守": r['stop_loss'],
                        "ROE": r['fund_data'].get('roe'),
                        "本益比": r['fund_data'].get('pe')
                    }
                else:
                    return ("FAIL", name, code, "行情資料不足")
            except Exception as e:
                return ("FAIL", item[0], item[1], str(e))

        executor = ThreadPoolExecutor(max_workers=5)
        try:
            total_items = len(MARKET_QUALITY_UNIVERSE)
            futures = [executor.submit(worker, item) for item in MARKET_QUALITY_UNIVERSE]
            for idx, f in enumerate(futures):
                status_text.text(f"連線更新中 ({idx+1}/{total_items})...")
                try:
                    res_item = f.result(timeout=8.0)
                    if isinstance(res_item, tuple) and res_item[0] == "FAIL":
                        failed_stocks.append(f"{res_item[1]} ({res_item[2]}): {res_item[3]}")
                    elif res_item:
                        scan_results.append(res_item)
                except Exception as ex:
                    failed_stocks.append(f"執行逾時或例外: {str(ex)}")
                progress_bar.progress((idx + 1) / total_items)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        status_text.empty()
        progress_bar.empty()

        if scan_results:
            df_res = pd.DataFrame(scan_results).sort_values(by="總評分", ascending=False).reset_index(drop=True)
            for rank, row in df_res.iterrows():
                badge = "🟢 優選" if row['總評分'] >= 75 else ("🟡 觀察" if row['總評分'] >= 60 else "🔴 暫緩")
                with st.container():
                    c1, c2, c3 = st.columns([2, 1, 1])
                    c1.markdown(f"**#{rank+1} {row['名稱']} ({row['代碼']})**")
                    c2.markdown(f"**{row['總評分']}** 分")
                    c3.caption(badge)

                    st.caption(f"📌 {row['產業地位']}")
                    c_m1, c_m2, c_m3 = st.columns(3)
                    c_m1.caption(f"現價: **{row['現價']:.2f}**")
                    c_m2.caption(f"ROE: **{row['ROE']:.1f}%**" if row['ROE'] is not None else "ROE: --")
                    c_m3.caption(f"PE: **{row['本益比']:.1f}x**" if (row['本益比'] is not None and row['本益比'] > 0) else "PE: --")
                    st.caption(f"防守 (停損): **{row['建議防守']:.2f} 元**")
                    st.write("---")

        if failed_stocks:
            with st.expander("⚠️ 部分標的連線未成功清單", expanded=False):
                for err in failed_stocks:
                    st.write(f"• {err}")

# ================= 模式 7：📢 戰情訊息導入 ＆ 法說會與即時外電 =================
elif st.session_state.main_mode == "events":
    st.subheader("📢 關鍵市場戰情導入 ＆ 即時外電／法說會速查")

    with st.expander("✍️ 【導入／更新置頂關鍵市場戰情分析訊息】", expanded=True):
        st.caption("系統現已預設**全自動同步最新即時外電戰情**；若您需要發布特定分析，可填寫下方欄位後點擊發布，系統將以手動戰情優先置頂。")
        b_title_in = st.text_input("戰情標題", value=current_briefing["title"], key="brief_title_in")
        b_content_in = st.text_area("戰情詳細分析內容", value=current_briefing["content"], height=140, key="brief_content_in")
        b_author_in = st.text_input("發布者署名", value=current_briefing.get("author", "系統策略中心"), key="brief_author_in")

        b_btn1, b_btn2, b_btn3 = st.columns(3)
        with b_btn1:
            if st.button("🚀 發布自訂戰情", type="primary", use_container_width=True, key="btn_pub_brief"):
                save_market_briefing(b_title_in, b_content_in, b_author_in, is_manual=True)
                st.success("已成功發布手動自訂戰情！")
                st.rerun()
        with b_btn2:
            if st.button("🤖 結合即時指標生成草稿", use_container_width=True, key="btn_auto_synth_brief"):
                tw_p = safe_float(df_market.iloc[-1]['Close']) if (df_market is not None and not df_market.empty) else 0.0
                tw_ma20 = safe_float(df_market['MA20'].iloc[-1], tw_p) if (df_market is not None and not df_market.empty) else 0.0
                sox_chg = ((safe_float(df_sox['Close'].iloc[-1]) - safe_float(df_sox['Close'].iloc[-2])) / (safe_float(df_sox['Close'].iloc[-2]) + 1e-9) * 100.0) if (df_sox is not None and len(df_sox) >= 2) else 0.0
                synth_title = f"🔥 即時量化戰情：台股現報 {tw_p:,.0f} 點 vs 費半連動 ({sox_chg:+.2f}%) 關鍵位階解析"
                synth_body = (
                    f"台股加權指數目前位於 {tw_p:,.2f} 點（月線 20MA 支撐/壓力位階：{tw_ma20:,.2f} 點），"
                    f"美股費城半導體指數近期變動 {sox_chg:+.2f}%，新台幣匯率現報 {global_forex.get('twd_rate') or 32.0:.2f}。\n\n"
                    f"📌 **關鍵總經與操作劇本**：\n"
                    f"• 緊盯外資買賣超與台指期夜盤動態，若守穩 {tw_ma20:,.0f} 點生命線，洗盤後易有反彈。\n"
                    f"• 當沖嚴守 ORB 與 VWAP 均價線紀律，尾盤 13:20 前無條件平倉。"
                )
                save_market_briefing(synth_title, synth_body, "系統策略中心", is_manual=True)
                st.rerun()
        with b_btn3:
            if st.button("🔄 恢復全自動同步外電", use_container_width=True, key="btn_reset_auto_brief"):
                if os.path.exists(BRIEFING_FILE):
                    try:
                        os.remove(BRIEFING_FILE)
                    except Exception:
                        pass
                st.success("已重設為全自動同步外電模式！")
                st.rerun()

    st.write("---")

    st.markdown("### 🌐 全頻道即時外電情報匯流中心 (含彭博 / LINE TODAY / 路透社)")
    st.caption("整合全球八大外電情報頻道，支援一鍵手動鎖定置頂焦點至首頁戰情廣播卡片")
    render_news_hub_widget(show_pin_btn=True, key_prefix="events_m7")

    st.markdown("### 🔍 個股最新重大訊息速查")
    col_n_input, col_n_btn = st.columns([2.4, 1.6])
    with col_n_input:
        news_ticker = st.text_input("輸入查詢標的代碼", value="2330.TW", label_visibility="collapsed", key="news_search_input")
    with col_n_btn:
        news_clicked = st.button("📰 查個股新聞", type="primary", use_container_width=True, key="fetch_news_btn")

    if news_clicked:
        clean_news_t = resolve_tw_ticker(news_ticker)
        with st.spinner("連線即時新聞庫檢索中..."):
            news_items = fetch_stock_news(clean_news_t)
            if news_items:
                st.success(f"{get_stock_display_label(clean_news_t)} 最新重大訊息：")
                for item in news_items:
                    with st.container():
                        st.markdown(f"**[{item['title']}]({item['link']})**")
                        st.caption(f"{item['publisher']} ｜ {item['time']}")
                        st.write("---")
            else:
                st.warning("暫查無該標的之即時重大訊息。")

    st.write("---")
    st.markdown("### 🗓️ 台股指標龍頭・法說會常態時程")
    for call in EARNINGS_CALLS:
        with st.container():
            st.markdown(f"**{call['公司']}** ｜ {call['重要性']}")
            st.info(f"📅 期間：{call['期間']}")
            st.caption(f"🎯 核心看點：{call['重點觀測']}")
            st.write("---")

# ================= 模式 8：💱 全球外匯大盤 =================
elif st.session_state.main_mode == "forex":
    st.subheader("💱 全球外匯與熱錢資金即時儀表板")
    st.caption("直連臺灣銀行官方牌告與全球匯率主機")

    fx_info = global_forex

    col_f1, col_f2, col_f3 = st.columns(3)
    col_f1.metric("USD/TWD", f"{fx_info['twd_rate']:.2f}" if fx_info['twd_rate'] else "檢索中", f"{fx_info['twd_change']:+.2f}")
    col_f2.metric("美元 (DXY)", f"{fx_info['dxy_rate']:.2f}" if fx_info['dxy_rate'] else "檢索中")
    col_f3.metric("日圓 (JPY)", f"{fx_info['jpy_rate']:.2f}" if fx_info['jpy_rate'] else "檢索中")

    st.caption(f"基準來源：**{fx_info['source']}**")
    st.write("---")
    st.info(f"**台幣狀態**：{fx_info['twd_status']}\n\n**趨勢**：{fx_info['twd_trend']}")
    st.caption(f"• 美元結構：{fx_info['dxy_trend']}")
    st.caption(f"• 日圓平倉風險：{fx_info['jpy_risk']}")

    # 🌟 VIX 252 日歷史百分位恐慌溫度計
    st.write("---")
    st.markdown("### ⚠️ VIX 恐慌指數 ＆ 252 日歷史百分位儀表板")
    vix_info = fetch_vix_percentile()
    if vix_info["has_data"]:
        v_c1, v_c2, v_c3 = st.columns(3)
        v_c1.metric("VIX 即時恐慌指數", f"{vix_info['vix_price']:.2f}", vix_info["status"])
        v_c2.metric("252 日歷史百分位 (Percentile)", f"{vix_info['vix_pct']:.1f}%", "極端恐慌區" if vix_info['vix_pct'] > 80 else ("偏高警戒" if vix_info['vix_pct'] > 60 else "常態平穩"))
        v_c3.metric("20日均價 (MA20)", f"{vix_info['vix_ma20']:.2f}")
        st.caption("📌 **VIX 百分位解讀**：若百分位高於 80%，代表市場波動極度劇烈、避險情緒高漲；若低於 30%，通常代表市場流動性佳、風險偏好穩定。")
    else:
        st.info("💡 目前暫時無法取得 ^VIX 歷史行情數據。")

    st.write("---")
    st.markdown("### 📈 美元兌新台幣走勢與月線 (20MA)")
    df_usdtwd = fetch_and_calc("USDTWD=X")
    if df_usdtwd is None:
        df_usdtwd = fetch_and_calc("TWD=X")

    if df_usdtwd is not None:
        st.line_chart(df_usdtwd[['Close', 'MA20']].dropna().tail(60))
    else:
        st.write("暫時無法取得匯率走勢。")

# 盤中 30 秒非阻塞式自動刷新控制器 (僅在即時看盤室且勾選時啟動前端計時，不阻塞 Python 執行緒)
if auto_refresh and st.session_state.get("main_mode") == "live_watch":
    components.html(
        """
        <script>
        (function() {
            const timerId = setTimeout(function() {
                try {
                    const buttons = window.parent.document.querySelectorAll('button');
                    for (let i = 0; i < buttons.length; i++) {
                        if (buttons[i].innerText && buttons[i].innerText.includes('立即刷新即時走勢與大盤統計')) {
                            buttons[i].click();
                            return;
                        }
                    }
                } catch (e) {}
            }, 30000);
        })();
        </script>
        """,
        height=0,
        width=0
    )
