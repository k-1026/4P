"""혼밥 챗봇 식당 데이터 만들기.

입력 (../식당목록/):
  - 대구푸드_맛집DB_905곳.json              대구시 위생정책과 공공데이터 [출처 10]
  - 대구푸드_메뉴표기_2인이상_1인분.csv      위 DB 메뉴 문구에서 팀이 뽑은 표 [출처 11]
  - 대구달서구_고깃집100곳_최소주문표시_*.csv   다이닝코드 직접 확인 [출처 34]
  - 대구달서구_한식찜쭈꾸미등189곳_*.csv       다이닝코드 직접 확인 [출처 34]
  - 대구달서구_289곳_혼밥대응표시_*.csv        위 289곳 다시 세기 [출처 34]

출력: ../혼밥챗봇_완성본.html (restaurants.json은 중간 파일)

1인분 판정(status)은 팀 자료에 적힌 것만 쓴다. 자료가 없으면 unk(확인 안 됨)다.
  ok    혼자 가능 확인 (1인 메뉴·세트, 혼밥 자리, 혼자면 예외)
  nomin 2인분 조건 못 찾음 (메뉴판·후기·블로그 직접 확인)
  hint  메뉴판에 1인분 표기 (최소 주문은 확인 안 됨)
  part  일부 메뉴만 2인 이상 표기 (나머지는 확인 안 됨)
  unk   1인분 확인 안 됨
  two   2인분 이상 (확인)

새로 모은 식당은 팀 수집양식(이 폴더의 `수집양식_빈양식.csv`와 같은 29열)으로
채워 ../식당목록/ 에 `*수집양식*.csv` 이름으로 넣는다. 파일 수는 상관없다.
이미 있는 가게(같은 구 + 같은 상호)는 수집양식 판정으로 덮어쓰고, 없으면 새로 더한다.
"""
import csv
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "식당목록")
OUT = os.path.join(HERE, "..", "혼밥챗봇_완성본.html")


def rd(pattern):
    """이름 형식에 맞는 파일을 모두 읽어 한 목록으로 합친다."""
    out = []
    for path in sorted(glob.glob(os.path.join(SRC, pattern))):
        with open(path, encoding="utf-8-sig") as f:
            out += list(csv.DictReader(f))
    return out


def col(row, prefix):
    """칸 이름이 '최소주문_판정(…)'처럼 설명을 달고 있어도 앞부분으로 찾는다."""
    for k, v in row.items():
        if k and k.strip().startswith(prefix):
            return (v or "").strip()
    return ""


def norm(name):
    return re.sub(r"[\s·()\[\]-]", "", name or "")


TAGS = [
    ("고기", r"삼겹|갈비|고깃|고기(?!만두)|막창|곱창|한우|돼지|숯불|목살|뒷고기|오리|소금구이|양념구이"),
    ("국밥·탕·찌개", r"국밥|탕(?!수)|해장|찌개|전골|순두부|추어|곰탕|설렁"),
    ("면", r"국수|칼국수|냉면|라멘|라면|우동|짬뽕|짜장|소바|쌀국수|파스타|면"),
    ("백반·정식", r"백반|정식|한상|밥상|쌈밥|비빔밥|덮밥|도시락|솥밥"),
    ("분식", r"떡볶이|김밥|분식|만두|오뎅|어묵|튀김|순대"),
    ("해산물·회", r"(?<!한)회(?!식|덮밥)|회덮밥|해물|아구|쭈꾸미|주꾸미|낙지|생선|초밥|스시|대게|조개|복어"),
    ("찜", r"찜"),
    ("샤브샤브", r"샤브"),
    ("치킨", r"치킨|닭강정"),
    ("돈가스", r"돈가스|돈까스|카츠"),
]
FD_TAG = {"일식": "일식", "중식": "중식", "양식": "양식", "세계요리": "세계요리",
          "디저트/베이커리": "카페·디저트", "전통차/커피전문점": "카페·디저트",
          "퓨전/뷔페": "뷔페", "특별한 술집": "술집", "한식": "한식"}
