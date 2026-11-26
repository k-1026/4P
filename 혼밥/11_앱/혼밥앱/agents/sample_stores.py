"""임의 가게 데이터 (실제 가게 데이터가 들어오기 전까지 쓰는 예시).

핸드폰이 보낸 내 위치를 가운데에 두고, 예시 가게 6곳을 정해 둔 방향·거리에 놓는다.
그래서 어디에서 열어도 1km 안에 후보가 생기고, 거리는 실제 내 위치에서 잰 값이 된다.
메뉴·1인석 정보는 가정 에이전트(메뉴·혼밥)가 '갱신했다'고 보는 값이다 (scenario_demo와 같음).
"""
import math

import user_location

# (id, 이름, 앱 평점, 걸어서 약 몇 분, 방향(도, 북쪽 0 · 동쪽 90))
PLACES = (
    ("A", "A 국밥집", 4.5, 8, 40),
    ("B", "B 라멘집", 4.6, 3, 130),
    ("C", "C 찌개집", 4.4, 6, 220),
    ("F", "F 샤브집", 4.7, 6, 300),
    ("S", "삼덕 백반", 4.3, 7, 350),
    ("H", "H 파스타집", 4.9, 20, 180),   # 1km 밖 -> 후보에서 빠지는 예
)
MENUS = {  # 📋 메뉴 에이전트(가정)가 갱신한 메뉴
    "A": [{"name": "순대국", "price": 9000, "soup": True}, {"name": "내장탕", "price": 10000, "soup": True}],
    "B": [{"name": "돈코츠 라멘", "price": 9500, "soup": True}, {"name": "차슈 라멘", "price": 11500, "soup": True}],
    "C": [{"name": "김치찌개 (2인)", "price": 18000, "soup": True}],
    "F": [{"name": "1인 샤브", "price": 14000, "soup": True}, {"name": "프리미엄 1인 샤브", "price": 18000, "soup": True}],
    "S": [{"name": "백반", "price": 8000, "soup": False}, {"name": "제육 정식", "price": 9000, "soup": False}],
    "H": [{"name": "수제 파스타", "price": 16000, "soup": False}],
}
SOLO = {  # 🪑 혼밥 에이전트(가정)가 갱신한 1인분·좌석 정보
    "A": {"single_ok": True},
    "B": {"single_ok": True, "seat": True, "seat_text": "바 자리"},
    "C": {"single_ok": False},
    "F": {"single_ok": True, "seat": True, "seat_text": "1인 냄비 바 좌석"},
    "S": {"single_ok": True},
    "H": {"single_ok": True, "seat": True, "seat_text": "창가 1인석"},
}
DETOUR, M_PER_MIN = 1.3, 70  # 거리 에이전트가 쓰는 값: 걷는 길 = 직선 x 1.3, 분당 70m


def around(place):
    """내 위치 둘레에 예시 가게를 놓는다. 직선거리는 '걸어서 N분'이 되도록 거꾸로 계산한다."""
    stores = []
    for sid, name, rate, minutes, bearing in PLACES:
        meters = minutes * M_PER_MIN / DETOUR
        lat = place["lat"] + meters * math.cos(math.radians(bearing)) / 111320
        lng = place["lng"] + meters * math.sin(math.radians(bearing)) / (111320 * math.cos(math.radians(place["lat"])))
        dist = round(user_location.distance_m(place["lat"], place["lng"], lat, lng))
        stores.append({"id": sid, "area": 0, "name": name, "rate": rate, "lat": lat, "lng": lng,
                       "dist_m": dist, "dist_from": "내 위치", "walk_min": math.ceil(dist / 67), "sample": True})
    return stores
