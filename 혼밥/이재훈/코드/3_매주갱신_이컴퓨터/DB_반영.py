"""매주 갱신 3단계: 2단계(Aside) 결과와 폐업 목록을 누적 파일에 적고, DB를 다시 만든다.

python -B -I DB_반영.py [--dir <갱신/YYYYMMDD>]

- 넣는 조건은 처음 DB와 같다: 같은 가게를 찾음 + 1인분 + '혼밥하기 좋아요' 5명 이상 + 좌표 있음.
- 통과한 가게 → 누적_추가.csv / 폐업한 DB 가게 → 누적_폐업.csv. 두 파일은 make_db.py가 DB를 만들 때마다 읽으므로,
  수집 결과로 DB를 다시 만들어도 갱신 내용이 사라지지 않는다.
- 통과하지 못한 새 가게는 대기목록_갱신.csv에 이유와 함께 쌓는다.
- 1인분인데 혼밥 후기만 모자란 새 가게는 판정 결과를 후기대기_새가게.csv에 남긴다. 후기_다시보기.py가 2·4·8주 뒤 다시 보고, 넘으면 누적_추가로 옮긴다.
- 같은 날 두 번 돌려도 같은 가게가 두 번 들어가지 않는다.
"""
import argparse
import csv
import datetime
import glob
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DBDIR = os.path.dirname(HERE)
sys.path.insert(0, DBDIR)
from make_db import KEY  # noqa: E402

ADD = os.path.join(HERE, "누적_추가.csv")
GONE = os.path.join(HERE, "누적_폐업.csv")
WAIT = os.path.join(HERE, "대기목록_갱신.csv")
LATER = os.path.join(HERE, "후기대기_새가게.csv")   # 1인분인데 혼밥 후기가 모자란 새 가게: 후기_다시보기.py가 2·4·8주 뒤 다시 봄
ADD_HEAD = ["식당ID", "관리번호", "상호", "업종", "행정동", "도로명주소", "위도", "경도", "지도링크", "지도가게번호", "본날",
            "근거문구", "일인메뉴명", "일인메뉴가격", "출처", "혼밥수", "주요요리", "메모"]
GONE_HEAD = ["식당ID", "상호", "폐업일자", "관리번호", "반영일"]
WAIT_HEAD = ["관리번호", "상호", "도로명주소", "들어가지_못한_이유", "본날", "찾음", "판정", "혼밥수", "링크"]


