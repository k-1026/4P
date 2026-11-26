"""🪑 혼밥 에이전트: 혼자 가기 좋은 정도를 점수로 매긴다.

기준: 혼밥팀 최종본(2026-11-26)의 혼밥점수.py와 같은 계산. 10점 만점.
  후기점수 (8)  조율자가 넘긴 후보들을 네이버 '혼밥하기 좋아요' 수로 줄 세워 올림(8 × (가게수 − 순위 + 1) ÷ 가게수)
                20곳이면 1~3등 8점 … 19~20등 1점. 수가 같으면 같은 순위. 후보가 달라지면 점수도 달라진다.
  1인석 (2)     1인석·바 좌석이 혼밥DB(일기·정보탭)나 내 혼밥일기에서 확인되면 +2, 없음·모름은 0
  탈락          2인분부터만 주문되는 가게 (혼밥DB 가게는 모두 1인분 가능)
  반론          점수 차 3점 이상이거나 1인석 여부가 달라 점수가 벌어지면 후기 수를 들어 동의/반대
  함께 반론     다른 에이전트가 반론할 때, 1순위보다 혼밥 점수가 높은 가게가 있으면 같이 반론한다
"""
from taste import josa

NAME = "혼밥"
REVIEW_TOP, SEAT_POINTS = 8, 2
CLEAR_GAP = 3
JOIN_RANKS = 10  # 함께 반론할 가게는 2~10순위에서 찾는다


def prepare(ctx):
    seen = {e.get("가게") for e in ctx.get("diary") or [] if "1인석 있음" in (e.get("혼밥포인트") or [])}
    return {"counts": [], "diary_seat": seen, "data": ctx.get("solo_data") or {}}


def opinion(state, ctx):
    said = "'혼밥하기 좋아요' 수로 후보끼리 줄을 세우고, 1인석이 확인되면 2점을 더할게요."
    if state["diary_seat"]:
        said += f" 혼밥일기에서 1인석 기록을 찾았어요: {', '.join(sorted(state['diary_seat']))}."
    return said


def candidates(state, stores, ctx):
    """후보 전체의 후기 수를 모은다. 순위는 이 안에서 정한다."""
    counts = [s["cnt"] for s in stores if s.get("cnt") is not None]
    said = f"후보 {len(counts)}곳의 '혼밥하기 좋아요'는 {min(counts):,}~{max(counts):,}명이에요." if counts else ""
    return {**state, "counts": counts}, said


def has_seat(state, store):
    extra = state["data"].get(store.get("id")) or {}
    return bool(store.get("solo_seat") == "있음" or store.get("seat") or extra.get("seat")
                or store.get("name") in state["diary_seat"])


def rank_of(state, store):
    """(순위, 가게수). 후기 수를 모르면 None"""
    count, counts = store.get("cnt"), state.get("counts") or []
    if count is None or not counts:
        return None
    return 1 + sum(1 for c in counts if c > count), len(counts)


def points(state, store):
    ranked = rank_of(state, store)
    review = 0
    if ranked:
        rank, n = ranked
        review = -(-REVIEW_TOP * (n - rank + 1) // n)  # 정수 올림
    return review + (SEAT_POINTS if has_seat(state, store) else 0)


def describe(state, store, ctx):
    count = store.get("cnt")
    seat = "1인석 확인" if has_seat(state, store) else "좌석 모름"
    return f"혼밥 좋아요 {count:,}명, {seat}" if count is not None else f"혼밥 후기 모름, {seat}"


def check(state, store, ctx):
    extra = state["data"].get(store.get("id")) or {}
    if store.get("single_ok") is False or extra.get("single_ok") is False:
        return False, '"2인분부터" 확인'
    return True, ""


def score(state, store, ctx):
    ranked, seat = rank_of(state, store), has_seat(state, store)
    tail = " 1인석도 확인됐어요." if seat else ""
    if not ranked:
        return {"score": points(state, store), "확실도": "낮음", "why": "혼밥 후기 수를 몰라요." + tail}
    rank, n = ranked
    return {"score": points(state, store), "확실도": "높음" if seat else "중간",
            "why": f"'혼밥하기 좋아요' {store['cnt']:,}명으로 후보 {n}곳 중 {rank}위예요." + tail}


def _line(state, store):
    count = f"'혼밥하기 좋아요' {store['cnt']:,}명" if store.get("cnt") is not None else "혼밥 후기 모름"
    return count + (", 1인석 있음" if has_seat(state, store) else "")


def rebut(state, sender, proposed, current, ctx):
    if rank_of(state, proposed) is None or rank_of(state, current) is None:
        return {"stance": "판단 안 함", "확실도": "낮음", "message": "혼밥 후기를 모르는 곳이 있어서 비교할 수 없어요."}
    gap = points(state, proposed) - points(state, current)
    detail = f"{proposed['name']}({_line(state, proposed)}), {current['name']}({_line(state, current)})"
    seat_matters = gap != 0 and has_seat(state, proposed) != has_seat(state, current)
    if abs(gap) < CLEAR_GAP and not seat_matters:
        return {"stance": "판단 안 함", "확실도": "중간", "message": f"혼밥 편의 차이는 작아요: {detail}."}
    if gap > 0:
        return {"stance": "동의", "확실도": "중간", "message": f"{sender} 의견에 동의해요. 혼자 가기에는 앞쪽이 나아요: {detail}."}
    return {"stance": "반대", "확실도": "중간", "message": f"{sender} 의견에는 반대예요. 혼자 가기에는 뒤쪽이 나아요: {detail}."}


def join(state, rows, proposal, ctx):
    """다른 에이전트의 반론에 함께한다. 내가 보기에 1순위보다 나은 가게가 있을 때만.
    상대가 민 곳과 같으면 동의로 힘을 보태고, 다르면 내 가게를 들어 같이 반론한다."""
    if len(rows) < 2:
        return None
    top = rows[0]["store"]
    best = max((row["store"] for row in rows[1:JOIN_RANKS]), key=lambda x: points(state, x))
    mine, theirs = points(state, best), points(state, top)
    if mine <= theirs:
        return None
    detail = f"{best['name']}({mine}점, {_line(state, best)})"
    if points(state, proposal["proposed"]) == mine:
        best = proposal["proposed"]
        return {"stance": "동의", "확실도": "중간", "proposed": best,
                "message": f"저도 같은 생각이에요. 혼자 가기에도 {best['name']}({mine}점, {_line(state, best)}) 쪽이 "
                           f"1순위 {top['name']}({theirs}점)보다 나아요."}
    return {"stance": "제안", "확실도": "중간", "proposed": best,
            "message": f"저도 같이 반론할게요. 혼자 가기에는 {detail}이 1순위 {top['name']}({theirs}점)보다 나아요."}


def propose(state, rows, ctx):
    """1순위보다 혼밥 점수가 3점 이상 높은 가게가 있으면 먼저 이의를 낸다."""
    if len(rows) < 2:
        return None
    top = rows[0]["store"]
    best = max((row["store"] for row in rows[1:]), key=lambda x: points(state, x))
    if points(state, best) - points(state, top) < CLEAR_GAP:
        return None
    return {"proposed": best, "current": top,
            "message": f"혼자 가기에는 {josa(best['name'], '이', '가')} 더 나아요 ({_line(state, best)}). "
                       f"1순위 {josa(top['name'], '은', '는')} {_line(state, top)}이에요."}
