"""오케스트레이터: call_agent 하나만 도구로 가진 run_agent. 서브에이전트 호출 = 도구 호출."""
import threading

from agent_loop import run_agent
from config import MAX_CALL_AGENT, MAX_TURNS_ORCHESTRATOR, MAX_TURNS_SUBAGENT
from logger import make_logger, new_run_id
from subagents import SUBAGENTS

# 에이전트 이름과 설명 목록을 오케스트레이터 프롬프트에 자동으로 끼워 넣는다
AGENT_LIST = "\n".join(f"- {a.name}: {a.description}" for a in SUBAGENTS.values())

ORCHESTRATOR_PROMPT = """너는 여러 전문 에이전트를 지휘하는 오케스트레이터다.
사용자 요청을 분석해 적임자에게 맡기고, 돌아온 결과를 종합해 답하는 것이 역할이다.

[사용 가능한 에이전트]
{agent_list}

[판단 절차]
1. 사용자 요청의 최종 목표와 필요한 하위 작업을 파악한다.
2. 인사나 간단한 질문처럼 에이전트가 필요 없는 요청은 위임하지 않고 직접 답한다.
   단, 사실·통계·수치를 조사해야 하는 요청은 직접 답하지 말고 반드시 조사 에이전트에게 위임한다.
3. 하위 작업마다 가장 적합한 에이전트를 고른다.
   맞는 에이전트가 없으면 억지로 맡기지 말고 그 사실을 사용자에게 말한다.
4. 서로 독립적인 작업은 한 번에 동시에 지시한다.
   예: 서로 다른 두 주제를 각각 조사하라는 요청이면, 한 응답 안에서 call_agent를 두 번 함께 호출한다.
   앞 작업의 결과가 필요한 작업은 그 결과를 받은 뒤에 지시한다.
   예: 조사한 뒤 요약문을 쓰라는 요청이면, 조사 결과를 받은 뒤 그 결과를 지시서에 담아 작성 에이전트를 부른다.
5. 조사한 내용을 요약문·보고서 등 문서로 작성해 달라는 요청은 조사 → 작성 → 검토 세 단계를 순서대로 모두 거친다.
   작성 결과를 받은 뒤에는 반드시 검토 에이전트를 부르고, 지시서에 작성된 초안과 조사 근거를 함께 담는다.
   검토에서 문제가 지적되면 최종 답변에 반영하거나 사용자에게 알린다.

[업무 지시서 작성 규칙]
에이전트는 이 대화를 전혀 보지 못한다. 지시서만 읽고 일할 수 있도록 다음을 모두 적는다.
- 목표: 무엇을, 왜 하는지
- 배경: 사용자가 준 관련 정보와 제약 조건, 앞선 에이전트의 결과 중 필요한 부분
- 범위: 해야 할 것과 하지 말아야 할 것
- 출력 형식: 결과, 근거, 불확실한 점

[결과 종합 규칙]
- 결과물을 나열하지 말고 사용자 질문에 대한 하나의 답으로 다시 쓴다.
- 에이전트 간 결과가 충돌하면 근거를 비교해 판단한다. 판단할 수 없으면 충돌 사실을 그대로 알린다.
- 결과가 부족하면 무엇이 부족한지 적은 보완 지시를 한 번 더 내린다. 같은 지시를 되풀이하지 않는다.
- 에이전트가 확인하지 못했다고 보고한 내용을 사실처럼 쓰지 않는다.
- 에이전트 보고에 없는 원인, 해석, 수치를 덧붙이지 않는다.
- 에이전트가 실패했거나 작업이 중단되었으면 어디까지 되었는지 사용자에게 알린다.
- 모의 검색 결과 등 실제가 아니라고 표시된 자료도 있는 값으로 작업을 이어가되, 최종 답변에 모의 데이터라는 사실을 알린다.
""".format(agent_list=AGENT_LIST)

# 오케스트레이터가 가진 유일한 도구 (agent_name은 enum으로 등록된 이름만 허용)
CALL_AGENT_TOOL = {
    "name": "call_agent",
    "description": "전문 에이전트에게 업무를 위임하고 결과를 받는다.",
    "parameters": {"type": "object", "properties": {
        "agent_name": {"type": "string", "enum": list(SUBAGENTS)},
        "task": {"type": "string", "description": "자기완결적인 업무 지시서"}},
        "required": ["agent_name", "task"]},
}


def call_agent(agent_name: str, task: str, emit) -> str:
    """서브에이전트를 새 루프로 실행하고 최종 답변만 돌려준다."""
    emit({"type": "delegate", "agent": agent_name, "task": task})
    agent = SUBAGENTS[agent_name]
    # 서브에이전트에는 call_agent를 주지 않는다 (위임 깊이 1단계)
    result = run_agent(agent.system_prompt, agent.tools, task,
                       max_turns=MAX_TURNS_SUBAGENT, on_event=emit, name=agent_name)
    emit({"type": "agent_result", "agent": agent_name, "result": result})
    return result


def make_executor(emit):
    """오케스트레이터 루프가 call_agent 요청을 실행할 때 쓰는 함수."""
    count = [0]  # 이번 요청에서 call_agent를 부른 횟수
    lock = threading.Lock()

    def execute(name: str, arguments: dict) -> str:
        with lock:
            count[0] += 1
            used = count[0]
        if used > MAX_CALL_AGENT:  # 호출 상한 초과: 위임하지 않고 모델에게 알린다
            return (f"오류: 요청당 call_agent 호출 상한({MAX_CALL_AGENT}회)을 넘었다. "
                    "더 위임하지 말고 지금까지 받은 결과로 답하라.")
        try:
            return call_agent(arguments["agent_name"], arguments["task"], emit)
        except Exception as e:
            # 예외로 죽지 않고 오류를 결과로 돌려줘 모델이 판단하게 한다
            return f"오류: {type(e).__name__}: {e}"
    return execute


def run_orchestrator(user_message: str, on_event=None, history=None,
                     max_turns: int = MAX_TURNS_ORCHESTRATOR) -> str:
    log = make_logger(new_run_id())  # 실행마다 로그 파일 하나

    def emit(event: dict) -> None:  # 모든 이벤트를 로그에 남기고 호출자에게도 전달
        log(event)
        if on_event:
            on_event(event)

    return run_agent(ORCHESTRATOR_PROMPT, [CALL_AGENT_TOOL], user_message,
                     max_turns=max_turns, on_event=emit, execute=make_executor(emit),
                     history=history, name="orchestrator")
