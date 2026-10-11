import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

# 頁面配置 (行動端最適化)
st.set_page_config(
    page_title="次日開市與即時量化決策站",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 注入手機端高觸感 CSS (大按鈕、防誤觸、直覺卡片)
st.markdown("""
<style>
    div.stButton > button {
        width: 100%;
        height: 3.2rem;
        font-size: 1.05rem !important;
        font-weight: 600 !important;
        border-radius: 12px !important;
        margin-bottom: 0.25rem;
        transition: all 0.15s ease-in-out;
    }
    div.stTextInput > div > div > input {
        height: 3rem !important;
        font-size: 1.1rem !important;
        border-radius: 10px !important;
    }
    div[data-testid="stMetric"] {
        background-color: rgba(128, 128, 128, 0.08);
        border: 1px solid rgba(128, 128, 128, 0.2);
        padding: 0.8rem 1rem;
        border-radius: 14px;
        margin-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

TAIPEI_TZ = timezone(timedelta(hours=8))

# ----------------- 通行密碼防護 -----------------
ACCESS_PASSWORD = st.secrets.get("PASSWORD", "invest888")

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

# ----------------- 數值安全轉換工具 -----------------
def safe_float(val, default=0.0):
    try:
        if val is None or val == "" or val == "-":
            return default
        f = float(val)
        return default if np.isnan(f) else f
    except (ValueError, TypeError):
        return default

# ----------------- 權威 API 1：臺灣證券交易所官方即時行情 (TWSE MIS) -----------------
def fetch_twse_realtime(ticker: str):
    clean_code = ticker.replace(".TW", "").replace(".TWO", "").strip()
    market = "otc" if ".TWO" in ticker.upper() else "tse"
    ex_ch = f"{market}_{clean_code}.tw"
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
                z_price = safe_float(item.get("z"))
                if z_price <= 0:
                    b_list = item.get("b", "_").split("_")
                    z_price = safe_float(b_list[0], default=y_close)

                return {
                    "code": clean_code,
                    "name": item.get("n", clean_code),
                    "match_price": z_price if z_price > 0 else y_close,
                    "open": safe_float(item.get("o"), default=z_price),
                    "high": safe_float(item.get("h"), default=z_price),
                    "low": safe_float(item.get("l"), default=z_price),
                    "volume": safe_float(item.get("v"), default=0),
                    "yesterday_close": y_close,
                    "date_str": item.get("d", ""),
                    "time": item.get("t", ""),
                    "is_live": True
                }
    except Exception:
        pass
    return None

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
                        return {"usd_twd": val, "source": "臺灣銀行官方牌告"}
    except Exception:
        pass
    return None

# ----------------- 歷史技術數據與指標計算 -----------------
@st.cache_data(ttl=60)
def fetch_and_calc(ticker: str, period: str = "1y"):
    try:
        obj = yf.Ticker(ticker)
        df = obj.history(period=period)
        if df.empty or len(df) < 20:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()

        if ".TW" in ticker.upper():
            twse_live = fetch_twse_realtime(ticker)
            if twse_live and twse_live["match_price"] > 0:
                now_taipei = datetime.now(TAIPEI_TZ)
                today_str = now_taipei.strftime("%Y%m%d")

                if twse_live.get("date_str") == today_str or now_taipei.weekday() < 5:
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

# ----------------- 基本面體質數據 -----------------
@st.cache_data(ttl=7200)
def fetch_fundamentals(ticker: str):
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        roe_raw = info.get('returnOnEquity', None)
        op_raw = info.get('operatingMargins', None)
        pe_raw = info.get('trailingPE', None)
        de_raw = info.get('debtToEquity', None)

        roe_val = safe_float(roe_raw * 100 if roe_raw is not None else 12.0)
        op_margin_val = safe_float(op_raw * 100 if op_raw is not None else 10.0)
        pe_val = safe_float(pe_raw if pe_raw is not None else 20.0)
        de_val = safe_float(de_raw if de_raw is not None else 65.0)

        fund_score = 0
        reasons = []

        if roe_val >= 15:
            fund_score += 15
            reasons.append(f"ROE 達 {roe_val:.1f}%，資本回報效率極佳")
        elif roe_val >= 10:
            fund_score += 10
            reasons.append(f"ROE 達 {roe_val:.1f}%，維持穩健水準")
        else:
            reasons.append(f"ROE 偏低 ({roe_val:.1f}%)")

        if op_margin_val >= 15:
            fund_score += 15
            reasons.append(f"營業利益率 {op_margin_val:.1f}%，本業競爭優勢顯著")
        elif op_margin_val >= 8:
            fund_score += 10
            reasons.append(f"營業利益率 {op_margin_val:.1f}%，本業獲利扎實")
        else:
            reasons.append(f"營業利益率偏低 ({op_margin_val:.1f}%)")

        if 8 <= pe_val <= 25:
            fund_score += 10
            reasons.append(f"本益比 {pe_val:.1f}x，估值處安全區間")
        elif pe_val < 8:
            fund_score += 7
            reasons.append(f"本益比低估 ({pe_val:.1f}x)")
        else:
            fund_score += 4
            reasons.append(f"本益比偏高 ({pe_val:.1f}x)，需成長性支撐")

        if de_val <= 80:
            fund_score += 10
            reasons.append(f"負債比率健康 ({de_val:.1f}%)，財務抗風險力強")
        elif de_val <= 150:
            fund_score += 6
            reasons.append(f"負債比率適中 ({de_val:.1f}%)")
        else:
            reasons.append(f"負債比率偏高 ({de_val:.1f}%)")

        return {
            "score": fund_score,
            "roe": roe_val,
            "op_margin": op_margin_val,
            "pe": pe_val,
            "debt_ratio": de_val,
            "reasons": reasons
        }
    except Exception:
        return {
            "score": 30,
            "roe": 12.0,
            "op_margin": 10.0,
            "pe": 18.0,
            "debt_ratio": 70.0,
            "reasons": ["採用行業基準均值計算"]
        }

# ----------------- 開盤即時與均線分析 -----------------
def analyze_opening_and_ma(df_stock, live_info=None):
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
        ma_alignment = "🔥 完美多頭排列 (股價 > 日線 > 月線 > 季線)"
        ma_score = 25
    elif close > ma20 and ma20 > ma60:
        ma_alignment = "📈 中長線偏多架構 (守穩月線與季線)"
        ma_score = 18
    elif close < ma5 < ma20 < ma60:
        ma_alignment = "❄️ 完全空頭排列 (股價被所有均線下壓)"
        ma_score = 0
    else:
        ma_alignment = "🔄 均線震盪糾結 (多空方向待表態)"
        ma_score = 10

    open_p = safe_float(last['Open'], close)
    prev_close = safe_float(prev['Close'], close)
    gap_pct = ((open_p - prev_close) / (prev_close + 1e-9)) * 100
    intraday_pct = ((close - open_p) / (open_p + 1e-9)) * 100

    opening_diag = []
    if gap_pct >= 1.5:
        opening_diag.append(f"強勢跳空開高 (+{gap_pct:.2f}%)，多方意圖明確。")
    elif gap_pct <= -1.5:
        opening_diag.append(f"弱勢跳空開低 ({gap_pct:.2f}%)，下檔承接力道待觀察。")
    else:
        opening_diag.append(f"平盤附近開出 ({gap_pct:+.2f}%)，由盤中量能決定方向。")

    if close > open_p:
        k_type = "🔴 盤中實體紅 K (開低走高或強開強走)"
        opening_diag.append("多方持續推進，買盤居主導地位。")
    elif close < open_p:
        k_type = "🟢 盤中實體黑 K (開高走低或弱勢下殺)"
        opening_diag.append("需嚴防主力開高出貨或高檔解套賣壓。")
    else:
        k_type = "⚪ 盤中十字星 (多空平手拉鋸)"

    return ma_status, ma_alignment, ma_score, gap_pct, intraday_pct, k_type, opening_diag

# ----------------- 歷史客觀勝率回測 -----------------
def backtest_strategy(df_stock):
    if len(df_stock) < 60:
        return None

    signals = (
        (df_stock['Close'] > df_stock['MA20']) &
        (df_stock['Close'] > df_stock['Close'].shift(1)) &
        (df_stock['Volume'] > df_stock['Vol_MA5']) &
        (df_stock['OSC'] > 0)
    )

    trade_returns = []
    indices = np.where(signals)[0]

    for idx in indices:
        if idx + 5 < len(df_stock):
            entry_p = safe_float(df_stock['Close'].iloc[idx])
            exit_p = safe_float(df_stock['Close'].iloc[idx + 5])
            if entry_p > 0:
                trade_returns.append((exit_p - entry_p) / entry_p * 100)

    if not trade_returns:
        return None

    win_rate = (len([r for r in trade_returns if r > 0]) / len(trade_returns)) * 100
    avg_return = np.mean(trade_returns)
    max_drawdown = min(trade_returns)

    return {
        "count": len(trade_returns),
        "win_rate": win_rate,
        "avg_return": avg_return,
        "max_drawdown": max_drawdown
    }

# ----------------- 全域外匯數據分析 -----------------
@st.cache_data(ttl=300)
def analyze_forex_data():
    res = {
        "twd_rate": 32.2,
        "twd_change": 0.0,
        "twd_status": "匯率平穩",
        "twd_trend": "震盪",
        "dxy_rate": 103.5,
        "dxy_trend": "中立",
        "jpy_rate": 150.0,
        "jpy_risk": "正常",
        "source": "Yahoo 即時外匯"
    }

    bot_data = fetch_bot_forex()
    if bot_data:
        res["twd_rate"] = bot_data["usd_twd"]
        res["source"] = bot_data["source"]

    df_usdtwd = fetch_and_calc("USDTWD=X")
    if df_usdtwd is None:
        df_usdtwd = fetch_and_calc("TWD=X")
    df_dxy = fetch_and_calc("DX-Y.NYB")
    df_jpy = fetch_and_calc("JPY=X")

    try:
        if df_usdtwd is not None and len(df_usdtwd) >= 2:
            last_twd = safe_float(df_usdtwd.iloc[-1]['Close'], 32.2)
            prev_twd = safe_float(df_usdtwd.iloc[-2]['Close'], 32.2)
            ma20_twd = safe_float(df_usdtwd['MA20'].iloc[-1], last_twd)

            if not bot_data:
                res["twd_rate"] = last_twd

            diff = last_twd - prev_twd
            res["twd_change"] = diff

            if diff < -0.05:
                res["twd_status"] = "🟢 今日強勢升值 (外資熱錢湧入)"
            elif diff > 0.05:
                res["twd_status"] = "🔴 今日明顯貶值 (外資匯出壓力)"
            else:
                res["twd_status"] = "⚪ 今日窄幅震盪整理"

            if res["twd_rate"] < ma20_twd:
                res["twd_trend"] = "波段升值格局 (資金面有利台股權值股)"
            else:
                res["twd_trend"] = "波段貶值格局 (外資權值股承壓，有利外銷出口)"

        if df_dxy is not None and len(df_dxy) >= 2:
            last_dxy = safe_float(df_dxy.iloc[-1]['Close'], 103.5)
            ma20_dxy = safe_float(df_dxy['MA20'].iloc[-1], last_dxy)
            res["dxy_rate"] = last_dxy
            res["dxy_trend"] = "偏強 (美元強勢，新興市場資金保守)" if last_dxy > ma20_dxy else "偏弱 (美元回落，熱錢回流)"

        if df_jpy is not None and len(df_jpy) >= 5:
            last_jpy = safe_float(df_jpy.iloc[-1]['Close'], 150.0)
            ma5_jpy = safe_float(df_jpy['MA5'].iloc[-1], last_jpy)
            res["jpy_rate"] = last_jpy
            if (last_jpy - ma5_jpy) / (ma5_jpy + 1e-9) < -0.015:
                res["jpy_risk"] = "⚠️ 警示：日圓近期急升，提防日圓套利平倉 (Carry Trade Unwind) 賣壓！"
            else:
                res["jpy_risk"] = "✅ 正常：日圓匯率平穩，無顯著平倉風險"
    except Exception:
        pass

    return res

# ----------------- 全維度綜合評估 -----------------
def analyze_full_stock(ticker, df_stock, df_market, df_futures, df_tsm, df_sox, forex_info):
    fund_data = fetch_fundamentals(ticker)
    live_twse = fetch_twse_realtime(ticker)
    ma_status, ma_alignment, ma_score, gap_pct, intraday_pct, k_type, opening_diag = analyze_opening_and_ma(df_stock, live_twse)

    last_stk = df_stock.iloc[-1]
    prev_stk = df_stock.iloc[-2] if len(df_stock) >= 2 else last_stk
    close = safe_float(last_stk['Close'])
    atr_val = safe_float(last_stk['ATR14'], default=close * 0.03)

    global_score = 0
    global_reasons = []
    try:
        tsm_change = ((df_tsm['Close'].iloc[-1] - df_tsm['Close'].iloc[-2]) / df_tsm['Close'].iloc[-2]) * 100
        if tsm_change >= 1.5:
            global_score += 15
            global_reasons.append(f"TSM ADR 大漲 ({tsm_change:+.1f}%)，國際連動強勁")
        elif tsm_change > 0:
            global_score += 10
            global_reasons.append(f"TSM ADR 小漲 ({tsm_change:+.1f}%)，美股氛圍平穩偏多")
        elif tsm_change > -1.5:
            global_score += 6
            global_reasons.append(f"TSM ADR 小跌 ({tsm_change:+.1f}%)，留意早盤震盪")
        else:
            global_reasons.append(f"TSM ADR 重挫 ({tsm_change:+.1f}%)，嚴防開盤恐慌跳空")

        if "升值" in forex_info['twd_status']:
            global_reasons.append(f"新台幣走升 ({forex_info['twd_rate']:.2f})，熱錢匯入台股")
        else:
            global_reasons.append(f"新台幣匯率整理 ({forex_info['twd_rate']:.2f})")
    except Exception:
        global_score = 8
        global_reasons.append("國際美股數據採中立基準分")

    mkt_score = 0
    mkt_reasons = []
    if df_market is not None and not df_market.empty:
        last_mkt = df_market.iloc[-1]
        if last_mkt['Close'] > last_mkt['MA20']:
            mkt_score += 12
            mkt_reasons.append("大盤站上月線 (20MA)，多方掌握發球權")
        else:
            mkt_reasons.append("大盤跌破月線，系統性拉回風險偏高")
        if last_mkt['MA20'] > last_mkt['MA60']:
            mkt_score += 8
            mkt_reasons.append("大盤季線多頭架構 (20MA > 60MA)")

    tech_score = 0
    tech_reasons = []
    vol_ratio = safe_float(last_stk['Volume']) / (safe_float(last_stk['Vol_MA5']) + 1e-9)
    if close > prev_stk['Close'] and vol_ratio >= 1.3:
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

    total_score = int((global_score + mkt_score + ma_score + tech_score) * 0.6 + fund_data['score'] * 0.8)
    total_score = min(max(total_score, 0), 100)

    ma20_val = safe_float(last_stk['MA20'], close * 0.95)
    stop_loss = max(close - 2 * atr_val, ma20_val)
    target_60d = safe_float(df_stock['High'].tail(60).max(), close * 1.1)

    return {
        "total_score": total_score,
        "fund_score": fund_data['score'],
        "close": close,
        "stop_loss": stop_loss,
        "target_60d": target_60d,
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
        "forex_info": forex_info,
        "live_info": live_twse
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

# ----------------- 狀態初始化 -----------------
if "main_mode" not in st.session_state:
    st.session_state.main_mode = "single"

if "sub_tab" not in st.session_state:
    st.session_state.sub_tab = "dec"

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "2330.TW"

if "analysis_cache" not in st.session_state:
    st.session_state.analysis_cache = None

# ----------------- 頂部三大主功能切換區 (配置獨立 key) -----------------
st.title("📱 股期決策旗艦站")

btn_col1, btn_col2, btn_col3 = st.columns(3)
with btn_col1:
    if st.button("🔍 個股診斷", type="primary" if st.session_state.main_mode == "single" else "secondary", use_container_width=True, key="main_nav_single"):
        st.session_state.main_mode = "single"
        st.rerun()

with btn_col2:
    if st.button("💎 優質雷達", type="primary" if st.session_state.main_mode == "market" else "secondary", use_container_width=True, key="main_nav_market"):
        st.session_state.main_mode = "market"
        st.rerun()

with btn_col3:
    if st.button("💱 外匯大盤", type="primary" if st.session_state.main_mode == "forex" else "secondary", use_container_width=True, key="main_nav_forex"):
        st.session_state.main_mode = "forex"
        st.rerun()

st.write("")

# 全域預載資料
df_market = fetch_and_calc("^TWII")
df_futures = fetch_and_calc("WTX=F")
if df_futures is None:
    df_futures = df_market
df_tsm = fetch_and_calc("TSM")
df_sox = fetch_and_calc("^SOX")
global_forex = analyze_forex_data()

# ================= 模式 1：個股全維度深度體檢 =================
if st.session_state.main_mode == "single":
    st.caption("⚡ 常用熱門股（點擊切換）：")

    q1, q2 = st.columns(2)
    with q1:
        if st.button("台積電 (2330)", use_container_width=True, key="qp_2330"):
            st.session_state.selected_ticker = "2330.TW"
            st.session_state.analysis_cache = None
            st.rerun()
        if st.button("鴻海 (2317)", use_container_width=True, key="qp_2317"):
            st.session_state.selected_ticker = "2317.TW"
            st.session_state.analysis_cache = None
            st.rerun()

    with q2:
        if st.button("聯發科 (2454)", use_container_width=True, key="qp_2454"):
            st.session_state.selected_ticker = "2454.TW"
            st.session_state.analysis_cache = None
            st.rerun()
        if st.button("富邦金 (2881)", use_container_width=True, key="qp_2881"):
            st.session_state.selected_ticker = "2881.TW"
            st.session_state.analysis_cache = None
            st.rerun()

    ticker_input = st.text_input("輸入查詢代碼 (上市 .TW / 上櫃 .TWO)", value=st.session_state.selected_ticker, key="ticker_input_field")

    if st.button("🚀 執行全維度深度診斷", type="primary", use_container_width=True, key="run_single_analysis_btn"):
        with st.spinner("連線 TWSE 撮合與官方主機計算中..."):
            df_stock = fetch_and_calc(ticker_input.strip())
            if df_stock is not None:
                res = analyze_full_stock(ticker_input.strip(), df_stock, df_market, df_futures, df_tsm, df_sox, global_forex)
                st.session_state.analysis_cache = (res, df_stock)
            else:
                st.session_state.analysis_cache = None
                st.error("無法取得該標的行情數據，請確認代碼是否正確。")

    if st.session_state.analysis_cache is not None:
        res, df_stock = st.session_state.analysis_cache
        is_below_stop = res['close'] <= res['stop_loss']
        risk_unit = max(res['close'] - res['stop_loss'], 0.0)
        target_1 = res['close'] + (1.5 * max(risk_unit, res['close'] * 0.03))

        st.divider()

        if res.get("live_info"):
            st.caption(f"⚡ **已直連臺灣證券交易所 (TWSE) 官方即時撮合** ｜ 時間：{res['live_info']['time']}")

        c1, c2 = st.columns(2)
        c1.metric("綜合決策總分", f"{res['total_score']} / 100")
        c2.metric("最新成交價", f"{res['close']:.2f} 元")

        c3, c4 = st.columns(2)
        c3.metric("建議防守價 (停損)", f"{res['stop_loss']:.2f} 元")
        risk_pct = (risk_unit / res['close']) * 100 if not is_below_stop else 0.0
        c4.metric("最大預期風險", f"{risk_pct:.2f}%" if not is_below_stop else "已在防守線下")

        st.write("---")
        st.markdown("### 🧭 功能模組切換（點選直接展開）")

        # 3×3 九宮格按鈕 (配置完全獨立 key)
        nav1, nav2, nav3 = st.columns(3)
        with nav1:
            if st.button("🎯 決策結論", type="primary" if st.session_state.sub_tab == "dec" else "secondary", use_container_width=True, key="grid_btn_dec"):
                st.session_state.sub_tab = "dec"
                st.rerun()
            if st.button("💎 企業體質", type="primary" if st.session_state.sub_tab == "fund" else "secondary", use_container_width=True, key="grid_btn_fund"):
                st.session_state.sub_tab = "fund"
                st.rerun()
            if st.button("📊 歷史勝率", type="primary" if st.session_state.sub_tab == "bt" else "secondary", use_container_width=True, key="grid_btn_bt"):
                st.session_state.sub_tab = "bt"
                st.rerun()

        with nav2:
            if st.button("⚡ 開盤即時", type="primary" if st.session_state.sub_tab == "rt" else "secondary", use_container_width=True, key="grid_btn_rt"):
                st.session_state.sub_tab = "rt"
                st.rerun()
            if st.button("🚪 階梯停利", type="primary" if st.session_state.sub_tab == "exit" else "secondary", use_container_width=True, key="grid_btn_exit"):
                st.session_state.sub_tab = "exit"
                st.rerun()
            if st.button("💱 匯率連動", type="primary" if st.session_state.sub_tab == "forex" else "secondary", use_container_width=True, key="grid_btn_forex"):
                st.session_state.sub_tab = "forex"
                st.rerun()

        with nav3:
            if st.button("📏 均線矩陣", type="primary" if st.session_state.sub_tab == "ma" else "secondary", use_container_width=True, key="grid_btn_ma"):
                st.session_state.sub_tab = "ma"
                st.rerun()
            if st.button("💰 風控試算", type="primary" if st.session_state.sub_tab == "calc" else "secondary", use_container_width=True, key="grid_btn_calc"):
                st.session_state.sub_tab = "calc"
                st.rerun()
            if st.button("📈 走勢圖表", type="primary" if st.session_state.sub_tab == "chart" else "secondary", use_container_width=True, key="grid_btn_chart"):
                st.session_state.sub_tab = "chart"
                st.rerun()

        st.write("---")

        if st.session_state.sub_tab == "dec":
            st.subheader("🎯 綜合決策結論")
            if is_below_stop:
                st.error("### 🔴 現價已跌破建議防守線：嚴禁進場！")
                st.write(f"- 當前價位（{res['close']:.2f} 元）低於防守點（{res['stop_loss']:.2f} 元），技術面偏空，切勿逆勢摸底。")
            elif res['total_score'] >= 75:
                st.success("### 🟢 積極偏多：體質與量價動能同步翻多，適合進場")
                st.write(f"- 建議防守價位：**{res['stop_loss']:.2f} 元**。")
            elif 60 <= res['total_score'] < 75:
                st.warning("### 🟡 穩健觀察：指標整理或分歧，僅限 1/3 以下微型試單")
            else:
                st.error("### 🔴 暫緩進場：評價過高或短期均線下壓，現金為王")

        elif st.session_state.sub_tab == "rt":
            st.subheader("⚡ 開盤即時狀態診斷 (TWSE 官方撮合)")
            st.markdown(f"**當前 K 棒型態：** `{res['k_type']}`")
            k1, k2 = st.columns(2)
            k1.metric("開盤跳空幅度", f"{res['gap_pct']:+.2f}%")
            k2.metric("開盤至今漲跌", f"{res['intraday_pct']:+.2f}%")
            st.write("---")
            st.markdown("**【即時開盤操作指引】**")
            for d in res['opening_diag']:
                st.write(f"• {d}")
            if res['gap_pct'] >= 2.5 and res['intraday_pct'] < 0:
                st.warning("⚠️ **警告：開大幅跳高但盤中走黑 K！** 典型主力開高出貨訊號，切勿市價追高！")
            elif res['gap_pct'] > 0 and res['intraday_pct'] > 0:
                st.success("🟢 **多方強推格局：跳空開高且紅 K 續攻！** 買盤扎實，可依計畫分批布局。")

        elif st.session_state.sub_tab == "ma":
            st.subheader("📏 日線・月線・季線 位階矩陣")
            st.markdown(f"**均線排列結構：** `{res['ma_alignment']}`")
            m1, m2, m3 = st.columns(3)
            m1.metric("日線 (5MA)", f"{res['ma_status']['ma5_val']:.2f}", f"{res['ma_status']['ma5_diff']:+.1f}%")
            m2.metric("月線 (20MA)", f"{res['ma_status']['ma20_val']:.2f}", f"{res['ma_status']['ma20_diff']:+.1f}%")
            m3.metric("季線 (60MA)", f"{res['ma_status']['ma60_val']:.2f}", f"{res['ma_status']['ma60_diff']:+.1f}%")
            st.caption("※ 正負百分比代表當前股價高於（+）或低於（-）該均線之乖離幅度。")

        elif st.session_state.sub_tab == "fund":
            st.subheader("💎 企業基本面體質護城河")
            f_data = res['fund_data']
            f1, f2 = st.columns(2)
            f1.metric("ROE 股東權益報酬率", f"{f_data['roe']:.1f}%")
            f2.metric("營業利益率", f"{f_data['op_margin']:.1f}%")
            f3, f4 = st.columns(2)
            f3.metric("本益比 (PE)", f"{f_data['pe']:.1f}x")
            f4.metric("負債比率 (D/E)", f"{f_data['debt_ratio']:.1f}%")
            st.write("---")
            for r in f_data['reasons']:
                st.write(f"• {r}")

        elif st.session_state.sub_tab == "exit":
            st.subheader("🚪 機械化分階出場規劃")
            st.markdown(f"""
            - **初始防守停損**：跌破 **`{res['stop_loss']:.2f}` 元** 嚴格離場，絕不凹單。
            - **第一階段目標（減碼 1/2）**：達 **`{target_1:.2f}` 元**（1.5R 盈虧比），賣出半數部位並上移防守至成本價（鎖定保本）。
            - **第二階段目標（波段收割）**：達 **`{res['target_60d']:.2f}` 元**（近 60 日波段壓力位）分批落袋。
            - **移動停利（Trailing Stop）**：其餘部位收盤跌破 5 日線全數獲利了結。
            """)

        elif st.session_state.sub_tab == "calc":
            st.subheader("🧮 部位規模與盈虧比試算 (雙重風控防護)")
            col_cap, col_risk = st.columns(2)
            with col_cap:
                total_capital = st.number_input("總操作資金 (NTD)", value=1000000, step=100000, key="calc_cap_input")
            with col_risk:
                risk_tolerance = st.slider("單筆最大承受損失比率", min_value=0.5, max_value=3.0, value=1.0, step=0.1, key="calc_risk_slider")

            max_risk_dollar = total_capital * (risk_tolerance / 100.0)

            if is_below_stop:
                st.error("⚠️ 警告：當前股價已在停損價位之下，無安全進場區間，建議買進張數：0 張！")
                suggested_lots = 0
                rr_ratio = 0.0
            else:
                loss_per_lot = risk_unit * 1000
                risk_based_lots = int(max_risk_dollar // loss_per_lot) if loss_per_lot > 0 else 0
                capital_max_lots = int(total_capital // (res['close'] * 1000)) if res['close'] > 0 else 0
                suggested_lots = min(risk_based_lots, capital_max_lots)

                potential_reward = max(res['target_60d'] - res['close'], 0)
                rr_ratio = potential_reward / risk_unit if risk_unit > 0 else 0

            b1, b2 = st.columns(2)
            b1.metric("單筆最大容許虧損", f"{int(max_risk_dollar):,} 元")
            b2.metric("建議最大進場張數", f"{suggested_lots} 張", help="同時受限於風險停損額與總現金購買力")

            b3, b4 = st.columns(2)
            b3.metric("目標獲利區 (近60日高)", f"{res['target_60d']:.2f} 元")
            b4.metric("預期盈虧比 (R/R)", f"{rr_ratio:.2f} : 1")

        elif st.session_state.sub_tab == "bt":
            st.subheader("📊 過去 1 年策略回測數據")
            bt = backtest_strategy(df_stock)
            if bt:
                bt1, bt2 = st.columns(2)
                bt1.metric("近 1 年訊號觸發次數", f"{bt['count']} 次")
                bt2.metric("持有 5 日勝率", f"{bt['win_rate']:.1f}%")
                bt3, bt4 = st.columns(2)
                bt3.metric("5 日平均報酬率", f"{bt['avg_return']:+.2f}%")
                bt4.metric("單次最大拉回風險", f"{bt['max_drawdown']:.2f}%")
            else:
                st.write("該標的歷史數據樣本不足以計算回測。")

        elif st.session_state.sub_tab == "forex":
            st.subheader("💱 外匯走勢與台股熱錢連動 (臺灣銀行官方連線)")
            fx = res['forex_info']
            fx1, fx2 = st.columns(2)
            fx1.metric("美元兌新台幣 (USD/TWD)", f"{fx['twd_rate']:.2f}", f"{fx['twd_change']:+.2f}")
            fx2.metric("美元指數 (DXY)", f"{fx['dxy_rate']:.2f}")

            st.caption(f"資料來源：**{fx['source']}**")
            st.write("---")
            st.markdown(f"**新台幣狀態：** {fx['twd_status']}")
            st.markdown(f"**中期趨勢判定：** {fx['twd_trend']}")
            st.markdown(f"**美元指數結構：** {fx['dxy_trend']}")
            st.markdown(f"**日圓套利平倉風險：** {fx['jpy_risk']}")

        elif st.session_state.sub_tab == "chart":
            st.subheader("📈 均線價格走勢圖")
            valid_cols = ['Close']
            for c in ['MA5', 'MA20', 'MA60']:
                if c in df_stock.columns and df_stock[c].notna().sum() > 5:
                    valid_cols.append(c)
            chart_data = df_stock[valid_cols].dropna().tail(60)
            st.line_chart(chart_data)

# ================= 模式 2：全市場優質體質雷達 =================
elif st.session_state.main_mode == "market":
    st.subheader("💎 市場穩健優質標的・即時連線掃描")
    st.caption("結合【基本面護城河】×【TWSE 官方即時量價多空動能】，全自動評分排序")

    if st.button("⚡ 開始全市場即時連線篩選", type="primary", use_container_width=True, key="market_scan_exec_btn"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        scan_results = []

        def worker(item):
            name, code, desc = item
            df_stk = fetch_and_calc(code)
            if df_stk is not None:
                r = analyze_full_stock(code, df_stk, df_market, df_futures, df_tsm, df_sox, global_forex)
                return {
                    "名稱": name,
                    "代碼": code,
                    "產業地位": desc,
                    "總評分": r['total_score'],
                    "現價": r['close'],
                    "建議防守": r['stop_loss'],
                    "ROE": r['fund_data']['roe'],
                    "本益比": r['fund_data']['pe']
                }
            return None

        with ThreadPoolExecutor(max_workers=5) as executor:
            total_items = len(MARKET_QUALITY_UNIVERSE)
            futures = [executor.submit(worker, item) for item in MARKET_QUALITY_UNIVERSE]
            for idx, f in enumerate(futures):
                status_text.text(f"官方主機連線更新中 ({idx+1}/{total_items})...")
                res_item = f.result()
                if res_item:
                    scan_results.append(res_item)
                progress_bar.progress((idx + 1) / total_items)

        status_text.empty()
        progress_bar.empty()

        df_res = pd.DataFrame(scan_results).sort_values(by="總評分", ascending=False).reset_index(drop=True)

        st.write("---")
        for rank, row in df_res.iterrows():
            badge = "🟢 強力優選" if row['總評分'] >= 75 else ("🟡 穩健觀察" if row['總評分'] >= 60 else "🔴 暫緩進場")
            with st.container():
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.markdown(f"**#{rank+1} {row['名稱']} ({row['代碼']})**")
                c2.markdown(f"總分: **{row['總評分']}** 分")
                c3.caption(badge)

                st.caption(f"📌 {row['產業地位']}")
                c_m1, c_m2, c_m3 = st.columns(3)
                c_m1.caption(f"現價: **{row['現價']:.2f}**")
                c_m2.caption(f"ROE: **{row['ROE']:.1f}%**")
                c_m3.caption(f"PE: **{row['本益比']:.1f}x**")
                st.caption(f"防守價位 (停損): **{row['建議防守']:.2f} 元**")
                st.write("---")

# ================= 模式 3：全球外匯與熱錢資金儀表板 =================
elif st.session_state.main_mode == "forex":
    st.subheader("💱 全球外匯與熱錢資金即時儀表板")
    st.caption("直連臺灣銀行官方牌告與全球匯率主機，精準掌握外資熱錢方向")

    fx_info = global_forex

    col_f1, col_f2, col_f3 = st.columns(3)
    col_f1.metric("美元兌新台幣 (USD/TWD)", f"{fx_info['twd_rate']:.2f}", f"{fx_info['twd_change']:+.2f}")
    col_f2.metric("美元指數 (DXY)", f"{fx_info['dxy_rate']:.2f}")
    col_f3.metric("美元兌日圓 (USD/JPY)", f"{fx_info['jpy_rate']:.2f}")

    st.caption(f"新台幣基準數據來源：**{fx_info['source']}**")
    st.write("---")
    st.markdown("### 📊 外匯核心訊號診斷")
    st.info(f"**新台幣狀態**：{fx_info['twd_status']}\n\n**波段趨勢**：{fx_info['twd_trend']}")
    st.markdown(f"• **美元指數結構**：{fx_info['dxy_trend']}")
    st.markdown(f"• **日圓套利平倉風險**：{fx_info['jpy_risk']}")

    st.write("---")
    st.markdown("### 📈 美元兌新台幣 (USD/TWD) 近期走勢與月線 (20MA)")
    df_usdtwd = fetch_and_calc("USDTWD=X")
    if df_usdtwd is None:
        df_usdtwd = fetch_and_calc("TWD=X")

    if df_usdtwd is not None:
        st.line_chart(df_usdtwd[['Close', 'MA20']].dropna().tail(60))
        st.caption("※ 匯率跌破月線代表台幣升值格局（熱錢湧入），站上月線代表貶值格局（資金趨向保守）。")
    else:
        st.write("暫時無法取得匯率走勢圖表。")

    st.write("---")
    st.markdown("### 🧭 實戰操作選股指南")
    st.markdown("""
    - **台幣強勢升值期**：
      - 🔥 **受惠族群**：大型權值股（台積電、聯發科）、金控金融、內需資產、航空航運。
      - 💡 **邏輯**：外資換匯買超台股，權值股推升指數最快。
    - **台幣弱勢貶值期**：
      - 🔥 **受惠族群**：中小型電子零組件、伺服器代工、工具機外銷。
      - 💡 **邏輯**：美元營收換回新台幣產生豐厚匯兌利益，毛利率提升。
    """)
