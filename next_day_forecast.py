import time
import numpy as np
import pandas as pd
try:
    import streamlit as st
except ImportError:
    class _DummySt:
        session_state = {}
        @staticmethod
        def cache_data(*args, **kwargs):
            def _dec(fn):
                fn.clear = lambda: None
                return fn
            return _dec
        @staticmethod
        def fragment(*args, **kwargs):
            def _dec(fn):
                return fn
            return _dec
    st = _DummySt()
from scipy.stats import norm
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def align_us_to_tw(tw_df: pd.DataFrame, us_df: pd.DataFrame) -> pd.DataFrame:
    """Align US market features to TW trading dates strictly backward without lookahead bias."""
    if tw_df is None or tw_df.empty or us_df is None or us_df.empty:
        return pd.DataFrame()
    left = tw_df.copy()
    right = us_df.copy()
    left["tw_date"] = pd.to_datetime(left["tw_date"]).dt.normalize()
    right["us_date"] = pd.to_datetime(right["us_date"]).dt.normalize()
    left = left.dropna(subset=["tw_date"]).sort_values("tw_date").reset_index(drop=True)
    right = right.dropna(subset=["us_date"]).sort_values("us_date").reset_index(drop=True)
    return pd.merge_asof(
        left,
        right,
        left_on="tw_date",
        right_on="us_date",
        direction="backward",
        allow_exact_matches=False,
    )


