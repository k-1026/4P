"""날씨 에이전트: 내 위치(없으면 대구)의 체감온도로 음식 방향을 알려준다."""
import json
import math
import os
import sys
from datetime import datetime, timedelta
from urllib.parse import urlencode
from urllib.request import urlopen

import user_location

URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
FOLDER = os.path.dirname(os.path.abspath(__file__))
NX, NY = 90, 91  # 대구 관측소(ASOS 143)가 있는 격자
PAST_URL = "https://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList"
STATION = 143  # 대구 관측소 (ASOS)


# 1. API 키 읽기
def read_key(folder):
    path = os.path.join(folder, "api_key.txt")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8-sig") as file:
        key = file.read().strip()
    if not key or not key.isascii():  # 안내 문구(한글)가 그대로면 키가 없는 것
        return None
    return key


# 2. 날씨 가져오기
def get_weather(key, when, grid=(NX, NY)):
    params = {"serviceKey": key, "pageNo": 1, "numOfRows": 10, "dataType": "JSON",
              "base_date": when.strftime("%Y%m%d"), "base_time": when.strftime("%H00"),
              "nx": grid[0], "ny": grid[1]}
    text = ""
    try:
        text = urlopen(URL + "?" + urlencode(params), timeout=10).read().decode("utf-8")
        items = json.loads(text)["response"]["body"]["items"]["item"]
        data = {item["category"]: float(item["obsrValue"]) for item in items}
        # 체감온도 계산에 필요한 값이 없거나 결측(-999 등)이면 사용하지 않는다
        if any(data[name] <= -900 for name in ("T1H", "REH", "WSD")):
            raise ValueError("관측값이 비어 있어요")
        return data
    except Exception as error:
        print(f"{when:%m월 %d일 %H시} 날씨를 가져오지 못했어요:", error)
        if text:
            print(text[:500])
        return None


# 전날 값: ASOS 시간자료 (전날까지의 관측값만 제공)
def get_past_weather(key, when, station=STATION):
    day, hour = when.strftime("%Y%m%d"), when.strftime("%H")
    params = {"serviceKey": key, "pageNo": 1, "numOfRows": 1, "dataType": "JSON",
              "dataCd": "ASOS", "dateCd": "HR", "startDt": day, "startHh": hour,
              "endDt": day, "endHh": hour, "stnIds": station}
    text = ""
    try:
        text = urlopen(PAST_URL + "?" + urlencode(params), timeout=10).read().decode("utf-8")
        item = json.loads(text)["response"]["body"]["items"]["item"][0]
        # 이름을 실황 API와 맞춘다: 기온, 습도, 풍속 (빈 값이면 오류 처리)
        return {"T1H": float(item["ta"]), "REH": float(item["hm"]), "WSD": float(item["ws"])}
    except Exception as error:
        print(f"{when:%m월 %d일 %H시} 과거 날씨를 가져오지 못했어요:", error)
        if text:
            print(text[:500])
        return None


# 3. 체감온도 계산하기 (기상청 공식)
def feels_like(data, month):
    temp = data["T1H"]
    if 5 <= month <= 9:  # 여름: 습도 사용
        rh = data["REH"]
        tw = (temp * math.atan(0.151977 * (rh + 8.313659) ** 0.5)
              + math.atan(temp + rh) - math.atan(rh - 1.676331)
              + 0.00391838 * rh ** 1.5 * math.atan(0.023101 * rh) - 4.686035)
        result = (-0.2442 + 0.55399 * tw + 0.45535 * temp
                  - 0.0022 * tw ** 2 + 0.00278 * tw * temp + 3.0)
    elif temp <= 10 and data["WSD"] >= 1.3:  # 겨울: 바람 사용
        wind = (data["WSD"] * 3.6) ** 0.16
        result = 13.12 + 0.6215 * temp - 11.37 * wind + 0.3965 * wind * temp
    else:
        result = temp
    return round(result, 1)


