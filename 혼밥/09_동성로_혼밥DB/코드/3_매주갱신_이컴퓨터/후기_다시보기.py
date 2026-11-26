"""매주 갱신 2-2단계: 혼밥 후기가 모자라 기다리는 가게의 '혼밥하기 좋아요' 수를 다시 본다.

python -B -I 후기_다시보기.py [--dir <갱신/YYYYMMDD>] [--최대 30] [--준비만] [--오늘 YYYY-MM-DD]

다시 보는 가게 (11-26 사용자 결정)
- 새 가게: 후기대기_새가게.csv(1인분인데 후기가 모자란 인허가 새 가게). 처음 본 날로부터 2주·4주·8주에 한 번씩, 그 뒤로는 매달.
- 기존 대기: 작업용/대기목록.csv 중 '한 달에 한 번 혼밥 후기 수'(1인분은 되는데 후기 5명 미만). 마지막으로 본 날로부터 매달.
- 한 번에 최대 30곳. 새 가게 먼저, 그다음 오래 기다린 순. 넘치면 다음 주로 미룬다.
- 지도에서 못 찾았거나 폐업·휴업 표시가 있던 가게는 더 보지 않는다.

결과
- 후기_다시보기_기록.csv: 다시 본 결과 전부.
- 기존 대기 가게: 누적_후기.csv에 적는다. make_db.py가 DB를 만들 때 이 숫자로 다시 판정한다(5명 이상이면 들어감).
- 새 가게가 5명 이상이면 후기대기_새가게.csv의 판정 줄을 혼밥수·본날만 새로 해서 누적_추가.csv로 옮긴다.
- 다른 수집이 돌고 있으면 시작하지 않는다(값 2). 캡차·멈춤·빠진 묶음이면 값 1(같은 날 다시 돌리면 끝난 묶음은 건너뜀).
"""
import argparse
import csv
import datetime
import glob
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DBDIR = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, DBDIR)
from DB_반영 import ADD, ADD_HEAD, LATER, append, rd  # noqa: E402
from make_db import KEY  # noqa: E402

WAITLIST = os.path.join(DBDIR, "작업용", "대기목록.csv")
LOG = os.path.join(HERE, "후기_다시보기_기록.csv")
LOG_HEAD = ["키", "종류", "상호", "본날", "찾음", "혼밥수", "링크", "메모"]
REDO = os.path.join(HERE, "누적_후기.csv")
REDO_HEAD = ["수집ID", "혼밥수", "본날", "찾음", "링크", "메모"]
NEW_STEPS = (14, 28, 56)   # 새 가게: 처음 본 날로부터 2·4·8주
MONTH = 30
SIZE = 5


def day(x):
    try:
        return datetime.date.fromisoformat((x or "")[:10])
    except ValueError:
        return None


def due(today):
    """오늘 볼 가게 [(순서, 볼날, 키, 종류, 상호, 주소, 링크)]."""
    seen = defaultdict(list)
    for r in rd(LOG):
        seen[r["키"]].append(r)
    stop = {k for k, rs in seen.items() if rs[-1]["찾음"] != "예" or re.search("폐업|휴업", rs[-1]["메모"])}
    added = {r["식당ID"] for r in rd(ADD)}
    out, keys = [], set()
    for r in rd(LATER):
        k = r["식당ID"]
        if k in added or k in stop or k in keys or not day(r["본날"]):
            continue
        n = len(seen[k])
        when = day(r["본날"]) + datetime.timedelta(days=NEW_STEPS[n]) if n < len(NEW_STEPS) \
            else day(seen[k][-1]["본날"]) + datetime.timedelta(days=MONTH)
        if when <= today:
            out.append((0, when, k, "새가게", r["상호"], r["도로명주소"], r["지도링크"]))
            keys.add(k)
    for r in rd(WAITLIST):
        k = r["수집ID"]
        if r["다시_볼_것"] != "한 달에 한 번 혼밥 후기 수" or k in stop or k in keys:
            continue
        last = max([d for d in [day(r["본날"])] + [day(x["본날"]) for x in seen[k]] if d], default=None)
        if not last:
            continue
        when = last + datetime.timedelta(days=MONTH)
        if when <= today:
            out.append((1, when, k, "기존", r["상호"], r["도로명주소"], r["링크"]))
            keys.add(k)
    return sorted(out)


def last_table(t):
    """마지막 머리줄 아래 표의 줄들(앞쪽 실행 로그·예시 표는 버림)."""
    pos, last = 0, None
    for line in t.splitlines(True):
        if "수집ID" in line and "찾음" in line:
            last = (pos, line)
        pos += len(line)
    if not last:
        return []
    pos, line = last
    n = len(next(csv.reader([line])))
    return [[x.strip() for x in r] for r in csv.reader(io.StringIO(t[pos + len(line):].split("```")[0])) if len(r) == n]


