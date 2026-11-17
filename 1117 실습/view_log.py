"""로그 보기: 누가 누구에게 무엇을 지시했고 무엇이 돌아왔는지 들여쓰기로 출력.
사용법: python view_log.py [로그파일 경로]  (생략하면 가장 최근 로그)"""
import json
import sys

from logger import LOG_DIR


def short(value, limit: int = 100) -> str:
    text = str(value).replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "…"


def describe(e: dict):
    """이벤트 하나를 한 줄 설명으로 바꾼다. 보여줄 필요 없으면 None."""
    who, kind = e["agent"], e["type"]
    if kind == "agent_start":
        label = "사용자 요청" if who == "orchestrator" else "지시서 받음"
        return f"[{who}] 시작 · {label}: {short(e['task'])}"
    if kind == "llm_call":
        u = e["usage"]
        return f"[{who}] 턴{e['turn']} 모델 호출 · 토큰 {u['input']}/{u['output']} · {e['elapsed']}s"
    if kind == "tool_call":
        return f"[{who}] 도구 요청 {e['name']}({short(e['arguments'], 60)})"
    if kind == "tool_result":
        return f"[{who}] 도구 결과 {short(e['result'])}"
    if kind == "agent_end":
        return (f"[{who}] 종료({e['stop_reason']}, {e['turns']}턴, {e['elapsed']}s)"
                f" · 결과: {short(e['result'])}")
    return None  # delegate, agent_result는 agent_start/agent_end와 겹쳐 생략


def show(path) -> None:
    events = [json.loads(line) for line in open(path, encoding="utf-8")]
    start = events[0]["ts"]
    print(f"== {path.name if hasattr(path, 'name') else path} ==")
    for e in events:
        line = describe(e)
        if line:
            indent = "" if e["agent"] == "orchestrator" else "      "  # 서브에이전트는 들여쓰기
            print(f"{e['ts'] - start:5.1f}s {indent}{line}")


def latest_log():
    return max(LOG_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)


if __name__ == "__main__":
    show(sys.argv[1] if len(sys.argv) > 1 else latest_log())
