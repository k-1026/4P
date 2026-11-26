"""오케스트레이터: 계획 · 배분 · 재계획.

1. 계획: 사용자 말 → 조건 (Gemini, 없으면 규칙)
2. 배분: 탐색 → 혼밥 분석 → 상황 → 검증 순서로 보드를 넘긴다
3. 재계획: 검증이 반려하면 사유를 읽고 조건을 풀어 다시 돌린다 (최대 MAX_ROUNDS번)
"""
import json
import re

import config
import llm
import store_lookup
import tools
from agents import context, explore, honbap, verify
from board import Board, new_candidate

# ---------- 1. 계획 ----------
PLAN_SYSTEM = f"""너는 대구 혼밥 식당 찾기 서비스의 오케스트레이터다.
식당을 추천하거나 지어내지 말고, 사용자 문장에서 조건만 JSON으로 뽑는다.
- gu: {", ".join(tools.GU)} 중 하나. 동네 이름이면 그 구로 바꾼다. 모르면 null
- tags: {", ".join(tools.TAGS)} 중 해당하는 것 배열
- keywords: 메뉴 이름 낱말 배열 (예: "추어탕")
- max_price: 1인 최대 가격(원, 정수) 또는 null
- walk_limit: 걸어서 최대 몇 분, 말하지 않았으면 null
- off_topic: 식당 찾기와 상관없으면 true
형식: {{"gu":null,"tags":[],"keywords":[],"max_price":null,"walk_limit":null,"off_topic":false}}"""


def clean(o: dict) -> dict:
    """LLM이 낸 조건을 허용된 값만 남겨 다듬는다. LLM 출력은 항상 이걸 거친다."""
    return {
        "gu": o.get("gu") if o.get("gu") in tools.GU else None,
        "tags": [t for t in (o.get("tags") or []) if t in tools.TAGS],
        "keywords": [str(w) for w in (o.get("keywords") or []) if len(str(w)) >= 2][:3],
        "max_price": int(o["max_price"]) if isinstance(o.get("max_price"), (int, float)) and o["max_price"] > 0 else None,
        "walk_limit": int(o["walk_limit"]) if isinstance(o.get("walk_limit"), (int, float)) and o["walk_limit"] > 0 else None,
        "off_topic": bool(o.get("off_topic")),
    }


def parse_price(text: str):
    t = text.replace(",", "").replace(" ", "")
    t = re.sub(r"([일이삼사오육칠팔구])(?=[천만])", lambda m: str("일이삼사오육칠팔구".index(m[1]) + 1), t)  # 오천원 → 5천원
    if m := re.search(r"(\d+)만(\d)천", t):
        return int(m[1]) * 10000 + int(m[2]) * 1000
    if m := re.search(r"(\d*)만원", t):
        return int(m[1] or 1) * 10000
    if m := re.search(r"(\d+)천원", t):
        return int(m[1]) * 1000
    if m := re.search(r"(\d{4,6})원", t):
        return int(m[1])
    return None


STOP = {"회사", "회의", "회식", "면접", "사회"}  # '회' · '면'이 들어갔지만 음식이 아닌 말


def plan_by_rule(text: str) -> dict:
    # 긴 이름부터 찾는다 ('달서구' 안의 '서구'를 먼저 잡지 않게)
    gu = next((g for g in sorted(tools.GU, key=len, reverse=True) if g in text), None) \
        or next((g for a, g in tools.AREA.items() if a in text), None)
    tags, kws = [], []
    for tok in re.findall(r"[가-힣]+", text):
        if tok in STOP or tok in tools.AREA or tok in tools.GU:
            continue
        for tag, words in tools.TAGS.items():
            if any(w in tok for w in words):
                tags.append(tag)
                word = re.sub(r"(이|가|을|를|은|는|도|으로|로)$", "", tok)
                word = re.sub(r"(맛집|식당|집)$", "", word)  # 추어탕집 → 추어탕
                if word != tag and len(word) >= 2 and word not in kws:  # '추어탕'처럼 메뉴 이름은 키워드로
                    kws.append(word)
    walk = re.search(r"(\d+)\s*분", text)
    return {"gu": gu, "tags": sorted(set(tags)), "keywords": kws[:3], "max_price": parse_price(text),
            "walk_limit": int(walk[1]) if walk else None, "off_topic": False}


def plan(board: Board):
    got = llm.ask_json(PLAN_SYSTEM, board.request)
    board.conditions.update(clean(got) if isinstance(got, dict) else plan_by_rule(board.request))
    board.note("오케스트레이터", f"계획({'Gemini' if got else '규칙'}): {_cond_text(board.conditions)}")


# ---------- 3. 재계획 ----------
REPLAN_SYSTEM = """너는 대구 혼밥 식당 찾기 서비스의 오케스트레이터다.
검증 담당이 결과가 너무 적다고 반려했다. 반려 사유를 보고 조건을 '하나만' 풀어라.
풀 수 있는 것: keywords 비우기, max_price 올리기(최대 +5000), walk_limit 늘리기, tags 비우기, gu를 null로(대구 전체).
2인분 이상 가게를 넣는 쪽으로는 절대 바꾸지 않는다.
형식: {"gu":..,"tags":[..],"keywords":[..],"max_price":..,"walk_limit":..,"why":"무엇을 왜 풀었는지 한 줄"}"""