def prepare(J, items):
    head = open(os.path.join(HERE, "후기_지시문.txt"), encoding="utf-8").read()
    os.makedirs(J, exist_ok=True)
    with open(os.path.join(J, "대상목록.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["키", "종류", "상호", "도로명주소", "지도링크", "볼날"])
        for _, when, k, kind, name, addr, link in items:
            w.writerow([k, kind, name, addr, link, when.isoformat()])
    for n, s in enumerate(range(0, len(items), SIZE)):
        part = [[k, name, addr, link] for _, _, k, _, name, addr, link in items[s:s + SIZE]]
        with open(os.path.join(J, f"prompt_{n:03d}.txt"), "w", encoding="utf-8") as f:
            f.write(head + json.dumps(part, ensure_ascii=False))
    shutil.copy2(os.path.join(HERE, "화면수집.py"), J)


def collect(J, today):
    """끝난 묶음의 답을 기록·누적 파일에 반영한다. 같은 날 두 번 돌려도 두 번 적지 않는다."""
    kinds = {}
    with open(os.path.join(J, "대상목록.csv"), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            kinds[r["키"]] = r
    got = {}
    for p in sorted(glob.glob(os.path.join(J, "prompt_*.txt"))):
        tag = os.path.basename(p)[7:-4]
        ids = {r[0] for r in json.loads(open(p, encoding="utf-8").read().split("입력:\n", 1)[1])}
        out = os.path.join(J, f"out_{tag}.csv")
        if os.path.exists(out):
            for r in last_table(open(out, encoding="utf-8", errors="replace").read()):
                if r[0] in ids and r[1] in ("예", "아니오"):
                    got[r[0]] = r
    logged = {(r["키"], r["본날"]) for r in rd(LOG)}
    redone = {(r["수집ID"], r["본날"]) for r in rd(REDO)}
    added = {r["식당ID"] for r in rd(ADD)}
    later = {r["식당ID"]: r for r in rd(LATER)}
    log, redo, add = [], [], []
    for k, r in got.items():
        _, found, cnt, link, memo = r[:5]
        kind = kinds[k]["종류"]
        if (k, today) not in logged:
            log.append({"키": k, "종류": kind, "상호": kinds[k]["상호"], "본날": today, "찾음": found, "혼밥수": cnt, "링크": link, "메모": memo})
        n = int(cnt) if cnt.isdigit() else None
        if kind == "기존" and (k, today) not in redone:
            redo.append({"수집ID": k, "혼밥수": cnt, "본날": today, "찾음": found, "링크": link, "메모": memo})
        if kind == "새가게" and found == "예" and n is not None and n >= KEY and k not in added and k in later \
                and not re.search("폐업|휴업", memo):
            x = dict(later[k])
            x.update({"혼밥수": n, "본날": today, "메모": (x.get("메모", "") + " | " if x.get("메모") else "") + f"후기 다시 보기 {today}: 혼밥 {n}명"})
            add.append(x)
    append(LOG, LOG_HEAD, log)
    append(REDO, REDO_HEAD, redo)
    append(ADD, ADD_HEAD, add)
    return len(got), len(add), sum(1 for x in redo if x["혼밥수"].isdigit() and int(x["혼밥수"]) >= KEY)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="")
    ap.add_argument("--최대", type=int, default=30)
    ap.add_argument("--준비만", action="store_true")
    ap.add_argument("--오늘", default="", help="시험용: 오늘 날짜를 바꿈")
    a = ap.parse_args()
    today = day(a.오늘) or datetime.date.today()
    d = os.path.abspath(a.dir) if a.dir else os.path.join(HERE, today.strftime("%Y%m%d"))
    J = os.path.join(d, "후기")
    if glob.glob(os.path.join(J, "prompt_*.txt")):   # 같은 날 다시: 묶음을 새로 만들지 않고 이어서
        print(f"이어서 함: {J}")
    else:
        items = due(today)
        print(f"오늘 볼 때가 된 가게 {len(items)}곳 (새 가게 {sum(x[0] == 0 for x in items)}) → 이번에 {min(len(items), a.최대)}곳")
        if not items:
            return 0
        prepare(J, items[:a.최대])
    if a.준비만:
        return 0
    for x in ("막힘.txt", "멈춤.txt"):
        if os.path.exists(os.path.join(J, x)):
            print(f"{x}가 있어 돌리지 않음(캡차면 사람이 풀고 지운 뒤 다시)")
            return 1
    from 새가게_판정 import busy
    if busy():
        print("다른 수집이 돌고 있어 시작하지 않음. 끝난 뒤 다시 돌리세요.")
        return 2
    subprocess.run([sys.executable, "-I", "-u", os.path.join(J, "화면수집.py")], cwd=J, stdin=subprocess.DEVNULL)
    spec = importlib.util.spec_from_file_location("화면수집_작업", os.path.join(J, "화면수집.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    tags = sorted(os.path.basename(p)[7:-4] for p in glob.glob(os.path.join(J, "prompt_*.txt")))
    left = [t for t in tags if not m.done(t)]
    n, moved, passed = collect(J, today.isoformat())
    print(f"다시 본 가게 {n}곳 | 새 가게 DB로 옮김 {moved} | 기존 대기 중 5명 넘음 {passed} (DB 다시 만들 때 들어감)")
    if os.path.exists(os.path.join(J, "막힘.txt")) or left:
        print(f"끝나지 않은 묶음 {len(left)}개" + (" | 막힘.txt 있음(캡차면 사람이 풀고 지운 뒤 다시)" if os.path.exists(os.path.join(J, "막힘.txt")) else ""))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
