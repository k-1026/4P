"""
가맹점 주소 대조 시험 (대구 밖 본부 브랜드 표본)

이름이 걸린 대구 가게의 주소가 공정위 가맹점 목록의 주소와 맞는지 확인
많이 걸린 브랜드 8개와 한 곳만 걸린 브랜드 12개를 고정 난수로 시험
개인정보 보호: 가맹점 대표자명은 저장하지 않음
필요한 것: 환경변수 DATA_GO_KR_KEY, ftc_외식브랜드_2025.csv, 프랜차이즈_대조후보_대구_지역.csv
결과: 시험_가맹점주소대조.csv
"""
import csv
import os
import random
import re
import sys
import time
from collections import Counter

import requests

KEY = os.environ.get("DATA_GO_KR_KEY")
if not KEY:
    sys.exit("DATA_GO_KR_KEY 환경변수가 없습니다.")
URL = "https://apis.data.go.kr/1130000/FftcbrandfrcslistinfoService/getbrandFrcsListinfo"
SRC = r"..\과제\docs\daegu_pay\6_대구전체_음식점_영업기간\대구전체_일반음식점_WGS84.csv"
YEAR = 2025


def fetch(mnno):
    out, page, total = [], 1, None
    while total is None or (page - 1) * 100 < total:
        for attempt in range(3):
            try:
                r = requests.get(URL, timeout=(15, 60), params={"serviceKey": KEY, "pageNo": page, "numOfRows": 100, "resultType": "json", "jngBizCrtraYr": YEAR, "brandMnno": mnno})
                d = r.json()
                total = int(d.get("totalCount") or 0)
                break
            except (requests.RequestException, ValueError) as e:
                if attempt == 2:
                    print("실패", mnno, type(e).__name__, flush=True)
                    return out, None
                time.sleep(10)
        out += d.get("items") or []
        page += 1
        time.sleep(0.2)
        if not total:
            break
    return out, total


def road_key(a):
    m = re.search(r"([가-힣0-9]+(?:로|길))\s*(\d+(?:-\d+)?)", a or "")
    return (m.group(1), m.group(2)) if m else None


def lot_key(a):
    m = re.search(r"([가-힣0-9]+(?:동|가|읍|면|리))\s+(?:산\s*)?0*(\d+)(?:-0*(\d+))?", a or "")
    return (m.group(1), m.group(2), m.group(3) or "") if m else None


with open("ftc_외식브랜드_2025.csv", encoding="utf-8-sig") as f:
    brand_id = {}
    for b in csv.DictReader(f):
        brand_id.setdefault(b["brandNm"], b["brandMnno"])
with open("프랜차이즈_대조후보_대구_지역.csv", encoding="utf-8-sig") as f:
    cands = [c for c in csv.DictReader(f) if c["본부지역"] == "대구 밖"]
with open(SRC, encoding="utf-8-sig") as f:
    addr = {r["관리번호"]: r for r in csv.DictReader(f)}

count = Counter(c["브랜드"] for c in cands)
top = [b for b, _ in count.most_common(8)]
ones = sorted(b for b, n in count.items() if n == 1)
rng = random.Random(20261106)
sample = top + rng.sample(ones, 12)

rows = []
for b in sample:
    mid = brand_id.get(b)
    stores, total = fetch(mid)
    daegu = [s for s in stores if "대구" in str(s.get("frcsAddr")) or str(s.get("areaNm", "")).startswith("대구")]
    keys = {road_key(s.get("frcsAddr")) for s in daegu} | {lot_key(s.get("frcsAddr")) for s in daegu}
    keys.discard(None)
    mine = [c for c in cands if c["브랜드"] == b]
    hit = 0
    for c in mine:
        s = addr[c["관리번호"]]
        if road_key(s["도로명주소"]) in keys or lot_key(s["지번주소"]) in keys:
            hit += 1
    rows.append({"브랜드": b, "구분": "상위" if b in top else "1곳", "후보": len(mine), "공정위_전체가맹점": total, "공정위_대구가맹점": len(daegu), "주소일치": hit, "상호예": mine[0]["상호"]})
    print(rows[-1], flush=True)

with open("시험_가맹점주소대조.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
for g in ("상위", "1곳"):
    x = [r for r in rows if r["구분"] == g]
    print(g, "후보", sum(r["후보"] for r in x), "주소일치", sum(r["주소일치"] for r in x), "공정위 대구 가맹점", sum(r["공정위_대구가맹점"] for r in x), "목록 없음", sum(1 for r in x if not r["공정위_전체가맹점"]))
print("저장 완료")