def build_training_frame(tw_df: pd.DataFrame, us_df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    """Build aligned training frame with next-day TW return target."""
    merged = align_us_to_tw(tw_df, us_df)
    if merged.empty or "tw_close" not in merged.columns:
        return pd.DataFrame()
    merged["target_next_ret"] = merged["tw_close"].pct_change().shift(-1)
    required = [c for c in feature_cols if c in merged.columns] + ["target_next_ret"]
    return merged.dropna(subset=required).reset_index(drop=True)


def fit_ridge_walkforward(
    train_df: pd.DataFrame,
    feature_cols: list[str],
    shrinkage: float = 0.75,
    default_sigma: float = 0.012,
) -> dict:
    """Fit standardized RidgeCV model and estimate out-of-sample residual volatility sigma."""
    if train_df is None or train_df.empty:
        return {
            "model": None,
            "feature_cols": feature_cols,
            "shrinkage": shrinkage,
            "sigma": default_sigma,
            "oos_r2": None,
            "has_edge": False,
        }
        
    available_cols = [c for c in feature_cols if c in train_df.columns]
    if not available_cols or "target_next_ret" not in train_df.columns:
        return {
            "model": None,
            "feature_cols": available_cols,
            "shrinkage": shrinkage,
            "sigma": default_sigma,
            "oos_r2": None,
            "has_edge": False,
        }

    # Drop NaNs and infinite values strictly before attempting training
    clean_df = train_df.dropna(subset=available_cols + ["target_next_ret"]).copy()
    clean_df = clean_df[np.isfinite(clean_df[available_cols]).all(axis=1)]
    clean_df = clean_df[np.isfinite(clean_df["target_next_ret"])]

    n_samples = len(clean_df)
    if n_samples < 10:
        return {
            "model": None,
            "feature_cols": available_cols,
            "shrinkage": shrinkage,
            "sigma": default_sigma,
            "oos_r2": None,
            "has_edge": False,
        }

    X = clean_df[available_cols].astype(float).values
    y = clean_df["target_next_ret"].astype(float).values
    
    n_splits = min(5, max(2, n_samples // 10))
    tscv = TimeSeriesSplit(n_splits=n_splits)

    alphas = np.logspace(-2, 3, 25)
    pipe = make_pipeline(StandardScaler(), RidgeCV(alphas=alphas, cv=tscv))
    pipe.fit(X, y)

    oos_preds = []
    oos_actuals = []
    for train_idx, test_idx in tscv.split(X):
        fold_pipe = make_pipeline(StandardScaler(), RidgeCV(alphas=alphas))
        fold_pipe.fit(X[train_idx], y[train_idx])
        preds = fold_pipe.predict(X[test_idx])
        oos_preds.extend(preds)
        oos_actuals.extend(y[test_idx])

    if len(oos_preds) >= 5:
        residuals = np.array(oos_actuals) - np.array(oos_preds)
        sigma = float(np.nanstd(residuals, ddof=1)) if len(residuals) > 1 else default_sigma
        sigma = max(sigma, 1e-4)
        ss_res = float(np.sum(residuals ** 2))
        ss_tot = float(np.sum((np.array(oos_actuals) - np.mean(oos_actuals)) ** 2))
        oos_r2 = (1.0 - ss_res / ss_tot) if ss_tot > 1e-12 else 0.0
    else:
        sigma = default_sigma
        oos_r2 = None

    has_edge = bool(oos_r2 is not None and oos_r2 > 0.0)
    return {
        "model": pipe,
        "feature_cols": available_cols,
        "shrinkage": float(shrinkage),
        "sigma": sigma,
        "oos_r2": oos_r2,
        "has_edge": has_edge,
    }


def predict_next_day(bundle: dict, features: dict[str, float | None], tw_base_index: float = 0.0) -> dict:
    """Continuous prediction from mu and sigma; blocks if >= 2 core features are missing or non-finite."""
    core_cols = bundle.get("feature_cols") or ["tsm_ret", "soxx_ret", "nq_ret", "tnx_bp"]
    missing = []
    vec = []
    for col in core_cols:
        val = features.get(col)
        if val is None or not np.isfinite(val):
            missing.append(col)
            vec.append(0.0)
        else:
            vec.append(float(val))

    if len(missing) >= 2:
        return {
            "status": "blocked",
            "reason": f"核心特徵缺漏達 {len(missing)} 項（{', '.join(missing)}），已暫停預測",
            "missing": missing,
        }

    model = bundle.get("model")
    if model is None:
        return {
            "status": "untrained",
            "reason": "尚無足夠歷史訓練樣本，無法產出統計估計",
            "missing": missing,
        }

    shrinkage = float(bundle.get("shrinkage", 0.75))
    sigma = float(bundle.get("sigma", 0.012))
    raw_mu = float(model.predict(np.array([vec], dtype=float))[0])
    mu = raw_mu * shrinkage
    p_up = float(norm.cdf(mu / max(sigma, 1e-4)))

    q05 = float(norm.ppf(0.05, loc=mu, scale=sigma))
    q25 = float(norm.ppf(0.25, loc=mu, scale=sigma))
    q50 = float(norm.ppf(0.50, loc=mu, scale=sigma))
    q75 = float(norm.ppf(0.75, loc=mu, scale=sigma))
    q95 = float(norm.ppf(0.95, loc=mu, scale=sigma))

    ci68_low, ci68_high = mu - sigma, mu + sigma
    ci90_low, ci90_high = q05, q95

    pts_est = (tw_base_index * mu) if (tw_base_index and tw_base_index > 0) else None
    return {
        "status": "ok",
        "mu": mu,
        "sigma": sigma,
        "p_up": p_up,
        "pts_est": pts_est,
        "ci68": (ci68_low, ci68_high),
        "ci90": (ci90_low, ci90_high),
        "quantiles": {"q05": q05, "q25": q25, "q50": q50, "q75": q75, "q95": q95},
        "missing": missing,
        "oos_r2": bundle.get("oos_r2"),
        "has_edge": bundle.get("has_edge", False),
    }


def evaluate_oos(log_df: pd.DataFrame) -> dict:
    """Evaluate realized direction hit rate, MAE, and OOS R2 from logged predictions with realized returns."""
    if log_df is None or log_df.empty:
        return {"count": 0, "hit_rate": None, "mae": None, "oos_r2": None, "has_edge": False}
    valid = log_df.dropna(subset=["mu", "actual_ret"]).copy()
    if valid.empty:
        return {"count": 0, "hit_rate": None, "mae": None, "oos_r2": None, "has_edge": False}

    pred_sign = np.sign(valid["mu"].astype(float))
    act_sign = np.sign(valid["actual_ret"].astype(float))
    non_zero = act_sign != 0
    hit_rate = float((pred_sign[non_zero] == act_sign[non_zero]).mean()) if non_zero.any() else None
    mae = float(np.mean(np.abs(valid["mu"].astype(float) - valid["actual_ret"].astype(float))))

    y_true = valid["actual_ret"].astype(float).values
    y_pred = valid["mu"].astype(float).values
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    oos_r2 = (1.0 - ss_res / ss_tot) if ss_tot > 1e-12 else None
    has_edge = bool(oos_r2 is not None and oos_r2 > 0.0 and len(valid) >= 20)

    return {
        "count": int(len(valid)),
        "hit_rate": hit_rate,
        "mae": mae,
        "oos_r2": oos_r2,
        "has_edge": has_edge,
    }


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_forecast_snapshot(bucket: int, us_data: list[dict] | None) -> dict:
    _ = bucket
    if not us_data:
        raise RuntimeError("尚無可用美股指標快照")
    by_sym = {d.get("symbol"): d for d in us_data if isinstance(d, dict) and d.get("symbol")}
    feats = {
        "tsm_ret": (float(by_sym["TSM"]["pct"]) / 100.0) if "TSM" in by_sym and by_sym["TSM"].get("pct") is not None else None,
        "soxx_ret": (float(by_sym["SOXX"]["pct"]) / 100.0) if "SOXX" in by_sym and by_sym["SOXX"].get("pct") is not None else None,
        "nq_ret": (float(by_sym["NQ=F"]["pct"]) / 100.0) if "NQ=F" in by_sym and by_sym["NQ=F"].get("pct") is not None else None,
        "tnx_bp": (float(by_sym["^TNX"]["diff"]) * 100.0) if "^TNX" in by_sym and by_sym["^TNX"].get("diff") is not None else None,
    }
    timestamps = {
        sym: by_sym[sym].get("bar_time", "未知")
        for sym in ["TSM", "SOXX", "NQ=F", "^TNX"]
        if sym in by_sym
    }
    return {
        "features": feats,
        "timestamps": timestamps,
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


@st.fragment(run_every=600)
def next_day_forecast_fragment(us_data: list[dict] | None = None, tw_base_index: float = 0.0) -> None:
    st.markdown("#### 📊 次日台股漲跌機率分布估計（每 10 分鐘局部更新）")
    manual_col, info_col = st.columns([1.2, 2.8])
    with manual_col:
        if st.button("🔄 立即更新預測", key="btn_refresh_next_day_forecast", use_container_width=True):
            _fetch_forecast_snapshot.clear()
            st.session_state["forecast_manual_tick"] = st.session_state.get("forecast_manual_tick", 0) + 1

    bucket = int(time.time() // 600) + int(st.session_state.get("forecast_manual_tick", 0))
    now_ts = time.time()
    try:
        # 取得真實的訓練歷史資料 (過去 1 年) 以訓練模型
        try:
            tw_hist = yf.Ticker("^TWII").history(period="1y")
            tsm_hist = yf.Ticker("TSM").history(period="1y")
            soxx_hist = yf.Ticker("SOXX").history(period="1y")
            nq_hist = yf.Ticker("NQ=F").history(period="1y")
            tnx_hist = yf.Ticker("^TNX").history(period="1y")
            
            tw_df = pd.DataFrame({"tw_date": tw_hist.index, "tw_close": tw_hist['Close']})
            us_df = pd.DataFrame({
                "us_date": tsm_hist.index,
                "tsm_ret": tsm_hist['Close'].pct_change(),
                "soxx_ret": soxx_hist['Close'].pct_change(),
                "nq_ret": nq_hist['Close'].pct_change(),
                "tnx_bp": tnx_hist['Close'].diff() * 100.0
            })
            train_df = build_training_frame(tw_df, us_df, ["tsm_ret", "soxx_ret", "nq_ret", "tnx_bp"])
            bundle = fit_ridge_walkforward(train_df, ["tsm_ret", "soxx_ret", "nq_ret", "tnx_bp"])
        except Exception as data_err:
            logging.warning(f"Failed to build training frame: {data_err}")
            bundle = {"model": None, "feature_cols": ["tsm_ret", "soxx_ret", "nq_ret", "tnx_bp"]}
        snap = _fetch_forecast_snapshot(bucket, us_data)
        st.session_state["last_good_forecast_snap"] = snap
        st.session_state["last_good_forecast_ts"] = now_ts
        stale_age_sec = 0.0
    except Exception as exc:
        snap = st.session_state.get("last_good_forecast_snap")
        last_ts = st.session_state.get("last_good_forecast_ts")
        if snap is None or last_ts is None:
            st.info(f"⚪ 預測模型等待前瞻行情資料中：{exc}")
            return
        stale_age_sec = max(0.0, now_ts - float(last_ts))
        st.warning(f"⚠️ 即時特徵抓取失敗，顯示上次成功數值（資料年齡：{int(stale_age_sec)} 秒；原因：{exc}）")

    feats = snap["features"]
    non_null_feats = {k: v for k, v in feats.items() if v is not None}
    if len(non_null_feats) < 3:
        st.warning("⚠️ 可用前瞻特徵不足，暫停次日漲跌估計。")
        return


    # 由訓練好的 Ridge 模型產生機率分布預估
    res = predict_next_day(bundle, feats, tw_base_index)
    if res.get("status") == "blocked":
        st.warning(res.get("reason", "資料不足，暫停預測。"))
        return
    elif res.get("status") == "untrained":
        st.info("⚪ " + res.get("reason", "模型尚未完成歷史資料學習。"))
        return

    mu = res["mu"]
    sigma = res["sigma"]
    p_up = res["p_up"]
    ci68 = res["ci68"]
    ci90 = res["ci90"]

    c1, c2, c3 = st.columns(3)
    pts_delta = f"約 {res['pts_est']:+.0f} 點" if res.get('pts_est') is not None else "點位基準未提供"
    c1.metric("預期次日漲跌幅 (μ)", f"{mu * 100:+.2f}%", delta=pts_delta)
    c2.metric("上漲機率 P(up) = Φ(μ/σ)", f"{p_up * 100:.1f}%", delta=f"σ = {sigma * 100:.2f}%")
    c3.metric("68% / 90% 區間", f"{ci68[0]*100:+.2f}% ~ {ci68[1]*100:+.2f}%", delta=f"90%: {ci90[0]*100:+.2f}% ~ {ci90[1]*100:+.2f}%")


    with info_col:
        next_sec = 600 - int(time.time() % 600)
        st.caption(f"🕒 最後更新：{snap['fetched_at']} ｜ 下次自動刷新約 {next_sec} 秒後")

    st.caption(f"特徵時間：{snap.get('timestamps', {})}")
    st.caption("⚠️ 模型尚無充足歷史回測優勢驗證，僅供參考；隔日漲跌雜訊極大，非交易訊號。")
