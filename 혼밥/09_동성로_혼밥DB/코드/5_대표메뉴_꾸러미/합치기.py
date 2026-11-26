"""수집 결과(out_NNN.csv)를 모아 대표메뉴_결과.csv(가게마다 한 줄)와 대표메뉴_목록.csv(메뉴마다 한 줄)로 만든다.

python -I 합치기.py [폴더 ...]      (폴더를 안 주면 이 꾸러미 폴더)

- out 파일 앞쪽의 실행 로그는 버리고, 파일마다 마지막 답 표(마지막 머리줄 ~ 다음 ```)만 읽는다.
- 그 묶음(prompt_NNN.txt)에 들어 있던 가게의 줄만 받는다(다른 묶음 가게가 섞여도 무시).
- 여러 번 돌려도 된다. 같은 가게는 나중에 본 것(폴더 순서 → 묶음 번호 순서)으로 바꾼다.
- 맡은 가게 중 답이 없는 곳을 끝에 알려 준다.
"""
import csv
import glob
import io
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
HEAD = ["수집ID", "찾음", "대표메뉴", "대표수", "메뉴_최근업데이트", "링크", "메모"]


def last_table(t):
    """마지막 머리줄 아래 표의 줄들."""
    pos, last = 0, None
    for line in t.splitlines(True):
        if "수집ID" in line and "찾음" in line:
            last = (pos, line)
        pos += len(line)
    if not last:
        return []
    pos, line = last
    n = len(next(csv.reader([line])))
    return [r for r in csv.reader(io.StringIO(t[pos + len(line):].split("```")[0])) if len(r) == n]


def dishes(text):
    """'맵국밥 10,000원; 냉수육 중200g 29,000원' → [('맵국밥', '10,000원', 10000), ...]"""
    out = []
    for part in re.split(r"[;；]", text or ""):
        part = part.strip()
        if not part:
            continue
        m = re.search(r"^(.+?)\s+((?:\d{1,3}(?:,\d{3})+|\d{3,7})\s*원?(?:\s*~\s*(?:\d{1,3}(?:,\d{3})+|\d{3,7})\s*원?)?|시가|변동)$", part)
        if m:
            p = re.match(r"(\d{1,3}(?:,\d{3})+|\d{3,7})", m.group(2))
            out.append((m.group(1).strip(), m.group(2).strip(), int(p.group(1).replace(",", "")) if p else None))
        else:
            out.append((part, "", None))
    return out


def main():
    dirs = [os.path.abspath(x) for x in sys.argv[1:]] or [HERE]
    best, want = {}, {}
    for d in dirs:
        names = {}
        p = os.path.join(d, "대상목록.csv")
        if os.path.exists(p):
            with open(p, encoding="utf-8-sig", newline="") as f:
                names = {r["수집ID"]: r["상호"] for r in csv.DictReader(f)}
        for pr in sorted(glob.glob(os.path.join(d, "prompt_*.txt"))):
            tag = os.path.basename(pr)[7:-4]
            ids = [r[0] for r in json.loads(open(pr, encoding="utf-8").read().split("입력:\n", 1)[1])]
            for i in ids:
                want.setdefault(i, names.get(i, ""))
            out = os.path.join(d, f"out_{tag}.csv")
            if not os.path.exists(out):
                continue
            t = open(out, encoding="utf-8", errors="replace").read()
            day = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(out)))
            for r in last_table(t):
                r = [x.strip() for x in r]
                if r[0] in ids and r[1] in ("예", "아니오"):
                    best[r[0]] = dict(zip(HEAD, r), 본날=day, 상호=names.get(r[0], ""))
    with open(os.path.join(HERE, "대표메뉴_결과.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["식당ID", "상호", "찾음", "대표메뉴", "대표수", "메뉴_최근업데이트", "링크", "메모", "본날"])
        w.writeheader()
        for i, r in sorted(best.items()):
            w.writerow({"식당ID": i, **{k: r[k] for k in ("상호", "찾음", "대표메뉴", "대표수", "메뉴_최근업데이트", "링크", "메모", "본날")}})
    n = 0
    with open(os.path.join(HERE, "대표메뉴_목록.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["식당ID", "상호", "메뉴명", "가격_글", "가격_원", "본날"])
        for i, r in sorted(best.items()):
            if r["찾음"] != "예":
                continue
            for name, ptxt, won in dishes(r["대표메뉴"]):
                w.writerow([i, r["상호"], name, ptxt, "" if won is None else won, r["본날"]])
                n += 1
    miss = [f"{want[i]}({i})" for i in want if i not in best]
    zero = sum(1 for r in best.values() if r["찾음"] == "예" and r["대표수"] == "0")
    print(f"맡은 가게 {len(want)}곳 중 답 {len(best)}곳 (대표 표시 없음 {zero}곳), 대표 메뉴 {n}줄, 답 없음 {len(miss)}곳")
    if miss:
        print("  답 없음:", ", ".join(miss[:15]), "…" if len(miss) > 15 else "")


if __name__ == "__main__":
    main()
