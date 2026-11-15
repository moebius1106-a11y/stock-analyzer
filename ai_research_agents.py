# -*- coding: utf-8 -*-
"""
ai_research_agents.py
股期決策旗艦站 V9.9 — 八大機構級 AI 研究員與量化風控引擎模組
包含：
1. 交易點子產生器 (Trade Idea Generator)
2. 自動化技術分析師 (Automated Technical Analyst - 日線 & 週線結構拆解)
3. 新聞轉交易研究 (News-to-Trade Researcher)
4. 交易策略回測分析師 (Trading Strategy Backtest Analyst)
5. 投資組合風險管理 (Portfolio Risk Manager - 集中度與 -20% 壓力測試)
6. 交易日誌分析師 (Trading Journal Analyst - 近20筆行為偏誤復盤)
7. 財報與基本面研究員 (Financial Statement & Fundamental Researcher)
8. 投資論點反方審查 (Investment Thesis Devil's Advocate)

設計原則：
- 確定性算術隔離：所有均線、週線指標、回測獲利因子、投組 -20% 壓力測試與日誌統計一律由 Python 精確計算。
- 單一 Prompt 路由器與按需觸發：僅在使用者點擊按鈕時呼叫 Gemini API，零背景記憶體負擔。
- 資訊安全：API Key 僅透過 HTTP Header `x-goog-api-key` 傳送，絕不暴露於 URL 或寫入設定檔。
"""

import json
import logging
import math
import os
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import requests
import streamlit as st

TAIPEI_TZ = timezone(timedelta(hours=8))

GEMINI_PRIMARY_MODEL = "gemini-2.5-flash"
GEMINI_SECONDARY_MODEL = "gemini-2.0-flash"


def _safe_float(val, default=0.0):
    try:
        if val is None:
            return default
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
            val = val.strip().replace(",", "")
            if val in ("", "-", "N/A", "nan", "None", "_", "--"):
                return default
        res = float(val)
        return res if math.isfinite(res) else default
    except (ValueError, TypeError, IndexError, OverflowError):
        return default


# ==============================================================================
# 一、 八大研究員角色規格與嚴格防幻覺提示詞庫 (Prompt Router Registry)
# ==============================================================================
AI_RESEARCH_AGENT_SPECS = {
    "trade_idea": {
        "icon": "🎯",
        "title": "1. 交易點子產生器",
        "subtitle": "先列出研究情境，不急著下單",
        "system_role": (
            "你是一位嚴謹的機構級買方（Buy-Side）交易策略師。"
            "請根據提供的【標的、日期與客觀行情數據】，提出 5 個值得進一步研究的交易情境（多空與區間皆可涵蓋）。\n"
            "【嚴格紀律】：\n"
            "1. 每個情境必須明確列出：觸發條件、參考進場區間、目標區間、失效條件（停損界線）與風險報酬比計算，並解釋技術面與基本面支持理由。\n"
            "2. 資料不足時必須在開頭先列出『資料缺口清單』，嚴禁捏造價格、即時行情或真實勝率。\n"
            "3. 明確區分『已確認事實』、『模型假設』與『待驗證項目』，結尾標註僅供研究輔助、不保證獲利。"
        ),
    },
    "tech_analyst": {
        "icon": "📐",
        "title": "2. 自動化技術分析師",
        "subtitle": "從日線與週線，拆解價格結構",
        "system_role": (
            "你是一位專精於多時間框架（Multi-Timeframe）的資深技術分析師。"
            "請根據提供的【日線與週線 OHLCV 統計數據】，拆解該標的之價格結構。\n"
            "【嚴格紀律】：\n"
            "1. 依序整理：關鍵支撐位、上檔壓力位、趨勢線結構、日/週移動平均線排列與動能指標（MACD / RSI / ATR）。\n"
            "2. 分別建立『偏多情境』、『盤整情境』與『偏空情境』，清楚說明各情境的成立條件、失效條件與盤中/收盤需要追蹤的確認訊號。\n"
            "3. 必須展示具體判斷依據；若週線或某項指標標示為 N/A（樣本不足），必須直說無法計算，絕不把情境分析當成確定性預測。"
        ),
    },
    "news_researcher": {
        "icon": "📰",
        "title": "3. 新聞轉交易研究",
        "subtitle": "先讀懂事件，再看可能影響",
        "system_role": (
            "你是一位事件驅動（Event-Driven）交易研究員。"
            "請整理使用者提供的【公司／產業新聞內容或標題清單】。\n"
            "【嚴格紀律】：\n"
            "1. 逐項列出事件日期、消息來源與『已確認事實』。\n"
            "2. 分析可能的『短期（1~5日）』與『長期（1~3季）』基本面與籌碼影響，明確區分『市場已知（Price-in）資訊』與『新增邊際資訊』。\n"
            "3. 條列『利多催化劑』、『利空風險』以及『可能推翻目前判斷的後續追蹤事件』。\n"
            "4. 嚴禁在缺乏依據時臆測具體漲跌幅百分比；若原文資訊不足以判斷，請直說並列出需要補充查證的原文細節。"
        ),
    },
    "backtest_analyst": {
        "icon": "🧪",
        "title": "4. 交易策略回測分析師",
        "subtitle": "先測規則，再檢查結果可信度",
        "system_role": (
            "你是一位量化策略驗證與統計審計師。"
            "請根據系統提供的【策略規則、進出場定義、交易成本/滑價假設與 Python 回測績效數據】進行嚴格可信度審查。\n"
            "【嚴格紀律】：\n"
            "1. 先確認進出場時序（隔日開盤買進避免當日收盤前視偏誤）、部位假設與交易成本（手續費、證交稅、滑價）是否合理。\n"
            "2. 解讀已算出的勝率、獲利因子（Profit Factor）、最大回撤（MDD）、交易次數與平均淨報酬，絕不編造或篡改回測數字。\n"
            "3. 深入檢查三大量化陷阱：『前視偏誤（Look-ahead Bias）』、『過度擬合（Overfitting）』與『樣本外（Out-of-Sample）衰減風險』，並提出具體改善驗證步驟。"
        ),
    },
    "portfolio_risk": {
        "icon": "🛡️",
        "title": "5. 投資組合風險管理",
        "subtitle": "找出集中風險與隱藏關聯",
        "system_role": (
            "你是一位機構風控長（CRO）。"
            "請根據系統算出的【投資組合持倉明細、現金比例、集中度指標與大盤下跌 20% 壓力測試結果】進行全面風險審計。\n"
            "【嚴格紀律】：\n"
            "1. 檢查產業板塊、地理區域、計價幣別（台幣/美元）及單一標的集中度，點出隱藏的共同風險因子（如半導體供應鏈共振、美債殖利率或匯率風險）。\n"
            "2. 若需計算精確跨資產相關性矩陣，明確告知所需歷史期間與取樣頻率。\n"
            "3. 針對『市場下跌 20% 壓力測試』結果說明模型假設限制（例如 Beta 非線性放大、流動性折價），並比較 3 種再平衡（Rebalancing）方案的風險、交易成本與報酬取捨，絕不保證避開虧損。"
        ),
    },
    "trading_journal": {
        "icon": "📓",
        "title": "6. 交易日誌分析師",
        "subtitle": "用紀錄找出反覆出現的問題",
        "system_role": (
            "你是一位交易心理學與行為金融學教練。"
            "請檢視使用者提供的【最近交易紀錄（最多 20 筆）與統計摘要】。\n"
            "【嚴格紀律】：\n"
            "1. 找出重複發生的操作錯誤（如凹單攤平、未設停損、逆勢摸底）、未遵守既定規則的情況、過早出場錯失波段機會，以及潛在行為偏誤（處置效應、過度自信、報復性下單）。\n"
            "2. 必須嚴格把『交易紀錄數據能直接證明的事』與『你的行為心理推測』分開條列。\n"
            "3. 最後提出 3 條『具體可執行、可量化追蹤』的個人交易紀律規則，並附上每日/每週檢核方式。若樣本數不足 20 筆，必須明確提醒樣本代表性受限，絕不宣稱套用規則一定能提高獲利。"
        ),
    },
    "fundamental_researcher": {
        "icon": "📑",
        "title": "7. 財報與基本面研究員",
        "subtitle": "把財報變成研究清單",
        "system_role": (
            "你是一位資深產業基本面研究員。"
            "請根據系統彙整的【公司財報關鍵數據、三率變化、現金流、負債結構與法說會/盈餘驚奇度紀錄】建立深度研究清單。\n"
            "【嚴格紀律】：\n"
            "1. 系統性拆解：營收成長動能、毛利率/營益率/淨利率趨勢、自由現金流與營業現金流品質、負債與資本結構變化。\n"
            "2. 列出核心成長來源、需剔除的一次性業外項目、潛在財務/營運風險，以及 5 個『法說會追問管理層的犀利問題』。\n"
            "3. 每個重要數字必須註明資料來源與期間；若涉及估值，明確列出假設前提、同業可比性限制與敏感度；遇到標示『未揭露/N/A』的欄位，嚴禁自行腦補或推估缺失財務數據。"
        ),
    },
    "contrarian_review": {
        "icon": "😈",
        "title": "8. 投資論點反方審查",
        "subtitle": "專門找出你可能看錯的地方",
        "system_role": (
            "你是一位專門負責挑戰投資委員會（IC）提案的反方研究員（Devil's Advocate）。"
            "請針對使用者貼上的【投資論點與當前標的數據】進行冷靜、客觀的壓力測試審查。\n"
            "【嚴格紀律】：\n"
            "1. 逐一檢驗該論點的隱含前提、支持證據強度、估值安全邊際假設，以及投資人最可能忽略的結構性風險。\n"
            "2. 列出『最有力的 3~4 個反對理由』、『市場對同一現象的替代解釋』，以及『哪些具體新資訊出現會讓原論點徹底失效』。\n"
            "3. 嚴禁為了反對而無理捏造問題；若使用者提供的論點缺乏關鍵前提（如持有週期、停損界線、估值基準），請先列出需要釐清的問題。\n"
            "4. 最後整理一份結構化『追蹤清單』：包含要觀察的指標、查證來源、建議更新頻率與重新評估觸發條件。"
        ),
    },
}


