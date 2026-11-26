"""매주 갱신을 한 번에: 0 받기 → 1 비교 → 2 Aside 판정 → 2-2 후기 다시 보기 → 3 DB 반영. 매주_갱신.bat이 이것을 부른다.

python -B -I -u 매주_갱신.py [--판정빼고]

- 기록은 이 폴더의 기록.txt에 쌓인다. 어느 단계든 멈추면 화면에 알림 창을 띄우고 끝낸다.
- 멈추면 '마지막 비교일'을 되돌려서, 다음에 돌릴 때 같은 기간을 다시 본다(새 가게를 놓치지 않게).
- 인허가 자료는 2일 전 기준이라, 지난번 비교일 3일 전부터 다시 받는다(겹친 가게는 비교·반영에서 걸러짐).
- 캡차가 뜨면 사람이 직접 풀어야 한다. 이 프로그램은 풀거나 피해 가지 않는다.
- --판정빼고: Aside를 쓰지 않고 0·1단계만(다른 수집이 돌 때 등). 후기 다시 보기도 하지 않는다.
"""
import argparse
import datetime
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
LAST = os.path.join(HERE, "마지막_비교일.txt")
LOG = os.path.join(HERE, "기록.txt")


def say(x):
    x = time.strftime("%Y-%m-%d %H:%M:%S ") + x
    print(x, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(x + "\n")


def alert(msg):
    code = "import ctypes,sys; ctypes.windll.user32.MessageBoxW(0, sys.argv[1], '혼밥 DB 매주 갱신', 0x41030)"
    subprocess.Popen([sys.executable, "-I", "-c", code, msg], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=0x00000008 | 0x00000200)


def step(name, args):
    p = subprocess.run([sys.executable, "-B", "-I", "-u", os.path.join(HERE, args[0]), *args[1:]], cwd=HERE,
                       capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
    tail = [x for x in (p.stdout or "").strip().splitlines() if x.strip()][-3:]
    say(f"{name}: 값 {p.returncode} | " + " / ".join(tail) + (" | " + p.stderr.strip()[-200:] if p.stderr.strip() else ""))
    return p.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--판정빼고", action="store_true")
    a = ap.parse_args()
    today = datetime.date.today()
    before = open(LAST, encoding="utf-8").read().strip() if os.path.exists(LAST) else ""
    start = (datetime.date.fromisoformat(before) - datetime.timedelta(days=3)) if before else today - datetime.timedelta(days=7)
    out = os.path.join(HERE, today.strftime("%Y%m%d"))
    raw = os.path.join(HERE, f"인허가_대구중구_{today:%Y%m%d}.csv")
    say(f"시작: {start} 이후 바뀐 인허가")

    def fail(where, why):
        if before:
            with open(LAST, "w", encoding="utf-8") as f:
                f.write(before)
        elif os.path.exists(LAST):
            os.remove(LAST)
        say(f"멈춤({where}): {why}. 마지막 비교일을 되돌림")
        alert(f"혼밥 DB 매주 갱신이 '{where}'에서 멈췄습니다.\n\n{why}\n\n기록: {LOG}\n캡차면 Aside에서 직접 풀고, 판정 폴더의 막힘.txt를 지운 뒤 매주_갱신.bat을 다시 누르세요.")
        return 1

    if step("0 받기", ["인허가_받기.py", "--since", start.strftime("%Y%m%d"), "--out", raw]):
        return fail("0 받기", "인허가 API에서 자료를 받지 못함(인터넷·인증키 확인)")
    if step("1 비교", ["인허가_비교.py", "--file", raw, "--since", start.isoformat(), "--out", out]):
        return fail("1 비교", "비교 프로그램 오류")
    if a.판정빼고:   # 판정을 안 했으니 다음에 같은 기간을 다시 보게 비교일을 되돌린다
        if before:
            with open(LAST, "w", encoding="utf-8") as f:
                f.write(before)
        elif os.path.exists(LAST):
            os.remove(LAST)
        say("판정은 빼고 끝냄(마지막 비교일을 되돌려 다음에 같은 기간을 다시 봄)")
        return 0
    rc = step("2 판정", ["새가게_판정.py", "--dir", out])
    if rc == 2:
        return fail("2 판정", "다른 수집이 돌고 있어 시작하지 않음. 그 수집이 끝난 뒤 다시")
    if rc:
        return fail("2 판정", "Aside 판정이 멈춤(캡차·로그인·시간 초과 등). 판정 폴더의 진행.txt 확인")
    rc = step("2-2 후기 다시 보기", ["후기_다시보기.py", "--dir", out])
    if rc == 2:
        return fail("2-2 후기 다시 보기", "다른 수집이 돌고 있어 시작하지 않음. 그 수집이 끝난 뒤 다시")
    if rc:
        return fail("2-2 후기 다시 보기", "Aside가 멈춤(캡차·로그인·시간 초과 등). 후기 폴더의 진행.txt 확인")
    if step("3 반영", ["DB_반영.py", "--dir", out]):
        return fail("3 반영", "DB 반영 또는 점검 실패")
    say("모두 끝")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
