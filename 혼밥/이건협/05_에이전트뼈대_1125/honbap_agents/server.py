"""탐색 에이전트를 눈으로 보는 작은 사이트.

    python server.py      → 브라우저에서 http://localhost:8765

키(.env)는 이 서버 안에서만 쓰고 브라우저로 보내지 않는다.
보여 주는 범위: 이름 꺼내기 → 팀 데이터 확인 → 탐색(카카오) → 탐색 결과. 다른 에이전트는 돌리지 않는다.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import store_lookup as sl
from agents import explore
from agents.honbap import LABEL
from board import Board, new_candidate

PORT = 8765
PAGE = Path(__file__).parent / "web" / "index.html"


def card(c: dict) -> dict:
    s, m = c["store"], c["map"] or {}
    return {
        "name": s["name"], "gu": s.get("gu", ""), "addr": s.get("addr", ""),
        "category": (m.get("category") or s.get("fd") or "").replace(" > ", " › "),
        "status": s.get("status", "unk"), "status_label": LABEL.get(s.get("status"), "1인분 확인 안 됨"),
        "why": s.get("why", ""), "found_by": c["found_by"], "in_team": c["in_team"], "link": c["link"],
        "x": m.get("x"), "y": m.get("y"), "url": m.get("url", ""),
    }


def ask(text: str) -> dict:
    board = Board(request=text)
    name, gu, intent = sl.detect_store(text)
    board.intent = intent or ""
    out = {"text": text, "name": name, "gu": gu, "intent": intent, "team": [], "explore": None,
           "outcome": "", "ask": "", "candidates": [], "log": board.log}

    if not name:
        out["outcome"] = "not_name"
        return out

    hits = sl.find_team_by_name(name, gu)
    out["team"] = [{"name": r["name"], "addr": r.get("addr", "")} for r in hits]

    if len(hits) == 1:
        board.note("오케스트레이터", f"'{name}'은(는) 팀 데이터에 있음 → 탐색 건너뜀")
        c = new_candidate(hits[0], sl.locate_team_store(hits[0]))
        out.update(outcome="team", candidates=[card(c)])
    elif len(hits) > 1:
        board.note("오케스트레이터", f"'{name}'이(가) 팀 데이터에 {len(hits)}곳 → 어느 가게인지 되물음")
        cands = [new_candidate(r) for r in hits]
        out.update(outcome="ambiguous", ask=explore._ask_text(name, cands), candidates=[card(c) for c in cands])
    else:
        board.note("오케스트레이터", f"'{name}'은(는) 팀 데이터에 없음 → 탐색 에이전트에 맡김")
        result = explore.find_store(board, name, gu)
        out["explore"] = result
        out.update(outcome=result, ask=board.ask, candidates=[card(c) for c in board.candidates])
    return out


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/ask":
            return self._send(404, b"not found", "text/plain")
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            text = str(body.get("text", "")).strip()[:100]
            data = ask(text) if text else {"error": "문장을 입력해 주세요"}
            self._send(200, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")
        except Exception as e:
            self._send(500, json.dumps({"error": str(e)}, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"탐색 에이전트 사이트: http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
