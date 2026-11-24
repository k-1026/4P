"""혼밥 챗봇 1차 데이터: 우리 자료 넷을 챗봇 팀 수집양식(29열) CSV 하나로 합친다. (사용자 결정 2026-11-24, 방안 C)

python -I 매칭도구/make_chatbot_v1.py --root . --form-head <챗봇/수집양식_빈양식.csv> --dalseo-judged <통합_v1/웹판정_시범.csv> --out <대구_수집양식_1차_20261124.csv>

입력과 우선순위 (같은 가게면 위가 이김):
  1. 달서구 지도 수집 판정 (11-24, judge_web_pilot.py 결과)  — 확인됨/추정만. '업종 기준'·모름은 넣지 않음
  2. 대구 전역 표본 최종 판정 904곳 (11-24) — 미상이 아닌 행 + 혼자 입장 가능/불가 행
  3. 다른 세션 '대구 2인분 이상' 844곳 — 미상 5곳 제외
  4. 혼밥 검색 종합 3,461곳 — 위 1~3에 같은 가게가 없고, 11-23 합본에서 2인분 쪽과 매칭되지 않았고, 인허가 폐업이 아니면
     → 최소주문 '1인분가능_추정' (방안 C의 규칙: 혼밥 검색에 나옴 + 2인분 이상 자료에 없음)

같은 가게 판단: 구군 + 상호(띄어쓰기·기호 뺀 것) — 챗봇 build_data.py와 같은 기준.
공개 저장소라 리뷰·블로그·커뮤니티 원문은 비운다(메뉴표기·공공DB 원문만 남김).
혼자 입장 '가능'은 리뷰·답글 근거가 있는 판정만 넣는다(혼자 태그 수로 본 추정은 넣지 않음 — 챗봇은 '가능'을 '혼자 가능 확인' 배지로 보여 주기 때문).
"""
import argparse
import csv
import os
import re
from collections import Counter

KEEP_TEXT = ("메뉴표기", "공공DB")


