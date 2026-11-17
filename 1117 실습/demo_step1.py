"""1단계 확인용: 두 번 연속 호출해서 두 번째 질문이 첫 답변을 기억하는지 본다."""
import llm

SYSTEM = "너는 재무 분석가다. 한국어로 짧게 답한다."


def show(messages: list) -> None:
    print(f"  [메시지 목록 {len(messages)}개]")
    for m in messages:
        print(f"   - {m['role']}: {m['content'][:60]!r}")


messages = [{"role": "user", "content": "우리 회사 3분기 매출은 120억, 2분기는 100억이야. 3분기 매출만 한 줄로 요약해줘."}]
print("1번째 호출 전")
show(messages)
r1 = llm.chat(SYSTEM, messages)
print("답변:", r1.text, "| 토큰:", r1.usage)

# 모델의 답을 목록에 붙여야 다음 호출에서 '기억'이 된다
messages.append(r1.as_assistant_message())
messages.append({"role": "user", "content": "그럼 전 분기 대비로는 몇 % 늘었어?"})
print("\n2번째 호출 전")
show(messages)
r2 = llm.chat(SYSTEM, messages)
print("답변:", r2.text, "| 토큰:", r2.usage)
