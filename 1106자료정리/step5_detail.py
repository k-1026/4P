"""
버틴집 가설 시험 3단계: 표본의 카카오맵 상세 수집 (비공식 경로)

계정 보호 원칙: 카카오 API 키·로그인 정보·쿠키를 넣지 않음. 요청 간격 1~2초, 오류 응답 시 즉시 중단
이미 kakao_raw에 있는 장소는 다시 요청하지 않음
필요한 파일: 시험표본_카카오ID.csv
결과: kakao_raw/{카카오ID}.json (점수는 출력하지 않음)
"""
import csv
import json
import os
import random
import sys
import time

import requests

RAW = "kakao_raw"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
os.makedirs(RAW, exist_ok=True)
with open("시험표본_카카오ID.csv", encoding="utf-8-sig") as f:
    ids = sorted({r["카카오ID"] for r in csv.DictReader(f) if r["카카오ID"]})

new = skip = 0
for pid in ids:
    path = os.path.join(RAW, f"{pid}.json")
    if os.path.exists(path):
        skip += 1
        continue
    if new:
        time.sleep(random.uniform(1, 2))
    try:
        r = requests.get(f"https://place.map.kakao.com/places/panel3/{pid}", timeout=20, headers={"User-Agent": UA, "Referer": f"https://place.map.kakao.com/{pid}", "Accept": "application/json", "pf": "PC"})
    except requests.RequestException as e:
        sys.exit(f"{pid} 요청 실패, 중단: {type(e).__name__}. 새로 받은 곳 {new}")
    if r.status_code != 200:
        sys.exit(f"{pid} 상태 {r.status_code}, 중단. 새로 받은 곳 {new}")
    try:
        data = r.json()
    except ValueError:
        sys.exit(f"{pid} JSON 아닌 응답, 중단. 새로 받은 곳 {new}")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    new += 1
print(f"대상 {len(ids)}곳 / 새로 수집 {new} / 이미 있음 {skip}")
