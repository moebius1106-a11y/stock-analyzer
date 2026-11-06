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

# 手機端直覺觸控與雙欄排版強制 CSS（已解鎖圖表橫向自由滑動，並防止指標擠壓）
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

    @media (max-width: 768px) {
        div[data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 0.4rem !important;
            width: 100% !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
        }
        div[data-testid="stColumn"], div[data-testid="column"] {
            flex: 1 1 calc(50% - 0.4rem) !important;
            min-width: calc(50% - 0.4rem) !important;
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

    /* 走勢圖支援手機橫向順暢滑動 (Scrollable Chart Wrapper) */
    .chart-scroll-box, div[data-testid="stVegaLiteChart"] {
        overflow-x: auto !important;
        overflow-y: hidden !important;
        -webkit-overflow-scrolling: touch !important;
        touch-action: pan-x !important;
        width: 100% !important;
        display: block !important;
        padding-bottom: 6px;
    }
    .chart-scroll-box::-webkit-scrollbar {
        height: 5px;
    }
    .chart-scroll-box::-webkit-scrollbar-thumb {
        background: rgba(128, 128, 128, 0.3);
        border-radius: 4px;
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

@st.cache_data(ttl=180)
def fetch_live_macro_rss(query_str: str = "台股 OR 美股 OR CPI OR 聯準會 OR 台積電 OR 費半"):
    encoded_q = quote(query_str)
    url = f"https://news.google.com/rss/search?q={encoded_q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    items = []
    try:
        r = requests.get(url, headers=headers, timeout=(2.0, 3.5))
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            for item in root.findall("./channel/item")[:8]:
                title = item.findtext("title", default="無標題")
                link = item.findtext("link", default="#")
                pub_date = item.findtext("pubDate", default="")
                source_el = item.find("source")
                source_name = source_el.text if source_el is not None else "財經快訊"
                items.append({
                    "title": title,
                    "link": link,
                    "source": source_name,
                    "pub_date": pub_date[:22] if pub_date else "即時"
                })
    except Exception:
        pass
    return items

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

# ----------------- 美股夜盤與核心指標即時監控模組 (徹底修復手機卡片擠壓問題) -----------------
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

def render_us_live_dashboard():
    """渲染美股夜盤與即時指標卡片看板（自適應雙欄，完全不擠壓）"""
    with st.expander("🌐 【美股大盤、ADR 與三大關鍵指標即時監控】", expanded=True):
        col_hdr1, col_hdr2 = st.columns([2.8, 1.2])
        with col_hdr1:
            st.caption("即時連線：台積電 ADR (TSM)、費半 (SOXX)、輝達 (NVDA)、那指期貨 (NQ) 與 10 年美債殖利率")
        with col_hdr2:
            if st.button("🔄 刷新美股", key="btn_refresh_us_live", use_container_width=True):
                fetch_us_live_indicators.clear()
                st.rerun()

        us_data = fetch_us_live_indicators()
        if us_data:
            # 採用 2 欄成組排版，在手機端給予寬裕空間，徹底杜絕文字被截成省略號
            for idx in range(0, len(us_data), 2):
                pair = us_data[idx:idx+2]
                cols = st.columns(2)
                for c_target, item in zip(cols, pair):
                    val_str = f"{item['price']:.2f}%" if item["unit"] == "%" else f"{item['unit']}{item['price']:,.2f}"
                    sign = "+" if item['diff'] >= 0 else ""
                    c_target.metric(
                        label=f"{item['label']} ({item['symbol']})",
                        value=val_str,
                        delta=f"{sign}{item['diff']:.2f} ({sign}{item['pct']:.2f}%)"
                    )
            
            tsm = next((x for x in us_data if x["symbol"] == "TSM"), None)
            if tsm:
                if tsm["price"] >= 370.0:
                    st.success(f"✅ **台積電 ADR 現報 ${tsm['price']:.2f}**：成功守穩 **370 美元** 多方防線！下週一金管會限空令（借券上限 3%）生效，外資面臨強迫軋空回補。")
                else:
                    st.warning(f"⚠️ **台積電 ADR 現報 ${tsm['price']:.2f}**：跌破 370 美元防線，下週一開盤啟動千點內政策防禦機制。")
        else:
            st.info("⚪ 目前外部美股撮合連線中，請稍候或點擊右上角刷新。")

# ----------------- 分時走勢核心渲染器 (修復手機右側截斷與解鎖向右滑動) -----------------
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

    st.caption("👉 **手機操作提示**：走勢圖支援以手指**向左／向右滑動**，完整檢視由開盤至最新分鐘的完整 K 線與均價！")

    min_y = min(low_p, y_close)
    max_y = max(high_p, y_close)
    pad = max((max_y - min_y) * 0.15, y_close * 0.002)
    y_domain = [min_y - pad, max_y + pad]

    # 動態計算足夠寬度，避免時間軸擠壓並賦予手機自由左右滑動的空間
    dynamic_chart_width = max(len(df_intra) * 7, 560)

    base = alt.Chart(df_intra).encode(
        x=alt.X('TimeStr:O', title=None, axis=alt.Axis(labelAngle=0, labelOverlap=True, tickCount=8))
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

    top_chart = (price_line + vwap_line + ref_rule).properties(height=210, width=dynamic_chart_width)

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
    ).properties(height=65, width=dynamic_chart_width)

    combined_chart = alt.vconcat(top_chart, vol_bars).resolve_scale(x='shared').configure_view(strokeOpacity=0.15)
    
    # 關閉強制鎖死寬度，讓圖表在 scroll 容器內隨意橫向手指滑動
    st.altair_chart(combined_chart, use_container_width=False)