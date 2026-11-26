"""매주 갱신 1단계: 인허가 자료와 지금 동성로 목록·DB를 비교해 '새 가게 후보'와 '폐업한 DB 가게'를 뽑는다.
DB와 원자료는 바꾸지 않는다(목록만 만든다). 2단계(새 가게를 Aside로 판정)·3단계(DB 반영)는 따로.

python -B -I 인허가_비교.py --file <인허가 CSV> [--since 2026-11-26] [--out <폴더>]

인허가 자료: 공공데이터포털 '전국일반음식점표준데이터'(행정안전부_식품_일반음식점, CSV, 매일 갱신·2일 전 기준).
  좌표는 EPSG:5174라 바로 쓰기 어려워서, 동성로는 **도로명주소**로 거른다(대구 중구 + 지금 목록에 나오는 도로명).
  칸 이름은 실제 파일로 확인하지 못해 흔한 이름들을 받아들인다(COLS). 없으면 어떤 칸이 없는지 말하고 멈춘다.
--since를 비우면 지난번 비교일(마지막_비교일.txt), 그것도 없으면 7일 전부터 본다.
"""
import argparse
import csv
import datetime
import difflib
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from 좌표 import meters, to_wgs84  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10 ** 7)
HERE = os.path.dirname(os.path.abspath(__file__))
DBDIR = os.path.dirname(HERE)
B = os.path.join(os.path.dirname(DBDIR), "매칭도구", "작업기록_20261125_중구동성로")
LAST = os.path.join(HERE, "마지막_비교일.txt")

COLS = {   # 우리 이름: 받아들이는 칸 이름들
    "관리번호": ("관리번호", "MNG_NO", "mgtNo"),
    "사업장명": ("사업장명", "BPLC_NM", "bplcNm"),
    "인허가일자": ("인허가일자", "LCPMT_YMD", "apvPermYmd"),
    "영업상태명": ("영업상태명", "SALS_STTS_NM", "trdStateNm"),
    "폐업일자": ("폐업일자", "CLSBIZ_YMD", "dcbYmd"),
    "도로명주소": ("도로명전체주소", "소재지도로명주소", "도로명주소", "ROAD_NM_ADDR", "rdnWhlAddr"),
    "지번주소": ("소재지전체주소", "소재지지번주소", "지번주소", "LOTNO_ADDR", "siteWhlAddr"),
    "업태구분명": ("업태구분명", "BZSTAT_SE_NM", "uptaeNm"),
    "X": ("좌표정보(X)", "좌표정보(x)", "좌표정보x(epsg5174)", "CRD_INFO_X", "x"),
    "Y": ("좌표정보(Y)", "좌표정보(y)", "좌표정보y(epsg5174)", "CRD_INFO_Y", "y"),
}
NEED = ("사업장명", "인허가일자", "영업상태명", "도로명주소")
# 지금 대상에서 뺀 업종과 맞춘다(피자·치킨·술집·카페). 실제 파일의 업태 이름을 보고 다시 맞춘다.
SKIP_KIND = re.compile(r"호프|통닭|치킨|정종|대포집|소주방|감성주점|라이브|룸살롱|단란|유흥|까페|카페|키즈|피자")
OPEN = re.compile(r"영업|정상")
NEAR = 150   # 가장 가까운 동성로 목록 가게가 이보다 멀면 동성로 밖으로 본다(m)
CLOSED = re.compile(r"폐업|취소|말소")


def day(x):
    """'2026-11-24', '20261124', '2026.11.24' → '2026-11-24'. 못 읽으면 ''."""
    d = re.sub(r"\D", "", x or "")[:8]
    return f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 else ""


def addr_key(a):
    """'대구광역시 중구 동성로1길 65, 2층 (삼덕동1가)' → ('동성로1길', '65'). 못 읽으면 None."""
    a = re.split(r"[,(]", a or "")[0]
    m = re.search(r"중구\s+(\S+(?:로|길))\s*(\d+(?:-\d+)?)", a)
    return (m.group(1), m.group(2)) if m else None


def name_key(n):
    return re.sub(r"[\s()（）\[\]·.,'\"-]|주식회사|\(주\)", "", n or "").lower()


