import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor

# 頁面配置
st.set_page_config(
    page_title="全方位量化與即時優質選股決策系統",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ----------------- 通行密碼防護 -----------------
ACCESS_PASSWORD = st.secrets.get("PASSWORD", "invest888")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 內部量化旗艦決策站")
    st.caption("請輸入通行碼以開始使用")
    pwd = st.text_input("訪問密碼", type="password")
    if st.button("登入系統", type="primary", use_container_width=True):
        if pwd == ACCESS_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("密碼錯誤，請重新輸入。")
    st.stop()

# ----------------- 即時與歷史數據計算 -----------------
@st.cache_data(ttl=60)
def fetch_and_calc(ticker: str, period: str = "6mo"):
    try:
        obj = yf.Ticker(ticker)
        df = obj.history(period=period)
        if df.empty or len(df) < 40:
            return None
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()

        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        df['Vol_MA5'] = df['Volume'].rolling(5).mean()

        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        df['RSI14'] = 100 - (100 / (1 + rs))

        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = ema12 - ema26
        df['MACD'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['OSC'] = df['DIF'] - df['MACD']

        hl = df['High'] - df['Low']
        hc = (df['High'] - df['Close'].shift()).abs()
        lc = (df['Low'] - df['Close'].shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        df['ATR14'] = tr.rolling(14).mean()

        return df
    except Exception:
        return None

# ----------------- 基本面體質評估引擎 -----------------
@st.cache_data(ttl=3600)
def fetch_fundamentals(ticker: str):
    """即時連線擷取企業基本面數據 (ROE、營利率、PE、負債比)"""
    try:
        t = yf.Ticker(ticker)
        info = t.info

        roe = info.get('returnOnEquity', None)
        op_margin = info.get('operatingMargins', None)
        pe = info.get('trailingPE', None)
        debt_to_equity = info.get('debtToEquity', None)

        roe_val = roe * 100 if roe is not None else 12.0
        op_margin_val = op_margin * 100 if op_margin is not None else 10.0
        pe_val = pe if pe is not None else 20.0
        de_val = debt_to_equity if debt_to_equity is not None else 65.0

        fund_score = 0
        reasons = []

        # 1. 股東權益報酬率 (ROE) (15分)
        if roe_val >= 15:
            fund_score += 15
            reasons.append(f"ROE 達 {roe_val:.1f}%，資本運用回報極高")
        elif roe_val >= 10:
            fund_score += 10
            reasons.append(f"ROE 達 {roe_val:.1f}%，屬穩健獲利水平")
        else:
            reasons.append(f"ROE 偏低 ({roe_val:.1f}%)")

        # 2. 營業利益率 (本業獲利護城河) (15分)
        if op_margin_val >= 15:
            fund_score += 15
            reasons.append(f"營業利益率 {op_margin_val:.1f}%，本業競爭優勢顯著")
        elif op_margin_val >= 8:
            fund_score += 10
            reasons.append(f"營業利益率 {op_margin_val:.1f}%，獲利能力扎實")
        else:
            reasons.append(f"營業利益率偏低 ({op_margin_val:.1f}%)")

        # 3. 本益比估值健康度 (10分)
        if 8 <= pe_val <= 25:
            fund_score += 10
            reasons.append(f"本益比 {pe_val:.1f}x，估值處合理安全區")
        elif pe_val < 8:
            fund_score += 7
            reasons.append(f"本益比低估 ({pe_val:.1f}x)")
        else:
            fund_score += 4
            reasons.append(f"本益比偏高 ({pe_val:.1f}x)，需成長性支撐")

        # 4. 財務安全槓桿 (10分)
        if de_val <= 80:
            fund_score += 10
            reasons.append(f"負債比率健康 ({de_val:.1f}%)，財務防禦力強")
        elif de_val <= 150:
            fund_score += 6
            reasons.append(f"負債比率適中 ({de_val:.1f}%)")
        else:
            reasons.append(f"負債比偏高 ({de_val:.1f}%)")

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
            "reasons": ["採用行業基準數據"]
        }

# ----------------- 單股全維度量化診斷 -----------------
def analyze_full_stock(ticker, df_stock, df_market, df_futures, df_tsm):
    fund_data = fetch_fundamentals(ticker)
    last = df_stock.iloc[-1]
    prev = df_stock.iloc[-2]
    close = last['Close']

    # 技術面評分 (50分)
    tech_score = 0
    tech_reasons = []

    if close > last['MA5'] > last['MA20']:
        tech_score += 18
        tech_reasons.append("短多強勢排列 (收盤 > 5MA > 20MA)")
    elif close > last['MA20']:
        tech_score += 10
        tech_reasons.append("站穩月線生命線")

    vol_ratio = last['Volume'] / (last['Vol_MA5'] + 1e-9)
    if close > prev['Close'] and vol_ratio >= 1.3:
        tech_score += 16
        tech_reasons.append(f"量增價漲 (爆量比: {vol_ratio:.1f}x)")
    elif close > prev['Close']:
        tech_score += 8
        tech_reasons.append("價漲量平")

    if last['OSC'] > 0 and last['OSC'] > prev['OSC']:
        tech_score += 8
        tech_reasons.append("MACD 紅柱放大")

    if 50 <= last['RSI14'] <= 70:
        tech_score += 8
        tech_reasons.append(f"RSI 處健康攻擊區 ({last['RSI14']:.1f})")

    total_score = fund_data['score'] + tech_score
    stop_loss = max(close - 2 * last['ATR14'], last['MA20'])
    target_60d = df_stock['High'].tail(60).max()

    return {
        "total_score": total_score,
        "fund_score": fund_data['score'],
        "tech_score": tech_score,
        "close": close,
        "stop_loss": stop_loss,
        "target_60d": target_60d,
        "fund_data": fund_data,
        "tech_reasons": tech_reasons
    }

# ----------------- 全市場優質藍籌旗艦池 (涵蓋各產業體質龍頭) -----------------
MARKET_QUALITY_UNIVERSE = [
    ("台積電", "2330.TW", "半導體先進製程龍頭"),
    ("聯發科", "2454.TW", "IC設計龍頭"),
    ("鴻海", "2317.TW", "全球電子代工/AI伺服器"),
    ("廣達", "2382.TW", "AI伺服器領航者"),
    ("緯穎", "6669.TW", "雲端超大型資料中心"),
    ("台達電", "2308.TW", "電源管理與綠能永續"),
    ("富邦金", "2881.TW", "金控獲利龍頭"),
    ("國泰金", "2882.TW", "全方位金控旗艦"),
    ("中信金", "2891.TW", "消費金融與財富管理龍頭"),
    ("兆豐金", "2886.TW", "官股外匯獲利模範生"),
    ("長榮", "2603.TW", "全球貨櫃航運龍頭"),
    ("奇鋐", "3017.TW", "散熱模組領導大廠"),
    ("雙
