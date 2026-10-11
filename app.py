import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# 頁面配置
st.set_page_config(
    page_title="次日開市與即時決策系統 (旗艦版)",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ----------------- 通行密碼防護 -----------------
ACCESS_PASSWORD = st.secrets.get("PASSWORD", "invest888")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 內部決策系統 (旗艦版)")
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
@st.cache_data(ttl=60)  # 快取設為 60 秒，兼顧盤中即時性與連線效能
def fetch_and_calc(ticker: str):
    try:
        obj = yf.Ticker(ticker)
        df = obj.history(period="6mo")
        if df.empty:
            return None
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()

        # 日線 (5MA)、月線 (20MA)、季線 (60MA)
        df['MA5'] = df['Close'].rolling(5).mean()    # 日線/週均
        df['MA20'] = df['Close'].rolling(20).mean()  # 月線
        df['MA60'] = df['Close'].rolling(60).mean()  # 季線
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

# ----------------- 開盤即時與均線分析 -----------------
def analyze_opening_and_ma(df_stock):
    last = df_stock.iloc[-1]
    prev = df_stock.iloc[-2]

    # 1. 均線位階與排列分析
    close = last['Close']
    ma5 = last['MA5']
    ma20 = last['MA20']
    ma60 = last['MA60']

    ma_status = {
        "ma5_diff": ((close - ma5) / ma5) * 100,
        "ma20_diff": ((close - ma20) / ma20) * 100,
        "ma60_diff": ((close - ma60) / ma60) * 100,
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
        ma_alignment = "🔄 均線震盪糾結 (多空方向待突破)"
        ma_score = 10

    # 2. 開盤即時動態連動
    open_p = last['Open']
    prev_close = prev['Close']
    gap_pct = ((open_p - prev_close) / prev_close) * 100
    intraday_pct = ((close - open_p) / open_p) * 100

    opening_diag = []
    if gap_pct >= 1.5:
        opening_diag.append(f"強勢跳空開高 (+{gap_pct:.2f}%)，買盤企圖心強。")
    elif gap_pct <= -1.5:
        opening_diag.append(f"弱勢跳空開低 ({gap_pct:.2f}%)，下檔承接力道待觀察。")
    else:
        opening_diag.append(f"平盤附近開出 ({gap_pct:+.2f}%)，由盤中量能決定方向。")

    if close > open_p:
        k_type = "🔴 盤中實體紅 K (開低走高或強開強走)"
        opening_diag.append("多方持續推進，買方居主導地位。")
    elif close < open_p:
        k_type = "🟢 盤中實體黑 K (開高走低或弱勢下殺)"
        opening_diag.append("需嚴防主力開高出貨或逢高解套賣壓。")
    else:
        k_type = "⚪ 盤中十字星 (多空平手拉鋸)"

    return ma_status, ma_alignment, ma_score, gap_pct, intraday_pct, k_type, opening_diag

# ----------------- 綜合全維度量化診斷 -----------------
def analyze_all(df_stock, df_market, df_futures, df_tsm, df_sox):
    last_stk = df_stock.iloc[-1]
    prev_stk = df_stock.iloc[-2]
    ma_status, ma_alignment, ma_score, gap_pct, intraday_pct, k_type, opening_diag = analyze_opening_and_ma(df_stock)

    # 國際盤 (滿分 15)
    global_score = 0
    global_reasons = []
    try:
        tsm_change = ((df_tsm['Close'].iloc[-1] - df_tsm['Close'].iloc[-2]) / df_tsm['Close'].iloc[-2]) * 100
        sox_change = ((df_sox['Close'].iloc[-1] - df_sox['Close'].iloc[-2]) / df_sox['Close'].iloc[-2]) * 100
        if tsm_change >= 1.5 and sox_change > 0:
            global_score += 15
            global_reasons.append(f"TSM ADR 漲 ({tsm_change:+.1f}%) 且費半走揚，隔日開盤動能強勁")
        elif tsm_change > 0:
            global_score += 10
            global_reasons.append(f"TSM ADR 小漲 ({tsm_change:+.1f}%)，美股氛圍平穩偏多")
        elif tsm_change > -1.5:
            global_score += 6
            global_reasons.append(f"TSM ADR 小跌 ({tsm_change:+.1f}%)，留意早盤震盪")
        else:
            global_reasons.append(f"TSM ADR 重挫 ({tsm_change:+.1f}%)，嚴防開盤恐慌跳空")
    except Exception:
        global_score = 8
        global_reasons.append("國際美股數據採中立基準分")

    # 大盤 (滿分 20)
    last_mkt = df_market.iloc[-1]
    mkt_score = 0
    mkt_reasons = []
    if last_mkt['Close'] > last_mkt['MA20']:
        mkt_score += 12
        mkt_reasons.append("大盤站上月線 (20MA)，趨勢偏多")
    else:
        mkt_reasons.append("大盤破月線，系統風險偏高")
    if last_mkt['MA20'] > last_mkt['MA60']:
        mkt_score += 8
        mkt_reasons.append("大盤季線多頭架構 (20MA > 60MA)")

    # 期貨 (滿分 15)
    fut_score = 0
    fut_reasons = []
    try:
        last_fut = df_futures.iloc[-1]
        if last_fut['Close'] > last_fut['MA5']:
            fut_score += 10
            fut_reasons.append("期貨站穩 5MA，短多力道積極")
        else:
            fut_reasons.append("期貨跌破 5MA，短多動能受限")
        if last_fut['Close'] >= last_mkt['Close']:
            fut_score += 5
            fut_reasons.append("期指正價差，市場樂觀")
        else:
            fut_reasons.append("期指逆價差，防回檔洗盤")
    except Exception:
        fut_score = 8
        fut_reasons.append("期貨採基準中立分")

    # 個股指標 (滿分 25)
    stk_tech_score = 0
    stk_reasons = []
    vol_ratio = last_stk['Volume'] / (last_stk['Vol_MA5'] + 1e-9)
    if last_stk['Close'] > prev_stk['Close'] and vol_ratio >= 1.3:
        stk_tech_score += 10
        stk_reasons.append(f"量增價漲 (爆量比: {vol_ratio:.1f}x 5日均量)")
    elif last_stk['Close'] > prev_stk['Close']:
        stk_tech_score += 5
        stk_reasons.append("價漲但量平")

    if last_stk['OSC'] > 0 and last_stk['OSC'] > prev_stk['OSC']:
        stk_tech_score += 8
        stk_reasons.append("MACD 紅柱放大，攻擊動能足")
    elif last_stk['OSC'] > 0:
        stk_tech_score += 4
        stk_reasons.append("MACD 維持多頭")

    if 50 <= last_stk['RSI14'] <= 70:
        stk_tech_score += 7
        stk_reasons.append(f"RSI 處健康攻擊區 ({last_stk['RSI14']:.1f})")

    # 總評分 (滿分 100 = 國際15 + 大盤20 + 期貨15 + 均線25 + 個股技術25)
    total_score = global_score + mkt_score + fut_score + ma_score + stk_tech_score
    stop_loss = max(last_stk['Close'] - 2 * last_stk['ATR14'], last_stk['MA20'])
    target_price = df_stock['High'].tail(60).max()

    return {
        "total_score": total_score,
        "close": last_stk['Close'],
        "stop_loss": stop_loss,
        "target_price": target_price,
        "ma_status": ma_status,
        "ma_alignment": ma_alignment,
        "gap_pct": gap_pct,
        "intraday_pct": intraday_pct,
        "k_type": k_type,
        "opening_diag": opening_diag,
        "global_reasons": global_reasons,
        "mkt_reasons": mkt_reasons,
        "fut_reasons": fut_reasons,
        "stk_reasons": stk_reasons
    }

# ----------------- 手機 UI 介面 -----------------
st.title("📱 股期決策儀表板 (旗艦版)")

# 快速標的按鈕
cols = st.columns(4)
quick_picks = [("台積電", "2330.TW"), ("聯發科", "2454.TW"), ("鴻海", "2317.TW"), ("元大台灣50", "0050.TW")]

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "2330.TW"

for i, (name, code) in enumerate(quick_picks):
    if cols[i].button(name, use_container_width=True):
        st.session_state.selected_ticker = code

ticker_input = st.text_input("輸入查詢代碼 (上市 .TW / 上櫃 .TWO)", value=st.session_state.selected_ticker)

if st.button("🔍 執行開盤即時與全維度分析", type="primary", use_container_width=True):
    with st.spinner("同步擷取 即時報價/日線/月線/季線/美股數據中..."):
        df_stock = fetch_and_calc(ticker_input.strip())
        df_market = fetch_and_calc("^TWII")
        df_futures = fetch_and_calc("WTX=F")
        df_tsm = fetch_and_calc("TSM")
        df_sox = fetch_and_calc("^SOX")
        if df_futures is None:
            df_futures = df_market

    if df_stock is None or df_market is None:
        st.error("無法取得行情數據，請確認代碼是否正確。")
    else:
        res = analyze_all(df_stock, df_market, df_futures, df_tsm, df_sox)

        # 頂部核心卡片
        c1, c2 = st.columns(2)
        c1.metric("多空綜合評分", f"{res['total_score']} / 100")
        c2.metric("最新報價", f"{res['close']:.2f} 元")

        c3, c4 = st.columns(2)
        c3.metric("建議防守價 (停損)", f"{res['stop_loss']:.2f} 元")
        risk_pct = ((res['close'] - res['stop_loss']) / res['close']) * 100
        c4.metric("最大預期風險", f"{risk_pct:.1f}%")

        st.divider()

        # 分頁選單
        tab_rt, tab1, tab2, tab3, tab4 = st.tabs([
            "⚡ 開盤即時連動", "🎯 決策結論", "📏 日/月/季線矩陣", "💰 風控計算機", "📈 均線技術走勢"
        ])

        # Tab: 開盤即時連動
        with tab_rt:
            st.subheader("⚡ 開盤即時狀態診斷")
            st.markdown(f"**當前 K 棒型態：** `{res['k_type']}`")

            k1, k2 = st.columns(2)
            k1.metric("開盤跳空幅度", f"{res['gap_pct']:+.2f}%")
            k2.metric("開盤至今漲跌", f"{res['intraday_pct']:+.2f}%")

            st.write("---")
            st.markdown("**【即時盤中操作建議】**")
            for d in res['opening_diag']:
                st.write(f"• {d}")

            if res['gap_pct'] >= 2.5 and res['intraday_pct'] < 0:
                st.warning("⚠️ **警告：開大幅跳高但盤中走黑 K！** 典型主力開高出貨訊號，切勿市價追高！")
            elif res['gap_pct'] > 0 and res['intraday_pct'] > 0:
                st.success("🟢 **多方強推格局：跳空開高且紅 K 續攻！** 買盤扎實，可依計畫分批布局。")

        # Tab: 決策結論
        with tab1:
            if res['total_score'] >= 75:
                st.success("### 🟢 積極偏多：適合進場操作")
                st.write(f"- 均線與多維度指標同步翻多，順勢作多勝率高。")
                st.write(f"- 嚴格停損價：**{res['stop_loss']:.2f} 元**。")
            elif 50 <= res['total_score'] < 75:
                st.warning("### 🟡 中性觀望：僅限小部位試單")
                st.write("- 部分指標尚未全面同步，追價勝率普通，建議部位降至 1/3 以下。")
            else:
                st.error("### 🔴 偏空避開：不建議進場")
                st.write("- 均線弱勢或大盤不穩，下檔空間未明確，現金為王。")

        # Tab: 日/月/季線矩陣
        with tab2:
            st.subheader("📏 日線・月線・季線 位階矩陣")
            st.markdown(f"**均線排列結構：** `{res['ma_alignment']}`")

            m1, m2, m3 = st.columns(3)
            m1.metric("日線 (5MA)", f"{res['ma_status']['ma5_val']:.2f}", f"{res['ma_status']['ma5_diff']:+.1f}%")
            m2.metric("月線 (20MA)", f"{res['ma_status']['ma20_val']:.2f}", f"{res['ma_status']['ma20_diff']:+.1f}%")
            m3.metric("季線 (60MA)", f"{res['ma_status']['ma60_val']:.2f}", f"{res['ma_status']['ma60_diff']:+.1f}%")

            st.caption("※ 綠/紅標籤代表當前股價高於（+）或低於（-）該均線之乖離百分比。")

        # Tab: 部位風控計算機
        with tab3:
            st.subheader("🧮 部位規模與盈虧比試算")
            col_cap, col_risk = st.columns(2)
            with col_cap:
                total_capital = st.number_input("總操作資金 (NTD)", value=1000000, step=100000)
            with col_risk:
                risk_tolerance = st.slider("單筆最大承受損失比率", min_value=0.5, max_value=3.0, value=1.0, step=0.1)

            max_risk_dollar = total_capital * (risk_tolerance / 100.0)
            loss_per_share = max(res['close'] - res['stop_loss'], 0.1)
            suggested_lots = int(max_risk_dollar // (loss_per_share * 1000))
            potential_reward = max(res['target_price'] - res['close'], 0)
            rr_ratio = potential_reward / loss_per_share if loss_per_share > 0 else 0

            b1, b2 = st.columns(2)
            b1.metric("單筆最大容許虧損", f"{int(max_risk_dollar):,} 元")
            b2.metric("建議最大進場張數", f"{suggested_lots} 張")

            b3, b4 = st.columns(2)
            b3.metric("目標獲利區 (近60日高)", f"{res['target_price']:.2f} 元")
            b4.metric("預期盈虧比 (R/R)", f"{rr_ratio:.2f} : 1")

        # Tab: 技術走勢
        with tab4:
            st.subheader("📈 收盤價與 三均線 (5MA / 20MA / 60MA) 走勢")
            chart_df = df_stock[['Close', 'MA5', 'MA20', 'MA60']].dropna().tail(60)
            st.line_chart(chart_df)
