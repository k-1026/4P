"""매주 갱신 2단계: 새가게_후보.csv의 가게를 Aside로 확인한다(동성로 수집과 같은 짧은 지시문·같은 감시·캡차 멈춤).

python -B -I 새가게_판정.py [--dir <갱신/YYYYMMDD>] [--준비만]

- <dir>/판정/ 폴더에 대상목록.csv, 지시문.txt, 간단_실행.py를 만들고 돌린다. 결과는 <dir>/판정/out_*.csv, 진행은 진행.txt.
- 다른 수집(동성로 수집 등)이 돌고 있으면 시작하지 않는다(Aside는 한 번에 하나).
- 캡차·이용 제한이 보이면 수집 프로그램이 멈추고 알림 창을 띄운다. 사람이 풀어야 한다.
- 끝나면 3단계 DB_반영.py를 돌린다.
"""
import argparse
import csv
import glob
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(os.path.dirname(os.path.dirname(HERE)), "매칭도구", "작업기록_20261125_중구동성로")


def latest():
    d = sorted(x for x in glob.glob(os.path.join(HERE, "2026*")) + glob.glob(os.path.join(HERE, "20[2-9][0-9]*")) if os.path.isdir(x))
    if not d:
        raise SystemExit("갱신 폴더가 없음: 먼저 인허가_비교.py를 돌리세요")
    return d[-1]


def busy():
    """다른 수집 프로그램이나 Aside 수집 명령이 돌고 있으면 True. 확인하지 못해도 True."""
    q = ("@(Get-CimInstance Win32_Process | Where-Object { ($_.Name -like 'python*' -and $_.CommandLine -match '간단_실행|시험_실행|수집_화면만|수집\\.py|이어서_') "
         "-or ($_.Name -eq 'aside.exe' -and $_.CommandLine -match 'aside\\S*\\s+exec\\s') }).Count")
    try:
        p = subprocess.run(["powershell", "-NoProfile", "-Command", q], capture_output=True, timeout=90)
        return p.stdout.decode("ascii", "replace").strip() != "0"
    except (OSError, subprocess.SubprocessError):
        return True


def prepare(d):
    with open(os.path.join(d, "새가게_후보.csv"), encoding="utf-8-sig", newline="") as f:
        R = list(csv.DictReader(f))
    J = os.path.join(d, "판정")
    os.makedirs(J, exist_ok=True)
    with open(os.path.join(J, "대상목록.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["수집ID", "상호", "도로명주소", "업종_소분류", "행정동"])
        for r in R:
            w.writerow([r["관리번호"], r["사업장명"], r["도로명주소"].split(",")[0].split("(")[0].strip(), r["업태"], r.get("행정동_추정", "")])
    shutil.copy(os.path.join(B, "3_간단", "지시문.txt"), J)
    run = open(os.path.join(B, "3_간단", "간단_실행.py"), encoding="utf-8").read()
    old = "B = os.path.dirname(H)\n"
    if run.count(old) != 1:
        raise SystemExit("간단_실행.py 모양이 예상과 다름")
    with open(os.path.join(J, "간단_실행.py"), "w", encoding="utf-8", newline="\n") as f:
        f.write(run.replace(old, f"B = {B!r}   # 동성로 수집 폴더(수집_화면만.py가 있는 곳)\n"))
    return J, len(R)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="")
    ap.add_argument("--준비만", action="store_true")
    a = ap.parse_args()
    d = os.path.abspath(a.dir) if a.dir else latest()
    J, n = prepare(d)
    print(f"새 가게 {n}곳 준비: {J}")
    if n == 0 or a.준비만:
        return 0
    for x in ("막힘.txt", "멈춤.txt"):
        if os.path.exists(os.path.join(J, x)):
            print(f"{x}가 있어 돌리지 않음(캡차면 사람이 풀고 지운 뒤 다시)")
            return 1
    if busy():
        print("다른 수집이 돌고 있어 시작하지 않음. 끝난 뒤 다시 돌리세요.")
        return 2
    rc = subprocess.run([sys.executable, "-I", "-u", os.path.join(J, "간단_실행.py")], cwd=J, stdin=subprocess.DEVNULL).returncode
    print("판정 끝" if rc == 0 else f"판정이 멈춤(값 {rc}). {J}의 진행.txt와 막힘.txt를 보세요.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
