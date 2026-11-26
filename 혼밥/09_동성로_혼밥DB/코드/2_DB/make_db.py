"""동성로 혼밥 DB를 만든다(다시 돌리면 그때까지 모인 수집 결과로 새로 만든다).

python -B -I make_db.py

1) 매칭도구/작업기록_20261125_중구동성로의 make_packs.py → 확정본_만들기.py를 임시 폴더에 돌린다(원자료는 읽기만 함).
2) '1인분이 되고 혼자 가서 먹을 수 있는' 가게만 넣는다(11-26 팀 결정):
   같은 가게를 찾았고(찾음=예) + 주요 요리 1인분 + 네이버 '혼밥하기 좋아요' KEY명(5명) 이상.
3) 같은 지도 가게(네이버·카카오 가게 번호가 같음)는 한 줄로 합친다.
4) 10곳 비교 시험 가게는 넣지 않는다(시험 결과를 흐리지 않으려고. 시안과 같은 방식).
5) 들어가지 못한 가게 중 다시 볼 곳은 작업용/대기목록.csv로 남긴다(팀에 넘기지 않음).
"""
import csv
import datetime
import glob
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(os.path.dirname(HERE), "매칭도구", "작업기록_20261125_중구동성로")
sys.path.insert(0, os.path.join(B, "에이전트자료"))
from 혼밥판정 import KEY  # noqa: E402

DB = os.path.join(HERE, "혼밥_동성로.db")
WAIT = os.path.join(HERE, "작업용", "대기목록.csv")
TODAY = datetime.date.today().isoformat()
TEST = ("운수좋은날불갈비", "몽돌", "팔공막창", "동경식당", "마당갈비", "진원소우", "유가네", "국일불갈비", "성서산호식당", "저절로막창")
DIRS = ("1_2인분의심", "3_간단", "4_이전판정_사진47", "5_이전판정_한그릇17", "6_팀원결과/*")


