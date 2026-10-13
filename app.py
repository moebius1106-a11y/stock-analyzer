import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import math
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

# 頁面配置
st.set_page_config(
    page_title="次日開市與即時量化決策站",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 手機端直覺觸控 CSS
st.markdown("""
<style>
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }
    div.stButton > button {
        width: 100%;
        height: 2.8rem !important;
        font-size: 0.98rem !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
        margin-bottom: 0.2rem;
        padding: 0 0.5rem !important;
    }
    div.stTextInput > div > div > input {
        height: 2.8rem !important;
        font-size: 1.05rem !important;
        border-radius: 10px !important;
    }
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
    .streamlit-expanderHeader {
        font-size: 1.02rem !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
        background-color: rgba(128, 128, 128, 0.05) !important;
    }
</style>
""", unsafe_allow_html=True)

TAIPEI_TZ = timezone(timedelta(hours=8))

# ----------------- 通行密碼防護 (P0-1: 徹底移除預設密碼) -----------------
try:
    ACCESS_PASSWORD = st.secrets["PASSWORD"]
except Exception:
    ACCESS_PASSWORD = None

if ACCESS_PASSWORD is None:
    st.error("🚨 **系統安全性錯誤：未檢測到 Streamlit Secrets [PASSWORD] 設定！**")
    st.markdown("""
    依據量化風控與系統安全原則，**本系統已嚴格拒絕使用公開預設密碼啟動**。
    
    **【解決步驟】**：
    1. 前往 Streamlit Cloud 管理後台（App Settings > Secrets）。
    2. 新增設定內容：
    ```toml
    PASSWORD = "您的專屬複雜密碼"
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

# ----------------- 數值安全轉換工具 (P1-4: 重構 Series 取值與容器判斷) -----------------
def safe_float(val, default=0.0):
    try:
        if val is None:
            return default
        # Series 嚴格以 iloc[0] 提取位置，防止標籤索引例外
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
            val = val.strip()
            if val in ("", "-", "N/A", "nan", "None", "_", "--"):
                return default
        result = float(val)
        if not math.isfinite(result):
            return default
        return result
    except (ValueError, TypeError, IndexError, OverflowError):
        return default

# ----------------- 股票代碼正規化 -----------------
def normalize_ticker(ticker: str):
    t = ticker.strip().upper()
    if t.endswith(".TWO"):
        return t[:-4], "otc"
    if t.endswith(".TW"):
        return t[:-3], "tse"
    return t, "tse"

# ----------------- 權威 API 1：臺灣證券交易所官方即時行情 (含時間戳與狀態) -----------------
def fetch_twse_realtime(ticker: str):
    code, market = normalize_ticker(ticker)
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
                    z_price = y_close
                    is_trading = False

                raw_lots = safe_float(item.get("v"), default=0.0)
                converted_shares = raw_lots * 1000.0
                date_str = item.get("d", "")
                time_str = item.get("t", "")

                # P1-5: 驗證撮合時間新鮮度 (09:00:00 ~ 13:30:00 判定為盤中交易)
                now_taipei = datetime.now(TAIPEI_TZ)
                today_str = now_taipei.strftime("%Y%m%d")
                status_label = "⚪ 盤後收盤資料"

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
                    "name": item.get("n", code),
                    "match_price": z_price,
                    "open": safe_float(item.get("o"), default=z_price),
                    "high": safe_float(item.get("h"), default=z_price),
                    "low": safe_float(item.get("l"), default=z_price),
                    "volume": converted_shares,
                    "yesterday_close": y_close,
                    "date_str": date_str,
                    "time": time_str,
                    "status_label": status_label,
                    "is_live": True,
                    "is_trading": is_trading
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

# ----------------- 基本面與 ETF 數據 (P0-3: 嚴禁假分數，實事求是) -----------------
@st.cache_data(ttl=7200)
def fetch_fundamentals(ticker: str):
    clean_code, _ = normalize_ticker(ticker)
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

            # P0-3: 若殖利率與 Beta 全數缺失，不可偽造假分數
            if yield_val is None and beta_val is None:
                return {
                    "has_data": False,
                    "is_etf": True,
                    "score": None,
                    "yield": None,
                    "beta": None,
                    "nav": nav_val,
                    "category": info.get('category', '指數股票型基金 (ETF)'),
                    "reasons": ["⚠️ 查無足夠之配息率與 Beta 數據，未計入基本面評分（比重已動態切換至技術面）"]
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
                    "reasons": ["⚠️ 查無足夠之財報數據，未計入基本面評分（比重已動態切換至技術面）"]
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
                if 8 <= pe_val <= 25:
                    fund_score += 10
                    reasons.append(f"本益比 {pe_val:.1f}x，估值處安全區間")
                elif pe_val < 8:
                    fund_score += 7
                    reasons.append(f"本益比低估 ({pe_val:.1f}x)")
                else:
                    fund_score += 4
                    reasons.append(f"本益比偏高 ({pe_val:.1f}x)")

            if de_val is not None:
                if de_val <= 80:
                    fund_score += 10
                    reasons.append(f"負債比率健康 ({de_val:.1f}%)，財務抗風險力強")
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

# ----------------- 歷史回測引擎 (P0-2: 單部位無重疊・摩擦成本・淨值 MDD) -----------------
def backtest_strategy(df_stock):
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
    COST_RATE = 0.0045  # 來回手續費與證交稅約 0.45%

    # P0-2: 單部位循序推進模型（持倉中嚴格跳過新訊號，杜絕虛擬重疊複利）
    while i < n_bars - 6:
        if signals.iloc[i]:
            # 訊號於 i 日收盤確認，次日 i+1 日以 Open 進場（杜絕前視偏誤）
            entry_p = safe_float(df_stock['Open'].iloc[i + 1])
            if entry_p <= 0:
                entry_p = safe_float(df_stock['Close'].iloc[i + 1])
            # 持有 5 個交易日，於 i+6 日以 Open 出場
            exit_p = safe_float(df_stock['Open'].iloc[i + 6])
            if exit_p <= 0:
                exit_p = safe_float(df_stock['Close'].iloc[i + 6])

            if entry_p > 0 and exit_p > 0:
                net_ret = ((exit_p - entry_p) / entry_p - COST_RATE) * 100.0
                trade_returns.append(net_ret)
                i += 6  # 結清部位後才尋找下一次進場點
                continue
        i += 1

    if not trade_returns:
        return None

    wins = [r for r in trade_returns if r > 0]
    win_rate = (len(wins) / len(trade_returns)) * 100.0
    avg_return = float(np.mean(trade_returns))
    worst_single_loss = float(min(trade_returns))

    # 計算累積資產淨值曲線 (Equity Curve) 與真實最大回撤 (MDD)
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
def analyze_full_stock(ticker, df_stock, df_market, df_futures, df_tsm, df_sox, forex_info):
    fund_data = fetch_fundamentals(ticker)
    analyst_data = fetch_analyst_consensus(ticker)
    live_twse = fetch_twse_realtime(ticker)
    ma_status, ma_alignment, ma_score, gap_pct, intraday_pct, k_type, opening_diag = analyze_opening_and_ma(df_stock, live_twse)

    last_stk = df_stock.iloc[-1]
    prev_stk = df_stock.iloc[-2] if len(df_stock) >= 2 else last_stk
    close = safe_float(last_stk['Close'])
    atr_val = safe_float(last_stk['ATR14'], default=close * 0.02)

    global_score = 0
    global_reasons = []
    try:
        if df_tsm is not None and len(df_tsm) >= 2:
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
        else:
            global_score += 8
            global_reasons.append("國際美股數據採中立基準分")

        if forex_info.get("has_real_twd"):
            if "升值" in forex_info['twd_status']:
                global_reasons.append(f"新台幣走升 ({forex_info['twd_rate']:.2f})，熱錢匯入台股")
            else:
                global_reasons.append(f"新台幣匯率整理 ({forex_info['twd_rate']:.2f})")
    except Exception:
        global_score = 8
        global_reasons.append("國際數據採基準分")

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

    analyst_bonus = 0
    if analyst_data["has_data"]:
        if "強力買進" in analyst_data["rec_label"]:
            analyst_bonus = 5
        elif "買進" in analyst_data["rec_label"]:
            analyst_bonus = 3
        elif "減碼" in analyst_data["rec_label"] or "賣出" in analyst_data["rec_label"]:
            analyst_bonus = -5

    tech_subtotal = global_score + mkt_score + ma_score + tech_score
    if fund_data["has_data"] and fund_data["score"] is not None:
        tech_part = tech_subtotal * (60.0 / 85.0)
        fund_part = fund_data['score'] * 0.70
        total_score = int(tech_part + fund_part + analyst_bonus)
    else:
        tech_part = tech_subtotal * (95.0 / 85.0)
        total_score = int(tech_part + analyst_bonus)

    total_score = min(max(total_score, 0), 100)

    ma20_val = safe_float(last_stk['MA20'], close * 0.96)
    if (close - ma20_val) < (0.5 * atr_val):
        stop_loss = max(close - 2.0 * atr_val, ma20_val - 0.5 * atr_val)
    else:
        stop_loss = max(close - 2.0 * atr_val, ma20_val)

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
        "live_info": live_twse
    }

def calculate_adr_parity(tsm_usd, tw_twd, usdtwd_rate):
    if tsm_usd <= 0 or tw_twd <= 0 or usdtwd_rate is None or usdtwd_rate <= 0:
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
            pub_ts = safe_float(n.get('providerPublishTime'))
            pub_time = datetime.fromtimestamp(pub_ts, tz=TAIPEI_TZ).strftime("%m/%d %H:%M") if pub_ts > 0 else "即時"
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
st.title("📱 股期決策旗艦站 (機構版)")

with st.expander("📘 點此查看【系統現行版本完整功能清單與架構指南】", expanded=False):
    st.markdown("""
    本系統採用多資料源交叉校驗與統計風控模型：
    
    1. **🎯 權威分析師共識 ＆ 精確下單指引**：
       - 直連全球與本土主流券商研究報告資料庫。
       - 揭露**機構共識平均目標價**、**潛在報酬空間 (%)**、**法人分歧區間**與**精確下單執行卡**。
    
    2. **🔍 個股全維度深度體檢**：
       - 整合 **臺灣證交所 (TWSE)** 撮合主機，嚴格單位對齊（張換算股），杜絕量能失真。
       - 撮合新鮮度標記（區分盤中即時 vs 盤後收盤資料）。
       - 三均線位階矩陣 (5MA / 20MA / 60MA)、階梯停利 SOP、購買力風控計算機。
       - **無前視偏誤歷史回測**：次日開盤進場、扣除 0.45% 實務交易成本，以權益曲線精算真實最大回撤 (MDD)。
    
    3. **📊 ETF 策略專區**：
       - 涵蓋市值型、高股息、海外科技與長天期美債。
       - 支援 `.TWO` 櫃買代碼精確解析，數據缺失時絕不灌入假分數。
    
    4. **⚡ 期貨與美台跨市場連動**：
       - **台積電 ADR (TSM) 1:5 理論換算** 與即時溢價率診斷。
       - **台指期 (WTX) 跨市場日期校驗**：期現貨不同步時明確警示，絕不拿現貨冒充。
    
    5. **💎 體質績優雷達 ＆ 📢 法說會新聞速查**：
       - 雙重實質濾網；財報缺失時不灌假資料，自動動態重新分配技術權重。
    
    6. **💱 全球外匯與熱錢大盤**：
       - 直連臺灣銀行官方牌告匯率系統，即時追蹤 USD/TWD、美元指數 (DXY) 與日圓套利平倉風險。
    """)

# 頂部六大模式切換
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
df_tsm = fetch_and_calc("TSM")
df_sox = fetch_and_calc("^SOX")
global_forex = analyze_forex_data()

# ================= 模式 1：個股全維度深度體檢 =================
if st.session_state.main_mode == "single":
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

    col_input, col_btn = st.columns([2.6, 1.4])
    with col_input:
        ticker_input = st.text_input("輸入查詢代碼", value=st.session_state.selected_ticker, label_visibility="collapsed", key="ticker_input_field")
    with col_btn:
        exec_clicked = st.button("🚀 執行診斷", type="primary", use_container_width=True, key="run_single_analysis_btn")

    if exec_clicked:
        with st.spinner("連線 TWSE 撮合與權威機構資料庫中..."):
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
        is_etf_asset = res['fund_data'].get('is_etf', False)
        an_data = res['analyst_data']

        # P1-5: 清楚揭示數據源、時間戳與撮合狀態
        if res.get("live_info"):
            asset_type_badge = "📊 ETF" if is_etf_asset else "🏢 個股"
            status_badge = res['live_info'].get('status_label', '⚪ 歷史報價')
            st.caption(f"⚡ **TWSE 撮合系統** ｜ {status_badge} ｜ {asset_type_badge} ｜ 時間：{res['live_info']['time']}")

        c1, c2 = st.columns(2)
        c1.metric("綜合決策總分", f"{res['total_score']} / 100")
        c2.metric("最新成交價", f"{res['close']:.2f} 元")

        c3, c4 = st.columns(2)
        c3.metric("建議防守價 (停損)", f"{res['stop_loss']:.2f} 元")
        risk_pct = (risk_unit / res['close']) * 100 if not is_below_stop else 0.0
        c4.metric("最大預期風險", f"{risk_pct:.2f}%" if not is_below_stop else "已在防守線下")

        # 模組 1：權威機構分析師共識 ＆ 精確下單指引
        with st.expander("🎯 【權威分析師共識 ＆ 精確下單指引】", expanded=True):
            if an_data["has_data"]:
                st.markdown(f"**機構綜合投資評等：** `{an_data['rec_label']}`")
                st.caption(f"📌 {an_data['rec_desc']}（共計 **{an_data['opinions']} 家** 券商機構追蹤）")

                upside_pct = ((an_data['target_mean'] - res['close']) / res['close']) * 100 if res['close'] > 0 else 0
                a_c1, a_c2 = st.columns(2)
                a_c1.metric("機構共識平均目標價", f"{an_data['target_mean']:.2f} 元" if an_data['target_mean'] > 0 else "未揭露", f"{upside_pct:+.1f}% 潛在空間" if an_data['target_mean'] > 0 else "")
                a_c2.metric("法人覆蓋機構數", f"{an_data['opinions']} 家")

                if an_data['target_high'] > 0:
                    st.caption(f"📊 法人區間分歧度：最低 **{an_data['target_low']:.2f} 元** ～ 最高 **{an_data['target_high']:.2f} 元**")
            else:
                st.info("💡 該標的暫無多數券商連續追蹤報告，目標價已依波段動態空間推算。")

            st.write("---")
            st.markdown("### 📋 【精確下單執行卡】")
            if is_below_stop:
                st.error("🚫 **當前禁止下單**：現價已跌破建議防守線，空方控盤，嚴禁逆勢摸底！")
            else:
                st.markdown(f"""
                1. **建議進場區間**：**`{res['close']:.2f} 元`**（早盤回測 5MA 不破可分批布局）。
                2. **波段防守點位**：**`{res['stop_loss']:.2f} 元`**（收盤破線立即退場，絕不凹單）。
                3. **第一獲利目標**：**`{target_1:.2f} 元`**（達成 1.5R 盈虧比，強制賣出 1/2 入袋並上移防守至成本）。
                4. **波段獲利目標**：**`{res['target_60d']:.2f} 元`**（對齊機構共識目標價或波段高點擴展區）。
                """)

        # 模組 2：決策結論與多空架構
        with st.expander("📝 【決策結論與多空架構】", expanded=False):
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

        # 模組 3：開盤即時撮合動態
        with st.expander("⚡ 【開盤即時撮合動態 (TWSE 官方)】", expanded=False):
            st.markdown(f"**當前 K 棒型態：** `{res['k_type']}`")
            k1, k2 = st.columns(2)
            k1.metric("開盤跳空幅度", f"{res['gap_pct']:+.2f}%")
            k2.metric("開盤至今漲跌", f"{res['intraday_pct']:+.2f}%")
            st.write("---")
            for d in res['opening_diag']:
                st.write(f"• {d}")

        # 模組 4：三均線矩陣
        with st.expander("📏 【日 / 月 / 季線 位階矩陣】", expanded=False):
            st.markdown(f"**均線排列結構：** `{res['ma_alignment']}`")
            m1, m2, m3 = st.columns(3)
            m1.metric("日線 (5MA)", f"{res['ma_status']['ma5_val']:.2f}", f"{res['ma_status']['ma5_diff']:+.1f}%")
            m2.metric("月線 (20MA)", f"{res['ma_status']['ma20_val']:.2f}", f"{res['ma_status']['ma20_diff']:+.1f}%")
            m3.metric("季線 (60MA)", f"{res['ma_status']['ma60_val']:.2f}", f"{res['ma_status']['ma60_diff']:+.1f}%")

        # 模組 5：體質護城河 (P0-3: 嚴格無虛構分數)
        fund_title = "💎 【ETF 專屬體質與配息分析】" if is_etf_asset else "💎 【企業基本面體質護城河】"
        with st.expander(fund_title, expanded=False):
            f_data = res['fund_data']
            if not f_data.get("has_data", False):
                st.warning("⚠️ 該標的未揭露足夠之財報/配息數據，系統已將基本面評分排除，並自動重新權衡動能指標。")
            elif is_etf_asset:
                f1, f2 = st.columns(2)
                f1.metric("預估年化殖利率", f"{f_data['yield']:.1f}%" if f_data['yield'] is not None else "未揭露")
                f2.metric("Beta 波動係數", f"{f_data['beta']:.2f}" if f_data['beta'] is not None else "未揭露")
                if f_data.get('nav') is not None:
                    st.caption(f"淨值 (NAV): {f_data['nav']:.2f} 元")
            else:
                f1, f2 = st.columns(2)
                f1.metric("ROE 股東權益報酬率", f"{f_data['roe']:.1f}%" if f_data['roe'] is not None else "無數據")
                f2.metric("營業利益率", f"{f_data['op_margin']:.1f}%" if f_data['op_margin'] is not None else "無數據")
                f3, f4 = st.columns(2)
                f3.metric("本益比 (PE)", f"{f_data['pe']:.1f}x" if f_data['pe'] is not None else "無數據")
                f4.metric("負債比率 (D/E)", f"{f_data['debt_ratio']:.1f}%" if f_data['debt_ratio'] is not None else "無數據")

            st.write("---")
            for r in f_data.get('reasons', []):
                st.write(f"• {r}")

        # 模組 6：階梯停利 SOP
        with st.expander("🚪 【階梯式分階出場 SOP】", expanded=False):
            st.markdown(f"""
            - **初始防守停損**：跌破 **`{res['stop_loss']:.2f}` 元** 嚴格離場，絕不凹單。
            - **第一階段目標（減碼 1/2）**：達 **`{target_1:.2f}` 元**（1.5R 盈虧比），賣出半數部位並上移防守至成本價（鎖定保本）。
            - **第二階段目標（波段收割）**：達 **`{res['target_60d']:.2f}` 元** 分批落袋。
            - **移動停利（Trailing Stop）**：其餘部位收盤跌破 5 日線全數獲利了結。
            """)

        # 模組 7：部位風控計算機
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
            b3.metric("目標獲利區", f"{res['target_60d']:.2f} 元")
            b4.metric("預期盈虧比 (R/R)", f"{rr_ratio:.2f} : 1")

        # 模組 8：無前視偏誤回測 (P0-2: 單部位循序模型)
        with st.expander("📊 【過去 1 年策略回測數據 (無前視偏誤・單部位模型)】", expanded=False):
            bt = backtest_strategy(df_stock)
            if bt:
                bt1, bt2 = st.columns(2)
                bt1.metric("近 1 年訊號次數", f"{bt['count']} 次")
                bt2.metric("持有 5 日勝率", f"{bt['win_rate']:.1f}%")
                bt3, bt4 = st.columns(2)
                bt3.metric("平均淨報酬率", f"{bt['avg_return']:+.2f}%", help="次日開盤進場，已扣除 0.45% 手續費與稅")
                bt4.metric("真實最大回撤 (MDD)", f"{bt['mdd']:.2f}%", help="連續權益曲線之最大峰谷回撤")
                st.caption(f"📌 單部位循序進出（持倉中不重複進場）、單次最差交易：`{bt['worst_loss']:.2f}%`")
            else:
                st.write("該標的歷史數據樣本不足以計算有效回測。")

        # 模組 9：均線走勢圖
        with st.expander("📈 【均線價格走勢圖】", expanded=False):
            valid_cols = ['Close']
            for c in ['MA5', 'MA20', 'MA60']:
                if c in df_stock.columns and df_stock[c].notna().sum() > 5:
                    valid_cols.append(c)
            chart_data = df_stock[valid_cols].dropna().tail(60)
            st.line_chart(chart_data)

# ================= 模式 2：📊 ETF 專區 (P1-7: 錯誤收集不靜默) =================
elif st.session_state.main_mode == "etf":
    st.subheader("📊 ETF 旗艦量化策略雷達")
    st.caption("熱門 ETF 全方位即時體檢・配息防禦 × 均線動能 × 定期定額試算")

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
        failed_etfs = []

        def etf_worker(item):
            try:
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

        # P1-7: 透明展示未成功標的
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

# ================= 模式 3：⚡ 期貨與美台跨市場連動 (P1-6: 期現貨日期同步檢驗) =================
elif st.session_state.main_mode == "futures":
    st.subheader("⚡ 期貨與美台跨市場連動核心")

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
        c_a3.metric("ADR 理論折合價", f"{parity_twd:.2f} 元" if parity_twd > 0 else "匯率檢索中")
        c_a4.metric("即時溢價率", f"{premium_pct:+.2f}%" if parity_twd > 0 else "--")

        if premium_pct >= 10.0:
            st.success(f"🔥 **ADR 大幅溢價 (+{premium_pct:.1f}%)**：次日台股高機率具備強勁推升動能！")
        elif premium_pct <= -2.0:
            st.warning(f"⚠️ **ADR 出現折價 ({premium_pct:.1f}%)**：提防現貨與 ADR 跨市場套利賣壓！")
        else:
            st.info(f"⚖️ **合理溢價區間 ({premium_pct:+.1f}%)**")
    st.write("---")

    st.markdown("### 📊 台指期 (WTX) 與現貨基差 (Basis)")
    # P1-6: 跨市場時間一致性校驗
    if df_market is not None and df_futures is not None:
        twii_close = df_market.iloc[-1]['Close']
        fut_close = df_futures.iloc[-1]['Close']
        date_twii = df_market.index[-1].date()
        date_fut = df_futures.index[-1].date()
        basis = fut_close - twii_close

        fb1, fb2, fb3 = st.columns(3)
        fb1.metric("現貨指數", f"{twii_close:.1f}")
        fb2.metric("台指期貨", f"{fut_close:.1f}")
        fb3.metric("即時基差", f"{basis:+.1f} 點")

        if date_twii == date_fut:
            if basis > 30:
                st.success("🟢 **實質正價差格局**：主力大額資金態度偏多樂觀！")
            elif basis < -60:
                st.warning("⚠️ **大幅逆價差格局**：避險情緒升溫，短線提防拉回洗盤！")
            else:
                st.info("⚪ **正常平價價差**")
        else:
            st.warning(f"⚠️ **期現貨日期不同步**：現貨最新日期為 `{date_twii}`，期貨為 `{date_fut}`（可能適逢期指夜盤或結算日），計算之基差僅供參考。")
    else:
        st.warning("⚠️ **期貨資料不可用**：台指期 (WTX=F) 連線中斷或非交易時段，系統嚴格拒絕使用現貨指數假冒。")

    st.write("---")

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

# ================= 模式 4：💎 體質績優雷達 (P1-7: 錯誤透明反饋) =================
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
                    r = analyze_full_stock(code, df_stk, df_market, df_futures, df_tsm, df_sox, global_forex)
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
                    c_m3.caption(f"PE: **{row['本益比']:.1f}x**" if row['本益比'] is not None else "PE: --")
                    st.caption(f"防守 (停損): **{row['建議防守']:.2f} 元**")
                    st.write("---")

        if failed_stocks:
            with st.expander("⚠️ 部分標的連線未成功清單", expanded=False):
                for err in failed_stocks:
                    st.write(f"• {err}")

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
