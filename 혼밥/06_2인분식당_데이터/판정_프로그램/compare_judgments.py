"""같은 표본을 두 출처로 판정한 결과를 가게마다 대조하고, 수집안내 3장 규칙으로 통합 판정을 낸다.

  A = Aside 수집(네이버·카카오 메뉴·메뉴판 사진·리뷰) → judge_signals.py 판정
  D = 다이닝코드 수집(메뉴판·후기·블로그) → 다른 세션의 판정(채움 파일)

통합 규칙:
  - 2인분이상_확정: 어느 한쪽에 메뉴 표기(또는 사장님 답글)로 2인분 이상 조건이 있음. 최소주문_인분은 큰 쪽.
  - 1인분가능_확정: 2인분 이상 근거가 없고, 어느 한쪽에 1인분 가능 확정 근거가 있음.
  - 양쪽 확정이 서로 반대(한쪽 2인분이상_확정, 다른 쪽 1인분가능_확정)면 통합은 2인분이상_확정으로 두고 '검토필요(엇갈림)'.
    (일부 메뉴만 2인분 이상인 가게는 1인분 메뉴가 같이 있을 수 있어 엇갈림이 아닐 수 있다.)
  - D의 '1인분가능_추정'·'2인분이상_추정'(메뉴 구성으로 짐작)은 3장 규칙의 '추정'(리뷰 2건 이상)과 달라서 통합 판정에 쓰지 않고 칸에만 남긴다.
  - 1인입장: 어느 한쪽이라도 불가면 불가, 아니면 가능 근거가 있으면 가능, 아니면 미상. 단 D의 '가능'은 키워드 근거일 수 있어 출처를 남긴다.
"""
import csv, sys
from collections import Counter

a_p, d_p, out_p = sys.argv[1:4]
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig")))
A = rd(a_p); D = rd(d_p)
ka, kd = list(A[0].keys()), list(D[0].keys())
col = lambda keys, prefix: next(k for k in keys if k.startswith(prefix))
AID, AMO, AEN, ASC, ATM = (col(ka, p) for p in ("수집ID", "최소주문_판정", "1인입장_판정", "조건_적용범위", "시간대제한"))
DID, DMO, DEN, DSC = (col(kd, p) for p in ("수집ID", "최소주문_판정", "1인입장_판정", "조건_적용범위"))
A1, D1 = col(ka, "근거1_원문"), col(kd, "근거1_원문")
D1S = col(kd, "근거1_출처")
dmap = {r[DID]: r for r in D}

