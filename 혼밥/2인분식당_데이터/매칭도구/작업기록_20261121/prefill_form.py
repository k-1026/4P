"""달서구 인허가 표본의 2인분 후보로 수집양식을 미리 채운다.
- 대구푸드 맛집DB(905곳, 지번주소)를 상권정보 지번주소+상호로 잇고
- 착한가격업소 연결 결과와 함께 근거 칸(공공DB)에 메뉴 원문을 넣는다.
- 최소주문_판정 등 판정 칸은 비워 둔다(수집 단계에서 채움).
"""
import csv, json, re, sys
from collections import Counter, defaultdict

link_p, sg_p, food_p, food2_p, gp_p, cand_p, form_p, out_p, food_out = sys.argv[1:10]
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig")))
L = rd(link_p); G = rd(sg_p); GP = rd(gp_p); CAND = rd(cand_p)
F = json.load(open(food_p, encoding="utf-8"))
F2 = {(r["구군"], r["업소명"]): r for r in rd(food2_p)}
form_hdr = next(csv.reader(open(form_p, encoding="utf-8-sig")))

nm = lambda s: re.sub(r"[^0-9A-Za-z가-힣]", "", re.sub(r"\(.*?\)", "", s or "")).lower()


def jibun(a):
    a = re.sub(r"\s+", " ", (a or "").strip())
    m = re.search(r"(\S+[동가리])\s(?:산\s?)?(\d+)(?:-(\d+))?", a)
    if not m:
        return None
    return (m.group(1), m.group(2), m.group(3) or "0")


by_j = defaultdict(list)
for g in G:
    if g["상권업종대분류명"] != "음식":
        continue
    j = (g["법정동명"], str(g["지번본번지"]), str(g["지번부번지"] or "0"))
    by_j[(g["시군구명"],) + j].append(g)

food_rows = []
for f in F:
    j = jibun(f["GNG_CS"])
    sn = nm(f["BZ_NM"])
    hit, lvl = None, "없음"
    if j:
        cands = by_j.get((f["gu"],) + j, [])
        for g in cands:
            ks = {nm(g["상호명"] + g["지점명"]), nm(g["상호명"])}
            if sn in ks:
                hit, lvl = g, "A_지번+상호"; break
        if not hit:
            for g in cands:
                ks = {nm(g["상호명"] + g["지점명"]), nm(g["상호명"])}
                if any(len(k) >= 2 and len(sn) >= 2 and (k in sn or sn in k) for k in ks):
                    hit, lvl = g, "B_지번+상호일부"; break
        if not hit and cands:
            lvl = "D_지번만"
    menu = re.sub(r"<br\s*/?>", " / ", f.get("MNU", "") or "")
    two = "O" if re.search(r"2\s?인\s?(이상|분|부터|세트|기준)|2~\d\s?인|\(2인", menu) else ""
    one = "O" if re.search(r"1\s?인\s?(분|메뉴|세트)|\(1인", menu) else ""
    x = F2.get((f["gu"], f["BZ_NM"]))
    food_rows.append({"구군": f["gu"], "업소명": f["BZ_NM"], "업종": f["FD_CS"], "지번주소": f["GNG_CS"],
                      "좌석수": f.get("SEAT_CNT", ""), "메뉴": menu,
                      "2인이상표기": (x or {}).get("'2인 이상' 표기", ""),
                      "1인분표기": (x or {}).get("'1인분/1인메뉴' 표기", ""),
                      "연결단계": lvl, "상가업소번호": hit["상가업소번호"] if hit else "",
                      "상권_상호명": (hit["상호명"] + (" " + hit["지점명"] if hit["지점명"] else "")) if hit else "",
                      "상권업종소분류명": hit["상권업종소분류명"] if hit else "",
                      "도로명주소": hit["도로명주소"] if hit else ""})
with open(food_out, "w", encoding="utf-8-sig", newline="") as f_:
    w = csv.DictWriter(f_, fieldnames=list(food_rows[0].keys())); w.writeheader(); w.writerows(food_rows)
fc = Counter(r["연결단계"] for r in food_rows)
print("대구푸드", len(food_rows), dict(fc), "연결", sum(bool(r["상가업소번호"]) for r in food_rows))
print("대구푸드 달서구", sum(r["구군"] == "달서구" for r in food_rows), "연결", sum(r["구군"] == "달서구" and bool(r["상가업소번호"]) for r in food_rows))
food_by = {r["상가업소번호"]: r for r in food_rows if r["상가업소번호"]}
gp_by = {r["상가업소번호"]: r for r in GP if r["상가업소번호"]}