# ==============================================================================
# 二、 確定性量化計算輔助引擎 (週線重採樣 / 強化回測 / 投組壓力測試 / 日誌統計)
# ==============================================================================
def compute_weekly_technicals(df_daily: pd.DataFrame) -> dict:
    """將日線 OHLCV 安全重採樣為週線 (W-FRI)，計算週線均線與 RSI14（不引入未來資料）"""
    if df_daily is None or df_daily.empty or len(df_daily) < 10:
        return {"has_weekly": False, "reason": "日線樣本不足，無法建立週線結構"}

    try:
        df = df_daily.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        agg_dict = {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }
        df_w = df.resample("W-FRI").agg(agg_dict).dropna(subset=["Close"])
        if df_w.empty or len(df_w) < 5:
            return {"has_weekly": False, "reason": "週線 K 棒不足 5 週"}

        df_w["W_MA5"] = df_w["Close"].rolling(5, min_periods=5).mean()
        df_w["W_MA20"] = df_w["Close"].rolling(20, min_periods=20).mean()

        delta = df_w["Close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_g = gain.ewm(alpha=1 / 14.0, adjust=False, min_periods=14).mean()
        avg_l = loss.ewm(alpha=1 / 14.0, adjust=False, min_periods=14).mean()
        rs = avg_g / (avg_l + 1e-9)
        df_w["W_RSI14"] = 100.0 - (100.0 / (1.0 + rs))

        last_w = df_w.iloc[-1]
        w_close = _safe_float(last_w["Close"])
        has_w_ma5 = pd.notna(last_w["W_MA5"])
        has_w_ma20 = pd.notna(last_w["W_MA20"])
        has_w_rsi = pd.notna(last_w["W_RSI14"])

        recent_12w = df_w.tail(12)
        w_high_12 = _safe_float(recent_12w["High"].max(), w_close)
        w_low_12 = _safe_float(recent_12w["Low"].min(), w_close)

        return {
            "has_weekly": True,
            "weekly_bars": len(df_w),
            "w_close": round(w_close, 2),
            "w_ma5": round(_safe_float(last_w["W_MA5"]), 2) if has_w_ma5 else "N/A (未滿5週)",
            "w_ma20": round(_safe_float(last_w["W_MA20"]), 2) if has_w_ma20 else "N/A (未滿20週)",
            "w_rsi14": round(_safe_float(last_w["W_RSI14"]), 1) if has_w_rsi else "N/A (未滿14週)",
            "w_high_12w": round(w_high_12, 2),
            "w_low_12w": round(w_low_12, 2),
            "w_trend": (
                "週線站上 20W 均線 (中長線多方)"
                if (has_w_ma20 and w_close >= _safe_float(last_w["W_MA20"]))
                else ("週線跌破 20W 均線 (中長線防守)" if has_w_ma20 else "週線 20W 暖機中 (N/A)")
            ),
        }
    except Exception as e:
        logging.warning(f"compute_weekly_technicals 計算異常: {e}")
        return {"has_weekly": False, "reason": f"週線計算異常: {str(e)}"}


def compute_enhanced_backtest_metrics(df_stock: pd.DataFrame, market_type: str = "tw", hold_days: int = 5) -> dict:
    """
    無前視偏誤（No Look-Ahead Bias）之可重現策略回測引擎：
    - 訊號於第 i 日收盤確認後，嚴格於第 i+1 日開盤進場，持有 hold_days 日後於第 i+1+hold_days 日開盤出場。
    - 計算勝率、獲利因子 (Profit Factor)、平均淨報酬、最大回撤 (MDD)、交易次數與樣本充足度。
    """
    if df_stock is None or len(df_stock) < 60:
        return {"has_data": False, "reason": "歷史日線樣本不足 60 筆，停止回測以避免統計失真"}

    required_cols = {"Open", "Close", "Volume"}
    if not required_cols.issubset(set(df_stock.columns)):
        return {"has_data": False, "reason": "缺少必要 OHLCV 欄位"}

    df = df_stock.copy()
    if "MA20" not in df.columns:
        df["MA20"] = df["Close"].rolling(20, min_periods=20).mean()
    if "Vol_MA5" not in df.columns:
        df["Vol_MA5"] = df["Volume"].rolling(5, min_periods=5).mean()
    if "OSC" not in df.columns:
        ema12 = df["Close"].ewm(span=12, adjust=False, min_periods=12).mean()
        ema26 = df["Close"].ewm(span=26, adjust=False, min_periods=26).mean()
        dif = ema12 - ema26
        macd = dif.ewm(span=9, adjust=False, min_periods=9).mean()
        df["OSC"] = dif - macd

    signals = (
        df["MA20"].notna()
        & df["Vol_MA5"].notna()
        & df["OSC"].notna()
        & (df["Close"] > df["MA20"])
        & (df["Close"] > df["Close"].shift(1))
        & (df["Volume"] > df["Vol_MA5"])
        & (df["OSC"] > 0)
    )

    if market_type == "us":
        cost_rate = 0.0010  # 美股雙邊滑價與手續費假設 0.10%
        cost_desc = "美股雙邊摩擦成本 0.10%"
    elif market_type == "futures":
        cost_rate = 0.0004  # 期貨交易稅與滑價假設 0.04%
        cost_desc = "台指期雙邊稅費與滑價 0.04%"
    else:
        cost_rate = 0.0045  # 台股證交稅 0.30% + 雙邊手續費與滑價 0.15%
        cost_desc = "台股雙邊證交稅與手續費滑價 0.45%"

    n_bars = len(df)
    trade_returns = []
    i = 0
    step_span = hold_days + 1

    while i < n_bars - step_span:
        if signals.iloc[i]:
            entry_p = _safe_float(df["Open"].iloc[i + 1])
            if entry_p <= 0:
                entry_p = _safe_float(df["Close"].iloc[i + 1])
            exit_p = _safe_float(df["Open"].iloc[i + step_span])
            if exit_p <= 0:
                exit_p = _safe_float(df["Close"].iloc[i + step_span])

            if entry_p > 0 and exit_p > 0:
                net_ret_pct = ((exit_p - entry_p) / entry_p - cost_rate) * 100.0
                trade_returns.append(net_ret_pct)
                i += step_span
                continue
        i += 1

    if not trade_returns:
        return {"has_data": False, "reason": "回測期間內無符合條件之進場訊號（0 筆交易）"}

    wins = [r for r in trade_returns if r > 0]
    losses = [r for r in trade_returns if r <= 0]
    gross_profit = sum(wins) if wins else 0.0
    gross_loss = abs(sum(losses)) if losses else 0.0
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 1e-6 else (99.0 if gross_profit > 0 else 0.0)

    win_rate = (len(wins) / len(trade_returns)) * 100.0
    avg_ret = float(np.mean(trade_returns))
    worst_loss = float(min(trade_returns))
    best_win = float(max(trade_returns))

    equity = [100.0]
    for r in trade_returns:
        equity.append(equity[-1] * (1.0 + r / 100.0))
    peak = equity[0]
    mdd = 0.0
    for val in equity:
        if val > peak:
            peak = val
        dd = (peak - val) / peak * 100.0
        if dd > mdd:
            mdd = dd

    start_dt = str(df.index[0])[:10]
    end_dt = str(df.index[-1])[:10]

    return {
        "has_data": True,
        "period": f"{start_dt} ~ {end_dt}",
        "rule_desc": f"日線站上 MA20 + 價漲量增 (>5日均量) + MACD紅柱 > 0，隔日開盤買進、持有 {hold_days} 個交易日開盤平倉",
        "cost_assumption": cost_desc,
        "trade_count": len(trade_returns),
        "win_rate_pct": round(win_rate, 1),
        "profit_factor": profit_factor,
        "avg_return_pct": round(avg_ret, 2),
        "max_drawdown_pct": round(mdd, 2),
        "best_trade_pct": round(best_win, 2),
        "worst_trade_pct": round(worst_loss, 2),
        "sample_warning": (
            "⚠️ 交易次數少於 15 次，統計顯著性不足，嚴防過度擬合。"
            if len(trade_returns) < 15
            else "✅ 樣本數達基礎門檻（仍須進行樣本外與跨多空循環驗證）。"
        ),
    }


def run_portfolio_stress_test(holdings_df: pd.DataFrame, cash_ntd: float = 0.0, usd_twd: float = 32.0) -> dict:
    """
    投資組合集中度與大盤下跌 20% 壓力測試 (確定性算術計算)
    holdings_df 欄位：代碼, 名稱, 市場(TW/US), 產業, 市值(原幣), Beta
    """
    cash_val = max(0.0, _safe_float(cash_ntd, 0.0))
    fx = _safe_float(usd_twd, 32.0)
    if fx <= 0:
        fx = 32.0

    rows = []
    if holdings_df is not None and not holdings_df.empty:
        for _, r in holdings_df.iterrows():
            sym = str(r.get("代碼", "")).strip().upper()
            raw_mv = _safe_float(r.get("市值(原幣)", 0.0))
            if not sym or raw_mv <= 0:
                continue
            mkt = str(r.get("市場(TW/US)", "TW")).strip().upper()
            sector = str(r.get("產業", "未分類")).strip() or "未分類"
            beta = _safe_float(r.get("Beta", 1.0), 1.0)
            beta = max(0.1, min(beta, 3.5))
            mv_ntd = raw_mv * fx if mkt == "US" else raw_mv
            rows.append({
                "symbol": sym,
                "name": str(r.get("名稱", sym)).strip() or sym,
                "market": mkt,
                "sector": sector,
                "mv_ntd": mv_ntd,
                "beta": beta,
            })

    invested_ntd = sum(x["mv_ntd"] for x in rows)
    total_ntd = invested_ntd + cash_val
    if total_ntd <= 0:
        return {"has_data": False, "reason": "投資組合總資產為 0，請先輸入持倉市值或現金水位。"}

    cash_pct = (cash_val / total_ntd) * 100.0
    invested_pct = (invested_ntd / total_ntd) * 100.0

    sector_map = {}
    mkt_map = {"TW": 0.0, "US": 0.0}
    weighted_beta_sum = 0.0
    max_single_weight = 0.0
    max_single_sym = "無"

    for x in rows:
        w = (x["mv_ntd"] / total_ntd) * 100.0
        x["weight_pct"] = round(w, 1)
        if w > max_single_weight:
            max_single_weight = w
            max_single_sym = f"{x['name']} ({x['symbol']})"
        sector_map[x["sector"]] = sector_map.get(x["sector"], 0.0) + w
        mkt_key = "US" if x["market"] == "US" else "TW"
        mkt_map[mkt_key] += w
        weighted_beta_sum += (x["mv_ntd"] / total_ntd) * x["beta"]

    # 大盤下跌 -20% 壓力測試（Beta 加權線性估算，現金假設波動為 0）
    stress_drop_pct = 20.0 * weighted_beta_sum
    stress_loss_ntd = total_ntd * (stress_drop_pct / 100.0)
    post_stress_ntd = max(0.0, total_ntd - stress_loss_ntd)

    top_sector = max(sector_map.items(), key=lambda kv: kv[1]) if sector_map else ("無", 0.0)

    alerts = []
    if max_single_weight > 30.0:
        alerts.append(f"⚠️ 單一標的集中度過高：{max_single_sym} 佔總資產 {max_single_weight:.1f}%（超過 30% 警戒線）")
    if top_sector[1] > 50.0:
        alerts.append(f"⚠️ 單一產業過度集中：【{top_sector[0]}】佔總資產 {top_sector[1]:.1f}%（超過 50% 系統風險線）")
    if cash_pct < 15.0:
        alerts.append(f"⚠️ 防禦現金水位偏低：目前僅 {cash_pct:.1f}%，大盤劇烈回檔時缺乏加碼與緩衝空間")
    if not alerts:
        alerts.append("✅ 基礎分散度符合一般風控門檻（仍需留意極端系統性行情下跨資產相關性趨近 1 的風險）")

    return {
        "has_data": True,
        "total_ntd": round(total_ntd, 0),
        "invested_ntd": round(invested_ntd, 0),
        "cash_ntd": round(cash_val, 0),
        "cash_pct": round(cash_pct, 1),
        "invested_pct": round(invested_pct, 1),
        "portfolio_beta": round(weighted_beta_sum, 2),
        "max_single_holding": f"{max_single_sym} ({max_single_weight:.1f}%)",
        "top_sector": f"{top_sector[0]} ({top_sector[1]:.1f}%)",
        "currency_split": f"台幣資產 {mkt_map['TW'] + cash_pct:.1f}% ｜ 美元資產 {mkt_map['US']:.1f}%",
        "stress_test_20pct": {
            "assumed_market_drop": "-20.0%",
            "estimated_portfolio_drop_pct": round(-stress_drop_pct, 2),
            "estimated_loss_ntd": round(stress_loss_ntd, 0),
            "remaining_equity_ntd": round(post_stress_ntd, 0),
            "model_limitation": "線性 Beta 模型未計入流動性折價、個股黑天鵝跳空或匯率劇烈波動，實際極端跌幅可能大於估算值。",
        },
        "risk_alerts": alerts,
        "holdings_breakdown": rows,
    }


def analyze_trading_journal_stats(journal_df: pd.DataFrame) -> dict:
    """分析最近 20 筆交易日誌之客觀統計數據"""
    if journal_df is None or journal_df.empty:
        return {"has_data": False, "reason": "尚未輸入任何交易紀錄"}

    valid_rows = []
    for _, r in journal_df.iterrows():
        sym = str(r.get("標的代碼", "")).strip().upper()
        if not sym:
            continue
        pnl = _safe_float(r.get("淨損益(元)", 0.0))
        obeyed = str(r.get("是否遵守紀律", "是")).strip()
        reason = str(r.get("進出場理由", "")).strip()
        direction = str(r.get("方向", "做多")).strip()
        dt_str = str(r.get("交易日期", "")).strip()
        valid_rows.append({
            "date": dt_str,
            "symbol": sym,
            "direction": direction,
            "pnl": pnl,
            "obeyed": obeyed,
            "reason": reason,
        })

    recent_20 = valid_rows[-20:]
    n = len(recent_20)
    if n == 0:
        return {"has_data": False, "reason": "有效交易筆數為 0"}

    wins = [x["pnl"] for x in recent_20 if x["pnl"] > 0]
    losses = [x["pnl"] for x in recent_20 if x["pnl"] < 0]
    total_pnl = sum(x["pnl"] for x in recent_20)
    win_rate = (len(wins) / n) * 100.0
    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(np.mean(losses)) if losses else 0.0
    payoff_ratio = round(avg_win / abs(avg_loss), 2) if abs(avg_loss) > 1e-6 else 0.0

    rule_breaks = [x for x in recent_20 if x["obeyed"] in ("否", "N", "No", "違規")]
    rule_break_pnl = sum(x["pnl"] for x in rule_breaks)

    return {
        "has_data": True,
        "sample_count": n,
        "sample_warning": (
            f"⚠️ 目前僅有 {n} 筆交易紀錄（未滿 20 筆基準），統計結論代表性有限。"
            if n < 20
            else "✅ 已達最近 20 筆完整復盤樣本門檻。"
        ),
        "total_net_pnl": round(total_pnl, 0),
        "win_rate_pct": round(win_rate, 1),
        "avg_win": round(avg_win, 0),
        "avg_loss": round(avg_loss, 0),
        "payoff_ratio": payoff_ratio,
        "rule_break_count": len(rule_breaks),
        "rule_break_pnl": round(rule_break_pnl, 0),
        "trades_list": recent_20,
    }


# ==============================================================================
# 三、 單一統一 Gemini Prompt 路由器 (安全 Header + 30分鐘快取 + 降級保護)
# ==============================================================================
@st.cache_data(ttl=86400, show_spinner=False)
def _discover_modern_gemini_models(api_key: str) -> list:
    if not api_key:
        return []
    url = "https://generativelanguage.googleapis.com/v1beta/models"
    headers = {"x-goog-api-key": api_key}
    try:
        resp = requests.get(url, headers=headers, timeout=(2.5, 4.0))
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            valid = []
            for m in models:
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    name = m.get("name", "").replace("models/", "").strip()
                    if name and not any(old in name.lower() for old in ["1.5", "1.0", "gemini-pro"]):
                        valid.append(name)
            flashes = [x for x in valid if "flash" in x.lower()]
            pros = [x for x in valid if "pro" in x.lower() and x not in flashes]
            return flashes + pros
    except Exception as e:
        logging.warning(f"ai_research_agents ListModels 異常: {e}")
    return []


@st.cache_data(ttl=1800, show_spinner=False)
def run_gemini_research_agent(
    api_key: str,
    model_name: str,
    agent_key: str,
    context_json_str: str,
    user_extra_input: str = "",
):
    """
    統一 AI 研究員執行路由器：
    - 使用 x-goog-api-key 安全 HTTP Header 傳輸金鑰
    - 主模型 gemini-2.5-flash，備援降級 gemini-2.0-flash
    - 嚴格隔離確定性數據，禁止 AI 篡改 Python 算出的客觀指標
    """
    if not api_key:
        return False, "⚠️ 尚未設定 Gemini API Key。請於頁面頂部「⚙️ 個人風控本金與偏好設定」填入金鑰，或於 Streamlit Secrets 配置 `GEMINI_API_KEY`。"

    spec = AI_RESEARCH_AGENT_SPECS.get(agent_key)
    if not spec:
        return False, f"⚠️ 未知的研究員類型：{agent_key}"

    target_model = (
        str(model_name).replace("models/", "").strip()
        if model_name and "自動" not in str(model_name)
        else GEMINI_PRIMARY_MODEL
    )
    if any(old in target_model.lower() for old in ["1.5", "1.0", "gemini-pro"]):
        target_model = GEMINI_PRIMARY_MODEL

    full_prompt = (
        f"【系統角色與任務規範】\n{spec['system_role']}\n\n"
        f"【系統已計算之客觀結構化事實數據 (JSON)】\n{context_json_str}\n\n"
    )
    if user_extra_input and user_extra_input.strip():
        full_prompt += f"【使用者補充輸入與研究問題】\n{user_extra_input.strip()}\n\n"

    full_prompt += "請使用繁體中文（台灣金融慣用語），以條列清晰的 Markdown 格式輸出完整研究分析報告。"

    discovered = _discover_modern_gemini_models(api_key) if (not model_name or "自動" in str(model_name)) else []
    candidate_models = list(dict.fromkeys([target_model] + discovered + [GEMINI_PRIMARY_MODEL, GEMINI_SECONDARY_MODEL]))
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {
            "temperature": 0.25,
            "maxOutputTokens": 1200,
        },
    }

    last_err = ""
    for m_id in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m_id}:generateContent"
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=(4.0, 18.0))
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        header_tag = f"*(由 `{m_id}` 研究員引擎產出・30分鐘快取保護・研究輔助用途，不保證獲利)*\n\n"
                        return True, header_tag + parts[0]["text"].strip()
                last_err = f"模型 `{m_id}` 回傳內容為空。"
            elif resp.status_code in (401, 403):
                return False, "⚠️ Gemini API Key 無效或未開通權限 (HTTP 401/403)，請檢查金鑰設定。"
            elif resp.status_code == 429:
                return False, "⚠️ Gemini API 呼叫頻率已達上限 (HTTP 429 Quota Exceeded)，請稍候 1 分鐘再試。"
            elif resp.status_code == 404:
                last_err = f"模型 `{m_id}` 不存在 (HTTP 404)"
                continue
            elif resp.status_code >= 500:
                last_err = f"Google 雲端伺服器暫時異常 (HTTP {resp.status_code})"
                continue
            else:
                last_err = f"HTTP {resp.status_code}: {resp.text[:140]}"
        except requests.Timeout:
            last_err = f"連線 `{m_id}` 逾時 (Timeout)"
        except Exception as e:
            logging.warning(f"Gemini Research Agent ({m_id}) 異常: {e}")
            last_err = f"連線異常: {str(e)}"

    return False, f"⚠️ AI 研究員暫時無法完成推演（{last_err}）。所有 Python 確定性量化數據仍可正常檢視。"