C189_TAG = {"한식": ["한식"], "쭈꾸미": ["해산물·회"], "닭볶음탕": ["찜", "국밥·탕·찌개"],
            "샤브샤브": ["샤브샤브"], "찜": ["찜"], "아구찜": ["찜", "해산물·회"],
            "찌개": ["국밥·탕·찌개"]}


def tags_from(text):
    return [t for t, pat in TAGS if re.search(pat, text or "")]


def parse_menus(mnu):
    out = []
    for part in re.split(r"<br\s*/?>|/", mnu or ""):
        part = re.sub(r"<[^>]+>", "", part).strip()
        if not part:
            continue
        m = re.search(r"([\d,]{4,})\s*원", part)
        price = int(m.group(1).replace(",", "")) if m else None
        name = re.sub(r"[\d,]{4,}\s*원.*$", "", part).strip(" -~:")
        out.append({"n": name[:40], "p": price})
    return out[:12]


def clean_sbw(t):
    t = re.sub(r"<[^>]+>", " ", t or "").split("  ")[0].strip()
    return "" if (not t or "없" in t[:25]) else t


def min_price(menus):
    side = re.compile(r"추가|사리|공기밥|음료|주류|소주|맥주|토핑|곱빼기")
    ps = [m["p"] for m in menus if m["p"] and m["p"] >= 5000 and not side.search(m["n"])]  # 곁들이 제외
    return min(ps) if ps else None


# ---------- 1) 대구푸드 905곳 ----------
with open(os.path.join(SRC, "대구푸드_맛집DB_905곳.json"), encoding="utf-8") as f:
    food = json.load(f)
mark = {(norm(r["업소명"]), r["주소"].strip()): r for r in rd("대구푸드_메뉴표기_*.csv")}

rows = []
for x in food:
    menus = parse_menus(x["MNU"])
    # 태그는 가게 이름과 앞쪽 메뉴 4개로만 붙인다 (곁들이 메뉴로 넓게 붙는 것을 막음)
    text = x["BZ_NM"] + " " + " ".join(m["n"] for m in menus[:4])
    tags = tags_from(text)
    if FD_TAG.get(x["FD_CS"]):
        tags.append(FD_TAG[x["FD_CS"]])
    r = {
        "id": "F" + x["OPENDATA_ID"], "name": x["BZ_NM"], "gu": x["gu"],
        "addr": x["GNG_CS"], "fd": x["FD_CS"], "tags": sorted(set(tags)),
        "menus": menus, "minP": min_price(menus), "hours": x["MBZ_HR"],
        "seats": x["SEAT_CNT"], "sbw": clean_sbw(x["SBW"]),
        "status": "unk", "why": "대구푸드 DB에 1인분 여부 칸이 없음", "src": "대구푸드 맛집 DB (대구시)",
        "note": "",
    }
    m = mark.get((norm(x["BZ_NM"]), x["GNG_CS"].strip()))
    if m:
        if m["'1인분/1인메뉴' 표기"].strip():
            r["status"], r["why"] = "hint", "메뉴판에 1인분 · 1인 메뉴 표기가 있음 (최소 주문은 확인 안 됨)"
        elif m["'2인 이상' 표기"].strip():
            priced = [mm for mm in menus if mm["p"]]
            if priced and all(re.search(r"2인", mm["n"]) for mm in priced):
                r["status"], r["why"] = "two", "메뉴판의 모든 메뉴가 2인 이상"
            else:
                r["status"], r["why"] = "part", "일부 메뉴만 2인 이상 표기 (다른 메뉴는 확인 안 됨)"
    rows.append(r)

# ---------- 2) 달서구 289곳 (다이닝코드 직접 확인) ----------
solo = {}
for h in rd("대구달서구_289곳_혼밥대응표시_*.csv"):
    solo.setdefault(h["다이닝코드 rid"], []).append(h)

