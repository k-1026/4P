"""레드팀 관제 서버 (표준 라이브러리만 사용).

실행: python bm/redteam_server.py  →  http://127.0.0.1:8766

- 실행 버튼: 레드팀 3개(investor, customer, competitor)를 동시에 `claude -p`로 실행
- 각 결과는 bm/redteam/<이름>_<시각>.md 에 원문 그대로 저장
- 완료 로그는 bm/redteam/run_log.jsonl 에 누적
- 결정 버튼: 수용/수정은 bm_canvas.md, bm_canvas.html 에 반영을 요청, 반려는 기록만 남기고 무시
"""

import json
import os
import re
import shutil
import subprocess
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BM = ROOT / "bm"
RT = BM / "redteam"
AGENTS = ROOT / ".claude" / "agents"
STATE = RT / "state.json"
LOG = RT / "run_log.jsonl"
DEC = RT / "decisions.json"
MONITOR = BM / "redteam_monitor.html"
NAMES = ["investor", "customer", "competitor"]
CLAUDE = os.environ.get("RT_CLAUDE_CMD") or shutil.which("claude") or "claude"
PORT = int(os.environ.get("RT_PORT", "8766"))

CHILD_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}
LOCK = threading.Lock()
APPLY_LOCK = threading.Lock()  # 캔버스 수정은 한 번에 하나씩

RUN_PROMPT = """대상 파일: bm/bm_canvas.md (현재 상태). 필요하면 같은 폴더의 bm/revenue_option.md, painpoint/painpoint_def.md, ax/risk_check.md, research/data/sources.md 를 읽으세요. 파일은 쓰지 마세요.
지적은 번호, 지적 내용, 근거, 심각도를 적으세요.
마지막에 사람이 결정해야 하는 항목만 아래 형식의 JSON 코드블록으로 한 번 더 출력하세요.
```json
[{"no": 1, "title": "짧은 제목", "proposal": "캔버스에 넣을 구체적 수정안 한 문장"}]
```"""


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path, obj):
    RT.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def append_log(entry):
    RT.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def agent_body(name):
    text = (AGENTS / f"redteam-{name}.md").read_text(encoding="utf-8")
    parts = text.split("---", 2)
    return parts[2].strip() if len(parts) >= 3 else text


def parse_items(text):
    blocks = re.findall(r"```json\s*(.*?)```", text, re.S)
    if not blocks:
        return []
    try:
        data = json.loads(blocks[-1])
        return data if isinstance(data, list) else []
    except Exception:
        return []


def set_agent(name, **fields):
    with LOCK:
        st = read_json(STATE, {"running": False, "agents": {}})
        st.setdefault("agents", {}).setdefault(name, {}).update(fields)
        write_json(STATE, st)


def run_agent(name, run_id):
    set_agent(name, status="running", started=now(), finished=None, items=[], file=None, error=None, run_id=run_id)
    try:
        proc = subprocess.run(
            [CLAUDE, "-p", "--append-system-prompt-file", str(AGENTS / f"redteam-{name}.md"),
             "--allowedTools", "Read", "Glob", "Grep"],
            input=RUN_PROMPT, capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(ROOT), timeout=1200, env=CHILD_ENV,
        )
        out = proc.stdout or ""
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or out)[-500:] or f"exit {proc.returncode}")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = RT / f"{name}_{stamp}.md"
        RT.mkdir(parents=True, exist_ok=True)
        path.write_text(out, encoding="utf-8")  # 원문 그대로 저장
        rel = path.relative_to(ROOT).as_posix()
        items = parse_items(out)
        set_agent(name, status="done", finished=now(), items=items, file=rel)
        append_log({"ts": now(), "run_id": run_id, "agent": name, "status": "done", "file": rel, "items": len(items)})
    except Exception as e:  # noqa: BLE001 - 오류 내용을 그대로 기록
        set_agent(name, status="error", finished=now(), error=str(e)[:500])
        append_log({"ts": now(), "run_id": run_id, "agent": name, "status": "error", "error": str(e)[:300]})


