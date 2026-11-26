"""1126proto 점수 도구 (참고 구현). 모든 숫자는 criteria.json에서 읽는다.

에이전트(LLM)는 점수를 직접 계산하지 않고 이 함수들을 도구로 부른다.
  - 개별 점수: 0~10 정수 (floor(x + 0.5)), 탈락·판단 불가는 None
  - 총점: 0.0~10.0, 소수 첫째 자리
"""
import json
import math
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "criteria.json"), encoding="utf-8") as _f:
    C = json.load(_f)

MAX = C["score"]["max"]


def r(x):
    """사사오입 정수"""
    return math.floor(x + 0.5)


def clamp(x):
    return max(0, min(MAX, x))


def result(store_id, verdict, score=None, confidence="high", evidence=None, reason=""):
    return {"store_id": store_id, "verdict": verdict, "score": score,
            "confidence": confidence, "evidence": evidence or [], "reason": reason}


# ───────── 날씨 ─────────
def weather_direction(feels_like):
    t = C["weather"]["feels_like_c"]
    if feels_like <= t["hot_soup_le"]:
        return "따뜻한 국물"
    if feels_like <= t["warm_le"]:
        return "따뜻한 요리"
    if feels_like < t["cold_ge"]:
        return "없음"
    return "차가운 요리"


def score_weather(store_id, direction, food_type):
    points = C["weather"]["scores"][direction].get(food_type)
    if points is None:
        return result(store_id, "unknown", confidence="low", reason="음식 종류 모름")
    return result(store_id, "pass", points, evidence=[f"날씨 방향 {direction}", f"음식 {food_type}"])


# ───────── 거리 ─────────
def walk_min(straight_m):
    w = C["distance"]["walk"]
    return math.ceil(straight_m * w["detour"] / w["m_per_min"])


def score_distance(stores, time_pressure=False):
    """stores: [{store_id, walk_min}] (walk_min이 None이면 unknown)"""
    known = [s["walk_min"] for s in stores if s.get("walk_min") is not None]
    nearest = min(known) if known else None
    factor = 2 if time_pressure else 1
    out = []
    for s in stores:
        w = s.get("walk_min")
        if w is None:
            out.append(result(s["store_id"], "unknown", confidence="low", reason="도보 시간 모름"))
        elif w > C["distance"]["drop_walk_min_gt"]:
            out.append(result(s["store_id"], "drop", evidence=[f"도보 {w}분"], reason="너무 멀다"))
        else:
            out.append(result(s["store_id"], "pass", clamp(MAX - factor * (w - nearest)),
                              evidence=[f"도보 {w}분", f"가장 가까운 곳 {nearest}분"]))
    return out


# ───────── 예산 ─────────
def budget_cap(segment, user_budget=None):
    if user_budget:
        return user_budget
    return C["budget"]["segment_caps"][segment]


def score_budget(stores, segment, user_budget=None):
    """stores: [{store_id, prices: [1인 메뉴 가격], confidence, voc_pos, voc_neg}]"""
    b = C["budget"]
    cap = budget_cap(segment, user_budget)
    for s in stores:
        prices = [p for p in s.get("prices") or [] if p is not None]
        s["price"] = r(statistics.median(prices)) if prices else None
    priced = [s for s in stores if s["price"] is not None]
    n = len(priced)
    out = []
    for s in stores:
        if s["price"] is None:
            out.append(result(s["store_id"], "unknown", confidence="low", reason="가격 없음"))
            continue
        if cap is None:
            base, how = b["premium_score"], "premium: 예산 변별력 없음"
        elif n < b["min_compare"]:
            ar = b["absolute_rule"]
            base = ar["le_80pct_cap"] if s["price"] <= cap * 0.8 else ar["le_cap"]
            how = f"비교 대상 {n}곳이라 절대 규칙"
        else:
            higher = sum(1 for p in priced if p["price"] > s["price"])
            base, how = r(MAX * higher / (n - 1)), f"{n}곳 중 더 비싼 곳 {higher}곳"
        adj = 0
        pos, neg = s.get("voc_pos", 0), s.get("voc_neg", 0)
        if b["voc_enabled"] and pos + neg >= b["voc_min_mentions"]:
            ratio = (pos - neg) / (pos + neg)
            adj = b["voc_adjust_max"] if ratio >= b["voc_ratio_ge"] else -b["voc_adjust_max"] if ratio <= -b["voc_ratio_ge"] else 0
        ev = [f"1인 가격 {s['price']:,}원", how]
        if cap is not None and s["price"] > cap:
            out.append(result(s["store_id"], "drop", confidence=s.get("confidence", "high"),
                              evidence=ev + [f"상한 {cap:,}원 초과"], reason="예산 초과"))
        else:
            out.append(result(s["store_id"], "pass", clamp(base + adj), s.get("confidence", "high"), ev))
    return out


