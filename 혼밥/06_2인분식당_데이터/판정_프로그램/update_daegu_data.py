"""대구 혼밥 식당 데이터 최신화: 이전 판(1차, v2 …)에 새 지도 수집 판정을 덮어 새 판 + 바뀐 목록 + 사례 문서를 만든다. (사용자 결정 2026-11-24)

python -I 매칭도구/update_daegu_data.py --root . --base <이전 판 csv> --judged <통합폴더/웹판정_시범.csv> --evidence <통합폴더/근거전체.csv> \
       --date 2026-11-24 --ver v2 --outdir <폴더>

새 지도 판정(judge_web_pilot.py 결과) → 값
  1인분 가능·확인됨            → 1인분 확인 (1인분가능_확정)
  1인분 가능·추정 + '일부 메뉴 2인분' 메모 → 일부 메뉴 2인분 (원래 2인분 판정 유지, 범위 일부 메뉴)
  1인분 가능·추정 (그 밖)       → 1인분 추정 (근거: 지도 메뉴에 한 그릇 가격, 2인분 조건 없음)
  2인분 이상·확인됨/추정        → 2인분 이상
  1인분 가능·업종 기준, 모름     → 정보 없음 (값을 바꾸지 않음)
  지도에서 못 찾음              → 정보 없음 + 메모 '지도에서 못 찾음(폐업·이전 가능)'
덮어쓰기 규칙
  - 정보 없음이면 이전 값 유지, 지도확인일·지도확인_결과만 적는다 (사용자 결정: '추정 유지 + 확인일 기록').
  - 새 값이 있으면 바꾼다. 단 이전이 '1인분 확인'이고 새 값이 '1인분 추정'이면 더 약한 근거라 이전 유지.
    이전이 확인(1인분 확인/2인분 이상 확정)인데 새 값이 정반대(2인분 이상 ↔ 1인분 확인)면 새 값을 쓰고 '검토 필요'를 단다.
  - 이전 판에 없던 가게는 새 값이 있을 때만 새 줄로 더한다(좌표는 상가정보).
같은 가게: 구군 + 도로명+건물번호 + 상호(앞부분·포함) — export_daegu_data.py와 같은 함수.
"""
import argparse
import csv
import importlib.util
import os
import re
from collections import Counter, defaultdict

_s = importlib.util.spec_from_file_location("ex", os.path.join(os.path.dirname(os.path.abspath(__file__)), "export_daegu_data.py"))
ex = importlib.util.module_from_spec(_s)
_s.loader.exec_module(ex)

NEW_COLS = ["지도확인일", "지도확인_결과"]
STRONG = {"1인분 확인": "1", "2인분 이상": "2"}


