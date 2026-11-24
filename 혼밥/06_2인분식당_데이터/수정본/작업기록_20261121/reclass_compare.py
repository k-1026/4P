"""국/탕/찌개류를 2인분 후보에서 비교 업종으로 옮기고, 비교 업종 파일을 만든다 (2026-11-21 결정).
비교 업종 = 국/탕/찌개류(국밥) · 일식 면 요리(라멘) · 일식 카레/돈가스/덮밥(돈가스)
예외: 국/탕/찌개류 중 상호에 '샤브'·'전골'이 있는 곳은 2인분 후보(상호키워드)로 남긴다.
"""
import csv, sys
from collections import Counter
B = sys.argv[1]
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig")))
def wr(p, rows):
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

CMP = {"국/탕/찌개류": "국밥·탕·찌개", "일식 면 요리": "라멘·일식 면", "일식 카레/돈가스/덮밥": "돈가스·덮밥"}
KEEP_KW = ("샤브", "전골")
cand_p = f"{B}/달서구_2인분후보업종_보완_202609.csv"
CAND = rd(cand_p)
ALL = rd(f"{B}/달서구_음식점_전체_202609.csv")

new_cand, moved = [], []
for r in CAND:
    if r["상권업종소분류명"] == "국/탕/찌개류":
        if any(k in (r["상호_키워드"] or "") for k in KEEP_KW):
            r["선정근거"] = "상호키워드"
            new_cand.append(r)
        else:
            moved.append(r)
    else:
        new_cand.append(r)
cand_ids = {r["상가업소번호"]: r["선정근거"] for r in new_cand}
extra_cols = [c for c in CAND[0].keys() if c not in ALL[0].keys() and c != "선정근거"]
by_cand = {r["상가업소번호"]: r for r in CAND}
cmp_rows = []
for r in ALL:
    s = r["상권업종소분류명"]
    if s in CMP and r["상가업소번호"] not in cand_ids:
        o = dict(r)
        o["비교업종"] = CMP[s]
        old = by_cand.get(r["상가업소번호"], {})
        for c in extra_cols:
            o[c] = old.get(c, "")
        cmp_rows.append(o)
cmp_ids = {r["상가업소번호"] for r in cmp_rows}
wr(cand_p, new_cand)
wr(f"{B}/달서구_비교업종_202609.csv", cmp_rows)

def label(gid, gu="달서구"):
    if not gid or gu != "달서구":
        return ""
    if gid in cand_ids:
        return cand_ids[gid]
    return "비교" if gid in cmp_ids else "아님"

# 인허가 표본 연결 파일
lp = f"{B}/가게목록_표본_상권정보연결_202609.csv"
L = rd(lp)
for r in L:
    if r["구군"] == "달서구" and r["상가업소번호"]:
        r["달서구_2인분후보"] = label(r["상가업소번호"])
    if r.get("지도업종_대응소분류") == "국/탕/찌개류":
        r["지도기반_2인분후보"] = "비교(지도업종)"
wr(lp, L)
# 착한가격업소 연결 파일
gp = f"{B}/착한가격업소_대구외식업_상권정보연결_202609.csv"
O = rd(gp)
for o in O:
    if o["기초"] == "달서구" and o["상가업소번호"]:
        o["달서구_2인분후보"] = label(o["상가업소번호"])
wr(gp, O)

print("후보", len(CAND), "→", len(new_cand), Counter(r["선정근거"] for r in new_cand))
print("국/탕에서 옮김", len(moved), "비교 파일", len(cmp_rows), Counter(r["비교업종"] for r in cmp_rows))
d = [r for r in L if r["구군"] == "달서구"]
print("달서구 표본", Counter(r["달서구_2인분후보"] for r in d), "지도기반", Counter(r.get("지도기반_2인분후보", "") for r in d if r.get("지도기반_2인분후보")))
print("착한 달서", Counter(o["달서구_2인분후보"] for o in O if o["기초"] == "달서구" and o["상가업소번호"]))
print("후보 중 착한", sum(r.get("착한가격업소") == "예" for r in new_cand), "대구푸드", sum(r.get("대구푸드") == "예" for r in new_cand),
      "2인표기(대구푸드)", [r["상호명"] for r in new_cand if r.get("대구푸드_2인이상표기") == "O"], "1인표기", [r["상호명"] for r in new_cand if r.get("대구푸드_1인분표기") == "O"])
print("비교 중 착한", sum(r.get("착한가격업소") == "예" for r in cmp_rows), "대구푸드", sum(r.get("대구푸드") == "예" for r in cmp_rows))
