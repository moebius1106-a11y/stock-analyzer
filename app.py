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
    ("雙鴻", "3324.TW", "水冷散熱關鍵大廠"),
    ("大立光", "3008.TW", "光學鏡頭專利領先者"),
    ("聯電", "2303.TW", "成熟製程晶圓代工"),
    ("元大台灣50", "0050.TW", "台股核心藍籌組合")
]

# ----------------- 手機 UI 介面 -----------------
st.title("📱 股期次日量化決策站 (旗艦專業版)")

mode = st.radio("功能模式選擇：", [
    "💎 全市場優質體質股即時量化雷達",
    "🔍 單股全維度深度體檢"
], horizontal=True)

df_market = fetch_and_calc("^TWII")
df_futures = fetch_and_calc("WTX=F") or df_market
df_tsm = fetch_and_calc("TSM")

# ================= 模式 1：優質體質即時雷達 =================
if mode == "💎 全市場優質體質股即時量化雷達":
    st.subheader("💎 市場穩健優質標的・即時連線掃描")
    st.caption("結合【基本面護城河 (ROE/營利率/PE)】×【即時量價多空動能】，全自動評分排序")

    if st.button("⚡ 開始全市場即時連線篩選", type="primary", use_container_width=True):
        progress_bar = st.progress(0)
        status_text = st.empty()
        scan_results = []

        def worker(item):
            name, code, desc = item
            df_stk = fetch_and_calc(code)
            if df_stk is not None:
                res = analyze_full_stock(code, df_stk, df_market, df_futures, df_tsm)
                return {
                    "名稱": name,
                    "代碼": code,
                    "產業地位": desc,
                    "總評分": res['total_score'],
                    "基本面評分": res['fund_score'],
                    "技術面評分": res['tech_score'],
                    "現價": res['close'],
                    "建議防守": res['stop_loss'],
                    "ROE": res['fund_data']['roe'],
                    "本益比": res['fund_data']['pe']
                }
            return None

        with ThreadPoolExecutor(max_workers=6) as executor:
            total_items = len(MARKET_QUALITY_UNIVERSE)
            futures = [executor.submit(worker, item) for item in MARKET_QUALITY_UNIVERSE]
            for idx, f in enumerate(futures):
                status_text.text(f"連線更新中 ({idx+1}/{total_items})...")
                res = f.result()
                if res:
                    scan_results.append(res)
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

# ================= 模式 2：單股深度體檢 =================
else:
    st.caption("熱門優質股快速點選：")
    q_cols = st.columns(4)
    quick_list = [("台積電", "2330.TW"), ("聯發科", "2454.TW"), ("鴻海", "2317.TW"), ("富邦金", "2881.TW")]

    if "selected_ticker" not in st.session_state:
        st.session_state.selected_ticker = "2330.TW"

    for i, (name, code) in enumerate(quick_list):
        if q_cols[i].button(name, use_container_width=True):
            st.session_state.selected_ticker = code

    ticker_input = st.text_input("輸入查詢代碼 (上市 .TW / 上櫃 .TWO)", value=st.session_state.selected_ticker)

    if st.button("🔍 執行體質與開市全維度診斷", type="primary", use_container_width=True):
        with st.spinner("同步運算基本面護城河、量價動能與均線矩陣..."):
            df_stock = fetch_and_calc(ticker_input.strip())

        if df_stock is None:
            st.error("無法取得該標的行情數據，請確認代碼是否正確。")
        else:
            res = analyze_full_stock(ticker_input.strip(), df_stock, df_market, df_futures, df_tsm)
            risk_unit = max(res['close'] - res['stop_loss'], 0.1)
            target_1 = res['close'] + (1.5 * risk_unit)

            c1, c2 = st.columns(2)
            c1.metric("綜合決策總分", f"{res['total_score']} / 100")
            c2.metric("最新收盤價", f"{res['close']:.2f} 元")

            c3, c4 = st.columns(2)
            c3.metric("建議停損防守", f"{res['stop_loss']:.2f} 元")
            c4.metric("單股預期風險", f"{((risk_unit / res['close']) * 100):.2f}%")

            st.divider()

            t_dec, t_fund, t_exit, t_chart = st.tabs([
                "🎯 決策結論", "💎 基本面體質診斷", "🚪 階梯停利 SOP", "📈 均線價格走勢"
            ])

            with t_dec:
                if res['total_score'] >= 75:
                    st.success("### 🟢 優質偏多：具基本面保護且動能充沛，適合進場")
                    st.write("企業體質穩健且技術指標同步翻多，順勢作多兼具安全邊際。")
                elif 60 <= res['total_score'] < 75:
                    st.warning("### 🟡 穩健觀察：體質優良但短期量價整理，小部位試單")
                else:
                    st.error("### 🔴 暫緩進場：評價過高或短期破線走弱，維持空手")

            with t_fund:
                st.subheader("💎 企業基本面體質護城河")
                f_data = res['fund_data']
                f1, f2 = st.columns(2)
                f1.metric("ROE 股東權益報酬率", f"{f_data['roe']:.1f}%")
                f2.metric("營業利益率", f"{f_data['op_margin']:.1f}%")

                f3, f4 = st.columns(2)
                f3.metric("本益比 (Trailing P/E)", f"{f_data['pe']:.1f}x")
                f4.metric("負債比率 (D/E)", f"{f_data['debt_ratio']:.1f}%")

                st.write("---")
                st.markdown("**【體質診斷重點】**")
                for r in f_data['reasons']:
                    st.write(f"• {r}")

            with t_exit:
                st.subheader("🚪 機械化分階出場規劃")
                st.markdown(f"""
                - **初始停損防守**：跌破 **`{res['stop_loss']:.2f}` 元** 嚴格退場。
                - **第一階段目標（減碼 1/2）**：達 **`{target_1:.2f}` 元**（1.5R 盈虧比），賣出半數部位並上移停損至成本價（鎖定保本）。
                - **第二階段目標（波段收割）**：達 **`{res['target_60d']:.2f}` 元**（60 日高點壓力位）分批離場。
                - **移動停利（Trailing Stop）**：其餘部位跌破 5MA 即全數結利。
                """)

            with t_chart:
                st.line_chart(df_stock[['Close', 'MA5', 'MA20', 'MA60']].dropna().tail(50))