# ───────── 취향 ─────────
def star10(stars, tone=0):
    """별점(1~5) -> 10점 환산. 후기 느낌(tone: +1/0/-1)은 ±1점 (2~10에서 자른다)"""
    return max(2, min(MAX, stars * 2 + tone * C["preference"]["review_tone_adjust"]))


def score_preference(store_id, shop_avg10=None, kind_avg10=None, kind_count=0,
                     repeat_days=None, mbti_axis=None, visited=False):
    """shop_avg10 / kind_avg10: 10점 환산 평균. mbti_axis: 'N'(탐험파) / 'R'(단골파) / None"""
    p = C["preference"]
    if shop_avg10 is not None:
        base, conf = shop_avg10, "high"
    elif kind_avg10 is not None:
        base, conf = kind_avg10, "high" if kind_count >= p["kind_high_confidence_count_ge"] else "mid"
    else:
        base, conf = p["no_record"], "low"
    penalty = p["repeat_penalty"].get(str(repeat_days), 0) if repeat_days is not None else 0
    bonus = 0
    if mbti_axis == "N":
        bonus = p["mbti"]["N_explorer"]["visited" if visited else "new"]
    elif mbti_axis == "R":
        m = p["mbti"]["R_regular"]
        if not visited:
            bonus = m["new"]
        elif shop_avg10 is not None and shop_avg10 >= 8:
            bonus = m["visited_ge_8"]
        elif shop_avg10 is not None and shop_avg10 >= 6:
            bonus = m["visited_ge_6"]
    score = clamp(r(base - penalty + bonus))
    return result(store_id, "pass", score, conf,
                  [f"기준 {base:g}점", f"연속 감점 -{penalty}", f"MBTI 보정 {bonus:+d}"])


# ───────── 혼밥편의 ─────────
def score_solo(store_id, min_order_qty=None, single_ok=None, seat=None, cozy_without_pct=False):
    s = C["solo"]
    if (min_order_qty or 0) >= s["drop_if_min_order_ge"] or single_ok is False:
        return result(store_id, "drop", reason="2인분부터")
    if seat in s["seat_confirmed_values"]:
        return result(store_id, "pass", s["seat_confirmed"], evidence=[f"1인석 확인({seat})"])
    if single_ok:
        points = s["single_ok_seat_unknown_cozy_no_pct"] if cozy_without_pct else s["single_ok_seat_unknown"]
        return result(store_id, "pass", points, "low", ["1인분 확인", "좌석 모름"])
    return result(store_id, "unknown", confidence="low", reason="1인분·좌석 모두 모름")


# ───────── 조율자 ─────────
WEIGHT_KEYS = ("solo", "distance", "budget", "preference", "weather")


def weights_for(time_pressure=False, premium=False, pct=None, available=WEIGHT_KEYS):
    """기준 열 선택 -> MBTI 배수 -> 준비된 에이전트끼리 합 100으로 다시 나눔"""
    col = "_".join(n for n, on in (("premium", premium), ("time_pressure", time_pressure)) if on)
    base = C["weights"][col or "default"]
    raw = {k: base[k] for k in available if base.get(k, 0) > 0}
    if pct:  # {"W": 0~1, "B": 0~1}
        times = {"weather": 0.5 + pct["W"], "preference": 1.5 - pct["W"], "solo": 0.5 + pct["B"]}
        raw = {k: v * times.get(k, 1) for k, v in raw.items()}
    total = sum(raw.values())
    return {k: v * 100 / total for k, v in raw.items()} if total else {}


def total_score(scores, weights):
    """scores: {agent: 0~10 또는 None(unknown=0)} -> 0.0~10.0"""
    value = sum((scores.get(k) or 0) * w for k, w in weights.items()) / 100
    return round(value, C["score"]["total_decimals"])


def should_debate(totals):
    ranked = sorted(totals, reverse=True)
    return len(ranked) > 1 and ranked[0] - ranked[1] <= C["debate"]["open_if_gap_le"]


def gap_stance(mine, theirs):
    """반론 공통: 점수 차 2점 이하면 '판단 안 함', 3점 이상이면 동의/반대"""
    if mine is None or theirs is None:
        return "판단 안 함"
    diff = mine - theirs
    if abs(diff) <= C["score"]["small_gap_le"]:
        return "판단 안 함"
    return "동의" if diff > 0 else "반대"