def relax_by_rule(cond: dict, rej: dict):
    """반려 사유를 보고 조건 하나를 푼다. 풀 게 없으면 None."""
    top = max(rej["by_rule"], key=rej["by_rule"].get) if rej["by_rule"] else None
    if top == "too_far":
        return {**cond, "walk_limit": (cond.get("walk_limit") or config.DEFAULT_WALK_MIN) + 10}, "멀어서 많이 빠짐 → 걷는 한도 +10분"
    if top == "walk_unknown":
        return {**cond, "walk_limit": None}, "가게 위치를 몰라 거리 조건을 뺌 (답할 때 알려 줘야 함)"
    if top == "over_price" and cond.get("max_price"):
        return {**cond, "max_price": cond["max_price"] + 3000}, "예산 때문에 많이 빠짐 → 예산 +3천원"
    # 후보 자체가 적으면 좁은 조건부터 푼다
    if cond.get("keywords"):
        return {**cond, "keywords": []}, "메뉴 이름으로는 적음 → 음식 종류로 넓힘"
    if cond.get("max_price"):
        return {**cond, "max_price": cond["max_price"] + 3000}, "후보가 적음 → 예산 +3천원"
    if cond.get("tags"):
        return {**cond, "tags": []}, "음식 종류를 풀어 근처 전체로 넓힘"
    if cond.get("gu"):
        return {**cond, "gu": None}, "구를 풀어 대구 전체로 넓힘"
    return None


def replan(board: Board) -> bool:
    rej = board.rejections[0]
    keep = {"inc_two": board.conditions.get("inc_two", False), "origin": board.conditions.get("origin")}
    cur = {k: board.conditions.get(k) for k in ("gu", "tags", "keywords", "max_price", "walk_limit")}

    got = llm.ask_json(REPLAN_SYSTEM, f"지금 조건: {json.dumps(cur, ensure_ascii=False)}\n반려 사유: {json.dumps(rej, ensure_ascii=False)}")
    if isinstance(got, dict) and (new := {k: v for k, v in clean(got).items() if k != "off_topic"}) != cur:
        why = f"Gemini: {got.get('why', '')}"
    else:
        out = relax_by_rule(cur, rej)
        if not out:
            board.note("오케스트레이터", "더 풀 조건이 없음 → 지금 결과로 마침")
            return False
        new, why = out
    board.conditions = {**new, **keep}
    board.note("오케스트레이터", f"재계획 — {why} → {_cond_text(board.conditions)}")
    return True


# ---------- 가게 하나를 물어봤을 때 ----------
def ask_about_store(board: Board, name: str, gu) -> bool:
    """'○○가게 혼밥 가능해?' 흐름. 처리했으면 True, 가게 이름이 아니었으면 False(→ 조건 검색).
    팀 데이터에 있으면 탐색을 건너뛰고, 없으면 탐색 에이전트가 지도에서 찾는다."""
    hits = store_lookup.find_team_by_name(name, gu)
    if len(hits) == 1:
        board.mode = "store"
        board.candidates = [new_candidate(hits[0])]
        board.note("오케스트레이터", f"'{name}'은(는) 팀 데이터에 있음 → 탐색 건너뜀")
    elif len(hits) > 1:
        board.mode = "store"
        board.candidates = [new_candidate(r) for r in hits]
        board.ask = explore._ask_text(name, board.candidates)
        board.note("오케스트레이터", f"'{name}'이(가) 팀 데이터에 {len(hits)}곳 → 어느 가게인지 되물음")
        return True
    else:
        board.note("오케스트레이터", f"'{name}'은(는) 팀 데이터에 없음 → 탐색 에이전트에 맡김")
        result = explore.find_store(board, name, gu)
        if result != "found":
            if result == "not_found":
                board.ask = f"'{name}'을(를) 대구 음식점에서 찾지 못했어요. 가게 이름을 다시 알려 주시겠어요?"
            elif result == "no_key":
                board.ask = "지금은 지도 검색을 쓸 수 없어 팀 데이터에 없는 가게는 찾을 수 없어요."
            return True

    board.round = 1
    honbap.run(board)
    context.run(board)
    verify.run(board)
    return True


# ---------- 전체 흐름 ----------
def run(request: str, origin=None) -> Board:
    board = Board(request=request)
    if origin:
        board.conditions["origin"] = origin

    name, gu, intent = store_lookup.detect_store(request)
    board.intent = intent or ""
    if name:
        board.note("오케스트레이터", f"가게 질문: '{name}' · 질문 종류: {intent or '모름'}")
    if name and ask_about_store(board, name, gu):
        return board

    plan(board)
    if board.conditions.get("off_topic"):
        board.note("오케스트레이터", "식당 찾기와 상관없는 말 → 종료")
        return board

    while True:
        board.round += 1
        explore.run(board)   # 2. 배분 (순서대로)
        honbap.run(board)
        context.run(board)
        if verify.run(board):
            break
        if board.round >= config.MAX_ROUNDS or not replan(board):
            board.note("오케스트레이터", f"반려가 남았지만 {len(board.final)}곳으로 답함")
            break
    return board


def _cond_text(c: dict) -> str:
    parts = [c.get("gu") or "대구 전체"]
    if c.get("tags"): parts.append("/".join(c["tags"]))
    if c.get("keywords"): parts.append("메뉴:" + ",".join(c["keywords"]))
    if c.get("max_price"): parts.append(f"{c['max_price']:,}원 이하")
    if c.get("walk_limit"): parts.append(f"걸어서 {c['walk_limit']}분")
    return " · ".join(parts)