def rd(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def run_packs(tmp):
    py = [sys.executable, "-B", "-I"]
    for args, cwd in (([os.path.join(B, "에이전트자료", "make_packs.py"), tmp], os.path.join(B, "에이전트자료")),
                      ([os.path.join(B, "확정본_만들기.py"), tmp, os.path.join(tmp, "f.csv")], B)):
        p = subprocess.run(py + args, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
        if p.returncode:
            raise SystemExit("만들기 실패: " + p.stderr[-500:])
    return rd(os.path.join(tmp, "f.csv")), rd(os.path.join(tmp, "메뉴", "동성로_주요요리_20261125.csv"))


def seen_days():
    """수집ID별로 그 가게가 적힌 가장 최근 Aside 답 파일의 날짜(파일이 바뀐 날)."""
    day = {}
    for d in DIRS:
        for p in glob.glob(os.path.join(B, d, "out_*.csv")):
            t = open(p, encoding="utf-8-sig", errors="replace").read()
            when = datetime.date.fromtimestamp(os.path.getmtime(p)).isoformat()
            for i in re.findall(r'^"?([^",\s]+)"?\s*,\s*"?(?:예|애매|아니오)', t, re.M):
                day[i] = max(day.get(i, ""), when)
    return day


def num(x):
    return int(x) if str(x).isdigit() else None


def source(r):
    memo = r["메모"]
    if "카카오" in memo:
        return "카카오메뉴"
    if "사진 봄" in memo or ("사진" in memo and "사진 없음" not in memo):
        return "메뉴사진"
    return "메뉴글"


def dish(text, mains):
    """근거문구에 이름이 들어 있는 주요 요리 중 가장 긴 이름의 (이름, 가격). 없으면 (None, None).
    근거문구를 글자로 쪼개면 '8P' 같은 조각이 이름으로 잡혀서, 이미 정리된 주요 요리 목록에서 고른다."""
    flat = re.sub(r"\s", "", text)
    hit = [m for m in mains if m["요리명"] and re.sub(r"\s", "", m["요리명"]) in flat]
    if not hit:
        return None, None
    m = max(hit, key=lambda m: len(m["요리명"]))
    return m["요리명"], num(m["가격_원"])


def weekly(c):
    """갱신/누적_추가.csv(매주 새로 넣은 가게)와 갱신/누적_폐업.csv(폐업)를 DB에 반영한다. 다시 만들어도 갱신이 사라지지 않게."""
    g = os.path.join(HERE, "갱신")
    add = rd(os.path.join(g, "누적_추가.csv")) if os.path.exists(os.path.join(g, "누적_추가.csv")) else []
    gone = rd(os.path.join(g, "누적_폐업.csv")) if os.path.exists(os.path.join(g, "누적_폐업.csv")) else []
    ids = {x[0] for x in c.execute("SELECT 식당ID FROM 식당")}
    keys = {x[0] for x in c.execute("SELECT 지도가게번호 FROM 식당 WHERE 지도가게번호 GLOB '[NK][0-9]*'")}
    n = 0
    for r in add:
        if r["식당ID"] in ids or (r["지도가게번호"] and r["지도가게번호"] in keys):
            continue
        i, when = r["식당ID"], r["본날"]
        c.execute("INSERT INTO 식당 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (i, r["상호"], r["업종"], "중구", r["행정동"] or None, r["도로명주소"], float(r["위도"]), float(r["경도"]),
                   r["지도링크"] or None, r["지도가게번호"] or None, when, when, None))
        c.execute("INSERT INTO 근거(식당ID,항목,메뉴명,인분,가격,요지,판단,출처,주소링크,본날,상태) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                  (i, "일인메뉴", r["일인메뉴명"] or None, 1, num(r["일인메뉴가격"]), r["근거문구"], "매주 갱신(Aside)", r["출처"], r["지도링크"] or None, when, "검토전"))
        c.execute("INSERT INTO 근거(식당ID,항목,수,요지,출처,주소링크,본날,상태) VALUES(?,?,?,?,?,?,?,?)",
                  (i, "혼밥후기수", num(r["혼밥수"]), f"네이버 '혼밥하기 좋아요' {r['혼밥수']}명", "리뷰키워드", r["지도링크"] or None, when, "검토전"))
        for part in re.split(r"[;；]", r["주요요리"]):
            m = re.search(r"^\s*(.+?)\s*((?:\d{1,3}(?:,\d{3})+)|\d{3,6})\s*원?\s*$", part)
            if m:
                c.execute("INSERT INTO 주요메뉴 VALUES(?,?,?,?,?,?)", (i, m.group(1).strip(), int(m.group(2).replace(",", "")), None, 0, when))
        c.execute("INSERT INTO 검색기록(식당ID,찾은날,찾은곳,결과,메모) VALUES(?,?,?,?,?)", (i, when, "네이버 지도", "있음", "매주 갱신(인허가 새 가게)"))
        ids.add(i)
        if r["지도가게번호"]:
            keys.add(r["지도가게번호"])
        n += 1
    # 폐업한 ID가 대표가 아니라 겹친ID에 들어가 있어도(같은 지도 가게의 대표가 바뀐 경우) 그 가게를 뺀다(Codex 3차 11-26)
    shut = {r["식당ID"] for r in gone}
    out = [sid for sid, tw in c.execute("SELECT 식당ID, 겹친ID FROM 식당").fetchall()
           if sid in shut or shut & {x.strip() for x in (tw or "").split(";") if x.strip()}]
    c.executemany("DELETE FROM 식당 WHERE 식당ID=?", [(i,) for i in out])
    c.execute("INSERT INTO 설정 VALUES('매주갱신', ?)", (f"새 가게 {n}곳 넣음, 폐업 {len(out)}곳 뺌 (누적 파일 기준)",))
    return n, len(out)


SEAT_HEAD = ["식당ID", "1인석", "출처", "본날", "요지", "확인자"]


def seats(c):
    """1인석/*.csv(혼밥일기 팀원·네이버 정보 탭 수집이 넘겨준 1인석 여부)를 근거 표에 '1인석' 줄로 넣는다.
    칸: 식당ID, 1인석(있음/없음), 출처(혼밥일기/정보탭), 본날(YYYY-MM-DD), 요지(짧게, 리뷰 작성자 이름 금지), 확인자(사람이 봤으면).
    DB에 없는 가게·잘못된 값은 넣지 않고 수만 센다. 돌려주는 값: (넣은 줄, 뺀 줄 이유별 수)."""
    ids = {x[0] for x in c.execute("SELECT 식당ID FROM 식당")}
    n, bad = 0, Counter()
    for p in sorted(glob.glob(os.path.join(HERE, "1인석", "*.csv"))):
        for x in rd(p):
            i, v, src, when = (x.get(k, "").strip() for k in ("식당ID", "1인석", "출처", "본날"))
            why = ("DB에 없는 가게" if i not in ids else "1인석 값이 있음/없음이 아님" if v not in ("있음", "없음")
                   else "출처가 혼밥일기/정보탭이 아님" if src not in ("혼밥일기", "정보탭")
                   else "본날 모양이 YYYY-MM-DD가 아님" if not re.fullmatch(r"20\d\d-[01]\d-[0-3]\d", when) else "")
            if why:
                bad[why] += 1
                continue
            who = (x.get("확인자") or "").strip() or None
            c.execute("INSERT INTO 근거(식당ID,항목,수,요지,출처,본날,상태,확인자) VALUES(?,?,?,?,?,?,?,?)",
                      (i, "1인석", 1 if v == "있음" else 0, (x.get("요지") or "").strip()[:200] or f"1인석 {v}", src, when,
                       "사람확인" if who else "검토전", who))
            n += 1
    c.execute("INSERT INTO 설정 VALUES('1인석', ?)", (f"1인석 줄 {n}개 넣음" + (f", 뺀 줄 {dict(bad)}" if bad else ""),))
    return n, bad


def human(rows):
    """사람확인_*.csv(사용자가 본 결과)를 수집 결과에 덮어쓴다. '맞음'은 그대로 두고 확인 표시만, '바꿈'은 주문·N·근거문구를 바꾼다.
    돌려주는 값: 사람이 1인분을 확인한 수집ID → 확인자."""
    fix = {}
    for p in sorted(glob.glob(os.path.join(HERE, "사람확인_*.csv"))):
        for x in rd(p):
            fix[x["수집ID"]] = x
    checked = {}
    for r in rows:
        x = fix.get(r["수집ID"])
        if not x:
            continue
        if x["결과"] == "바꿈":
            r["주문"], r["N"] = x["주문"], x["N"]
            r["근거문구"] = x["근거문구"] or r["근거문구"]
            r["확실한_정도"] = "사람확인: " + x["이유"]
        if r["주문"] == "1인분":
            checked[r["수집ID"]] = x["확인자"]
    return checked


def recheck(rows):
    """갱신/누적_후기.csv(후기_다시보기.py가 다시 본 '혼밥하기 좋아요' 수)를 수집 결과에 덮어쓴다. 가장 최근에 본 것만.
    덮어쓴 가게에는 _전_혼밥수(처음 수집 때 수)와 _후기날(다시 본 날)을 붙인다."""
    p = os.path.join(HERE, "갱신", "누적_후기.csv")
    if not os.path.exists(p):
        return 0
    last = {}
    for x in rd(p):
        if x["찾음"] == "예" and (x["수집ID"] not in last or x["본날"] >= last[x["수집ID"]]["본날"]):
            last[x["수집ID"]] = x
    n = 0
    for r in rows:
        x = last.get(r["수집ID"])
        if x and r["주문"]:
            r["_전_혼밥수"], r["_후기날"] = r["혼밥하기좋아요_수"], x["본날"]
            r["혼밥하기좋아요_수"] = x["혼밥수"]
            n += 1
    return n


def build():
    tmp = tempfile.mkdtemp()
    try:
        rows, menus = run_packs(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    day = seen_days()
    checked = human(rows)
    recheck(rows)
    passed, wait, skip = [], [], Counter()
    for r in rows:
        n = num(r["혼밥하기좋아요_수"])
        if not r["주문"]:
            continue   # 아직 안 봄: 수집이 끝나면 들어온다
        if r["상호"].replace(" ", "").startswith(TEST):
            skip["10곳 비교 시험 가게"] += 1
            continue
        if r["찾음"] == "예" and r["주문"] == "1인분" and n is not None and n >= KEY:
            passed.append(r)
        elif r["주문"] == "N인분":
            skip["N인분"] += 1
        elif r["찾음"] == "예" and r["주문"] == "1인분":
            wait.append((r, f"1인분은 되는데 혼밥 후기 {r['혼밥하기좋아요_수'] or '없음'}", "한 달에 한 번 혼밥 후기 수"))
        elif r["찾음"] == "예" and n is not None and n >= KEY:
            wait.append((r, f"혼밥 후기 {n}명인데 1인분 메뉴가 확인 안 됨", "메뉴가 바뀌었는지(메뉴 갱신 때)"))
        elif r["찾음"] in ("아니오", "애매"):
            wait.append((r, "지도에서 못 찾음" if r["찾음"] == "아니오" else "같은 가게인지 애매", "다음 주에 한 번 더 찾기"))
        else:
            skip["1인분도 혼밥 후기도 확인 안 됨"] += 1
    # 같은 지도 가게는 한 줄로: 혼밥 후기 수가 큰 쪽을 남기고 다른 ID는 겹친ID에 적는다
    keep, twin = {}, {}
    for r in sorted(passed, key=lambda r: (-num(r["혼밥하기좋아요_수"]), r["수집ID"])):
        k = r["지도가게번호"] if re.match(r"[NK]\d", r["지도가게번호"]) else "ID" + r["수집ID"]
        if k in keep:
            twin.setdefault(keep[k]["수집ID"], []).append(r["수집ID"])
        else:
            keep[k] = r
    shops = sorted(keep.values(), key=lambda r: r["수집ID"])
    byid = {}
    for m in menus:
        byid.setdefault(m["수집ID"], []).append(m)

    part = DB + ".만드는중"
    if os.path.exists(part):
        os.remove(part)
    c = sqlite3.connect(part)
    c.execute("PRAGMA foreign_keys=ON")
    with open(os.path.join(HERE, "schema.sql"), encoding="utf-8") as f:
        c.executescript(f.read())
    c.executemany("INSERT INTO 설정 VALUES(?,?)", [
        ("만든날", TODAY), ("대상", "대구 중구 동성로(성내1~3동)"), ("넣는조건", f"찾음=예 + 주요 요리 1인분 + 혼밥하기 좋아요 {KEY}명 이상"),
        ("혼밥후기_기준", str(KEY)), ("뺀것", "10곳 비교 시험 가게; 피자·치킨·술집; 식당 아닌 곳"),
        ("혼밥점수_기준", "10점 = 후기점수 8(앱이 넘긴 가게들을 혼밥하기 좋아요 수로 줄 세워 8칸, 1등 칸 8점~꼴찌 칸 1점) + 1인석·바 좌석 확인 2점. 혼밥점수.py가 계산")])
    for r in shops:
        i, when = r["수집ID"], day.get(r["수집ID"], r["확인일"])
        c.execute("INSERT INTO 식당 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (i, r["상호"], r["업종"], "중구", r["행정동"], r["도로명주소"], float(r["위도"]), float(r["경도"]),
                   r["링크"] or None, r["지도가게번호"] or None, when, when, "; ".join(twin.get(i, [])) or None))
        name, price = dish(r["근거문구"], byid.get(i, []))
        c.execute("INSERT INTO 근거(식당ID,항목,메뉴명,인분,가격,요지,판단,출처,주소링크,본날,상태,확인자) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                  (i, "일인메뉴", name, 1, price, r["근거문구"], r["확실한_정도"], source(r), r["링크"] or None, when,
                   "사람확인" if i in checked else "검토전", checked.get(i)))
        again = r.get("_후기날")
        if again and num(r["_전_혼밥수"]) is not None:   # 처음 수집 때 수도 남긴다(숫자는 덮어쓰지 않고 쌓음)
            c.execute("INSERT INTO 근거(식당ID,항목,수,요지,출처,주소링크,본날,상태) VALUES(?,?,?,?,?,?,?,?)",
                      (i, "혼밥후기수", num(r["_전_혼밥수"]), f"네이버 '혼밥하기 좋아요' {r['_전_혼밥수']}명", "리뷰키워드",
                       r["링크"] or None, when, "검토전"))
        c.execute("INSERT INTO 근거(식당ID,항목,수,요지,출처,주소링크,본날,상태) VALUES(?,?,?,?,?,?,?,?)",
                  (i, "혼밥후기수", num(r["혼밥하기좋아요_수"]), f"네이버 '혼밥하기 좋아요' {r['혼밥하기좋아요_수']}명"
                   + (" (후기 다시 보기)" if again else ""), "리뷰키워드", r["링크"] or None, again or when, "검토전"))
        if again and again > when:
            c.execute("UPDATE 식당 SET 마지막확인일=? WHERE 식당ID=?", (again, i))
        for m in byid.get(i, []):
            c.execute("INSERT INTO 주요메뉴 VALUES(?,?,?,?,?,?)", (i, m["요리명"], num(m["가격_원"]), m["가격_단위"] or None,
                                                              1 if m["곁들임일_수_있음"] else 0, when))
        c.execute("INSERT INTO 검색기록(식당ID,찾은날,찾은곳,결과,메모) VALUES(?,?,?,?,?)",
                  (i, when, "네이버 지도" if r["지도가게번호"].startswith("N") or "naver" in r["링크"] else "카카오맵", "있음", r["수집방식"]))
    weekly(c)
    seat_n, seat_bad = seats(c)
    c.commit()
    c.close()
    os.replace(part, DB)

    os.makedirs(os.path.dirname(WAIT), exist_ok=True)
    with open(WAIT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["수집ID", "상호", "도로명주소", "들어가지_못한_이유", "다시_볼_것", "혼밥하기좋아요_수", "주문", "링크", "본날"])
        for r, why, again in wait:
            w.writerow([r["수집ID"], r["상호"], r["도로명주소"], why, again, r["혼밥하기좋아요_수"], r["주문"], r["링크"], day.get(r["수집ID"], r["확인일"])])
    if seat_n or seat_bad:
        print(f"1인석 줄 {seat_n}개 넣음" + (f", 뺀 줄 {dict(seat_bad)}" if seat_bad else ""))
    return len(rows), sum(bool(r["주문"]) for r in rows), len(passed), len(shops), Counter(x[2] for x in wait), skip


if __name__ == "__main__":
    total, seen, ok, shops, wait, skip = build()
    print(f"대상 {total}곳, 지금까지 본 곳 {seen}, 조건 통과 {ok} → 같은 지도 가게 합친 뒤 DB {shops}곳")
    print("대기목록", sum(wait.values()), dict(wait))
    print("안 넣음", dict(skip))
