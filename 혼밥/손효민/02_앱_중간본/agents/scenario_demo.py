"""가정 상황을 실제 에이전트로 돌려 본다.

  🌡️ 날씨: 실제 코드(weather.py). 날씨 값만 상황에 맞춰 넣는다
  📒 취향: 실제 코드(taste.py) + 샘플 혼밥일기(국밥 좋아함, 어제 동성로 라멘, A 국밥집에 '1인석 있음')
  🚶 거리: 실제 코드(../distance_agent.js)를 node로 부른다
  🧭 조율자: 실제 코드(coordinator.py)
  🪑 혼밥, 📋 메뉴, 💰 가격: 아직 없어서 가정 에이전트(mock_agents.py)

실행: python scenario_demo.py            상황 1·2 (같은 가게, MBTI가 다른 두 사람)
      python scenario_demo.py 예시       처음에 보내 주신 A~E 예시
      python scenario_demo.py 예시 급함  예시 + "시간이 없어요"
"""
import sys
from datetime import datetime

import coordinator
import distance_agent
import mock_agents
import taste
import taste_agent
import weather_agent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TODAY = datetime(2026, 11, 26, 12, 0)  # 샘플 일기에서 '어제'가 11/25 라면인 날
ASSUMED = ["혼밥", "메뉴", "가격"]


def walk_to_dist(minutes):
    """거리 담당은 직선거리 x 1.3(우회) / 분당 70m로 도보 분을 계산하므로, 그 반대로 직선거리를 넣는다"""
    return int(minutes * 70 / 1.3)


def wrap(module, state):
    """실제 에이전트를 그대로 쓰되, 준비(prepare) 단계만 이 상황의 값으로 바꾼다"""
    names = ("opinion", "share", "candidates", "describe", "check", "score", "propose", "rebut")
    parts = {name: staticmethod(getattr(module, name)) for name in names if hasattr(module, name)}
    return type("Agent", (), {**parts, "prepare": staticmethod(lambda ctx: state)})


def agents_for(weather_report):
    diary = taste.load_diary(taste.FOLDER)
    profile = taste.build_profile(diary, taste.load_stores(taste.FOLDER), TODAY.date())
    return diary, [
        {"name": "혼밥", "weight": 35, "module": mock_agents.solo},
        {"name": "거리", "weight": 20, "module": distance_agent},
        {"name": "가격", "weight": 20, "module": mock_agents.price},
        {"name": "취향", "weight": 15, "module": wrap(taste_agent, profile)},
        {"name": "날씨", "weight": 10, "module": wrap(weather_agent, weather_report)},
        {"name": "메뉴", "weight": 0, "module": mock_agents.menu}]


# ─────────── 상황 1·2: 같은 날, 같은 가게, MBTI가 다른 두 사람 ───────────
COLD = {"time": "2026-11-26 12:00", "feels_like": 2.5, "yesterday": 6.5, "yesterday_source": "ASOS",
        "comparison": "어제 같은 시각보다 4.0도 낮아요.", "direction": "따뜻한 국물",
        "message": "따뜻한 국물요리 추천해요!"}
