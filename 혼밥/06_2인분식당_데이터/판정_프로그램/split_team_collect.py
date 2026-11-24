"""달서구 전체 수집을 4명(나 + 팀원 3명)이 나눠 하도록 행정동 묶음으로 나누고, 팀원 몫 패키지를 만든다.

python -I split_team_collect.py --root . --full <전체수집 폴더> --done-batches 0 1 2 3 4 --out <팀분담 폴더>

- 대상: 전체수집/대상목록.csv (5,312곳) 중 이미 내 컴퓨터에서 돌린 묶음(--done-batches)의 가게를 뺀 나머지
- 나누기: 행정동 단위, 대략 이웃한 동끼리 4묶음(GROUPS). 한 동은 한 사람에게만.
- 팀원 패키지(팀원1~3): prompt_NNN.txt(25곳씩, 지시문은 make_web_pilot.HEAD와 같음), 대상목록.csv, 안내.md, 수집.ps1, 마무리.ps1
- 내 몫(나): prompt + run_all.sh 만 (내 컴퓨터에서 바로 돌림)
"""
import argparse
import csv
import importlib.util
import json
import os
import random
import shutil

GROUPS = {
    "나_성서권": ["신당동", "이곡1동", "이곡2동", "용산1동", "용산2동"],
    "팀원1_월배남부권": ["진천동", "상인3동", "월성1동", "월성2동", "도원동", "유천동"],
    "팀원2_상인송현권": ["상인1동", "상인2동", "송현1동", "송현2동", "본동", "장기동"],
    "팀원3_두류감삼권": ["두류1.2동", "두류3동", "감삼동", "성당동", "죽전동", "본리동"],
}
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "작업기록_20261124_웹데이터_달서구", "팀원도구")


def load_pilot():
    spec = importlib.util.spec_from_file_location("make_web_pilot", os.path.join(HERE, "make_web_pilot.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--full", required=True)
    ap.add_argument("--done-batches", nargs="*", type=int, default=[])
    ap.add_argument("--out", required=True)
    ap.add_argument("--per", type=int, default=25)
    ap.add_argument("--seed", type=int, default=20261124)
    a = ap.parse_args()
    P = load_pilot()

    with open(os.path.join(a.full, "대상목록.csv"), encoding="utf-8-sig", newline="") as f:
        target = list(csv.DictReader(f))
    with open(os.path.join(a.root, "원본자료", "웹데이터_달서구_v0_20261124.csv"), encoding="utf-8-sig", newline="") as f:
        web = {r["상가업소번호"]: r for r in csv.DictReader(f)}
    done = set()
    for i in a.done_batches:
        with open(os.path.join(a.full, f"prompt_{i:03d}.txt"), encoding="utf-8") as f:
            done |= {r[0] for r in json.loads(f.read().split("입력:\n", 1)[1])}
    rest = [t for t in target if t["수집ID"] not in done]

    dong2g = {d: g for g, ds in GROUPS.items() for d in ds}
    miss = {web[t["수집ID"]]["행정동"] for t in rest} - set(dong2g)
    if miss:
        raise SystemExit(f"묶음에 없는 행정동: {miss}")
    rnd = random.Random(a.seed)
    os.makedirs(a.out, exist_ok=True)
    summary = []
    for g, dongs in GROUPS.items():
        rows = [t for t in rest if web[t["수집ID"]]["행정동"] in dongs]
        rows.sort(key=lambda t: t["수집ID"])
        rnd.shuffle(rows)
        d = os.path.join(a.out, g)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "대상목록.csv"), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, quoting=csv.QUOTE_ALL)
            w.writerow(["수집ID", "상호", "도로명주소", "행정동", "업종_소분류", "업종_갈래"])
            for t in rows:
                w.writerow([t["수집ID"], t["상호"], t["도로명주소"], web[t["수집ID"]]["행정동"], t["업종_소분류"], t["업종_갈래"]])
        nb = 0
        for k in range(0, len(rows), a.per):
            items = [[t["수집ID"], (web[t["수집ID"]]["상호"] + " " + web[t["수집ID"]]["지점명"]).strip(), t["도로명주소"], t["업종_소분류"]]
                     for t in rows[k:k + a.per]]
            with open(os.path.join(d, f"prompt_{k // a.per:03d}.txt"), "w", encoding="utf-8", newline="\n") as f:
                f.write(P.HEAD + json.dumps(items, ensure_ascii=False))
            nb += 1
        with open(os.path.join(d, "run_all.sh"), "w", encoding="utf-8", newline="\n") as f:
            f.write(P.RUN)
        if not g.startswith("나"):
            for n in ("수집.ps1", "마무리.ps1"):
                shutil.copyfile(os.path.join(TOOLS, n), os.path.join(d, n))
            with open(os.path.join(TOOLS, "안내_틀.md"), encoding="utf-8") as f:
                guide = f.read()
            guide = (guide.replace("{{이름}}", g).replace("{{동}}", ", ".join(dongs))
                     .replace("{{곳수}}", f"{len(rows):,}").replace("{{묶음수}}", str(nb)))
            with open(os.path.join(d, "안내.md"), "w", encoding="utf-8-sig") as f:
                f.write(guide)
        summary.append((g, dongs, len(rows), nb))

    with open(os.path.join(a.out, "분담표.md"), "w", encoding="utf-8-sig") as f:
        f.write("# 달서구 지도 수집 분담표 (2026-11-24)\n\n")
        f.write(f"- 전체 대상 {len(target):,}곳 중 내 컴퓨터에서 이미 돌린 묶음 {len(a.done_batches)}개({len(done)}곳)를 뺀 {len(rest):,}곳을 나눔\n")
        f.write("- 행정동 단위로, 대략 이웃한 동끼리 묶음. 한 동은 한 사람만.\n\n")
        f.write("| 몫 | 행정동 | 곳 수 | 묶음(25곳) |\n|---|---|---|---|\n")
        for g, dongs, n, nb in summary:
            f.write(f"| {g} | {', '.join(dongs)} | {n:,} | {nb} |\n")
    for g, dongs, n, nb in summary:
        print(f"{g}: {n}곳, {nb}묶음")
    print(f"합 {sum(s[2] for s in summary)} = 남은 {len(rest)} (이미 돌린 {len(done)})")


if __name__ == "__main__":
    main()
