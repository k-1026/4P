"""Gemini 호출. 모든 LLM 에이전트가 이 함수 하나를 같이 쓴다.

에이전트마다 다른 건 system(역할 설명)과 prompt뿐이다.
키가 없거나 실패하면 None을 돌려주고, 부른 쪽이 규칙으로 대신한다.
"""
import json
import urllib.request

import config


def ask_json(system: str, prompt: str):
    if not config.GEMINI_KEY:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": config.GEMINI_KEY},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.load(r)
        return json.loads(j["candidates"][0]["content"]["parts"][0]["text"])
    except Exception as e:  # 네트워크 · 한도 · JSON 깨짐 모두 규칙으로 넘긴다
        print(f"  (Gemini 실패, 규칙으로 대신: {e})")
        return None
