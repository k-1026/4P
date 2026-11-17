"""
3단계 사전 확인: 한국관광공사 관광정보 API에 대봉1동 식당이 몇 곳이나 있는지 조회

하는 일
  1. base_중구_대봉1동.csv의 좌표 중심에서 반경 1km 안의 음식점을 관광정보 API로 조회
  2. 174곳과 상호 + 거리로 비교
  3. 각 음식점의 영업시간·쉬는날·메뉴(소개정보)를 가져와 CSV로 저장

필요한 것
  환경변수 TOUR_API_KEY (공공데이터포털 인증키, 코드에 쓰지 않음)
  같은 폴더의 base_중구_대봉1동.csv

실행 (명령 프롬프트)
  set TOUR_API_KEY=키값
  python step3_tour_check.py

결과: tour_중구_대봉1동_확인.csv (기본표 수정 없음)
"""
import csv
import difflib
import math
import os
import re
import sys
import time

import requests

BASE_FILE = "base_중구_대봉1동.csv"
OUT_FILE = "tour_중구_대봉1동_확인.csv"
API = "https://apis.data.go.kr/B551011/KorService2"
RADIUS_M = 1000
MATCH_DIST_M = 200   # 이 거리 안에서만 같은 식당 후보로 봄
MATCH_NAME = 0.6     # 상호 유사도 기준

KEY = os.environ.get("TOUR_API_KEY")
if not KEY:
    sys.exit("TOUR_API_KEY 환경변수가 없습니다.")


def call(op, **params):
    """API 호출. 오류 메시지에 인증키가 찍히지 않도록 주소는 출력하지 않음"""
    params.update(serviceKey=KEY, MobileOS="ETC", MobileApp="DaeguMealMap", _type="json")
    try:
        r = requests.get(f"{API}/{op}", params=params, timeout=20)
    except requests.RequestException as e:
        sys.exit(f"{op} 요청 실패: {type(e).__name__}")
    try:
        data = r.json()
    except ValueError:
        sys.exit(f"{op} 응답이 JSON이 아닙니다 (상태 {r.status_code}): {r.text[:200].replace(KEY, '***')}")
    head = data.get("response", {}).get("header", {})
    if head.get("resultCode") != "0000":
        sys.exit(f"{op} 오류: {str(data)[:300].replace(KEY, '***')}")
    return data["response"]["body"]


def items_of(body):
    items = body.get("items")
    if not items:          # 결과가 없으면 빈 문자열로 옴
        return []
    item = items["item"]
    return item if isinstance(item, list) else [item]


def norm(name):
    return re.sub(r"[\s()\[\]·\-_.,&;]|본점|별관|분점|직영점|식당|대구", "", name or "").lower()


def dist_m(lat1, lon1, lat2, lon2):
    dy = (lat1 - lat2) * 111320
    dx = (lon1 - lon2) * 111320 * math.cos(math.radians(lat1))
    return math.hypot(dx, dy)


with open(BASE_FILE, encoding="utf-8-sig") as f:
    base = list(csv.DictReader(f))
lat_c = sum(float(b["위도"]) for b in base) / len(base)
lon_c = sum(float(b["경도"]) for b in base) / len(base)

# 1) 반경 안 음식점 전체 조회
found, page = [], 1
while True:
    body = call("locationBasedList2", mapX=lon_c, mapY=lat_c, radius=RADIUS_M,
                contentTypeId=39, arrange="E", numOfRows=100, pageNo=page)
    found += items_of(body)
    if len(found) >= int(body.get("totalCount") or 0) or not items_of(body):
        break
    page += 1
    time.sleep(0.3)

# 2) 174곳과 비교 + 3) 소개정보
rows = []
for t in found:
    lat, lon = float(t["mapy"]), float(t["mapx"])
    best, best_score, best_d = None, 0, None
    for b in base:
        d = dist_m(lat, lon, float(b["위도"]), float(b["경도"]))
        if d > MATCH_DIST_M:
            continue
        a, c = norm(t["title"]), norm(b["상호"] + b["지점"])
        score = difflib.SequenceMatcher(None, a, c).ratio()
        if a and c and (a in c or c in a):
            score = max(score, 0.9)
        if score > best_score:
            best, best_score, best_d = b, score, d

    intro = items_of(call("detailIntro2", contentId=t["contentid"], contentTypeId=39))
    intro = intro[0] if intro else {}
    time.sleep(0.3)

    matched = best is not None and best_score >= MATCH_NAME
    rows.append({
        "관광_ID": t["contentid"],
        "관광_상호": t["title"],
        "관광_주소": t.get("addr1", ""),
        "중심거리_m": round(dist_m(lat, lon, lat_c, lon_c)),
        "기본표_연결": "O" if matched else "",
        "기본표_상가ID": best["상가ID"] if matched else "",
        "기본표_상호": best["상호"] if matched else "",
        "상호유사도": round(best_score, 2) if best else "",
        "연결거리_m": round(best_d) if matched else "",
        "영업시간": intro.get("opentimefood", ""),
        "쉬는날": intro.get("restdatefood", ""),
        "대표메뉴": intro.get("firstmenu", ""),
        "취급메뉴": intro.get("treatmenu", ""),
        "좌석수": intro.get("seat", ""),
        "포장": intro.get("packing", ""),
        "주차": intro.get("parkingfood", ""),
    })

if rows:
    with open(OUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

matched = [r for r in rows if r["기본표_연결"]]
print(f"반경 {RADIUS_M}m 안 관광정보 음식점: {len(rows)}곳")
print(f"기본표 {len(base)}곳과 연결된 수: {len(matched)}곳 (식당 기준 {len({r['기본표_상가ID'] for r in matched})}곳)")
print(f"연결된 곳 중 영업시간 있음: {sum(1 for r in matched if r['영업시간'])}곳")
print(f"연결된 곳 중 쉬는날 있음: {sum(1 for r in matched if r['쉬는날'])}곳")
print(f"연결된 곳 중 메뉴 있음: {sum(1 for r in matched if r['대표메뉴'] or r['취급메뉴'])}곳")
print(f"저장 완료: {OUT_FILE}")
