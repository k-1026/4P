"""
대구 맛집 API - 대구 전체 구·군을 한 번에 받아 CSV로 저장

사용법:
  명령 프롬프트에서:  python matjib_all_daegu.py

결과: 같은 폴더에 matjib_daegu_all.csv 생성
"""
import csv
import json
import sys
import time
from urllib.parse import quote

import requests

BASE = "https://www.daegufood.go.kr/kor/api/tasty.html?mode=json&addr="
GU_LIST = ["중구", "동구", "서구", "남구", "북구", "수성구", "달서구", "달성군", "군위군"]

# 브라우저에서 연 것처럼 보이게 하는 정보 (일부 사이트는 프로그램 요청을 막음)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.daegufood.go.kr/",
}

rows = []
for gu in GU_LIST:
    url = BASE + quote(gu)
    try:
        res = requests.get(url, headers=HEADERS, timeout=30)
    except Exception as e:
        print(f"{gu}: 접속 실패 ({e})")
        continue
    text = res.content.decode("utf-8-sig", errors="replace").strip()
    try:
        data = json.loads(text)
    except ValueError:
        print(f"{gu}: JSON 아님 (HTTP {res.status_code}) 응답 앞부분 -> {text[:200]!r}")
        continue
    items = data.get("data") or []
    print(f"{gu}: {len(items)}곳 (total {data.get('total')})")
    for it in items:
        it["구군"] = gu
        it["MNU"] = (it.get("MNU") or "").replace("<br />", " / ").replace("<br/>", " / ")
        rows.append(it)
    time.sleep(1)

if not rows:
    sys.exit("받은 데이터가 없습니다. 위 출력 내용을 Claude에게 보내 주세요.")

fields = ["구군"] + [k for k in rows[0].keys() if k != "구군"]
with open("matjib_daegu_all.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)

print(f"저장 완료: matjib_daegu_all.csv (총 {len(rows)}곳)")
