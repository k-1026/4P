"""에이전트 대시보드 서버 (표준 라이브러리 + openpyxl).

실행:  python dashboard_server.py   ->  http://127.0.0.1:8766

- GET  /               dashboard.html
- GET  /api/state      에이전트 상태, run.log 내용, 시나리오별 월 손익, 검토 지적사항
- POST /api/start      {"mode": "demo" | "real"}  에이전트 실행
- POST /api/stop       실행 중지

시연(demo): 엑셀 값을 읽어 에이전트 4개가 순서대로 일하는 모습을 흉내 내고,
            기록은 run.log.demo.json 에만 남긴다. (run.log.json 은 건드리지 않음)
실제(real): `claude -p --agent <이름>` 을 순서대로 실행한다. 기록은 에이전트가
            run.log.json 에 직접 추가한다.
"""
import json
import shutil
import subprocess
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                       # 프로젝트 루트 (CLAUDE.md, .claude 가 있는 곳)
XLSX = HERE / "market_model_case_student_정리.xlsx"
REAL_LOG = HERE / "run.log.json"
DEMO_LOG = HERE / "run.log.demo.json"
PORT = 8766

AGENTS = [
    {"name": "researcher", "label": "시장조사", "step": "1 자료 수집"},
    {"name": "model-simulator", "label": "수익모델 계산", "step": "5 손익"},
    {"name": "competitor-analyzer", "label": "경쟁사 분석", "step": "8 경쟁·포지셔닝"},
    {"name": "reviewer", "label": "검토 및 심사", "step": "9 종합 판정"},
]

LOCK = threading.Lock()
STATE = {
    "running": False,
    "mode": None,
    "started": None,
    "agents": {a["name"]: {"status": "대기", "events": []} for a in AGENTS},
    "message": "",
}
STOP = threading.Event()
PROC = {"p": None}


# ---------------------------------------------------------------- 엑셀 읽기
_xl_cache = {"mtime": None, "data": None}


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_excel():
    """엑셀(저장된 계산값)에서 대시보드에 필요한 값을 읽는다."""
    if not XLSX.exists():
        return {"error": f"엑셀 파일이 없습니다: {XLSX.name}"}
    mtime = XLSX.stat().st_mtime
    if _xl_cache["mtime"] == mtime and _xl_cache["data"]:
        return _xl_cache["data"]
    try:
        import openpyxl

        wb = openpyxl.load_workbook(XLSX, data_only=True)
        s = wb["손익"]
        cols = "BCDEFG"
        pnl = []
        for c in cols:
            pnl.append({
                "label": str(s[f"{c}3"].value),
                "monthly_profit": s[f"{c}12"].value,
                "breakeven_daily": s[f"{c}15"].value,
                "daily_orders": s[f"{c}5"].value,
                "cell": f"손익!{c}12",
            })
        u = wb["단위경제"]
        unit = [{"label": str(u[f"{c}3"].value), "contribution_after_picking": u[f"{c}14"].value,
                 "cell": f"단위경제!{c}14"} for c in cols]
        p = wb["포지셔닝"]
        tags = {"F": 0, "I": 0, "U": 0}
        for r in range(14, 20):
            for c in ("D", "F"):
                t = p[f"{c}{r}"].value
                if t in tags:
                    tags[t] += 1
        z = wb["자료"]
        rows = [r for r in range(4, 20) if z[f"B{r}"].value is not None]
        with_src = [r for r in rows if z[f"E{r}"].value and z[f"F{r}"].value]
        dong_sum = sum(z[f"B{r}"].value for r in range(22, 37))
        data = {
            "pnl": pnl,
            "unit": unit,
            "positioning": {"same_speed": p["C20"].value, "gap": p["C21"].value, "tags": tags},
            "source": {"rows": len(rows), "with_source": len(with_src),
                       "dong_sum": dong_sum, "B4": z["B4"].value},
            "file": XLSX.name,
        }
        _xl_cache.update(mtime=mtime, data=data)
        return data
    except Exception as e:  # noqa: BLE001
        return {"error": f"엑셀을 읽지 못했습니다: {e}"}


