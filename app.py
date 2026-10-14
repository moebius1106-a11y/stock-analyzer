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
import html
import threading
import re
import csv
import io
import logging
import hmac
import hashlib
from urllib.parse import quote
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

# ----------------- 系統日誌設定 (消除 Exception: pass，明確錯誤分類) -----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(filename)s:%(lineno)d) %(message)s"
)
logger = logging.getLogger("QuantStation")

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

    /* 手機端強制維持雙欄/多欄等比並排 */
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

    div.stButton, div[data-testid="stFormSubmitButton"] {
        width: 100% !important;
        min-width: 0 !important;
        max-width: 100% !important;
    }
    div.stButton > button, div[data-testid="stFormSubmitButton"] > button {
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
</style>
""", unsafe_allow_html=True)

TAIPEI_TZ = timezone(timedelta(hours=8))
FILE_IO_LOCK = threading.Lock()

# ----------------- 原子寫入與持久化安全工具 -----------------
def atomic_write_json(filepath: str, data: dict) -> bool:
    """以暫存檔加檔案鎖進行原子替換，避免中斷導致 JSON 損毀。"""
    with FILE_IO_LOCK:
        tmp_path = f"{filepath}.tmp_{os.getpid()}_{time.time()}"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, filepath)
            return True
        except Exception as e:
            logger.error(f"寫入 JSON 失敗 ({filepath}): {e}")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            st.warning(f"⚠️ 資料儲存失敗 ({os.path.basename(filepath)}): 請檢查磁碟權限")
            return False

# ----------------- 身分驗證、密碼安全比對與節流 -----------------
try:
    ACCESS_PASSWORD = st.secrets["PASSWORD"]
except Exception:
    ACCESS_PASSWORD = None

try:
    CUSTOM_USERS_DICT = dict(st.secrets.get("USERS", {}))
except Exception:
    CUSTOM_USERS_DICT = {}

try:
    ADMIN_USERS = list(st.secrets.get("ADMIN_USERS", ["預設操盤手", "admin"]))
except Exception:
    ADMIN_USERS = ["預設操盤手", "admin"]

if ACCESS_PASSWORD is None and not CUSTOM_USERS_DICT:
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

# 驗證狀態初始化
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "current_user" not in st.session_state:
    st.session_state.current_user = "預設操盤手"
if "login_fails" not in st.session_state:
    st.session_state.login_fails = 0
if "lockout_until" not in st.session_state:
    st.session_state.lockout_until = 0

def constant_time_check(input_val: str, target_val: str) -> bool:
    """使用 hmac.compare_digest 防範時序攻擊 (Timing Attack)"""
    if input_val is None or target_val is None:
        return False
    return hmac.compare_digest(str(input_val).strip(), str(target_val).strip())

# 登入表單
if not st.session_state.authenticated:
    st.title("🔐 內部量化決策系統")
    st.caption("請輸入您的「使用者代號／暱稱」與「訪問密碼」以啟動個人獨立工作空間")

    # 登入節流鎖定檢查
    now_ts = time.time()
    if now_ts < st.session_state.lockout_until:
        rem_sec = int(st.session_state.lockout_until - now_ts)
        st.error(f"🛑 密碼連續錯誤過多，系統已暫時鎖定！請等待 {rem_sec} 秒後再試。")
        st.stop()

    with st.form("login_form", clear_on_submit=False):
        user_id_input = st.text_input("👤 使用者代號 / 暱稱", value="", placeholder="例：Alex、王董、VIP01", key="login_user_id")
        pwd = st.text_input("🔑 訪問密碼", type="password", key="login_pwd")
        login_btn = st.form_submit_button("🔓 登入個人決策空間", type="primary", use_container_width=True)

        if login_btn:
            clean_uid = user_id_input.strip() if user_id_input.strip() else "預設操盤手"
            is_valid = False

            # 若該使用者設有專屬密碼，必須嚴格匹配專屬密碼，共用密碼無效
            if clean_uid in CUSTOM_USERS_DICT:
                if constant_time_check(pwd, str(CUSTOM_USERS_DICT[clean_uid])):
                    is_valid = True
            elif ACCESS_PASSWORD is not None and constant_time_check(pwd, str(ACCESS_PASSWORD)):
                is_valid = True

            if is_valid:
                st.session_state.authenticated = True
                st.session_state.current_user = clean_uid
                st.session_state.login_fails = 0
                st.session_state.lockout_until = 0
                if "user_data" in st.session_state:
                    del st.session_state["user_data"]
                st.rerun()
            else:
                st.session_state.login_fails += 1
                if st.session_state.login_fails >= 5:
                    st.session_state.lockout_until = time.time() + 60
                    st.error("🚨 密碼連續錯誤已達 5 次，帳號暫時鎖定 60 秒！")
                else:
                    st.error(f"密碼錯誤或使用者未授權（剩餘嘗試次數：{5 - st.session_state.login_fails}）")
    st.stop()

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
    "WMT": "沃爾瑪", "^TWII": "加權指數", "WTX=F": "台指期貨連續月"
}

# 修正問題 13：正確依後綴長度剝除，先處理 .TWO 再處理 .TW
def get_stock_display_label(ticker: str, is_fav=False) -> str:
    t_upper = ticker.strip().upper()
    if t_upper.endswith(".TWO"):
        clean_code = t_upper[:-4]
    elif t_upper.endswith(".TW"):
        clean_code = t_upper[:-3]
    else:
        clean_code = t_upper

    name = GLOBAL_STOCK_NAMES.get(t_upper, GLOBAL_STOCK_NAMES.get(clean_code, ""))
    prefix = "⭐ " if is_fav else ""
    if name:
        return f"{prefix}{name} ({clean_code})"
    return f"{prefix}{clean_code}"

# ----------------- 使用者檔案記憶引擎 -----------------
PROFILES_FILE = "user_profiles.json"

def get_default_profile():
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

def load_all_profiles() -> dict:
    all_data = {"users": {}}
    if os.path.exists(PROFILES_FILE):
        try:
            with open(PROFILES_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict) and "users" in loaded:
                    all_data = loaded
        except Exception as e:
            logger.error(f"讀取使用者設定檔失敗: {e}")
    return all_data

def get_user_data() -> dict:
    uid = st.session_state.get("current_user", "預設操盤手")
    default_p = get_default_profile()
    if "user_data" not in st.session_state or st.session_state.get("loaded_uid") != uid:
        all_profiles = load_all_profiles()
        user_p = all_profiles["users"].get(uid, {})
        for k, v in default_p.items():
            if k not in user_p:
                user_p[k] = v
        st.session_state.user_data = user_p
        st.session_state.loaded_uid = uid
    return st.session_state.user_data

def save_user_data():
    uid = st.session_state.get("current_user", "預設操盤手")
    if "user_data" in st.session_state:
        st.session_state.user_data["last_active"] = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M")
        all_profiles = load_all_profiles()
        all_profiles["users"][uid] = st.session_state.user_data
        atomic_write_json(PROFILES_FILE, all_profiles)

def get_registered_user_list() -> list:
    all_profiles = load_all_profiles()
    users = list(all_profiles.get("users", {}).keys())
    cur = st.session_state.get("current_user", "預設操盤手")
    if cur not in users:
        users.insert(0, cur)
    return users

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

# ----------------- 修正問題 20：拒絕寫死過期事件與日期的市場戰情 -----------------
BRIEFING_FILE = "market_briefings.json"

def get_default_briefing():
    cur_date = datetime.now(TAIPEI_TZ).strftime("%m月%d日")
    return {
        "title": f"🔥 市場多空轉折與宏觀數據決策提示 ({cur_date})",
        "content": (
            "台股與全球資產目前處於均線位階攻防，短線需密切關注外資現貨與期貨留倉結構。\n\n"
            "📌 **核心客觀觀測指標**：\n"
            "• **總經數據連動**：留意即將公布之美國核心通膨與勞動市場數據是否與市場預期產生顯著偏離。\n"
            "• **熱錢匯流結構**：緊盯新台幣收盤匯率是否守穩月線，以及台指期實質價差之多空指引。\n"
            "• **紀律操作原則**：現價跌破月線（20MA）者嚴禁逆勢摸底，順勢持有者以 ATR 軌道嚴格設定防守價。"
        ),
        "author": "系統策略研究中心",
        "updated_at": datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M"),
        "level": "critical"
    }

def load_market_briefing() -> dict:
    if os.path.exists(BRIEFING_FILE):
        try:
            with open(BRIEFING_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "content" in data:
                    return data
        except Exception as e:
            logger.error(f"讀取戰情焦點失敗: {e}")
    return get_default_briefing()

def save_market_briefing(title: str, content: str, author: str):
    new_b = {
        "title": title.strip(),
        "content": content.strip(),
        "author": author.strip() or "系統策略中心",
        "updated_at": datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M"),
        "level": "critical"
    }
    atomic_write_json(BRIEFING_FILE, new_b)
    return new_b

# ----------------- 修正問題 12：數值安全轉換與非數值過濾 -----------------
def safe_float(val, default=0.0):
    try:
        if val is None or pd.isna(val):
            return default
        if isinstance(val, pd.Series):
            if val.empty:
                return default
            val = val.iloc[0]
        elif isinstance(val, (np.ndarray, list, tuple)):
            if len(val) == 0:
                return default
            val = val[0]
        if isinstance(val, str):
            val = val.strip().replace(",", "")
            if val in ("", "-", "N/A", "nan", "None", "_", "--", "NaN", "null"):
                return default
        result = float(val)
        if not math.isfinite(result):
            return default
        return result
    except (ValueError, TypeError, IndexError, OverflowError):
        return default

# 修正問題 3：格式化輸出全面使用 pd.notna 檢查，杜絕 nan% 破綻
def fmt_val(val, fmt="{:.1f}%", fallback="--") -> str:
    if pd.notna(val) and val is not None:
        try:
            f = float(val)
            if math.isfinite(f):
                return fmt.format(f)
        except Exception:
            pass
    return fallback

# 修正問題 8：版本無關之殖利率解析
def parse_yield_safely(yield_raw):
    y = safe_float(yield_raw, default=None)
    if y is None or not pd.notna(y) or y <= 0:
        return None
    if y <= 0.35:   # 0.055 形式轉 5.5%
        return y * 100.0
    if y <= 35.0:   # 已為百分比數值
        return y
    return None

# ----------------- 修正問題 2：代碼正規化排除 WMT (Walmart) 誤判 -----------------
def normalize_ticker(ticker: str, market_hint: str = None):
    t = ticker.strip().upper()
    if market_hint == "us":
        return t, "us"
    if market_hint == "futures":
        return t, "futures"
    if t.endswith("=F"):
        return t, "futures"
    if t.endswith(".TWO"):
        return t[:-4], "otc"
    if t.endswith(".TW"):
        return t[:-3], "tse"
    if market_hint == "tw":
        return t, "tse"
    # 純英文字母代碼（包含 WMT、NVDA）預設歸類美股
    return t, "us"

# ----------------- 臺灣證券交易所官方即時行情 (修正問題 9 & 17) -----------------
TWSE_SESSION = requests.Session()
TWSE_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://mis.twse.com.tw/stock/index.jsp"
})
TWSE_INITIALIZED = False

def ensure_twse_cookie():
    global TWSE_INITIALIZED
    if not TWSE_INITIALIZED:
        try:
            TWSE_SESSION.get("https://mis.twse.com.tw/stock/index.jsp", timeout=2.5)
            TWSE_INITIALIZED = True
        except Exception as e:
            logger.warning(f"TWSE Cookie 初始化超時: {e}")

# 快取失敗時 raise 以防快取被空值污染 (修正問題 4)
@st.cache_data(ttl=8, show_spinner=False)
def _fetch_twse_realtime_cached(ticker: str):
    code, market = normalize_ticker(ticker, market_hint="tw")
    if market in ("us", "futures"):
        raise ValueError("非台股標的")

    ensure_twse_cookie()
    ex_ch = f"{market}_{code}.tw"
    url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={ex_ch}&json=1&delay=0"

    resp = TWSE_SESSION.get(url, timeout=2.5)
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
            converted_shares = raw_lots * 1000.0  # TWSE 張轉股 (遵守防錯紅線 4)
            date_str = item.get("d", "")
            time_str = item.get("t", "")

            b_prices = [safe_float(x) for x in str(item.get("b", "")).split("_") if x.strip()][:5]
            b_vols = [int(safe_float(x)) for x in str(item.get("g", "")).split("_") if x.strip()][:5]
            a_prices = [safe_float(x) for x in str(item.get("a", "")).split("_") if x.strip()][:5]
            a_vols = [int(safe_float(x)) for x in str(item.get("f", "")).split("_") if x.strip()][:5]

            now_taipei = datetime.now(TAIPEI_TZ)
            today_str = now_taipei.strftime("%Y%m%d")

            # 依實際交易時段與日期評定新鮮度 (修正問題 17)
            if date_str == today_str:
                if "09:00:00" <= time_str <= "13:35:00":
                    status_label = "🟢 盤中即時撮合"
                    is_live = True
                else:
                    status_label = "⚪ 今日盤後結算"
                    is_live = False
            else:
                status_label = "🟡 前一交易日資料"
                is_live = False

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
                "is_live": is_live,
                "is_trading": is_trading,
                "bid_prices": b_prices,
                "bid_vols": b_vols,
                "ask_prices": a_prices,
                "ask_vols": a_vols
            }
    raise RuntimeError(f"TWSE 行情取得失敗: {ticker}")

def fetch_twse_realtime(ticker: str):
    try:
        return _fetch_twse_realtime_cached(ticker)
    except Exception as e:
        logger.debug(f"即時撮合連線例外: {e}")
        return None

# ----------------- 大盤即時統計看板 (修正問題 9 & 18) -----------------
@st.cache_data(ttl=15, show_spinner=False)
def _fetch_twse_market_dashboard_cached():
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

    ensure_twse_cookie()
    idx_url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_t00.tw|tse_t001.tw|otc_o00.tw&json=1&delay=0"
    r_idx = TWSE_SESSION.get(idx_url, timeout=2.5)
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

    # getStatis.jsp 官方欄位容錯解析
    stat_url = "https://mis.twse.com.tw/stock/api/getStatis.jsp?ex=tse&delay=0"
    r_stat = TWSE_SESSION.get(stat_url, timeout=2.5)
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

            if bw > 0: result["bid_orders"] = bw
            if sw > 0: result["ask_orders"] = sw
            if tr > 0: result["trade_orders"] = tr
            if bv > 0: result["bid_lots"] = bv
            if sv > 0: result["ask_lots"] = sv
            if tv > 0: result["trade_lots"] = tv

            if bw > 0 and bv > 0: result["avg_bid_lots"] = round(bv / bw, 1)
            if sw > 0 and sv > 0: result["avg_ask_lots"] = round(sv / sw, 1)

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

    if result["twii_price"] <= 0:
        raise RuntimeError("無法獲取 TWSE 大盤有效報價")
    return result

def fetch_twse_market_dashboard():
    try:
        return _fetch_twse_market_dashboard_cached()
    except Exception as e:
        logger.warning(f"大盤看板連線失敗: {e}")
        return {
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

# ----------------- yfinance 快取防污染包裝 (修正問題 4) -----------------
@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_yf_shared_info_cached(ticker: str):
    t = yf.Ticker(ticker)
    info = t.info
    if not info or not isinstance(info, dict) or len(info) < 2:
        raise RuntimeError(f"yfinance info 回傳為空 ({ticker})")
    return dict(info)

def fetch_yf_shared_info(ticker: str) -> dict:
    try:
        return _fetch_yf_shared_info_cached(ticker)
    except Exception as e:
        logger.debug(f"yfinance info 抓取失敗: {e}")
        return {}

@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_yf_earnings_history_cached(ticker: str):
    t = yf.Ticker(ticker)
    eh = t.earnings_history
    if eh is None or eh.empty:
        raise RuntimeError(f"無盈餘驚奇度歷史 ({ticker})")
    return eh.tail(4).copy()

def fetch_yf_earnings_history_safe(ticker: str):
    try:
        return _fetch_yf_earnings_history_cached(ticker)
    except Exception:
        return None

# ----------------- 修正問題 10 & 14：指標嚴格暖機期與時間對齊 -----------------
def _raw_fetch_and_calc(ticker: str, period: str = "1y"):
    obj = yf.Ticker(ticker)
    df = obj.history(period=period)
    if df is None or df.empty or len(df) < 15:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()

    # 盤中最新撮合 K 棒融合
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
                    target_tz = last_idx.tz if last_idx.tz is not None else TAIPEI_TZ
                    new_ts = pd.Timestamp(today_date).tz_localize(target_tz)
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

    # 均線計算（前 19 期不產生假 20MA）
    df['MA5'] = df['Close'].rolling(5, min_periods=5).mean()
    df['MA20'] = df['Close'].rolling(20, min_periods=20).mean()
    df['MA60'] = df['Close'].rolling(60, min_periods=60).mean()
    df['Vol_MA5'] = df['Volume'].rolling(5, min_periods=5).mean()

    # 修正問題 14：RSI14 嚴格要求 min_periods=14，杜絕前期資料虛假高分
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0.0)).rolling(14, min_periods=14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14, min_periods=14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI14'] = 100.0 - (100.0 / (1.0 + rs))

    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = ema12 - ema26
    df['MACD'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['OSC'] = df['DIF'] - df['MACD']

    # 修正問題 14：禁止對 ATR 使用 bfill()，嚴防未來資訊回填污染歷史
    hl = df['High'] - df['Low']
    hc = (df['High'] - df['Close'].shift(1)).abs()
    lc = (df['Low'] - df['Close'].shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df['ATR14'] = tr.rolling(14, min_periods=14).mean()

    return df.copy()

@st.cache_data(ttl=60, show_spinner=False)
def _fetch_and_calc_cached(ticker: str, period: str = "1y"):
    df = _raw_fetch_and_calc(ticker, period)
    if df is None or df.empty or len(df) < 15:
        raise RuntimeError(f"行情樣本不足 ({ticker})")
    return df

def fetch_and_calc(ticker: str, period: str = "1y"):
    try:
        return _fetch_and_calc_cached(ticker, period)
    except Exception as e:
        logger.debug(f"fetch_and_calc 例外: {e}")
        return None

# ----------------- 分時走勢圖數據引擎 -----------------
@st.cache_data(ttl=30, show_spinner=False)
def _fetch_intraday_series_cached(ticker: str):
    t = yf.Ticker(ticker)
    df_intra = t.history(period="1d", interval="1m")
    if df_intra is None or df_intra.empty or len(df_intra) < 5:
        df_5d = t.history(period="5d", interval="5m")
        if df_5d is not None and not df_5d.empty:
            last_day = df_5d.index[-1].date()
            df_intra = df_5d[df_5d.index.date == last_day].copy()

    if df_intra is None or df_intra.empty:
        raise RuntimeError(f"無分時資料 ({ticker})")

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
        raise RuntimeError("分時資料皆為 NaN")

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

def fetch_intraday_series(ticker: str):
    try:
        return _fetch_intraday_series_cached(ticker)
    except Exception:
        return None, None

def render_intraday_chart_widget(ticker: str, title_name: str = ""):
    df_intra, y_close = fetch_intraday_series(ticker)
    if df_intra is None or df_intra.empty:
        st.info("⚪ 目前無該標的之即時分時明細資料（可能處於非交易時段或資料庫維護中）。")
        return

    last_row = df_intra.iloc[-1]
    curr_p = safe_float(last_row['Close'])
    high_p = safe_float(df_intra['High'].max())
    low_p = safe_float(df_intra['Low'].min())
    chg_val = curr_p - y_close
    chg_pct = (chg_val / (y_close + 1e-9)) * 100.0

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

# ----------------- 修正問題 19：臺灣銀行匯率以 Header 精準解析 -----------------
@st.cache_data(ttl=300, show_spinner=False)
def _fetch_bot_forex_cached():
    url = "https://rate.bot.com.tw/xrt/flcsv/0/day"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=3.5)
    if r.status_code == 200:
        f = io.StringIO(r.text)
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            raise RuntimeError("臺銀匯率 CSV 表頭為空")

        # 動態尋找「即期賣出」或「現金賣出」欄位索引
        sell_idx = -1
        for idx, col_name in enumerate(header):
            if "本行即期賣出" in col_name or "即期賣出" in col_name:
                sell_idx = idx
                break
        if sell_idx == -1:
            for idx, col_name in enumerate(header):
                if "現金賣出" in col_name:
                    sell_idx = idx
                    break

        for row in reader:
            if len(row) > max(sell_idx, 2) and row[0].strip() == "USD":
                val = safe_float(row[sell_idx]) if sell_idx != -1 else safe_float(row[12] if len(row) > 12 else row[4])
                if val > 0:
                    return {"usd_twd": val, "source": "臺灣銀行官方牌告(即期賣出)", "is_real": True}
    raise RuntimeError("無法自臺銀 CSV 解析 USD/TWD")

def fetch_bot_forex():
    try:
        return _fetch_bot_forex_cached()
    except Exception as e:
        logger.warning(f"臺銀匯率解析失敗: {e}")
        return None

# ----------------- 全球外匯與熱錢監控 -----------------
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

                if last_twd < ma20_twd:
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
    except Exception as e:
        logger.debug(f"外匯數據解析例外: {e}")

    return res

# ----------------- 總經 RSS 外電引擎 -----------------
@st.cache_data(ttl=180, show_spinner=False)
def _fetch_live_macro_rss_cached(query_str: str):
    encoded_q = quote(query_str)
    url = f"https://news.google.com/rss/search?q={encoded_q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=3.5)
    if r.status_code == 200:
        root = ET.fromstring(r.content)
        items = []
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
        if items:
            return items
    raise RuntimeError("無法獲取 Google RSS 外電")

def fetch_live_macro_rss(query_str: str = "台股 OR 美股 OR 聯準會 OR 台積電 OR 費半"):
    try:
        return _fetch_live_macro_rss_cached(query_str)
    except Exception:
        return []

# ----------------- 個股新聞引擎 -----------------
@st.cache_data(ttl=600, show_spinner=False)
def _fetch_stock_news_cached(ticker: str):
    t = yf.Ticker(ticker)
    news_list = t.news
    if not news_list:
        raise RuntimeError(f"查無新聞: {ticker}")
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

def fetch_stock_news(ticker: str):
    try:
        return _fetch_stock_news_cached(ticker)
    except Exception:
        return []

# ----------------- 機構分析師共識 -----------------
def fetch_analyst_consensus(ticker: str):
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

# ----------------- 修正問題 6：期貨拒絕偽造機構共識與固定 8 家機構 -----------------
def fetch_futures_analyst_consensus(code: str, df_fut: pd.DataFrame, df_mkt: pd.DataFrame):
    if df_fut is None or df_fut.empty:
        return {
            "has_data": False,
            "rec_label": "⚪ 資料不可用",
            "rec_desc": "期貨合約行情不足，嚴禁進行技術推算",
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
        rec_label = "🔥 技術多頭攻擊結構"
        rec_desc = "均線多頭排列且實質正價差領先，多方動能充沛"
    elif last_fut > ma20:
        rec_label = "🟢 守穩月線偏多震盪"
        rec_desc = "價格守穩月線關鍵位階，拉回有買盤承接"
    elif last_fut < ma20 < ma60 and basis < -40:
        rec_label = "🔴 均線蓋頭逆價差防守"
        rec_desc = "逆價差擴大且均線壓制，空方主導避險"
    else:
        rec_label = "🟡 區間箱型整理"
        rec_desc = "均線糾結，短線處於區間拉鋸"

    atr = df_fut['ATR14'].iloc[-1] if ('ATR14' in df_fut.columns and pd.notna(df_fut['ATR14'].iloc[-1])) else 150.0
    recent_high = df_fut['High'].tail(20).max()
    recent_low = df_fut['Low'].tail(20).min()

    target_high = max(recent_high, last_fut + 2.0 * atr)
    target_low = min(recent_low, last_fut - 2.0 * atr)
    target_mean = (last_fut + target_high) / 2.0 if last_fut > ma20 else last_fut

    # 修正問題 6：opinions 嚴格設定為 0，誠實標註為內部技術模型推估
    return {
        "has_data": True,
        "rec_label": rec_label,
        "rec_desc": f"{rec_desc}（依均線與價差模型推估，無公開法人研究共識報告）",
        "target_mean": target_mean,
        "target_high": target_high,
        "target_low": target_low,
        "opinions": 0
    }

# ----------------- 四大權威機構研究套件 (修正問題 7 & 12) -----------------
def fetch_institutional_research_suite(ticker: str):
    clean_code, market = normalize_ticker(ticker)
    if market == "futures":
        return {"has_suite": False}

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
    div_yield = parse_yield_safely(info.get("dividendYield"))
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
            "div_yield": div_yield,
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

def format_large_money(val, currency="NTD") -> str:
    if val is None or not pd.notna(val) or val == 0:
        return "未揭露"
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

# ----------------- 修正問題 11：ETF 基本面評分不給空白加分 -----------------
def fetch_fundamentals(ticker: str):
    clean_code, market = normalize_ticker(ticker)
    if market == "futures":
        return {"has_data": False, "is_etf": False, "score": None, "reasons": []}

    info = fetch_yf_shared_info(ticker)
    is_etf = info.get('quoteType') == 'ETF' or clean_code.startswith(('00', '01'))

    if is_etf:
        yield_val = parse_yield_safely(info.get('yield', info.get('dividendYield', None)))
        beta_val = safe_float(info.get('beta'), default=None)
        nav_val = safe_float(info.get('navPrice'), default=None)

        # 修正問題 11：缺失資料明確標註未知，不給予假分數
        if yield_val is None and beta_val is None:
            return {
                "has_data": False,
                "is_etf": True,
                "score": None,
                "yield": None,
                "beta": None,
                "nav": nav_val,
                "category": info.get('category', '指數股票型基金 (ETF)'),
                "reasons": ["⚠️ 查無足夠之配息率與 Beta 數據，評分標記為不完整，未計入評分"]
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
        else:
            reasons.append("⚪ 配息率數據未揭露（不予計分）")

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
        else:
            reasons.append("⚪ Beta 波動度未揭露（不予計分）")

        fund_score += 10
        reasons.append("一籃子持股分散非系統性風險")

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

# ----------------- 修正問題 15：跨市場 Alpha 日期嚴格交集對齊 -----------------
def calc_aligned_alpha(df_stock: pd.DataFrame, df_market: pd.DataFrame, lookback_bars: int = 20) -> float:
    if df_stock is None or df_market is None or len(df_stock) < lookback_bars or len(df_market) < lookback_bars:
        return 0.0

    s_close = df_stock['Close'].copy()
    m_close = df_market['Close'].copy()

    # 統一標準化為 tz-naive 日期，以 inner join 精準匹配共同開盤日
    s_close.index = pd.to_datetime(s_close.index).tz_localize(None).normalize()
    m_close.index = pd.to_datetime(m_close.index).tz_localize(None).normalize()

    combined = pd.concat([s_close, m_close], axis=1, join='inner').dropna()
    if len(combined) <= lookback_bars:
        return 0.0

    stk_ret = (combined.iloc[-1, 0] / combined.iloc[-(lookback_bars + 1), 0] - 1.0) * 100.0
    mkt_ret = (combined.iloc[-1, 1] / combined.iloc[-(lookback_bars + 1), 1] - 1.0) * 100.0
    return float(stk_ret - mkt_ret)

# ----------------- 均線與跳空分析 -----------------
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
        "ma5_diff": ((close - ma5) / (ma5 + 1e-9)) * 100 if pd.notna(last['MA5']) else 0.0,
        "ma20_diff": ((close - ma20) / (ma20 + 1e-9)) * 100 if pd.notna(last['MA20']) else 0.0,
        "ma60_diff": ((close - ma60) / (ma60 + 1e-9)) * 100 if pd.notna(last['MA60']) else 0.0,
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

# ----------------- 修正問題 8 & 9：回測交易成本與盯市 MDD -----------------
def backtest_strategy(df_stock, market_type="tw", custom_spec=None):
    if df_stock is None or len(df_stock) < 60:
        return None

    # 信號產生條件（使用 T 日收盤資料確認）
    signals = (
        (df_stock['Close'] > df_stock['MA20']) &
        (df_stock['Close'] > df_stock['Close'].shift(1)) &
        (df_stock['Volume'] > df_stock['Vol_MA5']) &
        (df_stock['OSC'] > 0)
    )

    n_bars = len(df_stock)
    trade_returns = []
    daily_equity_curve = [100.0]
    i = 25  # 略過暖機期

    # 修正問題 8：分流精準交易成本
    if market_type == "us":
        cost_rate = 0.0010  # 美股 0.1% 來回滑價
        fee_label = "美股 0.1% 滑價"
    elif market_type == "futures":
        cost_rate = 0.0006  # 期交稅 10萬分之2*2 + 手續費 + 1跳滑價
        fee_label = "期指交易稅與滑價"
    else:
        # 台股 0.1425%*2*0.6(券商折扣) + 0.3% 交易稅 + 0.1% 滑價 = 0.57%
        cost_rate = 0.0057
        fee_label = "台股手續費(6折)+證交稅0.3%+滑價"

    while i < n_bars - 6:
        if signals.iloc[i]:
            # 遵守防錯紅線 7：T+1 日 Open 進場
            entry_p = safe_float(df_stock['Open'].iloc[i + 1])
            if entry_p <= 0:
                entry_p = safe_float(df_stock['Close'].iloc[i + 1])
            
            # 修正問題 9：盯市追蹤持倉 5 日間的真實每日浮動損益
            pos_cur_val = daily_equity_curve[-1]
            for hold_day in range(1, 6):
                bar_idx = i + 1 + hold_day
                if bar_idx < n_bars:
                    day_p = safe_float(df_stock['Close'].iloc[bar_idx])
                    if day_p > 0 and entry_p > 0:
                        unrealized_pct = (day_p - entry_p) / entry_p
                        daily_equity_curve.append(pos_cur_val * (1.0 + unrealized_pct))

            exit_p = safe_float(df_stock['Open'].iloc[i + 6])
            if exit_p <= 0:
                exit_p = safe_float(df_stock['Close'].iloc[i + 6])

            if entry_p > 0 and exit_p > 0:
                net_ret = ((exit_p - entry_p) / entry_p - cost_rate) * 100.0
                trade_returns.append(net_ret)
                # 更新最終實現權益
                daily_equity_curve.append(pos_cur_val * (1.0 + net_ret / 100.0))
                i += 6  # 循序不重疊持倉
                continue
        else:
            daily_equity_curve.append(daily_equity_curve[-1])
        i += 1

    if not trade_returns:
        return None

    wins = [r for r in trade_returns if r > 0]
    win_rate = (len(wins) / len(trade_returns)) * 100.0
    avg_return = float(np.mean(trade_returns))
    worst_single_loss = float(min(trade_returns))

    # 修正問題 9：由完整的連續每日盯市權益曲線計算真實 MDD
    peak = daily_equity_curve[0]
    max_dd = 0.0
    for val in daily_equity_curve:
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
        "mdd": max_dd,
        "fee_label": fee_label
    }

# ----------------- 全維度綜合評估 (修正問題 4, 12, 15) -----------------
def analyze_full_stock(ticker, df_stock, df_market, df_futures, df_tsm, df_sox, forex_info, asset_type="tw", include_inst_suite=True):
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

    # 修正問題 15：跨市場 Alpha 日期精確對齊
    rel_alpha_20d = calc_aligned_alpha(df_stock, df_market, lookback_bars=20)
    rel_alpha_60d = calc_aligned_alpha(df_stock, df_market, lookback_bars=60)

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

    if pd.notna(last_stk['RSI14']) and 50 <= last_stk['RSI14'] <= 70:
        tech_score += 7
        tech_reasons.append(f"RSI 處健康攻擊區 ({last_stk['RSI14']:.1f})")

    # 分析師加減分
    analyst_bonus = 0
    if analyst_data["has_data"]:
        rec = analyst_data["rec_label"]
        if "強力" in rec or "Strong" in rec:
            analyst_bonus = 5
        elif "偏多" in rec or "Buy" in rec:
            analyst_bonus = 3
        elif "減碼" in rec or "Underperform" in rec:
            analyst_bonus = -3
        elif "空" in rec or "Sell" in rec:
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

    # 遵守防錯紅線 5：停損價單向保護，月線壓力下停損嚴格錨定在現價下方
    ma20_val = safe_float(last_stk['MA20'], close * 0.96)
    if close >= ma20_val:
        raw_stop = max(close - 2.0 * atr_val, ma20_val - 0.5 * atr_val)
        stop_loss = min(raw_stop, close * 0.985)
        is_breakdown = False
    else:
        stop_loss = min(close - 2.0 * atr_val, close * 0.985)
        is_breakdown = True

    # 確保第二目標價恆大於第一目標價
    risk_unit = max(close - stop_loss, close * 0.015)
    target_1 = close + (1.5 * risk_unit)

    recent_60d_high = safe_float(df_stock['High'].tail(60).max(), close * 1.08)
    if analyst_data['target_mean'] > close:
        target_60d_cand = analyst_data['target_mean']
    elif recent_60d_high > close:
        target_60d_cand = recent_60d_high
    else:
        target_60d_cand = close + 2.5 * atr_val

    target_60d = max(target_60d_cand, target_1 * 1.03, close * 1.05)

    return {
        "total_score": total_score,
        "fund_score": fund_data.get('score'),
        "close": close,
        "stop_loss": stop_loss,
        "target_1": target_1,
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

# ----------------- 修正問題 4 & 5：期貨代碼與契約規格對照表 -----------------
# 嚴格禁止使用加權指數替換期貨
TW_FUTURES_SPECS = {
    "WTX": {
        "name": "台指期貨 (大台)",
        "ticker_yf": "WTX=F",
        "tick_value": 200,
        "initial_margin": 250000,
        "maintenance_margin": 192000,
        "desc": "全市場主力大額籌碼風向核心",
        "supported": True
    },
    "MTX": {
        "name": "小型台指 (小台)",
        "ticker_yf": "WTX=F",  # 與大台點位連動，以小台點值計算法人損益
        "tick_value": 50,
        "initial_margin": 62500,
        "maintenance_margin": 48000,
        "desc": "散戶與短線波段核心",
        "supported": True
    },
    "TMF": {
        "name": "微型台指 (微台)",
        "ticker_yf": "WTX=F",
        "tick_value": 10,
        "initial_margin": 12500,
        "maintenance_margin": 9600,
        "desc": "小資量化避險首選 (期交所正式代碼)",
        "supported": True
    },
    "TE": {
        "name": "電子期貨",
        "ticker_yf": None,  # Yahoo 無連續電子期合約
        "tick_value": 400,
        "initial_margin": 210000,
        "maintenance_margin": 161000,
        "desc": "追蹤電子權值類股",
        "supported": False
    },
    "TF": {
        "name": "金融期貨",
        "ticker_yf": None,  # Yahoo 無連續金融期合約
        "tick_value": 1000,
        "initial_margin": 130000,
        "maintenance_margin": 100000,
        "desc": "大型金控與壽險資產指標",
        "supported": False
    }
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

# ----------------- 狀態初始化 (修正問題 5：移除文字輸入框 value/key 雙重衝突) -----------------
if "main_mode" not in st.session_state:
    st.session_state.main_mode = "live_watch"

if "tw_ticker_field" not in st.session_state:
    st.session_state.tw_ticker_field = "2330.TW"
if "selected_tw_ticker" not in st.session_state:
    st.session_state.selected_tw_ticker = "2330.TW"

if "us_ticker_field" not in st.session_state:
    st.session_state.us_ticker_field = "NVDA"
if "selected_us_ticker" not in st.session_state:
    st.session_state.selected_us_ticker = "NVDA"

if "tw_fut_field" not in st.session_state:
    st.session_state.tw_fut_field = "WTX"
if "selected_fut_contract" not in st.session_state:
    st.session_state.selected_fut_contract = "WTX"

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
current_briefing = load_market_briefing()

# ----------------- 頂部導航與使用者面板 (修正問題 1：移除巢狀 expander) -----------------
st.title("📱 股期決策旗艦站 (跨市場機構版)")

with st.expander(f"👤 當前使用者：【{st.session_state.current_user}】（點此切換／風控與備份）", expanded=False):
    st.caption("每位使用者擁有完全獨立的常用股票、查詢歷史、預設操作本金與個人看盤筆記。")
    u_c1, u_c2 = st.columns([2.2, 1.8])
    with u_c1:
        known_users = get_registered_user_list()
        new_or_switch_uid = st.text_input("輸入要切換的使用者名稱", value="", placeholder=st.session_state.current_user, key="switch_uid_input")
    with u_c2:
        st.write("")
        if st.button("🔄 切換使用者", type="primary", use_container_width=True, key="btn_switch_uid"):
            target_u = new_or_switch_uid.strip()
            if target_u:
                # 修正問題 1：切換至設有專屬密碼的帳號必須重新登入認證
                if target_u in CUSTOM_USERS_DICT and target_u != st.session_state.current_user:
                    st.session_state.authenticated = False
                    st.session_state.current_user = target_u
                    st.info(f"使用者【{target_u}】設有專屬密碼，請先通過驗證。")
                    st.rerun()
                else:
                    st.session_state.current_user = target_u
                    if "user_data" in st.session_state:
                        del st.session_state["user_data"]
                    st.rerun()

    # 登出按鈕
    if st.button("🚪 登出系統", use_container_width=True, key="btn_logout"):
        st.session_state.authenticated = False
        st.rerun()

    if len(known_users) > 1:
        st.caption(f"📋 已建立之使用者檔案：`{'`、`'.join(known_users)}`")

    st.markdown("#### 💰 個人預設風控本金與筆記設定")
    p_c1, p_c2, p_c3 = st.columns(3)
    with p_c1:
        u_cap_tw = st.number_input("台股預設本金(NTD)", value=int(user_memory.get("capital_tw", 1000000)), step=100000, key="prof_cap_tw")
    with p_c2:
        u_cap_us = st.number_input("美股預設本金(USD)", value=int(user_memory.get("capital_us", 50000)), step=5000, key="prof_cap_us")
    with p_c3:
        u_risk = st.number_input("單筆風險(%)", min_value=0.5, max_value=5.0, value=float(user_memory.get("risk_pct", 1.0)), step=0.1, key="prof_risk")

    u_note = st.text_area("📝 個人專屬看盤備忘錄", value=user_memory.get("personal_note", ""), height=68, key="prof_note")
    if st.button("💾 儲存個人專屬設定", use_container_width=True, key="btn_save_profile"):
        user_memory["capital_tw"] = u_cap_tw
        user_memory["capital_us"] = u_cap_us
        user_memory["risk_pct"] = u_risk
        user_memory["personal_note"] = u_note
        save_user_data()
        st.success(f"已儲存【{st.session_state.current_user}】的專屬參數！")

    # 修正問題 1 & 22：改用 checkbox 代替巢狀 expander，並嚴格驗證備份 JSON Schema
    show_backup = st.checkbox("📦 展開備份碼管理（匯出 / 匯入防重置）", value=False, key="chk_backup_toggle")
    if show_backup:
        backup_str = json.dumps(user_memory, ensure_ascii=False)
        st.code(backup_str, language="json")
        restore_str = st.text_input("貼上備份碼一鍵還原", placeholder='{"tw_favorites": ...}', key="restore_json_in")
        if st.button("📥 確認還原個人設定", key="btn_restore_json"):
            try:
                restored = json.loads(restore_str)
                if not isinstance(restored, dict):
                    raise ValueError("備份碼非合規 JSON 物件")
                
                # 修正問題 22：嚴格白名單欄位校驗，防禦未授權欄位覆蓋
                allowed_keys = {"tw_favorites", "tw_recent", "us_favorites", "us_recent", "capital_tw", "capital_us", "capital_fut", "risk_pct", "personal_note"}
                validated_data = {}
                for k in allowed_keys:
                    if k in restored:
                        val = restored[k]
                        if "favorites" in k or "recent" in k:
                            if isinstance(val, list) and all(isinstance(x, str) for x in val):
                                validated_data[k] = val[:15]
                        elif "capital" in k:
                            validated_data[k] = max(safe_float(val, default=100000), 1000)
                        elif k == "risk_pct":
                            validated_data[k] = min(max(safe_float(val, default=1.0), 0.1), 10.0)
                        elif k == "personal_note":
                            validated_data[k] = str(val)[:500]

                if validated_data:
                    st.session_state.user_data.update(validated_data)
                    save_user_data()
                    st.success("個人設定驗證通過並成功還原！")
                    st.rerun()
                else:
                    st.error("備份碼中無任何有效欄位")
            except Exception as ex:
                st.error(f"備份碼還原失敗: {ex}")

# 修正問題 3：對置頂戰情進行全面 HTML 轉義防範 XSS
safe_b_title = html.escape(str(current_briefing.get('title', '')))
safe_b_content = html.escape(str(current_briefing.get('content', ''))).replace('\n', '<br>')
safe_b_author = html.escape(str(current_briefing.get('author', '')))
safe_b_time = html.escape(str(current_briefing.get('updated_at', '')))

st.markdown(f"""
<div class="macro-alert-card">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.3rem;">
        <b style="color:#e53935; font-size:1.0rem;">{safe_b_title}</b>
    </div>
    <div style="font-size:0.9rem; opacity:0.95;">
        {safe_b_content}
    </div>
    <div style="font-size:0.78rem; color:#777; margin-top:0.4rem; text-align:right;">
        發布單位：{safe_b_author} ｜ 更新時間：{safe_b_time}
    </div>
</div>
""", unsafe_allow_html=True)

# 置頂導航與自動刷新開關 (修正問題 23)
top_c1, top_c2 = st.columns([1.4, 1.0])
with top_c1:
    if st.button("📺 大盤即時看盤 (分時/戰情)", type="primary" if st.session_state.main_mode == "live_watch" else "secondary", use_container_width=True, key="m_nav_live_watch"):
        st.session_state.main_mode = "live_watch"
        st.rerun()
with top_c2:
    auto_refresh = st.checkbox("⏱️ 30秒自動刷新", value=False, key="global_auto_refresh")

# 模式切換
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

# 全域預載
df_market = fetch_and_calc("^TWII")
df_futures_bench = fetch_and_calc("WTX=F")
df_tsm = fetch_and_calc("TSM")
df_sox = fetch_and_calc("^SOX")
df_spx = fetch_and_calc("^GSPC")
global_forex = analyze_forex_data()

# ================= 四大機構研究面板 (修正問題 1：移除 tab_mr 巢狀 expander) =================
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
            "📊 財務分析",
            "📑 股票研究",
            "📈 財報分析",
            "🌐 市場研究",
            "📥 完整報告"
        ])

        with tab_fa:
            st.markdown("#### 📊 Financial Analysis（企業財務結構與現金流護城河）")
            fa_c1, fa_c2, fa_c3 = st.columns(3)
            fa_c1.metric("毛利率 (Gross)", fmt_val(fin['gross_margin']))
            fa_c2.metric("營益率 (Operating)", fmt_val(fin['op_margin']))
            fa_c3.metric("淨利率 (Net)", fmt_val(fin['profit_margin']))

            fa_c4, fa_c5, fa_c6 = st.columns(3)
            fa_c4.metric("股東權益報酬 (ROE)", fmt_val(fin['roe']))
            fa_c5.metric("資產報酬率 (ROA)", fmt_val(fin['roa']))
            fa_c6.metric("負債權益比 (D/E)", fmt_val(fin['debt_to_equity']))

            fa_c7, fa_c8 = st.columns(2)
            cr_str = fmt_val(fin['current_ratio'], fmt="{:.2f}")
            qr_str = fmt_val(fin['quick_ratio'], fmt="{:.2f}")
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
            eq_c1.metric("歷史本益比 (Trailing PE)", fmt_val(eq['trailing_pe'], fmt="{:.1f}x") if (eq['trailing_pe'] and eq['trailing_pe'] > 0) else "不適用/虧損")
            eq_c2.metric("預估本益比 (Forward PE)", fmt_val(eq['forward_pe'], fmt="{:.1f}x") if (eq['forward_pe'] and eq['forward_pe'] > 0) else "未揭露")
            eq_c3.metric("股價淨值比 (P/B)", fmt_val(eq['pb_ratio'], fmt="{:.2f}x"))

            eq_c4, eq_c5, eq_c6 = st.columns(3)
            eq_c4.metric("PEG 成長估值比", fmt_val(eq['peg_ratio'], fmt="{:.2f}"))
            eq_c5.metric("EV / EBITDA", fmt_val(eq['ev_ebitda'], fmt="{:.1f}x"))
            eq_c6.metric("現金殖利率", fmt_val(eq['div_yield'], fmt="{:.2f}%"))

            upside_str = "暫無目標均價"
            if an_data.get("target_mean", 0) > 0:
                up_val = ((an_data["target_mean"] - res["close"]) / res["close"]) * 100.0
                upside_str = f"目標均價 {an_data['target_mean']:.2f} {curr_sym}（潛在空間 {up_val:+.1f}%，區間 {an_data['target_low']:.1f} ~ {an_data['target_high']:.1f}）"

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
                • <b>估值模型結論</b>：{val_verdict}（每股淨值 Book Value：{fmt_val(eq['book_val'], fmt='{:.2f}')} {curr_sym}）
            </div>
            """, unsafe_allow_html=True)

        with tab_er:
            st.markdown("#### 📈 Earnings Reviewer（季度財報成長動能與盈餘驚奇度）")
            er_c1, er_c2, er_c3 = st.columns(3)
            er_c1.metric("營收年增率 (Rev YoY)", fmt_val(earn['rev_growth'], fmt="{:+.1f}%"))
            er_c2.metric("盈餘年增率 (Earn YoY)", fmt_val(earn['earn_growth'], fmt="{:+.1f}%"))
            er_c3.metric("季度盈餘成長 (QoQ/YoY)", fmt_val(earn['q_earn_growth'], fmt="{:+.1f}%"))

            er_c4, er_c5 = st.columns(2)
            er_c4.metric("近四季累計 EPS (Trailing)", f"{fmt_val(earn['trailing_eps'], fmt='{:.2f}')} {curr_sym}")
            er_c5.metric("法人預估未來 EPS (Forward)", f"{fmt_val(earn['forward_eps'], fmt='{:.2f}')} {curr_sym}")

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
            mr_c2.metric("外資/機構持股比", fmt_val(mkt['inst_held']))
            mr_c3.metric("Beta 波動風險", fmt_val(mkt['beta'], fmt="{:.2f}"))

            mr_c4, mr_c5 = st.columns(2)
            mr_c4.metric("近 20 日相對大盤超額報酬 (Alpha)", fmt_val(res.get('rel_alpha_20d', 0.0), fmt="{:+.2f}%"),
                         "強於大盤" if res.get('rel_alpha_20d', 0.0) > 0 else "弱於大盤")
            mr_c5.metric("近 60 日相對大盤超額報酬 (Alpha)", fmt_val(res.get('rel_alpha_60d', 0.0), fmt="{:+.2f}%"),
                         "波段領頭羊" if res.get('rel_alpha_60d', 0.0) > 0 else "波段落後大盤")

            pos_52w_str = "未揭露"
            if mkt['high_52w'] and mkt['low_52w'] and mkt['high_52w'] > mkt['low_52w']:
                pos_pct = ((res['close'] - mkt['low_52w']) / (mkt['high_52w'] - mkt['low_52w'])) * 100.0
                pos_52w_str = f"位於 52 週區間之 {pos_pct:.1f}% 位階（低點 {mkt['low_52w']:.2f} ～ 高點 {mkt['high_52w']:.2f}）"

            st.markdown(f"""
            <div class="inst-report-box">
                <b>💡 市場與籌碼研究員觀點：</b><br>
                • <b>所屬產業板塊</b>：{mkt['sector']} — {mkt['industry']}<br>
                • <b>52 週價格位階</b>：{pos_52w_str}<br>
                • <b>籌碼穩定度</b>：內部人大股東持股 {fmt_val(mkt['insider_held'])} ｜ 10日均量 vs 3月均量比：{fmt_val((mkt['avg_vol_10d']/(mkt['avg_vol_3m']+1e-9)), fmt='{:.2f}x') if (mkt['avg_vol_10d'] and mkt['avg_vol_3m']) else '--'}
            </div>
            """, unsafe_allow_html=True)

            # 修正問題 1：改用 checkbox 替代巢狀 expander
            if mkt["summary_text"]:
                show_sum = st.checkbox("📖 展開查看企業核心業務與全球競爭護城河簡介", value=False, key=f"chk_summary_{ticker_raw}")
                if show_sum:
                    st.info(mkt["summary_text"])

        with tab_export:
            st.markdown("#### 📥 完整機構級四維度投研報告（可直接複製或下載存檔）")
            report_md = f"""# 🏛️ 【{disp_name}】機構級四維度深度研究報告
- **報告生成時間**：{datetime.now(TAIPEI_TZ).strftime('%Y-%m-%d %H:%M')}
- **當前最新報價**：{res['close']:.2f} {curr_sym} ｜ **量化綜合總分**：{res['total_score']} / 100
- **建議波段停損價**：{res['stop_loss']:.2f} {curr_sym} ｜ **波段第一目標價**：{res['target_1']:.2f} {curr_sym} ｜ **波段獲利目標**：{res['target_60d']:.2f} {curr_sym}

---
## 1. 📊 Financial Analysis（財務分析）
- **三率表現**：毛利率 `{fmt_val(fin['gross_margin'])}` ｜ 營益率 `{fmt_val(fin['op_margin'])}` ｜ 淨利率 `{fmt_val(fin['profit_margin'])}`
- **資本報酬**：ROE `{fmt_val(fin['roe'])}` ｜ ROA `{fmt_val(fin['roa'])}`
- **償債與現金流**：負債權益比 `{fmt_val(fin['debt_to_equity'])}` ｜ 自由現金流 `{format_large_money(fin['free_cf'], curr_code)}`

## 2. 📑 Equity Research（股票估值研究）
- **機構共識評等**：{an_data.get('rec_label', 'N/A')}（共 {an_data.get('opinions', 0)} 家機構追蹤，目標均價 `{an_data.get('target_mean', 0):.2f} {curr_sym}`）
- **核心估值倍數**：Trailing PE `{fmt_val(eq['trailing_pe'], fmt='{:.1f}x')}` ｜ Forward PE `{fmt_val(eq['forward_pe'], fmt='{:.1f}x')}` ｜ P/B `{fmt_val(eq['pb_ratio'], fmt='{:.2f}x')}` ｜ EV/EBITDA `{fmt_val(eq['ev_ebitda'], fmt='{:.1f}x')}`

## 3. 📈 Earnings Reviewer（財報與盈餘分析）
- **成長動能**：營收年增率 `{fmt_val(earn['rev_growth'], fmt='{:+.1f}%')}` ｜ 盈餘年增率 `{fmt_val(earn['earn_growth'], fmt='{:+.1f}%')}`
- **每股盈餘**：Trailing EPS `{fmt_val(earn['trailing_eps'], fmt='{:.2f}')}` ｜ Forward EPS `{fmt_val(earn['forward_eps'], fmt='{:.2f}')}`

## 4. 🌐 Market Researcher（市場與籌碼研究）
- **產業板塊**：{mkt['sector']} / {mkt['industry']} ｜ **總市值**：{format_large_money(mkt['mkt_cap'], curr_code)}
- **機構籌碼與相對強度**：外資/機構持股 `{fmt_val(mkt['inst_held'])}` ｜ 近20日相對大盤 Alpha `{res.get('rel_alpha_20d', 0.0):+.2f}%` ｜ 近60日相對大盤 Alpha `{res.get('rel_alpha_60d', 0.0):+.2f}%`
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

# ================= 模組共用渲染器 (嚴格放置於模式判斷前，守護 Python 語法鏈) =================
def render_analysis_view(res, df_asset, mode_type="tw", custom_spec=None, fallback_warning=None, ticker_raw=None):
    is_downtrend = res.get('is_breakdown', False) or (res['close'] < res['ma_status']['ma20_val'])
    risk_unit = max(res['close'] - res['stop_loss'], res['close'] * 0.015)
    target_1 = res['target_1']
    an_data = res['analyst_data']
    stable_key_suffix = f"{mode_type}_{ticker_raw or 'default'}_{st.session_state.current_user}"

    if mode_type == "futures":
        currency_sym = "點"
        unit_name = "口 (Lots)"
        spec = custom_spec or TW_FUTURES_SPECS.get("WTX")
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
        st.markdown(f"**📌 當前診斷標的：`{disp_header}`** ｜ 👤 操盤手：`{st.session_state.current_user}`")

    if res.get("live_info"):
        status_badge = res['live_info'].get('status_label', '⚪ 歷史報價')
        st.caption(f"⚡ **TWSE 撮合系統** ｜ {status_badge} ｜ 時間：{res['live_info']['time']}")
    elif mode_type == "futures":
        st.caption(f"⚡ **期貨規格載入** ｜ 單位：指數點 ｜ {spec['name']} 保證金參數就位")
    elif mode_type == "us":
        st.caption(f"⚡ **美股即時行情連線** ｜ 幣別：USD ｜ 資料更新時序完整")

    if mode_type in ("tw", "us") and ticker_raw:
        m_key = "tw" if mode_type == "tw" else "us"
        cur_favs = user_memory.get(f"{m_key}_favorites", [])
        is_fav = ticker_raw in cur_favs
        fav_label = f"⭐ 已加入【{st.session_state.current_user}】的常用清單 (點此移出)" if is_fav else f"☆ 收藏至【{st.session_state.current_user}】的常用清單"
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

    # 0. 即時分時走勢圖 & 台股五檔委買賣明細 (修正問題 16：誠實標註為委買賣量差)
    with st.expander("📺 【即時分時走勢圖 (含昨收平盤線) ＆ 五檔委買賣掛單】", expanded=True):
        chart_ticker = "WTX=F" if mode_type == "futures" else (ticker_raw or "2330.TW")
        if mode_type == "futures" and df_futures_bench is None:
            chart_ticker = "^TWII"
        render_intraday_chart_widget(chart_ticker, title_name=disp_header or chart_ticker)

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

            st.caption(f"📌 **五檔委託單量比例**（報價時間：{live_info['time']}）：買量 **{total_bid_v:,} 張 ({bid_ratio:.1f}%)** vs 賣量 **{total_ask_v:,} 張 ({100-bid_ratio:.1f}%)**（此為掛單量差，非實質法人持倉）")
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

    if mode_type in ("tw", "us"):
        render_institutional_research_panel(res, ticker_raw, mode_type=mode_type)

    # 1. 分析師共識 / 模型估計 ＆ 精確下單指引
    guide_title = "🎯 【技術模型多空評等 ＆ 期貨下單執行卡】" if mode_type == "futures" else "🎯 【權威分析師共識 ＆ 精確下單指引】"
    with st.expander(guide_title, expanded=True):
        if an_data.get("has_data"):
            st.markdown(f"**綜合評估：** `{an_data['rec_label']}`")
            st.caption(f"📌 {an_data['rec_desc']}（共計 **{an_data['opinions']} 家** 機構追蹤）")

            a_c1, a_c2 = st.columns(2)
            if an_data['target_mean'] > 0:
                upside_pct = ((an_data['target_mean'] - res['close']) / res['close']) * 100
                a_c1.metric("法人目標點位", f"{an_data['target_mean']:.1f} {currency_sym}", f"{upside_pct:+.1f}% 空間")
            else:
                a_c1.metric("法人目標點位", "波段模型推算")
            a_c2.metric("追蹤覆蓋機構", f"{an_data['opinions']} 家")

            if an_data.get('target_high', 0) > 0:
                st.caption(f"📊 區間分歧度：下檔支撐 **{an_data['target_low']:.1f}** ～ 上檔壓力 **{an_data['target_high']:.1f} {currency_sym}**")
        else:
            st.info("💡 該標的暫無多數機構公開報告，目標價已依技術波動區間推算。")

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
                f1.metric("預估年化殖利率", fmt_val(f_data['yield']))
                f2.metric("Beta 波動係數", fmt_val(f_data['beta'], fmt="{:.2f}"))
            else:
                f1, f2 = st.columns(2)
                f1.metric("ROE 股東權益報酬率", fmt_val(f_data['roe']))
                f2.metric("營業利益率", fmt_val(f_data['op_margin']))
                f3, f4 = st.columns(2)
                f3.metric("本益比 (PE)", fmt_val(f_data['pe'], fmt="{:.1f}x") if (f_data['pe'] and f_data['pe'] > 0) else "不適用/虧損")
                f4.metric("負債比率 (D/E)", fmt_val(f_data['debt_ratio']))
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

    # 7. 修正問題 5：部位風控計算機明確標註公式與輸入依據
    with st.expander(f"💰 【部位風控與建議{unit_name}計算機】", expanded=False):
        col_cap, col_risk = st.columns(2)
        with col_cap:
            if mode_type == "futures":
                default_cap = int(user_memory.get("capital_tw", 1000000))
                cap_step = 100000
                cap_label = "期貨帳戶保證金 (NTD)"
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
            st.caption(f"📌 **風控計算依據**：停損點數 `{risk_unit:.1f}` 點 × 每點 `{spec['tick_value']}` 元 = 單口風險 `{loss_per_unit:,.0f}` 元；保證金要求 `{spec['initial_margin']:,}` 元/口。")
        elif mode_type == "us":
            loss_per_unit = risk_unit * 1.0
            risk_based_pos = int(max_risk_dollar // loss_per_unit) if loss_per_unit > 0 else 0
            capital_max_pos = int(total_capital // res['close']) if res['close'] > 0 else 0
            suggested_pos = min(risk_based_pos, capital_max_pos)
            st.caption(f"📌 **風控計算依據**：每股停損空間 `${risk_unit:.2f}` USD；單筆風險上限 `${max_risk_dollar:,.0f}` USD。")
        else:
            loss_per_unit = risk_unit * 1000.0
            risk_based_pos = int(max_risk_dollar // loss_per_unit) if loss_per_unit > 0 else 0
            capital_max_lots = int(total_capital // (res['close'] * 1000.0)) if res['close'] > 0 else 0
            suggested_pos = min(risk_based_pos, capital_max_lots)
            st.caption(f"📌 **風控計算依據**：每張停損空間 `{risk_unit*1000:,.0f}` 元；單筆最大容許風險 `{max_risk_dollar:,.0f}` 元。")

        potential_reward = max(res['target_60d'] - res['close'], 0)
        rr_ratio = potential_reward / risk_unit if risk_unit > 0 else 0

        if is_downtrend:
            st.warning(f"⚠️ **空方弱勢警示**：目前處於跌破月線格局，系統建議進場數量為 **0 {unit_name}**（觀望為宜）。依個人風控上限計算，最多承受規模為 **{suggested_pos} {unit_name}**。")
        else:
            b1, b2 = st.columns(2)
            b1.metric("單筆最大容許虧損", f"{int(max_risk_dollar):,} 元" if mode_type != "us" else f"{int(max_risk_dollar):,} USD")
            b2.metric("建議最大進場數量", f"{suggested_pos} {unit_name}")
            b3, b4 = st.columns(2)
            b3.metric("目標獲利區", f"{res['target_60d']:.1f} {currency_sym}")
            b4.metric("預期盈虧比 (R/R)", f"{rr_ratio:.2f} : 1")

    # 8. 修正問題 9：盯市 MDD 回測
    with st.expander(f"📊 【過去 1 年{unit_name}策略回測數據 (逐日盯市 MDD)】", expanded=False):
        bt = backtest_strategy(df_asset, market_type=mode_type, custom_spec=spec if mode_type == "futures" else None)
        if bt:
            bt1, bt2 = st.columns(2)
            bt1.metric("近 1 年訊號次數", f"{bt['count']} 次")
            bt2.metric("持有 5 日勝率", f"{bt['win_rate']:.1f}%")
            bt3, bt4 = st.columns(2)
            bt3.metric("平均淨報酬率", f"{bt['avg_return']:+.2f}%", help=bt.get('fee_label', '已扣除成本'))
            bt4.metric("逐日盯市最大回撤 (MDD)", f"{bt['mdd']:.2f}%", help="持倉 5 日間逐日市價連續權益曲線之最大峰谷回撤")
            st.caption(f"📌 單部位循序進出（無前視偏誤）、單次最差交易：`{bt['worst_loss']:.2f}%` ｜ 成本設定：`{bt.get('fee_label')}`")
        else:
            st.write("該標的歷史數據樣本不足或無法計算回測。")

    # 9. 日K均線走勢圖
    with st.expander("📈 【近 60 日均線 (5/20/60MA) 波段走勢圖】", expanded=False):
        valid_cols = ['Close']
        for c in ['MA5', 'MA20', 'MA60']:
            if c in df_asset.columns and df_asset[c].notna().sum() > 5:
                valid_cols.append(c)
        chart_data = df_asset[valid_cols].dropna().tail(60)
        st.line_chart(chart_data)

# ================= 模式 0：📺 大盤即時分時看盤室 (修正問題 23：Fragment 自動刷新) =================
@st.fragment(run_every=30 if auto_refresh and st.session_state.main_mode == "live_watch" else None)
def render_live_watch_mode():
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
    st.caption(f"資料時間：{dash['data_time']} ｜ 支援無阻塞 30 秒自動刷新")

    if st.button("🔄 立即刷新即時走勢與大盤統計", use_container_width=True, key="btn_refresh_live_watch"):
        _fetch_twse_market_dashboard_cached.clear()
        _fetch_intraday_series_cached.clear()
        _fetch_live_macro_rss_cached.clear()
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
    live_rss = fetch_live_macro_rss("台股 OR 費半 OR 聯準會 OR 台積電")
    if live_rss:
        for r_item in live_rss[:5]:
            safe_rss_title = html.escape(r_item['title'])
            safe_rss_src = html.escape(r_item['source'])
            st.markdown(f"• **[{safe_rss_title}]({r_item['link']})** — `{safe_rss_src}` ({r_item['pub_date']})")
    else:
        st.caption("目前暫無即時外電快訊。")

if st.session_state.main_mode == "live_watch":
    render_live_watch_mode()

# ================= 模式 1：🔍 台股診斷 (修正問題 7 & 13) =================
elif st.session_state.main_mode == "tw_stock":
    st.subheader(f"🔍 台股全維度深度體檢（👤 {st.session_state.current_user}）")

    def set_and_jump_tw_ticker(target_code: str):
        clean_code = target_code.strip().upper()
        if clean_code.isdigit():
            clean_code += ".TW"
        st.session_state.tw_ticker_field = clean_code
        st.session_state.selected_tw_ticker = clean_code
        st.session_state.analysis_cache_tw = None
        st.session_state.auto_run_tw = True

    tw_favs = user_memory.get("tw_favorites", ["2330.TW", "2454.TW", "2317.TW", "0050.TW"])
    st.caption(f"⭐ **【{st.session_state.current_user}】的常用股票清單**（點選一秒自動診斷）：")

    fav_cols = st.columns(2)
    for idx, fav_code in enumerate(tw_favs[:6]):
        col_target = fav_cols[idx % 2]
        display_label = get_stock_display_label(fav_code, is_fav=True)
        if col_target.button(display_label, use_container_width=True, key=f"tw_fav_{fav_code}"):
            set_and_jump_tw_ticker(fav_code)
            st.rerun()

    tw_recents = [r for r in user_memory.get("tw_recent", []) if r not in tw_favs][:4]
    if tw_recents:
        st.caption(f"🕒 **【{st.session_state.current_user}】的最近查詢紀錄**：")
        rec_cols = st.columns(2)
        for r_idx, r_code in enumerate(tw_recents):
            col_rec_target = rec_cols[r_idx % 2]
            rec_display = get_stock_display_label(r_code, is_fav=False)
            if col_rec_target.button(rec_display, use_container_width=True, key=f"tw_rec_{r_code}"):
                set_and_jump_tw_ticker(r_code)
                st.rerun()

    st.caption("💡 **台股輸入格式指引**：支援純代碼（如 `2330`、`00679B`，系統將自動偵測上市或上櫃）｜ 亦可明確輸入 `.TW` 或 `.TWO`")

    with st.form("tw_search_form", clear_on_submit=False):
        col_input, col_btn = st.columns([2.4, 1.6])
        with col_input:
            raw_tw_input = st.text_input(
                "輸入台股代碼",
                label_visibility="collapsed",
                placeholder="例：2330、00679B 或 6488.TWO",
                key="tw_ticker_field"
            )
        with col_btn:
            exec_clicked = st.form_submit_button("🚀 診斷台股", type="primary", use_container_width=True)

    with st.expander(f"⚙️ 管理【{st.session_state.current_user}】的台股常用清單", expanded=False):
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

        del_cols = st.columns(2)
        for d_idx, d_code in enumerate(user_memory["tw_favorites"]):
            del_label = f"❌ {get_stock_display_label(d_code, is_fav=False)}"
            if del_cols[d_idx % 2].button(del_label, key=f"del_tw_fav_{d_code}", use_container_width=True):
                user_memory["tw_favorites"].remove(d_code)
                save_user_data()
                st.rerun()

    cleaned_raw = raw_tw_input.strip().upper()

    if exec_clicked or st.session_state.auto_run_tw:
        st.session_state.auto_run_tw = False

        # 修正問題 7：台股模式拒絕純美股英文代碼誤輸
        if re.match(r'^[A-Z]{2,5}$', cleaned_raw) and not any(cleaned_raw.startswith(p) for p in ('00', '01')):
            st.error("🚨 偵測到您輸入的可能是美股代碼，請切換至上方【🇺🇸 美股診斷】功能進行查詢。")
        else:
            with st.spinner("連線行情主機與四大權威機構資料庫中..."):
                # 修正問題 7：自動相容 .TW 與 .TWO，上市失敗自動重試上櫃
                candidates = []
                if cleaned_raw.endswith(".TW") or cleaned_raw.endswith(".TWO"):
                    candidates = [cleaned_raw]
                else:
                    candidates = [f"{cleaned_raw}.TW", f"{cleaned_raw}.TWO"]

                df_stk = None
                final_ticker = None
                for cand in candidates:
                    df_try = fetch_and_calc(cand)
                    if df_try is not None:
                        df_stk = df_try
                        final_ticker = cand
                        break

                if df_stk is not None and final_ticker is not None:
                    st.session_state.selected_tw_ticker = final_ticker
                    st.session_state.tw_ticker_field = final_ticker
                    r = analyze_full_stock(final_ticker, df_stk, df_market, df_futures_bench, df_tsm, df_sox, global_forex, asset_type="tw", include_inst_suite=True)
                    st.session_state.analysis_cache_tw = (r, df_stk, final_ticker)
                    add_recent_history("tw", final_ticker)
                else:
                    st.session_state.analysis_cache_tw = None
                    st.error(f"無法取得【{cleaned_raw}】行情數據。請確認代碼是否正確（支援如 2330、00679B 或 6488.TWO）。")

    if st.session_state.analysis_cache_tw is not None:
        r, df_stk, cur_t = st.session_state.analysis_cache_tw
        render_analysis_view(r, df_stk, mode_type="tw", ticker_raw=cur_t)

# ================= 模式 2：🇺🇸 美股診斷 =================
elif st.session_state.main_mode == "us_stock":
    st.subheader(f"🇺🇸 美股全維度深度體檢（👤 {st.session_state.current_user}）")

    def set_and_jump_us_ticker(target_code: str):
        clean_code = target_code.strip().upper()
        st.session_state.us_ticker_field = clean_code
        st.session_state.selected_us_ticker = clean_code
        st.session_state.analysis_cache_us = None
        st.session_state.auto_run_us = True

    us_favs = user_memory.get("us_favorites", ["NVDA", "AAPL", "MSFT", "TSLA"])
    st.caption(f"⭐ **【{st.session_state.current_user}】的常用美股清單**（點選一秒自動診斷）：")

    fav_u_cols = st.columns(2)
    for idx, fav_u_code in enumerate(us_favs[:6]):
        col_u_target = fav_u_cols[idx % 2]
        display_u_label = get_stock_display_label(fav_u_code, is_fav=True)
        if col_u_target.button(display_u_label, use_container_width=True, key=f"us_fav_{fav_u_code}"):
            set_and_jump_us_ticker(fav_u_code)
            st.rerun()

    us_recents = [r for r in user_memory.get("us_recent", []) if r not in us_favs][:4]
    if us_recents:
        st.caption(f"🕒 **【{st.session_state.current_user}】的最近查詢紀錄**：")
        rec_u_cols = st.columns(2)
        for ru_idx, ru_code in enumerate(us_recents):
            col_rec_u = rec_u_cols[ru_idx % 2]
            rec_u_label = get_stock_display_label(ru_code, is_fav=False)
            if col_rec_u.button(rec_u_label, use_container_width=True, key=f"us_rec_{ru_code}"):
                set_and_jump_us_ticker(ru_code)
                st.rerun()

    st.caption("💡 **美股輸入格式指引**：請輸入美股英文代號（如 `NVDA`、`AAPL`、`TSLA`、`WMT`），大小寫皆可自動轉換。")

    with st.form("us_search_form", clear_on_submit=False):
        col_u_in, col_u_btn = st.columns([2.4, 1.6])
        with col_u_in:
            raw_us_input = st.text_input(
                "輸入美股代碼",
                label_visibility="collapsed",
                placeholder="例：NVDA、AAPL、WMT",
                key="us_ticker_field"
            )
        with col_u_btn:
            exec_us_btn = st.form_submit_button("🚀 診斷美股", type="primary", use_container_width=True)

    cleaned_us_ticker = raw_us_input.strip().upper()

    with st.expander(f"⚙️ 管理【{st.session_state.current_user}】的美股常用清單", expanded=False):
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
                r_us = analyze_full_stock(cleaned_us_ticker, df_stk_us, df_spx, None, None, df_sox, global_forex, asset_type="us", include_inst_suite=True)
                st.session_state.analysis_cache_us = (r_us, df_stk_us, cleaned_us_ticker)
                add_recent_history("us", cleaned_us_ticker)
            else:
                st.session_state.analysis_cache_us = None
                st.error("無法取得該美股行情，請確認英文代碼（如 NVDA, AAPL, TSM, W