def rd(p):
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def append(p, head, rows):
    new = not os.path.exists(p)
    with open(p, "a", encoding="utf-8-sig" if new else "utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=head, quoting=csv.QUOTE_ALL)
        if new:
            w.writeheader()
        w.writerows(rows)


def answers(folder):
    """Aside 답 파일들에서 수집ID별 줄(9칸). 파일마다 마지막 답 표만 읽고 앞의 생각 글·예시 표는 버린다(Codex 4차 11-26)."""
    got = {}
    for p in sorted(glob.glob(os.path.join(folder, "out_*.csv"))):
        t = open(p, encoding="utf-8-sig", errors="replace").read()
        i = t.rfind("수집ID")
        if i < 0:
            continue
        if t[i - 1:i] == '"':
            i -= 1
        for r in csv.reader(io.StringIO(t[i:].split("```")[0])):
            if len(r) >= 9 and r[0] != "수집ID" and r[1] in ("예", "애매", "아니오"):
                got[r[0]] = dict(zip(["수집ID", "찾음", "판정", "숫자", "근거문구", "주요요리", "혼밥수", "링크", "메모"], r[:9]))
    return got


def place(link):
    m = re.search(r"map\.naver\.com/.*?place/(\d+)", link) or re.search(r"pcmap\.place\.naver\.com/\w+/(\d+)", link)
    if m:
        return "N" + m.group(1)
    m = re.search(r"place\.map\.kakao\.com/(\d+)", link)
    return "K" + m.group(1) if m else ""


def dishes(text):
    """'닭칼국수 9,500원; 삼계칼국수 12,000원' → [('닭칼국수', 9500), ...]"""
    out = []
    for part in re.split(r"[;；]", text or ""):
        m = re.search(r"^\s*(.+?)\s*((?:\d{1,3}(?:,\d{3})+)|\d{3,6})\s*원?\s*$", part)
        if m:
            out.append((m.group(1).strip(), int(m.group(2).replace(",", ""))))
        elif part.strip():
            out.append((part.strip(), None))
    return out


def source(memo):
    if "카카오" in memo:
        return "카카오메뉴"
    if "사진" in memo and "사진 없음" not in memo:
        return "메뉴사진"
    return "메뉴글"


def row(sid, i, c, r, n, today):
    """누적_추가.csv 한 줄(새 가게 하나)."""
    ds_ = dishes(r["주요요리"])
    flat = re.sub(r"\s", "", r["근거문구"])
    hit = [x for x in ds_ if re.sub(r"\s", "", x[0]) in flat]
    name, price = max(hit, key=lambda x: len(x[0])) if hit else (None, None)
    return {"식당ID": sid, "관리번호": i, "상호": c["사업장명"], "업종": c["업태"], "행정동": c.get("행정동_추정", ""),
            "도로명주소": c["도로명주소"].split(",")[0].split("(")[0].strip(), "위도": c["위도"], "경도": c["경도"],
            "지도링크": r["링크"], "지도가게번호": place(r["링크"]), "본날": today, "근거문구": r["근거문구"],
            "일인메뉴명": name or "", "일인메뉴가격": price or "", "출처": source(r["메모"]), "혼밥수": n,
            "주요요리": r["주요요리"], "메모": r["메모"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="")
    ap.add_argument("--다시만들기안함", action="store_true", help="시험용: 누적 파일만 쓰고 DB는 다시 만들지 않음")
    a = ap.parse_args()
    if a.dir:
        d = os.path.abspath(a.dir)
    else:
        ds = sorted(x for x in glob.glob(os.path.join(HERE, "20[2-9][0-9]*")) if os.path.isdir(x))
        if not ds:
            raise SystemExit("갱신 폴더가 없음")
        d = ds[-1]
    today = datetime.date.today().isoformat()
    cand = {r["관리번호"]: r for r in rd(os.path.join(d, "새가게_후보.csv"))}
    got = answers(os.path.join(d, "판정"))
    have = {r["식당ID"] for r in rd(ADD)}
    gone = {r["식당ID"] for r in rd(GONE)}
    waited = {(r["관리번호"], r["본날"]) for r in rd(WAIT)}
    later = {r["관리번호"] for r in rd(LATER)}
    add, wait, miss, keep_later = [], [], [], []
    for i, c in cand.items():
        r = got.get(i)
        if not r:
            miss.append(c["사업장명"])
            continue
        n = int(r["혼밥수"]) if r["혼밥수"].isdigit() else None
        why = ("지도에서 못 찾음" if r["찾음"] == "아니오" else "같은 가게인지 애매" if r["찾음"] != "예"
               else "N인분" if r["판정"] == "N인분" else "1인분 확인 안 됨" if r["판정"] != "1인분"
               else f"혼밥 후기 {r['혼밥수'] or '없음'}(기준 {KEY}명)" if n is None or n < KEY
               else "좌표 없음" if not (c.get("위도") and c.get("경도")) else "")
        sid = "L" + re.sub(r"[^0-9A-Za-z]", "", i)
        if why.startswith("혼밥 후기") and c.get("위도") and c.get("경도") and i not in later and sid not in have:
            keep_later.append(row(sid, i, c, r, n, today))
        if why:
            if (i, today) not in waited:
                wait.append({"관리번호": i, "상호": c["사업장명"], "도로명주소": c["도로명주소"], "들어가지_못한_이유": why, "본날": today,
                             "찾음": r["찾음"], "판정": r["판정"], "혼밥수": r["혼밥수"], "링크": r["링크"]})
            continue
        if sid in have:
            continue
        add.append(row(sid, i, c, r, n, today))
    closed = [{"식당ID": x["식당ID"], "상호": x["DB상호"], "폐업일자": x["폐업일자"], "관리번호": x["관리번호"], "반영일": today}
              for x in rd(os.path.join(d, "폐업_DB가게.csv")) if x["식당ID"] not in gone]
    append(ADD, ADD_HEAD, add)
    append(GONE, GONE_HEAD, closed)
    append(WAIT, WAIT_HEAD, wait)
    append(LATER, ADD_HEAD, keep_later)
    print(f"{os.path.basename(d)}: 새 가게 {len(cand)}곳 중 DB에 넣음 {len(add)}, 대기 {len(wait)}, 아직 판정 없음 {len(miss)} | 폐업으로 뺌 {len(closed)}")
    if miss:
        print("  판정 없음:", ", ".join(miss[:10]))
    if a.다시만들기안함:
        return 3 if miss else 0
    for s in ("make_db.py", "test_db.py"):
        p = subprocess.run([sys.executable, "-B", "-I", os.path.join(DBDIR, s)], cwd=DBDIR, capture_output=True, text=True, encoding="utf-8")
        print(p.stdout.strip().splitlines()[-1] if p.stdout.strip() else "", p.stderr[-300:])
        if p.returncode:
            print(s, "실패")
            return 1
    if miss:   # 판정이 빠진 가게가 있으면 실패로 끝내서 매주_갱신이 비교일을 되돌리게 한다(다음에 다시 봄)
        print(f"판정이 없는 가게 {len(miss)}곳이 있어 실패로 끝냄(다음 실행에서 다시 봄)")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
