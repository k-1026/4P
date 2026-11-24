"""인허가 표본(가게목록_표본.csv)을 상권정보(대구 202609)와 잇는다.

연결 단계 (먼저 맞는 것 하나만 씀):
  A_주소+상호      도로명주소(건물번호까지)가 같고 정규화한 상호가 같음
  B_주소+상호일부  주소가 같고 한 상호가 다른 상호를 포함 (2글자 이상)
  C_상호+도로명    상호가 같고 같은 구·군·같은 도로명인데 건물번호가 다름 (해당 1곳뿐일 때만)
  D_주소만         주소는 같은데 상호가 다름 → 참고용, 소분류를 쓰지 않음
  없음
"""
import csv, re, sys
from collections import Counter, defaultdict

sample_p, sg_p, cand_p, out_dir = sys.argv[1:5]
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig")))
S = rd(sample_p)
G = rd(sg_p)
cand = {r["상가업소번호"]: r["선정근거"] for r in rd(cand_p)}


def addr(a):
    a = a.split("(")[0].split(",")[0]
    a = re.sub(r"\s+", " ", a).strip()
    return a


def name(n):
    n = re.sub(r"\(.*?\)", "", n)
    n = re.sub(r"[^0-9A-Za-z가-힣]", "", n).lower()
    return n


def gname(g):
    return name(g["상호명"] + g["지점명"]), name(g["상호명"])


by_addr = defaultdict(list)
by_name_gu = defaultdict(list)
for g in G:
    by_addr[addr(g["도로명주소"])].append(g)
    for k in set(gname(g)):
        if k:
            by_name_gu[(k, g["시군구명"])].append(g)

rows = []
for s in S:
    sa, sn = addr(s["도로명주소"]), name(s["상호"])
    at = by_addr.get(sa, [])
    hit, level = None, "없음"
    for g in at:
        if sn and sn in gname(g):
            hit, level = g, "A_주소+상호"
            break
    if not hit:
        for g in at:
            if any(len(k) >= 2 and len(sn) >= 2 and (k in sn or sn in k) for k in gname(g)):
                hit, level = g, "B_주소+상호일부"
                break
    if not hit and sn:
        road = lambda a: re.sub(r"\s\d[\d-]*$", "", a)
        same = {g["상가업소번호"]: g for g in by_name_gu.get((sn, s["구군"]), [])
                if road(addr(g["도로명주소"])) == road(sa)}
        if len(same) == 1:
            hit, level = next(iter(same.values())), "C_상호+도로명"
    addr_only = ""
    if not hit and at:
        level = "D_주소만"
        addr_only = " / ".join(f'{g["상호명"]}({g["상권업종소분류명"]})' for g in at[:5])
    use = hit is not None
    rows.append({
        **s,
        "연결단계": level,
        "상가업소번호": hit["상가업소번호"] if use else "",
        "상권_상호명": (hit["상호명"] + (" " + hit["지점명"] if hit["지점명"] else "")) if use else "",
        "상권업종대분류명": hit["상권업종대분류명"] if use else "",
        "상권업종중분류명": hit["상권업종중분류명"] if use else "",
        "상권업종소분류명": hit["상권업종소분류명"] if use else "",
        "상권_행정동명": hit["행정동명"] if use else "",
        "상권_도로명주소": hit["도로명주소"] if use else "",
        "경도": hit["경도"] if use else "",
        "위도": hit["위도"] if use else "",
        "달서구_2인분후보": (cand.get(hit["상가업소번호"], "아님") if hit["시군구명"] == "달서구" else "") if use else "",
        "같은주소_다른상호": addr_only,
    })

fields = list(rows[0].keys())
with open(f"{out_dir}/가게목록_표본_상권정보연결_202609.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)

lv = Counter(r["연결단계"] for r in rows)
print("전체", len(rows), dict(sorted(lv.items())))
print("구분별")
for k in ("기본", "예비"):
    print(" ", k, dict(sorted(Counter(r["연결단계"] for r in rows if r["구분"] == k).items())))
print("구군별 연결률(A~C)")
for gu in sorted({r["구군"] for r in rows}):
    rr = [r for r in rows if r["구군"] == gu]
    ok = sum(r["상가업소번호"] != "" for r in rr)
    print(f"  {gu} {ok}/{len(rr)} = {ok/len(rr):.1%}")
print("서비스_표시별 연결률")
for k, n in Counter(r["서비스_표시"] for r in rows).most_common(6):
    ok = sum(r["상가업소번호"] != "" for r in rows if r["서비스_표시"] == k)
    print(f"  [{k}] {ok}/{n}")
print("업태별 연결률 상위")
for k, n in Counter(r["업태"] for r in rows).most_common(10):
    ok = sum(r["상가업소번호"] != "" for r in rows if r["업태"] == k)
    print(f"  {k} {ok}/{n}")
print("대분류", Counter(r["상권업종대분류명"] for r in rows if r["상가업소번호"]).most_common())
dal = [r for r in rows if r["구군"] == "달서구"]
print("달서구 표본", len(dal), Counter(r["달서구_2인분후보"] for r in dal))
dup = Counter(r["상가업소번호"] for r in rows if r["상가업소번호"])
print("상가업소번호 중복 연결", sum(1 for v in dup.values() if v > 1))
import random
random.seed(1)
for lvname in ("B_주소+상호일부", "C_상호+도로명", "D_주소만", "없음"):
    ex = [r for r in rows if r["연결단계"] == lvname]
    print(lvname, "예시")
    for r in random.sample(ex, min(8, len(ex))):
        print("   ", r["상호"], "|", r["상권_상호명"] or r["같은주소_다른상호"][:40], "|", r["도로명주소"][:30], "|", r["상권_도로명주소"])
