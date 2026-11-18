"""RAG 평가: 확정한 질문 10개로 검색과 답변이 맞는지 표로 확인한다. 실행: python rag_eval.py"""
import rag

# (유형, 질문, 근거 파일 이름 일부, 검색된 조각에 있어야 할 글자, 답변에 있어야 할 글자, 답변에 있으면 안 되는 글자)
# 답변에 있어야 할 글자가 비어 있으면 '문서에 없음' 유형이라 "없다"는 표현이 있어야 통과한다
CASES = [
    ("단일", "아양기찻길 폐철교(아양철교)의 길이와 폭은?",
     ["야간관광"], ["277m"], ["277m", "3m"], []),
    ("단일", "2025년 9월 대구로페이 할인율을 13%로 올린 뒤 월 판매액은 얼마에서 얼마가 됐나?",
     ["대구로페이"], ["1,708억"], ["785억", "1,708억"], []),
    ("단일", "외국인 관광객 방문지 1위와 그 비율은?",
     ["시장하시죠"], ["83.6%"], ["서문시장", "83.6%"], []),
    ("비교", "대구 음식점 수가 문서마다 다른데, 각각 몇 곳이고 차이는?",
     ["기획서", "종합정리"], ["29,277", "39,439"], ["29,277", "39,439", "10,162"], []),
    ("비교", "착한가격업소가 대구시 자료와 사이트에서 각각 몇 곳인가?",
     ["착한가격", "종합정리"], ["612곳", "499곳"], ["612", "499"], []),
    ("비교", "대구 10미 가게 수가 문서마다 다른 이유는?",
     ["종합정리", "통합본"], ["824곳", "428행"], ["824", "428"], []),
    ("없음", "앞산케이블카 이용요금은 얼마인가?", ["야간관광"], [], [], []),
    ("없음", "2027년 대구로페이 발행 규모와 할인율은?", ["대구로페이"], [], [], []),
    ("없음", "시장하시죠 서비스 개발에 드는 총예산은?", ["시장하시죠"], [], [], []),
    ("없음", "동성로 스파크 옥상 테마파크(스파크랜드)는 언제 개장했나?",
     ["야간관광"], [], [], ["2020"]),
]
NO_WORDS = ("찾을 수 없", "없습니다", "않습니다", "확인되지", "확인하지 못", "찾지 못")  # '문서에 없음'을 뜻하는 표현


def judge(case: tuple, text: str, results: list) -> tuple:
    """(검색: 근거 파일, 검색: 근거 글자, 답변) 세 가지를 O/X로 판정한다."""
    _, _, files, keys, must, banned = case
    sources = " ".join(c["source"] for _, c in results)
    chunk_text = " ".join(c["text"] for _, c in results)
    hit_file = all(f in sources for f in files)
    hit_key = all(k in chunk_text for k in keys)
    if must:  # 답이 있는 질문: 정답 글자가 모두 있어야 한다
        ok = all(m in text for m in must)
    else:  # 답이 없는 질문: '없다'고 말해야 하고, 지어낸 글자가 없어야 한다
        ok = any(w in text for w in NO_WORDS) and not any(b in text for b in banned)
    return hit_file, hit_key, ok


def main() -> None:
    chunks, matrix = rag.load_index()
    print("| # | 유형 | 질문 | 검색:파일 | 검색:숫자 | 답변 | 답변 앞부분 |")
    print("|---|---|---|---|---|---|---|")
    rows = []
    for i, case in enumerate(CASES, 1):
        text, results = rag.answer(case[1], chunks, matrix)
        rows.append(judge(case, text, results))
        mark = ["O" if v else "X" for v in rows[-1]]
        head = text.replace("\n", " ")[:60]
        print(f"| {i} | {case[0]} | {case[1][:22]}… | {mark[0]} | {mark[1]} | {mark[2]} | {head} |", flush=True)
    for n, label in enumerate(["검색(근거 파일)", "검색(근거 숫자)", "답변"]):
        print(f"{label}: {sum(r[n] for r in rows)}/{len(rows)}")


if __name__ == "__main__":
    main()
