import streamlit as st
import requests
import time

def get_valid_gemini_models(api_key):
    return ["gemini-3.8-flash"] # Defaulting to the new model specified in requirements

def call_gemini_api(prompt, system_prompt=None):
    if "gemini_requests_this_min" not in st.session_state:
        st.session_state.gemini_requests_this_min = []
    
    current_time = time.time()
    st.session_state.gemini_requests_this_min = [t for t in st.session_state.gemini_requests_this_min if current_time - t < 60]
    if len(st.session_state.gemini_requests_this_min) >= 15:
        raise Exception("已達本機 Gemini 呼叫速率上限，請稍後再試。")

    api_key = st.secrets.get("GEMINI_API_KEY")
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    
    models = get_valid_gemini_models(api_key)
    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            if system_prompt:
                payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
                
            res = requests.post(url, headers=headers, json=payload, timeout=20)
            
            if res.status_code in [400, 401, 403]:
                raise PermissionError(f"Gemini API 驗證失敗 (HTTP {res.status_code})。請檢查金鑰。")
                
            res.raise_for_status()
            st.session_state.gemini_requests_this_min.append(current_time)
            return res.json()
        except requests.exceptions.Timeout:
            continue
        except PermissionError as pe:
            raise pe
    raise Exception("所有可用 Gemini 模型皆請求失敗或超時。")
