"""대구 1차 데이터를 '가게 한 곳당 한 줄' 파일로 내보낸다 (어떤 화면·서비스에도 넣을 수 있게). 사용자 결정 2026-11-24.

python -I 매칭도구/export_daegu_data.py --root . --data <대구_수집양식_1차_20261124.csv> --out <대구_혼밥식당_1차_20261124.csv>

- 입력: 챗봇 1차 데이터(4,487곳, Codex 검증 통과)
- 붙이는 것 (판정은 바꾸지 않음):
  · 위도·경도: 소상공인 상가정보 대구(2026-09)에서 도로명+건물번호와 상호(앞부분·포함)로 찾음 → 없으면 같은 건물 좌표 → 그래도 없으면 빈칸(좌표_근거='못 찾음')
  · 카카오 별점·방문자 리뷰 수: 혼밥 검색 자료에 있는 가게만
  · 화면용 분류(국밥·면·고기 …): 업종·상호·메뉴 글자로 정한 것. 판정에는 안 씀
  · 1인분_배지 / 혼밥_추천_대상: 아래 규칙
- 리뷰·블로그 원문은 넣지 않음.
"""
import argparse
import csv
import math
import os
import re
from collections import Counter

# 좌표·분류 함수 (웹 화면 사본 스크립트 make_web_daegu.py에서 옮겨 옴 — 화면은 쓰지 않기로 해서 그 파일은 지움)
CATS = [
    ("국밥", r"국밥|해장|곰탕|설렁|순대국|감자탕|추어|탕류|동태탕|갈비탕|삼계", "🍲", "#f1e2c9,#c9935a"),
    ("찌개", r"찌개|전골|청국장|순두부|부대", "🥘", "#f6dcc4,#d9773f"),
    ("고기", r"고기|구이|숯불|삼겹|갈비|막창|곱창|한우|식육|족발|보쌈|오리|닭갈비", "🔥", "#f3c7b5,#c8553a"),
    ("해산물", r"횟집|회센터|생선회|물회|모듬회|회 ?전문|해산물|해물|생선|복어|복 요리|아구|대게|장어|초밥", "🐟", "#dbe9f2,#6f9cc9"),
    ("면", r"국수|칼국수|냉면|밀면|라멘|라면|우동|소바|면 요리|쌀국수", "🍜", "#f6d9b8,#e9a35f"),
    ("중식", r"중국|중식|짜장|짬뽕|마라|훠궈|양꼬치", "🥟", "#f7d6cf,#d2553c"),
    ("분식", r"분식|김밥|떡볶이|만두|주먹밥|도시락|토스트", "🍙", "#e9f1e4,#8fbf7a"),
    ("덮밥", r"덮밥|돈까스|돈가스|카레|일식|텐동|규동", "🍛", "#fbe7c2,#e0a347"),
    ("양식", r"양식|경양식|파스타|피자|스테이크|레스토랑|이탈리안|버거|햄버거|샌드위치|샐러드|패스트푸드|브런치", "🍝", "#f5e6c8,#d9a441"),
    ("치킨", r"치킨|통닭|호프", "🍗", "#fbe3b3,#e8a33d"),
    ("세계요리", r"베트남|태국|인도|아시아|멕시|외국", "🌏", "#e6e1f0,#9a8bc0"),
    ("술집", r"주점|소주방|포차|이자카야|대포집", "🍶", "#e3dcd3,#8c7a66"),
    ("한식", r"한식|백반|정식|한정식|보리밥|쌈밥|비빔밥|밥상|기사식당", "🍱", "#e8eedb,#a9c08a"),
]