# 4. 음식 방향 판단하기 (지금 체감온도 기준)
def recommend(now):
    if now <= 5:
        return "따뜻한 국물", "따뜻한 국물요리 추천해요!"
    if now <= 10:
        return "따뜻한 요리", "따뜻한 요리 추천해요!"
    if now < 26:
        return "없음", "상관없어요. 원하는 음식을 골라 보세요!"
    return "차가운 요리", "차가운 요리 추천해요!"


# 어제와의 차이를 말로 만들기 (같은 시각 값일 때만)
def compare(now, yesterday, source):
    if yesterday is None or source != "ASOS":
        return None
    diff = round(now - yesterday, 1)
    if diff == 0:
        return "어제 같은 시각과 같아요."
    return f"어제 같은 시각보다 {abs(diff)}도 {'높아요' if diff > 0 else '낮아요'}."


# 다른 에이전트의 말에 답하기: 가게의 음식 종류가 지금 날씨에 맞는지만 판단한다
def reply(report, sender, store, food_type):
    """report는 main()의 결과. food_type은 "따뜻한 국물", "따뜻한 요리", "차가운 요리", "모름"."""
    direction = report["direction"]
    warm = ("따뜻한 국물", "따뜻한 요리")
    if direction == "없음":
        fits, text = None, "지금은 날씨 때문에 음식을 가릴 필요가 없어요."
    elif food_type not in warm + ("차가운 요리",):
        fits, text = None, "음식 종류를 몰라서 날씨에 맞는지 판단할 수 없어요."
    elif direction == "차가운 요리":
        fits = food_type != "따뜻한 국물"
        if food_type == "차가운 요리":
            text = "시원한 음식이라 날씨에 맞아요."
        elif fits:
            text = "더운 날이지만 국물요리가 아니라 괜찮아요."
        else:
            text = "더운 날이라 날씨에는 맞지 않아요."
    elif food_type == "차가운 요리":
        fits, text = False, "추운 날이라 차가운 음식은 날씨에 맞지 않아요."
    elif direction == "따뜻한 국물" and food_type == "따뜻한 요리":
        fits, text = True, "따뜻해서 날씨에는 괜찮지만, 국물요리가 더 좋아요."
    else:
        ending = "이라" if food_type == "따뜻한 국물" else "라"
        fits, text = True, f"{food_type}{ending} 날씨에는 맞아요."
    message = f"{sender} 의견 확인했어요. {store}: {text} (체감 {report['feels_like']}도)"
    return {"agent": "날씨", "to": sender, "store": store, "fits": fits, "message": message}


# 날씨 점수표: SCORES[지금 날씨 방향][가게 음식 종류]
SCORES = {"따뜻한 국물": {"따뜻한 국물": 10, "따뜻한 요리": 5, "차가운 요리": 0},
          "따뜻한 요리": {"따뜻한 국물": 10, "따뜻한 요리": 10, "차가운 요리": 0},
          "없음": {"따뜻한 국물": 5, "따뜻한 요리": 5, "차가운 요리": 5},
          "차가운 요리": {"따뜻한 국물": 0, "따뜻한 요리": 5, "차가운 요리": 10}}


# 가게의 날씨 점수. 퍼센트를 곱해 합치는 일은 조율자가 한다
def score(report, food_type):
    points = SCORES[report["direction"]].get(food_type)
    if points is None:  # 음식 종류를 모르면 중간 점수
        return {"agent": "날씨", "score": 5, "confirmed": False}
    return {"agent": "날씨", "score": points, "confirmed": True}