# ---------------------------------------------------------------- 로그 읽기/쓰기
def load_log(path):
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d.get("runs", []) if isinstance(d, dict) else []
    except Exception:  # 파일이 없거나 쓰는 도중이면 빈 목록
        return []


def append_demo(record):
    try:
        d = json.loads(DEMO_LOG.read_text(encoding="utf-8"))
    except Exception:
        d = {"meta": {"title": "시연용 로그 (실제 기록 아님)"}, "runs": []}
    d["runs"].append(record)
    DEMO_LOG.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def event(agent, text):
    with LOCK:
        STATE["agents"][agent]["events"].append({"t": datetime.now().strftime("%H:%M:%S"), "text": text})
        STATE["agents"][agent]["events"] = STATE["agents"][agent]["events"][-30:]


def set_status(agent, status):
    with LOCK:
        STATE["agents"][agent]["status"] = status


def won(v):
    return f"{v:,.0f}원" if isinstance(v, (int, float)) else str(v)


# ---------------------------------------------------------------- 시연 모드
def demo_records(x, run_no):
    """엑셀 값에 규칙을 기계적으로 적용해 기록을 만든다 (시연용)."""
    pnl, unit = x["pnl"], x["unit"]
    src = x["source"]
    neg = [p for p in pnl if isinstance(p["monthly_profit"], (int, float)) and p["monthly_profit"] < 0]
    unreach = [p for p in pnl if not isinstance(p["breakeven_daily"], (int, float))]
    neg_unit = [u for u in unit if isinstance(u["contribution_after_picking"], (int, float))
                and u["contribution_after_picking"] < 0]
    base = {p["label"]: p for p in pnl}
    tags = x["positioning"]["tags"]
    ts = now()
    recs = {}
    recs["researcher"] = {
        "step": "1 자료 수집", "status": "통과" if src["dong_sum"] == src["B4"] else "미통과",
        "inputs": ["자료!B4:G19", "자료!A22:B36"],
        "outputs": [{"cell": "자료!B4", "value": src["B4"], "note": "15개 동 세대 합계"}],
        "checks": [
            {"item": "모든 자료에 출처·URL 있음", "result": "통과" if src["rows"] == src["with_source"] else "미통과",
             "evidence": f"{src['with_source']}/{src['rows']}행"},
            {"item": "동별 합계 = 자료!B4", "result": "통과" if src["dong_sum"] == src["B4"] else "미통과",
             "evidence": f"합 {src['dong_sum']:,} / B4 {src['B4']:,}"},
        ],
        "assumptions": [], "issues": ["반올림·추산 값(상품매출, 시장 규모 등)은 원문 확인 필요"],
        "next": "2 가정 설정",
    }
    recs["model-simulator"] = {
        "step": "5 손익", "status": "통과",
        "inputs": ["단위경제!B14:G14", "시장규모!B16:D16", "가정!C5:E49"],
        "outputs": [{"cell": p["cell"], "value": p["monthly_profit"], "note": p["label"] + " 월 영업손익"} for p in pnl],
        "checks": [{"item": "시나리오 6개 모두 계산됨", "result": "통과", "evidence": "손익!B12:G12"}],
        "assumptions": ["선택 비율·월 주문 횟수·객단가 등 구분이 '가정'인 값 사용"],
        "issues": [f"{p['label']}: 월 손익 {won(p['monthly_profit'])} (적자)" for p in neg]
                  + [f"{p['label']}: 손익분기 도달 불가" for p in unreach],
        "next": "6 계단표",
    }
    recs["competitor-analyzer"] = {
        "step": "8 경쟁·포지셔닝", "status": "통과",
        "inputs": ["포지셔닝!A13:G21", "경쟁비교!A3:D10"],
        "outputs": [
            {"cell": "포지셔닝!C20", "value": x["positioning"]["same_speed"], "note": "같은 즉시성 점수 경쟁자 수"},
            {"cell": "포지셔닝!C21", "value": x["positioning"]["gap"], "note": "가장 가까운 직접 경쟁자와 점수 차이"},
        ],
        "checks": [{"item": "태그 [F]/[I]/[U] 표시", "result": "통과",
                    "evidence": f"F {tags['F']}, I {tags['I']}, U {tags['U']}"}],
        "assumptions": [],
        "issues": [f"점수 근거 중 확인되지 않은 항목(U) {tags['U']}건, 해석(I) {tags['I']}건"]
                  + [f"같은 즉시성 점수의 경쟁자 {x['positioning']['same_speed']}곳: 속도로는 차별되지 않음"],
        "next": "9 종합 판정",
    }
    # 판정: playbook 단계 9 기본 제안 기준을 기계적으로 적용 (시연)
    base_pnl = [p for p in pnl if "기준" in p["label"]]
    base_loss = any(p["monthly_profit"] < 0 for p in base_pnl)
    verdict = "부" if neg_unit and len(neg_unit) == len(unit) else ("조건부 시행" if base_loss or neg else "가")
    recs["reviewer"] = {
        "step": "9 종합 판정", "status": "보류" if neg or unreach else "통과",
        "inputs": ["run-1~3 기록", "손익!B12:G16", "단위경제!B14:G14"],
        "outputs": [{"cell": "-", "value": verdict, "note": "시연: playbook 단계 9 기본 기준을 기계적으로 적용한 예. 실제 판정 아님"}],
        "checks": [
            {"item": "세 시나리오·두 방안 모두 포함", "result": "통과", "evidence": "손익!B3:G3"},
            {"item": "불리한 숫자가 지적사항에 포함됨", "result": "통과" if neg else "해당 없음", "evidence": f"적자 {len(neg)}건"},
        ],
        "assumptions": ["판정 기준은 playbook 기본 제안(팀 합의 전)"],
        "issues": (
            [f"[적자] {p['label']} 월 영업손익 {won(p['monthly_profit'])} ({p['cell']})" for p in neg]
            + [f"[도달 불가] {p['label']} 손익분기 ({p['cell'].replace('12', '15')})" for p in unreach]
            + [f"[공헌이익 음수] {u['label']} 피킹 후 공헌이익 {won(u['contribution_after_picking'])} ({u['cell']})"
               for u in neg_unit]
            + ["[확인내용] 핵심 가정(선택 비율 등)의 검증 계획이 가정 시트에 없음"]
        ),
        "next": "사용자 승인 대기 (승인은 사용자만 한다)",
    }
    out = []
    for i, a in enumerate(AGENTS):
        r = recs[a["name"]]
        out.append({"id": f"demo-{run_no + i:03d}", "agent": a["name"], "timestamp": ts, **r})
    return {r["agent"]: r for r in out}