grp = lambda v: "2인분이상" if v.startswith("2인분이상") else ("1인분가능" if v.startswith("1인분가능") else "미상")
out = []
for a in A:
    sid = a[AID]; d = dmap.get(sid, {})
    amo, dmo = a[AMO], d.get(DMO, "")
    dkind = d.get(col(kd, "근거1_종류"), "")
    notes = []
    # 3장 규칙: 확정은 메뉴 표기·사장님 답글만. D의 블로그·후기 1건 '확정'은 리뷰 근거 1건으로 센다
    if dmo.endswith("확정") and dkind in ("메뉴표기", "사장답글", "공공DB"):
        d_conf = dmo
    else:
        d_conf = "미상"
        if dmo.endswith("확정"):
            notes.append(f"D '{dmo}'는 {dkind} 1건이 근거라 3장 규칙의 확정이 아님")
    # A 리뷰 1건 + D 블로그·후기 1건 = 서로 다른 글 2건 → 2인분이상_추정
    a_rev1 = "리뷰 1건만 2인 조건" in a.get(col(ka, "비고"), "")
    if d_conf == "미상" and dmo == "2인분이상_확정" and dkind in ("블로그", "방문자리뷰") and a_rev1 and not amo.startswith("2인분"):
        amo = "2인분이상_추정"; notes.append("A 리뷰 1건 + D 블로그·후기 1건으로 추정")
    # 배달 메뉴만 있던 가게의 D 1인분 근거는 검토
    if d_conf.startswith("1인분") and "배달 메뉴에만" in a.get(col(ka, "비고"), ""):
        notes.append("검토필요: A는 배달 메뉴에만 1인 표기를 봤음(D 근거가 배달 메뉴인지 확인)")
    # 통합 최소주문
    if amo.startswith("2인분이상") or d_conf.startswith("2인분이상"):
        mo = "2인분이상_확정" if (amo == "2인분이상_확정" or d_conf == "2인분이상_확정") else "2인분이상_추정"
        if (amo.startswith("2인분이상") and d_conf.startswith("1인분")) or (d_conf.startswith("2인분이상") and amo.startswith("1인분")):
            notes.append("검토필요(엇갈림): 한쪽은 2인분 이상, 다른 쪽은 1인분 가능")
        src = "+".join(s for s, v in (("A", amo), ("D", d_conf)) if v.startswith("2인분이상"))
    elif amo.startswith("1인분") or d_conf.startswith("1인분"):
        mo = "1인분가능_확정"; src = "+".join(s for s, v in (("A", amo), ("D", d_conf)) if v.startswith("1인분"))
    else:
        mo = "미상"; src = ""
        if dmo.endswith("추정"):
            notes.append(f"D만 '{dmo}'(메뉴 구성으로 짐작, 통합에 안 씀)")
    # 인분: A의 최소주문_인분, D는 근거 원문에서 숫자
    import re
    nd = ""
    if d_conf.startswith("2인분이상"):
        m = re.search(r"([2-5])\s*인", d.get(D1, ""))
        nd = m.group(1) if m else ""
    n_all = [int(x) for x in (a.get("최소주문_인분", ""), nd) if str(x).isdigit()]
    n = max(n_all) if n_all and mo.startswith("2인분") else ""
    # 1인입장
    aen, den = a[AEN], d.get(DEN, "")
    if den == "가능" and dkind not in ("메뉴표기", "사장답글"):
        notes.append(f"D 1인입장 '가능'은 {dkind} 근거라 통합에 안 씀")
        den_use = "미상"
    else:
        den_use = den
    if "불가" in (aen, den_use):
        en = "불가"
    elif "가능" in (aen, den_use):
        en = "가능"
    else:
        en = "미상"
    agree = "같음" if grp(amo) == grp(d_conf) else ("A만 판정" if grp(d_conf) == "미상" else ("D만 판정" if grp(amo) == "미상" else "다름"))
    out.append({
        "수집ID": sid, "묶음": "2인분후보" if sid.startswith("DS") else "비교업종", "상호": a["상호"], "상권_업종소분류": a[col(ka, "상권_업종소분류")],
        "A_최소주문": amo, "A_인분": a.get("최소주문_인분", ""), "A_범위": a[ASC], "A_1인입장": aen, "A_혼밥유형": a.get("혼밥_유형", ""), "A_근거": a[A1][:120],
        "D_최소주문": dmo, "D_범위": d.get(DSC, ""), "D_1인입장": den, "D_근거출처": d.get(D1S, ""), "D_근거": d.get(D1, "")[:120],
        "두출처_최소주문": agree,
        "통합_최소주문": mo, "통합_출처": src, "통합_인분": n, "통합_1인입장": en,
        "통합_시간대제한": a[ATM], "통합_메모": "; ".join(notes),
    })

# 통합 혼밥 유형
for o in out:
    mo, en, n = o["통합_최소주문"], o["통합_1인입장"], o["통합_인분"]
    nn = f"{n}인분" if n else "N인분"
    sc = o["A_범위"] or o["D_범위"]
    if en == "불가" and o["통합_시간대제한"]:
        t = "특정 시간대 혼자 불가"
    elif en == "불가":
        t = "혼자 불가" + (" (1인분 메뉴는 있음)" if mo.startswith("1인분") else "")
    elif mo.startswith("2인분") and sc == "일부 메뉴":
        t = f"일부 메뉴만 {nn} 이상"
    elif mo.startswith("2인분"):
        t = f"혼자 가능, {nn} 이상 주문" if en == "가능" else f"{nn} 이상 주문 (혼자 입장 미상)"
    elif mo.startswith("1인분"):
        t = "혼자 1인분 가능" if en == "가능" else "1인분 메뉴 있음 (혼자 입장 미상)"
    elif en == "가능":
        t = "혼자 입장 가능 (최소주문 미상)"
    else:
        t = "미상"
    o["통합_혼밥유형"] = t

with open(out_p, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)

for g in ("2인분후보", "비교업종"):
    x = [o for o in out if o["묶음"] == g]
    print(f"== {g} {len(x)}곳")
    print("  두 출처 최소주문:", dict(Counter(o["두출처_최소주문"] for o in x)))
    print("  A 묶음별:", dict(Counter(grp(o["A_최소주문"]) for o in x)), " D 묶음별(확정만):", dict(Counter(grp(o["D_최소주문"] if o["D_최소주문"].endswith("확정") else "미상") for o in x)))
    print("  통합 최소주문:", dict(Counter(o["통합_최소주문"] for o in x)), " 출처:", dict(Counter(o["통합_출처"] for o in x if o["통합_출처"])))
    print("  통합 인분:", dict(Counter(o["통합_인분"] for o in x if o["통합_인분"])), " 통합 1인입장:", dict(Counter(o["통합_1인입장"] for o in x)))
    print("  통합 혼밥유형:", Counter(o["통합_혼밥유형"] for o in x).most_common())
    print("  엇갈림:", [(o["수집ID"], o["상호"]) for o in x if "엇갈림" in o["통합_메모"]])
