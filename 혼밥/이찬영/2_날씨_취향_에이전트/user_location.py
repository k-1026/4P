"""사용자 위치: 앱(핸드폰)이 보낸 위도·경도를 읽고, 거리·날씨 격자·가까운 관측소를 계산한다.

  parse(value)          앱이 보낸 {"lat", "lng", "accuracy_m", "time"} -> 확인한 위치 (틀리면 None)
  distance_m(...)       두 점 사이 직선거리 (m)
  to_grid(lat, lng)     기상청 단기예보 격자 (nx, ny)
  nearest_station(...)  가장 가까운 지상(ASOS) 관측소 (번호, 이름, km) -> 어제 같은 시각 값에 쓴다
  label(place)          화면에 보여 줄 짧은 글
"""
import math

# 지상(ASOS) 관측소 (번호, 이름, 위도, 경도). 어제 같은 시각 값을 가장 가까운 곳에서 가져온다
STATIONS = (
    (90, "속초", 38.2509, 128.5647), (101, "춘천", 37.9026, 127.7357), (105, "강릉", 37.7515, 128.8910),
    (108, "서울", 37.5714, 126.9658), (112, "인천", 37.4777, 126.6249), (114, "원주", 37.3376, 127.9466),
    (119, "수원", 37.2723, 126.9853), (127, "충주", 36.9705, 127.9525), (129, "서산", 36.7766, 126.4939),
    (130, "울진", 36.9918, 129.4128), (131, "청주", 36.6392, 127.4407), (133, "대전", 36.3720, 127.3721),
    (136, "안동", 36.5729, 128.7073), (138, "포항", 36.0320, 129.3800), (140, "군산", 36.0053, 126.7614),
    (143, "대구", 35.8780, 128.6530), (146, "전주", 35.8408, 127.1172), (152, "울산", 35.5601, 129.3201),
    (156, "광주", 35.1729, 126.8916), (159, "부산", 35.1047, 129.0320), (162, "통영", 34.8455, 128.4356),
    (165, "목포", 34.8169, 126.3812), (168, "여수", 34.7393, 127.7406), (184, "제주", 33.5141, 126.5297),
    (189, "서귀포", 33.2461, 126.5653), (192, "진주", 35.1638, 128.0400), (232, "천안", 36.7624, 127.2927),
    (279, "구미", 36.1306, 128.3206), (283, "경주", 35.8174, 129.2009),
)


def parse(value):
    """앱이 보낸 위치를 확인한다. 위도·경도가 숫자가 아니거나 범위를 벗어나면 None"""
    if not isinstance(value, dict):
        return None
    lat, lng = value.get("lat"), value.get("lng")
    if (isinstance(lat, bool) or isinstance(lng, bool) or not isinstance(lat, (int, float))
            or not isinstance(lng, (int, float)) or not -90 <= lat <= 90 or not -180 <= lng <= 180):
        return None
    accuracy = value.get("accuracy_m")
    if isinstance(accuracy, bool) or not isinstance(accuracy, (int, float)) or accuracy < 0:
        accuracy = None
    return {"lat": float(lat), "lng": float(lng), "accuracy_m": accuracy,
            "time": value.get("time") if isinstance(value.get("time"), (int, float)) else None,
            "source": "gps"}


def distance_m(lat1, lng1, lat2, lng2):
    """두 점 사이 직선거리 (m, 지구를 공으로 보고 계산)"""
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def to_grid(lat, lng):
    """위도·경도 -> 기상청 격자 (nx, ny). 기상청이 공개한 람베르트 정각원추도법 변환식"""
    re, grid = 6371.00877 / 5.0, 5.0
    slat1, slat2, olon, olat = (math.radians(v) for v in (30.0, 60.0, 126.0, 38.0))
    xo, yo = 43, 136
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(
        math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5))
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5) ** sn * math.cos(slat1) / sn
    ro = re * sf / math.tan(math.pi * 0.25 + olat * 0.5) ** sn
    ra = re * sf / math.tan(math.pi * 0.25 + math.radians(lat) * 0.5) ** sn
    theta = math.radians(lng) - olon
    theta = (theta + math.pi) % (2 * math.pi) - math.pi
    theta *= sn
    del grid
    return int(ra * math.sin(theta) + xo + 0.5), int(ro - ra * math.cos(theta) + yo + 0.5)


def nearest_station(lat, lng):
    """가장 가까운 지상 관측소 -> (번호, 이름, 거리 km)"""
    number, name, slat, slng = min(STATIONS, key=lambda s: distance_m(lat, lng, s[2], s[3]))
    return number, name, round(distance_m(lat, lng, slat, slng) / 1000)


def label(place):
    text = f"내 위치(위도 {place['lat']:.4f}, 경도 {place['lng']:.4f})"
    if place.get("accuracy_m") is not None:
        text += f" 오차 약 {round(place['accuracy_m'])}m"
    return text
