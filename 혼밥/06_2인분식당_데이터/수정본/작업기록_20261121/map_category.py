"""상권정보에 없는 '지도_영업중_상권없음' 줄에 지도(카카오·네이버) 업종 기준 2인분 후보 표시를 붙인다.
상권 소분류 10개에 대응하는 지도 업종 낱말과, 후보 보완 때 쓴 상호 키워드를 그대로 쓴다.
상권 소분류 칸은 비워 두고, 새 칸(지도업종_대응소분류, 지도기반_2인분후보)에만 적는다.
"""
import csv, re, sys
from collections import Counter
link_p, cand_kw_p = sys.argv[1:3]
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig")))
L = rd(link_p)
# 후보 보완 때 쓴 상호 키워드 목록(상권정보 '상호_키워드' 칸에 나온 값들)
KW = set()
for r in rd(cand_kw_p):
    for k in (r.get("상호_키워드") or "").split("/"):
        if k:
            KW.add(k)
KW = sorted(KW, key=len, reverse=True)
MAP = [  # (지도 업종 낱말, 대응 소분류)
    ("곱창,막창", "곱창 전골/구이"),
    ("육류,고기", "고기 구이(돼지·소 구분 안 됨)"),
    ("샤브샤브", "샤브샤브(상호키워드 '샤브'와 같은 묶음)"),
    ("장어", "해산물 구이/찜"),
    ("해물,생선", "해산물 구이/찜 또는 횟집"),
    ("매운탕,해물탕", "국/탕/찌개류"),
    ("찌개,전골", "국/탕/찌개류"),
    ("국밥", "국/탕/찌개류"),
    ("족발,보쌈", "족발/보쌈"),
    ("닭요리", "닭/오리고기 구이/찜"),
    ("오리", "닭/오리고기 구이/찜"),
    ("복어", "복 요리 전문"),
    ("회", "횟집"),
]
for r in L:
    r.setdefault("지도업종_대응소분류", "")
    r.setdefault("지도기반_2인분후보", "")
for r in L:
    if r["연결단계"] != "지도_영업중_상권없음":
        continue
    cat = r["지도_업종"] or ""
    parts = re.split(r"[>]", cat)
    sub = ""
    for word, s in MAP:
        if any(p.strip() == word for p in parts):
            sub = s; break
    name = re.sub(r"\s", "", r["상호"] + " " + (r["지도_상호"] or ""))
    kw = next((k for k in KW if k in name), "")
    r["지도업종_대응소분류"] = sub
    r["지도기반_2인분후보"] = "지도업종" if sub else ("상호키워드:" + kw if kw else "아님")
with open(link_p, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(L[0].keys())); w.writeheader(); w.writerows(L)
X = [r for r in L if r["연결단계"] == "지도_영업중_상권없음"]
print("358", Counter(r["지도기반_2인분후보"].split(":")[0] for r in X))
print("대응소분류", Counter(r["지도업종_대응소분류"] for r in X if r["지도업종_대응소분류"]).most_common())
print("상호키워드", Counter(r["지도기반_2인분후보"] for r in X if r["지도기반_2인분후보"].startswith("상호")).most_common())
d = [r for r in X if r["구군"] == "달서구"]
print("달서구", len(d), [(r["상호"], r["업태"], r["지도_업종"], r["지도기반_2인분후보"]) for r in d if r["지도기반_2인분후보"] != "아님"])
print("구군별 후보", Counter(r["구군"] for r in X if r["지도기반_2인분후보"] != "아님").most_common())
