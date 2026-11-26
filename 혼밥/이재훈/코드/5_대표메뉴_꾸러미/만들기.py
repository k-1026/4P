"""혼밥 DB의 가게로 대표 메뉴 수집 묶음(prompt_NNN.txt, 5곳씩)을 만든다.

python -I 만들기.py --out <새 폴더> [--db <혼밥 DB>] [--새것만] [--틀 <지시문 틀>]

- 처음: 이 꾸러미에는 최종본(391곳) 묶음이 이미 들어 있어 돌릴 필요가 없다.
- 최종본이나 매주 갱신으로 가게가 늘면: --새것만 을 붙여 새 폴더에 만든다.
  이미 대표메뉴_결과.csv에 '찾음=예'로 있는 가게는 빼고, 남은 가게만 묶는다.
- 만든 폴더에는 수집.py·수집시작.bat·진행보기도 복사되므로 그 폴더의 수집시작.bat을 누르면 돈다.
- 이미 묶음이나 결과가 있는 폴더에는 만들지 않는다(묶음 번호가 어긋나지 않게).
"""
import argparse
import csv
import glob
import json
import os
import shutil
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
SIZE = 5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(HERE, "혼밥_동성로.db"), help="혼밥 DB 경로(안 주면 꾸러미 안의 최종본)")
    ap.add_argument("--out", required=True, help="묶음을 만들 새 폴더")
    ap.add_argument("--새것만", action="store_true", help="대표메뉴_결과.csv에 이미 있는 가게는 뺌")
    ap.add_argument("--틀", default=os.path.join(HERE, "지시문_틀.txt"), help="지시문 틀 파일(안 주면 지시문_틀.txt)")
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    need = [x for x in ("수집.py", "수집시작.bat", "진행보기.py", "진행보기.bat", "지시문_틀.txt") if not os.path.exists(os.path.join(HERE, x))]
    if need:
        raise SystemExit("꾸러미에 이 파일이 없습니다: " + ", ".join(need))
    if glob.glob(os.path.join(out, "prompt_*.txt")) or glob.glob(os.path.join(out, "out_*.csv")):
        raise SystemExit(f"{out}에 이미 묶음이나 결과가 있습니다. 새 폴더 이름을 주세요.")
    c = sqlite3.connect("file:" + os.path.abspath(a.db) + "?mode=ro", uri=True)
    rows = [list(r) for r in c.execute("SELECT 식당ID, 상호, 도로명주소, COALESCE(업종,''), COALESCE(지도링크,'') FROM 식당 ORDER BY 행정동, 도로명주소, 식당ID")]
    if a.새것만:
        res = os.path.join(HERE, "대표메뉴_결과.csv")
        seen = set()
        if os.path.exists(res):
            with open(res, encoding="utf-8-sig", newline="") as f:
                seen = {r["식당ID"] for r in csv.DictReader(f) if r["찾음"] == "예"}
        rows = [r for r in rows if r[0] not in seen]
    if not rows:
        print("새로 볼 가게가 없습니다.")
        return
    os.makedirs(out, exist_ok=True)
    head = open(os.path.abspath(a.틀), encoding="utf-8").read()
    if not head.endswith("입력:\n"):
        raise SystemExit("지시문 틀은 '입력:' 줄로 끝나야 합니다.")
    with open(os.path.join(out, "대상목록.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["수집ID", "상호", "도로명주소", "업종", "지도링크"])
        w.writerows(rows)
    for n, k in enumerate(range(0, len(rows), SIZE)):
        with open(os.path.join(out, f"prompt_{n:03d}.txt"), "w", encoding="utf-8") as f:
            f.write(head + json.dumps(rows[k:k + SIZE], ensure_ascii=False))
    if out != HERE:
        for x in ("수집.py", "수집시작.bat", "진행보기.py", "진행보기.bat"):
            shutil.copy2(os.path.join(HERE, x), out)
    print(f"{out}: 가게 {len(rows)}곳, 묶음 {-(-len(rows) // SIZE)}개")


if __name__ == "__main__":
    main()
