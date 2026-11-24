import time
import requests

try:
    import streamlit as st
except ImportError:
    st = None

BLOCKED_MODEL_KEYWORDS = ("tts", "image", "live", "embedding", "audio", "veo", "imagen")


def is_text_generation_model(model_name: str) -> bool:
    low = (model_name or "").lower()
    if not low:
        return False
    return not any(kw in low for kw in BLOCKED_MODEL_KEYWORDS)


def call_gemini_text(
    prompt: str,
    api_key: str,
    preferred_models: list[str] | None = None,
    timeout_sec: float = 20.0,
    max_per_minute: int = 15,
) -> tuple[bool, str]:
    if not api_key or not str(api_key).strip():
        return False, "尚未設定 Gemini API Key"

    state = getattr(st, "session_state", None) if st is not None else None
    now = time.time()
    if state is not None:
        req_log = state.get("gemini_req_timestamps", [])
        req_log = [t for t in req_log if now - t < 60.0]
        if len(req_log) >= max_per_minute:
            return False, f"已達本 Session 每分鐘 {max_per_minute} 次呼叫上限，請稍後再試"
        req_log.append(now)
        state["gemini_req_timestamps"] = req_log

    candidates = [
        m for m in (preferred_models or ["gemini-3.8-flash"])
        if is_text_generation_model(m)
    ] or ["gemini-3.8-flash"]

    headers = {
        "x-goog-api-key": str(api_key).strip(),
        "Content-Type": "application/json",
    }
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    deadline = time.monotonic() + float(timeout_sec)
    last_err = "未知錯誤"
    for model_name in candidates:
        remaining = deadline - time.monotonic()
        if remaining <= 0.5:
            last_err = f"已達總時限 {timeout_sec:.0f} 秒"
            break
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=min(remaining, 12.0))
            if resp.status_code in (400, 401, 403):
                return False, f"Gemini 驗證或請求錯誤 (HTTP {resp.status_code})，已立即停止重試"
            resp.raise_for_status()
            data = resp.json()
            cands = data.get("candidates") or []
            parts = ((cands[0].get("content") or {}).get("parts") or []) if cands else []
            text_out = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
            if text_out:
                return True, text_out
            last_err = f"模型 {model_name} 回傳空白內容"
        except Exception as exc:
            last_err = f"{model_name}: {exc}"
            continue

    return False, f"Gemini 呼叫失敗：{last_err}"