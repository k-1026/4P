"""조율자용 취향기록 에이전트 (taste.py를 조율자 규칙에 맞게 감싼 것).

혼밥 MBTI(ctx["mbti"])의 탐험파/단골파를 점수에 반영한다.
"""
import mbti
import taste
from taste import josa

NAME = "취향"


def prepare(ctx):
    return taste.load_profile(today=ctx["now"].date())


def opinion(state, ctx):
    said = taste.opinion(state)
    code = ctx.get("mbti")
    if mbti.has(code, "탐험파"):
        said += " 탐험파시니 안 가본 가게 위주로 볼게요."
    elif mbti.has(code, "단골파"):
        liked = [name for name, shop in state["가게별"].items() if shop["평균별점"] >= 4]
        said += " 단골파시니 가봤던 곳의 기록을 먼저 볼게요" + (f" ({', '.join(liked[:3])} 등)." if liked else ".")
    return said


def score(state, store, ctx):
    result = taste.score(state, store["name"], store["kind"], ctx.get("mbti"))
    why = taste.reason(state, store["name"], store["kind"])
    if result.get("mbti"):
        why += f" ({result['mbti']})"
    return {"score": result["score"], "확실도": result["확실도"], "why": why}


def propose(state, rows, ctx):
    """취향 점수로 1순위보다 2점 이상 나은 가게가 있으면 제안한다."""
    top = rows[0]
    mine = {id(row): score(state, row["store"], ctx)["score"] for row in rows}
    best = max(rows, key=lambda row: (mine[id(row)], row is top))
    if best is top or mine[id(best)] - mine[id(top)] < 2:
        return None
    name, now = best["store"]["name"], top["store"]["name"]
    new, old = mine[id(best)], mine[id(top)]
    code = ctx.get("mbti")
    if mbti.has(code, "단골파") and name in state["가게별"]:
        shop = state["가게별"][name]
        text = (f"단골파시니 가봤던 {josa(name, '은', '는')} 어떨까요? 별점 {shop['마지막별점']}점을 준 곳이에요. "
                f"{josa(now, '은', '는')} {'안 가본 곳이라 ' if now not in state['가게별'] else ''}"
                f"취향 점수가 {old:g}점이에요.")
    elif mbti.has(code, "탐험파") and name not in state["가게별"]:
        text = f"탐험파시니 안 가본 {josa(name, '은', '는')} 어떨까요? 취향 점수가 {new:g}점으로 {now}({old:g}점)보다 높아요."
    else:
        text = f"취향으로는 {name}({new:g}점) 쪽이 {now}({old:g}점)보다 나아요."
    return {"proposed": best["store"], "current": top["store"], "message": text}


def rebut(state, sender, proposed, current, ctx):
    answer = taste.rebut(state, sender, proposed["name"], proposed["kind"],
                         current["name"], current["kind"], ctx.get("hurry", False), ctx.get("mbti"))
    return {"stance": answer["stance"], "확실도": answer["확실도"],
            "message": answer["message"].split(": ", 1)[-1]}