# ==============================================================================
# 四、 UI 掛載渲染器 (1. 單股診斷內嵌式 AI 研究員  2. 獨立八大研究員總部)
# ==============================================================================
def render_stock_ai_agents_expander(
    res: dict,
    df_asset: pd.DataFrame,
    ticker_raw: str,
    mode_type: str,
    api_key: str,
    model_name: str,
    vix_info: dict = None,
    news_items: list = None,
):
    """
    嵌入於個股/ETF/期貨診斷頁面的「五大標的研究員快速召喚面板」
    支援：1. 交易點子產生器  2. 自動化技術分析師(日週線)  4. 策略回測分析師  7. 財報基本面研究員  8. 論點反方審查
    """
    disp_title = f"🧠 【八大 AI 研究員工作站：{ticker_raw} 深度結構拆解 (按需觸發)】"
    with st.expander(disp_title, expanded=False):
        st.caption(
            "⚡ **確定性數據隔離**：Python 先精算日/週線均線、回測獲利因子與財報三率，再按需交由 Gemini 執行機構級推理（不預先耗費記憶體與額度）。"
        )

        agent_options = {
            "trade_idea": "🎯 1. 交易點子產生器 (5大研究情境與失效條件)",
            "tech_analyst": "📐 2. 自動化技術分析師 (日線+週線結構拆解)",
            "backtest_analyst": "🧪 4. 交易策略回測分析師 (獲利因子與前視偏誤審計)",
            "fundamental_researcher": "📑 7. 財報與基本面研究員 (三率/現金流/法說追問)",
            "contrarian_review": "😈 8. 投資論點反方審查 (Devil's Advocate 盲點檢查)",
        }

        sel_agent = st.selectbox(
            "選擇指派的研究員角色",
            options=list(agent_options.keys()),
            format_func=lambda k: agent_options[k],
            key=f"stk_agent_sel_{mode_type}_{ticker_raw}",
        )

        extra_prompt = ""
        if sel_agent == "contrarian_review":
            extra_prompt = st.text_area(
                "輸入您目前看多或看空的投資論點（留空則自動審查系統當前評分結論）",
                placeholder="例：我認為該標的受惠 AI 伺服器出貨放量，且站穩月線，預期未來一季將突破前高...",
                height=80,
                key=f"stk_contra_in_{mode_type}_{ticker_raw}",
            )
        elif sel_agent == "trade_idea":
            extra_prompt = st.text_input(
                "補充操作週期偏好（選填）",
                placeholder="例：偏好 5~15 日短波段，最大可承受停損 3%",
                key=f"stk_idea_in_{mode_type}_{ticker_raw}",
            )

        # 組裝確定性上下文 JSON
        weekly_tech = compute_weekly_technicals(df_asset)
        bt_metrics = compute_enhanced_backtest_metrics(df_asset, market_type=mode_type)

        ma_stat = res.get("ma_status", {})
        context_payload = {
            "analysis_date": datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M"),
            "ticker": ticker_raw,
            "asset_type": mode_type,
            "latest_close": round(_safe_float(res.get("close")), 2),
            "composite_score_0_to_100": res.get("total_score"),
            "daily_structure": {
                "alignment": res.get("ma_alignment"),
                "ma5": round(_safe_float(ma_stat.get("ma5_val")), 2) if ma_stat.get("has_ma5") else "N/A",
                "ma20": round(_safe_float(ma_stat.get("ma20_val")), 2) if ma_stat.get("has_ma20") else "N/A (暖機未滿20日)",
                "ma60": round(_safe_float(ma_stat.get("ma60_val")), 2) if ma_stat.get("has_ma60") else "N/A (暖機未滿60日)",
                "system_stop_loss": round(_safe_float(res.get("stop_loss")), 2),
                "system_target_60d": round(_safe_float(res.get("target_60d")), 2),
                "rel_alpha_20d_pct": round(_safe_float(res.get("rel_alpha_20d")), 2),
            },
            "weekly_structure": weekly_tech,
            "vix_environment": vix_info if vix_info else {"status": "未載入"},
        }

        if sel_agent == "backtest_analyst":
            context_payload["backtest_audit"] = bt_metrics
        elif sel_agent == "fundamental_researcher":
            context_payload["fundamentals"] = res.get("fund_data", {})
            suite = res.get("inst_suite", {})
            if suite.get("has_suite"):
                context_payload["institutional_suite"] = {
                    "financial_analysis": suite.get("financial_analysis"),
                    "equity_research": suite.get("equity_research"),
                    "earnings_reviewer": suite.get("earnings_reviewer"),
                }
        elif sel_agent == "contrarian_review" and not extra_prompt.strip():
            extra_prompt = (
                f"系統目前對 {ticker_raw} 給出綜合評分 {res.get('total_score')}/100，"
                f"均線狀態為「{res.get('ma_alignment')}」，法人評等「{res.get('analyst_data', {}).get('rec_label', '中立')}」。"
                f"請擔任反方研究員，找出此判讀最可能出錯的盲點與失效條件。"
            )

        if news_items:
            context_payload["recent_headlines"] = [
                {"title": n.get("title"), "time": n.get("time")} for n in news_items[:3]
            ]

        res_state_key = f"stk_agent_out_{mode_type}_{ticker_raw}_{sel_agent}"
        if st.button(
            f"🚀 啟動【{AI_RESEARCH_AGENT_SPECS[sel_agent]['title']}】深度分析",
            type="primary",
            use_container_width=True,
            key=f"btn_run_stk_agent_{mode_type}_{ticker_raw}_{sel_agent}",
        ):
            with st.spinner(f"正在呼叫 {AI_RESEARCH_AGENT_SPECS[sel_agent]['title']} 進行結構化推理..."):
                ctx_str = json.dumps(context_payload, ensure_ascii=False, indent=2)
                ok, report_md = run_gemini_research_agent(
                    api_key=api_key,
                    model_name=model_name,
                    agent_key=sel_agent,
                    context_json_str=ctx_str,
                    user_extra_input=extra_prompt,
                )
                st.session_state[res_state_key] = (ok, report_md)

        if res_state_key in st.session_state:
            ok, report_md = st.session_state[res_state_key]
            if ok:
                st.markdown(report_md)
            else:
                st.warning(report_md)


