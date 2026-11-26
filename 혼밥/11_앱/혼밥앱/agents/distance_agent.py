"""조율자용 거리 에이전트: 거리 규칙(distance_rules.py)을 조율자와 말을 주고받게 이어 준다.

distance_rules.py는 원래 거리 담당 파일(../distance_agent.js)을 파이썬으로 옮긴 것이다.
Vercel 파이썬 함수에서는 node를 부를 수 없어서 옮겼고, test_distance_parity.py가 두 결과가 같은지 확인한다.
"""
import distance_rules

NAME = "거리"
# 앱이 위치를 보내지 않았을 때만 쓰는 시험용 기준점 (이때 거리는 앱의 가게별 거리 값을 쓴다)
ORIGIN = {"lat": 35.869317, "lng": 128.597574, "accuracy_m": None, "source": "test"}
SURE = {"high": "높음", "medium": "중간", "low": "낮음"}

def call(cmd, **payload):
    """거리 규칙 호출 (distance_rules.py)"""
    if cmd == "report":
        return distance_rules.build_report(payload["places"], payload["origin"], payload.get("options"))
    if cmd == "objection":
        return distance_rules.objection(payload["report"], **payload.get("extra", {}))
    if cmd == "rebut":
        return distance_rules.rebut(payload["report"], payload["sender"], payload["proposed"], payload["current"],
                                    **payload.get("extra", {}))
    raise ValueError(cmd)


def _extra(ctx):
    temp = ctx.get("temp_c")
    return {"weather": {"temp_c": temp} if isinstance(temp, (int, float)) else None,
            "urgent": bool(ctx.get("hurry"))}


def prepare(ctx):
    """도보 시간은 후보가 정해지면 잰다."""
    return {"report": None, "origin": ctx.get("origin") or ORIGIN}


def opinion(state, ctx):
    return ""  # 거리는 후보가 정해진 뒤(②)에 말한다


def candidates(state, stores, ctx):
    """후보 가게의 도보 시간과 거리 점수(가장 가까운 곳 기준)를 거리 담당에게 받는다."""
    origin = state.get("origin") or ORIGIN
    places = [{"id": str(s["id"]), "place_name": s["name"], "distance": s.get("dist_m"),
               "x": str(s.get("lng") or origin["lng"]), "y": str(s.get("lat") or origin["lat"]),
               "category_name": f"음식점 > {s.get('cat') or ''}"} for s in stores]
    report = call("report", places=places, origin=origin,
                  options={"radius_m": 1000, "truncated": False, "urgent": bool(ctx.get("hurry"))})
    listed = [c for c in report["candidates"] if c["walk_min"] is not None]
    said = ""
    if listed:
        near, far = listed[0], listed[-1]
        said = (f"후보 {len(listed)}곳 도보 약 {near['walk_min']}~{far['walk_min']}분이에요. "
                f"가장 가까운 곳은 {near['name']} ({near['walk_label']}).")
    if origin["source"] == "test":
        said += " (내 위치가 없어서 앱에 적힌 거리로 쟀어요.)"
    elif origin["source"] == "area":
        said += f" ({origin.get('area') or '고른 동네'} 중심에서 잰 거리라 오차가 있어요.)"
    return {"report": report, "origin": origin}, said


def _find(state, store):
    report = state.get("report") or {}
    return next((c for c in report.get("candidates", []) if c["id"] == str(store["id"])), None)


def describe(state, store, ctx):
    found = _find(state, store)
    return found["walk_label"] if found else "도보 시간 모름"


def check(state, store, ctx):
    found = _find(state, store)
    if found and found.get("excluded"):
        return False, found.get("exclude_reason") or "너무 멀어요"
    return True, ""


def score(state, store, ctx):
    found = _find(state, store)
    if not found or found.get("distance_score") is None:
        return {"score": 5, "확실도": "낮음", "why": "도보 시간을 알 수 없어요."}
    return {"score": found["distance_score"], "확실도": SURE.get(found["confidence"], "중간"),
            "why": f"도보 {found['walk_label']}이에요."}


def propose(state, rows, ctx):
    """거리 담당의 반론 규칙(1순위가 7분 넘게 걸리고, 4분 이상 가까운 비슷한 점수의 가게가 있을 때)."""
    ranking = [{"id": str(row["store"]["id"]), "score": row["total"]} for row in rows]
    found = call("objection", report=state["report"], extra={"first_ranking": ranking, **_extra(ctx)})
    if not found:
        return None
    by_id = {str(row["store"]["id"]): row["store"] for row in rows}
    return {"proposed": by_id[found["prefer"]], "current": by_id[found["target"]], "message": found["message"]}


def rebut(state, sender, proposed, current, ctx):
    answer = call("rebut", report=state["report"], sender=sender, proposed=str(proposed["id"]),
                  current=str(current["id"]), extra=_extra(ctx))
    return {"stance": answer["stance"], "확실도": "중간" if answer["stance"] != "판단 안 함" else "낮음",
            "message": answer["message"].split(": ", 1)[-1]}
