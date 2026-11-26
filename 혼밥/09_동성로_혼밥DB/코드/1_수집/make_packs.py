"""동성로 자료를 담당(에이전트)별 파일로 나누고 압축한다. 수집이 더 되면 다시 실행하면 새 결과가 들어간다.

python -I make_packs.py <출력 폴더>
"""
import csv
import glob
import io
import os
import re
import sys
import zipfile
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
H = os.path.dirname(os.path.abspath(__file__))
B = os.path.dirname(H)
sys.path.insert(0, os.path.dirname(B))
from judge_web_pilot import DISTRUST  # noqa: E402

OUT, DAY, KEY = sys.argv[1], "20261125", 5   # 5명: 사용자 결정 11-25
DONGS = ("성내1동", "성내2동", "성내3동")


def rd(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def answers(pat):
    """Aside 답(CSV)들을 수집ID별 줄 목록으로. 파일마다 마지막 답 표(마지막 머리줄 ~ 다음 ```)만 읽는다.
    앞의 생각 글·예시 표는 버린다(수집_화면만.answered()와 같은 규칙, Codex 4차 11-26)."""
    S = {}
    for p in sorted(glob.glob(pat)):
        with open(p, encoding="utf-8", errors="replace") as f:
            t = f.read()
        pos, last = 0, None
        for line in t.splitlines(True):
            if "수집ID" in line and "찾음" in line:
                last = (pos, line)
            pos += len(line)
        if last:
            pos, line = last
            head = [h.split("(")[0].strip() for h in next(csv.reader([line]))]
            for r in csv.reader(io.StringIO(t[pos + len(line):].split("```")[0])):
                if len(r) == len(head):
                    S.setdefault(r[0].strip(), []).append({k: v.strip() for k, v in zip(head, r)})
    return S


def num(x):
    m = re.search(r"\d+", (x or "").replace(",", ""))
    return int(m.group()) if m else None


W = rd(B + "/웹데이터_중구_v0_20261125.csv")
web = {r["상가업소번호"]: r for r in W}
one = {r["수집ID"] for r in rd(B + "/1_2인분의심/대상목록.csv")}
mine = {r["수집ID"] for r in rd(B + "/3_간단/대상목록.csv")}
team = {r["수집ID"] for r in rd(B + "/3_간단/팀원_한그릇목록.csv")}
old, new = answers(B + "/1_2인분의심/out_*.csv"), answers(B + "/3_간단/out_*.csv")
photo, again = answers(B + "/4_이전판정_사진47/out_*.csv"), answers(B + "/5_이전판정_한그릇17/out_*.csv")   # 11-24 판정만 있던 64곳을 다시 본 것
for x in (photo, again, answers(B + "/6_팀원결과/*/out_*.csv")):   # 팀원이 보내 준 압축은 6_팀원결과/컴퓨터N/에 푼다
    for i, v in x.items():
        new.setdefault(i, v)
hand = {r["수집ID"]: r for r in rd(H + "/옛방식_새기준판정.csv")}
full = lambda r: (r["상호"] + " " + r["지점명"]).strip()  # noqa: E731

J, MENU = [], []
NOTE7 = {"MA010120220812286869": "같은 주소에 바르미스시샤브 동성로점이 있으나 이름이 다름", "MA010120220813545521": "네이버·카카오에서 메뉴를 못 봄"}   # 첫 5곳(7칸 답)은 메모가 없어 로그에서 옮김
BAD_NAME = re.compile(r"음료|콜라|사이다|소주|맥주|공기밥|사리|추가|초등학생|원조 커피|아메리카노")


def menus(i, text, way):
    """'이름 12,000원; 이름 9,000원' → 요리명·가격 줄."""
    for x in re.split(r";", re.sub(r"\((카카오|네이버)[^)]*\)\s*$", "", text or "")):
        x = x.strip()
        m = list(re.finditer(r"(\d{1,3}(?:,\d{3})+|\d{4,6})\s*원?", x))
        if not x:
            continue
        name = re.sub(r"\s*[₩]?\s*\d{1,3}(,\d{3})+\s*원?.*$|\s*\d{4,6}\s*원.*$", "", x).strip() or x
        unit = ("무게" if re.search(r"\d+\s*g", x) else "크기·세트" if re.search(r"[2-9]\s*~?\s*\d?\s*인|\(\s*[소중대]\s*\)|\s[소중대](\s|$)|세트|SET|한\s*판|모[듬둠]|한마리|반마리|[小中大]", x) else "단품")
        MENU.append({"수집ID": i, "상호": full(web[i]), "업종": web[i]["업종_소분류"], "요리명": name, "가격_원": int(m[0].group(1).replace(",", "")) if m else "",
                     "가격_단위": unit, "화면_글자": x[:120], "곁들임일_수_있음": "예" if BAD_NAME.search(name) or re.search(r"냉면|찌개|볶음밥|우동|라면|짜파게티", name) and web[i]["업종_소분류"] in DISTRUST else "",
                     "수집방식": way, "확인일": "2026-11-25"})


def solo(n):
    return "가능(추정)" if n is not None and n >= KEY else "모름"


for i in web:
    w = web[i]
    base = {"수집ID": i, "상호": full(w), "업종": w["업종_소분류"], "행정동": w["행정동"], "도로명주소": w["도로명주소"], "위도": w["위도"], "경도": w["경도"]}
    if i in old:
        d = old[i][0]
        if d["찾음"] != "예":
            r = {"주문": "모름", "N": "", "확실한_정도": "지도에서 못 찾음", "근거문구": "", "따로_확인": ""}
        else:
            h = hand[i]
            r = {"주문": h["주문"], "N": h["N"], "확실한_정도": h["확실한_정도"], "근거문구": h["근거문구"], "따로_확인": h["따로_확인"]}
        n = num(d.get("혼밥키워드수"))
        u = next((x["근거_URL"] for x in old[i] if x["근거_URL"].startswith("http") and "blog" not in x["근거_URL"]), "")
        J.append({**base, **r, "혼자_가도_되나": solo(n), "혼밥하기좋아요_수": "" if n is None else n, "링크": u.split("?")[0], "메모": "", "수집방식": "옛 방식(메뉴·사진·카카오·리뷰)", "확인일": "2026-11-25"})
        if d["찾음"] == "예":
            menus(i, d["대표메뉴"], "옛 방식")
    elif i in new:
        d = new[i][0]
        v, e = d["판정"], d["근거문구"]
        sure = "" if d["찾음"] == "예" else {"애매": "같은 가게인지 애매함"}.get(d["찾음"], "지도에서 못 찾음")
        if d["찾음"] != "예":
            v = "모름"
        elif v == "1인분":
            sure = "확인됨(1인 표기)" if re.search(r"1\s*인\s*(세트|메뉴|정식|상|한상)|혼밥|나홀로|1인분\s*(씩|주문|가능)", e) else "추정(한 사람 몫 요리)"
        elif v == "N인분":
            sure = "확인됨(조건 문구)" if re.search(r"부터|이상|첫\s*주문|최초|기본|최소|단위", e) else "크기·세트뿐"
        else:
            sure = "근거 없음"
        n = num(d["혼밥수"])
        J.append({**base, "주문": v, "N": d["숫자"] if v == "N인분" else "1" if v == "1인분" else "", "확실한_정도": sure, "근거문구": e,
                  "따로_확인": "예" if d["찾음"] == "애매" else "", "혼자_가도_되나": solo(n), "혼밥하기좋아요_수": "" if n is None else n,
                  "링크": d["링크"].split("?")[0], "메모": d.get("메모", "") or NOTE7.get(i, ""), "수집방식": "새 방식(네이버 메뉴+사진)" if i in photo else "새 방식(네이버 메뉴)", "확인일": "2026-11-25"})
        menus(i, d.get("주요요리") or e, "새 방식")


def state(r):
    i = r["상가업소번호"]
    if i in old:
        return "모음(옛 방식)"
    if i in new:
        return "모음(새 방식)"
    if i in mine:
        return "모으는 중(이 컴퓨터)"
    if i in team:
        return "모을 예정(팀원)"
    if r["내부_수집ID"]:
        return "11-24까지의 판정 있음"
    if r["업종_소분류"] in ("피자", "치킨"):
        return "뺌(피자·치킨)"
    return "뺌(술집)" if r["행정동"] in DONGS else "보류(동성로 밖)"


PLACE = [{"수집ID": r["상가업소번호"], "상호": full(r), "도로명주소": r["도로명주소"], "층정보": r["층정보"], "행정동": r["행정동"],
          "동성로": "예" if r["행정동"] in DONGS else "", "위도": r["위도"], "경도": r["경도"]} for r in W]
LIST = [{"수집ID": r["상가업소번호"], "상호": full(r), "업종_중분류": r["업종_중분류"], "업종_소분류": r["업종_소분류"], "행정동": r["행정동"],
         "도로명주소": r["도로명주소"], "위도": r["위도"], "경도": r["경도"], "수집상태": state(r)} for r in W if r["행정동"] in DONGS]
DISH = [{k: m[k] for k in ("수집ID", "상호", "업종", "요리명", "가격_원", "가격_단위", "곁들임일_수_있음", "수집방식", "확인일")} for m in MENU]
PRICE = [m for m in MENU if m["가격_원"] != ""]
c, s = Counter(r["주문"] for r in J), Counter(r["혼자_가도_되나"] for r in J)
found = sum("못 찾음" not in r["확실한_정도"] and "애매" not in r["확실한_정도"] for r in J)
COMMON = f"""
## 알고 쓰기
- **임시본입니다(2026-11-25).** 동성로 수집이 끝나지 않았습니다. 끝나면 같은 이름으로 다시 만듭니다.
- 동성로 = 성내1·2·3동. 가게 목록과 좌표는 소상공인 상가정보(2026-09)이고, 문 닫은 가게가 섞여 있을 수 있습니다.
- `수집ID`가 같으면 같은 가게입니다. 다른 파일과 이 칸으로 붙이세요.
- 지도에서 본 자료라 **비율(%)로 쓰지 않습니다.** 팀 안에서만 쓰고 공개 저장소에 올리지 않습니다.
- 리뷰 글과 작성자 정보는 없습니다.
"""
PACK = [
    ("거리_손효민", f"중구_가게좌표_{DAY}.csv", PLACE, f"""# 거리 에이전트 자료 (손효민)

`중구_가게좌표_{DAY}.csv` — 중구 식당 {len(PLACE):,}곳의 좌표. 동성로 칸이 '예'인 곳 {sum(bool(r['동성로']) for r in PLACE):,}곳.

| 칸 | 뜻 |
|---|---|
| 위도, 경도 | WGS84. 사용자 위치와의 거리 계산에 씀 |
| 층정보 | 상가정보에 있는 층. 빈칸 많음 |
"""),
    ("탐색_이건협", f"동성로_가게목록_{DAY}.csv", LIST, f"""# 탐색 에이전트 자료 (이건협)

`동성로_가게목록_{DAY}.csv` — 동성로 식당 {len(LIST):,}곳.

| 수집상태 | 곳 수 |
|---|---|
""" + "".join(f"| {k} | {v} |\n" for k, v in Counter(r["수집상태"] for r in LIST).most_common()) + """
추천 후보로는 '뺌'을 빼고 쓰면 됩니다(피자·치킨·술집은 팀 결정으로 뺌).
"""),
    ("혼밥편의", f"동성로_1인분판정_{DAY}.csv", J, f"""# 혼밥편의 에이전트 자료

`동성로_1인분판정_{DAY}.csv` — 지금까지 본 {len(J)}곳(같은 가게를 찾은 곳 {found}곳).

| 주문 | 곳 수 | 뜻 |
|---|---|---|
| 1인분 | {c['1인분']} | 주요 요리 중 하나라도 1인분을 시킬 수 있음 |
| N인분 | {c['N인분']} | N인분부터만 됨. N은 1보다 큰 수, '미확인'은 크기·세트뿐이라 수가 안 적힘 |
| 모름 | {c['모름']} | 메뉴를 못 봤거나, 고깃집 등에서 값만 보이거나, 가게를 못 찾음 |

| 칸 | 뜻 |
|---|---|
| 확실한_정도 | 확인됨 = 문구로 적혀 있음. 추정 = 한 사람 몫 요리로 파는 것만 봄. 챗봇에서 둘을 구분해 말할 것 |
| 근거문구 | 메뉴에 적힌 글자 그대로 |
| 따로_확인 | '예'면 사람이 한 번 더 봐야 함 |
| 혼자_가도_되나 | 네이버 '혼밥하기 좋아요' {KEY}명 이상이면 가능(추정)(사용자 결정 11-25). 지금 가능(추정) {s['가능(추정)']}곳 |

**탈락**: 주문이 N인분인 곳. **모름은 탈락시키지 말고** '확인 안 됨'으로 보여 주세요.
옛 방식 {len(old)}곳의 판정은 새 기준(주요 요리)으로 Claude가 다시 붙인 **임시 판정**이고 사람이 확인하지 않았습니다. 좌석(1인석)은 모으지 않았습니다.
"""),
    ("예산", f"동성로_메뉴가격_{DAY}.csv", PRICE, f"""# 예산 에이전트 자료

`동성로_메뉴가격_{DAY}.csv` — 요리 {len(PRICE)}줄, 가게 {len({r['수집ID'] for r in PRICE})}곳.

| 칸 | 뜻 |
|---|---|
| 가격_원 | 화면에 보인 첫 가격(숫자만) |
| 가격_단위 | 단품 / 크기·세트 / 무게. **무게(100g 값 등)와 크기·세트는 한 사람 값이 아닐 수 있음** |
| 곁들임일_수_있음 | '예'면 1인 식사비 계산에서 빼는 것이 좋음 (낱말로 고른 것) |
| 화면_글자 | 원래 적힌 글자. 헷갈리면 이것을 볼 것 |

1인 예산은 **혼밥편의 파일에서 1인분인 가게**의 단품 가격으로 계산하세요. 가격은 바뀔 수 있습니다.
"""),
    ("메뉴", f"동성로_주요요리_{DAY}.csv", DISH, f"""# 메뉴 에이전트 자료

`동성로_주요요리_{DAY}.csv` — 요리 {len(DISH)}줄, 가게 {len({r['수집ID'] for r in DISH})}곳.

- '국밥', '덮밥' 같은 말로 **요리명과 업종**에서 찾으면 됩니다.
- '국물·면·밥·고기' 같은 묶음은 아직 정하지 않아 넣지 않았습니다.
- 옛 방식은 가게가 '대표'로 올린 메뉴라 곁들임(냉면·우동)이 섞여 있습니다. 곁들임일_수_있음 칸을 보세요.
"""),
]
os.makedirs(OUT, exist_ok=True)
for name, fn, rows, md in PACK:
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, fn), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(d, "읽어주세요.md"), "w", encoding="utf-8-sig", newline="\n") as f:
        f.write(md + COMMON)
    with zipfile.ZipFile(os.path.join(OUT, f"{name}_자료_{DAY}.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for x in (fn, "읽어주세요.md"):
            z.write(os.path.join(d, x), f"{name}/{x}")
    print(name, fn, len(rows))
print("주문", dict(c), "혼자", dict(s), "확실", dict(Counter(r["확실한_정도"] for r in J)), "따로", sum(r["따로_확인"] == "예" for r in J))
print("수집상태", dict(Counter(r["수집상태"] for r in LIST)))
