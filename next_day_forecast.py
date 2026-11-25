import time
import logging
import yfinance as yf
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
import pytz
from datetime import datetime, timezone, timedelta

TAIPEI_TZ = timezone(timedelta(hours=8))
NY_TZ = pytz.timezone('America/New_York')


def align_us_to_tw(tw_df: pd.DataFrame, us_df: pd.DataFrame) -> pd.DataFrame:
    """Align US market features to TW trading dates strictly backward without lookahead bias.
    US features must be available *before* the Taiwan market opens."""
    if tw_df is None or tw_df.empty or us_df is None or us_df.empty:
        return pd.DataFrame()
        
    left = tw_df.copy()
    right = us_df.copy()
    
    # 確保兩邊都有 datetime
    left["tw_date"] = pd.to_datetime(left["tw_date"])
    right["us_date"] = pd.to_datetime(right["us_date"])
    
    # P0: Extract session date strictly in local market timezone
    # TW: Asia/Taipei
    if left["tw_date"].dt.tz is None:
        left_local = left["tw_date"].dt.tz_localize("Asia/Taipei")
    else:
        left_local = left["tw_date"].dt.tz_convert("Asia/Taipei")
        
    # US: America/New_York
    if right["us_date"].dt.tz is None:
        right_local = right["us_date"].dt.tz_localize("America/New_York")
    else:
        right_local = right["us_date"].dt.tz_convert("America/New_York")
        
    left["tw_session_date"] = left_local.dt.date
    right["us_session_date"] = right_local.dt.date

    # Define strict cutoff and publish times in local timezones, then convert to UTC for merge
    # TW cutoff: 08:50 AM Taipei time of the TW session date
    left["tw_cutoff_ts"] = (left_local.dt.normalize() + pd.Timedelta(hours=8, minutes=50)).dt.tz_convert("UTC")
    
    # US publish: 16:30 PM NY time of the US session date
    right["us_available_ts"] = (right_local.dt.normalize() + pd.Timedelta(hours=16, minutes=30)).dt.tz_convert("UTC")
        
    left = left.dropna(subset=["tw_cutoff_ts"]).sort_values("tw_cutoff_ts").reset_index(drop=True)
    right = right.dropna(subset=["us_available_ts"]).sort_values("us_available_ts").reset_index(drop=True)
    
    # Merge backward: strictly no lookahead
    merged = pd.merge_asof(
        left,
        right,
        left_on="tw_cutoff_ts",
        right_on="us_available_ts",
        direction="backward",
        allow_exact_matches=False,
    )
    
    if not merged.empty:
        invalid_rows = merged["us_available_ts"] >= merged["tw_cutoff_ts"]
        merged = merged[~invalid_rows]
        
    return merged

