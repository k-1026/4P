"""혼밥 분석 에이전트: 혼밥 지수(0~100) 내기.

도구: 팀 1인분 판정(바탕 점수) + 카카오 블로그 검색(가산·감산)
LLM: 블로그 요약에서 신호를 읽는다. 키가 없으면 낱말 규칙으로 읽는다.
원칙: 블로그는 1인분 판정(status)을 바꾸지 않는다. 다르면 flags에 적어 팀이 확인한다.
"""
import re

import config
import llm
import tools
from board import Board

BASE = {"ok": 90, "nomin": 80, "hint": 75, "part": 55, "unk": 40, "two": 0}
LABEL = {"ok": "혼자 가능 확인", "nomin": "2인분 조건 없음", "hint": "1인분 메뉴 표기",
         "part": "일부 메뉴 2인 이상", "unk": "1인분 확인 안 됨", "two": "2인분 이상"}

SYSTEM = """너는 대구 혼밥 식당 서비스의 '혼밥 분석' 담당이다.
블로그 글 요약만 보고 아래 신호를 true/false로 답한다. 글에 없는 내용은 false다. 추측하지 않는다.
- solo_seat: 1인석, 바 좌석, 카운터석, 혼밥석이 있다
- solo_friendly: 혼자 와서 먹었다, 혼밥하기 좋다는 내용이 있다
- awkward: 혼자 가니 눈치가 보였다, 혼자는 어렵다는 내용이 있다
- two_min: 2인분부터, 2인 이상 주문 같은 조건이 있다
형식: {"solo_seat":false,"solo_friendly":false,"awkward":false,"two_min":false}"""

RULES = {  # Gemini가 없을 때 쓰는 낱말 규칙
    "solo_seat": r"1인석|혼밥석|바\s?좌석|바\s?테이블|카운터석|다찌",
    "solo_friendly": r"혼밥|혼자\s?(와서|가서|먹|방문)",
    "awkward": r"눈치",
    "two_min": r"2인분\s?(부터|이상)|2인\s?이상|2인부터",
}
POINTS = {"solo_seat": 5, "solo_friendly": 5, "awkward": -10}  # 페인포인트 ④ (눈치) 반영


def signals(name: str, posts: list):
    text = "\n".join(f"- {p['title']}: {p['snippet']}" for p in posts)
    got = llm.ask_json(SYSTEM, f"가게: {name}\n블로그 요약:\n{text}")
    if isinstance(got, dict):
        return {k: bool(got.get(k)) for k in RULES}, "Gemini"
    return {k: bool(re.search(p, text)) for k, p in RULES.items()}, "규칙"


def run(board: Board):
    for i, c in enumerate(board.candidates):
        st = c["store"].get("status", "unk")
        c["score"] = BASE.get(st, 40)
        c["evidence"].append(f"팀 판정: {LABEL.get(st, st)} — {c['store'].get('why', '')}")

        if i >= config.TOP_N:
            continue  # 블로그는 상위 몇 곳만
        posts = tools.kakao_blog(c["store"]["name"], c["store"].get("gu", ""))
        if not posts:
            continue
        sig, how = signals(c["store"]["name"], posts)
        for k, pt in POINTS.items():
            if sig[k]:
                c["score"] += pt
                c["evidence"].append(f"블로그({how}): {k} {'+' if pt > 0 else ''}{pt}")
        if sig["two_min"] and st != "two":
            c["flags"].append("블로그에 2인분 조건 언급 — 팀 판정과 다름, 확인 필요")
        c["score"] = max(0, min(100, c["score"]))

    board.candidates.sort(key=lambda c: -c["score"])
    blog_note = "" if config.KAKAO_KEY else " (카카오 키 없음 → 팀 판정 점수만)"
    board.note("혼밥 분석", f"{len(board.candidates)}곳 혼밥 지수 계산{blog_note}")
