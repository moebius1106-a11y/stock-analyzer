import html
import json
import logging
import math
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import altair as alt
import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import streamlit as st
import yfinance as yf

# ----------------- 結構化日誌配置 -----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(funcName)s) %(message)s"
)
logger = logging.getLogger("QuantitativeDecisionStation")

# ----------------- 全域資源、連線與鎖 -----------------
GLOBAL_EXECUTOR = ThreadPoolExecutor(max_workers=8)
FILE_LOCK = threading.Lock()

HTTP_SESSION = requests.Session()
retries = Retry(total=2, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=20)
HTTP_SESSION.mount("https://", adapter)
HTTP_SESSION.mount("http://", adapter)

TAIPEI_TZ = timezone(timedelta(hours=8))
CONNECT_TIMEOUT = 2.5
READ_TIMEOUT = 3.5

# ----------------- 頁面配置與響應式 CSS -----------------
st.set_page_config(
    page_title="次日開市與即時量化決策站",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
        overflow-x: hidden !important;
        max-width: 100vw !important;
    }
    .block-container {
        padding-top: 2.8rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
        max-width: 100% !important;
    }
    h1 { font-size: 1.35rem !important; font-weight: 800 !important; }
    h2 { font-size: 1.15rem !important; font-weight: 700 !important; }
    h3 { font-size: 1.02rem !important; font-weight: 600 !important; }

    @media (max-width: 768px) {
        div[data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-wrap: wrap !important;
            gap: 0.35rem !important;
            width: 100% !important;
        }
        div[data-testid="stColumn"], div[data-testid="column"] {
            flex: 1 1 45% !important;
            min-width: 140px !important;
        }
    }

    div.stButton, div[data-testid="stLinkButton"] {
        width: 100% !important;
    }
    div.stButton > button, div[data-testid="stFormSubmitButton"] > button {
        width: 100% !important;
        min-height: 2.6rem !important;
        font-weight: 700 !important;
        border-radius: 8px !important;
    }

    div[data-testid="stMetric"] {
        background-color: rgba(128, 128, 128, 0.08);
        border: 1px solid rgba(128, 128, 128, 0.2);
        padding: 0.5rem 0.6rem !important;
        border-radius: 8px;
        margin-bottom: 0.3rem;
        word-break: break-word !important;
    }

    .yahoo-stat-box {
        background-color: rgba(128, 128, 128, 0.06);
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 10px;
        padding: 0.75rem 0.9rem;
        font-size: 0.92rem;
        line-height: 1.6;
    }
    .yahoo-stat-row {
        display: flex;
        justify-content: space-between;
        border-bottom: 1px dashed rgba(128, 128, 128, 0.15);
        padding: 0.2rem 0;
    }
    .yahoo-stat-row:last-child { border-bottom: none; }
    .tw-up { color: #d32f2f; font-weight: 700; }
    .tw-down { color: #2e7d32; font-weight: 700; }
    .tw-flat { color: #757575; font-weight: 700; }

    .macro-alert-card {
        background: rgba(229, 57, 53, 0.06);
        border-left: 4px solid #d32f2f;
        border-radius: 8px;
        padding: 0.75rem;
        margin-bottom: 0.65rem;
        font-size: 0.92rem;
    }
    .inst-report-box {
        background: rgba(26, 115, 232, 0.05);
        border-left: 4px solid #1a73e8;
        border-radius: 8px;
        padding: 0.7rem;
        margin-bottom: 0.55rem;
        font-size: 0.92rem;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- 全市場股票中文名稱對照表 -----------------
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
    "GOOGL": "Alphabet A", "GOOG": "Alphabet C", "AMZN": "亞馬遜", "META": "Meta",
    "AMD": "超微", "TSM": "台積電ADR", "AVGO": "博通", "QCOM": "高通",
    "INTC": "英特爾", "ARM": "安謀", "SMCI": "美超微", "NFLX": "網飛",
    "MU": "美光", "ASML": "艾司摩爾", "PLTR": "Palantir", "COIN": "Coinbase",
    "^TWII": "加權指數", "WTX=F": "台指期貨(參考)"
}

def get_stock_display_label(ticker: str, is_fav: bool = False) -> str:
    t_upper = ticker.strip().upper()
    clean_code = t_upper.replace(".TW", "").replace(".TWO", "")
    name = GLOBAL_STOCK_NAMES.get(t_upper, GLOBAL_STOCK_NAMES.get(clean_code, ""))
    prefix = "⭐ " if is_fav else ""
    return f"{prefix}{name} ({clean_code})" if name else f"{prefix}{clean_code}"

# ----------------- 型別轉換與安全性清洗 -----------------
def safe_float(val, default: float = 0.0) -> float:
    if val is None or pd.isna(val):
        return default
    if isinstance(val, pd.Series):
        if val.empty: return default
        val = val.iloc[0]
    elif isinstance(val, (np.ndarray, list, tuple)):
        if len(val) == 0: return default
        val = val[0]
    if isinstance(val, (float, np.floating)):
        return float(val) if math.isfinite(val) else default
    if isinstance(val, (int, np.integer)):
        return float(val)
    if isinstance(val, str):
        cleaned = val.strip().replace(",", "")
        if cleaned in ("", "-", "N/A", "nan", "None", "_", "--", "null"):
            return default
        try:
            res = float(cleaned)
            return res if math.isfinite(res) else default
        except ValueError:
            return default
    return default

def sanitize_text(text: str) -> str:
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    return html.escape(text.strip())

def sanitize_ticker(ticker_raw: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9\.\^\=\-\_]", "", str(ticker_raw).strip().upper())
    return cleaned[:16]

# ----------------- 使用者隔離與設定儲存 -----------------
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
        "personal_note": "",
        "last_active": datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M")
    }

def get_user_data():
    if "user_data" not in st.session_state:
        default_s = get_default_settings()
        loaded = {}
        if os.path.exists(SETTINGS_FILE):
            with FILE_LOCK:
                try:
                    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content: loaded = json.loads(content)
                except Exception as e:
                    logger.warning(f"讀取設定失敗: {e}")
        merged = default_s.copy()
        if isinstance(loaded, dict):
            for k, v in loaded.items():
                if k in merged: merged[k] = v
        st.session_state.user_data = merged
    return st.session_state.user_data

def save_user_data():
    if "user_data" in st.session_state:
        st.session_state.user_data["last_active"] = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M")
        with FILE_LOCK:
            try:
                temp_file = f"{SETTINGS_FILE}.tmp"
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(st.session_state.user_data, f, ensure_ascii=False, indent=2)
                os.replace(temp_file, SETTINGS_FILE)
            except Exception as e:
                logger.error(f"寫入設定檔失敗: {e}")

def add_recent_history(market: str, ticker: str):
    data = get_user_data()
    key = f"{market}_recent"
    t_clean = sanitize_ticker(ticker)
    if not t_clean: return
    if t_clean in data.get(key, []):
        data[key].remove(t_clean)
    data.setdefault(key, []).insert(0, t_clean)
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
    t_clean = sanitize_ticker(ticker)
    if not t_clean: return
    data.setdefault(key, [])
    if t_clean in data[key]:
        data[key].remove(t_clean)
    else:
        data[key].append(t_clean)
    save_user_data()

# ----------------- 全市場戰情焦點 -----------------
BRIEFING_FILE = "market_briefings.json"

def get_default_briefing():
    now_str = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M")
    return {
        "title": "📌 盤勢焦點：請留意即將發布之總經指標與技術面均線扣抵",
        "content": (
            "• **總經觀察重點**：請密切留意最新公布之美國核心 CPI/PCE 年增率及聯準會利率決策方向。\n"
            "• **台股量化操作指引**：指數若站穩月線（20MA）生命線之上，多方順勢操作；若向下破線則應啟動減碼與波段停損防守。\n"
            "• **動態風險控管**：請依個人帳戶資金嚴格執行單筆停損百分比，嚴禁非理性逆勢加碼。"
        ),
        "author": "系統量化策略中心",
        "updated_at": now_str,
        "is_default": True
    }

def load_market_briefing():
    with FILE_LOCK:
        if os.path.exists(BRIEFING_FILE):
            try:
                with open(BRIEFING_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "content" in data:
                        return data
            except Exception as e:
                logger.warning(f"讀取戰情檔失敗: {e}")
    return get_default_briefing()

def save_market_briefing(title: str, content: str, author: str):
    now_str = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M")
    new_b = {
        "title": sanitize_text(title),
        "content": sanitize_text(content),
        "author": sanitize_text(author) or "系統量化策略中心",
        "updated_at": now_str,
        "is_default": False
    }
    with FILE_LOCK:
        try:
            temp_file = f"{BRIEFING_FILE}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(new_b, f, ensure_ascii=False, indent=2)
            os.replace(temp_file, BRIEFING_FILE)
        except Exception as e:
            logger.error(f"寫入戰情檔失敗: {e}")
    return new_b

# ----------------- 外部新聞 RSS -----------------
@st.cache_data(ttl=180, show_spinner=False)
def fetch_live_macro_rss(query_str: str = "台股 OR 美股 OR CPI OR 聯準會 OR 台積電"):
    encoded_q = quote(query_str)
    url = f"https://news.google.com/rss/search?q={encoded_q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
    items = []
    try:
        r = HTTP_SESSION.get(url, headers=headers, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            for item in root.findall("./channel/item")[:8]:
                title = sanitize_text(item.findtext("title", default="無標題"))
                link = item.findtext("link", default="#")
                pub_date = sanitize_text(item.findtext("pubDate", default=""))
                source_el = item.find("source")
                source_name = sanitize_text(source_el.text) if (source_el is not None and source_el.text) else "財經快訊"
                items.append({
                    "title": title,
                    "link": link,
                    "source": source_name,
                    "pub_date": pub_date[:22] if pub_date else "即時"
                })
    except Exception as e:
        logger.warning(f"擷取 RSS 失敗: {e}")
    return items

def normalize_ticker(ticker: str):
    t = sanitize_ticker(ticker)
    if t.endswith("=F") or t in ("WTX", "MTX", "WMT", "TE", "TF"):
        return t, "futures"
    if t.endswith(".TWO"):
        return t[:-4], "otc"
    if t.endswith(".TW"):
        return t[:-3], "tse"
    return t, "us"

# ----------------- Yahoo Finance 資訊取得 -----------------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_yf_shared_info(ticker: str):
    t_clean = sanitize_ticker(ticker)
    def _worker():
        t = yf.Ticker(t_clean)
        return dict(t.info or {})
    fut = GLOBAL_EXECUTOR.submit(_worker)
    try:
        return fut.result(timeout=4.0)
    except Exception as e:
        logger.warning(f"取得 yf_info 逾時或失敗 ({t_clean}): {e}")
        return {}

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_yf_earnings_history_safe(ticker: str):
    t_clean = sanitize_ticker(ticker)
    def _worker():
        t = yf.Ticker(t_clean)
        eh = t.earnings_history
        if eh is not None and not eh.empty:
            return eh.tail(4).copy()
        return None
    fut = GLOBAL_EXECUTOR.submit(_worker)
    try:
        return fut.result(timeout=3.0)
    except Exception as e:
        logger.warning(f"取得 earnings_history 失敗 ({t_clean}): {e}")
        return None

# ----------------- 證券交易所即時行情 -----------------
def fetch_twse_realtime(ticker: str):
    code, market = normalize_ticker(ticker)
    if market in ("us", "futures"):
        return None

    ex_ch = f"{market}_{code}.tw"
    url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={ex_ch}&json=1&delay=0"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        resp = HTTP_SESSION.get(url, headers=headers, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        if resp.status_code != 200:
            return None
        data = resp.json()
        msg_arr = data.get("msgArray", [])
        if not msg_arr:
            return None

        item = msg_arr[0]
        y_close = safe_float(item.get("y"))
        z_price = safe_float(item.get("z"), default=0.0)

        is_live_trade = True
        price_status = "🟢 盤中即時成交"
        display_price = z_price

        if z_price <= 0:
            b_first = safe_float(str(item.get("b", "")).split("_")[0], default=0.0)
            a_first = safe_float(str(item.get("a", "")).split("_")[0], default=0.0)
            if b_first > 0:
                display_price = b_first
                price_status = "🟡 委買參考價(尚未撮合)"
            elif a_first > 0:
                display_price = a_first
                price_status = "🟡 委賣參考價(尚未撮合)"
            elif y_close > 0:
                display_price = y_close
                price_status = "⚪ 前日收盤價(今日無成交)"
            else:
                display_price = 0.0
                price_status = "🔴 查無有效價格"
            is_live_trade = False

        stock_name = sanitize_text(str(item.get("n", code)))
        if stock_name:
            suffix = "TWO" if market == "otc" else "TW"
            GLOBAL_STOCK_NAMES[f"{code}.{suffix}"] = stock_name
            GLOBAL_STOCK_NAMES[code] = stock_name

        raw_lots = safe_float(item.get("v"), default=0.0)
        converted_shares = raw_lots * 1000.0
        date_str = item.get("d", "")
        time_str = item.get("t", "")

        raw_b = [safe_float(x) for x in str(item.get("b", "")).split("_") if x.strip()]
        raw_g = [int(safe_float(x)) for x in str(item.get("g", "")).split("_") if x.strip()]
        raw_a = [safe_float(x) for x in str(item.get("a", "")).split("_") if x.strip()]
        raw_f = [int(safe_float(x)) for x in str(item.get("f", "")).split("_") if x.strip()]

        bid_prices = (raw_b + [0.0] * 5)[:5]
        bid_vols = (raw_g + [0] * 5)[:5]
        ask_prices = (raw_a + [0.0] * 5)[:5]
        ask_vols = (raw_f + [0] * 5)[:5]

        chg_val = None
        pct_val = None
        if y_close > 0 and display_price > 0:
            chg_val = display_price - y_close
            pct_val = (chg_val / y_close) * 100.0

        return {
            "code": code,
            "market": market,
            "name": stock_name,
            "match_price": display_price,
            "is_live_trade": is_live_trade,
            "price_status": price_status,
            "open": safe_float(item.get("o"), default=display_price),
            "high": safe_float(item.get("h"), default=display_price),
            "low": safe_float(item.get("l"), default=display_price),
            "volume": converted_shares,
            "lots": int(raw_lots),
            "yesterday_close": y_close,
            "chg_val": chg_val,
            "pct_val": pct_val,
            "date_str": date_str,
            "time": time_str,
            "bid_prices": bid_prices,
            "bid_vols": bid_vols,
            "ask_prices": ask_prices,
            "ask_vols": ask_vols,
            "source": "臺灣證券交易所 (TWSE MIS 官方即時)"
        }
    except Exception as e:
        logger.error(f"解析 TWSE 即時資料異常: {e}")
        return None

# ----------------- 大盤統計儀表板 -----------------
@st.cache_data(ttl=15, show_spinner=False)
def fetch_twse_market_dashboard():
    result = {
        "twii_price": 0.0, "twii_chg": 0.0, "twii_pct": 0.0,
        "twii_high": 0.0, "twii_low": 0.0, "twii_open": 0.0, "twii_yclose": 0.0,
        "turnover_billion": 0.0,
        "up_count": None, "limit_up": None,
        "down_count": None, "limit_down": None,
        "flat_count": None,
        "data_time": datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "is_valid": False
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        idx_url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_t00.tw&json=1&delay=0"
        r_idx = HTTP_SESSION.get(idx_url, headers=headers, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        if r_idx.status_code == 200:
            msg_arr = r_idx.json().get("msgArray", [])
            if msg_arr:
                item = msg_arr[0]
                y_val = safe_float(item.get("y"))
                z_val = safe_float(item.get("z"), default=y_val)
                result["twii_price"] = z_val
                result["twii_yclose"] = y_val
                if y_val > 0:
                    result["twii_chg"] = z_val - y_val
                    result["twii_pct"] = (result["twii_chg"] / y_val) * 100.0
                v_million = safe_float(item.get("v"), default=0.0)
                if v_million > 0:
                    result["turnover_billion"] = v_million / 100.0
                result["is_valid"] = True
    except Exception as e:
        logger.warning(f"擷取 TWSE 大盤統計失敗: {e}")

    try:
        stat_url = "https://mis.twse.com.tw/stock/api/getStatis.jsp?ex=tse&delay=0"
        r_stat = HTTP_SESSION.get(stat_url, headers=headers, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        if r_stat.status_code == 200:
            detail = r_stat.json().get("detail", {})
            if isinstance(detail, dict) and detail:
                up_c = detail.get("up", detail.get("u"))
                dn_c = detail.get("down", detail.get("d"))
                lu_c = detail.get("limitUp", detail.get("lu", 0))
                ld_c = detail.get("limitDown", detail.get("ld", 0))
                fl_c = detail.get("unchanged", detail.get("z"))
                if up_c is not None: result["up_count"] = int(safe_float(up_c))
                if lu_c is not None: result["limit_up"] = int(safe_float(lu_c))
                if dn_c is not None: result["down_count"] = int(safe_float(dn_c))
                if ld_c is not None: result["limit_down"] = int(safe_float(ld_c))
                if fl_c is not None: result["flat_count"] = int(safe_float(fl_c))
    except Exception as e:
        logger.warning(f"擷取 TWSE 漲跌家數失敗: {e}")

    return result

# ----------------- 分時走勢圖資料 -----------------
@st.cache_data(ttl=30, show_spinner=False)
def fetch_intraday_series(ticker: str):
    t_clean = sanitize_ticker(ticker)
    try:
        t = yf.Ticker(t_clean)
        df_intra = t.history(period="1d", interval="1m")
        if df_intra is None or df_intra.empty or len(df_intra) < 3:
            df_5d = t.history(period="5d", interval="5m")
            if df_5d is not None and not df_5d.empty:
                last_day = df_5d.index[-1].date()
                df_intra = df_5d[df_5d.index.date == last_day].copy()

        if df_intra is None or df_intra.empty:
            return None, None

        if isinstance(df_intra.columns, pd.MultiIndex):
            df_intra.columns = df_intra.columns.get_level_values(0)

        y_close = None
        if ".TW" in t_clean or ".TWO" in t_clean:
            twse_info = fetch_twse_realtime(t_clean)
            if twse_info and twse_info["yesterday_close"] > 0:
                y_close = twse_info["yesterday_close"]

        if y_close is None:
            df_daily = t.history(period="5d", interval="1d")
            if df_daily is not None and len(df_daily) >= 2:
                y_close = safe_float(df_daily['Close'].iloc[-2])

        df_plot = df_intra[['Open', 'High', 'Low', 'Close', 'Volume']].dropna(subset=['Close']).copy()
        if df_plot.empty:
            return None, None

        if df_plot.index.tz is not None:
            local_idx = df_plot.index.tz_convert(TAIPEI_TZ) if (".TW" in t_clean or ".TWO" in t_clean or t_clean in ("^TWII", "WTX=F")) else df_plot.index
        else:
            local_idx = df_plot.index

        df_plot['TimeStr'] = local_idx.strftime('%H:%M')
        df_plot['YesterdayClose'] = y_close if (y_close and y_close > 0) else np.nan
        if y_close and y_close > 0:
            df_plot['Diff'] = df_plot['Close'] - y_close
            df_plot['Pct'] = (df_plot['Diff'] / y_close) * 100.0
        else:
            df_plot['Diff'] = np.nan
            df_plot['Pct'] = np.nan

        df_plot['BarColor'] = np.where(df_plot['Close'] >= df_plot['Open'], '漲(紅)', '跌(綠)')
        df_plot['VolLots'] = np.where(df_plot['Volume'] > 10000, df_plot['Volume'] / 1000.0, df_plot['Volume'])

        return df_plot.reset_index(drop=True), y_close
    except Exception as e:
        logger.error(f"產生分時數據失敗 ({t_clean}): {e}")
        return None, None

def render_intraday_chart_widget(ticker: str, title_name: str = ""):
    t_clean = sanitize_ticker(ticker)
    df_intra, y_close = fetch_intraday_series(t_clean)
    if df_intra is None or df_intra.empty:
        st.info("⚪ 該標的目前暫無足夠之即時分時明細資料（可能處於休市或資料源結算時段）。")
        return

    last_row = df_intra.iloc[-1]
    curr_p = safe_float(last_row['Close'])
    high_p = safe_float(df_intra['High'].max())
    low_p = safe_float(df_intra['Low'].min())

    display_title = sanitize_text(title_name or t_clean)
    if y_close and y_close > 0:
        chg_val = curr_p - y_close
        chg_pct = (chg_val / y_close) * 100.0
        color_cls = "tw-up" if chg_val > 0 else ("tw-down" if chg_val < 0 else "tw-flat")
        sign_str = "+" if chg_val > 0 else ""
        stat_html = (
            f"**{display_title}** ｜ 時間 `{last_row['TimeStr']}` ｜ "
            f"成交價 <span class='{color_cls}'>{curr_p:,.2f} ({sign_str}{chg_val:,.2f} / {sign_str}{chg_pct:.2f}%)</span> ｜ "
            f"最高 <span class='tw-up'>{high_p:,.2f}</span> ｜ 最低 <span class='tw-down'>{low_p:,.2f}</span> ｜ "
            f"昨收 `{y_close:,.2f}`"
        )
    else:
        stat_html = f"**{display_title}** ｜ 時間 `{last_row['TimeStr']}` ｜ 現價 **{curr_p:,.2f}** ｜ 昨收 `資料未揭露`"
    st.markdown(stat_html, unsafe_allow_html=True)

    base = alt.Chart(df_intra).encode(
        x=alt.X('TimeStr:O', title=None, axis=alt.Axis(labelAngle=0, labelOverlap=True, tickCount=6))
    )
    price_line = base.mark_line(color='#1a73e8', strokeWidth=2.0).encode(
        y=alt.Y('Close:Q', title='價格 / 點位', scale=alt.Scale(zero=False)),
        tooltip=[
            alt.Tooltip('TimeStr:O', title='時間'),
            alt.Tooltip('Close:Q', title='成交價', format=',.2f'),
            alt.Tooltip('High:Q', title='最高', format=',.2f'),
            alt.Tooltip('Low:Q', title='最低', format=',.2f')
        ]
    )

    if y_close and y_close > 0:
        ref_rule = alt.Chart(pd.DataFrame({'y': [y_close]})).mark_rule(
            strokeDash=[4, 4], color='#888888', strokeWidth=1.2
        ).encode(y='y:Q')
        top_chart = (price_line + ref_rule).properties(height=200)
    else:
        top_chart = price_line.properties(height=200)

    vol_bars = base.mark_bar().encode(
        y=alt.Y('VolLots:Q', title='分時量', axis=alt.Axis(labels=False, ticks=False)),
        color=alt.Color('BarColor:N', scale=alt.Scale(domain=['漲(紅)', '跌(綠)'], range=['#d32f2f', '#2e7d32']), legend=None)
    ).properties(height=60)

    st.altair_chart(alt.vconcat(top_chart, vol_bars).resolve_scale(x='shared'), width="stretch")

# ----------------- 官方匯率與全球外匯 -----------------
@st.cache_data(ttl=300, show_spinner=False)
def fetch_bot_forex():
    url = "https://rate.bot.com.tw/xrt/flcsv/0/day"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = HTTP_SESSION.get(url, headers=headers, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        if r.status_code == 200:
            for line in r.text.splitlines():
                parts = line.split(",")
                if len(parts) >= 5 and parts[0].strip() == "USD":
                    val = safe_float(parts[12]) if len(parts) >= 13 else safe_float(parts[4])
                    if val > 0:
                        return {"usd_twd": val, "source": "臺灣銀行官方牌告匯率(參考)", "is_real": True}
    except Exception as e:
        logger.warning(f"取得臺銀匯率失敗: {e}")
    return None

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
        "source": "Yahoo 即時外匯 (市場撮合參考)",
        "has_real_twd": False
    }

    bot_data = fetch_bot_forex()
    if bot_data:
        res["twd_rate"] = bot_data["usd_twd"]
        res["source"] = bot_data["source"]
        res["has_real_twd"] = True

    df_usdtwd = fetch_and_calc("USDTWD=X")
    df_dxy = fetch_and_calc("DX-Y.NYB")
    df_jpy = fetch_and_calc("JPY=X")

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
            if diff < -0.05: res["twd_status"] = "🟢 今日台幣呈現走升態勢（匯率走低）"
            elif diff > 0.05: res["twd_status"] = "🔴 今日台幣呈現走貶態勢（匯率走高）"
            else: res["twd_status"] = "⚪ 今日匯率區間狹幅震盪"

            res["twd_trend"] = "波段低於月線（相對升值結構）" if (res["twd_rate"] and res["twd_rate"] < ma20_twd) else "波段高於月線（相對貶值結構）"

    if df_dxy is not None and len(df_dxy) >= 2:
        last_dxy = safe_float(df_dxy.iloc[-1]['Close'])
        ma20_dxy = safe_float(df_dxy['MA20'].iloc[-1], last_dxy)
        res["dxy_rate"] = last_dxy
        res["dxy_trend"] = "偏強 (美元指數位於月線上方)" if last_dxy > ma20_dxy else "偏弱 (美元指數位於月線下方)"

    if df_jpy is not None and len(df_jpy) >= 5:
        last_jpy = safe_float(df_jpy.iloc[-1]['Close'])
        ma5_jpy = safe_float(df_jpy['MA5'].iloc[-1], last_jpy)
        res["jpy_rate"] = last_jpy
        if last_jpy > 0 and ma5_jpy > 0 and (last_jpy - ma5_jpy) / ma5_jpy < -0.015:
            res["jpy_risk"] = "⚠️ 警示：日圓近期短線大幅升值，需提防潛在套利交易平倉賣壓。"
        else:
            res["jpy_risk"] = "✅ 正常：日圓匯率短線波動維持於常態區間。"

    return res

# ----------------- 歷史技術數據與指標計算 -----------------
@st.cache_data(ttl=60, show_spinner=False)
def fetch_and_calc(ticker: str, period: str = "1y"):
    t_clean = sanitize_ticker(ticker)
    try:
        obj = yf.Ticker(t_clean)
        df = obj.history(period=period)
        if df.empty or len(df) < 15:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()

        if (".TW" in t_clean or ".TWO" in t_clean) and not t_clean.endswith("=F"):
            twse_live = fetch_twse_realtime(t_clean)
            if twse_live and twse_live.get("is_live_trade") and twse_live["match_price"] > 0:
                now_taipei = datetime.now(TAIPEI_TZ)
                today_str = now_taipei.strftime("%Y%m%d")
                if twse_live.get("date_str") == today_str:
                    last_idx = df.index[-1]
                    if last_idx.date() < now_taipei.date():
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
                        df.iloc[-1, df.columns.get_loc('High')] = max(df.iloc[-1]['High'], twse_live["high"])
                        df.iloc[-1, df.columns.get_loc('Low')] = min(df.iloc[-1]['Low'], twse_live["low"]) if twse_live["low"] > 0 else df.iloc[-1]['Low']
                        if twse_live["volume"] > 0:
                            df.iloc[-1, df.columns.get_loc('Volume')] = twse_live["volume"]

        df = df[df['Close'] > 0].copy()
        if len(df) < 10:
            return None

        df['MA5'] = df['Close'].rolling(5, min_periods=1).mean()
        df['MA20'] = df['Close'].rolling(20, min_periods=5).mean()
        df['MA60'] = df['Close'].rolling(60, min_periods=20).mean()
        df['Vol_MA5'] = df['Volume'].rolling(5, min_periods=1).mean()

        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14, min_periods=1).mean()
        rs = gain / (loss + 1e-9)
        df['RSI14'] = 100.0 - (100.0 / (1.0 + rs))

        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = ema12 - ema26
        df['MACD'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['OSC'] = df['DIF'] - df['MACD']

        hl = df['High'] - df['Low']
        hc = (df['High'] - df['Close'].shift()).abs()
        lc = (df['Low'] - df['Close'].shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        df['ATR14'] = tr.rolling(14, min_periods=1).mean().bfill()

        return df
    except Exception as e:
        logger.error(f"技術指標計算異常 ({t_clean}): {e}")
        return None

# ----------------- 歷史回測引擎 -----------------
def backtest_strategy(df_stock, market_type="tw"):
    if df_stock is None or len(df_stock) < 65:
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

    if market_type == "us": cost_rate = 0.0015
    elif market_type == "futures": cost_rate = 0.0006
    else: cost_rate = 0.00585

    while i < n_bars - 6:
        if signals.iloc[i]:
            entry_p = safe_float(df_stock['Open'].iloc[i + 1])
            prev_close_entry = safe_float(df_stock['Close'].iloc[i])

            if market_type == "tw" and prev_close_entry > 0:
                if (entry_p - prev_close_entry) / prev_close_entry >= 0.098:
                    i += 1
                    continue

            exit_p = safe_float(df_stock['Open'].iloc[i + 6])
            prev_close_exit = safe_float(df_stock['Close'].iloc[i + 5])

            if market_type == "tw" and prev_close_exit > 0:
                if (exit_p - prev_close_exit) / prev_close_exit <= -0.098:
                    if i + 7 < n_bars: exit_p = safe_float(df_stock['Open'].iloc[i + 7])

            if entry_p <= 0 or exit_p <= 0:
                i += 1
                continue

            net_ret = (((exit_p - entry_p) / entry_p) - cost_rate) * 100.0
            trade_returns.append(net_ret)
            i += 6
            continue
        i += 1

    if not trade_returns:
        return None

    wins = [r for r in trade_returns if r > 0]
    losses = [r for r in trade_returns if r <= 0]
    win_rate = (len(wins) / len(trade_returns)) * 100.0
    avg_return = float(np.mean(trade_returns))
    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(np.mean(losses)) if losses else 0.0
    worst_single_loss = float(min(trade_returns))

    equity = 100.0
    equity_curve = [equity]
    for r in trade_returns:
        equity *= (1.0 + r / 100.0)
        equity_curve.append(equity)

    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        if val > peak: peak = val
        dd = (peak - val) / peak * 100.0
        if dd > max_dd: max_dd = dd

    total_cum_ret = ((equity - 100.0) / 100.0) * 100.0

    return {
        "count": len(trade_returns),
        "win_rate": win_rate,
        "avg_return": avg_return,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "worst_loss": worst_single_loss,
        "mdd": max_dd,
        "total_cum_ret": total_cum_ret,
        "is_statistically_sound": len(trade_returns) >= 10
    }

# ----------------- 基本面體質評估 -----------------
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
            yield_val = safe_float(yield_raw * 100 if yield_raw is not None else None, default=None)
            beta_val = safe_float(beta_raw, default=None)

            if yield_val is None and beta_val is None:
                return {"has_data": False, "is_etf": True, "score": None, "yield": None, "beta": None, "reasons": ["⚠️ 查無足夠之配息率與 Beta 數據"]}

            fund_score = 0
            reasons = []
            if yield_val is not None:
                if yield_val >= 7.0: fund_score += 25; reasons.append(f"年化殖利率 {yield_val:.1f}%，高息防禦優勢")
                elif yield_val >= 4.5: fund_score += 20; reasons.append(f"年化殖利率 {yield_val:.1f}%，配息收益穩定")
                else: fund_score += 15; reasons.append(f"年化殖利率 {yield_val:.1f}%，屬成長/海外型")

            if beta_val is not None:
                if beta_val <= 0.8: fund_score += 15; reasons.append(f"Beta 係數 {beta_val:.2f}，抗跌防禦性佳")
                elif beta_val <= 1.2: fund_score += 12; reasons.append(f"Beta 係數 {beta_val:.2f}，貼近大盤波動")
                else: fund_score += 8; reasons.append(f"Beta 係數 {beta_val:.2f}，波動幅度相對較大")

            fund_score += 10
            reasons.append("成分股實施一籃子分散風險")

            return {
                "has_data": True,
                "is_etf": True,
                "score": fund_score,
                "yield": yield_val,
                "beta": beta_val,
                "reasons": reasons
            }
        else:
            roe_raw = info.get('returnOnEquity', None)
            op_raw = info.get('operatingMargins', None)
            pe_raw = info.get('trailingPE', None)
            de_raw = info.get('debtToEquity', None)

            roe_val = safe_float(roe_raw * 100 if roe_raw is not None else None, default=None)
            op_margin_val = safe_float(op_raw * 100 if op_raw is not None else None, default=None)
            pe_val = safe_float(pe_raw, default=None)
            de_val = safe_float(de_raw, default=None)

            if roe_val is None and op_margin_val is None and pe_val is None:
                return {"has_data": False, "is_etf": False, "score": None, "reasons": ["⚠️ 財務指標數據不足，排除基本面計分"]}

            fund_score = 0
            reasons = []
            if roe_val is not None:
                if roe_val >= 15: fund_score += 15; reasons.append(f"ROE 達 {roe_val:.1f}%，資本回報效率極佳")
                elif roe_val >= 10: fund_score += 10; reasons.append(f"ROE 達 {roe_val:.1f}%，維持穩健水準")
                else: reasons.append(f"ROE 偏低 ({roe_val:.1f}%)")

            if op_margin_val is not None:
                if op_margin_val >= 15: fund_score += 15; reasons.append(f"營業利益率 {op_margin_val:.1f}%，本業競爭優勢顯著")
                elif op_margin_val >= 8: fund_score += 10; reasons.append(f"營業利益率 {op_margin_val:.1f}%，獲利扎實")
                else: reasons.append(f"營業利益率偏低 ({op_margin_val:.1f}%)")

            if pe_val is not None:
                if pe_val <= 0: reasons.append("本益比不適用（近四季虧損）")
                elif 8 <= pe_val <= 25: fund_score += 10; reasons.append(f"本益比 {pe_val:.1f}x，估值合理")
                else: fund_score += 5; reasons.append(f"本益比為 {pe_val:.1f}x")

            if de_val is not None:
                if de_val <= 80: fund_score += 10; reasons.append(f"負債比率健康 ({de_val:.1f}%)")
                else: reasons.append(f"負債比率為 ({de_val:.1f}%)")

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
    except Exception as e:
        logger.warning(f"擷取基本面異常 ({ticker}): {e}")
        return {"has_data": False, "is_etf": False, "score": None, "reasons": ["⚠️ 基本面資料連線異常"]}

# ----------------- 全維度量化診斷主引擎 -----------------
def analyze_full_stock(ticker, df_stock, df_market, df_futures, df_tsm, df_sox, forex_info, asset_type="tw"):
    live_twse = fetch_twse_realtime(ticker) if asset_type == "tw" else None

    last_stk = df_stock.iloc[-1]
    prev_stk = df_stock.iloc[-2] if len(df_stock) >= 2 else last_stk

    close = safe_float(last_stk['Close'])
    if close <= 0:
        pos_closes = df_stock['Close'][df_stock['Close'] > 0]
        close = safe_float(pos_closes.iloc[-1]) if not pos_closes.empty else 1.0

    ma5 = safe_float(last_stk.get('MA5'), close)
    ma20 = safe_float(last_stk.get('MA20'), close)
    ma60 = safe_float(last_stk.get('MA60'), close)
    atr_val = safe_float(last_stk.get('ATR14'), default=close * 0.02)

    ma_status = {
        "ma5_diff": ((close - ma5) / (ma5 + 1e-9)) * 100,
        "ma20_diff": ((close - ma20) / (ma20 + 1e-9)) * 100,
        "ma60_diff": ((close - ma60) / (ma60 + 1e-9)) * 100,
        "ma5_val": ma5, "ma20_val": ma20, "ma60_val": ma60
    }

    if close > ma5 > ma20 > ma60:
        ma_alignment = "🔥 完美多頭排列 (價格 > 日線 > 月線 > 季線)"
        ma_score = 25
    elif close > ma20 and ma20 > ma60:
        ma_alignment = "📈 中長線偏多架構 (守穩月線與季線)"
        ma_score = 18
    elif close < ma5 < ma20 < ma60:
        ma_alignment = "❄️ 完全空頭排列 (受制所有均線壓制)"
        ma_score = 0
    else:
        ma_alignment = "🔄 均線震盪糾結 (多空方向待表態)"
        ma_score = 10

    open_p = safe_float(last_stk['Open'], close)
    prev_close = safe_float(prev_stk['Close'], close)
    gap_pct = ((open_p - prev_close) / (prev_close + 1e-9)) * 100.0
    intraday_pct = ((close - open_p) / (open_p + 1e-9)) * 100.0

    opening_diag = []
    if gap_pct >= 1.0: opening_diag.append(f"強勢跳空開高 (+{gap_pct:.2f}%)，多方意圖明確。")
    elif gap_pct <= -1.0: opening_diag.append(f"弱勢跳空開低 ({gap_pct:.2f}%)，下檔承接力道待觀察。")
    else: opening_diag.append(f"平盤附近開出 ({gap_pct:+.2f}%)，由盤中量能決定方向。")

    if close > open_p: k_type = "🔴 盤中實體紅 K (買盤持續推進)"
    elif close < open_p: k_type = "🟢 盤中實體黑 K (留意調節賣壓)"
    else: k_type = "⚪ 盤中十字星 (多空平手拉鋸)"

    analyst_data = {"has_data": False, "opinions": 0, "target_mean": 0.0, "rec_label": "⚪ 暫無機構評等"}
    fund_data = {"has_data": False, "score": None, "reasons": []}
    inst_suite = {"has_suite": False}

    if asset_type in ("tw", "us"):
        analyst_data = fetch_analyst_consensus(ticker)
        fund_data = fetch_fundamentals(ticker)
        inst_suite = fetch_institutional_research_suite(ticker)
    elif asset_type == "futures":
        analyst_data = {
            "has_data": False, "opinions": 0, "target_mean": 0.0,
            "rec_label": "⚪ 期貨合約無個別券商評等",
            "rec_desc": "期貨合約依市場大額籌碼、實質基差及均線波段進行量化推算"
        }

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
    if df_market is not None and not df_market.empty:
        last_mkt = df_market.iloc[-1]
        if last_mkt['Close'] > last_mkt['MA20']: mkt_score += 15
        if last_mkt['MA20'] > last_mkt['MA60']: mkt_score += 10

    tech_score = 0
    vol_ratio = safe_float(last_stk['Volume']) / (safe_float(last_stk['Vol_MA5']) + 1e-9)
    if close > prev_stk['Close'] and vol_ratio >= 1.2: tech_score += 10
    if last_stk['OSC'] > 0: tech_score += 8
    if 50 <= last_stk['RSI14'] <= 70: tech_score += 7

    if fund_data.get("has_data") and fund_data.get("score") is not None:
        tech_scaled = (mkt_score + ma_score + tech_score) / 65.0 * 60.0
        fund_scaled = (fund_data["score"] / 50.0) * 40.0
        total_score = int(min(max(tech_scaled + fund_scaled, 0), 100))
        scoring_model_desc = "雙維模型 (技術動能 60% + 基本面護城河 40%)"
    else:
        total_score = int(min(max((mkt_score + ma_score + tech_score) / 65.0 * 100.0, 0), 100))
        scoring_model_desc = "純技術動能模型 (大盤環境 38% + 均線架構 38% + 動能指標 24%)"

    is_breakdown = close < ma20
    if not is_breakdown:
        stop_loss = max(close - 2.0 * atr_val, ma20 - 0.5 * atr_val)
    else:
        stop_loss = close - 1.5 * atr_val

    if analyst_data.get("has_data") and analyst_data.get("target_mean", 0) > close:
        target_60d = analyst_data["target_mean"]
        target_source = "華爾街/機構分析師共識平均目標價"
    else:
        recent_high = safe_float(df_stock['High'].tail(60).max(), close * 1.08)
        target_60d = max(recent_high, close + 2.0 * atr_val)
        target_source = "量化模型波段高點與 ATR 波動率推算值"

    return {
        "total_score": total_score,
        "scoring_model_desc": scoring_model_desc,
        "close": close,
        "stop_loss": stop_loss,
        "target_60d": target_60d,
        "target_source": target_source,
        "is_breakdown": is_breakdown,
        "ma_status": ma_status,
        "ma_alignment": ma_alignment,
        "gap_pct": gap_pct,
        "intraday_pct": intraday_pct,
        "k_type": k_type,
        "opening_diag": opening_diag,
        "fund_data": fund_data,
        "analyst_data": analyst_data,
        "inst_suite": inst_suite,
        "rel_alpha_20d": rel_alpha_20d,
        "rel_alpha_60d": rel_alpha_60d,
        "live_info": live_twse,
        "asset_type": asset_type
    }

# ----------------- 完整機構研究報告渲染器 -----------------
def format_large_money(val, currency="NTD"):
    if val is None or val == 0: return "未揭露"
    abs_v = abs(val)
    sign = "-" if val < 0 else ""
    if currency == "USD":
        if abs_v >= 1e12: return f"{sign}${abs_v/1e12:.2f} 兆 (T)"
        if abs_v >= 1e9: return f"{sign}${abs_v/1e9:.2f} 十億 (B)"
        if abs_v >= 1e6: return f"{sign}${abs_v/1e6:.2f} 百萬 (M)"
        return f"{sign}${abs_v:,.0f}"
    else:
        if abs_v >= 1e12: return f"{sign}{abs_v/1e12:.2f} 兆元"
        if abs_v >= 1e8: return f"{sign}{abs_v/1e8:.2f} 億元"
        if abs_v >= 1e4: return f"{sign}{abs_v/1e4:.1f} 萬元"
        return f"{sign}{abs_v:,.0f} 元"

def fetch_institutional_research_suite(ticker: str):
    clean_code, market = normalize_ticker(ticker)
    if market == "futures": return {"has_suite": False}
    try:
        info = fetch_yf_shared_info(ticker)
        if not info: return {"has_suite": False}

        gross_margin = safe_float(info.get("grossMargins"), None)
        op_margin = safe_float(info.get("operatingMargins"), None)
        profit_margin = safe_float(info.get("profitMargins"), None)
        roe = safe_float(info.get("returnOnEquity"), None)
        roa = safe_float(info.get("returnOnAssets"), None)

        return {
            "has_suite": True,
            "financial_analysis": {
                "gross_margin": gross_margin * 100.0 if gross_margin else None,
                "op_margin": op_margin * 100.0 if op_margin else None,
                "profit_margin": profit_margin * 100.0 if profit_margin else None,
                "roe": roe * 100.0 if roe else None,
                "roa": roa * 100.0 if roa else None,
                "current_ratio": safe_float(info.get("currentRatio"), None),
                "quick_ratio": safe_float(info.get("quickRatio"), None),
                "debt_to_equity": safe_float(info.get("debtToEquity"), None),
                "free_cf": safe_float(info.get("freeCashflow"), None),
                "op_cf": safe_float(info.get("operatingCashflow"), None),
                "total_cash": safe_float(info.get("totalCash"), None),
                "total_debt": safe_float(info.get("totalDebt"), None)
            },
            "equity_research": {
                "trailing_pe": safe_float(info.get("trailingPE"), None),
                "forward_pe": safe_float(info.get("forwardPE"), None),
                "pb_ratio": safe_float(info.get("priceToBook"), None),
                "peg_ratio": safe_float(info.get("pegRatio"), None),
                "ev_ebitda": safe_float(info.get("enterpriseToEbitda"), None),
                "div_yield": safe_float(info.get("dividendYield")) * 100.0 if info.get("dividendYield") else None,
                "book_val": safe_float(info.get("bookValue"), None)
            },
            "earnings_reviewer": {
                "rev_growth": safe_float(info.get("revenueGrowth")) * 100.0 if info.get("revenueGrowth") else None,
                "earn_growth": safe_float(info.get("earningsGrowth")) * 100.0 if info.get("earningsGrowth") else None,
                "trailing_eps": safe_float(info.get("trailingEps"), None),
                "forward_eps": safe_float(info.get("forwardEps"), None),
                "total_rev": safe_float(info.get("totalRevenue"), None),
                "ebitda_val": safe_float(info.get("ebitda"), None)
            },
            "market_researcher": {
                "sector": sanitize_text(str(info.get("sector") or "指標產業")),
                "industry": sanitize_text(str(info.get("industry") or "指標企業")),
                "mkt_cap": safe_float(info.get("marketCap"), None),
                "beta": safe_float(info.get("beta"), None),
                "inst_held": safe_float(info.get("heldPercentInstitutions")) * 100.0 if info.get("heldPercentInstitutions") else None,
                "summary_text": sanitize_text(str(info.get("longBusinessSummary", "")))
            }
        }
    except Exception as e:
        logger.warning(f"擷取機構數據失敗: {e}")
        return {"has_suite": False}

def fetch_analyst_consensus(ticker: str):
    try:
        info = fetch_yf_shared_info(ticker)
        target_mean = safe_float(info.get('targetMeanPrice'))
        opinions = int(safe_float(info.get('numberOfAnalystOpinions'), 0))
        rec_key = str(info.get('recommendationKey', 'none')).lower()

        rec_map = {
            "strong_buy": ("🔥 強力買進 (Strong Buy)", "機構共識偏多"),
            "buy": ("🟢 買進 (Buy)", "機構共識偏多"),
            "hold": ("🟡 中立持有 (Hold)", "機構看法平穩"),
            "underperform": ("🟠 減碼 (Underperform)", "機構共識偏弱"),
            "sell": ("🔴 賣出 (Sell)", "機構看法保守")
        }
        rec_label, rec_desc = rec_map.get(rec_key, ("⚪ 暫無機構評等", "該標的無券商連續覆蓋"))

        return {
            "has_data": opinions > 0 or target_mean > 0,
            "target_mean": target_mean,
            "rec_label": rec_label,
            "rec_desc": rec_desc,
            "opinions": opinions
        }
    except Exception as e:
        logger.warning(f"分析師資料異常: {e}")
        return {"has_data": False, "target_mean": 0.0, "rec_label": "⚪ 暫無數據", "opinions": 0}

def render_institutional_research_panel(res, ticker_raw, mode_type="tw"):
    suite = res.get("inst_suite", {})
    if not suite or not suite.get("has_suite"): return

    fin = suite["financial_analysis"]
    eq = suite["equity_research"]
    earn = suite["earnings_reviewer"]
    mkt = suite["market_researcher"]
    an_data = res["analyst_data"]
    curr_code = "USD" if mode_type == "us" else "NTD"
    curr_sym = "USD" if mode_type == "us" else "元"
    disp_name = get_stock_display_label(ticker_raw, is_fav=False)

    with st.expander("🏛️ 【四大權威機構深度研究報告】Financial / Equity / Earnings / Market", expanded=True):
        tab_fa, tab_eq, tab_er, tab_mr, tab_export = st.tabs([
            "📊 財務分析", "📑 股票研究", "📈 財報分析", "🌐 市場研究", "📥 完整報告"
        ])
        with tab_fa:
            st.markdown("#### 📊 Financial Analysis（企業財務結構與現金流護城河）")
            fa1, fa2, fa3 = st.columns(3)
            fa1.metric("毛利率 (Gross)", f"{fin['gross_margin']:.1f}%" if fin['gross_margin'] else "未揭露")
            fa2.metric("營益率 (Operating)", f"{fin['op_margin']:.1f}%" if fin['op_margin'] else "未揭露")
            fa3.metric("淨利率 (Net)", f"{fin['profit_margin']:.1f}%" if fin['profit_margin'] else "未揭露")

            fa4, fa5, fa6 = st.columns(3)
            fa4.metric("股東權益報酬 (ROE)", f"{fin['roe']:.1f}%" if fin['roe'] else "未揭露")
            fa5.metric("資產報酬率 (ROA)", f"{fin['roa']:.1f}%" if fin['roa'] else "未揭露")
            fa6.metric("負債權益比 (D/E)", f"{fin['debt_to_equity']:.1f}%" if fin['debt_to_equity'] else "未揭露")

            fa7, fa8 = st.columns(2)
            cr_str = f"{fin['current_ratio']:.2f}" if fin['current_ratio'] else "--"
            qr_str = f"{fin['quick_ratio']:.2f}" if fin['quick_ratio'] else "--"
            fa7.metric("流動比率 / 速動比率", f"{cr_str} / {qr_str}")
            fa8.metric("自由現金流 (FCF)", format_large_money(fin['free_cf'], curr_code))

        with tab_eq:
            st.markdown("#### 📑 Equity Research（機構估值模型與目標位階）")
            eq1, eq2, eq3 = st.columns(3)
            eq1.metric("歷史本益比 (PE)", f"{eq['trailing_pe']:.1f}x" if (eq['trailing_pe'] and eq['trailing_pe'] > 0) else "不適用")
            eq2.metric("預估本益比 (Forward)", f"{eq['forward_pe']:.1f}x" if (eq['forward_pe'] and eq['forward_pe'] > 0) else "未揭露")
            eq3.metric("股價淨值比 (P/B)", f"{eq['pb_ratio']:.2f}x" if eq['pb_ratio'] else "未揭露")

            eq4, eq5, eq6 = st.columns(3)
            eq4.metric("PEG 成長估值比", f"{eq['peg_ratio']:.2f}" if eq['peg_ratio'] else "未揭露")
            eq5.metric("EV / EBITDA", f"{eq['ev_ebitda']:.1f}x" if eq['ev_ebitda'] else "未揭露")
            eq6.metric("現金殖利率", f"{eq['div_yield']:.2f}%" if eq['div_yield'] else "未揭露")

        with tab_er:
            st.markdown("#### 📈 Earnings Reviewer（季度成長動能與每股盈餘）")
            er1, er2 = st.columns(2)
            er1.metric("營收年增率 (YoY)", f"{earn['rev_growth']:+.1f}%" if earn['rev_growth'] else "未揭露")
            er2.metric("盈餘年增率 (YoY)", f"{earn['earn_growth']:+.1f}%" if earn['earn_growth'] else "未揭露")

            er3, er4 = st.columns(2)
            er3.metric("近四季累計 EPS", f"{earn['trailing_eps']:.2f} {curr_sym}" if earn['trailing_eps'] else "未揭露")
            er4.metric("預估未來 EPS", f"{earn['forward_eps']:.2f} {curr_sym}" if earn['forward_eps'] else "未揭露")

        with tab_mr:
            st.markdown("#### 🌐 Market Researcher（機構籌碼與相對強度）")
            mr1, mr2, mr3 = st.columns(3)
            mr1.metric("總市值規模", format_large_money(mkt['mkt_cap'], curr_code))
            mr2.metric("外資/機構持股比", f"{mkt['inst_held']:.1f}%" if mkt['inst_held'] else "未揭露")
            mr3.metric("Beta 波動風險", f"{mkt['beta']:.2f}" if mkt['beta'] else "未揭露")

            mr4, mr5 = st.columns(2)
            mr4.metric("近 20 日相對大盤 Alpha", f"{res.get('rel_alpha_20d', 0.0):+.2f}%", "強於大盤" if res.get('rel_alpha_20d', 0.0) > 0 else "弱於大盤")
            mr5.metric("近 60 日相對大盤 Alpha", f"{res.get('rel_alpha_60d', 0.0):+.2f}%", "波段領先" if res.get('rel_alpha_60d', 0.0) > 0 else "波段落後")

        with tab_export:
            st.markdown("#### 📥 完整機構級四維度投研報告下載")
            rep_md = f"""# 【{disp_name}】深度量化研究報告
- **生成時間**：{datetime.now(TAIPEI_TZ).strftime('%Y-%m-%d %H:%M')}
- **評估現價**：{res['close']:.2f} {curr_sym} ｜ **量化總分**：{res['total_score']} / 100
- **建議防守**：{res['stop_loss']:.2f} {curr_sym} ｜ **目標價**：{res['target_60d']:.2f} {curr_sym}
"""
            st.code(rep_md, language="markdown")
            st.download_button("💾 下載完整研究報告 (.md)", data=rep_md.encode("utf-8"), file_name=f"Report_{ticker_raw}.md", mime="text/markdown", width="stretch")

# ----------------- 全局商品規格與常態庫 -----------------
TW_FUTURES_SPECS = {
    "WTX": {"name": "台指期貨 (大台)", "tick_value": 200, "initial_margin": 250000, "desc": "全市場主力籌碼風向核心"},
    "MTX": {"name": "小型台指 (小台)", "tick_value": 50, "initial_margin": 62500, "desc": "散戶與短線波段核心"},
    "WMT": {"name": "微型台指 (微台)", "tick_value": 10, "initial_margin": 12500, "desc": "小資量化避險首選"},
    "TE": {"name": "電子期貨", "tick_value": 400, "initial_margin": 210000, "desc": "半導體與權值電子指標"},
    "TF": {"name": "金融期貨", "tick_value": 1000, "initial_margin": 130000, "desc": "大型金控與壽險資產指標"}
}

MARKET_QUALITY_UNIVERSE = [
    ("台積電", "2330.TW", "半導體先進製程龍頭"),
    ("聯發科", "2454.TW", "IC設計領航者"),
    ("鴻海", "2317.TW", "全球電子代工/AI伺服器"),
    ("廣達", "2382.TW", "AI伺服器領導大廠"),
    ("緯穎", "6669.TW", "雲端資料中心伺服器"),
    ("台達電", "2308.TW", "電源管理與綠能永續"),
    ("富邦金", "2881.TW", "金控獲利龍頭"),
    ("國泰金", "2882.TW", "全方位金控旗艦"),
    ("長榮", "2603.TW", "全球貨櫃航運龍頭"),
    ("奇鋐", "3017.TW", "散熱模組領導大廠"),
    ("大立光", "3008.TW", "光學鏡頭專利領先者"),
    ("元大台灣50", "0050.TW", "台股核心藍籌組合")
]

ETF_UNIVERSE = [
    ("元大台灣50", "0050.TW", "市值型", "台股市值前50大權值龍頭"),
    ("富邦台50", "006208.TW", "市值型", "低經理費追蹤台股前50大龍頭"),
    ("元大高股息", "0056.TW", "高股息", "預測高現金殖利率"),
    ("國泰永續高股息", "00878.TW", "高股息", "ESG+過去3年平均高殖利率/季配"),
    ("群益台灣精選高息", "00919.TW", "高股息", "宣告股利精準篩選/高配息率"),
    ("復華台灣科技優息", "00929.TW", "高股息", "全科技股高股息/月配息代表"),
    ("統一FANG+", "00757.TW", "海外科技", "美國科技巨頭/高成長動能"),
    ("國泰費城半導體", "00830.TW", "海外半導體", "全球半導體硬體/AI上游核心"),
    ("元大美債20年", "00679B.TWO", "債券避險", "長天期美債/穩定債息")
]

EARNINGS_CALLS = [
    {"公司": "台積電 (2330)", "重要性": "⭐⭐⭐⭐⭐", "期間": "每季第 1 個月中旬 (1/4/7/10月)", "重點觀測": "資本支出、CoWoS產能、AI半導體展望"},
    {"公司": "聯發科 (2454)", "重要性": "⭐⭐⭐⭐", "期間": "每季底至次月首週 (1/4/7/10月)", "重點觀測": "天璣旗艦晶片出貨、邊緣AI ASIC設計案"},
    {"公司": "鴻海 (2317)", "重要性": "⭐⭐⭐⭐", "期間": "每季中旬 (3/5/8/11月)", "重點觀測": "GB200 伺服器量產交期、電動車進度"},
    {"公司": "廣達 (2382)", "重要性": "⭐⭐⭐⭐", "期間": "每季中旬 (3/5/8/11月)", "重點觀測": "AI伺服器機櫃出貨比重、車用電子獲利動能"}
]

# ----------------- 全域基準平行預載 -----------------
@st.cache_data(ttl=120, show_spinner=False)
def preload_global_benchmarks():
    tickers = ["^TWII", "WTX=F", "TSM", "^SOX", "^GSPC"]
    results = {}
    futs = {t: GLOBAL_EXECUTOR.submit(fetch_and_calc, t) for t in tickers}
    for t, f in futs.items():
        try:
            results[t] = f.result(timeout=4.0)
        except Exception:
            results[t] = None
    return results

bench_dict = preload_global_benchmarks()
df_market = bench_dict.get("^TWII")
df_futures_bench = bench_dict.get("WTX=F")
df_tsm = bench_dict.get("TSM")
df_sox = bench_dict.get("^SOX")
df_spx = bench_dict.get("^GSPC")
global_forex = analyze_forex_data()
user_memory = get_user_data()
current_briefing = load_market_briefing()

# ----------------- 診斷結果總覽渲染器 -----------------
def render_analysis_view(res, df_asset, mode_type="tw", custom_spec=None, ticker_raw=None):
    close = safe_float(res.get('close', 1.0))
    stop_p = safe_float(res.get('stop_loss', close * 0.95))
    target_p = safe_float(res.get('target_60d', close * 1.05))
    risk_unit = max(close - stop_p, close * 0.015)
    target_1 = close + (1.5 * risk_unit)

    currency_sym = "元" if mode_type != "us" else "USD"
    unit_name = "張" if mode_type == "tw" else ("股" if mode_type == "us" else "口")

    st.markdown(f"### 📊 標的診斷分析：`{sanitize_text(get_stock_display_label(ticker_raw))}`")
    st.caption(f"📌 **模型基準**：{res.get('scoring_model_desc')} ｜ 目標價來源：{res.get('target_source')}")

    if res.get("live_info"):
        live = res["live_info"]
        st.info(f"⚡ **行情狀態**：{live['price_status']} ｜ 最新成交價：**{live['match_price']}** ｜ 來源：{live['source']}")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("量化綜合評分", f"{res['total_score']} / 100")
    m2.metric("最新評估價位", f"{close:,.2f} {currency_sym}")
    m3.metric("建議防守價 (模型)", f"{stop_p:,.2f} {currency_sym}")
    m4.metric("預期報酬目標", f"{target_p:,.2f} {currency_sym}")

    st.warning("⚠️ **金融風險提示**：所有模型計算之停損與目標價僅供策略參考，**絕非實際委託保證成交價格**。")

    # 分時圖與五檔盤口深度
    with st.expander("📺 【即時分時走勢與五檔委買賣深度】", expanded=True):
        render_intraday_chart_widget(ticker_raw, title_name=ticker_raw)
        live = res.get("live_info")
        if live and live.get("bid_prices") and live.get("ask_prices"):
            st.markdown("#### 📋 即時五檔盤口撮合深度")
            b_p, b_v = live["bid_prices"], live["bid_vols"]
            a_p, a_v = live["ask_prices"], live["ask_vols"]
            tot_bid, tot_ask = sum(b_v), sum(a_v)
            tot_depth = tot_bid + tot_ask
            bid_pct = (tot_bid / tot_depth * 100.0) if tot_depth > 0 else 50.0

            st.caption(f"🔥 委買總量：**{tot_bid:,}** 張 ({bid_pct:.1f}%) ｜ ❄️ 委賣總量：**{tot_ask:,}** 張 ({100.0-bid_pct:.1f}%)")
            st.progress(min(max(bid_pct / 100.0, 0.0), 1.0))

            rows = []
            for i in range(5):
                bp = f"{b_p[i]:,.2f}" if b_p[i] > 0 else "--"
                bv = f"{b_v[i]:,}" if b_v[i] > 0 else "--"
                ap = f"{a_p[i]:,.2f}" if a_p[i] > 0 else "--"
                av = f"{a_v[i]:,}" if a_v[i] > 0 else "--"
                rows.append(f"<div class='yahoo-stat-row'><span>{bv} 張 ({bp})</span><span style='color:#888;'>檔位 {i+1}</span><span>({ap}) {av} 張</span></div>")
            st.markdown(f"<div class='yahoo-stat-box'>{''.join(rows)}</div>", unsafe_allow_html=True)

    # 完整四大機構投研報告
    if mode_type in ("tw", "us"):
        render_institutional_research_panel(res, ticker_raw, mode_type=mode_type)

    # 精確下單指引
    with st.expander(f"🎯 【精確下單指引與策略 SOP】", expanded=True):
        if res.get('is_breakdown'):
            st.error(f"🚫 **空方防守警示**：現價跌破月線生命線（{res['ma_status']['ma20_val']:.2f}），嚴禁追價摸底！建議離場或嚴設防守 `{stop_p:,.2f} {currency_sym}`。")
        else:
            st.markdown(f"""
            1. **建議進場區間**：**`{close:,.2f} {currency_sym}`**（回測 5MA 不破分批布局）。
            2. **波段防守點位**：**`{stop_p:,.2f} {currency_sym}`**（跌破點位立即退場，絕不凹單）。
            3. **第一獲利目標**：**`{target_1:,.2f} {currency_sym}`**（達成 1.5R 盈虧比，平倉 1/2 入袋並上移防守至成本）。
            4. **波段獲利目標**：**`{target_p:,.2f} {currency_sym}`**（對齊機構目標價或波段高點擴展區）。
            """)

    # 策略歷史回測檢驗
    with st.expander(f"📊 【策略歷史回測檢驗 (持有5日・無前視偏誤)】", expanded=False):
        bt = backtest_strategy(df_asset, market_type=mode_type)
        if bt:
            if not bt["is_statistically_sound"]:
                st.warning(f"⚠️ **樣本數偏低警示**：近 1 年有效信號僅 {bt['count']} 次，統計可信度有限，回測僅供參考。")
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("交易次數", f"{bt['count']} 次")
            b2.metric("策略勝率", f"{bt['win_rate']:.1f}%")
            b3.metric("平均淨報酬", f"{bt['avg_return']:+.2f}%")
            b4.metric("歷史最大回撤", f"{bt['mdd']:.2f}%")
            st.caption(f"📌 平均獲利：`{bt['avg_win']:+.2f}%` ｜ 平均虧損：`{bt['avg_loss']:+.2f}%` ｜ 累積淨報酬：`{bt['total_cum_ret']:+.2f}%`")
        else:
            st.info("該標的歷史資料長度不足或未觸發有效技術信號。")

    # 風控部位試算
    with st.expander(f"💰 【部位風控與建議下單{unit_name}數計算】", expanded=False):
        cap_val = st.number_input(f"帳戶總可用資金 ({currency_sym})", value=int(user_memory.get(f"capital_{mode_type}", 1000000)), step=50000)
        risk_pct = st.slider("單筆最大承受損失比例 (%)", 0.5, 5.0, 1.0, 0.1)
        max_loss_dollar = cap_val * (risk_pct / 100.0)

        lot_size = 1000 if mode_type == "tw" else (1 if mode_type == "us" else custom_spec.get('tick_value', 200))
        loss_per_unit = risk_unit * lot_size
        sugg_pos = int(max_loss_dollar // loss_per_unit) if loss_per_unit > 0 else 0

        p1, p2 = st.columns(2)
        p1.metric("單筆容許最大損失額", f"{int(max_loss_dollar):,} {currency_sym}")
        p2.metric(f"建議最大下單規模", f"{sugg_pos} {unit_name}")

# ----------------- 頂部導航與功能設置 -----------------
st.title("📱 股期決策旗艦站 (跨市場完整版)")

with st.expander("⚙️ 個人風控本金、看盤備忘錄與資料備份", expanded=False):
    p_c1, p_c2, p_c3 = st.columns(3)
    u_cap_tw = p_c1.number_input("台股預設本金(NTD)", value=int(user_memory.get("capital_tw", 1000000)), step=100000)
    u_cap_us = p_c2.number_input("美股預設本金(USD)", value=int(user_memory.get("capital_us", 50000)), step=5000)
    u_risk = p_c3.number_input("單筆風險(%)", 0.5, 5.0, float(user_memory.get("risk_pct", 1.0)), 0.1)
    u_note = st.text_area("📝 個人看盤備忘錄", value=user_memory.get("personal_note", ""), height=68)
    if st.button("💾 儲存本機偏好設定", width="stretch"):
        user_memory["capital_tw"] = u_cap_tw
        user_memory["capital_us"] = u_cap_us
        user_memory["risk_pct"] = u_risk
        user_memory["personal_note"] = u_note
        save_user_data()
        st.success("已儲存偏好參數！")

st.markdown(f"""
<div class="macro-alert-card">
    <b>{sanitize_text(current_briefing['title'])}</b><br>
    <span style="opacity:0.9;">{sanitize_text(current_briefing['content']).replace(chr(10), '<br>')}</span><br>
    <div style="font-size:0.75rem; color:#888; text-align:right; margin-top:4px;">
        發布來源：{sanitize_text(current_briefing['author'])} ｜ 更新時間：{current_briefing['updated_at']}
    </div>
</div>
""", unsafe_allow_html=True)

# 8 大完整模式選單
if "main_mode" not in st.session_state: st.session_state.main_mode = "live_watch"
if "selected_tw_ticker" not in st.session_state: st.session_state.selected_tw_ticker = "2330.TW"
if "selected_us_ticker" not in st.session_state: st.session_state.selected_us_ticker = "NVDA"
if "selected_fut" not in st.session_state: st.session_state.selected_fut = "WTX"

top_c1, top_c2 = st.columns([1.5, 1.0])
with top_c1:
    if st.button("📺 大盤即時看盤 (分時/戰情)", type="primary" if st.session_state.main_mode == "live_watch" else "secondary", width="stretch"):
        st.session_state.main_mode = "live_watch"
        st.rerun()
with top_c2:
    auto_refresh = st.checkbox("⏱️ 30秒自動刷新", value=False)
    if auto_refresh:
        st.markdown("<script>setTimeout(function(){ window.location.reload(); }, 30000);</script>", unsafe_allow_html=True)

r1_c1, r1_c2 = st.columns(2)
if r1_c1.button("🔍 台股診斷", type="primary" if st.session_state.main_mode == "tw_stock" else "secondary", width="stretch"):
    st.session_state.main_mode = "tw_stock"; st.rerun()
if r1_c2.button("🇺🇸 美股診斷", type="primary" if st.session_state.main_mode == "us_stock" else "secondary", width="stretch"):
    st.session_state.main_mode = "us_stock"; st.rerun()

r2_c1, r2_c2 = st.columns(2)
if r2_c1.button("⚡ 台灣期貨", type="primary" if st.session_state.main_mode == "tw_futures" else "secondary", width="stretch"):
    st.session_state.main_mode = "tw_futures"; st.rerun()
if r2_c2.button("📈 美股期貨", type="primary" if st.session_state.main_mode == "us_futures" else "secondary", width="stretch"):
    st.session_state.main_mode = "us_futures"; st.rerun()

r3_c1, r3_c2 = st.columns(2)
if r3_c1.button("📊 ETF 專區", type="primary" if st.session_state.main_mode == "etf" else "secondary", width="stretch"):
    st.session_state.main_mode = "etf"; st.rerun()
if r3_c2.button("💎 體質雷達", type="primary" if st.session_state.main_mode == "market" else "secondary", width="stretch"):
    st.session_state.main_mode = "market"; st.rerun()

r4_c1, r4_c2 = st.columns(2)
if r4_c1.button("📢 法說與戰情導入", type="primary" if st.session_state.main_mode == "events" else "secondary", width="stretch"):
    st.session_state.main_mode = "events"; st.rerun()
if r4_c2.button("💱 外匯大盤", type="primary" if st.session_state.main_mode == "forex" else "secondary", width="stretch"):
    st.session_state.main_mode = "forex"; st.rerun()

st.write("---")

# ================= 模式 0：📺 即時大盤 =================
if st.session_state.main_mode == "live_watch":
    st.subheader("📺 臺灣加權指數即時走勢與盤面統計")
    dash = fetch_twse_market_dashboard()
    render_intraday_chart_widget("^TWII", title_name="加權指數 (^TWII)")

    if dash["is_valid"]:
        cls = "tw-up" if dash["twii_chg"] > 0 else ("tw-down" if dash["twii_chg"] < 0 else "tw-flat")
        sign = "+" if dash["twii_chg"] > 0 else ""
        st.markdown(f"""
        <div class="yahoo-stat-box">
            <div class="yahoo-stat-row">
                <span>加權指數</span>
                <span class="{cls}">{dash['twii_price']:,.2f} ({sign}{dash['twii_chg']:,.2f} / {sign}{dash['twii_pct']:.2f}%)</span>
            </div>
            <div class="yahoo-stat-row">
                <span>大盤成交金額</span>
                <span><b>{dash['turnover_billion']:,.2f} 億元</b></span>
            </div>
            <div class="yahoo-stat-row">
                <span>上漲 / 下跌家數</span>
                <span>上漲 <b class="tw-up">{dash['up_count'] or '--'}</b> ｜ 下跌 <b class="tw-down">{dash['down_count'] or '--'}</b></span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("⚠️ 暫時無法連線至臺灣證券交易所大盤行情伺服器。")

    st.markdown("### 🌐 即時市場焦點外電 (Google News)")
    live_rss = fetch_live_macro_rss("台股 OR 費半 OR CPI OR 聯準會 OR 台積電")
    for r_item in live_rss[:5]:
        st.markdown(f"• **[{r_item['title']}]({r_item['link']})** — `{r_item['source']}` ({r_item['pub_date']})")

# ================= 模式 1：🔍 台股診斷 =================
elif st.session_state.main_mode == "tw_stock":
    st.subheader("🔍 台股全維度深度體檢")

    tw_favs = user_memory.get("tw_favorites", ["2330.TW", "2454.TW"])
    st.caption("⭐ **常用股票清單**：")
    f_cols = st.columns(2)
    for idx, fav in enumerate(tw_favs[:4]):
        if f_cols[idx % 2].button(get_stock_display_label(fav, is_fav=True), width="stretch", key=f"fav_tw_{fav}"):
            st.session_state.selected_tw_ticker = fav
            st.rerun()

    tw_in = st.text_input("輸入台股代碼", value=st.session_state.selected_tw_ticker)
    clean_tw = sanitize_ticker(tw_in)
    if clean_tw.isdigit(): clean_tw = f"{clean_tw}.TW"

    if st.button("🚀 執行量化診斷", type="primary", width="stretch"):
        st.session_state.selected_tw_ticker = clean_tw
        add_recent_history("tw", clean_tw)
        with st.spinner("連線證交所撮合主機與資料庫計算中..."):
            df_stk = fetch_and_calc(clean_tw)
            if df_stk is not None:
                r = analyze_full_stock(clean_tw, df_stk, df_market, None, df_tsm, df_sox, global_forex, asset_type="tw")
                render_analysis_view(r, df_stk, mode_type="tw", ticker_raw=clean_tw)
            else:
                st.error("❌ 查無該標的行情數據，請確認代碼是否正確。")

# ================= 模式 2：🇺🇸 美股診斷 =================
elif st.session_state.main_mode == "us_stock":
    st.subheader("🇺🇸 美股深度量化診斷")

    us_favs = user_memory.get("us_favorites", ["NVDA", "AAPL"])
    st.caption("⭐ **常用美股清單**：")
    uf_cols = st.columns(2)
    for idx, fav in enumerate(us_favs[:4]):
        if uf_cols[idx % 2].button(get_stock_display_label(fav, is_fav=True), width="stretch", key=f"fav_us_{fav}"):
            st.session_state.selected_us_ticker = fav
            st.rerun()

    us_in = st.text_input("輸入美股英文代碼", value=st.session_state.selected_us_ticker)
    clean_us = sanitize_ticker(us_in)

    if st.button("🚀 診斷美股標的", type="primary", width="stretch"):
        st.session_state.selected_us_ticker = clean_us
        add_recent_history("us", clean_us)
        with st.spinner("連線華爾街資料庫分析中..."):
            df_us = fetch_and_calc(clean_us)
            if df_us is not None:
                r_us = analyze_full_stock(clean_us, df_us, df_spx, None, None, df_sox, global_forex, asset_type="us")
                render_analysis_view(r_us, df_us, mode_type="us", ticker_raw=clean_us)
            else:
                st.error("❌ 查無該美股代碼行情。")

# ================= 模式 3：⚡ 台灣期貨 =================
elif st.session_state.main_mode == "tw_futures":
    st.subheader("⚡ 台灣期貨專區 (台指期貨量化分析)")
    fq1, fq2 = st.columns(2)
    if fq1.button("台指期 (大台)", width="stretch"): st.session_state.selected_fut = "WTX"; st.rerun()
    if fq2.button("小型台指 (小台)", width="stretch"): st.session_state.selected_fut = "MTX"; st.rerun()

    fut_spec = TW_FUTURES_SPECS.get(st.session_state.selected_fut, TW_FUTURES_SPECS["WTX"])

    with st.spinner("連線期貨報價主機檢驗中..."):
        df_target_fut = fetch_and_calc("WTX=F")

    if df_target_fut is None or df_target_fut.empty:
        st.error("❌ **期貨即時行情獲取失敗**：外部即時報價源未提供有效之台指期貨連續月報價。")
        st.warning("🛡️ **系統防護已啟動**：嚴格禁止以加權現貨指數替代期貨進行下單計算。")
        if df_market is not None and not df_market.empty:
            st.markdown("#### 📌 【加權現貨大盤走勢 (僅供環境參考)】")
            st.line_chart(df_market['Close'].tail(60))
    else:
        st.success(f"✅ 成功連線台指期貨行情資料源 ｜ 套用規格：{fut_spec['name']}")
        r_fut = analyze_full_stock("WTX=F", df_target_fut, df_market, None, None, None, global_forex, asset_type="futures")
        render_analysis_view(r_fut, df_target_fut, mode_type="futures", custom_spec=fut_spec, ticker_raw="WTX=F")

# ================= 模式 4：📈 美股期貨 =================
elif st.session_state.main_mode == "us_futures":
    st.subheader("📈 美股期貨獨立專區")
    US_FUT_LIST = [
        ("微那斯達克期 (NQ)", "NQ=F", "全球科技龍頭風向球"),
        ("小標普500期 (ES)", "ES=F", "美股大盤流動性與宏觀資產"),
        ("道瓊期貨 (YM)", "YM=F", "傳統價值龍頭與防禦指標"),
        ("羅素2000期 (RTY)", "RTY=F", "中小型股景氣復甦動能")
    ]
    for name, code, desc in US_FUT_LIST:
        df_g = fetch_and_calc(code)
        if df_g is not None and len(df_g) >= 2:
            last_p = df_g.iloc[-1]['Close']
            prev_p = df_g.iloc[-2]['Close']
            chg_pct = ((last_p - prev_p) / prev_p) * 100
            c_f1, c_f2 = st.columns([2, 1])
            c_f1.markdown(f"**{name}** ｜ {desc}")
            c_f2.metric("點位", f"{last_p:.2f}", f"{chg_pct:+.2f}%")
            st.write("---")

# ================= 模式 5：📊 ETF 專區 =================
elif st.session_state.main_mode == "etf":
    st.subheader("📊 ETF 旗艦量化策略雷達")
    if st.button("⚡ 開始全維度即時掃描排行", type="primary", width="stretch"):
        progress_bar = st.progress(0)
        etf_results = []

        def etf_worker(item):
            try:
                name, code, cat, desc = item
                df_stk = fetch_and_calc(code)
                if df_stk is not None:
                    r = analyze_full_stock(code, df_stk, df_market, None, None, None, global_forex, asset_type="tw")
                    return {"名稱": name, "代碼": code, "類別": cat, "總評分": r['total_score'], "現價": r['close'], "建議防守": r['stop_loss'], "殖利率": r['fund_data'].get('yield')}
                return None
            except Exception:
                return None

        futs = [GLOBAL_EXECUTOR.submit(etf_worker, item) for item in ETF_UNIVERSE]
        for idx, f in enumerate(futs):
            try:
                res_item = f.result(timeout=6.0)
                if res_item: etf_results.append(res_item)
            except Exception:
                pass
            progress_bar.progress((idx + 1) / len(futs))
        progress_bar.empty()

        if etf_results:
            df_etf = pd.DataFrame(etf_results).sort_values(by="總評分", ascending=False).reset_index(drop=True)
            for rank, row in df_etf.iterrows():
                badge = "🟢 偏多" if row['總評分'] >= 75 else ("🟡 定額區" if row['總評分'] >= 60 else "🔴 觀望")
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.markdown(f"**#{rank+1} {row['名稱']} ({row['代碼']})**")
                c2.markdown(f"**{row['總評分']}** 分")
                c3.caption(badge)
                st.write("---")

    with st.expander("🧮 定期定額「微笑曲線」扣款計算機", expanded=False):
        etf_cap = st.number_input("每月預算 (NTD)", value=20000, step=5000)
        etf_state = st.radio("當前位階：", ["常態整理（月線與季線之間）", "大幅拉回（低於季線 5% 以上）", "高檔大漲（高於月線 6% 以上）"])
        if "大幅拉回" in etf_state: st.success(f"🎯 建議扣款 **{int(etf_cap * 1.5):,} 元**（加碼）")
        elif "高檔大漲" in etf_state: st.warning(f"🎯 建議扣款 **{int(etf_cap * 0.7):,} 元**（保留現金）")
        else: st.info(f"🎯 維持標準扣款 **{int(etf_cap):,} 元**")

# ================= 模式 6：💎 體質雷達 =================
elif st.session_state.main_mode == "market":
    st.subheader("💎 市場穩健優質標的掃描")
    if st.button("⚡ 開始掃描優選標的", type="primary", width="stretch"):
        progress_bar = st.progress(0)
        scan_results = []

        def worker(item):
            try:
                name, code, desc = item
                df_stk = fetch_and_calc(code)
                if df_stk is not None:
                    r = analyze_full_stock(code, df_stk, df_market, None, None, None, global_forex, asset_type="tw")
                    return {"名稱": name, "代碼": code, "產業地位": desc, "總評分": r['total_score'], "現價": r['close'], "ROE": r['fund_data'].get('roe')}
                return None
            except Exception:
                return None

        futs = [GLOBAL_EXECUTOR.submit(worker, item) for item in MARKET_QUALITY_UNIVERSE]
        for idx, f in enumerate(futs):
            try:
                res_item = f.result(timeout=6.0)
                if res_item: scan_results.append(res_item)
            except Exception:
                pass
            progress_bar.progress((idx + 1) / len(futs))
        progress_bar.empty()

        if scan_results:
            df_res = pd.DataFrame(scan_results).sort_values(by="總評分", ascending=False).reset_index(drop=True)
            for rank, row in df_res.iterrows():
                badge = "🟢 優選" if row['總評分'] >= 75 else "🟡 觀察"
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.markdown(f"**#{rank+1} {row['名稱']} ({row['代碼']})**")
                c2.markdown(f"**{row['總評分']}** 分")
                c3.caption(badge)
                st.write("---")

# ================= 模式 7：📢 法說與戰情導入 =================
elif st.session_state.main_mode == "events":
    st.subheader("📢 關鍵市場戰情導入 ＆ 法說會時程")
    with st.expander("✍️ 【導入／更新置頂戰情焦點】", expanded=True):
        b_title_in = st.text_input("戰情標題", value=current_briefing["title"])
        b_content_in = st.text_area("戰情內容", value=current_briefing["content"], height=100)
        if st.button("🚀 發布並更新置頂戰情", type="primary", width="stretch"):
            save_market_briefing(b_title_in, b_content_in, "系統量化策略中心")
            st.success("已更新全站置頂戰情！")
            st.rerun()

    st.markdown("### 🗓️ 台股指標龍頭・法說會常態時程")
    for call in EARNINGS_CALLS:
        st.markdown(f"**{call['公司']}** ｜ {call['重要性']}")
        st.caption(f"📅 期間：`{call['期間']}` ｜ 🎯 核心看點：{call['重點觀測']}")
        st.write("---")

# ================= 模式 8：💱 全球外匯大盤 =================
elif st.session_state.main_mode == "forex":
    st.subheader("💱 全球外匯與熱錢資金即時儀表板")
    fx = global_forex
    col_f1, col_f2, col_f3 = st.columns(3)
    col_f1.metric("USD/TWD", f"{fx['twd_rate']:.2f}" if fx['twd_rate'] else "檢索中", f"{fx['twd_change']:+.2f}")
    col_f2.metric("美元 (DXY)", f"{fx['dxy_rate']:.2f}" if fx['dxy_rate'] else "檢索中")
    col_f3.metric("日圓 (JPY)", f"{fx['jpy_rate']:.2f}" if fx['jpy_rate'] else "檢索中")
    st.caption(f"基準來源：**{fx['source']}**")
    st.info(f"**台幣走勢**：{fx['twd_status']}\n\n**波段結構**：{fx['twd_trend']}")
    st.caption(f"• 美元結構：{fx['dxy_trend']}")
    st.caption(f"• 日圓風險：{fx['jpy_risk']}")
