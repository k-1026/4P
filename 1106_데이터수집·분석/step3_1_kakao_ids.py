"""
3-1단계: 기본표의 각 식당을 카카오 장소 ID와 연결 (카카오 공식 로컬 API만 사용)

하는 일
  식당의 상호로, 그 식당 좌표 반경 100m 안의 음식점을 검색해 가장 맞는 곳 1개를 고름
  상호 유사도에 따라 상태를 '연결' / '확인 필요' / '없음'으로 표시

필요한 것
  환경변수 KAKAO_REST_KEY (코드에 쓰지 않음)
  같은 폴더의 base_중구_대봉1동.csv

실행
  python step3_1_kakao_ids.py 5     ← 앞에서 5곳만 시험 (결과: kakao_ids_시험.csv)
  python step3_1_kakao_ids.py       ← 전체 (결과: kakao_ids_중구_대봉1동.csv)
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
BASE_FILE = f"base_{AREA}.csv"
URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
RADIUS_M = 100
SCORE_OK = 0.8       # 이상이면 '연결'
SCORE_CHECK = 0.5    # 이상이면 '확인 필요', 미만이면 '없음'
WAIT_SEC = 0.3

KEY = os.environ.get("KAKAO_REST_KEY")
if not KEY:
    sys.exit("KAKAO_REST_KEY 환경변수가 없습니다. 새 명령 프롬프트 창에서 실행해 보세요.")

limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
out_file = "kakao_ids_시험.csv" if limit else f"kakao_ids_{AREA}.csv"


def norm(name):
    return re.sub(r"[\s()\[\]·\-_.,&;]|본점|별관|분점|직영점|식당|대구", "", name or "").lower()


def score(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0
    if a in b or b in a:
        return max(0.9, difflib.SequenceMatcher(None, a, b).ratio())
    return difflib.SequenceMatcher(None, a, b).ratio()


def search(name, lon, lat):
    try:
        r = requests.get(URL, headers={"Authorization": f"KakaoAK {KEY}"}, timeout=20, params={
            "query": name, "x": lon, "y": lat, "radius": RADIUS_M,
            "category_group_code": "FD6", "sort": "distance", "size": 15,
        })
    except requests.RequestException as e:
        sys.exit(f"요청 실패: {type(e).__name__}")
    if r.status_code != 200:
        sys.exit(f"카카오 API 오류 (상태 {r.status_code}): {r.text[:300]}")
    return r.json()["documents"]


with open(BASE_FILE, encoding="utf-8-sig") as f:
    base = list(csv.DictReader(f))
if limit:
    base = base[:limit]

rows, stat = [], Counter()
for b in base:
    name = b["상호"]
    full = name + b["지점"]
    docs = search(name, b["경도"], b["위도"])
    time.sleep(WAIT_SEC)

    scored = sorted(((score(full, d["place_name"]), d) for d in docs),
                    key=lambda p: (-p[0], int(p[1].get("distance") or 0)))
    best_s, best = scored[0] if scored else (0, None)
    tied = sum(1 for s, _ in scored if s >= SCORE_OK) >= 2

    if best is None or best_s < SCORE_CHECK:
        status = "없음"
    elif best_s >= SCORE_OK and not tied:
        status = "연결"
    else:
        status = "확인 필요"
    stat[status] += 1

    show = best if status != "없음" else None
    rows.append({
        "상가ID": b["상가ID"],
        "상호": name,
        "지점": b["지점"],
        "상태": status,
        "카카오ID": show["id"] if show else "",
        "카카오상호": show["place_name"] if show else "",
        "상호유사도": round(best_s, 2) if best else "",
        "거리_m": show.get("distance", "") if show else "",
        "카카오분류": show["category_name"] if show else "",
        "카카오주소": (show["road_address_name"] or show["address_name"]) if show else "",
        "전화": show["phone"] if show else "",
        "place_url": show["place_url"] if show else "",
        "후보수": len(docs),
        "후보목록": " / ".join(d["place_name"] for d in docs[:5]),
    })

with open(out_file, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print(f"조회: {len(rows)}곳 / " + ", ".join(f"{k} {v}곳" for k, v in stat.items()))
for r in rows:
    print(f"- {r['상호']} {r['지점']} → [{r['상태']}] {r['카카오상호']} (유사도 {r['상호유사도']}, {r['거리_m']}m, 후보 {r['후보수']})")
print(f"저장 완료: {out_file}")
