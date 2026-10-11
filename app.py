import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# 頁面配置 (針對手機瀏覽最適化)
st.set_page_config(
    page_title="次日開市決策系統 (專業版)",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ----------------- 通行密碼防護 -----------------
ACCESS_PASSWORD = st.secrets.get("PASSWORD", "invest888")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 內部決策系統 (專業版)")
    st.caption("請輸入通行碼以開始使用")
    pwd = st.text_input("訪問密碼", type="password")
    if st.button("登入系統", type="primary", use_container_width=True):
        if pwd == ACCESS_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("密碼錯誤，請重新輸入。")
    st.stop()

# ----------------- 行情數據與技術指標計算 -----------------
@st.cache_data(ttl=600)
def fetch_and_calc(ticker: str):
    try:
        obj = yf.Ticker(ticker)
        df = obj.history(period="6mo")
        if df.empty:
            return None
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()

        # 均線
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

        # ATR (14) - 動態真實波動區間
        hl = df['High'] - df['Low']
        hc = (df['High'] - df['Close'].shift()).abs()
        lc = (df['Low'] - df['Close'].shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        df['ATR14'] = tr.rolling(14).mean()

        return df
    except Exception:
        return None

# ----------------- 跨維度量化診斷核心 -----------------
def analyze_all(df_stock, df_market, df_futures, df_tsm, df_sox):
    # 1. 國際盤與美股半導體聯動 (滿分 15)
    global_score = 0
    global_reasons = []
    try:
        tsm_change = ((df_tsm['Close'].iloc[-1] - df_tsm['Close'].iloc[-2]) / df_tsm['Close'].iloc[-2]) * 100
        sox_change = ((df_sox['Close'].iloc[-1] - df_sox['Close'].iloc[-2]) / df_sox['Close'].iloc[-2]) * 100

        if tsm_change >= 1.5 and sox_change > 0:
            global_score += 15
            global_reasons.append(f"TSM ADR 大漲 ({tsm_change:+.1f}%) 且費半走揚，隔日開高機率高")
        elif tsm_change > 0:
            global_score += 10
            global_reasons.append(f"TSM ADR 小漲 ({tsm_change:+.1f}%)，國際盤情緒平穩偏多")
        elif tsm_change > -1.5:
            global_score += 6
            global_reasons.append(f"TSM ADR 小跌 ({tsm_change:+.1f}%)，需留意早盤震盪")
        else:
            global_reasons.append(f"TSM ADR 重挫 ({tsm_change:+.1f}%)，需嚴防次日恐慌性開低跳空")
    except Exception:
        global_score = 8
        global_reasons.append("國際美股盤勢資訊未完整連線，採中立基準分")

    # 2. 加權大盤結構 (滿分 20)
    last_mkt = df_market.iloc[-1]
    mkt_score = 0
    mkt_reasons = []
    if last_mkt['Close'] > last_mkt['MA20']:
        mkt_score += 12
        mkt_reasons.append("加權指數站上月線 (MA20)，多方掌控趨勢")
    else:
        mkt_reasons.append("大盤跌破月線，系統性拉回風險偏高")
    if last_mkt['MA20'] > last_mkt['MA60']:
        mkt_score += 8
        mkt_reasons.append("加權指數季線架構多頭 (MA20 > MA60)")

    # 3. 期貨領先動能 (滿分 15)
    fut_score = 0
    fut_reasons = []
    try:
        last_fut = df_futures.iloc[-1]
        if last_fut['Close'] > last_fut['MA5']:
            fut_score += 10
            fut_reasons.append("期指收在 5MA 之上，短線追價動能強")
        else:
            fut_reasons.append("期指跌破 5MA，短多力道受限")
        if last_fut['Close'] >= last_mkt['Close']:
            fut_score += 5
            fut_reasons.append("期指正價差，市場對後市偏樂觀")
        else:
            fut_reasons.append("期指逆價差，提防多空洗盤")
    except Exception:
        fut_score = 8
        fut_reasons.append("期貨數據持平中立計算")

    # 4. 個股量價與指標 (滿分 50)
    last_stk = df_stock.iloc[-1]
    prev_stk = df_stock.iloc[-2]
    stk_score = 0
    stk_reasons = []

    # 均線多頭
    if last_stk['Close'] > last_stk['MA5'] and last_stk['MA5'] > last_stk['MA20']:
        stk_score += 15
        stk_reasons.append("短多排列 (收盤 > 5MA > 20MA)")
    elif last_stk['Close'] > last_stk['MA20']:
        stk_score += 8
        stk_reasons.append("守穩月線支撐")
    else:
        stk_reasons.append("股價跌破月線，短多格局轉弱")

    # 成交量
    vol_ratio = last_stk['Volume'] / (last_stk['Vol_MA5'] + 1e-9)
    if last_stk['Close'] > prev_stk['Close'] and vol_ratio >= 1.3:
        stk_score += 15
        stk_reasons.append(f"量增價漲 (成交量為 5 日均量 {vol_ratio:.1f} 倍)")
    elif last_stk['Close'] > prev_stk['Close']:
        stk_score += 8
        stk_reasons.append("價漲但量能平淡，觀察追價力道")
    else:
        stk_reasons.append("量價背離或下殺出量")

    # MACD
    if last_stk['OSC'] > 0 and last_stk['OSC'] > prev_stk['OSC']:
        stk_score += 10
        stk_reasons.append("MACD 紅柱放大，攻擊動能充沛")
    elif last_stk['OSC'] > 0:
        stk_score += 5
        stk_reasons.append("MACD 維持多頭，但紅柱收斂")

    # RSI
    if 50 <= last_stk['RSI14'] <= 70:
        stk_score += 10
        stk_reasons.append(f"RSI 位於攻擊區 ({last_stk['RSI14']:.1f})")
    elif last_stk['RSI14'] > 70:
        stk_score += 5
        stk_reasons.append(f"RSI 超買 ({last_stk['RSI14']:.1f})，防高檔回吐")
    else:
        stk_reasons.append(f"RSI 偏弱 ({last_stk['RSI14']:.1f})")

    # 風險點位計算 (ATR 停損與 60 日壓力目標)
    stop_loss = max(last_stk['Close'] - 2 * last_stk['ATR14'], last_stk['MA20'])
    target_price = df_stock['High'].tail(60).max()  # 近 60 日波段最高點作為目標價

    total_score = global_score + mkt_score + fut_score + stk_score

    return {
        "total_score": total_score,
        "close": last_stk['Close'],
        "stop_loss": stop_loss,
        "target_price": target_price,
        "global_reasons": global_reasons,
        "mkt_reasons": mkt_reasons,
        "fut_reasons": fut_reasons,
        "stk_reasons": stk_reasons
    }

# ----------------- 手機 UI 介面 -----------------
st.title("📱 股期決策儀表板 (專業版)")

# 快速切換按鈕
st.caption("熱門標的一鍵選取：")
cols = st.columns(4)
quick_picks = [("台積電", "2330.TW"), ("聯發科", "2454.TW"), ("鴻海", "2317.TW"), ("元大台灣50", "0050.TW")]

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "2330.TW"

for i, (name, code) in enumerate(quick_picks):
    if cols[i].button(name, use_container_width=True):
        st.session_state.selected_ticker = code

ticker_input = st.text_input("查詢代碼 (上市加 .TW / 上櫃加 .TWO)", value=st.session_state.selected_ticker)

if st.button("🔍 執行次日全維度開市分析", type="primary", use_container_width=True):
    with st.spinner("同步擷取 台股/期指/台積ADR/美股費半數據中..."):
        df_stock = fetch_and_calc(ticker_input.strip())
        df_market = fetch_and_calc("^TWII")
        df_futures = fetch_and_calc("WTX=F")
        df_tsm = fetch_and_calc("TSM")
        df_sox = fetch_and_calc("^SOX")

        if df_futures is None:
            df_futures = df_market

    if df_stock is None or df_market is None:
        st.error("無法取得目標標的行情，請確認代碼輸入是否正確。")
    else:
        res = analyze_all(df_stock, df_market, df_futures, df_tsm, df_sox)

        # 頂部數值卡片
        c1, c2 = st.columns(2)
        c1.metric("綜合信心評分", f"{res['total_score']} / 100")
        c2.metric("最新收盤價", f"{res['close']:.2f} 元")

        c3, c4 = st.columns(2)
        c3.metric("建議防守價 (停損)", f"{res['stop_loss']:.2f} 元")
        risk_pct = ((res['close'] - res['stop_loss']) / res['close']) * 100
        c4.metric("最大預期風險", f"{risk_pct:.1f}%")

        st.divider()

        # 分頁標籤切換
        tab1, tab2, tab3, tab4 = st.tabs(["🎯 決策結論", "💰 部位風控計算機", "📊 跨維度明細", "📈 價格走勢"])

        with tab1:
            if res['total_score'] >= 75:
                st.success("### 🟢 積極偏多：次日適合進場")
                st.markdown(f"""
                - **隔日進場條件**：開盤若未受美股暴跌影響，且早盤量能持穩，可分批建立部位。
                - **波段防守點位**：嚴格以 **{res['stop_loss']:.2f} 元** 作為退場基準。
                """)
            elif 50 <= res['total_score'] < 75:
                st.warning("### 🟡 中性觀望：僅限小部位試單")
                st.markdown("""
                - **當前情勢**：國際盤或個股內部指標尚未完全同步，追價勝率普通。
                - **操作建議**：僅適合 1/3 以下微型部位試單，切勿盲目重押。
                """)
            else:
                st.error("### 🔴 偏空避開：次日不建議進場")
                st.markdown("""
                - **當前情勢**：市場結構偏弱，下檔空間未明確止跌。
                - **操作建議**：現金為王，維持空手觀望。
                """)

        with tab2:
            st.subheader("🧮 部位規模與盈虧比試算")
            st.caption("嚴格紀律：根據可承受損失，反推次日應買進的張數")

            col_cap, col_risk = st.columns(2)
            with col_cap:
                total_capital = st.number_input("總操作資金 (NTD)", value=1000000, step=100000)
            with col_risk:
                risk_tolerance = st.slider("單筆最大承受損失比率", min_value=0.5, max_value=3.0, value=1.0, step=0.1)

            # 計算部位張數
            max_risk_dollar = total_capital * (risk_tolerance / 100.0)
            loss_per_share = max(res['close'] - res['stop_loss'], 0.1)
            loss_per_lot = loss_per_share * 1000  # 一張 1000 股
            suggested_lots = int(max_risk_dollar // loss_per_lot)

            # 盈虧比計算 (Reward / Risk)
            potential_reward = max(res['target_price'] - res['close'], 0)
            rr_ratio = potential_reward / loss_per_share if loss_per_share > 0 else 0

            st.write("---")
            b1, b2 = st.columns(2)
            b1.metric("單筆最大容許虧損", f"{int(max_risk_dollar):,} 元")
            b2.metric("建議最大進場張數", f"{suggested_lots} 張", help="若大於 0 代表在停損紀律下可買進的上限")

            b3, b4 = st.columns(2)
            b3.metric("目標獲利區 (近60日高)", f"{res['target_price']:.2f} 元")
            b4.metric("預期盈虧比 (R/R)", f"{rr_ratio:.2f} : 1")

            if rr_ratio < 1.5:
                st.caption("⚠️ 提醒：盈虧比小於 1.5:1，上方空間相對有限，不宜積極追高。")
            else:
                st.caption("✅ 盈虧比達標：上方目標獲利空間大於停損風險區間。")

        with tab3:
            st.markdown("**【國際盤聯動 (TSM ADR / 費城半導體)】**")
            for r in res['global_reasons']:
                st.write(f"• {r}")

            st.markdown("**【加權大盤結構】**")
            for r in res['mkt_reasons']:
                st.write(f"• {r}")

            st.markdown("**【期貨動能與價差】**")
            for r in res['fut_reasons']:
                st.write(f"• {r}")

            st.markdown("**【個股量價指標】**")
            for r in res['stk_reasons']:
                st.write(f"• {r}")

        with tab4:
            st.line_chart(df_stock[['Close', 'MA20']].dropna().tail(50))
