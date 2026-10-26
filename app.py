import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import altair as alt
import requests
import xml.etree.ElementTree as ET
import math
import json
import os
import time
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
        box-sizing: border-box !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.84rem !important;
        font-weight: 600 !important;
        white-space: normal !important;
        word-break: break-all !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.15rem !important;
        font-weight: 700 !important;
        white-space: normal !important;
        word-break: break-all !important;
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
        "last_active": datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M")
    }

def get_user_data():
    if "user_data" not in st.session_state:
        default_s = get_default_settings()
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        for k, v in default_s.items():
                            if k not in loaded:
                                loaded[k] = v
                        st.session_state.user_data = loaded
                        return st.session_state.user_data
            except Exception:
                pass
        st.session_state.user_data = default_s
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
    "title": "🔥 關鍵戰情焦點：台股整數關卡攻防 vs 總經籌碼動向",
    "content": (
        "台股短線處於技術面整理與洗盤期，多空交戰核心在於外資籌碼動向與美股科技股財報展望。\n\n"
        "📌 **操作應變劇本**：\n"
        "• 指數守穩月線 (20MA) 偏多輪動操作；跌破月線則保留現金水位並嚴守停損。\n"
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
        r = requests.get(url, headers=headers, timeout=3.5)
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
        ex.shutdown(wait=False)
        return data
    except Exception:
        ex.shutdown(wait=False)
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
        ex.shutdown(wait=False)
        return res
    except Exception:
        ex.shutdown(wait=False)
        return None

def fetch_twse_realtime(ticker: str):
    code, market = normalize_ticker(ticker)
    if market in ("us", "futures"):
        return None

    ex_ch = f"{market}_{code}.tw"
    url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={ex_ch}&json=1&delay=0"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        resp = requests.get(url, headers=headers, timeout=2.5)
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
        r_idx = session.get(idx_url, headers=headers, timeout=2.5)
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
        r_stat = session.get(stat_url, headers=headers, timeout=2.5)
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
        df_plot['VolLots'] = np.where(df_plot['Volume'] > 10000, df_plot['Volume'] / 1000.0, df_plot['Volume'])

        tp = (df_plot['High'] + df_plot['Low'] + df_plot['Close']) / 3.0
        cum_tp_vol = (tp * df_plot['Volume']).cumsum()
        cum_vol = df_plot['Volume'].cumsum()
        df_plot['VWAP'] = np.where(cum_vol > 0, cum_tp_vol / cum_vol, df_plot['Close'])

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
    orb_window = df_intra.head(15)
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

    top_chart = (price_line + vwap_line + ref_rule).properties(height=210)

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
    ).properties(height=65)

    combined_chart = alt.vconcat(top_chart, vol_bars).resolve_scale(x='shared').configure_view(strokeOpacity=0.15)
    st.altair_chart(combined_chart, use_container_width=True)