checked = []
for g in rd("대구달서구_고깃집100곳_*.csv"):
    minq = g["주 메뉴 첫 주문 최소량"].strip()
    checked.append({"rid": g["다이닝코드 rid"], "name": g["식당"], "addr": g["주소(도로명 앞부분)"],
                    "tags": ["고기"] + [t for t in tags_from(g["식당"]) if t != "고기"],
                    "menu_ok": g["온라인 메뉴판 있음"] == "예",
                    "two": minq, "two_src": g["최소 주문 근거"]})
for g in rd("대구달서구_한식찜쭈꾸미등189곳_*.csv"):
    kind = g["업종(다이닝코드 검색)"]
    two = g["최소 주문 내용"].strip() or (g["판정"].strip() if g["판정"].strip() else "")
    checked.append({"rid": g["다이닝코드 rid"], "name": g["식당"], "addr": g["주소"],
                    "tags": C189_TAG.get(kind, []) + tags_from(g["식당"]),
                    "menu_ok": g["온라인 메뉴판 있음"] == "예",
                    "two": two, "two_src": g["근거"]})

by_name = {}
for r in rows:
    if r["gu"] == "달서구":
        by_name.setdefault(norm(r["name"]), r)

for c in checked:
    status, why, note = "unk", "다이닝코드에서 판단할 정보가 없음", ""
    if c["two"]:
        status, why = "two", f"2인분 이상: {c['two']}" + (f" ({c['two_src']})" if c["two_src"] else "")
    elif c["menu_ok"]:
        status, why = "nomin", "메뉴판 · 후기 · 블로그에서 2인분 조건을 못 찾음 (직접 확인)"
    for h in solo.get(c["rid"], []):
        kind, txt = h["구분"], h["내용(요약·원문 아님)"]
        if kind in ("1인 메뉴·세트 운영", "혼밥 자리·환영 표시", "혼자면 예외"):
            if status == "two":
                note = (note + " / " if note else "") + why
            status, why = "ok", f"{kind}: {txt} ({h['근거 위치']})"
        elif kind == "혼밥 불가 명시":
            status, why = "two", f"혼밥 불가 명시: {txt} ({h['근거 위치']})"
        elif kind == "시간대에 따라 다름":
            note = (note + " / " if note else "") + f"시간대에 따라 다름: {txt}"
        elif "충돌" in kind:
            note = (note + " / " if note else "") + f"자료끼리 다름: {txt}"
    base = by_name.get(norm(c["name"]))
    if base:  # 대구푸드 DB에도 있는 가게: 메뉴 · 가격은 DB, 판정은 직접 확인
        base.update(status=status, why=why, note=note, src="대구푸드 DB + 다이닝코드 직접 확인")
        base["tags"] = sorted(set(base["tags"] + c["tags"]))
        continue
    rows.append({
        "id": "D" + c["rid"], "name": c["name"], "gu": "달서구",
        "addr": c["addr"] if c["addr"] != "달서구" else "대구광역시 달서구",
        "fd": "", "tags": sorted(set(c["tags"])), "menus": [], "minP": None,
        "hours": "", "seats": "", "sbw": "", "status": status, "why": why,
        "src": "다이닝코드 직접 확인 (2026-11-21)", "note": note,
    })

# ---------- 3) 팀 수집양식으로 새로 모은 식당 (../식당목록/*수집양식*.csv) ----------
GU_ALL = ["중구", "동구", "서구", "남구", "북구", "수성구", "달서구", "달성군"]


