"""혼밥 점수(10점 만점) 계산 — 혼밥 에이전트가 조율자에게 주는 점수 (11-26 결정).

혼밥점수 = 후기점수(최대 8) + 일인석점수(2 또는 0)
- 후기점수: 앱이 넘겨준 가게들(보통 위치 기반 20곳)을 네이버 '혼밥하기 좋아요' 수로 줄 세워 8칸으로 나눈다.
  1등 칸 8점 … 꼴찌 칸 1점. 수가 같으면 같은 순위·같은 점수. 식: 올림(8 × (가게수 − 순위 + 1) ÷ 가게수)
  20곳이면 1~3등 8, 4~5등 7, 6~8등 6, 9~10등 5, 11~13등 4, 14~15등 3, 16~18등 2, 19~20등 1.
- 일인석점수: 1인석·바 좌석이 혼밥일기나 네이버 정보 탭에서 '있음'으로 확인되면 2점, 아니면(없음·모름) 0점.
- 점수는 DB에 저장하지 않는다. 같은 가게라도 함께 넘어온 가게들에 따라 점수가 달라진다.

파이썬에서
    import sqlite3, 혼밥점수
    con = sqlite3.connect("혼밥_동성로.db")
    결과, 없는가게 = 혼밥점수.score(con, ["MA0101...", "MA0101...", ...])   # 결과는 혼밥점수 높은 순

명령 창에서(시험용)
    python -I 혼밥점수.py MA0101... MA0101...          식당ID들로
    python -I 혼밥점수.py --위치 35.8690 128.5955       그 자리에서 가까운 20곳으로
"""
import argparse
import math
import os
import sqlite3
import sys

TOP, SEAT = 8, 2   # 후기점수 만점, 1인석 점수
HERE = os.path.dirname(os.path.abspath(__file__))


def review_points(counts):
    """혼밥하기 좋아요 수 목록 → 같은 순서의 (순위, 후기점수) 목록. 순위는 자기보다 많은 가게 수 + 1."""
    n = len(counts)
    out = []
    for c in counts:
        rank = 1 + sum(1 for x in counts if x > c)
        out.append((rank, -(-TOP * (n - rank + 1) // n)))   # 정수 올림
    return out


def score(con, ids):
    """식당ID 목록 → (점수 목록, DB에 없는 식당ID 목록). 점수 목록은 혼밥점수 높은 순(같으면 후기 수 많은 순)."""
    ids = list(dict.fromkeys(i for i in ids if i))   # 겹친 ID 한 번만
    if not ids:
        return [], []
    q = ",".join("?" * len(ids))
    rows = con.execute(f"SELECT 식당ID, 상호, 혼밥후기수, 일인석, 일인석출처, 위도, 경도 FROM 혼밥가게 WHERE 식당ID IN ({q})", ids).fetchall()
    found = {r[0] for r in rows}
    rows = [r for r in rows if r[2] is not None]
    pts = review_points([r[2] for r in rows])
    out = []
    for r, (rank, p) in zip(rows, pts):
        seat = SEAT if r[3] == "있음" else 0
        out.append({"식당ID": r[0], "상호": r[1], "혼밥후기수": r[2], "순위": rank, "가게수": len(rows), "후기점수": p,
                    "일인석": r[3] or "모름", "일인석출처": r[4] or "", "일인석점수": seat, "혼밥점수": p + seat})
    out.sort(key=lambda x: (-x["혼밥점수"], -x["혼밥후기수"], x["식당ID"]))
    return out, [i for i in ids if i not in found]


def nearest(con, lat, lon, k=20):
    """시험용: 한 자리에서 가까운 k곳의 식당ID (앱의 위치 기반 목록을 흉내 냄)."""
    d = lambda a, b: math.hypot(math.radians(a - lat), math.radians(b - lon) * math.cos(math.radians(lat)))  # noqa: E731
    rows = con.execute("SELECT 식당ID, 위도, 경도 FROM 식당").fetchall()
    return [r[0] for r in sorted(rows, key=lambda r: d(r[1], r[2]))[:k]]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--위치", nargs=2, type=float, metavar=("위도", "경도"))
    ap.add_argument("--db", default=os.path.join(HERE, "혼밥_동성로.db"))
    a = ap.parse_args()
    con = sqlite3.connect("file:" + os.path.abspath(a.db) + "?mode=ro", uri=True)
    ids = a.ids or (nearest(con, *a.위치) if a.위치 else [])
    if not ids:
        raise SystemExit("식당ID를 주거나 --위치 위도 경도 를 주세요.")
    out, miss = score(con, ids)
    for x in out:
        print(f"{x['혼밥점수']:>2}점 = 후기 {x['후기점수']} + 1인석 {x['일인석점수']}  | {x['순위']:>2}/{x['가게수']}등 {x['혼밥후기수']:>5}명 | {x['상호']}")
    if miss:
        print("DB에 없는 가게(혼밥 조건을 못 넘었거나 동성로 밖):", ", ".join(miss))


if __name__ == "__main__":
    main()