def render_ai_research_hub_mode(
    api_key: str,
    model_name: str,
    usd_twd_rate: float = 32.0,
    latest_news_list: list = None,
):
    """
    獨立頂部模式：「🧠 八大AI研究員總部」
    提供全套投資組合壓力測試、交易日誌行為審計、新聞轉交易研究、反方論點審查與跨標的策略實驗室。
    """
    st.subheader("🧠 八大機構級 AI 研究員工作總部")
    st.caption(
        "整合確定性 Python 量化風控引擎與 Gemini 深度研究工作流｜嚴格區分『已確認事實』與『模型推論』，資料不足絕不捏造。"
    )

    hub_tabs = st.tabs([
        "🛡️ 投組風控 (-20%壓測)",
        "📓 交易日誌分析師",
        "📰 新聞轉交易研究",
        "😈 投資論點反方審查",
        "📐 策略回測與點子實驗室",
    ])

    # --------------------------------------------------------------------------
    # Tab 1: 5. 投資組合風險管理 (Portfolio Risk Manager)
    # --------------------------------------------------------------------------
    with hub_tabs[0]:
        st.markdown("#### 🛡️ 5. 投資組合風險管理（集中度審計 ＆ 大盤下跌 20% 壓力測試）")
        st.caption("先由 Python 計算總資產、現金水位、產業/幣別集中度與 Beta 加權 -20% 壓力測試損益，再交由 AI 審查隱藏風險。")

        c_p1, c_p2, c_p3 = st.columns(3)
        with c_p1:
            port_cash = st.number_input("可用現金儲備 (NTD)", min_value=0, value=300000, step=50000, key="hub_port_cash")
        with c_p2:
            port_horizon = st.selectbox("預計投資期間", ["1~3 個月短波段", "6~12 個月中期配置", "1~3 年以上長線投資"], index=1, key="hub_port_horizon")
        with c_p3:
            port_max_dd = st.slider("最大可承受組合回撤 (%)", min_value=5, max_value=40, value=15, step=1, key="hub_port_maxdd")

        if "hub_portfolio_df" not in st.session_state:
            st.session_state.hub_portfolio_df = pd.DataFrame([
                {"代碼": "2330.TW", "名稱": "台積電", "市場(TW/US)": "TW", "產業": "半導體", "市值(原幣)": 450000, "Beta": 1.25},
                {"代碼": "0050.TW", "名稱": "元大台灣50", "市場(TW/US)": "TW", "產業": "市值ETF", "市值(原幣)": 250000, "Beta": 1.00},
                {"代碼": "NVDA", "名稱": "輝達", "市場(TW/US)": "US", "產業": "AI晶片", "市值(原幣)": 6000, "Beta": 1.65},
            ])

        edited_port = st.data_editor(
            st.session_state.hub_portfolio_df,
            num_rows="dynamic",
            use_container_width=True,
            key="hub_port_editor",
        )
        st.session_state.hub_portfolio_df = edited_port

        stress_res = run_portfolio_stress_test(edited_port, cash_ntd=port_cash, usd_twd=usd_twd_rate)
        if stress_res.get("has_data"):
            st.markdown("##### 📊 Python 確定性壓力測試與集中度儀表板")
            m1, m2, m3 = st.columns(3)
            m1.metric("投組總資產 (約當NTD)", f"{int(stress_res['total_ntd']):,} 元", f"現金比 {stress_res['cash_pct']}%")
            m2.metric("投組加權 Beta", f"{stress_res['portfolio_beta']:.2f}", f"最大單一持股 {stress_res['max_single_holding']}")
            st_20 = stress_res["stress_test_20pct"]
            m3.metric(
                "大盤 -20% 預估衝擊",
                f"{st_20['estimated_portfolio_drop_pct']:.1f}%",
                f"約 -{int(st_20['estimated_loss_ntd']):,} 元",
                delta_color="inverse",
            )
            for al in stress_res["risk_alerts"]:
                st.write(f"• {al}")
            st.caption(f"📌 模型限制說明：{st_20['model_limitation']}")

            if st.button("🤖 呼叫【投資組合風險管理師】進行再平衡與隱藏關聯審計", type="primary", use_container_width=True, key="btn_hub_port_ai"):
                with st.spinner("正在進行跨資產集中度與再平衡取捨分析..."):
                    ctx = {
                        "horizon": port_horizon,
                        "max_tolerable_loss_pct": port_max_dd,
                        "usd_twd_fx": usd_twd_rate,
                        "deterministic_stress_test": stress_res,
                    }
                    ok, md_out = run_gemini_research_agent(
                        api_key=api_key,
                        model_name=model_name,
                        agent_key="portfolio_risk",
                        context_json_str=json.dumps(ctx, ensure_ascii=False, indent=2),
                    )
                    st.session_state["hub_port_ai_out"] = (ok, md_out)

            if "hub_port_ai_out" in st.session_state:
                ok, md_out = st.session_state["hub_port_ai_out"]
                st.markdown(md_out) if ok else st.warning(md_out)
        else:
            st.info(stress_res.get("reason", "請輸入有效持倉"))

    # --------------------------------------------------------------------------
    # Tab 2: 6. 交易日誌分析師 (Trading Journal Analyst)
    # --------------------------------------------------------------------------
    with hub_tabs[1]:
        st.markdown("#### 📓 6. 交易日誌分析師（最近 20 筆交易復盤 ＆ 行為偏誤診斷）")
        st.caption("紀錄最近交易的進出場、損益與當時理由，系統將把『紀錄能證明的事』與『行為推測』分開，產出 3 條個人交易規則。")

        if "hub_journal_df" not in st.session_state:
            st.session_state.hub_journal_df = pd.DataFrame([
                {"交易日期": "2026-11-05", "標的代碼": "2330.TW", "方向": "做多", "淨損益(元)": 12500, "是否遵守紀律": "是", "進出場理由": "ORB 15分K突破且站穩VWAP，達1.5R分批停利"},
                {"交易日期": "2026-11-07", "標的代碼": "2454.TW", "方向": "做多", "淨損益(元)": -18000, "是否遵守紀律": "否", "進出場理由": "開高追價，跌破月線未停損反而向下攤平"},
                {"交易日期": "2026-11-10", "標的代碼": "WTX", "方向": "做空", "淨損益(元)": 8400, "是否遵守紀律": "是", "進出場理由": "跌破ORB低點順勢空單，13:15前平倉"},
                {"交易日期": "2026-11-12", "標的代碼": "2317.TW", "方向": "做多", "淨損益(元)": -9500, "是否遵守紀律": "否", "進出場理由": "看外電利多盤中追高，未等回測均線"},
            ])

        edited_journal = st.data_editor(
            st.session_state.hub_journal_df,
            num_rows="dynamic",
            use_container_width=True,
            key="hub_journal_editor",
        )
        st.session_state.hub_journal_df = edited_journal

        j_stats = analyze_trading_journal_stats(edited_journal)
        if j_stats.get("has_data"):
            jc1, jc2, jc3, jc4 = st.columns(4)
            jc1.metric("復盤樣本數", f"{j_stats['sample_count']} 筆")
            jc2.metric("交易勝率", f"{j_stats['win_rate_pct']}%")
            jc3.metric("賺賠比 (Payoff)", f"{j_stats['payoff_ratio']:.2f}")
            jc4.metric("違規交易損益", f"{int(j_stats['rule_break_pnl']):,} 元", f"違規 {j_stats['rule_break_count']} 筆")
            st.caption(j_stats["sample_warning"])

            if st.button("🤖 呼叫【交易日誌分析師】找出重複錯誤與 3 條紀律規則", type="primary", use_container_width=True, key="btn_hub_journal_ai"):
                with st.spinner("正在比對紀律違規紀錄與行為偏誤..."):
                    ok, md_out = run_gemini_research_agent(
                        api_key=api_key,
                        model_name=model_name,
                        agent_key="trading_journal",
                        context_json_str=json.dumps(j_stats, ensure_ascii=False, indent=2),
                    )
                    st.session_state["hub_journal_ai_out"] = (ok, md_out)

            if "hub_journal_ai_out" in st.session_state:
                ok, md_out = st.session_state["hub_journal_ai_out"]
                st.markdown(md_out) if ok else st.warning(md_out)

    # --------------------------------------------------------------------------
    # Tab 3: 3. 新聞轉交易研究 (News-to-Trade Researcher)
    # --------------------------------------------------------------------------
    with hub_tabs[2]:
        st.markdown("#### 📰 3. 新聞轉交易研究（事件拆解、已定價資訊與推翻條件）")
        st.caption("貼上外電全文、法說會摘要或挑選最新快訊，由研究員拆解短期/長期影響與利多利空（缺乏依據絕不猜測漲跌幅）。")

        news_target_corp = st.text_input("研究公司／產業主題", value="台積電 / AI 半導體供應鏈", key="hub_news_corp")
        default_news_blob = ""
        if latest_news_list:
            default_news_blob = "\n".join(
                [f"- [{x.get('pub_date', '即時')}] {x.get('title', '')}（來源：{x.get('source', '')}）" for x in latest_news_list[:5]]
            )

        news_raw_text = st.text_area(
            "貼上新聞原文、重訊公告或外電摘要（已自動帶入最新即時外電標題供參考）",
            value=default_news_blob,
            height=150,
            key="hub_news_blob",
        )

        if st.button("🤖 呼叫【新聞轉交易研究員】解析事件影響與推翻條件", type="primary", use_container_width=True, key="btn_hub_news_ai"):
            if not news_raw_text.strip():
                st.warning("請先貼上新聞原文或訊息內容，避免模型缺乏依據。")
            else:
                with st.spinner("正在拆解事件日期、已確認事實與推翻條件..."):
                    ctx = {
                        "target_company_or_sector": news_target_corp,
                        "current_date": datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d"),
                        "provided_news_content": news_raw_text.strip(),
                    }
                    ok, md_out = run_gemini_research_agent(
                        api_key=api_key,
                        model_name=model_name,
                        agent_key="news_researcher",
                        context_json_str=json.dumps(ctx, ensure_ascii=False, indent=2),
                    )
                    st.session_state["hub_news_ai_out"] = (ok, md_out)

        if "hub_news_ai_out" in st.session_state:
            ok, md_out = st.session_state["hub_news_ai_out"]
            st.markdown(md_out) if ok else st.warning(md_out)

    # --------------------------------------------------------------------------
    # Tab 4: 8. 投資論點反方審查 (Devil's Advocate)
    # --------------------------------------------------------------------------
    with hub_tabs[3]:
        st.markdown("#### 😈 8. 投資論點反方審查（Devil's Advocate 盲點審計）")
        st.caption("貼上你的看多或看空交易計畫，讓反方研究員檢查隱含前提、估值盲點、替代解釋與失效追蹤清單。")

        thesis_input = st.text_area(
            "貼上您的完整投資論點（建議包含：標的、進場理由、目標預期、持有期間與預設停損）",
            placeholder="例：我看好 2330.TW 未來兩季表現，因為 CoWoS 產能持續滿載且美國科技巨頭資本支出上修，目前 PE 仍在合理區間...",
            height=140,
            key="hub_contra_thesis",
        )

        if st.button("😈 啟動【反方研究員】審查論點漏洞與建立追蹤清單", type="primary", use_container_width=True, key="btn_hub_contra_ai"):
            if not thesis_input.strip():
                st.warning("請先輸入您的投資論點內容。")
            else:
                with st.spinner("正在審計前提假設與尋找最強反對理由..."):
                    ctx = {
                        "review_date": datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d"),
                        "user_investment_thesis": thesis_input.strip(),
                    }
                    ok, md_out = run_gemini_research_agent(
                        api_key=api_key,
                        model_name=model_name,
                        agent_key="contrarian_review",
                        context_json_str=json.dumps(ctx, ensure_ascii=False, indent=2),
                    )
                    st.session_state["hub_contra_ai_out"] = (ok, md_out)

        if "hub_contra_ai_out" in st.session_state:
            ok, md_out = st.session_state["hub_contra_ai_out"]
            st.markdown(md_out) if ok else st.warning(md_out)

    # --------------------------------------------------------------------------
    # Tab 5: 1, 2, 4, 7 跨標的快速召喚說明
    # --------------------------------------------------------------------------
    with hub_tabs[4]:
        st.markdown("#### 📐 1、2、4、7 號研究員（單一標的深度掛載說明）")
        st.info(
            "💡 **無縫整合提示**：\n"
            "• **1. 交易點子產生器**、**2. 自動化技術分析師（日線＋週線）**、**4. 交易策略回測分析師** 與 **7. 財報與基本面研究員** 已直接內嵌於「🔍 台股診斷」、「🇺🇸 美股診斷」與「⚡ 台灣期貨」的診斷結果頁面中！\n"
            "• 只要先查詢任一檔股票或期貨，展開下方的 **「🧠 【八大 AI 研究員工作站：深度結構拆解】」** 即可一鍵帶入該標的之真實日週線、回測獲利因子與財報三率數據進行推理。"
        )
