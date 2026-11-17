"""2단계 확인용: (A) 도구 2번 이상 쓰는 루프, (B) 서브에이전트 3개 단독 실행."""
from agent_loop import run_agent
from subagents import SUBAGENTS
from tools import get_specs


def printer(event: dict) -> None:
    """루프가 도는 모습을 턴별로 출력."""
    if event["type"] == "llm_call":
        print(f"  [턴 {event['turn']}] 모델 호출 (토큰 {event['usage']})")
    elif event["type"] == "tool_call":
        print(f"    -> 도구 요청: {event['name']}({event['arguments']})")
    elif event["type"] == "tool_result":
        print(f"    <- 실행 결과: {event['result'][:80]}")


print("=== A. 에이전트 루프 (도구 2회 이상) ===")
answer = run_agent(
    system="너는 도우미다. 계산과 시각은 반드시 도구로 확인한다. 한국어로 짧게 답한다.",
    tools=get_specs(["calculator", "get_current_time"]),
    user_message="지금 몇 시인지 알려주고, 1234 곱하기 56에 789를 더한 값도 계산해줘.",
    on_event=printer,
)
print("최종 답변:", answer)

print("\n=== B. 서브에이전트 단독 실행 ===")
agents = SUBAGENTS
for a in agents.values():
    print(f"- {a.name}: {a.description}")
tasks = {
    "researcher": "대구 골목상권 A의 점포 수와 연간 폐업률을 조사한다. 출처 URL을 함께 보고한다.",
    "writer": "자료: 상권 A 점포 120개, 연간 폐업률 12%. 이 자료만으로 소상공인 대상 3줄 요약문을 쓴다.",
    "reviewer": ("초안: '상권 A는 점포 120개 중 연간 약 10곳이 폐업한다.' "
                 "근거 자료: 상권 A 점포 120개, 연간 폐업률 12%. 초안의 숫자를 검토한다."),
}
for name, task in tasks.items():
    print(f"\n--- {name} ---")
    agent = agents[name]
    print(run_agent(agent.system_prompt, agent.tools, task, on_event=printer))
