"""Vercel 서버 함수: POST /api/recommend -> 조율자 + 에이전트의 상의 결과 (JSON)"""
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit

os.environ["TZ"] = "KST-9"        # 서버는 UTC라서 한국 시간으로 (날씨 조회·일기 날짜)
if hasattr(time, "tzset"):
    time.tzset()
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents"))

import phone_app  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def reply(self, status, body):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        # 이 사이트 화면에서 보낸 요청만 받는다
        origin = self.headers.get("Origin")
        host = self.headers.get("x-forwarded-host") or self.headers.get("Host")
        if origin and urlsplit(origin).netloc != host:
            return self.reply(403, {"ok": False, "text": "허용하지 않는 요청이에요."})
        length = int(self.headers.get("Content-Length") or 0)
        if length > phone_app.MAX_BODY:
            return self.reply(413, {"ok": False, "text": "보낸 값이 너무 커요."})
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("JSON 객체가 아니에요")
        except (ValueError, UnicodeDecodeError):
            return self.reply(400, {"ok": False, "text": "보낸 값을 읽지 못했어요."})
        try:
            answer = phone_app.recommend(body)
        except Exception as error:  # 위치 같은 값은 로그에 남기지 않고 종류만
            print(f"recommend 오류: {type(error).__name__}")
            answer = {"ok": False, "text": f"에이전트 실행 중 오류가 났어요: {type(error).__name__}"}
        self.reply(200, answer)
