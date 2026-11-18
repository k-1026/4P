"""Agentic RAG: 기존 run_agent를 그대로 호출하고, 모델이 search_docs 도구로 스스로 검색해 답한다.
사용: python agentic_rag.py 질문"""
import sys

from agent_loop import run_agent
from tools import get_specs

MAX_TURNS = 7  # 검색 최대 5번 + 최종 답변 1번 + 여유 1번

SYSTEM_PROMPT = """너는 지금 사용된 자료를 근거로 답하는 에이전트야. search_docs 도구로 문서를 찾을 수 있어.
- 일반 상식처럼 문서가 필요 없는 질문은 검색하지 않고 바로 대답한다.
- 검색어는 사용자의 문장을 그대로 쓰지 말고 핵심 키워드로 다시 쓴다. 질문에 주제가 여럿이면 주제마다 따로 검색한다.
- 결과에 답이 없으면 다른 검색어로 다시 찾는다. 같은 검색어를 반복하지 않는다.
- 검색은 최대 5번으로 제한한다.
- 검색된 문서에 있는 내용만을 근거로 답하고, 문장마다 출처 파일명을 괄호로 적는다.
- 끝내 찾지 못한 내용은 추측하지 말고 "문서에서 찾지 못했습니다"라고 답한다."""


def ask(question: str, on_event=None) -> str:
    """질문 하나를 기존 run_agent로 실행한다 (agent_loop.py는 고치지 않는다)."""
    return run_agent(SYSTEM_PROMPT, get_specs(["search_docs"]), question,
                     max_turns=MAX_TURNS, on_event=on_event, name="agentic_rag")


def print_search(event: dict) -> None:
    """모델이 검색할 때마다 검색어를 화면에 보여 준다."""
    if event["type"] == "tool_call":
        print(f"  검색: {event['arguments'].get('query')}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("사용: python agentic_rag.py 질문")
    print("\n답변:\n" + ask(" ".join(sys.argv[1:]), print_search))
