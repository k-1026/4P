import csv, json, sys
link_p, sg_p, items_p, cand_p, review_p = sys.argv[1:6]
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig")))
L = rd(link_p)
G = {g["상가업소번호"]: g for g in rd(sg_p)}
cand = {r["상가업소번호"]: r["선정근거"] for r in rd(cand_p)}
items = json.load(open(items_p, encoding="utf-8"))

SURE = {8:0, 14:1, 32:9, 54:4, 65:0, 70:0, 73:3, 109:1, 110:0, 131:0, 137:29, 138:1, 147:0, 148:0,
        149:48, 161:0, 164:0, 170:1, 179:55, 181:0, 195:0, 203:3, 206:2, 212:23, 214:0, 223:0, 234:20,
        239:0, 252:1, 266:0, 271:0, 279:0, 284:0, 286:1, 292:22, 293:0, 298:3, 300:2, 302:0, 303:0,
        308:1, 310:1, 313:0, 317:4, 318:2, 321:0, 322:5, 330:0, 336:0, 337:0, 339:0, 340:0, 344:0,
        350:0, 356:0, 363:0, 364:1, 373:161, 377:0, 5:0}
LIKELY = {6:0, 11:38, 43:0, 53:2, 55:132, 71:0, 91:0, 108:0, 115:0, 124:0, 136:3, 157:1, 166:1,
          172:4, 175:0, 176:0, 185:0, 197:32, 202:0, 213:0, 227:1, 255:20, 261:0, 272:1, 316:0,
          335:0, 341:0, 361:2, 381:0}
assert not set(SURE) & set(LIKELY)

review = []
for n, it in enumerate(items):
    r = L[it["row"]]
    assert r["연결단계"] == "D_주소만" and r["상호"] == it["상호"]
    if n in SURE or n in LIKELY:
        k = SURE.get(n, LIKELY.get(n))
        g = G[it["c"][k][0]]
        lvl = "E_손확인_같은가게" if n in SURE else "F_손확인_유력"
        r.update({
            "연결단계": lvl, "상가업소번호": g["상가업소번호"],
            "상권_상호명": (g["상호명"] + (" " + g["지점명"] if g["지점명"] else "")),
            "상권업종대분류명": g["상권업종대분류명"], "상권업종중분류명": g["상권업종중분류명"],
            "상권업종소분류명": g["상권업종소분류명"], "상권_행정동명": g["행정동명"],
            "상권_도로명주소": g["도로명주소"], "경도": g["경도"], "위도": g["위도"],
            "달서구_2인분후보": cand.get(g["상가업소번호"], "아님") if g["시군구명"] == "달서구" else "",
        })
        review.append([it["row"] + 2, r["구군"], r["상호"], lvl, r["상권_상호명"], g["상권업종소분류명"]])
    else:
        r["연결단계"] = "D_손확인_다른가게"
        review.append([it["row"] + 2, r["구군"], r["상호"], "D_손확인_다른가게", r["같은주소_다른상호"], ""])

with open(link_p, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(L[0].keys()))
    w.writeheader(); w.writerows(L)
with open(review_p, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["표본파일_줄번호", "구군", "표본_상호", "손확인_판정", "상권_상호명(다른가게면 같은주소 가게들)", "상권업종소분류명"])
    w.writerows(review)

from collections import Counter
print(Counter(r["연결단계"] for r in L))
ok = [r for r in L if r["상가업소번호"]]
print("연결 A~F", len(ok), f"{len(ok)/len(L):.1%}", "A~E", sum(not r["연결단계"].startswith("F") for r in ok))
for k in ("기본", "예비"):
    print(k, sum(1 for r in ok if r["구분"] == k), "/", sum(1 for r in L if r["구분"] == k))
dal = [r for r in L if r["구군"] == "달서구"]
print("달서구", Counter(r["달서구_2인분후보"] for r in dal))
print("새로 이은 달서구", [(r["상호"], r["연결단계"], r["상권업종소분류명"], r["달서구_2인분후보"]) for r in dal if r["연결단계"][0] in "EF"])
d = Counter(r["상가업소번호"] for r in ok); print("중복 연결 가게", sum(v > 1 for v in d.values()))
