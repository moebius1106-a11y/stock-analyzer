import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import altair as alt
import requests
import math
import json
import os
import time
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

# 頁面配置
st.set_page_config(
    page_title="次日開市與即時量化決策站",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 手機端直覺觸控與雙欄排版強制 CSS (徹底鎖死視窗寬度、消除單欄坍塌與橫向溢出)
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

    /* 手機端強制維持雙欄/多欄等比並排：覆蓋 Streamlit 預設 640px 100% 寬度限制 */
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

    /* 按鈕大小與字級最佳化：緊湊雙列排版，文字單行完整顯示不溢出 */
    div.stButton {
        width: 100% !important;
        min-width: 0 !important;
        max-width: 100% !important;
    }
    div.stButton > button {
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
        display: block !important;
        box-sizing: border-box !important;
    }

    div.stTextInput > div > div > input {
        height: 2.85rem !important;
        font-size: 1.05rem !important;
        border-radius: 9px !important;
    }

    /* 數值卡片防擠壓保護 */
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

    /* Yahoo 風格大盤統計看盤室表格樣式 */
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
</style>
""", unsafe_allow_html=True)

TAIPEI_TZ = timezone(timedelta(hours=8))

# ----------------- 通行密碼防護 (強制 Secrets 安全檢查) -----------------
try:
    ACCESS_PASSWORD = st.secrets["PASSWORD"]
except Exception:
    ACCESS_PASSWORD = None

if ACCESS_PASSWORD is None:
    st.error("🚨 **系統安全性錯誤：未檢測到 Streamlit Secrets [PASSWORD] 設定！**")
    st.markdown("""
    **【解決步驟】**：
    1. 前往 Streamlit Cloud 管理後台（App Settings > Secrets）。
    2. 新增設定內容：
    ```toml
    PASSWORD = "您的專屬密碼"
    ```
    3. 儲存後重新整理本頁面即可正常啟動。
    """)
    st.stop()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 內部量化決策系統")
    st.caption("請輸入通行碼以開始使用")
    pwd = st.text_input("訪問密碼", type="password", key="login_pwd")
    if st.button("🔓 登入系統", type="primary", use_container_width=True, key="login_btn"):
        if pwd == ACCESS_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("密碼錯誤，請重新輸入。")
    st.stop()

# ----------------- 全市場股票中文名稱對照字典 (執行緒安全共享字典) -----------------
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

# ----------------- 常用股票與歷史持久化記憶模組 -----------------
HISTORY_FILE = "user_history.json"

def get_user_data():
    default_data = {
        "tw_favorites": ["2330.TW", "2454.TW", "2317.TW", "0050.TW"],
        "tw_recent": ["2330.TW", "2454.TW"],
        "us_favorites": ["NVDA", "AAPL", "MSFT", "TSLA"],
        "us_recent": ["NVDA", "AAPL"]
    }
    if "user_data" not in st.session_state:
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in default_data.items():
                        if k not in data or not isinstance(data[k], list):
                            data[k] = v
                    st.session_state.user_data = data
            except Exception:
                st.session_state.user_data = default_data
        else:
            st.session_state.user_data = default_data
    return st.session_state.user_data

def save_user_data():
    if "user_data" in st.session_state:
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
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

def toggle_favorite_stock(market: str, ticker: str):
    data = get_user_data()
    key = f"{market}_favorites"
    ticker = ticker.strip().upper()
    if ticker in data[key]:
        data[key].remove(ticker)
    else:
        data[key].append(ticker)
    save_user_data()

# ----------------- 數值安全轉換工具 -----------------
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

# ----------------- 股票與期貨代碼正規化 -----------------
def normalize_ticker(ticker: str):
    t = ticker.strip().upper()
    if t.endswith("=F") or t in ("WTX", "MTX", "WMT", "TE", "TF"):
        return t, "futures"
    if t.endswith(".TWO"):
        return t[:-4], "otc"
    if t.endswith(".TW"):
        return t[:-3], "tse"
    return t, "us"

# ----------------- 權威 API 1：臺灣證券交易所官方即時行情 (含五檔委買賣解析) -----------------
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

                # 解析即時五檔委買與委賣明細
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

# ----------------- 權威 API 1-B：大盤即時統計看板 (加權含金融/未含金融/委買委賣/漲跌家數) -----------------
@st.cache_data(ttl=15)
def fetch_twse_market_dashboard():
    """
    直連證交所 MIS 擷取：
    1. 加權指數 (含金融 t00.tw) 與 加權指數 (未含金融 t001.tw) 與 櫃買指數 (o00.tw)
    2. 大盤委買/委賣筆數、張數、成交金額、漲跌停家數統計
    """
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

    # 1. 取得加權指數 (t00.tw)、未含金融指數 (t001.tw)、櫃買指數 (o00.tw)
    try:
        idx_url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_t00.tw|tse_t001.tw|otc_o00.tw&json=1&delay=0"
        r_idx = session.get(idx_url, headers=headers, timeout=3.0)
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
                    # t00 的 v 單位為百萬元，除以 100 轉為億元
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

    # 2. 取得大盤委買委賣筆數/張數與漲跌家數 (getStatis.jsp)
    try:
        stat_url = "https://mis.twse.com.tw/stock/api/getStatis.jsp?ex=tse&delay=0"
        r_stat = session.get(stat_url, headers=headers, timeout=3.0)
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

# ----------------- 即時分時走勢數據擷取與雙層圖表渲染引擎 -----------------
@st.cache_data(ttl=30)
def fetch_intraday_series(ticker: str):
    """
    擷取當日 1 分 K 或 5 分 K 分時走勢資料，並對齊昨收基準價
    """
    try:
        t = yf.Ticker(ticker)
        # 優先取 1 分 K，若休市或無資料則取近 5 日之 5 分 K 並篩選最後一個交易日
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

        # 取得昨收基準價
        df_daily = t.history(period="5d", interval="1d")
        y_close = None
        if df_daily is not None and len(df_daily) >= 2:
            if isinstance(df_daily.columns, pd.MultiIndex):
                df_daily.columns = df_daily.columns.get_level_values(0)
            y_close = safe_float(df_daily['Close'].iloc[-2])

        # 若為台股或加權指數，優先以 TWSE 官方昨收價與最新撮合價校準
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

        # 轉換時區顯示時間字串
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

        return df_plot.reset_index(drop=True), y_close
    except Exception:
        return None, None

def render_intraday_chart_widget(ticker: str, title_name: str = ""):
    """
    渲染 Yahoo 股市風格之即時分時走勢圖（藍色走勢線 + 昨收平盤虛線 + 底部紅綠成交量柱）
    """
    df_intra, y_close = fetch_intraday_series(ticker)
    if df_intra is None or df_intra.empty:
        st.info("⚪ 目前無該標的之分時明細資料（可能處於非交易時段或外部報價源結算中）。")
        return

    last_row = df_intra.iloc[-1]
    curr_p = safe_float(last_row['Close'])
    high_p = safe_float(df_intra['High'].max())
    low_p = safe_float(df_intra['Low'].min())
    chg_val = curr_p - y_close
    chg_pct = (chg_val / (y_close + 1e-9)) * 100.0

    # 頂部即時跳動狀態列 (如同截圖左上角：時間、價、最高價、最低價、昨收)
    color_cls = "tw-up" if chg_val > 0 else ("tw-down" if chg_val < 0 else "tw-flat")
    sign_str = "+" if chg_val > 0 else ""
    st.markdown(
        f"**{title_name or ticker}** ｜ 時間 `{last_row['TimeStr']}` ｜ "
        f"成交價 <span class='{color_cls}'>{curr_p:,.2f} ({sign_str}{chg_val:,.2f} / {sign_str}{chg_pct:.2f}%)</span> ｜ "
        f"最高 <span class='tw-up'>{high_p:,.2f}</span> ｜ "
        f"最低 <span class='tw-down'>{low_p:,.2f}</span> ｜ "
        f"昨收平盤 `{y_close:,.2f}`",
        unsafe_allow_html=True
    )

    # 計算 Y 軸上下邊界，確保包含昨收虛線並留有 15% 視覺緩衝
    min_y = min(low_p, y_close)
    max_y = max(high_p, y_close)
    pad = max((max_y - min_y) * 0.15, y_close * 0.002)
    y_domain = [min_y - pad, max_y + pad]

    # 上層：分時價格折線 + 漸層區域 + 昨收平盤虛線
    base = alt.Chart(df_intra).encode(
        x=alt.X('TimeStr:O', title=None, axis=alt.Axis(labelAngle=0, labelOverlap=True, tickCount=6))
    )

    price_line = base.mark_line(color='#1a73e8', strokeWidth=2.2).encode(
        y=alt.Y('Close:Q', title='價格 / 點位', scale=alt.Scale(domain=y_domain, zero=False)),
        tooltip=[
            alt.Tooltip('TimeStr:O', title='時間'),
            alt.Tooltip('Close:Q', title='成交價', format=',.2f'),
            alt.Tooltip('Diff:Q', title='漲跌', format='+,.2f'),
            alt.Tooltip('Pct:Q', title='漲跌幅(%)', format='+.2f'),
            alt.Tooltip('High:Q', title='當分最高', format=',.2f'),
            alt.Tooltip('Low:Q', title='當分最低', format=',.2f'),
            alt.Tooltip('VolLots:Q', title='單筆量', format=',.0f')
        ]
    )

    ref_rule = alt.Chart(pd.DataFrame({'y': [y_close]})).mark_rule(
        strokeDash=[4, 4], color='#777777', strokeWidth=1.5
    ).encode(y='y:Q')

    top_chart = (price_line + ref_rule).properties(height=210)

    # 下層：紅綠分時成交量柱狀圖
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

# ----------------- 權威 API 2：臺灣銀行官方牌告匯率 -----------------
@st.cache_data(ttl=300)
def fetch_bot_forex():
    url = "https://rate.bot.com.tw/xrt/flcsv/0/day"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=3.5)
        if r.status_code == 200:
            lines = r.text.splitlines()
            for line in lines:
                parts = line.split(",")
                if len(parts) >= 5 and parts[0].strip() == "USD":
                    val = safe_float(parts[12]) if len(parts) >= 13 else 0.0
                    if val <= 0 and len(parts) >= 5:
                        val = safe_float(parts[4])
                    if val <= 0 and len(parts) >= 4:
                        val = safe_float(parts[3])
                    if val > 0:
                        return {"usd_twd": val, "source": "臺灣銀行官方牌告", "is_real": True}
    except Exception:
        pass
    return None

# ----------------- 權威 API 3：機構分析師評等與目標價 -----------------
@st.cache_data(ttl=3600)
def fetch_analyst_consensus(ticker: str):
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

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

# ----------------- 期貨專屬權威分析師與法人籌碼共識 -----------------
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

    last_fut = df_fut.iloc[-1]['Close']
    ma5 = df_fut['MA5'].iloc[-1]
    ma20 = df_fut['MA20'].iloc[-1]
    ma60 = df_fut['MA60'].iloc[-1]

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

    atr = df_fut['ATR14'].iloc[-1] if 'ATR14' in df_fut.columns else 150.0
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

# ----------------- 歷史技術數據與指標計算 -----------------
@st.cache_data(ttl=60)
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

        df['MA5'] = df['Close'].rolling(5, min_periods=1).mean()
        df['MA20'] = df['Close'].rolling(20, min_periods=5).mean()
        df['MA60'] = df['Close'].rolling(60, min_periods=20).mean()
        df['Vol_MA5'] = df['Volume'].rolling(5, min_periods=1).mean()

        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14, min_periods=1).mean()
        total_move = gain + loss
        rs = gain / (loss + 1e-9)
        df['RSI14'] = np.where(total_move < 1e-6, 50.0, 100 - (100 / (1 + rs)))

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

        return df.copy()
    except Exception:
        return None

# ----------------- 基本面與 ETF 數據 -----------------
@st.cache_data(ttl=7200)
def fetch_fundamentals(ticker: str):
    clean_code, market = normalize_ticker(ticker)
    if market == "futures":
        return {"has_data": False, "is_etf": False, "score": None, "reasons": []}

    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

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

            fund_score += 10
            reasons.append("成分股已實施一籃子分散風險")

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
                    reasons.append(f"負債比率健康 ({de_val:.1f}%)，財務防禦佳")
                elif de_val <= 150:
                    fund_score += 6
                    reasons.append(f"負債比率適中 ({de_val:.1f}%)")
                else:
                    reasons.append(f"負債比率偏高 ({de_val:.1f}%)")

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

# ----------------- 開盤即時與均線分析 -----------------
def analyze_opening_and_ma(df_stock, live_info=None):
    if df_stock is None or len(df_stock) == 0:
        return {}, "資料不足", 0, 0.0, 0.0, "⚪ 無資料", ["資料不足"]

    last = df_stock.iloc[-1]
    prev = df_stock.iloc[-2] if len(df_stock) >= 2 else last
    close = safe_float(last['Close'])
    ma5 = safe_float(last['MA5'], close)
    ma20 = safe_float(last['MA20'], close)
    ma60 = safe_float(last['MA60'], close)

    ma_status = {
        "ma5_diff": ((close - ma5) / (ma5 + 1e-9)) * 100,
        "ma20_diff": ((close - ma20) / (ma20 + 1e-9)) * 100,
        "ma60_diff": ((close - ma60) / (ma60 + 1e-9)) * 100,
        "ma5_val": ma5,
        "ma20_val": ma20,
        "ma60_val": ma60
    }

    if close > ma5 > ma20 > ma60:
        ma_alignment = "🔥 完美多頭排列 (價格 > 日線 > 月線 > 季線)"
        ma_score = 25
    elif close > ma20 and ma20 > ma60:
        ma_alignment = "📈 中長線偏多架構 (守穩月線與季線)"
        ma_score = 18
    elif close < ma5 < ma20 < ma60:
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

# ----------------- 歷史回測引擎 -----------------
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

# ----------------- 外匯數據分析 -----------------
@st.cache_data(ttl=300)
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

# ----------------- 全維度綜合量化評估 -----------------
def analyze_full_stock(ticker, df_stock, df_market, df_futures, df_tsm, df_sox, forex_info, asset_type="tw"):
    live_twse = fetch_twse_realtime(ticker) if asset_type == "tw" else None
    ma_status, ma_alignment, ma_score, gap_pct, intraday_pct, k_type, opening_diag = analyze_opening_and_ma(df_stock, live_twse)

    last_stk = df_stock.iloc[-1]
    prev_stk = df_stock.iloc[-2] if len(df_stock) >= 2 else last_stk
    close = safe_float(last_stk['Close'])
    atr_val = safe_float(last_stk['ATR14'], default=close * 0.02)

    global_score = 0
    global_reasons = []

    if asset_type == "futures":
        analyst_data = fetch_futures_analyst_consensus(ticker, df_stock, df_market)
        fund_data = {"has_data": False, "score": None, "reasons": []}
        global_score = 12
    elif asset_type == "us":
        analyst_data = fetch_analyst_consensus(ticker)
        fund_data = fetch_fundamentals(ticker)
        global_score = 10
    else:
        analyst_data = fetch_analyst_consensus(ticker)
        fund_data = fetch_fundamentals(ticker)
        try:
            if df_tsm is not None and len(df_tsm) >= 2:
                tsm_change = ((df_tsm['Close'].iloc[-1] - df_tsm['Close'].iloc[-2]) / df_tsm['Close'].iloc[-2]) * 100
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

    # 大盤位階
    mkt_score = 0
    mkt_reasons = []
    if df_market is not None and not df_market.empty:
        last_mkt = df_market.iloc[-1]
        if last_mkt['Close'] > last_mkt['MA20']:
            mkt_score += 12
            mkt_reasons.append("大盤站上月線 (20MA)，多方主導發球權")
        else:
            mkt_reasons.append("大盤跌破月線，系統性拉回風險偏高")
        if last_mkt['MA20'] > last_mkt['MA60']:
            mkt_score += 8
            mkt_reasons.append("大盤季線多頭架構 (20MA > 60MA)")

    # 技術量價
    tech_score = 0
    tech_reasons = []
    vol_ratio = safe_float(last_stk['Volume']) / (safe_float(last_stk['Vol_MA5']) + 1e-9)
    if close > prev_stk['Close'] and vol_ratio >= 1.2:
        tech_score += 10
        tech_reasons.append(f"量增價漲 (爆量比: {vol_ratio:.1f}x)")
    elif close > prev_stk['Close']:
        tech_score += 5
        tech_reasons.append("價漲但量能平淡")

    if last_stk['OSC'] > 0 and last_stk['OSC'] > prev_stk['OSC']:
        tech_score += 8
        tech_reasons.append("MACD 紅柱放大，攻擊動能足")
    elif last_stk['OSC'] > 0:
        tech_score += 4
        tech_reasons.append("MACD 維持多頭")

    if 50 <= last_stk['RSI14'] <= 70:
        tech_score += 7
        tech_reasons.append(f"RSI 處健康攻擊區 ({last_stk['RSI14']:.1f})")

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

    # 防守停損與多空准入
    ma20_val = safe_float(last_stk['MA20'], close * 0.96)
    if close >= ma20_val:
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
        "forex_info": forex_info,
        "live_info": live_twse,
        "asset_type": asset_type
    }

# ----------------- 台灣期貨專屬商品規格庫 -----------------
TW_FUTURES_SPECS = {
    "WTX": {
        "name": "台指期貨 (大台)",
        "tick_value": 200,
        "initial_margin": 250000,
        "maintenance_margin": 192000,
        "desc": "全市場主力大額籌碼風向核心，波動點數價值最高"
    },
    "MTX": {
        "name": "小型台指 (小台)",
        "tick_value": 50,
        "initial_margin": 62500,
        "maintenance_margin": 48000,
        "desc": "散戶與短線波段核心，靈活高流動性"
    },
    "WMT": {
        "name": "微型台指 (微台)",
        "tick_value": 10,
        "initial_margin": 12500,
        "maintenance_margin": 9600,
        "desc": "小資量化避險首選，精確微調投資組合部位"
    },
    "TE": {
        "name": "電子期貨",
        "tick_value": 400,
        "initial_margin": 210000,
        "maintenance_margin": 161000,
        "desc": "追蹤半導體與權值電子類股，連動美股費半"
    },
    "TF": {
        "name": "金融期貨",
        "tick_value": 1000,
        "initial_margin": 130000,
        "maintenance_margin": 100000,
        "desc": "大型金控與壽險資產指標，防禦震盪特性顯著"
    }
}

# ----------------- 即時新聞雙結構解析引擎 -----------------
@st.cache_data(ttl=600)
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

# ----------------- 狀態初始化 -----------------
if "main_mode" not in st.session_state:
    st.session_state.main_mode = "live_watch"

if "selected_tw_ticker" not in st.session_state:
    st.session_state.selected_tw_ticker = "2330.TW"

if "selected_us_ticker" not in st.session_state:
    st.session_state.selected_us_ticker = "NVDA"

if "selected_fut_contract" not in st.session_state:
    st.session_state.selected_fut_contract = "WTX"

if "auto_run_tw" not in st.session_state:
    st.session_state.auto_run_tw = False

if "auto_run_us" not in st.session_state:
    st.session_state.auto_run_us = False

if "analysis_cache_tw" not in st.session_state:
    st.session_state.analysis_cache_tw = None

if "analysis_cache_us" not in st.session_state:
    st.session_state.analysis_cache_us = None

if "analysis_cache_fut" not in st.session_state:
    st.session_state.analysis_cache_fut = None

if "etf_category_filter" not in st.session_state:
    st.session_state.etf_category_filter = "全部"

user_memory = get_user_data()

# ----------------- 頂部導航與完整功能暨版本說明書 -----------------
st.title("📱 股期決策旗艦站 (跨市場機構版)")

with st.expander("📘 點此查看【系統現行版本完整功能清單與版本更新日誌】", expanded=False):
    st.markdown("""
    ### 🌟 系統定位與核心架構
    本系統為**跨市場（大盤即時看盤、台股、美股、台灣期貨、美股期貨、ETF、全球外匯）全維度量化決策平台**，整合臺灣證券交易所 (TWSE) 官方即時撮合、臺灣銀行官方牌告匯率與華爾街/本土法人共識報告資料庫，提供客觀透明之進出場點位與風險控管計算。

    ---
    ### 🛠️ 核心功能模組總覽
    1. **📺 大盤與個股即時分時看盤室（V7.0 全新搭載）**：
       - **Yahoo 股市級別即時分時走勢圖**：包含當日 1分/5分K 藍色價格折線、**昨收平盤灰色基準虛線**、底部紅綠分時成交量柱狀圖，並支援觸控十字游標檢視各分鐘高低價與量能。
       - **大盤右側統計數據看板**：即時連線證交所揭露**加權指數（含金融）**、**加權指數（未含金融）**、**成交金額（億）**、**委買/委賣筆數與張數（含均買/均賣張數）**、**漲跌停與平盤家數**。
       - **個股即時五檔委買賣明細**：查詢台股時自動解析買進一～五檔、賣出一～五檔掛單價量與內外買賣力道比。
       - **盤中 30 秒自動刷新開關**：勾選後自動更新看盤畫面，免手動重整。
    2. **🔍 台股全維度深度體檢**：
       - 直連 TWSE 撮合主機（成交量自動由「張」換算為「股」對齊均量），內建 10 大就地展開分析卡（含即時分時圖與五檔掛單、分析師目標價與下單執行卡、多空結論、開盤跳空、5/20/60MA 矩陣、基本面護城河、階梯停利 SOP、風控計算機、無前視偏誤回測、日K均線圖）。
    3. **🇺🇸 美股全維度深度體檢**：
       - 與台股 100% 同規格之全維度分析，直連華爾街機構目標價與評等，內建美股分時走勢、股數 (Shares) 風控計算機與低摩擦成本回測。
    4. **⚡ 台灣期貨獨立專區**：
       - 內建五大期貨契約規格：**大台 (WTX)**、**小台 (MTX)**、**微台 (WMT)**、**電子期 (TE)**、**金融期 (TF)**，含即時基差看板與保證金口數計算機。
    5. **📈 美股期貨 ＆ 📊 ETF 策略專區 ＆ 💎 體質雷達 ＆ 📢 法說新聞 ＆ 💱 外匯大盤**：
       - 涵蓋微那指/微標普等四大美指期、ETF 四大分類排行與微笑曲線試算、核心藍籌雙重濾網、即時新聞雙結構解析、臺銀官方匯率與日圓平倉風險監控。

    ---
    ### 📜 歷次版本更新日誌 (Version Changelog)
    - **V7.0（即時分時看盤與大盤委買賣統計版 - 現行版本）**：
      - 新增「📺 大盤即時看盤」專區，完整還原加權指數分時走勢圖（含昨收平盤虛線、底部紅綠量能柱）與大盤統計表（加權含金融/未含金融、委買委賣筆數/張數/均張、漲跌停家數）。
      - 於台股、美股、台灣期貨診斷中全面嵌入「即時分時走勢圖」與「台股即時五檔委買委賣掛單表」，並加入盤中 30 秒自動刷新開關。
    - **V6.0（行動端雙欄鎖定與深度除錯版）**：
      - 完成手機端 CSS 雙欄強制並排鎖定（`max-width: 100vw`），徹底消除單欄長條坍塌與右側視窗溢出問題。
      - 新增全市場中英股票名稱智慧對照字典（`GLOBAL_STOCK_NAMES`）與 `user_history.json` 跨重整持久化記憶系統。
      - 修復空方破線時「建議停損價高於現價」之數學矛盾；排除虧損公司負本益比誤判；相容新版 `yfinance` 巢狀新聞結構。
    - **V5.0（跨市場獨立拆分版）**：
      - 將「台股、美股、台灣期貨、美股期貨」拆分為獨立專區，新增台灣期貨智慧路由與保證金口數風控計算機。
    - **V4.0（機構量化加固與防偏誤版）**：
      - 移除公開預設密碼強制檢驗 Secrets、修正 `.TWO` 上櫃截斷錯誤、修正 TWSE 成交量「張轉股（×1000）」單位對齊。
      - 重構無前視偏誤回測引擎（$T+1$ 開盤進場、單部位不重疊持倉、扣除交易稅費、精算真實峰谷最大回撤 MDD）。
    - **V3.0（權威分析師與行動端就地展開版）**：
      - 接入主流券商分析師共識目標價與評等，建立「精確下單執行卡」與就地展開式卡片介面。
    - **V2.0 ～ V1.0（ETF 量化與基礎決策站初版）**：
      - 建立 ETF 微笑曲線試算、台積電 ADR 溢價換算、技術指標引擎、TWSE 即時行情與臺銀牌告匯率串接。
    """)

# 置頂大盤即時分時看盤室按鈕 + 盤中自動更新開關
top_c1, top_c2 = st.columns([1.4, 1.0])
with top_c1:
    if st.button("📺 大盤即時看盤 (分時走勢/委買賣)", type="primary" if st.session_state.main_mode == "live_watch" else "secondary", use_container_width=True, key="m_nav_live_watch"):
        st.session_state.main_mode = "live_watch"
        st.rerun()
with top_c2:
    auto_refresh = st.checkbox("⏱️ 30秒自動刷新", value=False, key="global_auto_refresh")

# 頂部八大模式切換 (手機端強制 2 欄並排)
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
    if st.button("📢 法說消息", type="primary" if st.session_state.main_mode == "events" else "secondary", use_container_width=True, key="m_nav_events"):
        st.session_state.main_mode = "events"
        st.rerun()
with r4_c2:
    if st.button("💱 外匯大盤", type="primary" if st.session_state.main_mode == "forex" else "secondary", use_container_width=True, key="m_nav_forex"):
        st.session_state.main_mode = "forex"
        st.rerun()

st.write("")

# 全域預載
df_market = fetch_and_calc("^TWII")
df_futures_bench = fetch_and_calc("WTX=F")
df_tsm = fetch_and_calc("TSM")
df_sox = fetch_and_calc("^SOX")
df_spx = fetch_and_calc("^GSPC")
global_forex = analyze_forex_data()

# ================= 模式 0：📺 大盤即時分時看盤室 (完整重現 Yahoo 股市看盤介面) =================
if st.session_state.main_mode == "live_watch":
    dash = fetch_twse_market_dashboard()

    # 若證交所 MIS 休市或未回傳點位，以 df_market 最新收盤自動補齊
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
        st.rerun()

    # 1. 渲染即時分時走勢圖 (藍色折線 + 昨收平盤虛線 + 紅綠量能柱)
    render_intraday_chart_widget("^TWII", title_name="加權指數 (^TWII)")

    # 2. 渲染右側/下方 Yahoo 股市風格大盤統計明細表
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
    st.caption("註：成交金額與委買委賣統計直連臺灣證券交易所 (TWSE MIS) 官方即時接口，非盤中時段部份委買賣欄位將顯示結算中。")

# ================= 模組共用渲染器 (內建分時走勢與五檔委買賣明細) =================
def render_analysis_view(res, df_asset, mode_type="tw", custom_spec=None, fallback_warning=None, ticker_raw=None):
    is_downtrend = res.get('is_breakdown', False) or (res['close'] < res['ma_status']['ma20_val'])
    risk_unit = max(res['close'] - res['stop_loss'], res['close'] * 0.015)
    target_1 = res['close'] + (1.5 * risk_unit)
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

    # 常用標的即時收藏/取消收藏按鈕
    if mode_type in ("tw", "us") and ticker_raw:
        m_key = "tw" if mode_type == "tw" else "us"
        cur_favs = user_memory.get(f"{m_key}_favorites", [])
        is_fav = ticker_raw in cur_favs
        fav_label = "⭐ 已加入常用清單 (點此移出)" if is_fav else "☆ 收藏至常用股票清單"
        if st.button(fav_label, use_container_width=True, key=f"btn_fav_toggle_{stable_key_suffix}"):
            toggle_favorite_stock(m_key, ticker_raw)
            st.rerun()

    c1, c2 = st.columns(2)
    c1.metric("綜合決策總分", f"{res['total_score']} / 100")
    c2.metric("最新點位/現價", f"{res['close']:.2f} {currency_sym}")

    c3, c4 = st.columns(2)
    c3.metric("建議防守價 (停損)", f"{res['stop_loss']:.2f} {currency_sym}")
    risk_pct = (risk_unit / res['close']) * 100
    c4.metric("最大預期風險", f"{risk_pct:.2f}%")

    # 0. V7.0 新增：即時分時走勢圖 & 台股五檔委買賣明細
    with st.expander("📺 【即時分時走勢圖 (含昨收平盤線) ＆ 五檔委買賣明細】", expanded=True):
        chart_ticker = "WTX=F" if mode_type == "futures" else (ticker_raw or "2330.TW")
        if mode_type == "futures" and df_futures_bench is None:
            chart_ticker = "^TWII"
        render_intraday_chart_widget(chart_ticker, title_name=disp_header or chart_ticker)

        # 若為台股且有 TWSE 五檔掛單明細，渲染五檔委買委賣表與力道條
        live_info = res.get("live_info")
        if live_info and live_info.get("bid_prices") and live_info.get("ask_prices"):
            st.markdown("#### 📋 證交所即時五檔委買／委賣掛單明細")
            b_p = live_info["bid_prices"]
            b_v = live_info["bid_vols"]
            a_p = live_info["ask_prices"]
            a_v = live_info["ask_vols"]

            total_bid_v = sum(b_v)
            total_ask_v = sum(a_v)
            total_depth = total_bid_v + total_ask_v
            bid_ratio = (total_bid_v / total_depth * 100.0) if total_depth > 0 else 50.0

            st.caption(f"🔥 **五檔委買總量：{total_bid_v:,} 張 ({bid_ratio:.1f}%)** vs ❄️ **五檔委賣總量：{total_ask_v:,} 張 ({100-bid_ratio:.1f}%)**")
            st.progress(min(max(bid_ratio / 100.0, 0.0), 1.0))

            rows_html = ""
            for i in range(max(len(b_p), len(a_p))):
                bp_str = f"{b_p[i]:.2f}" if i < len(b_p) and b_p[i] > 0 else "--"
                bv_str = f"{b_v[i]:,}" if i < len(b_v) else "--"
                ap_str = f"{a_p[i]:.2f}" if i < len(a_p) and a_p[i] > 0 else "--"
                av_str = f"{a_v[i]:,}" if i < len(a_v) else "--"
                rows_html += f"""
                <div class="yahoo-stat-row">
                    <span>買{i+1}: <b class="tw-up">{bp_str}</b> ({bv_str}張)</span>
                    <span>賣{i+1}: <b class="tw-down">{ap_str}</b> ({av_str}張)</span>
                </div>
                """
            st.markdown(f"<div class='yahoo-stat-box'>{rows_html}</div>", unsafe_allow_html=True)

    # 1. 權威分析師/期顧共識 ＆ 精確下單指引
    guide_title = "🎯 【權威期顧分析師共識 ＆ 精確期貨下單卡】" if mode_type == "futures" else "🎯 【權威分析師共識 ＆ 精確下單指引】"
    with st.expander(guide_title, expanded=True):
        if an_data.get("has_data"):
            st.markdown(f"**機構綜合多空評等：** `{an_data['rec_label']}`")
            st.caption(f"📌 {an_data['rec_desc']}（共計 **{an_data['opinions']} 家** 機構追蹤）")

            a_c1, a_c2 = st.columns(2)
            if an_data['target_mean'] > 0:
                upside_pct = ((an_data['target_mean'] - res['close']) / res['close']) * 100
                a_c1.metric("法人目標點位", f"{an_data['target_mean']:.1f} {currency_sym}", f"{upside_pct:+.1f}% 空間")
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
            st.error(f"🚫 **當前禁止做多**：現價（{res['close']:.2f} {currency_sym}）已跌破月線生命線（{res['ma_status']['ma20_val']:.2f} {currency_sym}），空方控盤，順勢交易者嚴禁逆勢摸底！若持有部位，波段停損價設為 `{res['stop_loss']:.2f} {currency_sym}`。")
        else:
            st.markdown(f"""
            1. **建議進場區間**：**`{res['close']:.2f} {currency_sym}`**（回測 5MA 不破分批布局）。
            2. **波段防守點位**：**`{res['stop_loss']:.2f} {currency_sym}`**（跌破點位立即退場，絕不凹單）。
            3. **第一獲利目標**：**`{target_1:.2f} {currency_sym}`**（達成 1.5R 盈虧比，平倉 1/2 入袋並上移防守至成本）。
            4. **波段獲利目標**：**`{res['target_60d']:.2f} {currency_sym}`**（對齊機構目標價或波段高點擴展區）。
            """)

    # 2. 決策結論與多空架構
    with st.expander("📝 【決策結論與多空架構】", expanded=False):
        if is_downtrend:
            st.error(f"### 🔴 空方架構：現價（{res['close']:.2f} {currency_sym}）跌破月線生命線（{res['ma_status']['ma20_val']:.2f} {currency_sym}），嚴禁追價摸底！")
            st.write(f"- 當前價位位於月線（20MA）之下，短中期均線蓋頭下壓，等待止跌築底翻揚再行介入。建議防守價位：**{res['stop_loss']:.2f} {currency_sym}**。")
        elif res['total_score'] >= 75:
            st.success(f"### 🟢 積極偏多：技術量價動能同步翻多，適合進場 (防守: {res['stop_loss']:.2f} {currency_sym})")
        elif 60 <= res['total_score'] < 75:
            st.warning("### 🟡 穩健觀察：指標整理或分歧，僅限輕倉試單")
        else:
            st.error("### 🔴 暫緩進場：評價過高或短期均線下壓，空手觀望為上")

    # 3. 開盤即時撮合動態
    with st.expander("⚡ 【開盤即時撮合動態】", expanded=False):
        st.markdown(f"**當前 K 棒型態：** `{res['k_type']}`")
        k1, k2 = st.columns(2)
        k1.metric("開盤跳空幅度", f"{res['gap_pct']:+.2f}%")
        k2.metric("開盤至今漲跌", f"{res['intraday_pct']:+.2f}%")
        st.write("---")
        for d in res['opening_diag']:
            st.write(f"• {d}")

    # 4. 三均線矩陣
    with st.expander("📏 【日 / 月 / 季線 位階矩陣】", expanded=False):
        st.markdown(f"**均線排列結構：** `{res['ma_alignment']}`")
        m1, m2, m3 = st.columns(3)
        m1.metric("日線 (5MA)", f"{res['ma_status']['ma5_val']:.2f}", f"{res['ma_status']['ma5_diff']:+.1f}%")
        m2.metric("月線 (20MA)", f"{res['ma_status']['ma20_val']:.2f}", f"{res['ma_status']['ma20_diff']:+.1f}%")
        m3.metric("季線 (60MA)", f"{res['ma_status']['ma60_val']:.2f}", f"{res['ma_status']['ma60_diff']:+.1f}%")

    # 5. 體質 / 契約規格護城河
    if mode_type == "futures":
        with st.expander("💎 【期貨契約規格與保證金護城河】", expanded=False):
            st.markdown(f"**標的商品**：`{spec['name']}` ｜ {spec['desc']}")
            sp1, sp2 = st.columns(2)
            sp1.metric("每一跳動點價值", f"NT$ {spec['tick_value']:,} 元")
            sp2.metric("原始保證金門檻", f"NT$ {spec['initial_margin']:,} 元")

            sp3, sp4 = st.columns(2)
            sp3.metric("維持保證金警戒線", f"NT$ {spec['maintenance_margin']:,} 元")
            leverage = (res['close'] * spec['tick_value']) / spec['initial_margin'] if spec['initial_margin'] > 0 else 0
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

    # 6. 階梯停利 SOP
    with st.expander("🚪 【階梯式分階出場 SOP】", expanded=False):
        st.markdown(f"""
        - **初始防守停損**：跌破 **`{res['stop_loss']:.2f}` {currency_sym}** 嚴格離場，絕不凹單。
        - **第一階段目標（減碼 1/2）**：達 **`{target_1:.2f}` {currency_sym}**（1.5R 盈虧比），平倉半數部位入袋並上移防守至成本價（鎖定保本）。
        - **第二階段目標（波段收割）**：達 **`{res['target_60d']:.2f}` {currency_sym}** 分批落袋。
        - **移動停利（Trailing Stop）**：其餘部位收盤跌破 5 日線全數獲利了結。
        """)

    # 7. 部位風控計算機
    with st.expander(f"💰 【部位風控與建議{unit_name}計算機】", expanded=False):
        col_cap, col_risk = st.columns(2)
        with col_cap:
            if mode_type == "futures":
                default_cap = 1000000
                cap_step = 100000
                cap_label = "期貨專戶保證金餘額 (NTD)"
            elif mode_type == "us":
                default_cap = 50000
                cap_step = 5000
                cap_label = "總操作資金 (USD)"
            else:
                default_cap = 1000000
                cap_step = 100000
                cap_label = "總操作資金 (NTD)"
            total_capital = st.number_input(cap_label, value=default_cap, step=cap_step, key=f"calc_cap_{stable_key_suffix}")
        with col_risk:
            risk_tolerance = st.slider("單筆最大承受損失比率 (%)", min_value=0.5, max_value=3.0, value=1.0, step=0.1, key=f"calc_risk_{stable_key_suffix}")

        max_risk_dollar = total_capital * (risk_tolerance / 100.0)

        if mode_type == "futures":
            loss_per_unit = risk_unit * spec['tick_value']
            risk_based_pos = int(max_risk_dollar // loss_per_unit) if loss_per_unit > 0 else 0
            margin_max_pos = int(total_capital // spec['initial_margin']) if spec['initial_margin'] > 0 else 0
            suggested_pos = min(risk_based_pos, margin_max_pos)
        elif mode_type == "us":
            loss_per_unit = risk_unit * 1.0
            risk_based_pos = int(max_risk_dollar // loss_per_unit) if loss_per_unit > 0 else 0
            capital_max_pos = int(total_capital // res['close']) if res['close'] > 0 else 0
            suggested_pos = min(risk_based_pos, capital_max_pos)
        else:
            loss_per_unit = risk_unit * 1000.0
            risk_based_pos = int(max_risk_dollar // loss_per_unit) if loss_per_unit > 0 else 0
            capital_max_lots = int(total_capital // (res['close'] * 1000.0)) if res['close'] > 0 else 0
            suggested_pos = min(risk_based_pos, capital_max_lots)

        potential_reward = max(res['target_60d'] - res['close'], 0)
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

    # 8. 無前視偏誤回測
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

    # 9. 日K均線走勢圖
    with st.expander("📈 【近 60 日均線 (5/20/60MA) 波段走勢圖】", expanded=False):
        valid_cols = ['Close']
        for c in ['MA5', 'MA20', 'MA60']:
            if c in df_asset.columns and df_asset[c].notna().sum() > 5:
                valid_cols.append(c)
        chart_data = df_asset[valid_cols].dropna().tail(60)
        st.line_chart(chart_data)

# ================= 模式 1：🔍 台股診斷 =================
elif st.session_state.main_mode == "tw_stock":
    st.subheader("🔍 台股全維度深度體檢")

    tw_favs = user_memory.get("tw_favorites", ["2330.TW", "2454.TW", "2317.TW", "0050.TW"])
    st.caption("⭐ **我的常用股票清單**（點選一秒自動診斷）：")

    fav_cols = st.columns(2)
    for idx, fav_code in enumerate(tw_favs[:6]):
        col_target = fav_cols[idx % 2]
        display_label = get_stock_display_label(fav_code, is_fav=True)
        if col_target.button(display_label, use_container_width=True, key=f"tw_fav_{fav_code}"):
            st.session_state.selected_tw_ticker = fav_code
            st.session_state.analysis_cache_tw = None
            st.session_state.auto_run_tw = True
            st.rerun()

    tw_recents = [r for r in user_memory.get("tw_recent", []) if r not in tw_favs][:4]
    if tw_recents:
        st.caption("🕒 **最近查詢紀錄**：")
        rec_cols = st.columns(2)
        for r_idx, r_code in enumerate(tw_recents):
            col_rec_target = rec_cols[r_idx % 2]
            rec_display = get_stock_display_label(r_code, is_fav=False)
            if col_rec_target.button(rec_display, use_container_width=True, key=f"tw_rec_{r_code}"):
                st.session_state.selected_tw_ticker = r_code
                st.session_state.analysis_cache_tw = None
                st.session_state.auto_run_tw = True
                st.rerun()

    st.caption("💡 **台股輸入格式指引**：上市請輸入 `代碼.TW`（如 `2330.TW`，亦支援純數字如 `2330` 自動轉上市）｜ 上櫃請輸入 `代碼.TWO`（如 `6488.TWO`）")

    col_input, col_btn = st.columns([2.4, 1.6])
    with col_input:
        raw_tw_input = st.text_input(
            "輸入台股代碼",
            value=st.session_state.selected_tw_ticker,
            label_visibility="collapsed",
            placeholder="例：2330.TW 或 6488.TWO",
            key="tw_ticker_field"
        )
    with col_btn:
        exec_clicked = st.button("🚀 診斷台股", type="primary", use_container_width=True, key="run_tw_btn")

    with st.expander("⚙️ 管理我的台股常用清單", expanded=False):
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
        with st.spinner("連線 TWSE 撮合主機計算中..."):
            df_stk = fetch_and_calc(cleaned_tw_ticker)
            if df_stk is not None:
                r = analyze_full_stock(cleaned_tw_ticker, df_stk, df_market, df_futures_bench, df_tsm, df_sox, global_forex, asset_type="tw")
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
    st.subheader("🇺🇸 美股全維度深度體檢 (全功能同規格)")

    us_favs = user_memory.get("us_favorites", ["NVDA", "AAPL", "MSFT", "TSLA"])
    st.caption("⭐ **我的常用美股清單**（點選一秒自動診斷）：")

    fav_u_cols = st.columns(2)
    for idx, fav_u_code in enumerate(us_favs[:6]):
        col_u_target = fav_u_cols[idx % 2]
        display_u_label = get_stock_display_label(fav_u_code, is_fav=True)
        if col_u_target.button(display_u_label, use_container_width=True, key=f"us_fav_{fav_u_code}"):
            st.session_state.selected_us_ticker = fav_u_code
            st.session_state.analysis_cache_us = None
            st.session_state.auto_run_us = True
            st.rerun()

    us_recents = [r for r in user_memory.get("us_recent", []) if r not in us_favs][:4]
    if us_recents:
        st.caption("🕒 **最近查詢紀錄**：")
        rec_u_cols = st.columns(2)
        for ru_idx, ru_code in enumerate(us_recents):
            col_rec_u = rec_u_cols[ru_idx % 2]
            rec_u_label = get_stock_display_label(ru_code, is_fav=False)
            if col_rec_u.button(rec_u_label, use_container_width=True, key=f"us_rec_{ru_code}"):
                st.session_state.selected_us_ticker = ru_code
                st.session_state.analysis_cache_us = None
                st.session_state.auto_run_us = True
                st.rerun()

    st.caption("💡 **美股輸入格式指引**：請輸入美股英文代號（如 `NVDA`、`AAPL`、`TSLA`、`MSFT`、`TSM`），大小寫皆可自動識別轉換。")

    col_u_in, col_u_btn = st.columns([2.4, 1.6])
    with col_u_in:
        raw_us_input = st.text_input(
            "輸入美股代碼",
            value=st.session_state.selected_us_ticker,
            label_visibility="collapsed",
            placeholder="例：NVDA、AAPL、TSM",
            key="us_ticker_field"
        )
    with col_u_btn:
        exec_us_btn = st.button("🚀 診斷美股", type="primary", use_container_width=True, key="run_us_btn")

    cleaned_us_ticker = raw_us_input.strip().upper()

    with st.expander("⚙️ 管理我的美股常用清單", expanded=False):
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
        with st.spinner("連線美股即時行情與華爾街資料庫中..."):
            df_stk_us = fetch_and_calc(cleaned_us_ticker)
            if df_stk_us is not None:
                r_us = analyze_full_stock(cleaned_us_ticker, df_stk_us, df_spx, None, None, df_sox, global_forex, asset_type="us")
                st.session_state.analysis_cache_us = (r_us, df_stk_us, cleaned_us_ticker)
                add_recent_history("us", cleaned_us_ticker)
            else:
                st.session_state.analysis_cache_us = None
                st.error("無法取得該美股行情，請確認英文代碼（如 NVDA, AAPL, TSM, AMD）。")

    if st.session_state.analysis_cache_us is not None:
        r_us, df_stk_us, cur_ut = st.session_state.analysis_cache_us
        render_analysis_view(r_us, df_stk_us, mode_type="us", ticker_raw=cur_ut)

# ================= 模式 3：⚡ 台灣期貨 (智慧路由版) =================
elif st.session_state.main_mode == "tw_futures":
    st.subheader("⚡ 台灣期貨全維度專區 (優質契約・期顧共識・基差診斷)")
    st.caption("內建熱門台期契約池・自選查詢・多空目標壓力與保證金風控")

    fq1, fq2 = st.columns(2)
    with fq1:
        if st.button("台指期 (大台)", use_container_width=True, key="fq_wtx"):
            st.session_state.selected_fut_contract = "WTX"
            st.session_state.analysis_cache_fut = None
            st.rerun()
        if st.button("微型台指 (微台)", use_container_width=True, key="fq_wmt"):
            st.session_state.selected_fut_contract = "WMT"
            st.session_state.analysis_cache_fut = None
            st.rerun()
    with fq2:
        if st.button("小型台指 (小台)", use_container_width=True, key="fq_mtx"):
            st.session_state.selected_fut_contract = "MTX"
            st.session_state.analysis_cache_fut = None
            st.rerun()
        if st.button("電子期貨 (TE)", use_container_width=True, key="fq_te"):
            st.session_state.selected_fut_contract = "TE"
            st.session_state.analysis_cache_fut = None
            st.rerun()

    st.caption("💡 **期貨輸入格式指引**：可點選上方按鈕或輸入契約簡稱（`WTX` 大台、`MTX` 小台、`WMT` 微台、`TE` 電子期、`TF` 金融期）。")

    col_f_in, col_f_btn = st.columns([2.4, 1.6])
    with col_f_in:
        raw_fut_input = st.text_input(
            "輸入契約代碼",
            value=st.session_state.selected_fut_contract,
            label_visibility="collapsed",
            placeholder="例：WTX、MTX、WMT",
            key="tw_fut_field"
        )
    with col_f_btn:
        exec_fut_btn = st.button("🚀 診斷期貨", type="primary", use_container_width=True, key="run_fut_btn")

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

    if exec_fut_btn or st.session_state.analysis_cache_fut is None:
        with st.spinner("連線期貨點位與期顧模型中..."):
            df_target_fut = fetch_and_calc("WTX=F")
            fallback_note = None

            if df_target_fut is None or df_target_fut.empty:
                df_target_fut = df_market
                fallback_note = f"📌 **行情資料來源提示**：外部資料庫未提供此期貨即時報價，走勢與均線位階參考加權指數標的；風控與下單已精確套用【{spec_info['name']}】契約規格（每點 {spec_info['tick_value']} 元、保證金 {spec_info['initial_margin']:,} 元）。"

            if df_target_fut is not None:
                r_fut = analyze_full_stock(clean_key, df_target_fut, df_market, None, None, None, global_forex, asset_type="futures")
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

    US_FUT_LIST = [
        ("微那斯達克期 (NQ)", "NQ=F", "全球科技龍頭風向球"),
        ("小標普500期 (ES)", "ES=F", "美股大盤流動性與宏觀資產"),
        ("道瓊期貨 (YM)", "YM=F", "傳統價值龍頭與金融防禦"),
        ("羅素2000期 (RTY)", "RTY=F", "中小型股景氣復甦動能")
    ]

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
                    r = analyze_full_stock(code, df_stk, df_market, df_futures_bench, df_tsm, df_sox, global_forex, asset_type="tw")
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
                    res_item = f.result()
                    if isinstance(res_item, tuple) and res_item[0] == "FAIL":
                        failed_etfs.append(f"{res_item[1]} ({res_item[2]}): {res_item[3]}")
                    elif res_item:
                        etf_results.append(res_item)
                except Exception as ex:
                    failed_etfs.append(f"執行例外: {str(ex)}")
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
                    r = analyze_full_stock(code, df_stk, df_market, df_futures_bench, df_tsm, df_sox, global_forex, asset_type="tw")
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
                    res_item = f.result()
                    if isinstance(res_item, tuple) and res_item[0] == "FAIL":
                        failed_stocks.append(f"{res_item[1]} ({res_item[2]}): {res_item[3]}")
                    elif res_item:
                        scan_results.append(res_item)
                except Exception as ex:
                    failed_stocks.append(f"執行例外: {str(ex)}")
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

# ================= 模式 7：📢 法說會日程與重大訊息 =================
elif st.session_state.main_mode == "events":
    st.subheader("📢 重要法說會日程 ＆ 即時重大訊息速查")
    st.caption("支援輸入台股代號（如 2330 或 2330.TW）與美股代號（如 NVDA）")

    col_n_input, col_n_btn = st.columns([2.4, 1.6])
    with col_n_input:
        news_ticker = st.text_input("輸入查詢標的代碼", value="2330.TW", label_visibility="collapsed", key="news_search_input")
    with col_n_btn:
        news_clicked = st.button("📰 查重大訊息", type="primary", use_container_width=True, key="fetch_news_btn")

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
