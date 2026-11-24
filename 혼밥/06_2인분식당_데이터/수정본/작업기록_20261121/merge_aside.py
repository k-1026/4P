"""Aside 지도 확인 결과(aside_out_*.csv)를 연결 파일에 반영한다.

판정 → 연결단계
  있음           → 지도_영업중_상권없음   (가게는 지도에 있으나 상권정보에 없음, 소분류 없음)
  이름바뀜       → 지도_이름바뀜          (같은 주소 상권정보 가게 중 지도 상호와 맞는 곳이 있으면 이어서 소분류 씀)
  이전           → 지도_이전              (옮긴 주소의 상권정보 가게와 상호가 맞으면 이어서 소분류 씀)
  없음_다른가게  → 지도_다른가게만있음
  없음           → 지도_찾을수없음
  폐업표시       → 지도_폐업표시
"""
import csv, io, re, sys, glob
from collections import defaultdict, Counter

link_p, sg_p, cand_p, out_glob, log_p = sys.argv[1:6]
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig")))
L = rd(link_p)
G = rd(sg_p)
cand = {r["상가업소번호"]: r["선정근거"] for r in rd(cand_p)}
nm = lambda s: re.sub(r"[^0-9A-Za-z가-힣]", "", re.sub(r"\(.*?\)", "", s or "")).lower()
addr = lambda a: re.sub(r"\s+", " ", (a or "").replace("대구광역시", "대구").split("(")[0].split(",")[0].replace(" 지하 ", " ")).strip()
bldg = lambda a: re.sub(r"\s+\d+층.*$", "", addr(a))
by = defaultdict(list)
for g in G:
    by[addr(g["도로명주소"])].append(g)

res = {}
for p in sorted(glob.glob(out_glob)):
    txt = open(p, encoding="utf-8", errors="replace").read()
    s = txt.find("번호,")
    if s < 0:
        s = txt.find('"번호"')
    if s < 0:
        print("머리줄 없음:", p); continue
    body = txt[s:].split("```")[0]
    for row in csv.DictReader(io.StringIO(body)):
        try:
            res[int(str(row.get("번호", "")).strip().strip('"'))] = row
        except ValueError:
            pass
print("지도 결과", len(res))

MAP = {"있음": "지도_영업중_상권없음", "이름바뀜": "지도_이름바뀜", "이전": "지도_이전",
       "없음_다른가게": "지도_다른가게만있음", "없음": "지도_찾을수없음", "폐업표시": "지도_폐업표시"}
CLR = ["상가업소번호", "상권_상호명", "상권업종대분류명", "상권업종중분류명", "상권업종소분류명",
       "상권_행정동명", "상권_도로명주소", "경도", "위도", "달서구_2인분후보"]
for c in ("지도_판정", "지도_상호", "지도_업종", "지도_주소", "지도_출처", "지도_메모", "지도_확인일"):
    for r in L:
        r.setdefault(c, "")

log = []
for n, row in res.items():
    r = L[n - 2]
    if not r["연결단계"].startswith(("D_손확인", "없음")):
        log.append([n, r["상호"], "건너뜀(이미 연결)", ""]); continue
    j = (row.get("판정") or "").strip()
    r.update({"지도_판정": j, "지도_상호": row.get("지도_상호", ""), "지도_업종": row.get("지도_업종", ""),
              "지도_주소": row.get("지도_주소", ""), "지도_출처": row.get("지도출처(카카오/네이버)", row.get("지도출처", "")),
              "지도_메모": row.get("메모", ""), "지도_확인일": "2026-11-21"})
    hit = None
    if j in ("이름바뀜", "이전"):
        place = addr(row.get("지도_주소")) if j == "이전" else addr(r["도로명주소"])
        mn = nm(row.get("지도_상호") if j == "이름바뀜" else r["상호"])
        pool = by.get(place, []) or by.get(bldg(row.get("지도_주소", "")), [])
        for g in pool:
            k = nm(g["상호명"] + g["지점명"])
            if mn and (mn == k or mn in k or k in mn or mn == nm(g["상호명"])):
                hit = g; break
    if j in MAP:
        r["연결단계"] = MAP[j] + ("_상권연결" if hit else "")
    if hit:
        r.update({"상가업소번호": hit["상가업소번호"],
                  "상권_상호명": hit["상호명"] + (" " + hit["지점명"] if hit["지점명"] else ""),
                  "상권업종대분류명": hit["상권업종대분류명"], "상권업종중분류명": hit["상권업종중분류명"],
                  "상권업종소분류명": hit["상권업종소분류명"], "상권_행정동명": hit["행정동명"],
                  "상권_도로명주소": hit["도로명주소"], "경도": hit["경도"], "위도": hit["위도"],
                  "달서구_2인분후보": cand.get(hit["상가업소번호"], "아님") if hit["시군구명"] == "달서구" else ""})
    log.append([n, r["상호"], r["연결단계"], r["상권_상호명"] if hit else ""])

with open(link_p, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(L[0].keys())); w.writeheader(); w.writerows(L)
with open(log_p, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f); w.writerow(["표본파일_줄번호", "표본_상호", "결과", "이은_상권상호"]); w.writerows(log)

print(Counter(r["연결단계"] for r in L).most_common())
ok = [r for r in L if r["상가업소번호"]]
print("연결", len(ok), f"{len(ok)/len(L):.1%}", [sum(r["구분"] == k for r in ok) for k in ("기본", "예비")])
miss = [r for r in L if r["연결단계"].startswith(("D_손확인", "없음")) and not r["연결단계"].startswith("없음_행사")]
print("지도 결과 없이 남은 줄", len(miss))
dal = [r for r in L if r["구군"] == "달서구"]
print("달서구", Counter(r["달서구_2인분후보"] for r in dal))
