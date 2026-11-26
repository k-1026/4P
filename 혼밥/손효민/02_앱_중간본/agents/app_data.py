"""혼밥 앱(혼밥_홈화면_v2.html)이 보낸 데이터 읽기: 내 혼밥일기와 가게 목록.

앱은 일기를 브라우저 안에 저장해서 파이썬이 직접 못 읽는다. 그래서 앱이
  ① 에이전트 화면(app.py)이 켜져 있으면 http://localhost:8765/app-sync 로 보내고 -> 앱데이터.json
  ② 꺼져 있으면 honbap_agent_data.json 파일로 내려받게 한다 -> 다운로드 폴더
에이전트는 둘 중 더 최근 것을 읽는다.
"""
import glob
import json
import math
import os
from datetime import datetime

import mbti
import user_location

FOLDER = os.path.dirname(os.path.abspath(__file__))
FILE = "앱데이터.json"
DOWNLOAD_PATTERN = "honbap_agent_data*.json"
MAX_BYTES = 2_000_000
WALK_M_PER_MIN = 67  # 걷는 속도 (분당 약 67m = 시속 4km)

# 앱의 가게 분류(cat) -> 취향 에이전트의 11가지 음식 종류. 메뉴 이름이 더 정확하면 MENU_WORDS가 먼저
CAT_MAP = {"국밥": "국밥·탕", "라멘": "면", "우동": "면", "국수": "면", "한식": "밥·덮밥",
           "고기": "고기·구이", "양식": "기타", "버거": "빵·패스트푸드", "샤브": "찌개",
           "덮밥": "밥·덮밥", "분식": "분식", "편의점": "밥·덮밥", "뷔페": "기타",
           "돈까스": "튀김·까스", "초밥": "초밥·회", "샐러드": "가벼운 식사"}
MENU_WORDS = (("분식", ("김밥", "떡볶이", "라볶이")),
              ("국밥·탕", ("국밥", "곰탕", "순대국", "설렁탕", "해장국", "갈비탕", "감자탕")),
              ("찌개", ("찌개", "전골", "샤브")),
              ("면", ("라멘", "우동", "국수", "소바", "냉면", "칼국수", "짬뽕", "짜장", "파스타", "쌀국수")),
              ("밥·덮밥", ("덮밥", "텐동", "비빔밥", "백반", "도시락", "카레", "볶음밥")),
              ("튀김·까스", ("돈까스", "카츠", "치킨", "가라아게")),
              ("초밥·회", ("초밥", "스시", "사시미")),
              ("빵·패스트푸드", ("버거", "샌드위치", "토스트")),
              ("가벼운 식사", ("샐러드", "포케", "죽")))
COLD_WORDS = ("냉면", "물회", "냉모밀", "메밀", "샐러드", "포케", "콩국수")


def food_kind(store):
    """가게 하나의 음식 종류 (메뉴 에이전트가 생기면 이 일은 메뉴 에이전트가 한다)"""
    menu = f"{store.get('menu', '')} {store.get('name', '')}"
    for kind, words in MENU_WORDS:
        if any(word in menu for word in words):
            return kind
    return CAT_MAP.get(store.get("cat", ""), "기타")


def weather_type(store):
    """날씨 에이전트가 쓰는 음식 종류: 따뜻한 국물 / 따뜻한 요리 / 차가운 요리"""
    menu = f"{store.get('menu', '')} {store.get('name', '')}"
    if any(word in menu for word in COLD_WORDS):
        return "차가운 요리"
    return "따뜻한 국물" if store.get("soup") else "따뜻한 요리"