def rd(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def col(r, p):
    for k, v in r.items():
        if k and k.startswith(p):
            return (v or "").strip()
    return ""


def addr_key(s):
    m = re.search(r"([가-힣A-Za-z0-9]+(?:로|길))\s*(\d+(?:-\d+)?)", (s or "").replace("대구광역시", "").replace("대구 ", ""))
    return (m.group(1) + " " + m.group(2)) if m else ""


def nm(s):
    return re.sub(r"[\s·()\[\]\-&]", "", s or "").lower().replace("대구", "")


def same(a, b):
    s, l = sorted((a, b), key=len)
    return (len(s) >= 2 and l.startswith(s)) or (len(s) >= 3 and s in l)


def km(a, b, c, d):
    return 6371000 * 2 * math.asin(math.sqrt(math.sin(math.radians(c - a) / 2) ** 2 +
                                             math.cos(math.radians(a)) * math.cos(math.radians(c)) * math.sin(math.radians(d - b) / 2) ** 2))


def price_of(menu):
    m = re.search(r"(\d{1,3}(?:,\d{3})+|\d{4,6})\s*원", menu or "")
    return int(m.group(1).replace(",", "")) if m else None



BADGE = {"1인분가능_확정": "1인분 확인", "1인분가능_추정": "1인분 추정", "미상": "1인분 확인 안 됨"}
COLS = ["가게ID", "상호", "구군", "도로명주소", "위도", "경도", "좌표_근거", "분류", "업종_원자료", "대표메뉴_또는_업종", "가격_원자료",
        "1인분_배지", "최소주문_판정", "조건_인분_범위", "혼자_입장", "혼밥_추천_대상", "카카오_별점", "방문자_리뷰수",
        "판정_출처", "근거_종류", "근거_링크", "확인일", "메모"]


def src_of(sid):
    """수집ID 앞부분으로 출처 이름 (비고 칸은 원문 조각이 섞일 수 있어 쓰지 않음)"""
    if sid.startswith("W-"):
        return "달서구 지도 수집 (11-24)"
    if sid.startswith("H-"):
        return "혼밥 검색 + 2인분 자료 없음 (추정 규칙)"
    if sid.startswith("DG-"):
        return "다른 세션 대구 2인분 이상 수집 (11-23)"
    return "대구 전역 표본 최종 판정 (11-24)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    R_ = lambda *p: os.path.join(a.root, *p)
    shops = {}
    for s in rd(R_("원본자료", "소상공인시장진흥공단_상가상권정보_대구_202609.csv")):
        if s["상권업종대분류명"] == "음식" and s["위도"]:
            k = addr_key(s["도로명주소"])
            if k:
                shops.setdefault(k, []).append((nm(s["상호명"] + s["지점명"]), s["위도"], s["경도"]))
    hb = {r["혼밥ID"]: r for r in rd(R_("원본자료", "작업폴더", "매칭도구", "작업기록_20261123_합치기", "혼밥검색종합_음식점.csv"))}

    out, n = [], Counter()
    for i, r in enumerate(rd(a.data)):
        c = lambda p: col(r, p)
        name, addr, sid = c("상호"), c("도로명주소"), c("수집ID")
        # 구군은 주소에 적힌 구를 우선 (Codex 검증 11-24: 원자료에 달서구 주소인데 '서구'로 적힌 18곳)
        m = re.search(r"(중구|동구|서구|남구|북구|수성구|달서구|달성군|군위군)", re.sub(r"^(대구광역시|대구)\s*", "", addr))
        gu = m.group(1) if m else c("구군")
        if gu != c("구군"):
            n["구군 고침(주소 기준)"] += 1
        cands = shops.get(addr_key(addr), [])
        hit = next((x for x in cands if same(x[0], nm(name))), None)
        how = "주소+상호" if hit else ("같은 건물" if cands else "못 찾음")
        hit = hit or (cands[0] if cands else ("", "", ""))
        n["좌표: " + how] += 1
        mino, scope, ent = c("최소주문_판정"), c("조건_적용범위"), c("1인입장_판정")
        badge = BADGE.get(mino) or ("일부 메뉴 2인분" if scope == "일부 메뉴" else "2인분 이상")
        h = hb.get(sid, {})
        menu = c("대표메뉴")
        text = " ".join([c("상권_업종소분류"), c("인허가_업태"), h.get("카테고리", ""), menu, name])
        cat = next((x[0] for x in CATS if re.search(x[1], text)), "기타")
        in_ = mino.split("_")[0] if mino.startswith("2인분") else ""
        pv = price_of(menu)
        out.append({
            "가게ID": f"DG1-{i + 1:05d}", "상호": name, "구군": gu, "도로명주소": addr,
            "위도": hit[1], "경도": hit[2], "좌표_근거": how, "분류": cat,
            "업종_원자료": c("상권_업종소분류") or c("인허가_업태") or h.get("카테고리", ""),
            "대표메뉴_또는_업종": re.sub(r"\s+", " ", menu)[:80], "가격_원자료": pv if pv else "",
            "1인분_배지": badge, "최소주문_판정": mino,
            "조건_인분_범위": scope if mino.startswith("2인분") else "",
            "혼자_입장": ent if ent in ("가능", "불가") else "모름",
            "혼밥_추천_대상": "아니오" if badge == "2인분 이상" or ent == "불가" else "예",
            "카카오_별점": h.get("카카오별점", ""), "방문자_리뷰수": h.get("방문자리뷰", ""),
            "판정_출처": src_of(sid), "근거_종류": c("근거1_종류"), "근거_링크": c("근거1_URL"),
            "확인일": c("확인일"), "메모": "일부 메뉴만 2인분 (나머지 메뉴는 1인분 가능)" if badge == "일부 메뉴 2인분" else "",
        })
    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(out)
    print(f"{len(out)}곳 -> {a.out}")
    for k, v in sorted(n.items()):
        print(f"  {k}: {v}")
    for k in ("1인분_배지", "혼자_입장", "혼밥_추천_대상", "구군", "분류"):
        print(k, dict(Counter(r[k] for r in out)))
    print("별점 있음", sum(1 for r in out if r["카카오_별점"]), "가격 있음", sum(1 for r in out if r["가격_원자료"]))


if __name__ == "__main__":
    main()
