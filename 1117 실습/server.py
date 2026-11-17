"""웹 서버: 채팅 화면을 내려주고, /api/chat 으로 오케스트레이터 실행 과정을 줄 단위 JSON으로 흘려보낸다."""
import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from orchestrator import run_orchestrator

PORT = 8000
INDEX_HTML = Path(__file__).parent / "web" / "index.html"
SESSIONS: dict = {}  # session_id -> 대화 이력 (메모리에만 보관)
# 화면에 보낼 진행 이벤트: 채팅창 진행 목록(delegate, agent_result)과 조직도·작업 내역용
PROGRESS_TYPES = ("delegate", "agent_result", "agent_start", "agent_end",
                  "llm_call", "tool_call", "tool_result")


def run_job(session_id: str, message: str, q: queue.Queue) -> None:
    """오케스트레이터를 실행하고 이벤트를 큐에 쌓는다 (병렬 스레드가 와도 큐가 순서를 지킨다)."""
    history = SESSIONS.setdefault(session_id, [])

    def on_event(event: dict) -> None:
        if event["type"] in PROGRESS_TYPES:
            # event 안의 type이 덮어쓰지 않도록 나중에 type을 지정한다
            q.put({**event, "type": "progress", "event": event["type"]})

    try:
        text = run_orchestrator(message, on_event=on_event, history=history)
        history += [{"role": "user", "content": message},
                    {"role": "assistant", "content": text}]
        q.put({"type": "final", "text": text})
    except Exception as e:  # 실패해도 서버가 죽지 않고 화면에 오류를 알린다
        q.put({"type": "error", "message": f"{type(e).__name__}: {e}"})


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/":
            return self.send_error(404)
        data = INDEX_HTML.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != "/api/chat":
            return self.send_error(404)
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))  # {session_id, message}
        q: queue.Queue = queue.Queue()
        threading.Thread(target=run_job, daemon=True,
                         args=(body["session_id"], body["message"], q)).start()
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.end_headers()  # 길이를 모르는 스트림이라 Content-Length 없이 보내고 끝나면 연결을 닫는다
        self.stream(q)

    def stream(self, q: queue.Queue) -> None:
        """큐에서 이벤트를 꺼내는 대로 한 줄씩 브라우저로 보낸다."""
        while True:
            item = q.get()
            self.wfile.write((json.dumps(item, ensure_ascii=False) + "\n").encode("utf-8"))
            self.wfile.flush()
            if item["type"] in ("final", "error"):
                return


if __name__ == "__main__":
    print(f"http://127.0.0.1:{PORT} 에서 실행 중 (Ctrl+C로 종료)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
