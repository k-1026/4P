"""정한 폴더를 차례로 끝까지 돌린다. 한 번에 하나만. 앱이 꺼져 앞 수집이 멈췄으면 이어서 돌린다.

python -I -u 이어서_전부.py 3_간단 4_이전판정_사진47 5_이전판정_한그릇17 6_팀원결과/이컴퓨터
캡차 등으로 막힘.txt가 생기면 다음으로 넘어가지 않고 끝낸다. 멈추려면 아무 폴더에나 멈춤.txt. 기록은 이어서_전부.txt.
빠진 가게·시간 넘음처럼 막힘이 아닌 멈춤은 같은 폴더를 두 번까지 다시 해 보고, 그래도 안 되면 끝낸다.
"""
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.dirname(os.path.abspath(__file__))
TEST = "--시험" in sys.argv
F = [x for x in sys.argv[1:] if not x.startswith("--")]
WAIT = 0.2 if TEST else 10


def say(x):
    x = time.strftime("%m-%d %H:%M:%S ") + x
    print(x, flush=True)
    with open(os.path.join(BASE, "이어서_전부.txt"), "a", encoding="utf-8") as f:
        f.write(x + "\n")


def stopped():
    for d in F:
        for x in ("막힘.txt", "멈춤.txt"):
            if os.path.exists(os.path.join(BASE, d, x)):
                return f"{x}: {d}"
    return ""


def finished(d):
    p = os.path.join(BASE, d, "진행.txt")
    if not os.path.exists(p):
        return False
    with open(p, encoding="utf-8", errors="replace") as f:
        return ([x.strip() for x in f if x.strip()] or [""])[-1] == "모두 끝"


def busy():
    """다른 수집 프로그램이나 Aside 수집 명령이 돌고 있으면 True. 확인하지 못해도 True."""
    if TEST:
        return False
    q = ("@(Get-CimInstance Win32_Process | Where-Object { ($_.Name -like 'python*' -and $_.CommandLine -match '간단_실행|시험_실행|수집_화면만') "
         "-or ($_.Name -eq 'aside.exe' -and $_.CommandLine -match 'aside\\S*\\s+exec\\s') }).Count")
    try:
        p = subprocess.run(["powershell", "-NoProfile", "-Command", q], capture_output=True, timeout=90)
        return p.stdout.decode("ascii", "replace").strip() != "0"
    except (OSError, subprocess.SubprocessError):
        return True


def main():
    say("시작: " + ", ".join(F))
    for d in F:
        fails = 0
        while not finished(d):
            if stopped():
                say(stopped() + " 때문에 끝냄")
                return 1
            if busy():   # 앞 수집이 도는 동안 기다린다
                time.sleep(WAIT)
                continue
            time.sleep(WAIT)
            if busy() or finished(d):
                continue
            say(f"{d} 돌림")
            rc = subprocess.run([sys.executable, "-I", "-u", os.path.join(BASE, d, "간단_실행.py")], cwd=os.path.join(BASE, d), stdin=subprocess.DEVNULL).returncode
            say(f"{d} 종료 값 {rc}")
            if rc and not stopped():
                fails += 1
                if fails > 2:
                    say(f"{d}가 세 번 멈춰 끝냄")
                    return 1
                time.sleep(WAIT * 6)
        say(f"{d} 모두 끝")
    say("전부 끝")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