def start_run():
    with LOCK:
        st = read_json(STATE, {})
        if st.get("running"):
            return None
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        write_json(STATE, {"running": True, "run_id": run_id, "started": now(), "finished": None, "agents": {}})
    append_log({"ts": now(), "run_id": run_id, "event": "start", "agents": NAMES})

    def worker():
        threads = [threading.Thread(target=run_agent, args=(n, run_id)) for n in NAMES]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        with LOCK:
            st = read_json(STATE, {})
            st["running"] = False
            st["finished"] = now()
            write_json(STATE, st)
        append_log({"ts": now(), "run_id": run_id, "event": "complete"})

    threading.Thread(target=worker, daemon=True).start()
    return run_id


def set_decision(key, **fields):
    with LOCK:
        data = read_json(DEC, {})
        data.setdefault(key, {}).update(fields)
        write_json(DEC, data)


def apply_to_canvas(key, proposal):
    """수용·수정 항목을 캔버스 파일에 반영 (한 번에 하나씩)."""
    with APPLY_LOCK:
        set_decision(key, status="반영 중", ts=now())
        prompt = (
            "아래 수정안 한 건을 bm/bm_canvas.md 와 bm/bm_canvas.html 에 반영하세요. "
            "해당 칸만 고치고 다른 칸은 건드리지 마세요. 근거 표기(가정값/확인값/결정)를 지키세요. "
            "수정 후 어떤 칸을 고쳤는지 한 줄로만 답하세요.\n\n수정안: " + proposal
        )
        try:
            proc = subprocess.run(
                [CLAUDE, "-p", "--allowedTools", "Read", "Edit"],
                input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace",
                cwd=str(ROOT), timeout=900, env=CHILD_ENV,
            )
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or proc.stdout or "")[-300:])
            set_decision(key, status="반영됨", ts=now(), result=(proc.stdout or "").strip()[-300:])
            append_log({"ts": now(), "event": "canvas_applied", "key": key})
        except Exception as e:  # noqa: BLE001
            set_decision(key, status="오류", ts=now(), error=str(e)[:300])
            append_log({"ts": now(), "event": "canvas_error", "key": key, "error": str(e)[:300]})


def record_decision(body):
    key = body.get("key", "")
    verdict = body.get("verdict", "")
    if not key or verdict not in ("수용", "수정", "반려"):
        return 400, {"error": "key와 verdict(수용/수정/반려)가 필요합니다"}
    base = {"verdict": verdict, "ts": now(), "title": body.get("title", ""), "agent": body.get("agent", ""), "no": body.get("no")}
    if verdict == "반려":
        set_decision(key, status="무시됨", **base)
        append_log({"ts": now(), "event": "decision", "key": key, "verdict": verdict})
        return 200, {"ok": True}
    proposal = body.get("note") if verdict == "수정" else body.get("proposal")
    proposal = (proposal or "").strip()
    if not proposal:
        return 400, {"error": "수정안이 비어 있습니다"}
    set_decision(key, status="대기", proposal=proposal, **base)
    append_log({"ts": now(), "event": "decision", "key": key, "verdict": verdict})
    threading.Thread(target=apply_to_canvas, args=(key, proposal), daemon=True).start()
    return 200, {"ok": True}


def snapshot():
    st = read_json(STATE, {"running": False, "agents": {}})
    decisions = read_json(DEC, {})
    lines = LOG.read_text(encoding="utf-8").splitlines() if LOG.exists() else []
    log = [json.loads(x) for x in lines[-60:] if x.strip()]
    return {"state": st, "decisions": decisions, "log": log}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload, ctype="application/json; charset=utf-8"):
        data = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        if self.path in ("/", "/index.html"):
            self._send(200, MONITOR.read_bytes(), "text/html; charset=utf-8")
        elif self.path.startswith("/api/state"):
            self._send(200, snapshot())
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        body = json.loads(raw.decode("utf-8", errors="replace") or "{}")
        if self.path == "/api/run":
            run_id = start_run()
            if run_id is None:
                self._send(409, {"error": "이미 실행 중입니다"})
            else:
                self._send(200, {"run_id": run_id})
        elif self.path == "/api/decision":
            code, payload = record_decision(body)
            self._send(code, payload)
        else:
            self._send(404, {"error": "not found"})

    def log_message(self, fmt, *args):  # 콘솔 출력 줄이기
        pass


if __name__ == "__main__":
    print(f"레드팀 관제: http://127.0.0.1:{PORT}  (Ctrl+C로 종료)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
