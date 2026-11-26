"""상황 에이전트: 영업 · 날씨 · 동선.

도구: 팀 데이터 영업시간 + 기상청 초단기실황 + TMAP 보행자 경로
지금은 LLM 없이 규칙만 쓴다. (예: 비 오면 걷는 한도를 줄인다)
"""
import config
import store_lookup
import tools
from board import Board


def run(board: Board):
    cond = board.conditions
    origin = tuple(cond.get("origin") or config.DEFAULT_ORIGIN)

    weather = tools.kma_weather()
    cond["rain"] = bool(weather and weather["rain"])
    if weather:
        board.note("상황", f"날씨: {'비/눈' if cond['rain'] else '맑음/흐림'}, {weather['temp']}도")
    else:
        board.note("상황", "기상청 키 없음 또는 실패 → 날씨 모름")

    known_walk = 0
    for c in board.candidates:
        ctx = c["context"]
        if c["map"] is None and board.mode == "store":  # 탐색을 건너뛴 팀 가게는 여기서 위치를 찾는다
            c["map"] = store_lookup.locate_team_store(c["store"])
        ctx["open_now"] = tools.open_now(c["store"].get("hours", ""))
        if board.mode == "store" and not cond.get("origin"):
            ctx["walk_min"] = None  # 가게 하나를 물었고 사용자 위치를 모르면 거리를 재지 않는다
        elif c["map"]:
            ctx["walk_min"] = tools.tmap_walk_min(origin, (c["map"]["x"], c["map"]["y"]))
            known_walk += 1
        else:
            ctx["walk_min"] = None  # 모름. 검증에서 걸러 내지 않는다.

    opened = sum(c["context"]["open_now"] is True for c in board.candidates)
    board.note("상황", f"영업 중 확인 {opened}곳 · 걷는 시간 계산 {known_walk}곳")