def build_training_frame(tw_df: pd.DataFrame, us_df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    """Build aligned training frame with next-day TW return target."""
    merged = align_us_to_tw(tw_df, us_df)
    if merged.empty or "tw_close" not in merged.columns:
        return pd.DataFrame()
        
    # Target: T+1 Close / T Close - 1 
    # Cutoff is T 08:50 AM. This target predicts the market evolution from T Close to T+1 Close.
    merged["target_next_ret"] = merged["tw_close"].pct_change().shift(-1)
    
    for c in feature_cols:
        if c not in merged.columns:
             return pd.DataFrame() 
             
    required = feature_cols + ["target_next_ret", "tw_cutoff_ts", "us_available_ts"]
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
            "oos_count": 0,
            "has_edge": False,
        }
        
    available_cols = [c for c in feature_cols if c in train_df.columns]
    if len(available_cols) != len(feature_cols) or "target_next_ret" not in train_df.columns:
        return {
            "model": None,
            "feature_cols": feature_cols,
            "shrinkage": shrinkage,
            "sigma": default_sigma,
            "oos_r2": None,
            "oos_count": 0,
            "has_edge": False,
        }

    clean_df = train_df.dropna(subset=available_cols + ["target_next_ret"]).copy()
    clean_df = clean_df[np.isfinite(clean_df[available_cols]).all(axis=1)]
    clean_df = clean_df[np.isfinite(clean_df["target_next_ret"])]

    n_samples = len(clean_df)
    if n_samples < 20: # Require at least 20 samples total for CV
        return {
            "model": None,
            "feature_cols": available_cols,
            "shrinkage": shrinkage,
            "sigma": default_sigma,
            "oos_r2": None,
            "oos_count": 0,
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

    oos_count = len(oos_preds)
    if oos_count >= 10:
        residuals = np.array(oos_actuals) - np.array(oos_preds)
        sigma = float(np.nanstd(residuals, ddof=1)) if len(residuals) > 1 else default_sigma
        sigma = max(sigma, 1e-4)
        ss_res = float(np.sum(residuals ** 2))
        ss_tot = float(np.sum((np.array(oos_actuals) - np.mean(oos_actuals)) ** 2))
        oos_r2 = (1.0 - ss_res / ss_tot) if ss_tot > 1e-12 else 0.0
    else:
        sigma = default_sigma
        oos_r2 = None

    # P1: Strictly require minimum sample and strict baseline beat
    has_edge = bool(oos_r2 is not None and oos_r2 > 0.001 and oos_count >= 10)
    return {
        "model": pipe,
        "feature_cols": available_cols,
        "shrinkage": float(shrinkage),
        "sigma": sigma,
        "oos_r2": oos_r2,
        "oos_count": oos_count,
        "has_edge": has_edge,
    }

def predict_next_day(bundle: dict, features: dict[str, float | None], tw_base_index: float = 0.0) -> dict:
    """Continuous prediction from mu and sigma; blocks if >= 1 core feature is missing."""
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

    if len(missing) >= 1:
        return {
            "status": "blocked",
            "reason": f"核心特徵缺漏（{', '.join(missing)}），已暫停預測",
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
        "tnx_bp": float(by_sym["^TNX"]["diff"]) if "^TNX" in by_sym and by_sym["^TNX"].get("diff") is not None else None,
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

@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_and_train_ridge_model() -> dict:
    try:
        tw_hist = yf.Ticker("^TWII").history(period="1y")
        tsm_hist = yf.Ticker("TSM").history(period="1y")
        soxx_hist = yf.Ticker("SOXX").history(period="1y")
        nq_hist = yf.Ticker("NQ=F").history(period="1y")
        tnx_hist = yf.Ticker("^TNX").history(period="1y")
    except Exception as e:
        raise RuntimeError(f"Yahoo API 歷史行情抓取失敗: {e}")
    
    if tw_hist.empty or tsm_hist.empty or soxx_hist.empty or nq_hist.empty or tnx_hist.empty:
        raise RuntimeError("部份歷史資料為空，無法建立訓練管線。")

    # 確保日曆合併基礎
    if tw_hist.index.tz is None:
        tw_hist.index = tw_hist.index.tz_localize("Asia/Taipei")
    if tsm_hist.index.tz is None:
        tsm_hist.index = tsm_hist.index.tz_localize("America/New_York")
    
    tw_df = pd.DataFrame({"tw_date": tw_hist.index, "tw_close": tw_hist['Close']})
    
    # 建立美股交易日曆對齊表 (以 TSM 交易日為準)
    us_raw = pd.DataFrame(index=tsm_hist.index)
    
    # P1: 改以獨立計算再 join，避免 ffill 跨日複製未發布的變動率
    # 停牌日或缺 bar 時，該日期的報酬率為 NaN，會在最後被 dropna 濾除，確保不重複污染樣本
    tsm_ret_s = tsm_hist['Close'].pct_change()
    soxx_ret_s = soxx_hist['Close'].pct_change()
    nq_ret_s = nq_hist['Close'].pct_change()
    tnx_bp_s = tnx_hist['Close'].diff() * 100.0
    
    us_raw["tsm_ret"] = tsm_ret_s
    us_raw = us_raw.join(soxx_ret_s.rename("soxx_ret"), how="left")
    us_raw = us_raw.join(nq_ret_s.rename("nq_ret"), how="left")
    us_raw = us_raw.join(tnx_bp_s.rename("tnx_bp"), how="left")
    
    # P1: 確保 index 轉換安全
    us_df = us_raw.reset_index()
    # 將無論是 Date 或 Datetime 命名的欄位，強制更名為 us_date
    date_col = next((c for c in us_df.columns if c.lower() in ("date", "datetime", "index")), None)
    if date_col:
        us_df = us_df.rename(columns={date_col: "us_date"})
        
    train_df = build_training_frame(tw_df, us_df, ["tsm_ret", "soxx_ret", "nq_ret", "tnx_bp"])
    bundle = fit_ridge_walkforward(train_df, ["tsm_ret", "soxx_ret", "nq_ret", "tnx_bp"])
    
    bundle["metadata"] = {
        "train_samples": len(train_df),
        "last_tw_date": str(train_df["tw_cutoff_ts"].max())[:10] if not train_df.empty else "N/A",
        "last_us_date": str(train_df["us_available_ts"].max())[:10] if not train_df.empty else "N/A",
        "cached_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    return bundle


@st.fragment(run_every=600)
def next_day_forecast_fragment(us_data: list[dict] | None = None, tw_base_index: float = 0.0) -> None:
    st.markdown("#### 📊 次日台股漲跌機率分布估計（每 10 分鐘局部更新）")
    manual_col, info_col = st.columns([1.2, 2.8])
    with manual_col:
        if st.button("🔄 立即更新預測", key="btn_refresh_next_day_forecast", use_container_width=True):
            _fetch_forecast_snapshot.clear()
            _fetch_and_train_ridge_model.clear()
            st.session_state["forecast_manual_tick"] = st.session_state.get("forecast_manual_tick", 0) + 1

    bucket = int(time.time() // 600) + int(st.session_state.get("forecast_manual_tick", 0))
    now_ts = time.time()
    
    # 1. Train Model (P0: Properly separate model errors from snapshot errors)
    bundle = None
    try:
        bundle = _fetch_and_train_ridge_model()
    except Exception as data_err:
        logging.warning(f"Failed to fetch and train model: {data_err}")
        st.error(f"❌ 歷史訓練資料抓取與對齊失敗：{data_err}")
        # Stop completely if no valid model can be loaded
        return

    if not bundle or not bundle.get("model"):
        st.warning("⚠️ 模型尚未完成歷史資料學習或樣本外優勢未確立。")
        return

    # 2. Fetch Live Snapshot
    try:
        snap = _fetch_forecast_snapshot(bucket, us_data)
        
        # P1: 嚴格多因子 Freshness Gate (確保每項報價時間同步且不過期)
        timestamps = snap.get("timestamps", {})
        if not timestamps:
            raise ValueError("快照內缺少時間戳資訊")
            
        max_age_sec = 0.0
        parsed_ts_list = []
        
        for sym, ts_str in timestamps.items():
            if not isinstance(ts_str, str) or len(ts_str) < 10:
                raise ValueError(f"無法解析的時間格式 ({sym}: {ts_str})")
            
            try:
                dt_obj = pd.to_datetime(ts_str)
                if dt_obj.tz is None:
                    dt_obj = dt_obj.tz_localize("America/New_York")
                ts_val = dt_obj.timestamp()
                
                # 拒絕未來時間
                if ts_val > now_ts + 600:
                    raise ValueError(f"偵測到異常未來時間 ({sym})")
                    
                age_h = (now_ts - ts_val) / 3600.0
                # 拒絕過於老舊的資料
                if age_h > 96.0:  # 考量四天長假
                    raise ValueError(f"來源行情過舊 ({sym} 為 {age_h:.1f} 小時前)")
                    
                parsed_ts_list.append(ts_val)
                max_age_sec = max(max_age_sec, now_ts - ts_val)
            except Exception as e:
                raise ValueError(f"時間驗證失敗 ({sym}): {e}")
                
        # 確保各特徵之間的報價時間差距不超過 48 小時 (避免某項停牌過久)
        if max(parsed_ts_list) - min(parsed_ts_list) > 172800:
            raise ValueError("各前瞻特徵來源時間嚴重不同步，停止預測以防失真")
            
        st.session_state["last_good_forecast_snap"] = snap
        # 取最新的一筆時間作為快照年齡基準
        st.session_state["last_good_forecast_ts"] = max(parsed_ts_list)
        stale_age_sec = max(0.0, now_ts - st.session_state["last_good_forecast_ts"])
        
    except Exception as exc:
        snap = st.session_state.get("last_good_forecast_snap")
        last_ts = st.session_state.get("last_good_forecast_ts")
        if snap is None or last_ts is None:
            st.info(f"⚪ 預測模型等待前瞻即時行情中：{exc}")
            return
            
        stale_age_sec = max(0.0, now_ts - float(last_ts))
        
        # P0: Hard cutoff for stale data usage (Max 2 hours stale allowed for caching fallback)
        if stale_age_sec > 7200:
            st.error(f"🔴 快取即時特徵已嚴重過期 ({int(stale_age_sec/60)} 分鐘)，停止機率預估。原因：{exc}")
            return
            
        st.warning(f"⚠️ 即時特徵最新抓取失敗，使用快取數值（資料已延遲：{int(stale_age_sec/60)} 分鐘；原因：{exc}）")

    feats = snap["features"]
    
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
        meta = bundle.get("metadata", {})
        next_sec = 600 - int(time.time() % 600)
        st.caption(f"🕒 行情特徵最後更新：{snap['fetched_at']} ｜ 行情年齡：{int(stale_age_sec/60)} 分鐘 ｜ 下次自動刷新約 {next_sec} 秒後")
        st.caption(f"🧪 模型訓練批次：{meta.get('cached_at', '未知')} ｜ 樣本數：{meta.get('train_samples', 0)} ｜ 樣本外邊際優勢(OOS R2): {res.get('oos_r2', 0.0):.4f}")

    st.caption(f"特徵時間 (當地)：{snap.get('timestamps', {})}")
    st.caption("⚠️ 模型機率分布為客觀歷史殘差映射，隔日漲跌雜訊極大，非交易訊號保證。")
