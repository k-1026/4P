"""
3-1단계 보충: 1차에서 '없음'이 나온 식당을 주변 음식점 목록으로 다시 찾기 (카카오 공식 API만 사용)

하는 일
  식당 좌표 반경 50m 안의 음식점 목록을 받아 상호의 겹치는 글자로 비교
  이미 1차에서 다른 식당에 연결된 카카오 장소는 후보에서 제외
  찾은 곳은 모두 '확인 필요'로 표시 (사람 또는 추가 정보로 확인 전까지 확정하지 않음)

필요한 것
  환경변수 KAKAO_REST_KEY, 같은 폴더의 kakao_ids_중구_대봉1동.csv, base_중구_대봉1동.csv

실행
  python step3_1b_kakao_retry.py

결과: kakao_ids_2차_중구_대봉1동.csv (1차 결과 파일은 수정하지 않음)
"""
import csv
import difflib
import os
import re
import sys
import time
from collections import Counter

import requests

AREA = "중구_대봉1동"
URL = "https://dapi.kakao.com/v2/local/search/category.json"
RADIUS_M = 50
MAX_PAGES = 3
MIN_COMMON = 2       # 겹치는 글자 최소 수
MIN_RATIO = 0.6      # 겹치는 글자 수 / 짧은 쪽 상호 길이
WAIT_SEC = 0.3

KEY = os.environ.get("KAKAO_REST_KEY")
if not KEY:
    sys.exit("KAKAO_REST_KEY 환경변수가 없습니다. 새 명령 프롬프트 창에서 실행해 보세요.")


def norm(name):
    return re.sub(r"[\s()\[\]·\-_.,&;]|본점|별관|분점|직영점|식당|대구|대봉점|점$", "", name or "").lower()


def common_len(a, b):
    m = difflib.SequenceMatcher(None, a, b).find_longest_match(0, len(a), 0, len(b))
    return m.size


def nearby(lon, lat):
    docs = []
    for page in range(1, MAX_PAGES + 1):
        try:
            r = requests.get(URL, headers={"Authorization": f"KakaoAK {KEY}"}, timeout=20, params={
                "category_group_code": "FD6", "x": lon, "y": lat, "radius": RADIUS_M,
                "sort": "distance", "size": 15, "page": page,
            })
        except requests.RequestException as e:
            sys.exit(f"요청 실패: {type(e).__name__}")
        if r.status_code != 200:
            sys.exit(f"카카오 API 오류 (상태 {r.status_code}): {r.text[:300]}")
        data = r.json()
        docs += data["documents"]
        time.sleep(WAIT_SEC)
        if data["meta"]["is_end"]:
            break
    return docs


with open(f"kakao_ids_{AREA}.csv", encoding="utf-8-sig") as f:
    first = list(csv.DictReader(f))
with open(f"base_{AREA}.csv", encoding="utf-8-sig") as f:
    base = {b["상가ID"]: b for b in csv.DictReader(f)}

taken = {r["카카오ID"] for r in first if r["카카오ID"]}
rows, stat = [], Counter()
for r in [x for x in first if x["상태"] == "없음"]:
    b = base[r["상가ID"]]
    a = norm(r["상호"] + r["지점"])
    cands = []
    all_docs = nearby(b["경도"], b["위도"])
    for d in all_docs:
        if d["id"] in taken:
            continue
        c = norm(d["place_name"])
        n = common_len(a, c)
        if n >= MIN_COMMON and n / min(len(a), len(c)) >= MIN_RATIO:
            cands.append((n / min(len(a), len(c)), n, d))
    cands.sort(key=lambda p: (-p[0], -p[1], int(p[2].get("distance") or 0)))
    best = cands[0][2] if cands else None
    status = "확인 필요" if best else "없음"
    stat[status] += 1
    rows.append({
        "상가ID": r["상가ID"],
        "상호": r["상호"],
        "지점": r["지점"],
        "상가업종": b["업종"],
        "도로명주소": b["도로명주소"],
        "상태": status,
        "카카오ID": best["id"] if best else "",
        "카카오상호": best["place_name"] if best else "",
        "겹침비율": round(cands[0][0], 2) if best else "",
        "거리_m": best.get("distance", "") if best else "",
        "카카오분류": best["category_name"] if best else "",
        "카카오주소": (best["road_address_name"] or best["address_name"]) if best else "",
        "place_url": best["place_url"] if best else "",
        "주변음식점수": len(all_docs),
        "후보목록": " / ".join(c[2]["place_name"] for c in cands[:3]),
    })

out = f"kakao_ids_2차_{AREA}.csv"
with open(out, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print(f"재검색: {len(rows)}곳 / " + ", ".join(f"{k} {v}곳" for k, v in stat.items()))
for x in rows:
    if x["상태"] != "없음":
        print(f"- {x['상호']} {x['지점']} → {x['카카오상호']} ({x['겹침비율']}, {x['거리_m']}m) | {x['카카오분류']}")
print("주변 음식점 0곳인 식당:", ", ".join(x["상호"] for x in rows if x["주변음식점수"] == 0) or "없음")
print(f"저장 완료: {out}")
