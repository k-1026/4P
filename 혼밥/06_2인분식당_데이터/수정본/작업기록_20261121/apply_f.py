import csv, sys
link_p, review_p = sys.argv[1:3]
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig")))
L = rd(link_p)

# 표본파일 줄번호 -> (판정, 근거)
SAME = "E_손확인_같은가게"
UNK = "G_손확인_판단불가"
J = {
    35:   (SAME, "고유어 '형제' 같음, 인허가 한식 ↔ 국수/칼국수"),
    67:   (SAME, "'몬스터즈/몬스터스' 같음, 호프 ↔ 생맥주 전문"),
    393:  (SAME, "'미미' 같음, 분식 ↔ 김밥/만두/분식"),
    452:  (SAME, "'남쑨이포차' 같음, 뒤에 붙은 이름만 다름"),
    470:  (SAME, "같은 운영사(롯데컬처웍스)·같은 롯데시네마 율하, 커피숍 ↔ 카페"),
    623:  (SAME, "'불로할매' 같음, 뒤는 보신탕/식당(일반어)"),
    806:  (SAME, "'천서리' 메밀 같음, 한식 ↔ 냉면/밀면"),
    975:  (SAME, "'바삭이' 같음, 치킨"),
    1047: (SAME, "'땅땅치킨' 같음, 치킨"),
    1227: (SAME, "'맥·코리아·치킨호프' 글자 같고 순서만 다름, 치킨"),
    1392: (SAME, "'서울' 같음, 탕류 ↔ 국/탕/찌개류"),
    1656: (UNK,  "'김가네·부대찌개' 같으나 대표 메뉴가 헛제사밥 ↔ 철판닭갈비로 다름, 소분류도 돼지고기 구이/찜이라 같은 가게인지 판단 불가"),
    1760: (SAME, "'백곰가족' 같음, 커피숍 ↔ 카페"),
    1814: (SAME, "'경애네' 비빔밥 같음"),
    1825: (SAME, "'삼부자' 같음, 숯불갈비 ↔ 돼지고기 구이/찜"),
    1831: (UNK,  "'월미' 같으나 식당 ↔ 매점으로 영업 형태가 다름"),
    1898: (SAME, "'화개장터' 국밥 같음, 앞에 대표자 이름만 붙음"),
    1967: (SAME, "'소동밀면'은 '소문난동래밀면' 줄임, 같은 2층"),
    2009: (SAME, "'태경' 같음, 한식뷔페 ↔ 백반/한정식"),
    2100: (SAME, "'봉조' 뒷고기 같음"),
    2232: (UNK,  "'7090' 같으나 미스트짱 ↔ 미스트롯으로 이름이 다르고 라이브카페 ↔ 무도 유흥 주점으로 업종도 다름"),
    2512: (SAME, "'마들렌' 같음, 국채보상로 지점명, 제과점 ↔ 빵/도넛"),
    2596: (SAME, "'봉희' 같음, 한식 ↔ 곰탕"),
    2716: (SAME, "'바다속' 같음, 횟집 ↔ 횟집"),
    3440: (SAME, "'북성로' 같음, 뒤는 식당(일반어)/석쇠"),
    3683: (UNK,  "'골목'은 흔한 말이고 식당 ↔ 소주방으로 영업 형태가 다름"),
    3760: (SAME, "'장군' 같음, 식육(숯불구이) ↔ 소고기 구이/찜"),
    4022: (SAME, "'용가' 같음, 같은 3층, 중국식 ↔ 중국집"),
    4298: (SAME, "'개미' 같음, 분식 ↔ 김밥/만두/분식"),
}
CLR = ["상가업소번호", "상권_상호명", "상권업종대분류명", "상권업종중분류명", "상권업종소분류명",
       "상권_행정동명", "상권_도로명주소", "경도", "위도", "달서구_2인분후보"]
F = [i for i, r in enumerate(L) if r["연결단계"] == "F_손확인_유력"]
assert sorted(i + 2 for i in F) == sorted(J), (len(F), len(J))
for i in F:
    r = L[i]
    lvl, why = J[i + 2]
    r["연결단계"] = lvl
    if lvl == UNK:
        r["같은주소_다른상호"] = f'{r["상권_상호명"]}({r["상권업종소분류명"]})'
        for c in CLR:
            r[c] = ""

with open(link_p, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(L[0].keys())); w.writeheader(); w.writerows(L)

R = rd(review_p)
for x in R:
    x.setdefault("2차_근거", "")
    n = int(x["표본파일_줄번호"])
    if n in J:
        x["손확인_판정"], x["2차_근거"] = J[n]
        if J[n][0] == UNK:
            x["상권업종소분류명"] = ""
with open(review_p, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(R[0].keys())); w.writeheader(); w.writerows(R)

from collections import Counter
print(Counter(r["연결단계"] for r in L))
ok = [r for r in L if r["상가업소번호"]]
print("연결", len(ok), f"{len(ok)/len(L):.1%}")
for k in ("기본", "예비"):
    print(k, sum(r["구분"] == k for r in ok), "/", sum(r["구분"] == k for r in L))
print("리뷰파일", Counter(x["손확인_판정"] for x in R))
dal = [r for r in L if r["구군"] == "달서구"]
print("달서구", Counter(r["달서구_2인분후보"] for r in dal))
