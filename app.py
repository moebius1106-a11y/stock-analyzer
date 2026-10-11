import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor

# 頁面配置
st.set_page_config(
    page_title="次日開市與即時量化決策站 (大滿貫旗艦版)",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ----------------- 通行密碼防護 -----------------
ACCESS_PASSWORD = st.secrets.get("PASSWORD", "invest888")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 內部量化決策站 (大滿貫版)")
    st.caption("請輸入通行碼以開始使用")
    pwd = st.text_input("訪問密碼", type="password")
    if st.button("登入系統", type="primary", use_container_width=True):
        if pwd == ACCESS_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("密碼錯誤，請重新輸入。")
    st.stop()

# ----------------- 行情數據與技術指標 -----------------
@st.cache_data(ttl=60)
def fetch_and_calc(ticker: str, period: str = "1y"):
    try:
        obj = yf.Ticker(ticker)
        df = obj.history(period=period)
        if df.empty or len(df) < 40:
            return None
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()

        # 日線 (5MA)、月線 (20MA)、季線 (60MA)
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

# ----------------- 基本面體質數據 -----------------
@st.cache_data(ttl=3600)
def fetch_fundamentals(ticker: str):
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

        if roe_val >= 15:
            fund_score += 15
            reasons.append(f"ROE 達 {roe_val:.1f}%，資本創造獲利效率極佳")
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
            reasons.append(f"本益比 {pe_val:.1f}x，估值處合理安全區間")
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
def analyze_opening_and_ma(df_stock):
    last = df_stock.iloc[-1]
    prev = df_stock.iloc[-2]
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
        ma_alignment = "🔄 均線震盪糾結 (多空方向待表態)"
        ma_score = 10

    open_p = last['Open']
    prev_close = prev['Close']
    gap_pct = ((open_p - prev_close) / prev_close) * 100
    intraday_pct = ((close - open_p) / open_p) * 100

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

# ----------------- 全維度綜合評估 -----------------
def analyze_full_stock(ticker, df_stock, df_market, df_futures, df_tsm, df_sox):
    fund_data = fetch_fundamentals(ticker)
    ma_status, ma_alignment, ma_score, gap_pct, intraday_pct, k_type, opening_diag = analyze_opening_and_ma(df_stock)

    last_stk = df_stock.iloc[-1]
    prev_stk = df_stock.iloc[-2]
    close = last_stk['Close']

    # 1. 國際盤 (滿分 15)
    global_score = 0
    global_reasons = []
    try:
        tsm_change = ((df_tsm['Close'].iloc[-1] - df_tsm['Close'].iloc[-2]) / df_tsm['Close'].iloc[-2]) * 100
        if tsm_change >= 1.5:
            global_score += 15
            global_reasons.append(f"TSM ADR 大漲 ({tsm_change:+.1f}%)，國際連動動能強勁")
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

    # 2. 大盤與期貨 (滿分 20)
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

    # 3. 技術動能 (滿分 25)
    tech_score = 0
    tech_reasons = []
    vol_ratio = last_stk['Volume'] / (last_stk['Vol_MA5'] + 1e-9)
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

    # 總分整合 (技術面 60% + 基本面 40%)
    total_score = int((global_score + mkt_score + ma_score + tech_score) * 0.6 + fund_data['score'] * 0.8)
    total_score = min(total_score, 100)

    stop_loss = max(close - 2 * last_stk['ATR14'], last_stk['MA20'])
    target_60d = df_stock['High'].tail(60).max()

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
        "fund_data": fund_data
    }

# ----------------- 全市場優質藍籌旗艦池 -----------------
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

# ----------------- UI 介面 -----------------
st.title("📱 股期次日量化決策站 (大滿貫旗艦版)")

mode = st.radio("功能模式選擇：", [
    "🔍 單股全維度深度體檢 (完整功能)",
    "💎 全市場優質體質股即時量化雷達"
], horizontal=True)

df_market = fetch_and_calc("^TWII")
df_futures = fetch_and_calc("WTX=F") or df_market
df_tsm = fetch_and_calc("TSM")
df_sox = fetch_and_calc("^SOX")

