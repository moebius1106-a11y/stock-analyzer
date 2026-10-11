import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# 頁面配置
st.set_page_config(
    page_title="次日開市全自動量化決策站",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ----------------- 通行密碼防護 -----------------
ACCESS_PASSWORD = st.secrets.get("PASSWORD", "invest888")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 內部量化決策站")
    st.caption("請輸入通行碼以開始使用")
    pwd = st.text_input("訪問密碼", type="password")
    if st.button("登入系統", type="primary", use_container_width=True):
        if pwd == ACCESS_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("密碼錯誤，請重新輸入。")
    st.stop()

# ----------------- 行情數據與指標計算 -----------------
@st.cache_data(ttl=300)
def fetch_and_calc(ticker: str, period: str = "1y"):
    try:
        obj = yf.Ticker(ticker)
        df = obj.history(period=period)
        if df.empty or len(df) < 60:
            return None
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()

        # 均線 (5MA, 20MA, 60MA)
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        df['Vol_MA5'] = df['Volume'].rolling(5).mean()

        # RSI (14)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        df['RSI14'] = 100 - (100 / (1 + rs))

        # MACD (12, 26, 9)
        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = ema12 - ema26
        df['MACD'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['OSC'] = df['DIF'] - df['MACD']

        # ATR (14)
        hl = df['High'] - df['Low']
        hc = (df['High'] - df['Close'].shift()).abs()
        lc = (df['Low'] - df['Close'].shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        df['ATR14'] = tr.rolling(14).mean()

        return df
    except Exception:
        return None

# ----------------- 綜合量化評分引擎 -----------------
def evaluate_stock_quick(df_stock, df_market, df_futures, df_tsm):
    """計算單一標的之綜合量化分數 (用於篩選與分析)"""
    if df_stock is None or len(df_stock) < 30:
        return 0, 0, 0, 0

    last = df_stock.iloc[-1]
    prev = df_stock.iloc[-2]

    # 1. 大盤環境 (20分)
    score_mkt = 0
    if df_market is not None and not df_market.empty:
        last_mkt = df_market.iloc[-1]
        if last_mkt['Close'] > last_mkt['MA20']:
            score_mkt += 12
        if last_mkt['MA20'] > last_mkt['MA60']:
            score_mkt += 8

    # 2. 國際/期貨 (20分)
    score_macro = 10
    try:
        if df_tsm is not None and len(df_tsm) >= 2:
            tsm_pct = ((df_tsm['Close'].iloc[-1] - df_tsm['Close'].iloc[-2]) / df_tsm['Close'].iloc[-2]) * 100
            if tsm_pct > 1.0:
                score_macro += 5
            elif tsm_pct < -1.5:
                score_macro -= 5
        if df_futures is not None and not df_futures.empty:
            if df_futures.iloc[-1]['Close'] > df_futures.iloc[-1]['MA5']:
                score_macro += 5
    except Exception:
        pass

    # 3. 均線排列 (25分)
    score_ma = 0
    close = last['Close']
    if close > last['MA5'] > last['MA20'] > last['MA60']:
        score_ma = 25
    elif close > last['MA20'] and last['MA20'] > last['MA60']:
        score_ma = 18
    elif close > last['MA20']:
        score_ma = 12

    # 4. 量價與動能 (35分)
    score_tech = 0
    vol_ratio = last['Volume'] / (last['Vol_MA5'] + 1e-9)
    if close > prev['Close'] and vol_ratio >= 1.3:
        score_tech += 15
    elif close > prev['Close']:
        score_tech += 8

    if last['OSC'] > 0 and last['OSC'] > prev['OSC']:
        score_tech += 10
    elif last['OSC'] > 0:
        score_tech += 5

    if 50 <= last['RSI14'] <= 70:
        score_tech += 10

    total_score = score_mkt + score_macro + score_ma + score_tech
    stop_loss = max(close - 2 * last['ATR14'], last['MA20'])
    target_60d = df_stock['High'].tail(60).max()

    return total_score, close, stop_loss, target_60d

# ----------------- 歷史客觀勝率回測模組 -----------------
def backtest_strategy(df_stock):
    """回測過去 1 年內出現多頭訊號 (股價>20MA 且 量增價漲 且 MACD>0) 後持有 5 日的表現"""
    if len(df_stock) < 120:
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
            entry_p = df_stock['Close'].iloc[idx]
            exit_p = df_stock['Close'].iloc[idx + 5]
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

# ----------------- 手機 UI 介面 -----------------
st.title("📱 股期次日量化決策站")

# 觀察清單池 (涵蓋權值、半導體、AI、傳產龍頭)
FOCUS_POOL = [
    ("台積電", "2330.TW"), ("聯發科", "2454.TW"), ("鴻海", "2317.TW"),
    ("廣達", "2382.TW"), ("緯創", "3231.TW"), ("長榮", "2603.TW"),
    ("元大台灣50", "0050.TW"), ("欣興", "3037.TW"), ("世芯-KY", "3661.TW"),
    ("智原", "3035.TW"), ("奇鋐", "3017.TW"), ("雙鴻", "3324.TW")
]

# 頂部導航
mode = st.radio("功能選擇：", ["🔍 單股全維度深度體檢", "🚀 次日潛力股自動掃描"], horizontal=True)

# 預先載入宏觀環境
df_market = fetch_and_calc("^TWII")
df_futures = fetch_and_calc("WTX=F") or df_market
df_tsm = fetch_and_calc("TSM")
df_sox = fetch_and_calc("^SOX")

# ================= 模式 1：潛力股雷達掃描 =================
if mode == "🚀 次日潛力股自動掃描":
    st.subheader("🚀 明日高勝率候選股排行榜")
    st.caption("自動掃描重點熱門池，篩選出均線多頭、量能爆發與國際盤共振的標的")

    if st.button("🔥 開始全自動掃描排行", type="primary", use_container_width=True):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, (name, code) in enumerate(FOCUS_POOL):
            status_text.text(f"分析中: {name} ({code})...")
            df_stk = fetch_and_calc(code)
            if df_stk is not None:
                score, close_p, stop_p, _ = evaluate_stock_quick(df_stk, df_market, df_futures, df_tsm)
                results.append({"名稱": name, "代碼": code, "總評分": score, "最新價": close_p, "防守價": stop_p})
            progress_bar.progress((i + 1) / len(FOCUS_POOL))

        status_text.empty()
        progress_bar.empty()

        results_df = pd.DataFrame(results).sort_values(by="總評分", ascending=False).reset_index(drop=True)

        st.write("---")
        for rank, row in results_df.iterrows():
            badge = "🟢 優先關注" if row['總評分'] >= 75 else ("🟡 震盪觀察" if row['總評分'] >= 50 else "🔴 避開")
            with st.container():
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.markdown(f"**#{rank+1} {row['名稱']} ({row['代碼']})**")
                c2.markdown(f"評分: **{row['總評分']}** 分")
                c3.caption(badge)
                st.caption(f"最新價: {row['最新價']:.2f} 元 ｜ 建議防守點: {row['防守價']:.2f} 元")
                st.write("---")

# ================= 模式 2：單股深度體檢 =================
else:
    st.caption("熱門標的一鍵選取：")
    q_cols = st.columns(4)
    quick_list = [("台積電", "2330.TW"), ("聯發科", "2454.TW"), ("鴻海", "2317.TW"), ("元大台灣50", "0050.TW")]

    if "selected_ticker" not in st.session_state:
        st.session_state.selected_ticker = "2330.TW"

    for i, (name, code) in enumerate(quick_list):
        if q_cols[i].button(name, use_container_width=True):
            st.session_state.selected_ticker = code

    ticker_input = st.text_input("輸入查詢代碼 (上市 .TW / 上櫃 .TWO)", value=st.session_state.selected_ticker)

    if st.button("🔍 執行次日全維度診斷", type="primary", use_container_width=True):
        with st.spinner("同步運算技術量價、均線矩陣與歷史數據..."):
            df_stock = fetch_and_calc(ticker_input.strip())

        if df_stock is None:
            st.error("無法取得該標的行情數據，請確認代碼是否正確。")
        else:
            score, close_p, stop_p, target_60d = evaluate_stock_quick(df_stock, df_market, df_futures, df_tsm)
            risk_unit = max(close_p - stop_p, 0.1)

            # 階梯式停利價位計算
            target_1 = close_p + (1.5 * risk_unit)      # 第一目標 (1.5R 盈虧比)
            target_2 = max(target_60d, close_p * 1.05)  # 第二目標 (波段壓力)

            # 頂部核心卡片
            c1, c2 = st.columns(2)
            c1.metric("綜合決策評分", f"{score} / 100")
            c2.metric("最新收盤價", f"{close_p:.2f} 元")

            c3, c4 = st.columns(2)
            c3.metric("建議停損點 (破線退場)", f"{stop_p:.2f} 元")
            c4.metric("單股承擔風險", f"{((risk_unit / close_p) * 100):.2f}%")

            st.divider()

            # 5 大功能分頁
            t_dec, t_exit, t_backtest, t_ma, t_chart = st.tabs([
                "🎯 決策結論", "🚪 階梯停利 SOP", "📊 客觀歷史勝率", "📏 均線位階矩陣", "📈 價格走勢圖"
            ])

            # Tab 1: 決策
            with t_dec:
                if score >= 75:
                    st.success("### 🟢 積極偏多：次日適合依計畫進場")
                    st.write("大盤環境、均線架構與量價同步偏多，做多勝率高。")
                elif 50 <= score < 75:
                    st.warning("### 🟡 中性觀望：僅限 1/3 以下微型部位試單")
                    st.write("指標處於整理或分歧階段，不可盲目追價。")
                else:
                    st.error("### 🔴 偏空避開：下個開市日不建議進場")
                    st.write("空方壓制或大盤風險高，保持空手、持盈保泰。")

            # Tab 2: 停利 SOP
            with t_exit:
                st.subheader("🚪 機械化出場規劃（告別抱上抱下）")
                st.markdown(f"""
                - **初始停損防守**：跌破 **`{stop_p:.2f}` 元** 立即退場，不凹單。
                - **第一階段目標（減碼 1/2）**：達 **`{target_1:.2f}` 元**（盈虧比 1.5R），**立即賣出半數部位入袋，並將剩餘部位停損點上移至進場成本（鎖定保本）**。
                - **第二階段目標（波段目標）**：達 **`{target_2:.2f}` 元**（波段壓力位），視量能分批收工。
                - **移動停利（Trailing Stop）**：其餘部位若收盤**跌破 5 日均線**或**自波段高點拉回超過 2 倍 ATR**，全數獲利了結。
                """)

            # Tab 3: 回測驗證
            with t_backtest:
                st.subheader("📊 過去 1 年策略回測真實數據")
                bt = backtest_strategy(df_stock)
                if bt:
                    b1, b2 = st.columns(2)
                    b1.metric("近 1 年訊號觸發次數", f"{bt['count']} 次")
                    b2.metric("持有 5 日勝率", f"{bt['win_rate']:.1f}%")

                    b3, b4 = st.columns(2)
                    b3.metric("5 日平均報酬率", f"{bt['avg_return']:+.2f}%")
                    b4.metric("單次最大回撤拉回", f"{bt['max_drawdown']:.2f}%")

                    st.caption("※ 回測邏輯：當該股在過去符合月線上走揚、量增價漲與動能偏多時進場持有 5 日之歷史回溯。")
                else:
                    st.write("數據樣本不足，無法進行有效回測。")

            # Tab 4: 均線矩陣
            with t_ma:
                st.subheader("📏 日 / 月 / 季線 位階")
                last_row = df_stock.iloc[-1]
                m1, m2, m3 = st.columns(3)
                m1.metric("日線 (5MA)", f"{last_row['MA5']:.2f}")
                m2.metric("月線 (20MA)", f"{last_row['MA20']:.2f}")
                m3.metric("季線 (60MA)", f"{last_row['MA60']:.2f}")

            # Tab 5: 走勢
            with t_chart:
                st.line_chart(df_stock[['Close', 'MA5', 'MA20', 'MA60']].dropna().tail(50))