# 띄어쓰지 않고 붙은 지점명: 동성로 근처 지명 + 점, 또는 본점·직영점·N호점만 뗀다('교동반점'의 '반점' 같은 상호는 남김)
BRANCH = re.compile(r"(?:(?:대구)?(?:동성로|중앙로|반월당|대구역|삼덕|종로|대봉|중구|동인|서문시장|경대병원|더현대|현대백화점|대백|롯데|동아|대구)(?:\d+호)?점"
                    r"|본점|직영점|\d+호점)$")


def base_name(raw):
    """지점명을 뗀 이름 열쇠. 띄어 쓴 마지막 낱말이 '…점'이면 그 낱말을 떼고, 붙어 있으면 BRANCH만 뗀다(Codex 2차 11-26)."""
    parts = re.sub(r"\(.*?\)|（.*?）|\[.*?\]", " ", raw or "").split()
    if len(parts) > 1 and re.fullmatch(r"[가-힣A-Za-z0-9]{1,8}점", parts[-1]) and not parts[-1].endswith("반점"):
        parts = parts[:-1]
    k = name_key(" ".join(parts))
    return BRANCH.sub("", k) or k


def same_name(a, b):
    """같은 가게 이름인지. 띄어쓰기·지점명('동성로점')은 무시. 글자 순서가 다르거나 일부만 겹치면 다른 가게로 본다(Codex 검토 11-26)."""
    ra, rb = a, b
    a, b = name_key(a), name_key(b)
    if not (a and b):
        return False
    if a == b:
        return True
    ba, bb = base_name(ra), base_name(rb)
    if ba == bb:
        return True
    short, long_ = sorted((ba, bb), key=len)
    if len(short) >= 3 and long_.startswith(short):   # '규카츠정' / '규카츠정본관'처럼 앞이 같을 때만
        return True
    # 오타·띄어쓰기 차이 정도만 같은 가게로(글자 순서가 다른 '전주식당/주전식당'은 다름)
    return min(len(ba), len(bb)) >= 4 and difflib.SequenceMatcher(None, ba, bb).ratio() >= 0.9