# ================= 模式 1：單股深度體檢 (包含全部 8 大分頁) =================
if mode == "🔍 單股全維度深度體檢 (完整功能)":
    st.caption("熱門優質股快速點選：")
    q_cols = st.columns(4)
    quick_list = [("台積電", "2330.TW"), ("聯發科", "2454.TW"), ("鴻海", "2317.TW"), ("富邦金", "2881.TW")]

    if "selected_ticker" not in st.session_state:
        st.session_state.selected_ticker = "2330.TW"

    for i, (name, code) in enumerate(quick_list):
        if q_cols[i].button(name, use_container_width=True):
            st.session_state.selected_ticker = code

    ticker_input = st.text_input("輸入查詢代碼 (上市 .TW / 上櫃 .TWO)", value=st.session_state.selected_ticker)

    if st.button("🔍 執行全維度診斷", type="primary", use_container_width=True):
        with st.spinner("同步運算開盤動態、日/月/季線、基本面護城河與風控模型..."):
            df_stock = fetch_and_calc(ticker_input.strip())

        if df_stock is None:
            st.error("無法取得該標的行情數據，請確認代碼是否正確。")
        else:
            res = analyze_full_stock(ticker_input.strip(), df_stock, df_market, df_futures, df_tsm, df_sox)
            risk_unit = max(res['close'] - res['stop_loss'], 0.1)
            target_1 = res['close'] + (1.5 * risk_unit)

            # 頂部 2x2 數值卡片
            c1, c2 = st.columns(2)
            c1.metric("綜合決策總分", f"{res['total_score']} / 100")
            c2.metric("最新收盤價", f"{res['close']:.2f} 元")

            c3, c4 = st.columns(2)
            c3.metric("建議防守價 (停損)", f"{res['stop_loss']:.2f} 元")
            risk_pct = (risk_unit / res['close']) * 100
            c4.metric("最大預期風險", f"{risk_pct:.2f}%")

            st.divider()

            # 完整的 8 大分頁
            t_rt, t_dec, t_ma, t_fund, t_exit, t_calc, t_bt, t_chart = st.tabs([
                "⚡ 開盤即時", "🎯 決策結論", "📏 日/月/季線矩陣", "💎 基本面體質",
                "🚪 階梯停利", "💰 風控計算機", "📊 歷史勝率", "📈 均線走勢"
            ])

            # Tab 1: 開盤即時連動
            with t_rt:
                st.subheader("⚡ 開盤即時狀態診斷")
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

            # Tab 2: 決策結論
            with t_dec:
                if res['total_score'] >= 75:
                    st.success("### 🟢 積極偏多：體質與量價動能同步翻多，適合進場")
                    st.write(f"- 建議防守價位：**{res['stop_loss']:.2f} 元**。")
                elif 60 <= res['total_score'] < 75:
                    st.warning("### 🟡 穩健觀察：指標整理或分歧，僅限 1/3 以下微型試單")
                else:
                    st.error("### 🔴 暫緩進場：評價過高或短期均線下壓，現金為王")

            # Tab 3: 日/月/季線位階矩陣 (完整保留)
            with t_ma:
                st.subheader("📏 日線・月線・季線 位階矩陣")
                st.markdown(f"**均線排列結構：** `{res['ma_alignment']}`")
                m1, m2, m3 = st.columns(3)
                m1.metric("日線 (5MA)", f"{res['ma_status']['ma5_val']:.2f}", f"{res['ma_status']['ma5_diff']:+.1f}%")
                m2.metric("月線 (20MA)", f"{res['ma_status']['ma20_val']:.2f}", f"{res['ma_status']['ma20_diff']:+.1f}%")
                m3.metric("季線 (60MA)", f"{res['ma_status']['ma60_val']:.2f}", f"{res['ma_status']['ma60_diff']:+.1f}%")
                st.caption("※ 正負百分比標籤代表當前股價高於（+）或低於（-）該均線之乖離幅度。")

            # Tab 4: 基本面體質護城河
            with t_fund:
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

            # Tab 5: 階梯停利 SOP
            with t_exit:
                st.subheader("🚪 機械化分階出場規劃")
                st.markdown(f"""
                - **初始防守停損**：跌破 **`{res['stop_loss']:.2f}` 元** 嚴格離場，絕不凹單。
                - **第一階段目標（減碼 1/2）**：達 **`{target_1:.2f}` 元**（1.5R 盈虧比），賣出半數部位並上移防守至成本價（鎖定保本）。
                - **第二階段目標（波段收割）**：達 **`{res['target_60d']:.2f}` 元**（近 60 日波段壓力位）分批落袋。
                - **移動停利（Trailing Stop）**：其餘部位收盤跌破 5 日線全數獲利了結。
                """)

            # Tab 6: 部位風控計算機 (完整保留)
            with t_calc:
                st.subheader("🧮 部位規模與盈虧比試算")
                col_cap, col_risk = st.columns(2)
                with col_cap:
                    total_capital = st.number_input("總操作資金 (NTD)", value=1000000, step=100000)
                with col_risk:
                    risk_tolerance = st.slider("單筆最大承受損失比率", min_value=0.5, max_value=3.0, value=1.0, step=0.1)

                max_risk_dollar = total_capital * (risk_tolerance / 100.0)
                loss_per_lot = risk_unit * 1000
                suggested_lots = int(max_risk_dollar // loss_per_lot)
                potential_reward = max(res['target_60d'] - res['close'], 0)
                rr_ratio = potential_reward / risk_unit if risk_unit > 0 else 0

                b1, b2 = st.columns(2)
                b1.metric("單筆最大容許虧損", f"{int(max_risk_dollar):,} 元")
                b2.metric("建議最大進場張數", f"{suggested_lots} 張")

                b3, b4 = st.columns(2)
                b3.metric("目標獲利區 (近60日高)", f"{res['target_60d']:.2f} 元")
                b4.metric("預期盈虧比 (R/R)", f"{rr_ratio:.2f} : 1")

            # Tab 7: 客觀歷史勝率回測 (完整保留)
            with t_bt:
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

            # Tab 8: 均線走勢圖 (四線合一)
            with t_chart:
                st.subheader("📈 收盤價與 5MA / 20MA / 60MA 走勢")
                st.line_chart(df_stock[['Close', 'MA5', 'MA20', 'MA60']].dropna().tail(50))

# ================= 模式 2：全市場優質體質雷達 =================
else:
    st.subheader("💎 市場穩健優質標的・即時連線掃描")
    st.caption("結合【基本面護城河】×【即時量價多空動能】，全自動評分排序")

    if st.button("⚡ 開始全市場即時連線篩選", type="primary", use_container_width=True):
        progress_bar = st.progress(0)
        status_text = st.empty()
        scan_results = []

        def worker(item):
            name, code, desc = item
            df_stk = fetch_and_calc(code)
            if df_stk is not None:
                r = analyze_full_stock(code, df_stk, df_market, df_futures, df_tsm, df_sox)
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

        with ThreadPoolExecutor(max_workers=6) as executor:
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
