"""
버틴집 가설 시험 2단계: 표본 60곳의 카카오 장소 ID 찾기 (공식 API)

좌표가 있으면 반경 100m 키워드 검색, 없거나 못 찾으면 '대구 중구 + 상호'로 검색 후 주소 확인
필요한 것: 환경변수 KAKAO_REST_KEY, 시험표본_중구.csv,
           ..\\과제\\docs\\daegu_pay\\6_대구전체_음식점_영업기간\\대구전체_일반음식점_WGS84.csv (좌표)
결과: 시험표본_카카오ID.csv
집단별 비교 전이므로 상호와 평점을 출력하지 않음
"""
import csv
import difflib
import os
import re
import sys
import time
from collections import Counter

import requests

URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
COORD_FILE = r"..\과제\docs\daegu_pay\6_대구전체_음식점_영업기간\대구전체_일반음식점_WGS84.csv"
KEY = os.environ.get("KAKAO_REST_KEY")
if not KEY:
    sys.exit("KAKAO_REST_KEY 환경변수가 없습니다.")


def norm(name):
    name = re.sub(r"\(.*?\)", "", name or "")
    return re.sub(r"[\s\[\]·\-_.,&;]|본점|별관|분점|직영점|식당|대구", "", name).lower()


def score(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0
    r = difflib.SequenceMatcher(None, a, b).ratio()
    return max(0.9, r) if a in b or b in a else r


def search(**params):
    try:
        r = requests.get(URL, headers={"Authorization": f"KakaoAK {KEY}"}, timeout=20, params=params)
    except requests.RequestException as e:
        sys.exit(f"요청 실패: {type(e).__name__}")
    if r.status_code != 200:
        sys.exit(f"카카오 API 오류 (상태 {r.status_code})")
    time.sleep(0.3)
    return r.json()["documents"]


with open(COORD_FILE, encoding="utf-8-sig") as f:
    coord = {r["관리번호"]: r for r in csv.DictReader(f)}
with open("시험표본_중구.csv", encoding="utf-8-sig") as f:
    sample = list(csv.DictReader(f))

rows, stat = [], Counter()
for s in sample:
    c = coord.get(s["관리번호"], {})
    docs, how = [], ""
    if c.get("위도") and c.get("경도"):
        docs, how = search(query=s["상호"], x=c["경도"], y=c["위도"], radius=100, category_group_code="FD6", sort="distance", size=15), "좌표100m"
    if not docs:
        docs = [d for d in search(query=f"대구 중구 {s['상호']}", category_group_code="FD6", size=15) if "중구" in d["address_name"]]
        how = "상호검색"
    best = max(docs, key=lambda d: score(s["상호"], d["place_name"]), default=None)
    sim = score(s["상호"], best["place_name"]) if best else 0
    status = "없음" if sim < 0.5 else ("연결" if sim >= 0.8 else "확인 필요")
    stat[(s["집단"], status)] += 1
    ok = status != "없음"
    rows.append({"시험번호": s["시험번호"], "집단": s["집단"], "관리번호": s["관리번호"], "상호": s["상호"], "업태": s["업태"], "업력_년": s["업력_년"], "생존배수": s["생존배수"],
                 "상태": status, "방법": how if ok else "", "유사도": round(sim, 2), "카카오ID": best["id"] if ok else "", "카카오상호": best["place_name"] if ok else "", "카카오분류": best["category_name"] if ok else "", "거리_m": best.get("distance", "") if ok else ""})

with open("시험표본_카카오ID.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print("집단별 연결:", sorted(stat.items()))
print("저장 완료: 시험표본_카카오ID.csv")
