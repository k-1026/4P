"""평가: 테스트 질문을 모두 실행하고, 로그에서 실제 호출된 에이전트를 뽑아 기대값과 비교한다."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # 상위 폴더의 모듈을 import하기 위해

from orchestrator import run_orchestrator  # noqa: E402
from view_log import latest_log  # noqa: E402

CASES_FILE = Path(__file__).parent / "cases.json"
PAUSE_SEC = 20  # 무료 티어 분당 요청 제한을 피하려고 질문 사이에 쉰다


def summarize(log_path) -> dict:
    """로그 한 건에서 실제 호출된 에이전트, 턴 수, 토큰, 소요 시간을 뽑는다."""
    events = [json.loads(line) for line in open(log_path, encoding="utf-8")]
    called = sorted(e["agent"] for e in events
                    if e["type"] == "agent_start" and e["agent"] != "orchestrator")
    end = next(e for e in events if e["type"] == "agent_end" and e["agent"] == "orchestrator")
    tokens = sum((e["usage"]["input"] or 0) + (e["usage"]["output"] or 0)
                 for e in events if e["type"] == "llm_call")
    return {"actual": called, "turns": end["turns"], "tokens": tokens,
            "elapsed": end["elapsed"], "stop": end["stop_reason"], "log": log_path.name}


def run_case(case: dict) -> dict:
    run_orchestrator(case["question"])
    result = summarize(latest_log())  # 방금 실행한 로그가 가장 최근 파일
    # 모델 호출 실패 등으로 중단된 실행은 판단이 없었으므로 채점하지 않는다
    result["valid"] = result["stop"] == "done"
    result["ok"] = result["valid"] and result["actual"] == sorted(case["expected"])
    return result


def join(agents: list) -> str:
    return ",".join(agents) or "-"


def print_table(cases: list, results: list) -> None:
    print("| # | 유형 | 질문 | 기대 | 실제 | 일치 | 턴 | 토큰 | 시간(s) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for i, (c, r) in enumerate(zip(cases, results), 1):
        q = c["question"][:28] + ("…" if len(c["question"]) > 28 else "")
        mark = "오류" if not r["valid"] else ("O" if r["ok"] else "X")
        print(f"| {i} | {c['type']} | {q} | {join(sorted(c['expected']))} | {join(r['actual'])} "
              f"| {mark} | {r['turns']} | {r['tokens']} | {r['elapsed']} |")
    valid = [r for r in results if r["valid"]]
    hit = sum(r["ok"] for r in valid)
    rate = f"{hit / len(valid):.0%}" if valid else "-"
    print(f"\n라우팅 정확도: {hit}/{len(valid)} = {rate} (오류로 채점 제외 {len(results) - len(valid)}건)")


if __name__ == "__main__":
    cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    results = []
    for i, case in enumerate(cases):
        if i:
            time.sleep(PAUSE_SEC)
        results.append(run_case(case))
        print(f"[{i + 1}/{len(cases)}] 완료: {case['type']} -> {join(results[-1]['actual'])}", flush=True)
    print()
    print_table(cases, results)
    print("\n로그:", ", ".join(r["log"] for r in results))
