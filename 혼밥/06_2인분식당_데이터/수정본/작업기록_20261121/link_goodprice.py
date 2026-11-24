"""착한가격업소 대구 외식업(506곳)을 상권정보·2인분 후보·인허가 표본과 잇는다.
연결 단계는 인허가 표본과 같은 규칙: A 주소+상호 / B 주소+상호일부 / C 상호+도로명 / D 주소만 / 없음
"""
import csv, re, sys, html
from collections import defaultdict, Counter
import openpyxl

xlsx, sg_p, cand_p, sample_p, out_p, cand_out = sys.argv[1:7]
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig")))
ws = openpyxl.load_workbook(xlsx, read_only=True)["대구_외식업"]
rows = list(ws.iter_rows(values_only=True))
hdr = [str(h) for h in rows[0]]
GP = [dict(zip(hdr, ["" if v is None else str(v) for v in r])) for r in rows[1:] if any(r)]
G = rd(sg_p)
CAND = rd(cand_p)
cand = {r["상가업소번호"]: r["선정근거"] for r in CAND}
S = rd(sample_p)


ROAD_SP = re.compile(r"^(대구광역시\s\S+\s(?:\S+[읍면]\s)?\S+(?:로|길))\s(\d+(?:-\d+)?)")
ROADNO = re.compile(r"^(대구광역시\s\S+\s(?:\S+[읍면]\s)?[^\s\d]+(?:로|길)(?:\d+[번안가]?길)?)\s?(\d+(?:-\d+)?)")


def addr(a):
    a = re.sub(r"^대구\s", "대구광역시 ", a.strip()).replace(" 지하 ", " ")
    a = re.sub(r"\s+", " ", a.split("(")[0].split(",")[0]).strip()
    a = re.sub(r"(로|길) (\d+[번안가]?길)", r"\1\2", a)
    m = ROAD_SP.match(a) or ROADNO.match(a)
    return f"{m.group(1)} {m.group(2)}" if m else a


def name(n):
    n = html.unescape(n)
    n = re.sub(r"\(.*?\)", "", n)
    return re.sub(r"[^0-9A-Za-z가-힣]", "", n).lower()


road = lambda a: re.sub(r"\s\d[\d-]*$", "", a)
by_addr = defaultdict(list); by_name_gu = defaultdict(list)
for g in G:
    by_addr[addr(g["도로명주소"])].append(g)
    for k in {name(g["상호명"] + g["지점명"]), name(g["상호명"])}:
        if k:
            by_name_gu[(k, g["시군구명"])].append(g)
s_by_addr = defaultdict(list)
for i, s in enumerate(S):
    s_by_addr[addr(s["도로명주소"])].append((i + 2, s))

out = []
for p in GP:
    sa, sn, gu = addr(p["주소"]), name(p["업소명"]), p["기초"]
    at = by_addr.get(sa, [])
    hit, lvl = None, "없음"
    for g in at:
        if sn and sn in {name(g["상호명"] + g["지점명"]), name(g["상호명"])}:
            hit, lvl = g, "A_주소+상호"; break
    if not hit:
        for g in at:
            ks = {name(g["상호명"] + g["지점명"]), name(g["상호명"])}
            if any(len(k) >= 2 and len(sn) >= 2 and (k in sn or sn in k) for k in ks):
                hit, lvl = g, "B_주소+상호일부"; break
    if not hit and sn:
        same = {g["상가업소번호"]: g for g in by_name_gu.get((sn, gu), []) if road(addr(g["도로명주소"])) == road(sa)}
        if len(same) == 1:
            hit, lvl = next(iter(same.values())), "C_상호+도로명"
    other = ""
    if not hit and at:
        lvl = "D_주소만"
        other = " / ".join(f'{g["상호명"]}({g["상권업종소분류명"]})' for g in at[:6])
    # 인허가 표본과 겹치는지
    srow = ""
    for n, s in s_by_addr.get(sa, []):
        k = name(s["상호"])
        if k and (k == sn or (len(k) >= 2 and len(sn) >= 2 and (k in sn or sn in k))):
            srow = str(n); break
    u = hit is not None
    out.append({**p, "연결단계": lvl,
                "상가업소번호": hit["상가업소번호"] if u else "",
                "상권_상호명": (hit["상호명"] + (" " + hit["지점명"] if hit["지점명"] else "")) if u else "",
                "상권업종소분류명": hit["상권업종소분류명"] if u else "",
                "상권_행정동명": hit["행정동명"] if u else "",
                "달서구_2인분후보": (cand.get(hit["상가업소번호"], "아님") if hit["시군구명"] == "달서구" else "") if u else "",
                "같은주소_다른상호": other,
                "인허가표본_줄번호": srow})

with open(out_p, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)

# 2인분 후보 파일에 착한가격업소 칸 붙이기
gp_by_id = {}
for o in out:
    if o["상가업소번호"]:
        gp_by_id[o["상가업소번호"]] = o
for r in CAND:
    o = gp_by_id.get(r["상가업소번호"])
    r["착한가격업소"] = "예" if o else ""
    menus = [o.get(f"착한가격메뉴 품목{k}", "") + (f'({o.get(f"착한가격메뉴 가격{k}", "")}원)' if o.get(f"착한가격메뉴 가격{k}") else "") for k in range(1, 5)] if o else []
    r["착한가격메뉴"] = " / ".join(m for m in menus if m and not m.startswith("("))
    r["착한_2인표기"] = o.get("메뉴명에 2인·다인분 표기", "") if o else ""
    r["착한_1인표기"] = o.get("메뉴명에 1인·1인분 표기", "") if o else ""
with open(cand_out, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(CAND[0].keys())); w.writeheader(); w.writerows(CAND)

c = Counter(o["연결단계"] for o in out)
print("착한 외식업", len(out), dict(sorted(c.items())))
ok = [o for o in out if o["상가업소번호"]]
print("연결 A~C", len(ok), f"{len(ok)/len(out):.1%}")
print("구군별", [(g, sum(o["기초"] == g for o in ok), sum(o["기초"] == g for o in out)) for g in sorted({o["기초"] for o in out})])
dal = [o for o in out if o["기초"] == "달서구"]
print("달서구", len(dal), "연결", sum(bool(o["상가업소번호"]) for o in dal), Counter(o["달서구_2인분후보"] for o in dal if o["상가업소번호"]))
print("달서 후보 중 착한", [(o["업소명"], o["상권업종소분류명"], o["달서구_2인분후보"], o["착한가격메뉴 품목1"]) for o in dal if o["달서구_2인분후보"] in ("소분류", "상호키워드")])
print("소분류 분포(연결된 곳)", Counter(o["상권업종소분류명"] for o in ok).most_common(12))
print("인허가 표본과 겹침", sum(bool(o["인허가표본_줄번호"]) for o in out))
for col in ("메뉴명에 2인·다인분 표기", "메뉴명에 1인·1인분 표기"):
    print(col, [(o["기초"], o["업소명"], o[col], o["연결단계"], o["상권업종소분류명"], o["인허가표본_줄번호"]) for o in out if o.get(col)])
print("D 예시", [(o["업소명"], o["같은주소_다른상호"][:40]) for o in out if o["연결단계"] == "D_주소만"][:15])
print("없음 예시", [(o["업소명"], o["주소"][:35]) for o in out if o["연결단계"] == "없음"][:15])
