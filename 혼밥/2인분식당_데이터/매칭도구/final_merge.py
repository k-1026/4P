"""두 출처 통합 판정 + 미상 손확인 + 블로그 근거를 합쳐 최종 판정을 낸다 (수집안내 3장 규칙).

python -I final_merge.py 대조파일.csv 미상손확인.csv 최종판정.csv [블로그결과.csv ...]

- 통합 판정이 미상이 아닌 곳은 그대로 둔다.
- 미상인 곳:
  * 손확인 '크기메뉴_최소2인' → 2인분이상_추정(가게 전체), 인분 = 가장 작은 크기 인원 (사용자 결정 2026-11-21)
  * 손확인 '가게규칙_1인1메뉴' → 1인분가능_확정
  * 블로그 문장 + 이미 있던 리뷰·블로그 1건을 합쳐 서로 다른 글 2건 이상이 2인 조건을 말하면 2인분이상_추정
  * 1인입장: 블로그 + 리뷰 합쳐 2건 이상이면 불가/가능
"""
import csv, io, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import judge_signals as J

x_p, m_p, out_p, *blog_ps = sys.argv[1:]
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig")))
X = rd(x_p)
M = {r["수집ID"]: r for r in rd(m_p)}
norm = lambda s: re.sub(r"\s+", " ", s or "").strip()

blog = {}
for p in blog_ps:
    t = open(p, encoding="utf-8", errors="replace").read()
    s = t.find('"수집ID"')
    if s < 0:
        print("머리줄 없음:", p); continue
    for r in csv.DictReader(io.StringIO(t[s:].split("```")[0])):
        k = {kk.split("(")[0]: v for kk, v in r.items() if kk}
        if k.get("근거_종류") == "블로그" and k.get("근거_원문"):
            if "협찬" in (k.get("메모") or ""):
                k["협찬"] = "O"
            blog.setdefault(k["수집ID"], []).append(k)
        else:
            blog.setdefault(k.get("수집ID", ""), [])

out = []
for o in X:
    sid = o["수집ID"]; m = M.get(sid, {})
    f = {"수집ID": sid, "묶음": o["묶음"], "상호": o["상호"], "상권_업종소분류": o["상권_업종소분류"],
         "최종_최소주문": o["통합_최소주문"], "최종_인분": o["통합_인분"], "최종_범위": o["A_범위"] or o["D_범위"],
         "최종_1인입장": o["통합_1인입장"], "최종_시간대제한": o["통합_시간대제한"], "판정경로": o["통합_출처"] or "",
         "손확인_분류": m.get("손확인_분류", ""), "블로그_근거": "", "최종_메모": o["통합_메모"]}
    B = blog.get(sid, [])
    if B:
        f["블로그_근거"] = " | ".join(f"{norm(b['근거_원문'])[:70]}({b.get('근거_작성일', '')}{', 협찬' if b.get('협찬') else ''})" for b in B[:4])
    if o["통합_최소주문"] == "미상":
        g = m.get("손확인_분류", "")
        why = m.get("손확인_내용", "")
        # 이미 있던 1건짜리 근거
        prior_cond = 1 if ("2인분이상" in o["D_최소주문"] and "블로그" in o["통합_메모"]) or "리뷰 1건만" in o.get("A_근거", "") else 0
        if "D '2인분이상_확정'는 블로그" in o["통합_메모"] or "D '2인분이상_확정'는 방문자리뷰" in o["통합_메모"]:
            prior_cond = 1
        b_cond = {norm(b["근거_원문"]) for b in B if J.COND2.search(b["근거_원문"]) and not b.get("협찬")}
        b_no = {norm(b["근거_원문"]) for b in B if J.ENTRY_NO.search(b["근거_원문"]) and not b.get("협찬")}
        b_ok = {norm(b["근거_원문"]) for b in B if (J.ENTRY_OK.search(b["근거_원문"]) or J.ENTRY_OK_REPLY.search(b["근거_원문"])) and not b.get("협찬")}
        prior_no = 1 if g == "1인입장_단서1건" and re.search(r"나가세요|입장불가|안돼|못", why) else 0
        prior_ok = 1 if g == "1인입장_단서1건" and not prior_no else 0
        if g == "크기메뉴_최소2인":
            n = re.search(r"(\d)\s*(인|人)", why)
            f.update({"최종_최소주문": "2인분이상_추정", "최종_인분": n.group(1) if n else 2, "최종_범위": "가게 전체", "판정경로": "손확인(크기 메뉴)"})
        elif g == "가게규칙_1인1메뉴":
            f.update({"최종_최소주문": "1인분가능_확정", "판정경로": "손확인(1인 1메뉴)"})
            if sid == "DS-075":   # 냄비탕만 2인분부터(리뷰 1 + 다이닝코드 블로그 1 = 2건), 혼밥 리뷰 2건
                f.update({"최종_최소주문": "2인분이상_추정", "최종_인분": 2, "최종_범위": "일부 메뉴", "최종_1인입장": "가능",
                          "최종_메모": "냄비탕만 2인분부터(리뷰+블로그 2건), 1인 뚝배기 있음, 혼밥 리뷰 2건"})
        if f["최종_최소주문"] == "미상" and len(b_cond) + prior_cond >= 2:
            ns = [int(d) for t in b_cond for d in re.findall(r"([2-5])\s*인", t)]
            f.update({"최종_최소주문": "2인분이상_추정", "최종_인분": max(ns) if ns else "", "판정경로": "블로그+기존 1건" if prior_cond else "블로그 2건",
                      "최종_범위": "가게 전체" if any(J.STORE_RULE.search(t) for t in b_cond) else ""})
        elif f["최종_최소주문"] == "미상" and b_cond:
            f["최종_메모"] = (f["최종_메모"] + "; " if f["최종_메모"] else "") + f"블로그 2인 조건 {len(b_cond)}건(기준 미달)"
        if f["최종_1인입장"] == "미상":
            if len(b_no) + prior_no >= 2 and not b_ok:
                f["최종_1인입장"] = "불가"
            elif len(b_ok) + prior_ok >= 2 and not b_no:
                f["최종_1인입장"] = "가능"
    # 혼밥 유형
    mo, en, n, sc = f["최종_최소주문"], f["최종_1인입장"], f["최종_인분"], f["최종_범위"]
    nn = f"{n}인분" if n else "N인분"
    if en == "불가" and f["최종_시간대제한"]:
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
    f["최종_혼밥유형"] = t
    out.append(f)

with open(out_p, "w", encoding="utf-8-sig", newline="") as fo:
    w = csv.DictWriter(fo, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
from collections import Counter
for g in ("2인분후보", "비교업종"):
    x = [f for f in out if f["묶음"] == g]
    two = [f for f in x if f["최종_최소주문"].startswith("2인분")]
    print(f"== {g} {len(x)}곳 | 최소주문 {dict(Counter(f['최종_최소주문'] for f in x))}")
    print(f"   2인분이상 {len(two)}곳: 가게 전체 {sum(f['최종_범위'] != '일부 메뉴' for f in two)}, 일부 메뉴 {sum(f['최종_범위'] == '일부 메뉴' for f in two)}, 인분 {dict(Counter(str(f['최종_인분']) for f in two))}")
    print(f"   1인입장 {dict(Counter(f['최종_1인입장'] for f in x))}")
    print(f"   혼밥유형 {Counter(f['최종_혼밥유형'] for f in x).most_common()}")
    print(f"   블로그 근거 있는 곳 {sum(bool(f['블로그_근거']) for f in x)}, 판정경로 {dict(Counter(f['판정경로'] for f in x if f['판정경로']))}")