def validate(data):
    """앱이 보낸 값을 확인하고 필요한 것만 남긴다. 모양이 틀리면 ValueError."""
    if not isinstance(data, dict) or not isinstance(data.get("posts"), list) \
            or not isinstance(data.get("restaurants"), list):
        raise ValueError("앱 데이터 모양이 달라요 (posts, restaurants가 필요해요)")
    stores = []
    for r in data["restaurants"]:
        if isinstance(r, dict) and isinstance(r.get("id"), (int, float)) and str(r.get("name") or "").strip():
            stores.append({key: r.get(key) for key in (
                "id", "area", "name", "cat", "rate", "cnt", "tags", "seat", "kiosk", "wait",
                "dist", "min", "price", "menu", "soup", "grill", "outlet", "quiet", "lat", "lng")})
    posts = []
    for p in data["posts"]:
        if isinstance(p, dict):
            posts.append({"id": str(p.get("id", "")), "ts": p.get("ts"), "rid": p.get("rid"),
                          "rate": p.get("rate"), "text": str(p.get("text") or "")[:500],
                          "points": [str(t) for t in p.get("points") or [] if isinstance(t, str)]})
    areas = [str(a) for a in data.get("areas") or [] if isinstance(a, str)]
    code = str(data.get("mbti") or "").upper()
    return {"version": data.get("version", 1), "exported": data.get("exported"),
            "nick": str(data.get("nick") or "")[:12], "mbti": code if mbti.parse(code) else None,
            "mbti_pct": data.get("mbti_pct") if mbti.parse(code) and mbti.parse_pct(code, data.get("mbti_pct"))[0] else None,
            "location": user_location.parse(data.get("location")),
            "posts": posts, "restaurants": stores, "areas": areas}


def save(data, folder=FOLDER):
    clean = validate(data)
    with open(os.path.join(folder, FILE), "w", encoding="utf-8") as file:
        json.dump(clean, file, ensure_ascii=False, indent=2)
    return clean


def find(folder=FOLDER):
    """앱데이터.json과 (진짜 폴더일 때만) 다운로드 폴더의 파일 중 가장 최근 것"""
    paths = [os.path.join(folder, FILE)]
    if os.path.abspath(folder) == FOLDER:
        paths += glob.glob(os.path.join(os.path.expanduser("~"), "Downloads", DOWNLOAD_PATTERN))
    paths = [path for path in paths if os.path.isfile(path)]
    return max(paths, key=os.path.getmtime) if paths else None


def load(folder=FOLDER):
    """앱 데이터 (없거나 읽을 수 없으면 None)"""
    path = find(folder)
    if path is None or os.path.getsize(path) > MAX_BYTES:
        return None
    try:
        with open(path, encoding="utf-8-sig") as file:
            data = validate(json.load(file))
    except (OSError, ValueError):
        return None
    data["path"] = path
    return data


def stores(data):
    """조율자와 에이전트들이 같이 쓰는 가게 목록.
    사용자 위치와 가게 좌표가 있으면 내 위치에서 잰 직선거리, 없으면 앱이 적어 둔 거리(dist)를 쓴다."""
    place, result = data.get("location"), []
    for r in data["restaurants"]:
        dist, src = (r.get("dist"), "앱 거리값") if isinstance(r.get("dist"), (int, float)) else (None, None)
        if place and all(isinstance(r.get(k), (int, float)) for k in ("lat", "lng")):
            dist, src = round(user_location.distance_m(place["lat"], place["lng"], r["lat"], r["lng"])), "내 위치"
        result.append({**r, "kind": food_kind(r), "weather_type": weather_type(r), "dist_m": dist, "dist_from": src,
                       "walk_min": None if dist is None else max(1, math.ceil(dist / WALK_M_PER_MIN))})
    return result


def kinds(data):
    """가게 이름 -> 음식 종류 (취향 에이전트용)"""
    return {r["name"].strip(): food_kind(r) for r in data["restaurants"]}


def diary(data):
    """앱의 내 일기 -> 취향 에이전트의 일기 모양. 가게를 찾을 수 없는 일기도 넘겨서 '읽지 못한 일기'로 센다."""
    names = {r["id"]: r["name"] for r in data["restaurants"]}
    result = []
    for p in data["posts"]:
        try:
            when = datetime.fromtimestamp(float(p["ts"]) / 1000).strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError, OverflowError, OSError):
            when = None
        points = [t.split(" ", 1)[1] if " " in t else t for t in p["points"]]  # '⚡ 빨리 나옴' -> '빨리 나옴'
        result.append({"날짜": when, "가게": names.get(p["rid"], ""), "별점": p["rate"],
                       "혼밥포인트": points, "후기": p["text"]})
    return result