# 반론하기: 다른 에이전트가 미는 가게와 지금 1순위 가게를 날씨 점수로 비교한다
def rebut(report, sender, proposed, proposed_type, current, current_type):
    """proposed는 상대가 미는 가게, current는 지금 1순위 가게."""
    direction = report["direction"]
    fit = {} if direction == "없음" else SCORES[direction]
    new, old = fit.get(proposed_type), fit.get(current_type)
    first = f"{proposed} 쪽({proposed_type})"
    second = f"{current} 쪽({current_type})"
    if not fit:
        stance, text = "판단 안 함", f"지금은 날씨로 반론할 것이 없어요. {first}도 괜찮아요."
    elif new is None or old is None:
        stance, text = "판단 안 함", f"음식 종류를 몰라서 {first}과 {second}을 비교할 수 없어요."
    elif new < old:
        stance, text = "반대", f"날씨로는 {second}이 {first}보다 나아요."
    elif new == 0:
        stance, text = "반대", f"{first}도 {second}도 날씨에 맞지 않아요. 다른 곳을 찾아봐요."
    elif new > old:
        stance, text = "동의", f"날씨로는 {first}이 {second}보다 나아요."
    else:
        good = "맞아요" if new == 10 else "괜찮아요"
        stance, text = "동의", f"{first}도 날씨에는 {good}."
    message = f"{sender} 의견에 대해: {text} (체감 {report['feels_like']}도)"
    return {"agent": "날씨", "to": sender, "stance": stance, "message": message}


# 5. 실행하기: 실행할 때마다 API에서 지금과 전날 값을 가져온다
def where(place):
    """날씨를 볼 곳: 사용자 위치가 있으면 그 격자와 가장 가까운 관측소, 없으면 대구 관측소"""
    if not place:
        return {"grid": (NX, NY), "station": STATION, "label": "대구 관측소 (내 위치 없음)", "mine": False}
    grid = user_location.to_grid(place["lat"], place["lng"])
    station, name, km = user_location.nearest_station(place["lat"], place["lng"])
    return {"grid": grid, "station": station, "mine": True,
            "label": f"{user_location.label(place)} · 어제 값은 {name} 관측소({km}km)"}


def main(today=None, fetch=get_weather, folder=FOLDER, fetch_past=get_past_weather, place=None):
    """place: user_location.parse()로 읽은 사용자 위치 (없으면 대구)"""
    today = today or datetime.now()
    spot = where(place)
    if spot["mine"]:  # 기본값(대구)일 때는 예전처럼 부른다 (시험용 가짜 함수와 맞추기 위해)
        fetch = (lambda f: lambda key, when: f(key, when, spot["grid"]))(fetch)
        fetch_past = (lambda f: lambda key, when: f(key, when, spot["station"]))(fetch_past)

    key = read_key(folder)
    if key is None:
        print("api_key.txt 파일에 API 키를 넣고 저장해 주세요.")
        return None

    weather_time = today - timedelta(minutes=15)  # 자료가 늦게 올라와서 15분 전
    today_data = fetch(key, weather_time)
    if today_data is None:
        return None
    now = feels_like(today_data, weather_time.month)

    # 전날 같은 시각의 값은 ASOS에서 가져온다
    old_time = weather_time - timedelta(days=1)
    old_data = fetch_past(key, old_time)
    source = "ASOS"
    if old_data is None:
        # 대체값: 실황 API는 최근 24시간만 주므로 23시간 전 정시를 요청한다
        old_time = today - timedelta(hours=23)
        if old_time.date() < weather_time.date():  # 23:00~00:14에는 전날 값이 없다
            old_data = fetch(key, old_time)
            source = "대체값"
    yesterday = None if old_data is None else feels_like(old_data, old_time.month)
    if yesterday is None:
        source = None

    direction, message = recommend(now)
    print("지금 체감온도:", now)
    if yesterday is None:
        print("전날 체감온도: 가져오지 못함")
    else:
        note = " (대체값: 같은 시각이 아니에요)" if source == "대체값" else ""
        print(f"전날 {old_time:%H시} 체감온도: {yesterday}{note}")
    comparison = compare(now, yesterday, source)
    if comparison:
        print(comparison)
    print(message)

    # 다른 에이전트(조율자)가 읽는 결과 파일
    report = {"time": today.strftime("%Y-%m-%d %H:%M"), "feels_like": now,
              "yesterday": yesterday, "yesterday_source": source, "comparison": comparison,
              "direction": direction, "message": message,
              "where": spot["label"], "grid": list(spot["grid"]), "station": spot["station"]}
    with open(os.path.join(folder, "weather_result.json"), "w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    return report


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
