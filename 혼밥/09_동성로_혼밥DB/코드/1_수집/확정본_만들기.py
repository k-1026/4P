"""동성로 확정본(임시)을 만든다. 식당이 아닌 12곳(뺀가게_식당아님)을 빼고 1,152곳을 한 줄씩 적는다. 겹침은 합치지 않고 후보로만 적는다.
혼밥 판정은 에이전트자료/혼밥판정.py(사용자 결정 11-25)로 붙인다.

python -B -I 확정본_만들기.py <make_packs 출력 폴더> <결과 CSV>
원자료는 읽기만 한다. 먼저 에이전트자료/make_packs.py를 같은 폴더로 돌린다.
"""
import csv
import os
import re
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")
PACK, OUT = sys.argv[1:3]
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(H))
sys.path.insert(0, os.path.join(H, "에이전트자료"))
from judge_web_pilot import DISTRUST  # noqa: E402
from 혼밥판정 import KEY, decide  # noqa: E402


def rd(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# 검토판 3번: 12곳은 사용자가 빼기로 정했다(뺀가게_식당아님 파일). 나머지는 후보로만 적는다.
GONE = {r["수집ID"] for n in ("뺀가게_식당아님_20261125.csv", "뺀가게_지도에술집_20261125.csv", "뺀가게_사용자결정_20261126.csv") for r in rd(os.path.join(H, n))}
DROP = [(r"하삼동커피", "업종이 카페"), (r"카페노리터", "보드게임카페"), (r"따끈따끈베이커리", "제과점"), (r"사케미", "카카오 분류 술집"),
        (r"메가박스", "영화관"), (r"대구경북영화영상사회적협동조합", "영화관 주소"), (r"세라젬웰카페", "제품 체험 카페"), (r"^와플$", "디저트"),
        (r"과일N디저트", "디저트"), (r"달롱도르", "요거트 아이스크림"), (r"케이디티컴퍼니", "지도에 기업, 메뉴 없음")]
ASK = [(r"닦발집", "술집인지 사용자 결정"),
       (r"크로바|누하스라운지", "술집일 수 있음"), (r"말랑블링룸카페|길카페|영플라워카페|카페골덴|카페든", "카페일 수 있음"),
       (r"위버멘쉬에프앤비|정답에프앤비|상한에프앤비|신디푸드|^진컴퍼니|버블믹컴퍼니|씨앤코컴퍼니|카르멜", "사업자 이름 같음")]


def mark(name):
    for rules, word in ((DROP, "뺄 후보"), (ASK, "확인 필요")):
        for pat, why in rules:
            if re.search(pat, name):
                return f"{word}: {why}"
    return ""


# naver.me 짧은 링크 → 네이버 가게 번호 (11-26 짧은 링크가 넘어가는 주소로 풀어 둠). 같은 가게를 합치고 정식 링크로 바꾸는 데 쓴다
SHORT = {}
if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "짧은링크_가게번호.csv")):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "짧은링크_가게번호.csv"), encoding="utf-8-sig", newline="") as f:
        SHORT = {r["짧은링크"].strip().strip('"').strip(): r["가게번호"] for r in csv.DictReader(f) if r["가게번호"]}


def clean(link):
    return (link or "").strip().strip('"').strip()


def full_link(link):
    """짧은 링크를 풀 수 있으면 정식 네이버 지도 주소로."""
    k = SHORT.get(clean(link), "")
    return f"https://map.naver.com/p/entry/place/{k[1:]}" if k else (link or "")


def place(link):
    if clean(link) in SHORT:
        return SHORT[clean(link)]
    m = re.search(r"map\.naver\.com/.*?place/(\d+)", link) or re.search(r"pcmap\.place\.naver\.com/\w+/(\d+)", link)
    if m:
        return "N" + m.group(1)
    m = re.search(r"place\.map\.kakao\.com/(\d+)", link)
    if m:
        return "K" + m.group(1)
    return "짧은 주소" if "naver.me" in link or "kko." in link else ("모름" if link else "")


L = [r for r in rd(PACK + "/탐색_이건협/동성로_가게목록_20261125.csv") if not r["수집상태"].startswith("뺌") and r["수집ID"] not in GONE]
J = {r["수집ID"]: r for r in rd(PACK + "/혼밥편의/동성로_1인분판정_20261125.csv")}
M = defaultdict(list)
for m in rd(PACK + "/메뉴/동성로_주요요리_20261125.csv"):
    M[m["수집ID"]].append(m)

same = defaultdict(list)
for r in L:
    same[(re.sub(r"\s", "", r["상호"]), r["도로명주소"])].append(r["수집ID"])
pid = defaultdict(list)
for i, j in J.items():
    if re.match(r"[NK]\d", place(j["링크"])):
        pid[place(j["링크"])].append(i)

