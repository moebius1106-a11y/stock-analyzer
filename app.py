import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

# 頁面配置 (行動端極致緊湊最適化)
st.set_page_config(
    page_title="次日開市與即時量化決策站",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 手機端直覺觸控 CSS：縮小不必要留白、緊湊一體化控制
st.markdown("""
<style>
    /* 頂部緊湊間距 */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }
    /* 按鈕大拇指舒適度、降低高度避免下推 */
    div.stButton > button {
        width: 100%;
        height: 2.8rem !important;
        font-size: 0.98rem !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
        margin-bottom: 0.2rem;
        padding: 0 0.5rem !important;
    }
    /* 輸入框高度優化 */
    div.stTextInput > div > div > input {
        height: 2.8rem !important;
        font-size: 1.05rem !important;
        border-radius: 10px !important;
    }
    /* 指標卡片緊湊化 */
    div[data-testid="stMetric"] {
        background-color: rgba(128, 128, 128, 0.08);
        border: 1px solid rgba(128, 128, 128, 0.18);
        padding: 0.5rem 0.7rem !important;
        border-radius: 12px;
        margin-bottom: 0.3rem;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.85rem !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.25rem !important;
    }
    /* 折疊卡片 (Expander) 質感加強 */
    .streamlit-expanderHeader {
        font-size: 1.02rem !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
        background-color: rgba(128, 128, 128, 0.05) !important;
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

        if ".TW" in ticker.upper() or ".TWO" in ticker.upper():
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

# ----------------- 基本面與 ETF 專屬數據 -----------------
@st.cache_data(ttl=7200)
def fetch_fundamentals(ticker: str):
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        clean_code = ticker.replace(".TW", "").replace(".TWO", "").strip()
        is_etf = info.get('quoteType') == 'ETF' or clean_code.startswith(('00', '01'))

        if is_etf:
            yield_raw = info.get('yield', info.get('dividendYield', None))
            yield_val = safe_float(yield_raw * 100 if yield_raw is not None else 5.2)
            beta_val = safe_float(info.get('beta', 0.85))
            nav_val = safe_float(info.get('navPrice', 0.0))

            fund_score = 0
            reasons = []

            if yield_val >= 7.0:
                fund_score += 25
                reasons.append(f"預估年化殖利率 {yield_val:.1f}%，高息防禦優勢顯著")
            elif yield_val >= 4.5:
                fund_score += 20
                reasons.append(f"預估年化殖利率 {yield_val:.1f}%，配息收益穩定")
            else:
                fund_score += 15
                reasons.append(f"年化殖利率 {yield_val:.1f}%，屬市值成長或科技型 ETF")

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
            "is_etf": False,
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

# ----------------- 外匯數據分析 -----------------
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
                res["twd_trend"] = "波段升值格局 (資金面有利台股權值與ETF)"
            else:
                res["twd_trend"] = "波段貶值格局 (權值股承壓，有利外銷出口)"

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
                res["jpy_risk"] = "⚠️ 警示：日圓近期急升，提防日圓套利平倉賣壓！"
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
    atr_val = safe_float(last_stk['ATR14'], default=close * 0.02)

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

    total_score = int((global_score + mkt_score + ma_score + tech_score) * 0.6 + fund_data['score'] * 0.8)
    total_score = min(max(total_score, 0), 100)

    ma20_val = safe_float(last_stk['MA20'], close * 0.96)
    stop_loss = max(close - 2 * atr_val, ma20_val)
    target_60d = safe_float(df_stock['High'].tail(60).max(), close * 1.08)

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

def calculate_adr_parity(tsm_usd, tw_twd, usdtwd_rate):
    if tsm_usd <= 0 or tw_twd <= 0 or usdtwd_rate <= 0:
        return 0.0, 0.0
    parity_twd = (tsm_usd * usdtwd_rate) / 5.0
    premium_pct = ((parity_twd - tw_twd) / tw_twd) * 100.0
    return parity_twd, premium_pct

@st.cache_data(ttl=600)
def fetch_stock_news(ticker: str):
    try:
        t = yf.Ticker(ticker)
        news_list = t.news
        if not news_list:
            return []
        formatted = []
        for n in news_list[:6]:
            pub_ts = n.get('providerPublishTime', None)
            pub_time = datetime.fromtimestamp(pub_ts, tz=TAIPEI_TZ).strftime("%m/%d %H:%M") if pub_ts else "即時"
            formatted.append({
                "title": n.get('title', '無標題'),
                "publisher": n.get('publisher', '財經即時訊'),
                "link": n.get('link', '#'),
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
    ("元大美債20年", "00679B.TWO", "債券避險", "長天期美國公債/降息受惠"),
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
    st.session_state.main_mode = "single"

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "2330.TW"

if "analysis_cache" not in st.session_state:
    st.session_state.analysis_cache = None

if "etf_category_filter" not in st.session_state:
    st.session_state.etf_category_filter = "全部"

# ----------------- 頂部導航與功能說明書 -----------------
st.title("📱 股期決策旗艦站")

# 📘 功能說明書：點擊即展開，讓使用者隨時查閱現行版本所有功能
with st.expander("📘 點此查看【系統現行版本完整功能清單與操作說明】", expanded=False):
    st.markdown("""
    本決策系統專為**機構級盤後開市決策**與**盤中即時應變**設計，目前完整具備以下六大核心模組：
    
    1. **🔍 個股全維度深度體檢**：
       - 直連 **臺灣證交所 (TWSE)** 撮合主機，提供 **0 延遲** 即時開盤跳空診斷與紅黑 K 棒判定。
       - **三均線矩陣**：日線 (5MA)、月線 (20MA)、季線 (60MA) 排列架構與乖離率計算。
       - **階梯停利 SOP**：初始停損、1.5R 保本減碼點、60 日壓力波段目標與移動停利機制。
       - **部位風控計算機**：同時考量「單筆最大容許虧損」與「總現金購買力上限」的雙重保護。
       - **歷史回測驗證**：客觀回溯過去 1 年策略真實勝率、期望報酬率與最大拉回幅度。
    
    2. **📊 ETF 策略專區**：
       - 分類涵蓋市值型、高股息、海外科技與長天期美債。
       - 專屬體質診斷（年化殖利率、Beta 波動係數、一籃子分散風險評級）。
       - 內建 **定期定額「微笑曲線」加碼計算機**，依季線乖離率提供增減扣款建議。
    
    3. **⚡ 期貨與美台跨市場連動**：
       - **台積電 ADR (TSM) 換算**：按 1:5 理論折合台幣價，精算即時溢價率（>10% 預警次日跳空開高）。
       - **台指期 (WTX) 基差分析**：期現貨正/逆價差診斷，洞悉市場大額資金多空傾向。
       - 追蹤全球美股微那斯達克 (NQ)、標普 (ES)、黃金 (GC)、輕原油 (CL) 5MA 短線動能。
    
    4. **💎 體質績優雷達**：
       - 雙重量化濾網：基本面護城河（ROE $\ge 15\%$、營業利益率、本益比、負債比）＋ TWSE 即時技術動能。
       - 採用平行多執行緒技術，秒級掃描全市場核心藍籌排行榜。
    
    5. **📢 重要法說會日程 ＆ 即時重大訊息速查**：
       - 直連權威財經新聞資料庫，一鍵檢索個股最新重大消息。
       - 整理指標龍頭（台積電、聯發科、鴻海等）季度法說會時程與必看核心看點。
    
    6. **💱 全球外匯與熱錢大盤**：
       - 直連 **臺灣銀行官方牌告匯率系統**，取得最權威新台幣即期匯價。
       - 追蹤美元指數 (DXY) 與日圓 (JPY) 套利平倉黑天鵝風險，提供外匯選股對應指引。
    """)

# 頂部六大模式切換（2x3 緊湊大拇指按鈕，高度控制在 2.8rem）
r1_c1, r1_c2, r1_c3 = st.columns(3)
with r1_c1:
    if st.button("🔍 個股診斷", type="primary" if st.session_state.main_mode == "single" else "secondary", use_container_width=True, key="m_nav_single"):
        st.session_state.main_mode = "single"
        st.rerun()
with r1_c2:
    if st.button("📊 ETF專區", type="primary" if st.session_state.main_mode == "etf" else "secondary", use_container_width=True, key="m_nav_etf"):
        st.session_state.main_mode = "etf"
        st.rerun()
with r1_c3:
    if st.button("⚡ 期貨連動", type="primary" if st.session_state.main_mode == "futures" else "secondary", use_container_width=True, key="m_nav_futures"):
        st.session_state.main_mode = "futures"
        st.rerun()

r2_c1, r2_c2, r2_c3 = st.columns(3)
with r2_c1:
    if st.button("💎 體質雷達", type="primary" if st.session_state.main_mode == "market" else "secondary", use_container_width=True, key="m_nav_market"):
        st.session_state.main_mode = "market"
        st.rerun()
with r2_c2:
    if st.button("📢 法說消息", type="primary" if st.session_state.main_mode == "events" else "secondary", use_container_width=True, key="m_nav_events"):
        st.session_state.main_mode = "events"
        st.rerun()
with r2_c3:
    if st.button("💱 外匯大盤", type="primary" if st.session_state.main_mode == "forex" else "secondary", use_container_width=True, key="m_nav_forex"):
        st.session_state.main_mode = "forex"
        st.rerun()

st.write("")

# 全域預載
df_market = fetch_and_calc("^TWII")
df_futures = fetch_and_calc("WTX=F")
if df_futures is None:
    df_futures = df_market
df_tsm = fetch_and_calc("TSM")
df_sox = fetch_and_calc("^SOX")
global_forex = analyze_forex_data()

# ================= 模式 1：個股全維度深度體檢 (極致緊湊零滑動優化) =================
if st.session_state.main_mode == "single":
    # 快捷熱門股（單排 4 欄，不佔直向空間）
    h_c1, h_c2, h_c3, h_c4 = st.columns(4)
    if h_c1.button("台積電", use_container_width=True, key="qp_2330"):
        st.session_state.selected_ticker = "2330.TW"
        st.session_state.analysis_cache = None
        st.rerun()
    if h_c2.button("聯發科", use_container_width=True, key="qp_2454"):
        st.session_state.selected_ticker = "2454.TW"
        st.session_state.analysis_cache = None
        st.rerun()
    if h_c3.button("鴻海", use_container_width=True, key="qp_2317"):
        st.session_state.selected_ticker = "2317.TW"
        st.session_state.analysis_cache = None
        st.rerun()
    if h_c4.button("0050", use_container_width=True, key="qp_0050"):
        st.session_state.selected_ticker = "0050.TW"
        st.session_state.analysis_cache = None
        st.rerun()

    # 一體化搜尋與診斷列（橫向併排，點完視線完全不移動）
    col_input, col_btn = st.columns([2.6, 1.4])
    with col_input:
        ticker_input = st.text_input("輸入查詢代碼", value=st.session_state.selected_ticker, label_visibility="collapsed", key="ticker_input_field")
    with col_btn:
        exec_clicked = st.button("🚀 執行診斷", type="primary", use_container_width=True, key="run_single_analysis_btn")

    if exec_clicked:
        with st.spinner("連線 TWSE 撮合與官方主機計算中..."):
            df_stock = fetch_and_calc(ticker_input.strip())
            if df_stock is not None:
                res = analyze_full_stock(ticker_input.strip(), df_stock, df_market, df_futures, df_tsm, df_sox, global_forex)
                st.session_state.analysis_cache = (res, df_stock)
            else:
                st.session_state.analysis_cache = None
                st.error("無法取得該標的行情數據，請確認代碼是否正確。")

    # 診斷結果直接在當前螢幕就地展示
    if st.session_state.analysis_cache is not None:
        res, df_stock = st.session_state.analysis_cache
        is_below_stop = res['close'] <= res['stop_loss']
        risk_unit = max(res['close'] - res['stop_loss'], 0.0)
        target_1 = res['close'] + (1.5 * max(risk_unit, res['close'] * 0.03))
        is_etf_asset = res['fund_data'].get('is_etf', False)

        if res.get("live_info"):
            asset_type_badge = "📊 ETF" if is_etf_asset else "🏢 個股"
            st.caption(f"⚡ **TWSE 撮合** ｜ {asset_type_badge} ｜ {res['live_info']['time']}")

        # 頂部四大核心數值卡片（首屏即視）
        c1, c2 = st.columns(2)
        c1.metric("綜合決策總分", f"{res['total_score']} / 100")
        c2.metric("最新成交價", f"{res['close']:.2f} 元")

        c3, c4 = st.columns(2)
        c3.metric("建議防守價 (停損)", f"{res['stop_loss']:.2f} 元")
        risk_pct = (risk_unit / res['close']) * 100 if not is_below_stop else 0.0
        c4.metric("最大預期風險", f"{risk_pct:.2f}%" if not is_below_stop else "已在防守線下")

        # 模組 1：綜合決策結論（首頁直接展開，完全不需滑動）
        with st.expander("🎯 【決策結論與操作指引】", expanded=True):
            if is_below_stop:
                st.error("### 🔴 現價已跌破建議防守線：嚴禁追價！")
                st.write(f"- 當前價位（{res['close']:.2f} 元）低於防守點（{res['stop_loss']:.2f} 元）。")
            elif res['total_score'] >= 75:
                st.success("### 🟢 積極偏多：體質與量價動能同步翻多，適合進場")
                st.write(f"- 建議防守價位：**{res['stop_loss']:.2f} 元**。")
            elif 60 <= res['total_score'] < 75:
                st.warning("### 🟡 穩健觀察：指標整理或分歧，僅限 1/3 以下微型試單")
            else:
                st.error("### 🔴 暫緩進場：評價過高或短期均線下壓，現金為王")

        # 模組 2：開盤即時撮合診斷（就地展開）
        with st.expander("⚡ 【開盤即時撮合動態 (TWSE 官方)】", expanded=False):
            st.markdown(f"**當前 K 棒型態：** `{res['k_type']}`")
            k1, k2 = st.columns(2)
            k1.metric("開盤跳空幅度", f"{res['gap_pct']:+.2f}%")
            k2.metric("開盤至今漲跌", f"{res['intraday_pct']:+.2f}%")
            st.write("---")
            for d in res['opening_diag']:
                st.write(f"• {d}")

        # 模組 3：三均線矩陣（就地展開）
        with st.expander("📏 【日 / 月 / 季線 位階矩陣】", expanded=False):
            st.markdown(f"**均線排列結構：** `{res['ma_alignment']}`")
            m1, m2, m3 = st.columns(3)
            m1.metric("日線 (5MA)", f"{res['ma_status']['ma5_val']:.2f}", f"{res['ma_status']['ma5_diff']:+.1f}%")
            m2.metric("月線 (20MA)", f"{res['ma_status']['ma20_val']:.2f}", f"{res['ma_status']['ma20_diff']:+.1f}%")
            m3.metric("季線 (60MA)", f"{res['ma_status']['ma60_val']:.2f}", f"{res['ma_status']['ma60_diff']:+.1f}%")

        # 模組 4：體質護城河（就地展開）
        fund_title = "💎 【ETF 專屬體質與配息分析】" if is_etf_asset else "💎 【企業基本面體質護城河】"
        with st.expander(fund_title, expanded=False):
            f_data = res['fund_data']
            if is_etf_asset:
                f1, f2 = st.columns(2)
                f1.metric("預估年化殖利率", f"{f_data['yield']:.1f}%")
                f2.metric("Beta 波動係數", f"{f_data['beta']:.2f}")
            else:
                f1, f2 = st.columns(2)
                f1.metric("ROE 股東權益報酬率", f"{f_data['roe']:.1f}%")
                f2.metric("營業利益率", f"{f_data['op_margin']:.1f}%")
                f3, f4 = st.columns(2)
                f3.metric("本益比 (PE)", f"{f_data['pe']:.1f}x")
                f4.metric("負債比率 (D/E)", f"{f_data['debt_ratio']:.1f}%")
            st.write("---")
            for r in f_data['reasons']:
                st.write(f"• {r}")

        # 模組 5：階梯停利 SOP（就地展開）
        with st.expander("🚪 【階梯式分階出場 SOP】", expanded=False):
            st.markdown(f"""
            - **初始防守停損**：跌破 **`{res['stop_loss']:.2f}` 元** 嚴格離場，絕不凹單。
            - **第一階段目標（減碼 1/2）**：達 **`{target_1:.2f}` 元**（1.5R 盈虧比），賣出半數部位並上移防守至成本價（鎖定保本）。
            - **第二階段目標（波段收割）**：達 **`{res['target_60d']:.2f}` 元**（近 60 日波段壓力位）分批落袋。
            - **移動停利（Trailing Stop）**：其餘部位收盤跌破 5 日線全數獲利了結。
            """)

        # 模組 6：風控計算機（就地展開）
        with st.expander("💰 【部位風控與建議張數計算機】", expanded=False):
            col_cap, col_risk = st.columns(2)
            with col_cap:
                total_capital = st.number_input("總操作資金 (NTD)", value=1000000, step=100000, key="calc_cap_input")
            with col_risk:
                risk_tolerance = st.slider("單筆最大承受損失比率", min_value=0.5, max_value=3.0, value=1.0, step=0.1, key="calc_risk_slider")

            max_risk_dollar = total_capital * (risk_tolerance / 100.0)
            if is_below_stop:
                st.error("⚠️ 警告：當前價格已在停損價位之下，建議買進張數：0 張！")
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

        # 模組 7：歷史勝率回測（就地展開）
        with st.expander("📊 【過去 1 年策略回測數據】", expanded=False):
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

        # 模組 8：走勢圖表（就地展開）
        with st.expander("📈 【均線價格走勢圖】", expanded=False):
            valid_cols = ['Close']
            for c in ['MA5', 'MA20', 'MA60']:
                if c in df_stock.columns and df_stock[c].notna().sum() > 5:
                    valid_cols.append(c)
            chart_data = df_stock[valid_cols].dropna().tail(60)
            st.line_chart(chart_data)

# ================= 模式 2：📊 ETF 專區 =================
elif st.session_state.main_mode == "etf":
    st.subheader("📊 ETF 旗艦量化策略雷達")
    st.caption("熱門 ETF 全方位即時體檢・配息防禦 × 均線動能 × 定期定額試算")

    # 分類篩選（單排 4 欄）
    f1, f2, f3, f4 = st.columns(4)
    if f1.button("全部", type="primary" if st.session_state.etf_category_filter == "全部" else "secondary", use_container_width=True, key="filter_etf_all"):
        st.session_state.etf_category_filter = "全部"
        st.rerun()
    if f2.button("市值型", type="primary" if st.session_state.etf_category_filter == "市值型" else "secondary", use_container_width=True, key="filter_etf_cap"):
        st.session_state.etf_category_filter = "市值型"
        st.rerun()
    if f3.button("高股息", type="primary" if st.session_state.etf_category_filter == "高股息" else "secondary", use_container_width=True, key="filter_etf_div"):
        st.session_state.etf_category_filter = "高股息"
        st.rerun()
    if f4.button("海外/債", type="primary" if st.session_state.etf_category_filter == "海外/債券" else "secondary", use_container_width=True, key="filter_etf_overseas"):
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

        def etf_worker(item):
            name, code, cat, desc = item
            df_stk = fetch_and_calc(code)
            if df_stk is not None:
                r = analyze_full_stock(code, df_stk, df_market, df_futures, df_tsm, df_sox, global_forex)
                return {
                    "名稱": name,
                    "代碼": code,
                    "類別": cat,
                    "特色": desc,
                    "總評分": r['total_score'],
                    "現價": r['close'],
                    "建議防守": r['stop_loss'],
                    "殖利率": r['fund_data'].get('yield', 5.0),
                    "ma20_diff": r['ma_status']['ma20_diff'],
                    "ma60_diff": r['ma_status']['ma60_diff']
                }
            return None

        with ThreadPoolExecutor(max_workers=5) as executor:
            total_items = len(target_etfs)
            futures = [executor.submit(etf_worker, item) for item in target_etfs]
            for idx, f in enumerate(futures):
                status_text.text(f"連線撮合中 ({idx+1}/{total_items})...")
                res_item = f.result()
                if res_item:
                    etf_results.append(res_item)
                progress_bar.progress((idx + 1) / total_items)

        status_text.empty()
        progress_bar.empty()

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
                c_m2.caption(f"殖利率: **{row['殖利率']:.1f}%**")
                c_m3.caption(f"防守: **{row['建議防守']:.2f}**")
                st.write("---")

    with st.expander("🧮 定期定額「微笑曲線」扣款計算機", expanded=False):
        etf_cap = st.number_input("每月預算 (NTD)", value=20000, step=5000, key="etf_monthly_budget")
        etf_state = st.radio("當前位階：", ["常態整理（月線與季線之間）", "大幅拉回（低於季線 5% 以上）", "高檔大漲（高於月線 6% 以上）"], key="etf_state_radio")
        if "大幅拉回" in etf_state:
            st.success(f"🎯 建議扣款 **{int(etf_cap * 1.5):,} 元**（1.5 倍加碼）")
        elif "高檔大漲" in etf_state:
            st.warning(f"🎯 建議扣款 **{int(etf_cap * 0.7):,} 元**（0.7 倍扣款保留現金）")
        else:
            st.info(f"🎯 維持標準扣款 **{int(etf_cap):,} 元**")

# ================= 模式 3：⚡ 期貨與美台跨市場連動 =================
elif st.session_state.main_mode == "futures":
    st.subheader("⚡ 期貨與美台跨市場連動核心")

    # 1. 台積電 ADR 換算卡片
    st.markdown("### 🏆 台積電 ADR (TSM) 即時換算")
    df_tsm_now = fetch_and_calc("TSM")
    df_2330_now = fetch_and_calc("2330.TW")

    if df_tsm_now is not None and df_2330_now is not None:
        tsm_p = df_tsm_now.iloc[-1]['Close']
        tw_p = df_2330_now.iloc[-1]['Close']
        usdtwd_curr = global_forex['twd_rate']
        parity_twd, premium_pct = calculate_adr_parity(tsm_p, tw_p, usdtwd_curr)

        c_a1, c_a2 = st.columns(2)
        c_a1.metric("TSM ADR 最新價", f"{tsm_p:.2f} USD")
        c_a2.metric("台積電現股", f"{tw_p:.2f} 元")

        c_a3, c_a4 = st.columns(2)
        c_a3.metric("ADR 理論折合價", f"{parity_twd:.2f} 元")
        c_a4.metric("即時溢價率", f"{premium_pct:+.2f}%", f"{premium_pct:+.2f}%")

        if premium_pct >= 10.0:
            st.success(f"🔥 **ADR 大幅溢價 (+{premium_pct:.1f}%)**：次日台股高機率具備強勁推升動能！")
        elif premium_pct <= -2.0:
            st.warning(f"⚠️ **ADR 出現折價 ({premium_pct:.1f}%)**：提防現貨與 ADR 跨市場套利賣壓！")
        else:
            st.info(f"⚖️ **合理溢價區間 ({premium_pct:+.1f}%)**")
    st.write("---")

    # 2. 台指期貨基差診斷
    st.markdown("### 📊 台指期 (WTX) 與現貨基差 (Basis)")
    if df_market is not None and df_futures is not None:
        twii_close = df_market.iloc[-1]['Close']
        fut_close = df_futures.iloc[-1]['Close']
        basis = fut_close - twii_close

        fb1, fb2, fb3 = st.columns(3)
        fb1.metric("現貨指數", f"{twii_close:.1f}")
        fb2.metric("台指期貨", f"{fut_close:.1f}")
        fb3.metric("價差", f"{basis:+.1f} 點")

        if basis > 30:
            st.success("🟢 **實質正價差格局**：主力大額資金態度偏多樂觀！")
        elif basis < -60:
            st.warning("⚠️ **大幅逆價差格局**：避險情緒升溫，短線提防拉回洗盤！")
        else:
            st.info("⚪ **正常平價價差**")
    st.write("---")

    # 3. 國際主要期貨動能
    st.markdown("### 🌐 全球美股期貨與關鍵大宗商品")
    GLOBAL_FUT_LIST = [
        ("微那斯達克期 (NQ)", "NQ=F", "美股科技領先指標"),
        ("小標普期 (ES)", "ES=F", "美股大盤流動性"),
        ("紐約黃金期 (GC)", "GC=F", "地緣政治避險指標"),
        ("輕原油期 (CL)", "CL=F", "通膨與能源供應")
    ]
    for name, code, desc in GLOBAL_FUT_LIST:
        df_g = fetch_and_calc(code)
        if df_g is not None and len(df_g) >= 2:
            last_p = df_g.iloc[-1]['Close']
            prev_p = df_g.iloc[-2]['Close']
            chg_pct = ((last_p - prev_p) / prev_p) * 100
            ma5_g = df_g['MA5'].iloc[-1]
            status = "🔥 站上 5MA" if last_p > ma5_g else "❄️ 破 5MA"
            gc1, gc2 = st.columns([2, 1])
            gc1.markdown(f"**{name}** ｜ {desc}")
            gc2.metric("點位", f"{last_p:.2f}", f"{chg_pct:+.2f}%")
            st.caption(f"結構：`{status}`")
            st.write("---")

# ================= 模式 4：💎 體質績優雷達 =================
elif st.session_state.main_mode == "market":
    st.subheader("💎 市場穩健優質標的・即時連線掃描")

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
                    "ROE": r['fund_data'].get('roe', 12.0),
                    "本益比": r['fund_data'].get('pe', 18.0)
                }
            return None

        with ThreadPoolExecutor(max_workers=5) as executor:
            total_items = len(MARKET_QUALITY_UNIVERSE)
            futures = [executor.submit(worker, item) for item in MARKET_QUALITY_UNIVERSE]
            for idx, f in enumerate(futures):
                status_text.text(f"連線更新中 ({idx+1}/{total_items})...")
                res_item = f.result()
                if res_item:
                    scan_results.append(res_item)
                progress_bar.progress((idx + 1) / total_items)

        status_text.empty()
        progress_bar.empty()

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
                c_m1.caption(f"ROE: **{row['ROE']:.1f}%**")
                c_m3.caption(f"PE: **{row['本益比']:.1f}x**")
                st.caption(f"防守 (停損): **{row['建議防守']:.2f} 元**")
                st.write("---")

# ================= 模式 5：📢 法說會日程與重大訊息 =================
elif st.session_state.main_mode == "events":
    st.subheader("📢 重要法說會日程 ＆ 即時重大訊息速查")

    col_n_input, col_n_btn = st.columns([2.6, 1.4])
    with col_n_input:
        news_ticker = st.text_input("輸入查詢標的代碼", value="2330.TW", label_visibility="collapsed", key="news_search_input")
    with col_n_btn:
        news_clicked = st.button("📰 查重大訊息", type="primary", use_container_width=True, key="fetch_news_btn")

    if news_clicked:
        with st.spinner("連線即時新聞庫檢索中..."):
            news_items = fetch_stock_news(news_ticker.strip())
            if news_items:
                st.success(f"{news_ticker} 最新重大訊息：")
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

# ================= 模式 6：💱 全球外匯大盤 =================
elif st.session_state.main_mode == "forex":
    st.subheader("💱 全球外匯與熱錢資金即時儀表板")
    st.caption("直連臺灣銀行官方牌告與全球匯率主機")

    fx_info = global_forex

    col_f1, col_f2, col_f3 = st.columns(3)
    col_f1.metric("USD/TWD", f"{fx_info['twd_rate']:.2f}", f"{fx_info['twd_change']:+.2f}")
    col_f2.metric("美元 (DXY)", f"{fx_info['dxy_rate']:.2f}")
    col_f3.metric("日圓 (JPY)", f"{fx_info['jpy_rate']:.2f}")

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