def collected_status(c):
    minq, solo = col(c, "최소주문_판정"), col(c, "1인입장_판정")
    scope = col(c, "조건_적용범위")
    kind, where, date = col(c, "근거1_종류"), col(c, "근거1_출처"), col(c, "근거1_작성일")
    ev = " · ".join(x for x in [kind, where, date] if x)
    if kind == "메뉴표기" and col(c, "근거1_원문"):  # 메뉴 문구는 그대로 보여 줘도 된다
        ev = col(c, "근거1_원문")[:40] + (f" ({where})" if where else "")
    tail = f" — 근거: {ev}" if ev else ""
    if solo == "불가":
        return "two", "혼자 입장 불가" + tail
    if minq.startswith("2인분이상"):
        est = " (추정)" if "추정" in minq else ""
        if "일부" in scope:
            return "part", "일부 메뉴만 2인분 이상" + est + tail
        return "two", "2인분 이상" + est + tail
    if minq == "1인분가능_확정" or solo == "가능":
        return "ok", ("1인분 가능 확인" if minq == "1인분가능_확정" else "혼자 입장 가능 확인") + tail
    if minq.startswith("1인분가능"):
        return "nomin", "1인분 가능 (추정)" + tail
    return "unk", "수집했지만 1인분 여부를 판단할 근거 없음"


by_gu_name = {}
for r in rows:
    by_gu_name.setdefault((r["gu"], norm(r["name"])), r)

added = updated = skipped = 0
for c in rd("*수집양식*.csv"):
    name, cid = col(c, "상호"), col(c, "수집ID")
    if not name or cid.startswith("예시"):
        skipped += 1
        continue
    addr = col(c, "도로명주소")
    gu = col(c, "구군") or next((g for g in GU_ALL if g in addr), "")
    status, why = collected_status(c)
    note = col(c, "시간대제한")
    note = f"시간대 제한: {note}" if note else ""
    src = "팀 수집양식" + (f" (확인 {col(c, '확인일')})" if col(c, "확인일") else "")
    text = " ".join([name, col(c, "대표메뉴"), col(c, "상권_업종소분류"), col(c, "인허가_업태")])
    base = by_gu_name.get((gu, norm(name)))
    if base:  # 이미 있는 가게: 판정을 새 자료로 바꾸고, 다르면 이전 판정을 참고로 남긴다
        if base["status"] != status and base["status"] != "unk":
            note = (note + " / " if note else "") + f"이전 자료: {base['why']}"
        base.update(status=status, why=why, note=note, src=base["src"] + " + " + src)
        base["tags"] = sorted(set(base["tags"] + tags_from(text)))
        updated += 1
        continue
    r = {
        "id": "C" + (cid or str(len(rows))), "name": name, "gu": gu,
        "addr": addr or (f"대구광역시 {gu}" if gu else "대구광역시"),
        "fd": "", "tags": sorted(set(tags_from(text))),
        "menus": [{"n": col(c, "대표메뉴")[:40], "p": None}] if col(c, "대표메뉴") else [],
        "minP": None, "hours": "", "seats": "", "sbw": "",
        "status": status, "why": why, "src": src, "note": note,
    }
    rows.append(r)
    by_gu_name[(gu, norm(name))] = r
    added += 1
print(f"수집양식: 새 가게 {added}, 판정 바꾼 가게 {updated}, 건너뛴 줄 {skipped}")

with open(os.path.join(HERE, "restaurants.json"), "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))

from collections import Counter
print(len(rows), Counter(r["status"] for r in rows))
print(Counter(t for r in rows for t in r["tags"]).most_common())

# ---------- 4) 챗봇 HTML 한 장 만들기 ----------
with open(os.path.join(HERE, "챗봇_빈틀.html"), encoding="utf-8") as f:
    html = f.read()
data_js = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
html = html.replace("/*__DATA__*/(window.HONBAP_DATA || [])", data_js)
html = html.replace('<script src="restaurants.js"></script><!--DEV-->\n', "")
with open(os.path.join(HERE, "restaurants.js"), "w", encoding="utf-8") as f:  # 템플릿 미리보기용
    f.write("window.HONBAP_DATA=" + data_js + ";")
with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print("혼밥챗봇_완성본.html", len(html.encode("utf-8")) // 1024, "KB")