def rd(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def norm(s):
    return re.sub(r"[\s·()\[\]\-]", "", s or "")


def col(row, prefix):
    for k, v in row.items():
        if k and k.startswith(prefix):
            return (v or "").strip()
    return ""


def gu_of(addr):
    m = re.search(r"(중구|동구|서구|남구|북구|수성구|달서구|달성군|군위군)", addr or "")
    return m.group(1) if m else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--form-head", required=True)
    ap.add_argument("--dalseo-judged", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    R = lambda *p: os.path.join(a.root, *p)
    with open(a.form_head, encoding="utf-8-sig", newline="") as f:
        head = next(csv.reader(f))
    H = lambda p: next(h for h in head if h.startswith(p))
    out, seen, why = [], {}, Counter()
    by_mgmt, by_addr = {}, {}   # 관리번호 → src, 주소키 → [(정규화 상호, src)]  (Codex 검증 11-24: '…본점'처럼 상호만 다른 같은 가게)

    def addr_key(s):
        """도로명 + 건물번호만 (층·호·괄호·뒤에 붙은 상호는 뺌). Codex 2라운드: '9-3 덕일생고기 본점'"""
        m = re.search(r"([가-힣A-Za-z0-9]+(?:로|길))\s*(\d+(?:-\d+)?)", (s or "").replace("대구광역시", "").replace("대구 ", ""))
        return (m.group(1) + " " + m.group(2)) if m else ""

    def same_name(a, b):
        """앞부분이 같거나(2글자 이상), 한쪽 상호가 다른 쪽 안에 들어 있으면(3글자 이상) 같은 가게.
        Codex 3라운드: '산골순두부보쌈' / '갓바위산골순두부보쌈'"""
        a, b = (x.lower().replace("대구", "") for x in (a, b))   # 'K2'/'k2', '대구신천점'/'신천점'
        s, l = sorted((a, b), key=len)
        return (len(s) >= 2 and l.startswith(s)) or (len(s) >= 3 and s in l)

    def add(key, row, src):
        if key in seen:
            why[f"겹침: {src} → {seen[key]} 유지"] += 1
            return
        mg, ak, nm = row.get("관리번호", "").strip(), addr_key(row.get("도로명주소", "")), key[1]
        # 관리번호가 같아도 상호 앞부분까지 같을 때만 같은 가게 (Codex 2라운드: 같은 건물 다른 가게에 한 번호가 붙은 경우)
        if mg and any(same_name(n, nm) for n, _ in by_mgmt.get(mg, [])):
            why[f"겹침(관리번호+상호): {src} → {by_mgmt[mg][0][1]} 유지"] += 1
            return
        if ak and any(same_name(n, nm) for n, _ in by_addr.get(ak, [])):
            why[f"겹침(주소+상호 앞부분): {src} → {by_addr[ak][0][1]} 유지"] += 1
            return
        seen[key] = src
        if mg:
            by_mgmt.setdefault(mg, []).append((nm, src))
        if ak:
            by_addr.setdefault(ak, []).append((nm, src))
        r = {h: "" for h in head}
        for k, v in row.items():
            r[H(k)] = v
        for n in ("1", "2"):
            if r[H(f"근거{n}_종류")] not in KEEP_TEXT:
                r[H(f"근거{n}_원문")] = ""
        out.append(r)
        why[src] += 1

    # 1. 달서구 지도 수집 판정
    web = {r["상가업소번호"]: r for r in rd(R("원본자료", "웹데이터_달서구_v0_20261124.csv"))}
    for j in rd(a.dalseo_judged):
        if j["판정_이유"] == "수집 결과 없음" or j["지도_못찾음"] or j["근거_수준"] not in ("확인됨", "추정"):
            continue
        w = web[j["상가업소번호"]]
        yn, lv = j["1인분_여부"], j["근거_수준"]
        mino = {("2인분 이상", "확인됨"): "2인분이상_확정", ("2인분 이상", "추정"): "2인분이상_추정",
                ("1인분 가능", "확인됨"): "1인분가능_확정", ("1인분 가능", "추정"): "1인분가능_추정"}[(yn, lv)]
        ent = j["혼자_입장"] if j["혼자_근거_수준"] == "확인됨" else "미상"
        add(("달서구", norm(w["상호"])), {
            "수집ID": "W-" + j["상가업소번호"], "상호": w["상호"], "구군": "달서구", "행정동": w["행정동"],
            "도로명주소": w["도로명주소"], "상권_업종소분류": w["업종_소분류"], "대표메뉴": j["대표메뉴"][:80],
            "최소주문_판정": mino, "1인입장_판정": ent, "조건_적용범위": j["조건_범위"],
            "근거1_종류": "지도수집", "근거1_출처": "네이버·카카오 지도 (Aside)", "확인일": "2026-11-24", "확인자": "Claude+Aside",
            "비고": "; ".join(x for x in (j["판정_이유"], j["1인분_메모"], "따로 확인 필요" if j["따로_확인"] else "") if x),
        }, "1 달서구 지도 수집")

    # 2. 대구 전역 표본 최종 판정
    pre = {r["수집ID"]: r for r in rd(R("원본자료", "2인분식당_수집양식_대구전역표본_사전입력.csv"))}
    for f in rd(R("원본자료", "2인분식당_최종판정_대구전역_20261124.csv")):
        if f["최종_최소주문"] == "미상" and f["최종_1인입장"] not in ("가능", "불가"):
            continue
        p = pre.get(f["수집ID"], {})
        gu = f["구군"] if f["구군"] in ("중구", "동구", "서구", "남구", "북구", "수성구", "달서구", "달성군", "군위군") else gu_of(p.get("도로명주소", ""))
        add((gu, norm(f["상호"])), {
            "수집ID": f["수집ID"], "관리번호": p.get("관리번호(인허가)", ""), "상호": f["상호"], "구군": gu,
            "행정동": p.get("행정동", ""), "도로명주소": p.get("도로명주소", ""), "상권_업종소분류": f["상권_업종소분류"],
            "최소주문_판정": f["최종_최소주문"], "1인입장_판정": f["최종_1인입장"], "시간대제한": f["최종_시간대제한"],
            "조건_적용범위": f["최종_범위"], "근거1_종류": "지도·블로그", "근거1_URL": f["근거1_URL"],
            "근거2_URL": f["근거2_URL"], "확인일": "2026-11-24", "확인자": "Claude+Aside+Codex",
            "비고": f"대구 전역 표본 최종 판정({f['판정경로'][:20]})",
        }, "2 대구 표본")

    # 3. 다른 세션 2인분 이상 844곳
    for o in rd(R("자동화", "원본자료", "다른세션_대구2인분이상_20261123", "대구_2인분이상_식당_네이버카카오_구군별.csv")):
        if col(o, "최소주문_판정") == "미상":
            continue
        row = {h.split("(")[0]: o.get(h, "") for h in o}
        row["비고"] = ("다른 세션 대구 2인분 이상 검색 수집(11-23). " + row.get("비고", "")).strip()
        add((col(o, "구군"), norm(col(o, "상호"))), {k: v for k, v in row.items() if k and any(h.startswith(k) for h in head)}, "3 다른 세션 844곳")

    # 4. 혼밥 검색 종합 → 1인분가능_추정
    stat = {r["혼밥ID"]: r for r in rd(R("원본자료", "작업폴더", "매칭도구", "작업기록_20261123_합치기", "혼밥검색종합_음식점.csv"))}
    for u in rd(R("원본자료", "작업폴더", "원본자료", "대구_1인분·2인분이상_합본_20261123.csv")):
        if u["출처"] != "1인분쪽만(혼밥 검색)":
            continue
        s = stat.get(u["혼밥ID"], {})
        if s.get("인허가_상태") == "폐업":
            why["4 제외: 인허가 폐업"] += 1
            continue
        ent = "가능" if s.get("1인입장판정") == "가능" else "미상"
        add((u["구군"], norm(u["상호"])), {
            "수집ID": u["혼밥ID"], "관리번호": u["인허가_관리번호"], "상호": u["상호"], "구군": u["구군"],
            "도로명주소": u["도로명주소"], "인허가_업태": s.get("인허가_업태", ""), "대표메뉴": u["혼밥쪽_카테고리"],
            "최소주문_판정": "1인분가능_추정", "1인입장_판정": ent,
            "근거1_종류": "검색", "근거1_출처": "네이버·카카오 '혼밥' 검색 (11-23)",
            "근거1_URL": u["네이버링크"] or u["카카오링크"], "확인일": "2026-11-23", "확인자": "다른 세션 검색 수집",
            "비고": "방안 C 1차 추정: 혼밥 검색에 나옴 + 2인분 이상 자료에 없음 (메뉴·리뷰로 1인분 확인 안 함)",
        }, "4 혼밥 검색 추정")

    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=head, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(out)
    print(f"{len(out)}곳 -> {a.out}")
    for k, v in sorted(why.items()):
        print(f"  {k}: {v}")
    print("최소주문:", dict(Counter(r[H('최소주문_판정')] for r in out)))
    print("1인입장:", dict(Counter(r[H('1인입장_판정')] for r in out)))
    print("구군:", dict(Counter(r[H('구군')] for r in out)))


if __name__ == "__main__":
    main()