# ================= 模組共用渲染器 =================
def render_analysis_view(res, df_asset, mode_type="tw", custom_spec=None, fallback_warning=None, ticker_raw=None):
    is_downtrend = res.get('is_breakdown', False) or (res['close'] < res['ma_status']['ma20_val'])
    close = safe_float(res.get('close', 0.0))
    if close <= 0:
        close = 1.0

    risk_unit = max(close - safe_float(res.get('stop_loss', 0.0)), close * 0.015)
    target_1 = close + (1.5 * risk_unit)
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

    # ★★★ 當沖實戰決策室 (台股專屬・手機響應式完全適配版) ★★★
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

            # ★ 手機版完美適配：CDP 價格階梯看板（告別欄位擠壓與數值省略號）
            if cdp_info:
                st.markdown("##### 📏 今日 CDP 逆勢五大關鍵價（依前一交易日日K計算）")
                cdp_ladder_html = f"""
                <div style="background: rgba(128,128,128,0.06); border: 1px solid rgba(128,128,128,0.22); border-radius: 12px; padding: 8px 12px; margin: 6px 0 10px 0;">
                    <div style="display:flex; justify-content:space-between; align-items:center; padding: 6px 0; border-bottom: 1px dashed rgba(128,128,128,0.2);">
                        <span style="background: rgba(229,57,53,0.16); color: #e53935; font-weight: 700; padding: 2px 8px; border-radius: 6px; font-size: 0.85rem;">AH 最高阻力</span>
                        <b style="color: #e53935; font-size: 1.15rem;">{cdp_info['AH']:,.2f}</b>
                        <span style="color: #888; font-size: 0.78rem;">極限超買 / 追高警戒</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; padding: 6px 0; border-bottom: 1px dashed rgba(128,128,128,0.2);">
                        <span style="background: rgba(255,152,0,0.16); color: #f57c00; font-weight: 700; padding: 2px 8px; border-radius: 6px; font-size: 0.85rem;">NH 次高阻力</span>
                        <b style="color: #f57c00; font-size: 1.15rem;">{cdp_info['NH']:,.2f}</b>
                        <span style="color: #888; font-size: 0.78rem;">多單停利 / 波段壓力</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; padding: 6px 0; border-bottom: 1px dashed rgba(128,128,128,0.2);">
                        <span style="background: rgba(26,115,232,0.16); color: #1a73e8; font-weight: 700; padding: 2px 8px; border-radius: 6px; font-size: 0.85rem;">CDP 多空平衡</span>
                        <b style="color: #1a73e8; font-size: 1.15rem;">{cdp_info['CDP']:,.2f}</b>
                        <span style="color: #888; font-size: 0.78rem;">今日強弱分水嶺軸心</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; padding: 6px 0; border-bottom: 1px dashed rgba(128,128,128,0.2);">
                        <span style="background: rgba(67,160,71,0.16); color: #43a047; font-weight: 700; padding: 2px 8px; border-radius: 6px; font-size: 0.85rem;">NL 次低支撐</span>
                        <b style="color: #43a047; font-size: 1.15rem;">{cdp_info['NL']:,.2f}</b>
                        <span style="color: #888; font-size: 0.78rem;">空單回補 / 拉回承接</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; padding: 6px 0;">
                        <span style="background: rgba(46,125,50,0.16); color: #2e7d32; font-weight: 700; padding: 2px 8px; border-radius: 6px; font-size: 0.85rem;">AL 最低支撐</span>
                        <b style="color: #2e7d32; font-size: 1.15rem;">{cdp_info['AL']:,.2f}</b>
                        <span style="color: #888; font-size: 0.78rem;">超跌防守 / 破底警戒</span>
                    </div>
                </div>
                """
                st.markdown(cdp_ladder_html, unsafe_allow_html=True)

            # ★ 手機版完美適配：現股當沖損益與保本跳動計算機（2×2 矩陣看板）
            st.markdown("##### 🧮 現股當沖損益與保本跳動檔位計算機")
            calc_c1, calc_c2 = st.columns(2)
            with calc_c1:
                dt_shares_lot = st.number_input("當沖進場張數 (張)", min_value=1, max_value=500, value=1, step=1, key=f"dt_lots_{stable_key_suffix}")
            with calc_c2:
                saved_disc = float(user_memory.get("daytrade_fee_discount", 0.28))
                dt_discount = st.number_input("券商折讓 (如0.28)", min_value=0.10, max_value=1.00, value=saved_disc, step=0.01, key=f"dt_disc_{stable_key_suffix}")

            needed_ticks, tick_sz, cost_1lot, profit_1tick = calc_daytrade_breakeven(close, dt_discount)
            total_cost_lots = cost_1lot * dt_shares_lot
            total_1tick_profit = profit_1tick * dt_shares_lot
            net_profit_1tick = total_1tick_profit - total_cost_lots

            net_color = "#e53935" if net_profit_1tick > 0 else "#43a047"
            calc_grid_html = f"""
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; margin: 8px 0 10px 0;">
                <div style="background: rgba(128,128,128,0.06); border: 1px solid rgba(128,128,128,0.2); border-radius: 10px; padding: 7px 10px;">
                    <div style="font-size:0.78rem; color:#777;">每檔跳動金額 (Tick)</div>
                    <div style="font-size:1.15rem; font-weight:800; color:#1a73e8;">{tick_sz:.2f} 元/股</div>
                    <div style="font-size:0.75rem; color:#888;">跳動 1 檔 = {int(profit_1tick * dt_shares_lot):,} 元</div>
                </div>
                <div style="background: rgba(128,128,128,0.06); border: 1px solid rgba(128,128,128,0.2); border-radius: 10px; padding: 7px 10px;">
                    <div style="font-size:0.78rem; color:#777;">損益兩平跳動檔位</div>
                    <div style="font-size:1.15rem; font-weight:800; color:#e53935;">{needed_ticks} 檔保本</div>
                    <div style="font-size:0.75rem; color:#888;">跳 {needed_ticks} 檔打平成本</div>
                </div>
                <div style="background: rgba(128,128,128,0.06); border: 1px solid rgba(128,128,128,0.2); border-radius: 10px; padding: 7px 10px;">
                    <div style="font-size:0.78rem; color:#777;">買賣總稅費成本</div>
                    <div style="font-size:1.15rem; font-weight:800;">{int(total_cost_lots):,} 元</div>
                    <div style="font-size:0.75rem; color:#888;">當沖稅0.15% + 手續費</div>
                </div>
                <div style="background: rgba(128,128,128,0.06); border: 1px solid rgba(128,128,128,0.2); border-radius: 10px; padding: 7px 10px;">
                    <div style="font-size:0.78rem; color:#777;">跳 1 檔淨盈虧</div>
                    <div style="font-size:1.15rem; font-weight:800; color:{net_color};">{int(net_profit_1tick):+,} 元</div>
                    <div style="font-size:0.75rem; color:#888;">{'扣除成本後獲利' if net_profit_1tick > 0 else '跳1檔尚不足打平'}</div>
                </div>
            </div>
            """
            st.markdown(calc_grid_html, unsafe_allow_html=True)
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
        if is_downtrend:
            st.error(f"🚫 **當前禁止做多**：現價（{close:.2f} {currency_sym}）已跌破月線生命線（{res['ma_status']['ma20_val']:.2f} {currency_sym}），空方控盤，順勢交易者嚴禁逆勢摸底！若持有部位，波段停損價設為 `{res['stop_loss']:.2f} {currency_sym}`。")
        else:
            st.markdown(f"""
            1. **建議進場區間**：**`{close:.2f} {currency_sym}`**（回測 5MA 不破分批布局）。
            2. **波段防守點位**：**`{res['stop_loss']:.2f} {currency_sym}`**（跌破點位立即退場，絕不凹單）。
            3. **第一獲利目標**：**`{target_1:.2f} {currency_sym}`**（達成 1.5R 盈虧比，平倉 1/2 入袋並上移防守至成本）。
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
        m1.metric("日線 (5MA)", f"{res['ma_status']['ma5_val']:.2f}", f"{res['ma_status']['ma5_diff']:+.1f}%")
        m2.metric("月線 (20MA)", f"{res['ma_status']['ma20_val']:.2f}", f"{res['ma_status']['ma20_diff']:+.1f}%")
        m3.metric("季線 (60MA)", f"{res['ma_status']['ma60_val']:.2f}", f"{res['ma_status']['ma60_diff']:+.1f}%")

    if mode_type == "futures":
        with st.expander("💎 【期貨契約規格與保證金護城河】", expanded=False):
            st.markdown(f"**標的商品**：`{spec['name']}` ｜ {spec['desc']}")
            sp1, sp2 = st.columns(2)
            sp1.metric("每一跳動點價值", f"NT$ {spec['tick_value']:,} 元")
            sp2.metric("原始保證金門檻", f"NT$ {spec['initial_margin']:,} 元")

            sp3, sp4 = st.columns(2)
            sp3.metric("維持保證金警戒線", f"NT$ {spec['maintenance_margin']:,} 元")
            leverage = (close * spec['tick_value']) / spec['initial_margin'] if spec['initial_margin'] > 0 else 0
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
                f4.metric("負債比率 (D/E)", f"{f_data['debt_ratio']:.1f}%" if f_data['debt_ratio'] is not None else "無數據")
            st.write("---")
            for r in f_data.get('reasons', []):
                st.write(f"• {r}")

    with st.expander("🚪 【階梯式分階出場 SOP】", expanded=False):
        st.markdown(f"""
        - **初始防守停損**：跌破 **`{res['stop_loss']:.2f}` {currency_sym}** 嚴格離場，絕不凹單。
        - **第一階段目標（減碼 1/2）**：達 **`{target_1:.2f}` {currency_sym}**（1.5R 盈虧比），平倉半數部位入袋並上移防守至成本價（鎖定保本）。
        - **第二階段目標（波段收割）**：達 **`{res['target_60d']:.2f}` {currency_sym}** 分批落袋。
        - **移動停利（Trailing Stop）**：其餘部位收盤跌破 5 日線全數獲利了結。
        """)

    with st.expander(f"💰 【部位風控與建議{unit_name}計算機】", expanded=False):
        col_cap, col_risk = st.columns(2)
        with col_cap:
            if mode_type == "futures":
                default_cap = int(user_memory.get("capital_tw", 1000000))
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
            loss_per_unit = risk_unit * spec['tick_value']
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

        if is_downtrend:
            st.warning(f"⚠️ **空方弱勢警示**：目前處於跌破月線格局，系統建議進場數量為 **0 {unit_name}**（觀望為宜）。若依個人風控上限計算，最多承受規模為 **{suggested_pos} {unit_name}**。")
        else:
            b1, b2 = st.columns(2)
            b1.metric("單筆最大容許虧損", f"{int(max_risk_dollar):,} 元" if mode_type != "us" else f"{int(max_risk_dollar):,} USD")
            b2.metric("建議最大進場數量", f"{suggested_pos} {unit_name}", help="同時受限於風險停損額與保證金/現金購買力")
            b3, b4 = st.columns(2)
            b3.metric("目標獲利區", f"{res['target_60d']:.1f} {currency_sym}")
            b4.metric("預期盈虧比 (R/R)", f"{rr_ratio:.2f} : 1")

    with st.expander(f"📊 【過去 1 年{unit_name}策略回測數據 (無前視偏誤)】", expanded=False):
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
            bt4.metric("真實最大回撤 (MDD)", f"{bt['mdd']:.2f}%", help="連續權益曲線之最大峰谷回撤")
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
current_briefing = get_auto_market_briefing(df_market, df_sox, global_forex)

# ----------------- 頂部導航與功能設置 -----------------
st.title("📱 股期決策旗艦站 (跨市場機構版)")

with st.expander("⚙️ 個人風控本金、當沖折讓、看盤備忘錄與資料備份", expanded=False):
    p_c1, p_c2, p_c3 = st.columns(3)
    with p_c1:
        u_cap_tw = st.number_input("台股預設本金(NTD)", value=int(user_memory.get("capital_tw", 1000000)), step=100000, key="prof_cap_tw")
    with p_c2:
        u_cap_us = st.number_input("美股預設本金(USD)", value=int(user_memory.get("capital_us", 50000)), step=5000, key="prof_cap_us")
    with p_c3:
        u_risk = st.number_input("單筆風險(%)", min_value=0.5, max_value=5.0, value=float(user_memory.get("risk_pct", 1.0)), step=0.1, key="prof_risk")

    u_disc = st.slider("當沖券商手續費折讓（例如 2.8 折輸入 0.28）", min_value=0.10, max_value=1.00, value=float(user_memory.get("daytrade_fee_discount", 0.28)), step=0.01, key="prof_disc")
    u_note = st.text_area("📝 個人看盤備忘錄", value=user_memory.get("personal_note", ""), height=68, key="prof_note")
    
    if st.button("💾 儲存本機偏好設定", use_container_width=True, key="btn_save_profile"):
        user_memory["capital_tw"] = u_cap_tw
        user_memory["capital_us"] = u_cap_us
        user_memory["risk_pct"] = u_risk
        user_memory["daytrade_fee_discount"] = u_disc
        user_memory["personal_note"] = u_note
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
                    st.session_state.user_data.update(restored)
                    save_user_data()
                    st.success("設定資料已成功還原！")
                    st.rerun()
            except Exception:
                st.error("備份碼格式不正確，請確認複製完整。")

with st.expander("📘 點此查看【系統現行版本完整功能清單與版本說明】", expanded=False):
    st.markdown("""
    ### 🌟 系統定位與核心架構
    本系統為**跨市場全維度量化決策平台**，整合臺灣證券交易所 (TWSE) 官方即時撮合、臺灣銀行官方牌告匯率、Google 財經外電 RSS、華爾街四大權威機構研究模組與**當沖實戰決策室（VWAP/CDP/ORB突破/保本跳動計算）**。

    ---
    ### 🛠️ 核心功能模組總覽
    1. **⚡ 當沖實戰決策室（VWAP生命線・ORB突破・CDP五關卡・保本跳動計算）**：
       - **VWAP 典型價格均價線**：盤中多空第一分水嶺。
       - **ORB 15分K高低突破**：開盤主力表態順勢多空信號。
       - **CDP 逆勢五關卡價**：依前日日K高低收精確定位 AH、NH、CDP、NL、AL。
       - **當沖保本檔位計算機**：自動依股價級距換算損益兩平跳動檔位（含 0.15% 減半證交稅）。
       - **尾盤平倉倒數計時**：13:00 啟動提醒、13:20 強制清倉警報。
    2. **🏛️ 四大華爾街級權威機構深度研究套件**：
       - 財務分析（三率/現金流）、股票研究（多維估值/目標價）、財報分析（營收EPS/驚奇度）、市場研究（籌碼/Alpha）。
    3. **📋 證交所即時五檔盤口深度**：
       - 雙向深度能量條看板，視覺化呈現委買委賣厚度。
    """)

# ★ 置頂戰情廣播卡片（全自動即時更新，免手動訂選）
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
    st.markdown("### 🌐 即時市場焦點與總經快訊 (Google 財經即時連線)")
    live_rss = fetch_live_macro_rss("台股 OR 費半 OR CPI OR 聯準會 OR 台積電")
    if live_rss:
        for r_item in live_rss[:5]:
            st.markdown(f"• **[{r_item['title']}]({r_item['link']})** — `{r_item['source']}` ({r_item['pub_date']})")
    else:
        st.caption("目前暫無即時外電快訊。")

# ================= 模式 1：🔍 台股診斷 =================
elif st.session_state.main_mode == "tw_stock":
    st.subheader("🔍 台股全維度深度體檢")

    def set_and_jump_tw_ticker(target_code: str):
        clean_code = target_code.strip().upper()
        if clean_code.isdigit():
            clean_code += ".TW"
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
            clean_new_fav = new_fav_in.strip().upper()
            if clean_new_fav.isdigit():
                clean_new_fav += ".TW"
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

    cleaned_tw_ticker = raw_tw_input.strip().upper()
    if cleaned_tw_ticker.isdigit():
        cleaned_tw_ticker = f"{cleaned_tw_ticker}.TW"

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

    if exec_fut_btn or st.session_state.auto_run_fut or st.session_state.analysis_cache_fut is None:
        st.session_state.auto_run_fut = False
        st.session_state.selected_fut_contract = clean_key
        with st.spinner("連線期貨點位與期顧模型中..."):
            df_target_fut = fetch_and_calc("WTX=F")
            fallback_note = None

            if df_target_fut is None or df_target_fut.empty:
                df_target_fut = df_market
                fallback_note = f"📌 **行情資料來源提示**：外部資料庫未提供此期貨即時報價，走勢與均線位階參考加權指數標的；風控與下單已精確套用【{spec_info['name']}】契約規格（每點 {spec_info['tick_value']} 元、保證金 {spec_info['initial_margin']:,} 元）。"

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
                st.session_state.analysis_cache_fut = (r_fut, df_target_fut, spec_info, fallback_note, clean_key)
            else:
                st.session_state.analysis_cache_fut = None
                st.error("暫時無法取得台股指數基準行情，請稍後再試。")

    if st.session_state.analysis_cache_fut is not None:
        r_fut, df_fut_obj, spec_obj, fb_msg, fut_k = st.session_state.analysis_cache_fut
        render_analysis_view(r_fut, df_fut_obj, mode_type="futures", custom_spec=spec_obj, fallback_warning=fb_msg, ticker_raw=fut_k)

# ================= 模式 4：📈 美股期貨 =================
elif st.session_state.main_mode == "us_futures":
    st.subheader("📈 美股期貨獨立專區")
    st.caption("四大美指期貨即時動能・微那斯達克 / 微標普 / 道瓊 / 羅素2000")

    for name, code, desc in US_FUT_LIST:
        df_g = fetch_and_calc(code)
        if df_g is not None and len(df_g) >= 2:
            last_p = df_g.iloc[-1]['Close']
            prev_p = df_g.iloc[-2]['Close']
            chg_pct = ((last_p - prev_p) / prev_p) * 100
            ma5_g = df_g['MA5'].iloc[-1]
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

        with ThreadPoolExecutor(max_workers=5) as executor:
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

        with ThreadPoolExecutor(max_workers=5) as executor:
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
                tw_p = df_market.iloc[-1]['Close'] if df_market is not None else 0
                tw_ma20 = df_market['MA20'].iloc[-1] if df_market is not None else 0
                sox_chg = ((df_sox['Close'].iloc[-1] - df_sox['Close'].iloc[-2]) / df_sox['Close'].iloc[-2] * 100) if (df_sox is not None and len(df_sox) >= 2) else 0
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

    st.markdown("### 🌐 總經與市場焦點外電即時導入 (Google News RSS)")
    rss_q1, rss_q2 = st.columns(2)
    with rss_q1:
        if st.button("🔥 台股 / 費半 / 台積電", use_container_width=True, key="rss_btn_tw"):
            st.session_state.rss_query = "台股 OR 費半 OR 台積電"
    with rss_q2:
        if st.button("🇺🇸 美國 CPI / 聯準會 / 美股", use_container_width=True, key="rss_btn_us"):
            st.session_state.rss_query = "美國 CPI OR 聯準會 OR 那斯達克"

    cur_rss_q = st.session_state.get("rss_query", "台股 OR 美國 CPI OR 費半 OR 台積電")
    rss_items = fetch_live_macro_rss(cur_rss_q)
    if rss_items:
        for idx_r, r_it in enumerate(rss_items):
            with st.container():
                st.markdown(f"**[{r_it['title']}]({r_it['link']})**")
                c_r1, c_r2 = st.columns([2.5, 1.5])
                c_r1.caption(f"來源：{r_it['source']} ｜ {r_it['pub_date']}")
                if c_r2.button("📌 手動鎖定為置頂", key=f"pin_rss_{idx_r}", use_container_width=True):
                    save_market_briefing(
                        f"🔥 市場快訊：{r_it['title'][:28]}...",
                        f"【外電焦點】{r_it['title']}（來源：{r_it['source']}）\n\n請密切留意該事件對台指期夜盤、美股科技股與次日開盤跳空幅度之連動影響。",
                        "系統策略中心",
                        is_manual=True
                    )
                    st.rerun()
                st.write("---")

    st.markdown("### 🔍 個股最新重大訊息速查")
    col_n_input, col_n_btn = st.columns([2.4, 1.6])
    with col_n_input:
        news_ticker = st.text_input("輸入查詢標的代碼", value="2330.TW", label_visibility="collapsed", key="news_search_input")
    with col_n_btn:
        news_clicked = st.button("📰 查個股新聞", type="primary", use_container_width=True, key="fetch_news_btn")

    if news_clicked:
        clean_news_t = news_ticker.strip().upper()
        if clean_news_t.isdigit():
            clean_news_t += ".TW"
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

    st.write("---")
    st.markdown("### 📈 美元兌新台幣走勢與月線 (20MA)")
    df_usdtwd = fetch_and_calc("USDTWD=X")
    if df_usdtwd is None:
        df_usdtwd = fetch_and_calc("TWD=X")

    if df_usdtwd is not None:
        st.line_chart(df_usdtwd[['Close', 'MA20']].dropna().tail(60))
    else:
        st.write("暫時無法取得匯率走勢。")

# 盤中 30 秒自動刷新控制器
if auto_refresh:
    time.sleep(30)
    st.rerun()
