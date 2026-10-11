import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="次日開市決策系統",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)

ACCESS_PASSWORD = st.secrets.get("PASSWORD", "invest888")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 內部決策系統")
    st.caption("請輸入通行碼以開始使用")
    pwd = st.text_input("訪問密碼", type="password")
    if st.button("登入系統", type="primary", use_container_width=True):
        if pwd == ACCESS_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("密碼錯誤，請重新輸入。")
    st.stop()

@st.cache_data(ttl=600)
def fetch_and_calc(ticker: str):
    try:
        obj = yf.Ticker(ticker)
        df = obj.history(period="6mo")
        if df.empty:
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

def analyze_all(df_stock, df_market, df_futures):
    last_mkt = df_market.iloc[-1]
    mkt_score = 0
    mkt_reasons = []
    if last_mkt['Close'] > last_mkt['MA20']:
        mkt_score += 15
        mkt_reasons.append("大盤站上月線 (MA20)")
    else:
        mkt_reasons.append("大盤跌破月線，系統性風險偏高")
    if last_mkt['MA20'] > last_mkt['MA60']:
        mkt_score += 10
        mkt_reasons.append("季線多頭架構 (MA20 > MA60)")

    fut_score = 0
    fut_reasons = []
    try:
        last_fut = df_futures.iloc[-1]
        if last_fut['Close'] > last_fut['MA5']:
            fut_score += 15
            fut_reasons.append("期貨收在 5MA 之上，短線偏多")
        else:
            fut_reasons.append("期貨破 5MA，短線動能轉弱")
        if last_fut['Close'] >= last_mkt['Close']:
            fut_score += 10
            fut_reasons.append("期貨維持正價差，市場偏樂觀")
        else:
            fut_reasons.append("期貨呈現逆價差，提防震盪")
    except Exception:
        fut_score = 12
        fut_reasons.append("期貨數據採中立評分")

    last_stk = df_stock.iloc[-1]
    prev_stk = df_stock.iloc[-2]
    stk_score = 0
    stk_reasons = []

    if last_stk['Close'] > last_stk['MA5'] and last_stk['MA5'] > last_stk['MA20']:
        stk_score += 15
        stk_reasons.append("短多排列 (收盤 > 5MA > 20MA)")
    elif last_stk['Close'] > last_stk['MA20']:
        stk_score += 8
        stk_reasons.append("守穩月線")
    else:
        stk_reasons.append("失守月線")

    vol_ratio = last_stk['Volume'] / (last_stk['Vol_MA5'] + 1e-9)
    if last_stk['Close'] > prev_stk['Close'] and vol_ratio >= 1.3:
        stk_score += 15
        stk_reasons.append(f"量增價漲 (爆量比: {vol_ratio:.1f}x)")
    elif last_stk['Close'] > prev_stk['Close']:
        stk_score += 8
        stk_reasons.append("價漲量平")
    else:
        stk_reasons.append("量價背離或跌出量")

    if last_stk['OSC'] > 0 and last_stk['OSC'] > prev_stk['OSC']:
        stk_score += 10
        stk_reasons.append("MACD 紅柱放大，攻擊動能充足")
    elif last_stk['OSC'] > 0:
        stk_score += 5
        stk_reasons.append("MACD 維持多頭")

    if 50 <= last_stk['RSI14'] <= 70:
        stk_score += 10
        stk_reasons.append(f"RSI 處攻擊區 ({last_stk['RSI14']:.1f})")
    elif last_stk['RSI14'] > 70:
        stk_score += 5
        stk_reasons.append("RSI 超買防震盪")
    else:
        stk_reasons.append(f"RSI 偏弱 ({last_stk['RSI14']:.1f})")

    stop_loss = max(last_stk['Close'] - 2 * last_stk['ATR14'], last_stk['MA20'])
    total_score = mkt_score + fut_score + stk_score

    return total_score, last_stk['Close'], stop_loss, mkt_reasons, fut_reasons, stk_reasons

st.title("📱 股期決策儀表板")
st.caption("熱門標的快速選取：")
cols = st.columns(4)
quick_picks = [("台積電", "2330.TW"), ("聯發科", "2454.TW"), ("鴻海", "2317.TW"), ("元大台灣50", "0050.TW")]

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "2330.TW"

for i, (name, code) in enumerate(quick_picks):
    if cols[i].button(name, use_container_width=True):
        st.session_state.selected_ticker = code

ticker_input = st.text_input("查詢代碼 (台股請加 .TW / .TWO)", value=st.session_state.selected_ticker)

if st.button("🔍 執行次日開市分析", type="primary", use_container_width=True):
    with st.spinner("計算行情數據中..."):
        df_stock = fetch_and_calc(ticker_input.strip())
        df_market = fetch_and_calc("^TWII")
        df_futures = fetch_and_calc("WTX=F")
        if df_futures is None:
            df_futures = df_market

    if df_stock is None or df_market is None:
        st.error("無法取得行情數據，請確認代碼是否正確。")
    else:
        total_score, close_p, stop_p, mkt_r, fut_r, stk_r = analyze_all(df_stock, df_market, df_futures)

        c1, c2 = st.columns(2)
        c1.metric("多空評分", f"{total_score} / 100")
        c2.metric("最新收盤", f"{close_p:.2f}")

        c3, c4 = st.columns(2)
        c3.metric("建議防守價", f"{stop_p:.2f}")
        risk_pct = ((close_p - stop_p) / close_p) * 100
        c4.metric("最大預期風險", f"{risk_pct:.1f}%")

        st.divider()

        tab1, tab2, tab3 = st.tabs(["🎯 決策結論", "📊 指標明細", "📈 價格走勢"])

        with tab1:
            if total_score >= 75:
                st.success("### 🟢 積極偏多：次日適合進場")
                st.write(f"- 開盤若未大幅跳空，可分批佈局。")
                st.write(f"- 停損防守價設在 **{stop_p:.2f} 元**。")
            elif 50 <= total_score < 75:
                st.warning("### 🟡 中性觀望：僅限小部位試單")
                st.write("- 部分指標尚未全面同步，追價勝率普通。")
                st.write("- 建議部位控制在 1/3 以下。")
            else:
                st.error("### 🔴 偏空避開：次日不建議進場")
                st.write("- 市場結構轉弱，風險大於潛在獲利。")
                st.write("- 建議持盈保泰，空手觀望。")

        with tab2:
            st.markdown("**【大盤狀態】**")
            for r in mkt_r:
                st.write(f"• {r}")
            st.markdown("**【期貨動能】**")
            for r in fut_r:
                st.write(f"• {r}")
            st.markdown("**【個股量價】**")
            for r in stk_r:
                st.write(f"• {r}")

        with tab3:
            st.line_chart(df_stock[['Close', 'MA20']].dropna().tail(40))
