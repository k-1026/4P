"""에이전트 루프: 모델 호출 -> 도구 실행 -> 결과 전달을 모델이 그만할 때까지 반복."""
import time
from concurrent.futures import ThreadPoolExecutor

import llm
from tools import execute_tool


def run_tools(tool_calls: list, emit, execute) -> dict:
    """한 응답에 담긴 도구 요청을 동시에 실행하고, 요청 순서대로 결과를 묶는다."""
    def run_one(call):
        emit({"type": "tool_call", "name": call.name, "arguments": call.arguments})
        result = execute(call.name, call.arguments)
        emit({"type": "tool_result", "name": call.name, "result": result})
        return {"name": call.name, "id": call.id, "result": result}

    with ThreadPoolExecutor(max_workers=4) as pool:  # LLM 호출은 대기가 대부분이라 스레드로 충분
        results = list(pool.map(run_one, tool_calls))  # map은 요청 순서를 유지한다
    return {"role": "tool", "results": results}


def stop_message(reason: str, partial: list) -> str:
    """중단 시 돌려줄 문장: 중단 사유와 그때까지의 도구 결과."""
    done = "\n".join(f"- {r[:300]}" for r in partial) or "- (없음)"
    return f"[작업 중단: {reason}]\n지금까지 받은 결과:\n{done}"


def agent_turns(system, tools, messages, max_turns, emit, execute):
    """루프 본체. (최종 텍스트, 종료 사유, 사용한 턴 수)를 돌려준다."""
    partial = []  # 중단되면 함께 돌려줄 도구 결과 모음
    for turn in range(1, max_turns + 1):
        began = time.time()
        try:
            response = llm.chat(system, messages, tools)
        except Exception as e:  # 타임아웃 등 모델 호출 실패도 예외로 죽지 않는다
            reason = f"모델 호출 실패 ({type(e).__name__}: {e})"
            return stop_message(reason, partial), "llm_error", turn
        emit({"type": "llm_call", "turn": turn, "usage": response.usage,
              "elapsed": round(time.time() - began, 2)})
        messages.append(response.as_assistant_message())
        if not response.tool_calls:  # 도구 요청이 없으면 최종 답변 -> 루프 종료
            return response.text, "done", turn
        tool_message = run_tools(response.tool_calls, emit, execute)
        messages.append(tool_message)  # 결과를 붙여 다음 턴으로
        partial += [r["result"] for r in tool_message["results"]]
    return stop_message(f"최대 {max_turns}턴 도달", partial), "max_turns", max_turns


def run_agent(system: str, tools: list, user_message: str,
              max_turns: int = 10, on_event=None, execute=execute_tool,
              history: list | None = None, name: str = "agent") -> str:
    def emit(event: dict) -> None:  # 모든 이벤트에 에이전트 이름을 붙여 보낸다
        if on_event:
            on_event({"agent": name, **event})

    began = time.time()
    emit({"type": "agent_start", "task": user_message})
    # 이전 대화(history)가 있으면 그 뒤에 새 질문을 붙여 맥락을 유지한다
    messages = list(history or []) + [{"role": "user", "content": user_message}]
    text, reason, turns = agent_turns(system, tools, messages, max_turns, emit, execute)
    emit({"type": "agent_end", "result": text, "stop_reason": reason, "turns": turns,
          "elapsed": round(time.time() - began, 2)})
    return text
