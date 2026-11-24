"""팀원 결과(결과_*.csv)와 내 컴퓨터 수집 결과(out_*.csv)를 한 폴더로 합쳐, judge_web_pilot.py로 바로 판정할 수 있게 한다.

python -I merge_team_collect.py --target 전체수집/대상목록.csv --mine 전체수집 팀분담/나_성서권 --team 받은파일/결과_팀원1_월배남부권.csv ... --out 통합

- --mine: Aside 원래 출력(out_*.csv, 앞뒤 설명글·``` 포함 가능)이 있는 폴더들
- --team: 팀원 마무리.ps1 결과 CSV (묶음·몫 칸이 붙어 있음)
출력: <out>/대상목록.csv (전체 대상), <out>/out_<출처>.csv (머리줄 포함 CSV), <out>/합치기_보고.md
같은 가게가 여러 출처에 있으면 먼저 읽은 출처(내 것 → 팀원 순)만 쓰고 보고에 적는다.
"""
import argparse
import csv
import glob
import io
import os
from collections import Counter, OrderedDict


def aside_rows(path):
    txt = open(path, encoding="utf-8-sig", errors="replace").read()
    s = txt.find('"수집ID"')
    if s < 0:
        return None, []
    body = txt[s:].split("```")[0]
    rd = csv.DictReader(io.StringIO(body))
    return rd.fieldnames, [r for r in rd if (r.get("수집ID") or "").strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--mine", nargs="*", default=[])
    ap.add_argument("--team", nargs="*", default=[])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    with open(a.target, encoding="utf-8-sig", newline="") as f:
        target = list(csv.DictReader(f))
    tid = OrderedDict((t["수집ID"], t) for t in target)

    sources = []   # (이름, 머리줄, 행들)
    for d in a.mine:
        for p in sorted(glob.glob(os.path.join(d, "out_*.csv"))):
            head, rows = aside_rows(p)
            if head:
                sources.append((f"{os.path.basename(os.path.normpath(d))}_{os.path.basename(p)[:-4]}", head, rows))
    for p in a.team:
        with open(p, encoding="utf-8-sig", newline="") as f:
            rd = csv.DictReader(f)
            head = [h for h in rd.fieldnames if h not in ("묶음", "몫")]
            rows = [{h: r.get(h, "") for h in head} for r in rd if (r.get("수집ID") or "").strip()]
        sources.append((os.path.splitext(os.path.basename(p))[0], head, rows))

    os.makedirs(a.out, exist_ok=True)
    owner, dup, extra, per = {}, Counter(), set(), Counter()
    for name, head, rows in sources:
        keep = []
        for r in rows:
            sid = r["수집ID"].strip()
            if sid not in tid:
                extra.add(sid)
                continue
            if owner.get(sid, name) != name:
                dup[sid] += 1
                continue
            owner[sid] = name
            keep.append(r)
        per[name] = len({r["수집ID"] for r in keep})
        with open(os.path.join(a.out, f"out_{name}.csv"), "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=head, quoting=csv.QUOTE_ALL, extrasaction="ignore")
            w.writeheader()
            w.writerows(keep)
    with open(os.path.join(a.out, "대상목록.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(target[0].keys()), quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(target)

    missing = [t for t in target if t["수집ID"] not in owner]
    lines = ["# 팀 수집 결과 합치기 보고", "",
             f"- 전체 대상 {len(target):,}곳, 결과 있음 {len(owner):,}곳, **빠짐 {len(missing):,}곳**",
             f"- 같은 가게가 두 출처에 있어 뒤 것을 버림: {len(dup)}곳",
             f"- 대상목록에 없는 수집ID: {len(extra)}개" + (f" ({', '.join(sorted(extra)[:10])})" if extra else ""), "",
             "| 출처 | 가게 수 |", "|---|---|"]
    by_src = Counter()
    for name, n in per.items():
        by_src[name.split("_out_")[0] if "_out_" in name else name] += n
    lines += [f"| {k} | {v:,} |" for k, v in by_src.items()]
    if missing:
        lines += ["", "## 빠진 가게 (처음 50곳)", "", "| 수집ID | 상호 | 업종_갈래 |", "|---|---|---|"]
        lines += [f"| {t['수집ID']} | {t['상호']} | {t.get('업종_갈래', '')} |" for t in missing[:50]]
    with open(os.path.join(a.out, "합치기_보고.md"), "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines[:5]))


if __name__ == "__main__":
    main()