# 2인분 후보 파일·비교 업종 파일에 착한가격업소·대구푸드 칸
import os
cmp_p = os.path.join(os.path.dirname(cand_p), "달서구_비교업종_202609.csv")
for path in (cand_p, cmp_p):
    if not os.path.exists(path):
        continue
    RR = rd(path)
    for r in RR:
        g = gp_by.get(r["상가업소번호"])
        r["착한가격업소"] = "예" if g else ""
        ms = []
        if g:
            for i in range(1, 5):
                it, pr = g.get(f"착한가격메뉴 품목{i}", ""), g.get(f"착한가격메뉴 가격{i}", "")
                if it:
                    ms.append(f"{it}({pr}원)" if pr else it)
        r["착한가격메뉴"] = " / ".join(ms)
        r["착한_2인표기"] = g.get("메뉴명에 2인·다인분 표기", "") if g else ""
        r["착한_1인표기"] = g.get("메뉴명에 1인·1인분 표기", "") if g else ""
        x = food_by.get(r["상가업소번호"])
        r["대구푸드"] = "예" if x else ""
        r["대구푸드_2인이상표기"] = x["2인이상표기"] if x else ""
        r["대구푸드_1인분표기"] = x["1인분표기"] if x else ""
    with open(path, "w", encoding="utf-8-sig", newline="") as f_:
        w = csv.DictWriter(f_, fieldnames=list(RR[0].keys())); w.writeheader(); w.writerows(RR)
    print(os.path.basename(path), len(RR), "착한", sum(r["착한가격업소"] == "예" for r in RR), "대구푸드", sum(r["대구푸드"] == "예" for r in RR),
          "2인표기", sum(r["대구푸드_2인이상표기"] == "O" for r in RR), "1인표기", sum(r["대구푸드_1인분표기"] == "O" for r in RR))

# 수집양식 미리 채우기: 달서구 인허가 표본 중 2인분 후보
rows = []
order = lambda r: (r["구분"] != "기본", int(r["순서"] or 0))
dal = [r for r in L if r["구군"] == "달서구"]
# DS = 2인분 후보, DC = 비교 업종. 상권정보에 없고 지도 업종으로 정한 표본은 각 묶음 뒤에 붙인다.
groups = [
    ("DS", sorted([r for r in dal if r["달서구_2인분후보"] in ("소분류", "상호키워드")], key=order)
           + sorted([r for r in dal if r.get("지도기반_2인분후보", "") not in ("", "아님", "비교(지도업종)")], key=order)),
    ("DC", sorted([r for r in dal if r["달서구_2인분후보"] == "비교"], key=order)
           + sorted([r for r in dal if r.get("지도기반_2인분후보", "") == "비교(지도업종)"], key=order)),
]
seq = [(p, k, r) for p, rs in groups for k, r in enumerate(rs, 1)]
for prefix, k, r in seq:
    o = {h: "" for h in form_hdr}
    def put(prefix, val):
        for h in form_hdr:
            if h.startswith(prefix):
                o[h] = val; return
    put("수집ID", f"{prefix}-{k:03d}")
    put("표본구분", r["구분"]); put("관리번호", r["관리번호"]); put("상호", r["상호"]); put("구군", r["구군"])
    put("행정동", r["상권_행정동명"]); put("도로명주소", r["도로명주소"]); put("인허가_업태", r["업태"])
    put("상권_업종소분류", r["상권업종소분류명"])
    if not r["상권업종소분류명"] and r.get("지도_주소"):
        put("도로명주소", r["도로명주소"])
    ev = []
    g = gp_by.get(r["상가업소번호"])
    if g:
        menus = [g.get(f"착한가격메뉴 품목{i}", "") for i in range(1, 5)]
        ev.append(("공공DB", "행정안전부 착한가격업소(2026-09-30)", " / ".join(m for m in menus if m) or "(착한가격메뉴 없음)"))
    x = food_by.get(r["상가업소번호"])
    if x:
        ev.append(("공공DB", "대구푸드 맛집DB", x["메뉴"][:300]))
    for n, (kind, src, txt) in enumerate(ev[:2], 1):
        put(f"근거{n}_종류", kind); put(f"근거{n}_출처", src); put(f"근거{n}_원문", txt)
    grp = "2인분후보" if prefix == "DS" else "비교업종"
    if r["달서구_2인분후보"] in ("소분류", "상호키워드", "비교"):
        notes = [f"묶음={grp}", f"선정근거={'상권소분류' if r['달서구_2인분후보'] == '비교' else r['달서구_2인분후보']}"]
    else:
        notes = [f"묶음={grp}", f"선정근거=지도업종({r.get('지도_업종', '')} → {r.get('지도업종_대응소분류', '')}), 상권정보에 없음"]
    notes += [f"표본줄={L.index(r) + 2}", f"연결단계={r['연결단계']}"]
    if r.get("지도_판정"):
        notes.append(f"지도={r['지도_판정']}")
    put("비고", "; ".join(notes))
    rows.append(o)
with open(out_p, "w", encoding="utf-8-sig", newline="") as f_:
    w = csv.DictWriter(f_, fieldnames=form_hdr); w.writeheader(); w.writerows(rows)
for pfx in ("DS", "DC"):
    rr = [r for r in rows if r[form_hdr[0]].startswith(pfx)]
    print("수집양식", pfx, len(rr), Counter(r["상권_업종소분류"] for r in rr).most_common(), Counter(r[form_hdr[1]] for r in rr))
print("근거 있는 줄", sum(bool(r[[h for h in form_hdr if h.startswith('근거1_종류')][0]]) for r in rows))
