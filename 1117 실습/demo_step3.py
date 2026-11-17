"""3단계 확인용: 질문 4종(직접 답변·단일 위임·병렬 위임·순차 위임)으로 오케스트레이터 실행."""
import time

from orchestrator import run_orchestrator

START = time.time()


def printer(event: dict) -> None:
    """어느 에이전트에게 어떤 지시서를 보냈는지, 무엇이 돌아왔는지 출력."""
    t = f"{time.time() - START:5.1f}s"
    if event["type"] == "llm_call" and event["agent"] == "orchestrator":
        print(f"  [{t}] 오케스트레이터 턴 {event['turn']}")
    elif event["type"] == "delegate":
        print(f"  [{t}] → {event['agent']} 에게 지시서: {event['task'][:110]!r}")
    elif event["type"] == "agent_result":
        print(f"  [{t}] ← {event['agent']} 결과 도착 ({len(event['result'])}자)")


QUESTIONS = [
    ("직접 답변", "안녕, 너는 무엇을 할 수 있어?"),
    ("단일 위임", "대구 골목상권의 점포 수를 조사해줘."),
    ("병렬 위임", "대구 골목상권의 점포 수 현황과 외식업 폐업률 동향을 각각 따로 조사해줘."),
    ("순차 위임", "대구 골목상권의 점포 수와 폐업률을 조사한 뒤, 소상공인용 3줄 요약문으로 써줘."),
]

import sys

# 인자로 질문 번호(1~4)를 주면 그것만 실행한다. 예: python demo_step3.py 3 4
picked = [int(a) - 1 for a in sys.argv[1:]] or range(len(QUESTIONS))
for n, (kind, question) in enumerate(QUESTIONS[i] for i in picked):
    if n:
        time.sleep(40)  # 무료 티어 분당 15회 요청 제한을 피하려고 질문 사이에 쉰다
    START = time.time()
    print(f"\n===== [{kind}] {question}")
    print("최종 답변:\n" + run_orchestrator(question, on_event=printer))