DEMO_STEPS = {
    "researcher": ["playbook 단계 1 읽는 중", "자료 시트 16개 항목 점검", "출처·URL 누락 확인"],
    "model-simulator": ["playbook 단계 2~7 읽는 중", "가정 시트에서 시나리오 6개 읽기", "월 손익·손익분기 계산 확인"],
    "competitor-analyzer": ["playbook 단계 8 읽는 중", "경쟁 대안 4층 분류 확인", "[F]/[I]/[U] 태그 세는 중"],
    "reviewer": ["playbook 단계 9 읽는 중", "단계별 타당성 확인 대조", "불리한 숫자 누락 점검"],
}


def run_demo():
    x = read_excel()
    if "error" in x:
        with LOCK:
            STATE["message"] = x["error"]
        return
    DEMO_LOG.write_text(json.dumps({"meta": {"title": "시연용 로그 (실제 기록 아님)", "created": now()},
                                    "runs": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    recs = demo_records(x, 1)
    for a in AGENTS:
        if STOP.is_set():
            return
        n = a["name"]
        set_status(n, "작업 중")
        for line in DEMO_STEPS[n]:
            event(n, line)
            for _ in range(8):          # 약 1.6초
                if STOP.is_set():
                    return
                time.sleep(0.2)
        append_demo(recs[n])
        event(n, f"기록 추가: {recs[n]['id']} ({recs[n]['status']})")
        set_status(n, "완료")


# ---------------------------------------------------------------- 실제 모드
PROMPT = (
    "1116 실습/playbook.md를 먼저 읽고 {step} 단계를 수행해라. "
    "대상 엑셀은 `1116 실습/market_model_case_student_정리.xlsx` 이며 읽기 전용으로만 쓴다(수정 금지). "
    "끝나면 `1116 실습/run.log.json`의 runs 배열에 CLAUDE.md의 '단계별 실행 로그' 형식으로 기록 1건만 추가해라. "
    "다른 파일은 수정하지 마라. 불리한 숫자는 issues에 반드시 적어라."
)


def run_real():
    exe = shutil.which("claude")
    if not exe:
        with LOCK:
            STATE["message"] = "claude 명령을 찾지 못했습니다."
        return
    for a in AGENTS:
        if STOP.is_set():
            return
        n = a["name"]
        set_status(n, "작업 중")
        event(n, "claude -p 실행 시작")
        try:
            p = subprocess.Popen(
                [exe, "-p", PROMPT.format(step=a["step"]), "--agent", n, "--permission-mode", "acceptEdits"],
                cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace")
        except Exception as e:  # noqa: BLE001
            event(n, f"실행 실패: {e}")
            set_status(n, "오류")
            return
        PROC["p"] = p
        for line in p.stdout:
            line = line.strip()
            if line:
                event(n, line[:300])
            if STOP.is_set():
                break
        if STOP.is_set():
            try:
                p.terminate()
            except Exception:
                pass
            return
        p.wait()
        set_status(n, "완료" if p.returncode == 0 else "오류")
        event(n, f"종료 코드 {p.returncode}")
        if p.returncode != 0:
            return


def worker(mode):
    try:
        (run_demo if mode == "demo" else run_real)()
    finally:
        with LOCK:
            STATE["running"] = False
            if STOP.is_set():
                STATE["message"] = "사용자가 중지함"
            for n, a in STATE["agents"].items():
                if a["status"] == "작업 중":
                    a["status"] = "중지됨"
                    a["events"].append({"t": datetime.now().strftime("%H:%M:%S"), "text": "사용자가 중지함"})


def start(mode):
    with LOCK:
        if STATE["running"]:
            return False, "이미 실행 중입니다."
        STOP.clear()
        STATE.update(running=True, mode=mode, started=now(), message="")
        for a in STATE["agents"].values():
            a.update(status="대기", events=[])
    threading.Thread(target=worker, args=(mode,), daemon=True).start()
    return True, "시작"


def stop():
    STOP.set()
    p = PROC.get("p")
    if p and p.poll() is None:
        try:
            p.terminate()
        except Exception:
            pass
    return True, "중지 요청"


# ---------------------------------------------------------------- HTTP
def build_state():
    with LOCK:
        snap = json.loads(json.dumps(STATE))
    mode = snap["mode"] or "demo"
    runs = load_log(DEMO_LOG if mode == "demo" else REAL_LOG)
    if not snap["mode"]:
        runs = load_log(REAL_LOG)
        mode = "real"
    reviewer = [r for r in runs if r.get("agent") == "reviewer"]
    issues = []
    for r in reviewer:
        for i in r.get("issues", []):
            issues.append({"run": r.get("id"), "text": i})
    all_issues = [{"run": r.get("id"), "agent": r.get("agent"), "text": i}
                  for r in runs for i in r.get("issues", []) if r.get("agent") != "reviewer"]
    return {
        "running": snap["running"], "mode": snap["mode"], "log_mode": mode, "message": snap["message"],
        "agents": [{**a, **snap["agents"][a["name"]]} for a in AGENTS],
        "runs": runs, "excel": read_excel(),
        "review_issues": issues, "other_issues": all_issues,
        "log_file": "run.log.demo.json" if mode == "demo" else "run.log.json",
        "server_time": now(),
    }


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):  # 콘솔 조용히
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        b = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path in ("/", "/dashboard.html"):
            self._send(200, (HERE / "dashboard.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path.startswith("/api/state"):
            self._send(200, json.dumps(build_state(), ensure_ascii=False))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            body = {}
        if self.path == "/api/start":
            mode = body.get("mode") if body.get("mode") in ("demo", "real") else "demo"
            ok, msg = start(mode)
        elif self.path == "/api/stop":
            ok, msg = stop()
        else:
            return self._send(404, json.dumps({"error": "not found"}))
        self._send(200, json.dumps({"ok": ok, "message": msg}, ensure_ascii=False))


if __name__ == "__main__":
    print(f"대시보드: http://127.0.0.1:{PORT}  (종료: Ctrl+C)")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
