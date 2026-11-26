"""Vercel 서버 함수: /config.js -> 카카오맵 JavaScript 키 (환경 변수 KAKAO_JS_KEY)"""
import json
import os
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        data = f"window.KAKAO_JS_KEY = {json.dumps(os.environ.get('KAKAO_JS_KEY', ''))};\n".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)
