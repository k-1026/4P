"""새 에이전트를 만들 때 복사해서 쓰는 틀 (이 파일 자체는 조율자가 쓰지 않는다).

조율자(coordinator.py)는 아래 이름의 파일이 있으면 자동으로 불러서 함께 상의한다.
    혼밥편의 -> solo_agent.py      거리 -> distance_agent.py
    예산     -> budget_agent.py    (날씨 -> weather_agent.py, 취향 -> taste_agent.py 는 이미 있음)
파일을 만들고 아래 함수 다섯 개를 채우면 끝. 없는 함수(check)는 빼도 된다.

가게(store)는 앱 가게 목록에서 온 사전(dict)이다. 자주 쓰는 값:
    name 이름, kind 음식 종류(11가지), weather_type 날씨용 종류, dist_m 거리(m), walk_min 도보(분),
    price 가격(원), seat 1인석 여부, kiosk 키오스크, wait 대기(0~2), rate 평점, menu 대표 메뉴, tags 태그
ctx(상황)는 조율자가 넘긴다: now 지금 시각, hurry 시간이 없는지, budget 예산(원, 없으면 None)
"""

NAME = "예시"  # 조율자에서 부르는 이름 (혼밥편의 / 거리 / 예산 중 하나)


def prepare(ctx):
    """처음 한 번: 필요한 데이터를 준비해서 돌려준다. 준비에 실패하면 None (이번엔 빠짐)."""
    return {}


def opinion(state, ctx):
    """처음 하는 말 한두 문장. 예: '시간이 없으시면 5분 이내 위주로 볼게요.'"""
    return ""


# (선택) 후보를 고르기 전에 전체 가게에서 빼야 할 가게가 있으면 아래 함수를 만든다. (메뉴 에이전트가 2인분 가게를 뺄 때 씀)
# def before_candidates(state, stores, ctx):
#     return 남길_가게_목록, "조율자에게 할 말 (없으면 빈 문자열)"


def check(state, store, ctx):
    """탈락 조건 (선택). 통과면 (True, ""), 탈락이면 (False, "2인분부터 주문 가능").
    점수와 상관없이 빠지는 조건만 여기 둔다."""
    return True, ""


def score(state, store, ctx):
    """0~10점. why는 최종 답에 쓰는 짧은 이유, 확실도는 높음/중간/낮음."""
    return {"score": 5, "확실도": "낮음", "why": ""}


def rebut(state, sender, proposed, current, ctx):
    """다른 에이전트가 proposed(가게)를 current(지금 1순위) 대신 밀 때 내 생각.
    stance는 동의 / 반대 / 판단 안 함. 자기 영역(거리면 거리)만 판단한다."""
    return {"stance": "판단 안 함", "확실도": "낮음", "message": ""}
