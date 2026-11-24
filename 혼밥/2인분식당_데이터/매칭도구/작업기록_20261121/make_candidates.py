import csv, sys
from collections import Counter

base = sys.argv[1]
rd = lambda p: list(csv.DictReader(open(f"{base}/{p}", encoding="utf-8-sig")))
allr = rd("달서구_음식점_전체_202609.csv")
cand = rd("달서구_2인분후보업종_202609.csv")
cid = {r["상가업소번호"] for r in cand}
cats = {r["상권업종소분류명"] for r in cand}

out = []
for r in allr:
    if r["상가업소번호"] in cid:
        r["선정근거"] = "소분류"
    elif r["상호_키워드"]:
        r["선정근거"] = "상호키워드"
    else:
        continue
    out.append(r)

fields = list(allr[0].keys()) + ["선정근거"]
fields = list(dict.fromkeys(fields))
with open(f"{base}/달서구_2인분후보업종_보완_202609.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(out)

print("후보 보완", len(out), Counter(r["선정근거"] for r in out))
kw = Counter(r["상호_키워드"] for r in out if r["선정근거"] == "상호키워드")
print(kw.most_common())

# 행정동별 집계
dongs = sorted({r["행정동명"] for r in allr})
tot = Counter(r["행정동명"] for r in allr)
a = Counter(r["행정동명"] for r in out if r["선정근거"] == "소분류")
b = Counter(r["행정동명"] for r in out if r["선정근거"] == "상호키워드")
with open(f"{base}/달서구_행정동별_2인분후보_보완_202609.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["행정동", "소분류_후보", "상호키워드_추가", "후보_합계", "음식점 전체"])
    for d in dongs:
        w.writerow([d, a[d], b[d], a[d] + b[d], tot[d]])
    w.writerow(["합계", sum(a.values()), sum(b.values()), len(out), len(allr)])
print("동 합계", sum(a.values()), sum(b.values()), len(allr))