def known_list():
    """지금 동성로 목록 1,348곳(뺀 가게 포함)을 make_packs로 만들어 읽는다. 원자료는 읽기만 함."""
    tmp = tempfile.mkdtemp()
    try:
        p = subprocess.run([sys.executable, "-B", "-I", os.path.join(B, "에이전트자료", "make_packs.py"), tmp],
                           cwd=os.path.join(B, "에이전트자료"), capture_output=True, text=True, encoding="utf-8")
        if p.returncode:
            raise SystemExit("목록 만들기 실패: " + p.stderr[-400:])
        with open(os.path.join(tmp, "탐색_이건협", "동성로_가게목록_20261125.csv"), encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def db_shops(path):
    if not os.path.exists(path):
        return []
    c = sqlite3.connect("file:" + path + "?mode=ro", uri=True)
    try:
        return [dict(zip(("식당ID", "상호", "도로명주소"), r)) for r in c.execute("SELECT 식당ID, 상호, 도로명주소 FROM 식당")]
    finally:
        c.close()


def open_rows(path):
    """인코딩(UTF-8 / CP949)을 알아서 읽고, 칸 이름을 우리 이름으로 맞춰 한 줄씩 돌려준다."""
    for enc in ("utf-8-sig", "cp949"):
        try:
            f = open(path, encoding=enc, newline="")
            head = next(csv.reader([f.readline()]))
            break
        except UnicodeDecodeError:
            f.close()
    else:
        raise SystemExit("파일 인코딩을 읽지 못함")
    head = [h.strip() for h in head]
    pick = {k: next((h for h in v if h in head), None) for k, v in COLS.items()}
    miss = [k for k in NEED if not pick[k]]
    if miss:
        raise SystemExit(f"칸을 못 찾음: {miss}. 파일의 칸 이름: {head[:40]}")
    idx = {k: head.index(h) for k, h in pick.items() if h}
    for row in csv.reader(f):
        yield {k: (row[i].strip() if i < len(row) else "") for k, i in idx.items()}
    f.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--since", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--db", default=os.path.join(DBDIR, "혼밥_동성로.db"))
    ap.add_argument("--list", default="", help="시험용: 목록 CSV를 직접 줌(비우면 make_packs로 만듦)")
    a = ap.parse_args()
    today = datetime.date.today()
    since = day(a.since) or (open(LAST, encoding="utf-8").read().strip() if os.path.exists(LAST) else "") or (today - datetime.timedelta(days=7)).isoformat()
    out = a.out or os.path.join(HERE, today.strftime("%Y%m%d"))
    os.makedirs(out, exist_ok=True)

    if a.list:
        with open(a.list, encoding="utf-8-sig", newline="") as f:
            L = list(csv.DictReader(f))
    else:
        L = known_list()
    roads = {k[0] for k in (addr_key(r["도로명주소"]) for r in L) if k}
    by_addr = {}
    for r in L:
        by_addr.setdefault(addr_key(r["도로명주소"]), []).append(r)
    pts = [(float(r["위도"]), float(r["경도"]), r.get("행정동", "")) for r in L if r.get("위도") and r.get("경도")]
    db = db_shops(a.db)
    db_addr = {}
    for s in db:
        db_addr.setdefault(addr_key(s["도로명주소"]), []).append(s)

    new, closed, seen = [], [], Counter()
    for r in open_rows(a.file):
        seen["읽은 줄"] += 1
        addr = r.get("도로명주소", "")
        if "대구" not in addr or "중구" not in addr:
            continue
        k = addr_key(addr)
        if not k or k[0] not in roads:
            continue
        seen["동성로 도로"] += 1
        state, kind = r.get("영업상태명", ""), r.get("업태구분명", "")
        if CLOSED.search(state):
            for s in db_addr.get(k, []):
                if same_name(s["상호"], r["사업장명"]):
                    closed.append({"식당ID": s["식당ID"], "DB상호": s["상호"], "인허가상호": r["사업장명"], "폐업일자": day(r.get("폐업일자", "")),
                                   "주소": addr, "관리번호": r.get("관리번호", ""), "확인": "상호·주소 같음"})
            continue
        if not OPEN.search(state) or day(r["인허가일자"]) < since:
            continue
        seen["기간 안 새 인허가"] += 1
        if SKIP_KIND.search(kind):
            seen["뺀 업태(술집·치킨·카페 등)"] += 1
            continue
        old = [x for x in by_addr.get(k, []) + db_addr.get(k, []) if same_name(x["상호"], r["사업장명"])]
        if old:
            seen["이미 목록에 있음"] += 1
            continue
        p = to_wgs84(r.get("X"), r.get("Y"))
        far, dong = None, ""
        if p and pts:
            far, dong = min((meters(p, q[:2]), q[2]) for q in pts)
            if far > NEAR:
                seen["동성로 밖(좌표)"] += 1
                continue
        other = [x["상호"] for x in by_addr.get(k, [])]
        memo = ["같은 주소의 다른 가게가 바뀌었을 수 있음"] if other else []
        if not p:
            memo.append("좌표 없음(DB에 넣으려면 좌표가 필요)")
        new.append({"관리번호": r.get("관리번호", ""), "사업장명": r["사업장명"], "인허가일자": day(r["인허가일자"]), "업태": kind,
                    "도로명주소": addr, "위도": f"{p[0]:.7f}" if p else "", "경도": f"{p[1]:.7f}" if p else "", "행정동_추정": dong,
                    "가장가까운_목록가게_m": f"{far:.0f}" if far is not None else "", "같은주소_기존가게": "; ".join(other), "메모": "; ".join(memo)})

    def put(name, rows, head):
        with open(os.path.join(out, name), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=head, quoting=csv.QUOTE_ALL)
            w.writeheader()
            w.writerows(rows)

    put("새가게_후보.csv", new, ["관리번호", "사업장명", "인허가일자", "업태", "도로명주소", "위도", "경도", "행정동_추정", "가장가까운_목록가게_m", "같은주소_기존가게", "메모"])
    put("폐업_DB가게.csv", closed, ["식당ID", "DB상호", "인허가상호", "폐업일자", "주소", "관리번호", "확인"])
    if not a.list:   # 시험이 아닐 때만 비교일을 남긴다
        with open(LAST, "w", encoding="utf-8") as f:
            f.write(today.isoformat())
    print(f"기준일 {since} 이후 | 읽은 줄 {seen['읽은 줄']:,} | 동성로 도로 {seen['동성로 도로']:,} | 새 인허가 {seen['기간 안 새 인허가']}"
          f" → 뺀 업태 {seen['뺀 업태(술집·치킨·카페 등)']}, 이미 있음 {seen['이미 목록에 있음']}, 동성로 밖 {seen['동성로 밖(좌표)']}, **새 가게 후보 {len(new)}** | 폐업한 DB 가게 {len(closed)}")
    print("결과:", out)


if __name__ == "__main__":
    main()
