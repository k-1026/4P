"""짧은 지시문으로 대상목록.csv를 5곳씩 돌린다. 감시·멈춤은 ../수집_화면만.py의 것을 그대로 쓴다.

python -I -u 간단_실행.py [돌릴 묶음 수]     끝난 묶음은 건너뛴다. 멈추려면 이 폴더에 멈춤.txt.
"""
import csv
import importlib.util
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
H = os.path.dirname(os.path.abspath(__file__))
B = os.path.dirname(H)
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 10 ** 6
sys.argv = ["x", os.path.relpath(H, B)]
s = importlib.util.spec_from_file_location("c", os.path.join(B, "수집_화면만.py"))
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
with open(os.path.join(H, "지시문.txt"), encoding="utf-8") as f:
    m.HEAD = f.read()
m.RULE = ""   # 안전 규칙은 지시문 안에 있다
if "[가장 먼저 지킬 것" not in m.HEAD or not m.HEAD.endswith("입력:\n") or "좌석" in m.HEAD:
    raise SystemExit("지시문이 예상과 다름")


def say(x):
    print(x, flush=True)
    with open(os.path.join(H, "진행.txt"), "a", encoding="utf-8") as f:
        f.write(x + "\n")


for name in ("막힘.txt", "멈춤.txt"):
    if os.path.exists(os.path.join(H, name)):
        raise SystemExit(name + "가 있어 돌리지 않음")
with open(os.path.join(H, "대상목록.csv"), encoding="utf-8-sig", newline="") as f:
    items = [[r["수집ID"], r["상호"], r["도로명주소"], r["업종_소분류"]] for r in csv.DictReader(f)]
left = [k for k in range(0, len(items), 5)
        if not m.done(os.path.join(H, f"out_{k // 5:03d}.csv"), [r[0] for r in items[k:k + 5]])]
for k in left[:LIMIT]:
    part, t0 = items[k:k + 5], time.time()
    why, _ = m.run(k // 5, part)
    out = os.path.join(H, f"out_{k // 5:03d}.csv")
    txt = open(out, encoding="utf-8", errors="replace").read() if os.path.exists(out) else ""
    n = len({r[0] for r in part} & m.answered(txt))
    say(f"{k // 5:03d} {why or '정상'} {n}/{len(part)}곳 {(time.time() - t0) / 60:.1f}분 {time.strftime('%H:%M:%S')}")
    if why or n < len(part):
        say("여기서 끝냄" if why else "빠진 가게가 있어 여기서 끝냄")
        raise SystemExit(1)
say("모두 끝" if len(left) <= LIMIT else f"정한 {LIMIT}묶음 끝")
