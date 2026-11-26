"""검증 에이전트: 조건 위반 점검.

도구: 규칙 체크리스트 (아래 CHECKS). LLM을 쓰지 않는다 — 'if문이 AI보다 정확한' 일이라서.
가게마다 규칙을 돌려 어긴 가게는 빼고, 남은 가게가 너무 적으면 보드에 반려 사유를 적는다.
오케스트레이터는 그 사유를 읽고 재계획한다.
"""
from collections import Counter

import config
from board import Board

MIN_SCORE = 30


def walk_limit(cond):
    limit = cond.get("walk_limit") or config.DEFAULT_WALK_MIN
    return max(5, limit * 2 // 3) if cond.get("rain") else limit  # 비 오면 덜 걷게


# 규칙 하나 = (코드, 설명, 어겼으면 True). 팀 규칙이 늘면 여기에 한 줄씩 더한다.
CHECKS = [
    ("no_source", "출처 없는 가게 (지어낸 가게 방지: 팀 데이터나 지도 검색에서 온 가게만)",
     lambda c, cond: not c["store"].get("id")),
    ("two_portion", "2인분 이상 가게",
     lambda c, cond: c["store"].get("status") == "two" and not cond.get("inc_two")),
    ("wrong_gu", "다른 구",
     lambda c, cond: bool(cond.get("gu")) and c["store"].get("gu") != cond["gu"]),
    ("over_price", "예산 넘음",
     lambda c, cond: bool(cond.get("max_price")) and (c["store"].get("minP") or 0) > cond["max_price"]),
    ("closed", "지금 영업 안 함",
     lambda c, cond: c["context"].get("open_now") is False),
    ("too_far", "걷기에 너무 멂",
     lambda c, cond: c["context"].get("walk_min") is not None and c["context"]["walk_min"] > walk_limit(cond)),
    ("walk_unknown", "사용자가 거리를 정했는데 위치를 모름",
     lambda c, cond: bool(cond.get("walk_limit")) and c["context"].get("walk_min") is None),
    ("low_score", f"혼밥 지수 {MIN_SCORE} 미만",
     lambda c, cond: (c["score"] or 0) < MIN_SCORE),
]


def run(board: Board):
    cond = board.conditions
    count = Counter()
    passed = []
    for c in board.candidates:
        c["rejected"] = [code for code, _, broke in CHECKS if broke(c, cond)]
        count.update(c["rejected"])
        if not c["rejected"]:
            passed.append(c)

    passed.sort(key=lambda c: (-c["score"], c["context"].get("walk_min") or 999))  # 같은 점수면 가까운 곳 먼저
    board.rejections = []

    if board.mode == "store":
        # 가게 하나를 물어본 경우: 빼지 않고, 걸린 규칙을 그대로 알려 준다 (재계획도 하지 않음)
        board.final = board.candidates
        board.note("검증", f"물어본 가게 점검: {dict(count) or '걸린 규칙 없음'}")
        return True

    board.final = passed
    if len(passed) < config.MIN_RESULTS:
        board.rejections.append({
            "code": "too_few",
            "detail": f"통과 {len(passed)}곳 < 최소 {config.MIN_RESULTS}곳",
            "by_rule": dict(count),  # 어떤 규칙에 많이 걸렸는지 → 재계획 힌트
            "candidates": len(board.candidates),
        })
        board.note("검증", f"반려: {board.rejections[0]['detail']} · 걸린 규칙 {dict(count) or '없음(후보 자체가 적음)'}")
    else:
        board.note("검증", f"통과 {len(passed)}곳 · 걸러 낸 규칙 {dict(count) or '없음'}")
    return not board.rejections
