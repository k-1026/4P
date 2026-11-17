"""
공정위 외식 브랜드 목록 받기와 대구 영업 중 가게 시험 대조

개인정보 보호: 대표자명, 사업자·법인등록번호는 저장하지 않음
대조: 상호에서 괄호·공백·'○○점'을 정리한 뒤
      '정확히 일치' 또는 '브랜드명(4자 이상)으로 시작'만 후보로 표시 (확정 아님)
필요한 것: 환경변수 DATA_GO_KR_KEY
결과: ftc_외식브랜드_2025.csv, 프랜차이즈_대조후보_대구.csv
"""
import csv
import os
import re
import sys
import time
from collections import Counter

import requests

YEAR = 2025
BRAND_FILE = f"ftc_외식브랜드_{YEAR}.csv"
URL = "https://apis.data.go.kr/1130000/FftcBrandRlsInfo2_Service/getBrandinfo"
SRC = r"..\과제\docs\daegu_pay\6_대구전체_음식점_영업기간\대구전체_일반음식점_WGS84.csv"
COLS = ["brandMnno", "jnghdqrtrsMnno", "brandNm", "corpNm", "indutyLclasNm", "indutyMlsfcNm", "majrGdsNm", "jngBizStrtDate"]


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
                    sys.exit(f"{page}쪽 실패: {type(e).__name__}. 받은 {len(rows)}건은 저장하지 않음")
                time.sleep(15 * (attempt + 1))
        rows += [{c: i.get(c, "") for c in COLS} for i in d.get("items") or [] if i.get("indutyLclasNm") == "외식"]
        if page % 20 == 0:
            print("쪽", page, "외식 누적", len(rows), flush=True)
        page += 1
        time.sleep(0.2)
    with open(BRAND_FILE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"전체 {total}건 중 외식 {len(rows)}건 저장", flush=True)
    return rows


def clean(name):
    s = re.sub(r"\(.*?\)|\[.*?\]", "", name or "")
    s = re.sub(r"[\s·\-_.,&]", "", s).lower()
    return s


def strip_branch(s):
    return re.sub(r"(본점|직영점|[가-힣a-z0-9]{1,12}점)$", "", s)


if os.path.exists(BRAND_FILE):
    with open(BRAND_FILE, encoding="utf-8-sig") as f:
        brands = list(csv.DictReader(f))
else:
    brands = fetch()

name_map = {}
for b in brands:
    k = clean(b["brandNm"])
    if k:
        name_map.setdefault(k, b)
long_names = sorted((k for k in name_map if len(k) >= 4), key=len, reverse=True)
by_first = {}
for k in long_names:
    by_first.setdefault(k[:2], []).append(k)

with open(SRC, encoding="utf-8-sig") as f:
    shops = [r for r in csv.DictReader(f) if r["상태"] == "영업/정상"]

out, stat = [], Counter()
for r in shops:
    full = clean(r["사업장명"])
    short = strip_branch(full)
    hit, how = None, ""
    if full in name_map:
        hit, how = full, "정확"
    elif short in name_map:
        hit, how = short, "지점명 제거 후 정확"
    else:
        for k in by_first.get(full[:2], []):
            if full.startswith(k):
                hit, how = k, "브랜드명으로 시작"
                break
    if hit:
        b = name_map[hit]
        stat[how] += 1
        out.append({"관리번호": r["관리번호"], "상호": r["사업장명"], "구군": r["구군"], "업태": r["업태"], "브랜드": b["brandNm"], "본부": b["corpNm"], "브랜드업종": b["indutyMlsfcNm"], "대조방법": how})

with open("프랜차이즈_대조후보_대구.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(out)

print("외식 브랜드", len(brands), "/ 업종", Counter(b["indutyMlsfcNm"] for b in brands).most_common(8))
print("대구 영업 중", len(shops), "/ 후보", len(out), f"({len(out) / len(shops):.1%})", dict(stat))
c = Counter(x["브랜드"] for x in out)
print("상위 브랜드 40:", c.most_common(40))
short2 = [k for k, n in c.items() if len(clean(k)) <= 3]
print("3자 이하 브랜드 후보 수", len(short2), "/ 가게", sum(c[k] for k in short2), short2[:25])
print("한 곳만 걸린 브랜드", sum(1 for n in c.values() if n == 1), "/ 전체 브랜드", len(c))
print("저장 완료")
