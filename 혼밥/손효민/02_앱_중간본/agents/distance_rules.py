"""거리 규칙: ../distance_agent.js의 buildReport / objection / rebut를 파이썬으로 옮긴 것.

Vercel 파이썬 함수에서는 node를 부를 수 없어서 옮겼다. 규칙을 바꿀 때는 test_distance_parity.py로
JS와 결과가 같은지 확인하거나, JS를 더 쓰지 않기로 하면 JS 파일과 그 시험을 함께 지운다.
"""
import math

RADIUS_M = 1000          # 검색 반경
WALK_M_PER_MIN = 70      # 성인 평균 보행 속도
DETOUR = 1.3             # 직선거리 대비 실제 길 우회 비율
LOW_ACCURACY_M = 300     # 내 위치 오차가 이보다 크면 확실도 낮춤
OBJECTION = {"far_min": 7, "closer_by_min": 4, "max_score_gap": 1.0, "cold_c": 5}
REBUT = {"small_gap_min": 2, "small_gap_min_urgent": 1, "cold_c": 5}


def _round(x):  # JS Math.round
    return math.floor(x + 0.5)


def _num(x):    # JS에서 숫자를 글로 바꾼 모양 (4.0 -> "4", 13.6 -> "13.6")
    return str(int(x)) if float(x).is_integer() else repr(float(x))


def josa(word, with_batchim, without):
    code = ord(word[-1]) if word else 0
    return word + (with_batchim if 0xAC00 <= code <= 0xD7A3 and (code - 0xAC00) % 28 else without)


def walk_label(minutes):
    return "알 수 없음" if minutes is None else f"약 {minutes}분"


def _is_temp(weather):
    t = (weather or {}).get("temp_c")
    return t if isinstance(t, (int, float)) and not isinstance(t, bool) else None


def build_report(places, origin, options=None):
    """후보의 도보 시간과 거리 점수. 가장 가까운 곳 10점, 1분마다 1점(급하면 2점)씩 깎는다."""
    options = options or {}
    accuracy = origin.get("accuracy_m")
    low_origin = accuracy is not None and accuracy > LOW_ACCURACY_M
    candidates = []
    for p in places or []:
        distance = p.get("distance")
        straight = None if distance is None or distance == "" else float(distance)
        walk = None if straight is None else max(1, math.ceil(_round(straight * DETOUR) / WALK_M_PER_MIN))
        confidence = "low" if straight is None or low_origin else "medium"
        candidates.append({"id": str(p["id"]), "name": p.get("place_name"), "walk_min": walk,
                           "walk_label": walk_label(walk), "source": "straight_line_estimate",
                           "confidence": confidence, "excluded": False, "exclude_reason": None})
    candidates.sort(key=lambda c: math.inf if c["walk_min"] is None else c["walk_min"])
    timed = [c["walk_min"] for c in candidates if c["walk_min"] is not None]
    nearest = min(timed) if timed else None
    per_min = 2 if options.get("urgent") else 1
    for c in candidates:
        c["distance_score"] = (None if c["walk_min"] is None
                               else max(0, _round(10 - (c["walk_min"] - nearest) * per_min)))
    return {"agent": "distance", "ok": True, "origin": origin,
            "criteria": {"radius_m": options.get("radius_m", RADIUS_M), "urgent": bool(options.get("urgent"))},
            "candidates": candidates}


def objection(report, first_ranking=None, weather=None, **_):
    """1순위가 7분 넘게 걸리고, 4분 이상 가까우며 점수 차 1점 이하인 후보가 있으면 한 번 반론한다."""
    if not report or not report.get("ok") or not first_ranking or len(first_ranking) < 2:
        return None
    by_id = {c["id"]: c for c in report["candidates"]}
    ranked = [{**r, "id": str(r["id"]), "c": by_id.get(str(r["id"]))} for r in first_ranking]
    ranked = [r for r in ranked if r["c"] and r["c"]["walk_min"] is not None and not r["c"]["excluded"]]
    if len(ranked) < 2:
        return None
    top = ranked[0]
    if top["c"]["walk_min"] <= OBJECTION["far_min"]:
        return None
    closer = [r for r in ranked[1:] if top["c"]["walk_min"] - r["c"]["walk_min"] >= OBJECTION["closer_by_min"]
              and top["score"] - r["score"] <= OBJECTION["max_score_gap"]]
    if not closer:
        return None
    alt = sorted(closer, key=lambda r: (-r["score"], r["c"]["walk_min"]))[0]
    temp = _is_temp(weather)
    name = lambda r: r["c"]["name"] or r["id"]
    if temp is not None and temp <= OBJECTION["cold_c"]:
        message = (f"{_num(temp)}도인데 {josa(name(top), '은', '는')} {top['c']['walk_label']}이에요. "
                   f"{alt['c']['walk_label']}인 {josa(name(alt), '이', '가')} 낫지 않나요?")
    else:
        message = (f"{josa(name(top), '은', '는')} {top['c']['walk_label']}이에요. "
                   f"{alt['c']['walk_label']}인 {josa(name(alt), '이', '가')} 더 가까운데 어떨까요?")
    return {"agent": "distance", "target": top["id"], "prefer": alt["id"], "message": message}


def rebut(report, sender, proposed, current, weather=None, urgent=None, **_):
    """다른 에이전트가 미는 가게와 지금 1순위를 도보 시간으로 비교한다. 점수는 바꾸지 않는다."""
    def find(key):
        if not report or not report.get("ok"):
            return None
        return next((c for c in report["candidates"] if c["id"] == str(key) or c["name"] == key), None)

    p, c = find(proposed), find(current)
    label = lambda x, key: (x and x["name"]) or str(key)
    if not p or not c or p["walk_min"] is None or c["walk_min"] is None:
        missing = [label(x, key) for x, key in ((p, proposed), (c, current)) if not x or x["walk_min"] is None]
        return {"stance": "판단 안 함",
                "message": f"{sender} 의견에 대해: {', '.join(missing)}의 도보 시간을 몰라서 거리로는 비교할 수 없어요."}
    is_urgent = bool(urgent) if urgent is not None else bool(report["criteria"].get("urgent"))
    small = REBUT["small_gap_min_urgent"] if is_urgent else REBUT["small_gap_min"]
    diff = p["walk_min"] - c["walk_min"]
    temp = _is_temp(weather)
    if abs(diff) < small:
        stance = "판단 안 함"
        text = f"{p['name']}({p['walk_label']})와 {c['name']}({c['walk_label']})는 거리 차이가 작아요."
    elif diff > 0:
        stance = "반대"
        text = f"{josa(p['name'], '은', '는')} {p['walk_label']}이라 {c['name']}보다 {diff}분 더 걸려요."
        if temp is not None and temp <= REBUT["cold_c"]:
            text += f" {_num(temp)}도라 오래 걷기엔 추워요."
        if is_urgent:
            text += " 시간이 없으시니 가까운 쪽이 나아요."
    else:
        stance = "동의"
        text = f"{josa(p['name'], '이', '가')} {c['name']}보다 {-diff}분 더 가까워요 ({p['walk_label']})."
    text += " (직선거리 추정값 기준)"
    return {"stance": stance, "message": f"{sender} 의견에 대해: {text}"}