STORES = [  # 메뉴·좌석은 비워 두고, 메뉴·혼밥 에이전트가 '갱신'해서 채운다
    {"id": "A", "area": 0, "name": "A 국밥집", "rate": 4.5, "dist_m": walk_to_dist(8)},
    {"id": "B", "area": 0, "name": "B 라멘집", "rate": 4.6, "dist_m": walk_to_dist(3)},
    {"id": "C", "area": 0, "name": "C 찌개집", "rate": 4.4, "dist_m": walk_to_dist(6)},
    {"id": "F", "area": 0, "name": "F 샤브집", "rate": 4.7, "dist_m": walk_to_dist(6)},
    {"id": "S", "area": 0, "name": "삼덕 백반", "rate": 4.3, "dist_m": walk_to_dist(7)},
    {"id": "H", "area": 0, "name": "H 파스타집", "rate": 4.9, "dist_m": walk_to_dist(20)},  # 1km 밖
]
MENUS = {  # 📋 메뉴 에이전트가 갱신한 메뉴 (가정)
    "A": [{"name": "순대국", "price": 9000, "soup": True}, {"name": "내장탕", "price": 10000, "soup": True}],
    "B": [{"name": "돈코츠 라멘", "price": 9500, "soup": True}, {"name": "차슈 라멘", "price": 11500, "soup": True}],
    "C": [{"name": "김치찌개 (2인)", "price": 18000, "soup": True}],
    "F": [{"name": "1인 샤브", "price": 14000, "soup": True}, {"name": "프리미엄 1인 샤브", "price": 18000, "soup": True}],
    "S": [{"name": "백반", "price": 8000, "soup": False}, {"name": "제육 정식", "price": 9000, "soup": False}],
    "H": [{"name": "수제 파스타", "price": 16000, "soup": False}],
}
SOLO = {  # 🪑 혼밥 에이전트가 갱신한 1인분·좌석 데이터 (가정). A의 1인석은 내 혼밥일기에서 확인
    "A": {"single_ok": True},
    "B": {"single_ok": True, "seat": True, "seat_text": "바 자리"},
    "C": {"single_ok": False},
    "F": {"single_ok": True, "seat": True, "seat_text": "1인 냄비 바 좌석"},
    "S": {"single_ok": True},
    "H": {"single_ok": True, "seat": True, "seat_text": "창가 1인석"},
}
PEOPLE = {"WBNV": "구석자리파 · 탐험파 · 알뜰파", "AORP": "아무자리파 · 단골파 · 맛우선파"}


def run_person(code, hurry=False, pct=None):
    """pct: 사용자가 정한 혼밥 MBTI 퍼센트 [날씨파, 구석자리파, 탐험파, 알뜰파 쪽 %] (없으면 기본 비율)"""
    diary, agents = agents_for(COLD)
    ctx = {"now": TODAY, "hurry": hurry, "mbti": code, "mbti_pct": pct, "diary": diary, "menus": MENUS,
           "menus_updated": "11/26 09:00", "solo_data": SOLO, "solo_updated": "11/26 09:00"}
    return coordinator.run(ctx, [dict(s) for s in STORES], agents, [], assumed=ASSUMED)


# ─────────── 예시: 처음에 보내 주신 A~E ───────────
EXAMPLE_WEATHER = {"time": "2026-11-26 12:00", "feels_like": 4.0, "yesterday": 10.0, "yesterday_source": "ASOS",
                   "comparison": "어제 같은 시각보다 6.0도 낮아요.", "direction": "따뜻한 국물",
                   "message": "따뜻한 국물요리 추천해요!"}
EXAMPLE = [
    {"id": "A", "area": 0, "name": "A 국밥집", "dist_m": walk_to_dist(8), "price": 9000, "soup": True},
    {"id": "B", "area": 0, "name": "B 라멘집", "dist_m": walk_to_dist(3), "price": 9500, "soup": True},
    {"id": "C", "area": 0, "name": "C 찌개집", "dist_m": walk_to_dist(6), "price": 9000, "soup": True},
    {"id": "D", "area": 0, "name": "D 돈까스집", "dist_m": walk_to_dist(5), "price": 8000, "soup": False},
    {"id": "E", "area": 0, "name": "E 덮밥집", "dist_m": walk_to_dist(4), "price": 12000, "soup": False},
]
EXAMPLE_SOLO = {"A": {"single_ok": True, "seat": True, "seat_text": "바 자리", "old_review": "2년 전"},
                "B": {"single_ok": True, "seat": True, "seat_text": "바 자리"},
                "C": {"single_ok": False}, "D": {"single_ok": True},
                "E": {"seat": True, "seat_text": "1인석"}}


def run_example(hurry=False):
    _, agents = agents_for(EXAMPLE_WEATHER)
    ctx = {"now": TODAY, "hurry": hurry, "budget": 10000, "diary": [], "solo_data": EXAMPLE_SOLO}
    return coordinator.run(ctx, [dict(s) for s in EXAMPLE], agents, [], assumed=ASSUMED)


def main(args):
    if "예시" in args:
        result = run_example("급함" in args)
        print("예시 A~E · 체감 4도 · 예산 1만 원" + (' · "시간이 없어요"' if "급함" in args else "") + "\n")
        print(result["text"])
        return result
    results = {}
    for code, words in PEOPLE.items():
        results[code] = run_person(code, "급함" in args)
        print(f"\n████ 혼밥 MBTI {code} ({words}) ████\n")
        print(results[code]["text"])
    return results


if __name__ == "__main__":
    main(sys.argv[1:])
