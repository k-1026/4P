"""대구 전역 2인분 후보 업종·비교 업종 목록을 상권정보에서 만든다 (달서구와 같은 기준, 2026-11-23).

후보 = 소분류 9개(돼지고기 구이/찜, 횟집, 해산물 구이/찜, 곱창 전골/구이, 닭/오리고기 구이/찜, 족발/보쌈, 소고기 구이/찜, 마라탕/훠궈, 복 요리 전문)
     + 상호에 2인분 메뉴 키워드(갈비·막창·족발·찜닭·삼겹·곱창·샤브·뭉티기·보쌈·아구·닭갈비·대창·찜갈비·전골)가 있는 가게
     단, 국/탕/찌개류는 '샤브'·'전골'만 후보로 남기고 나머지(갈비탕 등)는 비교 업종
비교 = 국/탕/찌개류 · 일식 면 요리 · 일식 카레/돈가스/덮밥 중 후보가 아닌 곳

python -I build_frame_daegu.py 상권정보.csv 후보출력.csv 비교출력.csv
"""
import csv, sys
from collections import Counter
sg_p, cand_out, cmp_out = sys.argv[1:4]
CAND_SUB = {"돼지고기 구이/찜", "횟집", "해산물 구이/찜", "곱창 전골/구이", "닭/오리고기 구이/찜", "족발/보쌈", "소고기 구이/찜", "마라탕/훠궈", "복 요리 전문"}
CMP = {"국/탕/찌개류": "국밥·탕·찌개", "일식 면 요리": "라멘·일식 면", "일식 카레/돈가스/덮밥": "돈가스·덮밥"}
KW = ["찜갈비", "닭갈비", "뭉티기", "갈비", "막창", "족발", "찜닭", "삼겹", "곱창", "샤브", "보쌈", "아구", "대창", "전골"]
COLS = ["상가업소번호", "상호명", "지점명", "상권업종중분류명", "상권업종소분류명", "표준산업분류명", "시군구명", "행정동명", "법정동명", "도로명주소", "층정보", "경도", "위도"]

R = [r for r in csv.DictReader(open(sg_p, encoding="utf-8-sig")) if r["상권업종대분류명"] == "음식"]
cand, cmp_ = [], []
for r in R:
    name = r["상호명"].replace(" ", "")
    found = []
    for k in KW:
        if k in name and not any(k in f for f in found):
            found.append(k)
    kws = "/".join(sorted(found, key=lambda k: name.find(k)))
    sub = r["상권업종소분류명"]
    o = {c: r[c] for c in COLS}
    o["상호_키워드"] = kws
    if sub == "국/탕/찌개류":
        if any(k in kws for k in ("샤브", "전골")):
            o["선정근거"] = "상호키워드"; cand.append(o)
        else:
            o["비교업종"] = CMP[sub]; cmp_.append(o)
    elif sub in CAND_SUB:
        o["선정근거"] = "소분류"; cand.append(o)
    elif kws:
        o["선정근거"] = "상호키워드"; cand.append(o)
    elif sub in CMP:
        o["비교업종"] = CMP[sub]; cmp_.append(o)
for path, rows in ((cand_out, cand), (cmp_out, cmp_)):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print("대구 음식", len(R), "후보", len(cand), "비교", len(cmp_))
for gu in sorted({r["시군구명"] for r in R}):
    n = sum(r["시군구명"] == gu for r in R)
    c = sum(o["시군구명"] == gu for o in cand); k = sum(o["시군구명"] == gu for o in cmp_)
    print(f"  {gu}: 음식 {n}, 후보 {c} ({c / n:.1%}), 비교 {k}")
print("후보 선정근거", Counter(o["선정근거"] for o in cand))