rows = []
for r in L:
    i, j = r["수집ID"], J.get(r["수집ID"], {})
    tw = [x for x in same[(re.sub(r"\s", "", r["상호"]), r["도로명주소"])] if x != i]
    key = place(j.get("링크", ""))
    sure = j.get("확실한_정도", "")
    found = "" if not j else "아니오" if "못 찾음" in sure else "애매" if "애매" in sure else "예"
    flag = []
    s = j.get("혼밥하기좋아요_수", "")
    order, n, level, verdict, why = "", "", sure, "", ""
    if j:
        order, n, level, verdict, why, flag = decide(found, j["주문"], j["N"], sure, j["근거문구"], int(s) if s.isdigit() else None, M[i])
    if j.get("따로_확인") == "예":
        flag.append("수집 때 표시")
    if order == "1인분" and level.startswith("추정") and r["업종_소분류"] in DISTRUST:
        flag.append("고깃집·횟집 등인데 1인분 추정")
    if re.search(r"이자카야|요리\s*주점|술집|주점", j.get("메모", "")):
        flag.append("지도에 술집으로 적힘")
    rows.append({
        "수집ID": i, "상호": r["상호"], "업종": r["업종_소분류"], "행정동": r["행정동"], "도로명주소": r["도로명주소"], "위도": r["위도"], "경도": r["경도"],
        "수집상태": r["수집상태"], "찾음": found, "혼밥판정": verdict, "판정이유": why, "주문": order, "N": n, "확실한_정도": level, "근거문구": j.get("근거문구", ""),
        "혼밥하기좋아요_수": j.get("혼밥하기좋아요_수", ""),
        "주요요리_가격": "; ".join(f"{m['요리명']} {m['가격_원']}({m['가격_단위']}{', 곁들임일 수 있음' if m['곁들임일_수_있음'] else ''})" for m in M[i]),
        "링크": full_link(j.get("링크", "")), "지도가게번호": key, "메모": j.get("메모", ""), "수집방식": j.get("수집방식", ""), "확인일": j.get("확인일", ""),
        "겹침후보": "; ".join(["상호·주소 같음 " + x for x in tw] + ["지도 가게 같음 " + x for x in pid.get(key, []) if x != i]),
        "목록후보": mark(r["상호"]), "따로_볼_이유": "; ".join(flag), "사람확인": "", "확인자": ""})

with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]), quoting=csv.QUOTE_ALL)
    w.writeheader()
    w.writerows(rows)

bad = []
for x in rows:
    seen = bool(x["주문"])
    lat, lon = float(x["위도"] or 0), float(x["경도"] or 0)
    if not (35.84 < lat < 35.89 and 128.57 < lon < 128.62):
        bad.append((x["상호"], "좌표가 동성로 밖", f"{lat:.4f},{lon:.4f}"))
    if x["주문"] == "1인분" and (x["N"] != "1" or not x["근거문구"]):
        bad.append((x["상호"], "1인분인데 N이 1이 아니거나 근거 없음", x["N"]))
    if x["주문"] == "N인분" and (not (x["N"] == "미확인" or x["N"].isdigit() and int(x["N"]) > 1) or not x["근거문구"]):
        bad.append((x["상호"], "N인분인데 N이 이상하거나 근거 없음", x["N"]))
    if x["주문"] == "모름" and x["N"]:
        bad.append((x["상호"], "모름인데 N이 있음", x["N"]))
    if x["주문"] in ("1인분", "N인분") and x["찾음"] != "예":
        bad.append((x["상호"], "가게를 못 찾았는데 판정이 있음", x["찾음"]))
    if x["찾음"] == "예" and not x["링크"]:
        bad.append((x["상호"], "찾았는데 링크 없음", x["수집방식"]))
    if seen != (x["수집상태"].startswith("모음(")):
        bad.append((x["상호"], "수집상태와 판정이 안 맞음", x["수집상태"]))
ids = [x["수집ID"] for x in rows]
print("줄", len(rows), "겹친 ID", len(ids) - len(set(ids)), "지도 링크 종류", dict(Counter(re.sub(r"\d+", "", x["지도가게번호"]) for x in rows if x["찾음"] == "예")))
print("주문", dict(Counter(x["주문"] or "아직 안 봄" for x in rows)))
print("겹침후보", sum(bool(x["겹침후보"]) for x in rows), "목록후보", dict(Counter(x["목록후보"].split(":")[0] for x in rows)), "따로 볼", dict(Counter(f for x in rows for f in x["따로_볼_이유"].split("; ") if f)))
print("점검에서 걸린 것", len(bad), dict(Counter(b[1] for b in bad)))
for b in bad[:40]:
    print("  ", *b, sep=" | ")
