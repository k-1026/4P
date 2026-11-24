"""대구 전역 인허가 표본에서 2인분 후보·비교 업종 가게를 골라 수집양식을 미리 채운다 (달서구와 같은 방법, 2026-11-23).

- 표본: 가게목록_표본_상권정보연결_202609.csv (인허가 무작위 표본 4,435곳, 구·군 묶음 + 동성로 묶음)
- 후보·비교 판정: 대구_2인분후보업종_202609.csv / 대구_비교업종_202609.csv (상가업소번호), 상권정보에 없는 곳은 지도기반_2인분후보 칸
- 달서구 114곳은 기존 번호(DS-/DC-)를 그대로 쓰고, 나머지는 '묶음코드-S/C-번호'(예: JG-S-001)
- 근거 칸에는 착한가격업소·대구푸드 메뉴 원문(공공DB)을 넣는다. 판정 칸은 비워 둔다.

python -I prefill_daegu.py 원본자료폴더 빈수집양식.csv 출력.csv
"""
import csv, sys
from collections import Counter
B, form_p, out_p = sys.argv[1:4]
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig")))
L = rd(f"{B}/가게목록_표본_상권정보연결_202609.csv")
cand = {r["상가업소번호"]: r for r in rd(f"{B}/대구_2인분후보업종_202609.csv")}
cmp_ = {r["상가업소번호"]: r for r in rd(f"{B}/대구_비교업종_202609.csv")}
gp = {r["상가업소번호"]: r for r in rd(f"{B}/착한가격업소_대구외식업_상권정보연결_202609.csv") if r["상가업소번호"]}
food = {r["상가업소번호"]: r for r in rd(f"{B}/대구푸드_맛집DB_상권정보연결_202609.csv") if r["상가업소번호"]}
dal = {r["관리번호(인허가)"]: r for r in rd(f"{B}/2인분식당_수집양식_달서구표본_사전입력.csv")}
hdr = next(csv.reader(open(form_p, encoding="utf-8-sig")))
CODE = {"01_중구": "JG", "02_동구": "DG", "03_서구": "SG", "04_남구": "NG", "05_북구": "BG", "06_수성구": "SS",
        "07_달서구": "DS", "08_달성군": "DSG", "09_군위군": "GW", "10_동성로": "DSR"}

def put(o, prefix, val):
    for h in hdr:
        if h.startswith(prefix):
            o[h] = val; return

rows = []; seq = Counter()
order = sorted(range(len(L)), key=lambda i: (L[i]["묶음"], L[i]["구분"] != "기본", int(L[i]["순서"] or 0)))
for i in order:
    r = L[i]; g = r["상가업소번호"]
    if g:
        grp = "S" if g in cand else ("C" if g in cmp_ else None)
        basis = (cand[g]["선정근거"] if g in cand else "상권소분류") if grp else ""
        sub = r["상권업종소분류명"]
    else:
        m = r.get("지도기반_2인분후보", "")
        grp = "S" if m and m not in ("아님", "비교(지도업종)") else ("C" if m == "비교(지도업종)" else None)
        basis = f"지도업종({r.get('지도_업종', '')} → {r.get('지도업종_대응소분류', '')}), 상권정보에 없음" if grp else ""
        sub = ""
    if not grp:
        continue
    o = {h: "" for h in hdr}
    if r["묶음"] == "07_달서구" and r["관리번호"] in dal:
        sid = dal[r["관리번호"]][hdr[0]]
    else:
        code = CODE[r["묶음"]]; seq[(code, grp)] += 1
        sid = f"{code}-{grp}-{seq[(code, grp)]:03d}"
    put(o, "수집ID", sid); put(o, "표본구분", r["구분"]); put(o, "관리번호", r["관리번호"]); put(o, "상호", r["상호"])
    put(o, "구군", r["구군"]); put(o, "행정동", r["상권_행정동명"]); put(o, "도로명주소", r["도로명주소"]); put(o, "인허가_업태", r["업태"])
    put(o, "상권_업종소분류", sub)
    ev = []
    if g in gp:
        ms = [gp[g].get(f"착한가격메뉴 품목{k}", "") for k in range(1, 5)]
        ev.append(("공공DB", "행정안전부 착한가격업소(2026-09-30)", " / ".join(x for x in ms if x) or "(착한가격메뉴 없음)"))
    if g in food:
        ev.append(("공공DB", "대구푸드 맛집DB", food[g]["메뉴"][:300]))
    for n, (k, s, t) in enumerate(ev[:2], 1):
        put(o, f"근거{n}_종류", k); put(o, f"근거{n}_출처", s); put(o, f"근거{n}_원문", t)
    notes = [f"묶음={'2인분후보' if grp == 'S' else '비교업종'}", f"표본묶음={r['묶음']}", f"선정근거={basis}", f"표본줄={i + 2}", f"연결단계={r['연결단계']}"]
    if r.get("지도_판정"):
        notes.append(f"지도={r['지도_판정']}")
    put(o, "비고", "; ".join(notes))
    rows.append(o)
with open(out_p, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=hdr); w.writeheader(); w.writerows(rows)
c = Counter((r[hdr[0]].rsplit("-", 1)[0] if "-" in r[hdr[0]] and not r[hdr[0]].startswith(("DS-", "DC-")) else r[hdr[0]][:2], r[hdr[1]]) for r in rows)
print("전체", len(rows))
for k in sorted(c):
    print(" ", k, c[k])
print("공공DB 근거 있는 줄", sum(bool(r[[h for h in hdr if h.startswith('근거1_종류')][0]]) for r in rows))
