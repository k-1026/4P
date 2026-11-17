"""5단계 확인용: (1) 오케스트레이터 max_turns=2로 일부러 중단, (2) 도구가 오류를 내는 실행."""
import time

from orchestrator import run_orchestrator
from view_log import latest_log, show

print("===== 1. max_turns=2 로 일부러 중단시킨 실행 =====")
q1 = "대구 골목상권의 점포 수와 폐업률을 조사한 뒤, 소상공인용 3줄 요약문으로 써줘."
print("최종 반환:\n" + run_orchestrator(q1, max_turns=2))
show(latest_log())

time.sleep(30)  # 무료 티어 분당 요청 제한을 피하려고 쉰다

print("\n===== 2. 도구가 오류를 내는 실행 (0으로 나누기) =====")
q2 = ("검토 에이전트에게 이 초안을 검토시켜줘. 초안: '1인당 매출은 총매출 100을 직원 수 0으로 나눈 값이다.' "
      "근거 자료: 총매출 100, 직원 수 0. 계산을 검토해서 결과를 알려줘.")
print("최종 반환:\n" + run_orchestrator(q2))
show(latest_log())
