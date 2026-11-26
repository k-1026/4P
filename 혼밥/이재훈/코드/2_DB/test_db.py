"""혼밥_동성로.db 점검. DB를 바꾸지 않는다(잘못된 값 막기 시험은 되돌린다).

python -B -I test_db.py
"""
import os
import re
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
c = sqlite3.connect("file:" + os.path.join(HERE, "혼밥_동성로.db") + "?mode=ro", uri=True)
try:
    from make_db import KEY, TEST  # noqa: E402  (수집 폴더가 있는 이 컴퓨터)
except ImportError:   # DB만 받은 팀원 컴퓨터: 기준은 DB 설정 표에서 읽고, 시험 가게 점검은 건너뜀
    KEY, TEST = int(c.execute("SELECT 값 FROM 설정 WHERE 이름='혼밥후기_기준'").fetchone()[0]), None
c.execute("PRAGMA foreign_keys=ON")
q = lambda s, *a: c.execute(s, a).fetchall()  # noqa: E731
fails = []


def check(label, ok, detail=""):
    print("통과" if ok else "실패", label, detail if not ok else "")
    if not ok:
        fails.append(label)


n = q("SELECT COUNT(*) FROM 식당")[0][0]
check("가게가 있음", n > 0, n)
check("모든 가게에 1인 메뉴 근거", q("SELECT COUNT(*) FROM 식당 s WHERE NOT EXISTS(SELECT 1 FROM 근거 g WHERE g.식당ID=s.식당ID AND 항목='일인메뉴')")[0][0] == 0)
low = q("SELECT 식당ID FROM 혼밥가게 WHERE 혼밥후기수 IS NULL OR 혼밥후기수<?", KEY)
check(f"모든 가게 혼밥 후기 {KEY}명 이상", not low, low[:5])
check("N인분·크기세트 근거가 없음", q("SELECT COUNT(*) FROM 근거 WHERE 항목 IN ('최소주문','크기세트만')")[0][0] == 0)
names = [r[0] for r in q("SELECT 상호 FROM 식당")]
if TEST:
    check("10곳 비교 시험 가게 없음", not [x for x in names if x.replace(" ", "").startswith(TEST)])
else:
    print("참고: 수집 폴더가 없어 10곳 비교 시험 가게 점검은 건너뜀")
dup = q("SELECT 지도가게번호, COUNT(*) FROM 식당 WHERE 지도가게번호 GLOB '[NK][0-9]*' GROUP BY 1 HAVING COUNT(*)>1")
check("같은 지도 가게가 두 줄로 없음", not dup, dup)
out = q("SELECT 상호 FROM 식당 WHERE NOT (위도 BETWEEN 35.84 AND 35.89 AND 경도 BETWEEN 128.57 AND 128.62)")
check("좌표가 모두 동성로 근처", not out, out)
check("보기(혼밥가게) 줄 수 = 식당 수", q("SELECT COUNT(*) FROM 혼밥가게")[0][0] == n)
check("모든 근거에 본날", q("SELECT COUNT(*) FROM 근거 WHERE 본날 NOT GLOB '20[2-9][0-9]-[01][0-9]-[0-3][0-9]'")[0][0] == 0)
hum = q("SELECT COUNT(*), SUM(확인자 IS NULL) FROM 근거 WHERE 상태='사람확인'")[0]
print("참고: 사람확인 근거", hum[0], "줄")
check("사람확인 근거에는 모두 확인자", not hum[1])
miss = q("SELECT COUNT(*) FROM 근거 WHERE 항목='일인메뉴' AND (메뉴명 IS NULL OR 가격 IS NULL)")[0][0]
print("참고: 1인 메뉴 근거 중 메뉴명·가격을 따로 못 읽은 줄", miss, "(요지에는 원문 그대로 있음)")
bad = [r for r in q("SELECT 요지 FROM 근거 WHERE 항목='일인메뉴'") if not r[0].strip()]
check("1인 메뉴 요지가 비지 않음", not bad)
check("리뷰 작성자 칸이 없음", not [x for t in ("식당", "근거") for x in q(f"PRAGMA table_info({t})") if re.search("작성자|닉네임", x[1])])

import 혼밥점수  # noqa: E402
one = q("SELECT 일인석 FROM 혼밥가게")
print("참고: 1인석 있음", sum(r[0] == "있음" for r in one), "곳 / 없음", sum(r[0] == "없음" for r in one), "곳 / 모름", sum(r[0] is None for r in one), "곳")
ids20 = 혼밥점수.nearest(c, 35.8690, 128.5955)
out, miss = 혼밥점수.score(c, ids20 + ["없는ID"])
check("점수: 가까운 20곳 모두 1~10점, 1등 칸 8점·꼴찌 칸 1점", len(out) == 20 and all(1 <= x["혼밥점수"] <= 10 for x in out)
      and max(x["후기점수"] for x in out) == 8 and min(x["후기점수"] for x in out) == 1, [(x["상호"], x["후기점수"]) for x in out][:3])
check("점수: DB에 없는 ID는 따로 알려 줌", miss == ["없는ID"], miss)
check("점수: 후기 수가 많으면 후기점수가 낮지 않음", all(a["후기점수"] >= b["후기점수"] for a in out for b in out if a["혼밥후기수"] > b["혼밥후기수"]))
check("점수: 20곳 칸 나누기 1~3등 8 … 19~20등 1", [p for _, p in 혼밥점수.review_points(list(range(20, 0, -1)))]
      == [8, 8, 8, 7, 7, 6, 6, 6, 5, 5, 4, 4, 4, 3, 3, 2, 2, 2, 1, 1])
