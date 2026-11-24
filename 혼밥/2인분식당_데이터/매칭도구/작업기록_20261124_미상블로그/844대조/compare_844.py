"""다른 세션 '대구 2인분 이상 844곳'과 우리 표본 904곳이 겹치는 가게의 판정을 대조한다 (2026-11-24).

python -I compare_844.py   (이 폴더에서)

입력(읽기만): match_844_표본904.csv(store_match.py 결과), 844곳 원본 csv, 우리 1차 판정, 달서구 최종 판정
출력: 대조_844_표본904.csv (겹치는 가게 한 줄), 화면에 요약
- 자동 연결(A·B)만 같은 가게로 본다. D(주소만 같음)는 후보로 따로 적고, 같은 가게로 세지 않는다.
- 우리 쪽 값은 달서구=11-21 최종, 그 밖=1차(지도). 판정을 바꾸지 않고 비교만 한다.
"""
import csv
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
P844 = os.path.join(ROOT, "자동화", "원본자료", "다른세션_대구2인분이상_20261123", "대구_2인분이상_식당_네이버카카오_구군별.csv")
PJ = os.path.join(ROOT, "원본자료", "2인분식당_수집양식_대구전역표본_판정_Aside_20261123.csv")
PD = os.path.join(ROOT, "원본자료", "2인분식당_최종판정_20261121.csv")


def rd(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def col(row, prefix):
    return next(k for k in row if k == prefix or k.startswith(prefix + "("))


M = rd(os.path.join(HERE, "match_844_표본904.csv"))
O = {r["수집ID"]: r for r in rd(P844)}
J = {r["수집ID"]: r for r in rd(PJ)}
D = {r["수집ID"]: r for r in rd(PD)}
j0, o0 = next(iter(J.values())), next(iter(O.values()))
JMO, JEN, JSC = col(j0, "최소주문_판정"), col(j0, "1인입장_판정"), col(j0, "조건_적용범위")
OMO, OEN, OSC = col(o0, "최소주문_판정"), col(o0, "1인입장_판정"), col(o0, "조건_적용범위")


def ours(sid):
    if sid in D:
        d = D[sid]
        return d["최종_최소주문"], d["최종_1인입장"], d["최종_범위"], "달서구 최종(11-21)"
    j = J[sid]
    return j[JMO], j[JEN], j[JSC], "1차(지도)"


def relation(a, b):
    """a=우리, b=다른 세션 최소주문."""
    if a == b:
        return "같음"
    if a.startswith("2인분") and b.startswith("2인분"):
        return "둘 다 2인분이상(확정/추정 차이)"
    if a == "미상" and b.startswith("2인분"):
        return "우리 미상 ↔ 그쪽 2인분이상"
    if a.startswith("1인분") and b.startswith("2인분"):
        return "충돌: 우리 1인분가능 ↔ 그쪽 2인분이상"
    return f"기타: {a} ↔ {b}"


out, cands = [], []
for m in M:
    o = O[m["수집ID"]]
    step = m["매칭_단계"]
    if step.startswith(("A_", "B_")):
        sid = m["매칭_ID"]
        mo, en, sc, src = ours(sid)
        out.append({
            "우리_수집ID": sid, "그쪽_수집ID": o["수집ID"], "매칭_단계": step, "우리_상호": J[sid]["상호"], "그쪽_상호": o["상호"],
            "구군": o["구군"], "우리_주소": J[sid]["도로명주소"], "그쪽_주소": o["도로명주소"],
            "우리_최소주문": mo, "그쪽_최소주문": o[OMO], "최소주문_관계": relation(mo, o[OMO]),
            "우리_범위": sc, "그쪽_범위": o[OSC], "우리_1인입장": en, "그쪽_1인입장": o[OEN],
            "우리_판정출처": src, "그쪽_근거1": (o["근거1_원문"] or "")[:120], "그쪽_근거1_URL": o["근거1_URL"],
            "그쪽_근거2": (o["근거2_원문"] or "")[:120], "그쪽_근거2_URL": o["근거2_URL"],
        })
    elif step.startswith("D_"):
        cands.append((o["수집ID"], o["상호"], o["도로명주소"], m["매칭_같은주소_다른상호"]))

path = os.path.join(HERE, "대조_844_표본904.csv")
with open(path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()), quoting=csv.QUOTE_ALL)
    w.writeheader()
    w.writerows(out)
with open(os.path.join(HERE, "후보_주소만같음.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, quoting=csv.QUOTE_ALL)
    w.writerow(["그쪽_수집ID", "그쪽_상호", "그쪽_주소", "같은주소_우리표본"])
    w.writerows(cands)

print(f"같은 가게 {len(out)}곳 (중복 우리ID {len(out) - len({x['우리_수집ID'] for x in out})})")
print("최소주문 관계:", Counter(x["최소주문_관계"] for x in out).most_common())
print("우리 판정 출처:", Counter(x["우리_판정출처"] for x in out).most_common())
print("1인입장:", Counter((x["우리_1인입장"], x["그쪽_1인입장"]) for x in out).most_common())
print(f"주소만 같은 후보 {len(cands)}곳 -> 후보_주소만같음.csv")
