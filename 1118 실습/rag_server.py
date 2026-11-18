"""채팅 웹 서버: 화면을 내려주고, /api/chat 의 mode에 따라
RAG(문서 질의응답) · Agentic RAG(스스로 검색) · 멀티에이전트 중 하나로 답한다."""
import json
import queue
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import rag

# 에이전트 코드는 1117 실습 폴더에 있다 (수정하지 않고 그대로 불러 쓴다)
sys.path.insert(0, str(rag.ROOT / "1117 실습"))
import agentic_rag  # noqa: E402  (Agentic RAG: run_agent + search_docs)
import server as agent_server  # noqa: E402  (멀티에이전트: run_job = 오케스트레이터 실행)

PORT = 8001  # 8000은 기존 멀티에이전트 서버가 쓰므로 겹치지 않게 8001
INDEX_HTML = rag.ROOT / "rag_web" / "index.html"
CHUNKS, MATRIX = rag.load_index()  # 서버를 켤 때 색인을 한 번만 읽는다
PROGRESS_TYPES = ("agent_start", "agent_end", "llm_call", "tool_call", "tool_result")


def make_reply(message: str) -> str:
    """RAG 모드: 질문 -> 답변 + 검색된 조각 출처 목록(마크다운)."""
    text, results = rag.answer(message, CHUNKS, MATRIX)
    sources = "\n".join(f"- {c['source']} #{c['chunk_id']} (유사도 {s:.2f})" for s, c in results)
    return f"{text}\n\n**출처 (검색된 조각)**\n{sources}"


def run_agentic(message: str, q: queue.Queue) -> None:
    """Agentic RAG를 실행하고 진행 이벤트와 최종 답을 큐에 쌓는다."""
    def on_event(event: dict) -> None:
        if event["type"] in PROGRESS_TYPES:
            q.put({**event, "type": "progress", "event": event["type"]})
    try:
        q.put({"type": "final", "text": agentic_rag.ask(message, on_event)})
    except Exception as e:  # 실패해도 서버가 죽지 않고 화면에 오류를 알린다
        q.put({"type": "error", "message": f"{type(e).__name__}: {e}"})


class Handler(BaseHTTPRequestHandler):
    def send_body(self, content_type: str, data: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path != "/":
            return self.send_error(404)
        self.send_body("text/html; charset=utf-8", INDEX_HTML.read_bytes())

    def do_POST(self):
        if self.path != "/api/chat":
            return self.send_error(404)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        mode = body.get("mode")
        if mode in ("agent", "multirag"):  # 멀티에이전트 / Multi Agentic RAG (같은 오케스트레이터, 에이전트 6종 사용)
            job = (agent_server.run_job, (body["session_id"], body["message"]))
        elif mode == "agentic":  # Agentic RAG
            job = (run_agentic, (body["message"],))
        else:  # RAG
            return self.reply_rag(body["message"])
        q: queue.Queue = queue.Queue()
        threading.Thread(target=job[0], daemon=True, args=(*job[1], q)).start()
        self.stream_queue(q)

    def reply_rag(self, message: str) -> None:
        try:
            item = {"type": "final", "text": make_reply(message)}
        except Exception as e:  # 실패해도 서버가 죽지 않고 화면에 오류를 알린다
            item = {"type": "error", "message": f"{type(e).__name__}: {e}"}
        # 화면은 한 줄짜리 JSON을 받는 형식(NDJSON)이라 한 줄로 보낸다
        self.send_body("application/x-ndjson; charset=utf-8",
                       (json.dumps(item, ensure_ascii=False) + "\n").encode("utf-8"))

    def stream_queue(self, q: queue.Queue) -> None:
        """진행 이벤트를 큐에서 꺼내는 대로 한 줄씩 흘려보낸다."""
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.end_headers()  # 길이를 모르는 스트림이라 Content-Length 없이 보내고 끝나면 연결을 닫는다
        while True:
            item = q.get()
            self.wfile.write((json.dumps(item, ensure_ascii=False) + "\n").encode("utf-8"))
            self.wfile.flush()
            if item["type"] in ("final", "error"):
                return


if __name__ == "__main__":
    print(f"http://127.0.0.1:{PORT} 에서 실행 중 (Ctrl+C로 종료)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