def new_value(j):
    """웹판정 한 줄 → (배지, 최소주문, 범위, 설명) 또는 None(정보 없음)"""
    if j["지도_못찾음"]:
        return None, "지도에서 못 찾음(폐업·이전 가능)"
    yn, lv, memo = j["1인분_여부"], j["근거_수준"], j["1인분_메모"]
    if yn == "1인분 가능" and lv == "확인됨":
        return ("1인분 확인", "1인분가능_확정", "", "지도: 1인분·1인 메뉴 표기"), "1인분 확인"
    if yn == "1인분 가능" and lv == "추정" and "일부 메뉴 2인분" in memo:
        mino = j["1차_최소주문"] if j["1차_최소주문"].startswith("2인분") else "2인분이상_확정"
        return ("일부 메뉴 2인분", mino, "일부 메뉴", "지도: 일부 메뉴에만 2인분 조건"), "일부 메뉴 2인분"
    if yn == "1인분 가능" and lv == "추정":
        return ("1인분 추정", "1인분가능_추정", "", "지도: 한 그릇 단위 가격, 2인분 조건 없음"), "1인분 추정(메뉴)"
    if yn == "2인분 이상":
        mino = "2인분이상_확정" if lv == "확인됨" else "2인분이상_추정"
        return ("2인분 이상", mino, j["조건_범위"] or "가게 전체", "지도: 2인분 이상 조건"), "2인분 이상"
    return None, "지도 확인, 인분 정보 없음"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--judged", required=True)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--ver", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    base = ex.rd(a.base)
    cols = list(base[0].keys()) + [c for c in NEW_COLS if c not in base[0]]
    for b in base:
        for c in NEW_COLS:
            b.setdefault(c, "")
    idx = defaultdict(list)   # (구, 주소키) → 행 번호
    for i, b in enumerate(base):
        idx[(b["구군"], ex.addr_key(b["도로명주소"]))].append(i)
    web = {r["상가업소번호"]: r for r in ex.rd(os.path.join(a.root, "원본자료", "웹데이터_달서구_v0_20261124.csv"))}
    ev = defaultdict(list)
    for e in ex.rd(a.evidence):
        ev[e["수집ID"]].append(e)

    changes, cases, n = [], [], Counter()
    nxt = max(int(re.sub(r"\D", "", b["가게ID"]) or 0) for b in base) + 1
    for j in ex.rd(a.judged):
        if j["판정_이유"] == "수집 결과 없음":
            continue
        w = web[j["상가업소번호"]]
        gu = "달서구"
        k = ex.addr_key(w["도로명주소"])
        names = {ex.nm(w["상호"]), ex.nm(w["상호"] + w["지점명"])}
        sc = [(match_score(ex.nm(base[i]["상호"]), names), i) for i in idx.get((gu, k), [])]
        sc = [x for x in sc if x[0] > 0]
        hit = max(sc)[1] if sc else None
        val, res = new_value(j)
        ent_new = "가능" if j["혼자_입장"] == "가능" and j["혼자_근거_수준"] == "확인됨" else None
        # 사례용 근거 문구 (메뉴판 문구만, 리뷰·블로그 원문은 쓰지 않음)
        menu_ev = [e["근거_원문"] for e in ev.get(j["상가업소번호"], []) if e["근거_종류"] == "메뉴표기" and e["근거_원문"]]
        if hit is None:
            n["새 가게: " + ("추가" if val else "정보 없어 안 넣음")] += 1
            if not val:
                continue
            badge, mino, scope, why = val
            row = {c: "" for c in cols}
            row.update({"가게ID": f"DG2-{nxt:05d}", "상호": w["상호"], "구군": gu, "도로명주소": w["도로명주소"],
                        "위도": w["위도"], "경도": w["경도"], "좌표_근거": "상가정보(수집 대상)", "분류": cat_of(w, j),
                        "업종_원자료": w["업종_소분류"], "대표메뉴_또는_업종": re.sub(r"\s+", " ", j["대표메뉴"])[:80],
                        "가격_원자료": ex.price_of(j["대표메뉴"]) or "", "1인분_배지": badge, "최소주문_판정": mino,
                        "조건_인분_범위": scope if mino.startswith("2인분") else "", "혼자_입장": ent_new or "모름",
                        "판정_출처": f"달서구 지도 수집 ({a.date})", "근거_종류": "지도수집", "확인일": a.date,
                        "메모": "일부 메뉴만 2인분 (나머지 메뉴는 1인분 가능)" if badge == "일부 메뉴 2인분" else "",
                        "지도확인일": a.date, "지도확인_결과": res})
            row["혼밥_추천_대상"] = "아니오" if badge == "2인분 이상" or row["혼자_입장"] == "불가" else "예"
            nxt += 1
            base.append(row)
            changes.append({"가게ID": row["가게ID"], "상호": row["상호"], "구분": "새 가게", "전": "", "후": badge, "근거": why})
            continue
        b = base[hit]
        before = b["1인분_배지"]
        b["지도확인일"], b["지도확인_결과"] = a.date, res
        if before == "1인분 추정" and b["판정_출처"].startswith("혼밥 검색"):
            cases.append({"상호": b["상호"], "주소": b["도로명주소"], "1차": before, "지도": res,
                          "대표메뉴": j["대표메뉴"][:70], "메뉴문구": " / ".join(pick_ev(menu_ev, res)[:2])[:120]})
        if not val:
            n["기존: 정보 없음(유지)"] += 1
            if res.startswith("지도에서 못 찾음"):
                b["메모"] = (b["메모"] + " / " if b["메모"] else "") + res
            continue
        badge, mino, scope, why = val
        if before == "1인분 확인" and badge == "1인분 추정":
            n["기존: 더 약한 근거라 유지"] += 1
            continue
        flag = STRONG.get(before) and STRONG.get(badge) and STRONG[before] != STRONG[badge]
        if before == badge and b["최소주문_판정"] == mino:
            n["기존: 같은 값(확인일만)"] += 1
            b["판정_출처"], b["확인일"] = f"달서구 지도 수집 ({a.date})", a.date
            continue
        n["기존: 값 바뀜" + (" (검토 필요)" if flag else "")] += 1
        b.update({"1인분_배지": badge, "최소주문_판정": mino, "조건_인분_범위": scope if mino.startswith("2인분") else "",
                  "판정_출처": f"달서구 지도 수집 ({a.date})", "근거_종류": "지도수집", "근거_링크": "", "확인일": a.date,
                  "메모": ("검토 필요: 이전 확인 값과 반대 / " if flag else "") + ("일부 메뉴만 2인분 (나머지 메뉴는 1인분 가능)" if badge == "일부 메뉴 2인분" else "")})
        if ent_new:
            b["혼자_입장"] = ent_new
        b["혼밥_추천_대상"] = "아니오" if badge == "2인분 이상" or b["혼자_입장"] == "불가" else "예"
        changes.append({"가게ID": b["가게ID"], "상호": b["상호"], "구분": "값 바뀜" + (" (검토 필요)" if flag else ""), "전": before, "후": badge, "근거": why})

    tag = f"대구_혼밥식당_{a.ver}_{a.date.replace('-', '')}"
    with open(os.path.join(a.outdir, tag + ".csv"), "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=cols, quoting=csv.QUOTE_ALL)
        wr.writeheader()
        wr.writerows(base)
    with open(os.path.join(a.outdir, f"바뀐목록_{a.ver}.csv"), "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["가게ID", "상호", "구분", "전", "후", "근거"], quoting=csv.QUOTE_ALL)
        wr.writeheader()
        wr.writerows(changes)
    write_cases(os.path.join(a.outdir, f"사례_추정확인_{a.ver}.md"), cases, a)
    print(f"{tag}.csv {len(base)}곳 (바뀐 줄 {len(changes)})")
    for k, v in sorted(n.items()):
        print(f"  {k}: {v}")
    print("1인분_배지:", dict(Counter(b["1인분_배지"] for b in base)))
    print("추정 사례:", dict(Counter(c["지도"] for c in cases)))


def match_score(b, names):
    """같은 주소 안에서 같은 가게일 점수 (0 = 아님). 3 똑같은 상호(한 글자 포함) > 2 앞부분·포함 일치 > 1 앞 4글자+ 같고 다른 부분이 지점명('…점').
    Codex 검증 11-24: '준' / '삼선미나주곰탕냉면 호산점'·'삼선미나주곰탕 계명대점' 은 같은 가게, '이랜드이츠리미니'·'이랜드이츠피자몰'은 다른 가게"""
    best = 0
    for n in names:
        if not b or not n:
            continue
        if b == n:
            return 3
        if ex.same(b, n):
            best = max(best, 2)
            continue
        p = 0
        while p < min(len(b), len(n)) and b[p] == n[p]:
            p += 1
        rb, rn = b[p:], n[p:]
        if p >= 4 and (rb.endswith("점") or not rb) and (rn.endswith("점") or not rn):
            best = max(best, 1)
    return best


def pick_ev(lines, res):
    """사례 표에 보여 줄 메뉴판 문구: 결과와 관계있는 줄을 앞에 (1인분 쪽이면 '1인', 2인분 쪽이면 '2인·3인')"""
    pat = r"[2-9]\s*인" if res in ("2인분 이상", "일부 메뉴 2인분") else r"1\s*인|혼밥|나홀로"
    return [x for x in lines if re.search(pat, x)] + [x for x in lines if not re.search(pat, x)]


def cat_of(w, j):
    text = " ".join([w["업종_소분류"], j["대표메뉴"], w["상호"]])
    return next((x[0] for x in ex.CATS if re.search(x[1], text)), "기타")


def write_cases(path, cases, a):
    c = Counter(x["지도"] for x in cases)
    tot = len(cases)
    judged = sum(v for k, v in c.items() if k in ("1인분 확인", "1인분 추정(메뉴)", "일부 메뉴 2인분", "2인분 이상"))
    good = sum(v for k, v in c.items() if k in ("1인분 확인", "1인분 추정(메뉴)", "일부 메뉴 2인분"))
    L = [f"# '1인분 추정'은 맞았나 — 실제 사례 ({a.ver}, {a.date})", "",
         "1차 데이터의 '1인분 추정'(혼밥 검색에 나옴 + 2인분 이상 자료에 없음) 가게 가운데, 이번에 Aside로 네이버·카카오 지도를 직접 본 달서구 가게를 모았다.",
         "", f"- 대상: **{tot}곳**", ""]
    L += ["| 지도로 본 결과 | 곳 수 | 뜻 |", "|---|---|---|"]
    mean = {"1인분 확인": "추정이 맞음 (1인분·1인 메뉴 표기)", "1인분 추정(메뉴)": "대체로 맞음 (한 그릇 가격, 2인분 조건 없음)",
            "일부 메뉴 2인분": "대체로 맞음 (일부 메뉴만 2인분)", "2인분 이상": "**추정이 틀림**",
            "지도 확인, 인분 정보 없음": "판단 못 함", "지도에서 못 찾음(폐업·이전 가능)": "판단 못 함 (폐업·이전 가능)"}
    for k in mean:
        if c.get(k):
            L.append(f"| {k} | {c[k]} | {mean[k]} |")
    if judged:
        L += ["", f"**판단할 수 있었던 {judged}곳 중 {good}곳({good * 100 // judged}%)은 추정이 맞거나 대체로 맞았고, {judged - good}곳({(judged - good) * 100 // judged}%)은 실제로 2인분 이상이었다.**",
              "(표본이 작은 달서구 일부 자료라 대구 전체 비율로 쓰지 않는다. 지도 수집은 D등급 — 사례·경향으로만 쓴다.)"]
    for k in ("2인분 이상", "1인분 확인", "일부 메뉴 2인분", "1인분 추정(메뉴)", "지도에서 못 찾음(폐업·이전 가능)", "지도 확인, 인분 정보 없음"):
        xs = [x for x in cases if x["지도"] == k]
        if not xs:
            continue
        L += ["", f"## {k} ({len(xs)}곳)", "", "| 상호 | 주소 | 대표 메뉴 (지도) | 메뉴판 문구 |", "|---|---|---|---|"]
        for x in xs[:12]:
            L.append(f"| {x['상호']} | {x['주소']} | {x['대표메뉴'].replace('|', '/')} | {x['메뉴문구'].replace('|', '/')} |")
        if len(xs) > 12:
            L.append(f"| … 외 {len(xs) - 12}곳 | | | |")
    with open(path, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
