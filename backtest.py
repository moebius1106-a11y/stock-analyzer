import math
import numpy as np
import pandas as pd


def wilson_confidence_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 0.0)
    p = max(0.0, min(1.0, successes / total))
    denom = 1.0 + (z * z) / total
    center = (p + (z * z) / (2.0 * total)) / denom
    half_width = (z * math.sqrt((p * (1.0 - p) + (z * z) / (4.0 * total)) / total)) / denom
    return (max(0.0, center - half_width), min(1.0, center + half_width))


def compute_mark_to_market_mdd(equity_series: pd.Series) -> float:
    if equity_series is None or equity_series.empty:
        return 0.0
    s = pd.to_numeric(equity_series, errors="coerce").dropna()
    if s.empty:
        return 0.0
    peaks = s.cummax()
    dd = (s - peaks) / peaks.replace(0, np.nan)
    min_dd = float(dd.min()) if not dd.dropna().empty else 0.0
    return abs(min_dd) * 100.0 if min_dd < 0 else 0.0


def evaluate_trade_sample_adequacy(trade_count: int, wins: int) -> dict:
    ci_low, ci_high = wilson_confidence_interval(wins, trade_count)
    win_rate = (wins / trade_count * 100.0) if trade_count > 0 else 0.0
    return {
        "trade_count": int(trade_count),
        "win_rate_pct": win_rate,
        "ci95_low_pct": ci_low * 100.0,
        "ci95_high_pct": ci_high * 100.0,
        "low_sample_warning": trade_count < 30,
    }
