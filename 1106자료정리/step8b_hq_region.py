"""
가맹본부 소재지를 받아 프랜차이즈 후보를 대구 본부와 대구 밖 본부로 나눔

개인정보 보호: 대표자명, 전화·팩스, 사업자·법인등록번호, 상세 주소는 저장하지 않음. 시·도와 시·군·구만 저장
필요한 것: 환경변수 DATA_GO_KR_KEY, ftc_외식브랜드_2025.csv, 프랜차이즈_대조후보_대구.csv
결과: ftc_본부지역_2025.csv, 프랜차이즈_대조후보_대구_지역.csv
"""
import csv
import os
import re
import sys
import time
from collections import Counter

import requests

YEAR = 2025
HQ_FILE = f"ftc_본부지역_{YEAR}.csv"
URL = "https://apis.data.go.kr/1130000/FftcJnghdqrtrsGnrlDtl3_Service/getjnghdqrtrsGnlinfo2"


def region(addr):
    p = re.sub(r"\s+", " ", addr or "").strip().split(" ")
    return (p[0] if p else "", p[1] if len(p) > 1 else "")


def fetch():
    key = os.environ.get("DATA_GO_KR_KEY")
    if not key:
        sys.exit("DATA_GO_KR_KEY 환경변수가 없습니다.")
    rows, page, total = [], 1, None
    while total is None or (page - 1) * 100 < total:
        for attempt in range(4):
            try:
                r = requests.get(URL, timeout=(15, 90), params={"serviceKey": key, "pageNo": page, "numOfRows": 100, "resultType": "json", "jngBizCrtraYr": YEAR})
                d = r.json()
                total = int(d["totalCount"])
                break
            except (requests.RequestException, ValueError, KeyError) as e:
                if attempt == 3:
                    sys.exit(f"{page}쪽 실패: {type(e).__name__}")
                time.sleep(15 * (attempt + 1))
        for i in d.get("items") or []:
            sido, sgg = region(i.get("lctnAddr"))
            rows.append({"jnghdqrtrsMnno": i.get("jnghdqrtrsMnno", ""), "본부상호": i.get("jnghdqrtrsConmNm", ""), "지역명": i.get("areaNm", ""), "시도": sido, "시군구": sgg, "브랜드수": i.get("brandCnt", "")})
        if page % 20 == 0:
            print("쪽", page, len(rows), flush=True)
        page += 1
        time.sleep(0.2)
    with open(HQ_FILE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("본부", total, "저장", len(rows), flush=True)
    return rows


if os.path.exists(HQ_FILE):
    with open(HQ_FILE, encoding="utf-8-sig") as f:
        hq_rows = list(csv.DictReader(f))
else:
    hq_rows = fetch()
hq = {h["jnghdqrtrsMnno"]: h for h in hq_rows}

with open("ftc_외식브랜드_2025.csv", encoding="utf-8-sig") as f:
    brand_list = list(csv.DictReader(f))
by_name = {}
for b in brand_list:
    by_name.setdefault(b["brandNm"], b)


def is_daegu(h):
    return bool(h) and ((h["시도"] or "").startswith("대구") or (h["지역명"] or "").startswith("대구"))


print("본부 시도 상위:", Counter(h["시도"] for h in hq_rows).most_common(10))
print("지역명 상위:", Counter(h["지역명"] for h in hq_rows).most_common(8))
print("대구 본부:", sum(is_daegu(h) for h in hq_rows))

with open("프랜차이즈_대조후보_대구.csv", encoding="utf-8-sig") as f:
    cands = list(csv.DictReader(f))
out = []
for c in cands:
    b = by_name.get(c["브랜드"])
    h = hq.get(b["jnghdqrtrsMnno"]) if b else None
    c["본부지역"] = "확인 불가" if not h or not (h["시도"] or h["지역명"]) else ("대구" if is_daegu(h) else "대구 밖")
    c["본부시도"] = (h["시도"] or h["지역명"]) if h else ""
    out.append(c)
with open("프랜차이즈_대조후보_대구_지역.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(out)

print("후보", len(out), dict(Counter(c["본부지역"] for c in out)))
print("대조방법×지역", dict(Counter((c["대조방법"], c["본부지역"]) for c in out)))
for g in ("대구", "대구 밖"):
    cnt = Counter(c["브랜드"] for c in out if c["본부지역"] == g)
    print(f"{g} 브랜드 {len(cnt)}개, 한 곳만 걸림 {sum(1 for n in cnt.values() if n == 1)}개, 상위 25:", cnt.most_common(25))
print("저장 완료")