check("점수: 같은 수는 같은 점수, 1곳뿐이면 8점", 혼밥점수.review_points([76, 76, 10]) == [(1, 8), (1, 8), (3, 3)]
      and 혼밥점수.review_points([5]) == [(1, 8)], 혼밥점수.review_points([76, 76, 10]))

INS = "INSERT INTO 근거(식당ID,항목,메뉴명,인분,수,요지,출처,본날,상태,확인자) VALUES(?,?,?,?,?,?,?,?,?,?)"
sid = q("SELECT 식당ID FROM 식당 LIMIT 1")[0][0]
w = sqlite3.connect(":memory:")
w.execute("PRAGMA foreign_keys=ON")
w.executescript(open(os.path.join(HERE, "schema.sql"), encoding="utf-8").read())
w.execute("INSERT INTO 식당(식당ID,상호,구군,도로명주소,위도,경도,처음넣은날,마지막확인일) VALUES(?,?,?,?,?,?,?,?)",
          (sid, "시험", "중구", "주소", 35.87, 128.59, "2026-11-26", "2026-11-26"))
for label, a in [("사람확인인데 확인자 없음", (sid, "일인메뉴", "국밥", 1, None, "국밥 9,000원", "메뉴글", "2026-11-26", "사람확인", None)),
                 ("1인 메뉴인데 2인분", (sid, "일인메뉴", "국밥", 2, None, "x", "메뉴글", "2026-11-26", "검토전", None)),
                 ("혼밥 후기 수가 비어 있음", (sid, "혼밥후기수", None, None, None, "x", "리뷰키워드", "2026-11-26", "검토전", None)),
                 ("모르는 출처", (sid, "일인메뉴", "국밥", 1, None, "x", "블로그", "2026-11-26", "검토전", None)),
                 ("없는 가게", ("없는ID", "일인메뉴", "국밥", 1, None, "x", "메뉴글", "2026-11-26", "검토전", None)),
                 ("추정 상태는 받지 않음", (sid, "일인메뉴", "국밥", 1, None, "x", "메뉴글", "2026-11-26", "추정", None)),
                 ("1인석 수가 0·1이 아님", (sid, "1인석", None, None, 2, "x", "혼밥일기", "2026-11-26", "검토전", None)),
                 ("1인석 출처가 혼밥일기·정보탭이 아님", (sid, "1인석", None, None, 1, "x", "메뉴글", "2026-11-26", "검토전", None))]:
    try:
        w.execute(INS, a)
        check("막힘: " + label, False, "들어가 버림")
    except sqlite3.IntegrityError:
        check("막힘: " + label, True)
w.execute(INS, (sid, "일인메뉴", "국밥", 1, None, "국밥 9,000원", "메뉴글", "2026-11-26", "검토전", None))
check("바른 근거는 들어감", w.execute("SELECT COUNT(*) FROM 근거").fetchone()[0] == 1)

# 1인석·점수 시험(빈 DB): 정보탭 있음 → +2. 혼밥일기 없음이 와도 정보탭이 있으니 그대로. 정보탭이 나중에 없음 → 0
for k, cnt in (("B1", 40), ("B2", 640)):
    w.execute("INSERT INTO 식당(식당ID,상호,구군,도로명주소,위도,경도,처음넣은날,마지막확인일) VALUES(?,?,?,?,?,?,?,?)",
              (k, k, "중구", "주소", 35.87, 128.59, "2026-11-26", "2026-11-26"))
    w.execute(INS, (k, "혼밥후기수", None, None, cnt, f"{cnt}명", "리뷰키워드", "2026-11-26", "검토전", None))
S = lambda: {x["식당ID"]: (x["후기점수"], x["일인석"], x["혼밥점수"]) for x in 혼밥점수.score(w, ["B1", "B2"])[0]}  # noqa: E731
check("점수: 2곳 중 640명 1등 8점, 40명 2등 4점, 1인석 모름", S() == {"B2": (8, "모름", 8), "B1": (4, "모름", 4)}, S())
w.execute(INS, ("B1", "1인석", None, None, 1, "바 좌석", "정보탭", "2026-11-26", "검토전", None))
w.execute(INS, ("B1", "1인석", None, None, 0, "없음", "혼밥일기", "2026-11-27", "검토전", None))
check("점수: 정보탭 있음 + 혼밥일기 없음 → +2", S()["B1"] == (4, "있음", 6), S())
w.execute(INS, ("B1", "1인석", None, None, 0, "바 좌석 없어짐", "정보탭", "2026-11-28", "검토전", None))
check("점수: 정보탭이 나중에 없음 → +0", S()["B1"] == (4, "없음", 4), S())
w.execute(INS, ("B2", "1인석", None, None, 1, "1인석 있음", "혼밥일기", "2026-11-29", "검토전", None))
check("점수: 1등 + 1인석 → 만점 10점", S()["B2"] == (8, "있음", 10), S())

print(f"\n가게 {n}곳, 근거 {q('SELECT COUNT(*) FROM 근거')[0][0]}줄, 주요메뉴 {q('SELECT COUNT(*) FROM 주요메뉴')[0][0]}줄, 실패 {len(fails)}")
sys.exit(1 if fails else 0)
