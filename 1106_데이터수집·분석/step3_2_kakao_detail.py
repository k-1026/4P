"""
3-2단계: 카카오맵 장소 상세 수집 (비공식 경로, 크롤링)

계정 보호 원칙: 이 스크립트에는 카카오 API 키·로그인 정보·쿠키를 넣지 않음
요청 간격 1~2초, 한 번에 한 구역만, 오류 응답이 오면 즉시 중단

필요한 파일: kakao_수집대상_중구_대봉1동.csv

실행
  python step3_2_kakao_detail.py 5   ← 목록에서 고르게 5곳만 시험
결과
  kakao_raw/{카카오ID}.json          원본 응답 전체
  kakao_상세_시험.csv                주요 항목 요약 (원본 형식 확인 전까지는 시험용)

이미 받은 장소는 kakao_raw에 파일이 있으면 다시 요청하지 않음
"""
import csv
import json
import os
import random
import sys
import time

import requests

AREA = "중구_대봉1동"
TARGET_FILE = f"kakao_수집대상_{AREA}.csv"
RAW_DIR = "kakao_raw"
URL = "https://place.map.kakao.com/places/panel3/{id}"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

if len(sys.argv) != 2:
    sys.exit("시험할 곳 수를 적어 주세요. 예: python step3_2_kakao_detail.py 5")
n = int(sys.argv[1])

with open(TARGET_FILE, encoding="utf-8-sig") as f:
    targets = list(csv.DictReader(f))
step = max(1, len(targets) // n)
sample = targets[::step][:n]     # 목록에서 고르게 선택

os.makedirs(RAW_DIR, exist_ok=True)

rows = []
for i, t in enumerate(sample):
    pid = t["카카오ID"]
    path = os.path.join(RAW_DIR, f"{pid}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    else:
        if i:
            time.sleep(random.uniform(1, 2))
        try:
            r = requests.get(URL.format(id=pid), timeout=20, headers={
                "User-Agent": USER_AGENT,
                "Referer": f"https://place.map.kakao.com/{pid}",
                "Accept": "application/json",
                "pf": "PC",
            })
        except requests.RequestException as e:
            sys.exit(f"요청 실패, 중단: {type(e).__name__}")
        if r.status_code != 200:
            sys.exit(f"{t['카카오상호']}({pid}) 상태 {r.status_code}, 중단. 응답 앞부분: {r.text[:200]}")
        try:
            data = r.json()
        except ValueError:
            sys.exit(f"{t['카카오상호']}({pid}) JSON이 아닌 응답, 중단. 응답 앞부분: {r.text[:200]}")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)

    hours = data.get("open_hours") or {}
    menus = ((data.get("menu") or {}).get("menus") or {}).get("items") or []
    score = (data.get("kakaomap_review") or {}).get("score_set") or {}
    rows.append({
        "카카오ID": pid,
        "상호": (data.get("summary") or {}).get("name", ""),
        "목록상태": t["상태"],
        "술집표시": t["술집표시"],
        "최상위키": ",".join(data.keys()),
        "영업정보있음": "O" if hours else "",
        "open_hours원본": json.dumps(hours, ensure_ascii=False),
        "메뉴수": len(menus),
        "메뉴예시": " / ".join(f"{m.get('name')} {m.get('price', '')}" for m in menus[:3]),
        "리뷰수": score.get("review_count", ""),
    })

with open("kakao_상세_시험.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print(f"수집: {len(rows)}곳")
for r in rows:
    print(f"- {r['상호']} ({r['카카오ID']}) 영업정보 {r['영업정보있음'] or 'X'}, 메뉴 {r['메뉴수']}개, 리뷰 {r['리뷰수']}개, 술집표시 {r['술집표시'] or '-'}")
print("저장 완료: kakao_상세_시험.csv, kakao_raw 폴더")
