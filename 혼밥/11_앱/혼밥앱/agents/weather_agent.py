"""조율자용 날씨 에이전트 (weather.py를 조율자 규칙에 맞게 감싼 것)."""
import contextlib
import io

import weather

NAME = "날씨"


def prepare(ctx):
    """날씨를 새로 가져온다. 실패하면 None (조율자가 날씨를 빼고 계산)."""
    with contextlib.redirect_stdout(io.StringIO()):  # weather.main()이 찍는 글은 숨긴다
        try:
            return weather.main(ctx["now"], place=ctx.get("origin"))
        except Exception:
            return None


def opinion(state, ctx):
    parts = [f"체감 {state['feels_like']}도예요" + (f" ({state['where']})." if state.get("where") else ".")]
    if state.get("comparison"):
        parts.append(state["comparison"])
    parts.append(state["message"])
    return " ".join(parts)


def score(state, store, ctx):
    result = weather.score(state, store["weather_type"])
    reply = weather.reply(state, "조율자", store["name"], store["weather_type"])
    why = reply["message"].split(": ", 1)[-1].rsplit(" (체감", 1)[0]
    return {"score": result["score"], "확실도": "높음" if result["confirmed"] else "낮음", "why": why}


def rebut(state, sender, proposed, current, ctx):
    answer = weather.rebut(state, sender, proposed["name"], proposed["weather_type"],
                           current["name"], current["weather_type"])
    sure = "낮음" if answer["stance"] == "판단 안 함" else "높음"
    return {"stance": answer["stance"], "확실도": sure,
            "message": answer["message"].split(": ", 1)[-1]}
