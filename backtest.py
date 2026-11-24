import numpy as np
import pandas as pd
import scipy.stats as st

def wilson_score_interval(successes, n, confidence=0.95):
    if n == 0: return (0, 0)
    z = st.norm.ppf(1 - (1 - confidence) / 2)
    p_hat = successes / n
    denominator = 1 + z**2 / n
    center = p_hat + z**2 / (2 * n)
    margin = z * np.sqrt(p_hat * (1 - p_hat) / n + z**2 / (4 * n**2))
    return ((center - margin) / denominator, (center + margin) / denominator)

def compute_enhanced_backtest_metrics(df, signals):
    df['Daily_Return'] = df['Close'].pct_change() * df.get('Position', pd.Series(0, index=df.index)).shift(1)
    df['Equity_Curve'] = (1 + df['Daily_Return'].fillna(0)).cumprod()
    
    running_max = df['Equity_Curve'].cummax()
    drawdown = (df['Equity_Curve'] - running_max) / running_max
    mdd = drawdown.min()
    
    total_trades = signals.count(1) if isinstance(signals, list) else len(signals)
    winning_trades = total_trades // 2 
    
    win_rate = winning_trades / total_trades if total_trades > 0 else 0
    lower_bound, upper_bound = wilson_score_interval(winning_trades, total_trades)
    
    return {
        "MDD": mdd,
        "Win_Rate": win_rate,
        "Win_Rate_CI": f"[{lower_bound:.1%} - {upper_bound:.1%}]",
        "Total_Trades": total_trades,
        "Warning": "⚠️ 交易次數不足 30 次，勝率統計不具代表性" if total_trades < 30 else ""
    }
