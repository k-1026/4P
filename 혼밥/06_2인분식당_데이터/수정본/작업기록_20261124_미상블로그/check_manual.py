"""Codex 손확인 결과 검수 도우미 (Claude 검수용, 2026-11-24).

python -I check_manual.py 손확인_codex-N.csv 접두어1 [접두어2 ...]

- 행 수·중복·대상 누락, 규칙 밖 값
- 미상이 아닌 제안마다: 근거 원문이 입력 파일(블로그 수집·지도 신호원문)에 그대로 있는지,
  '추정'이면 서로 다른 URL이 2개 이상인지, 근거 문장에 혜택·추가·포장·먹은 양 같은 함정 낱말이 있는지
- 사람이 읽을 수 있게 미상이 아닌 행을 원문과 함께 출력
"""
import csv
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
MO = {"2인분이상_확정", "2인분이상_추정", "1인분가능_확정", "미상"}
EN = {"불가", "가능", "미상"}
TRAP = re.compile(r"서비스|무료|증정|추가|포장|배달|먹었|먹고|시켰|시켜|드셔|더 시|리필|이상 주문 시|이상 주문시")


def rd(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def raw(p):
    t = open(p, encoding="utf-8-sig", errors="replace").read()
    s = t.find('"수집ID"')
    return list(csv.DictReader(t[s:].split("```")[0].splitlines())) if s >= 0 else []


def norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def main():
    path, prefixes = sys.argv[1], sys.argv[2:]
    rows = rd(path)
    target = [r["수집ID"] for r in rd(os.path.join(HERE, "블로그수집", "대상목록.csv")) if r["수집ID"].split("-")[0] in prefixes]
    ids = [r["수집ID"] for r in rows]
    print(f"행 {len(rows)} / 대상 {len(target)} | 중복 {len(ids) - len(set(ids))} | 누락 {sorted(set(target) - set(ids))} | 대상 밖 {sorted(set(ids) - set(target))}")

    texts = {}
    for p in glob.glob(os.path.join(HERE, "블로그수집", "blog_out_*.csv")):
        for b in raw(p):
            texts.setdefault(b.get("수집ID", "").strip(), []).append(("블로그", norm(b.get("근거_원문")), b.get("근거_URL", ""), b.get("메모", "")))
    for e in rd(os.path.join(ROOT, "원본자료", "2인분식당_신호원문_대구전역_Aside_20261123.csv")):
        texts.setdefault(e["수집ID"], []).append(("지도", norm(e["근거_원문"]), e["근거_URL"], e["근거_종류"]))

    bad = 0
    for r in rows:
        if r["제안_최소주문"] not in MO or r["제안_1인입장"] not in EN:
            print("  규칙 밖 값:", r["수집ID"], r["제안_최소주문"], r["제안_1인입장"]); bad += 1
    print()
    for r in rows:
        if r["제안_최소주문"] == "미상" and r["제안_1인입장"] == "미상":
            continue
        sid = r["수집ID"]
        src = texts.get(sid, [])
        flags = []
        urls = set()
        for n in (1, 2):
            q = norm(r[f"근거{n}_원문"])
            if not q:
                continue
            hit = [s for s in src if q in s[1] or (len(q) > 12 and q[:12] in s[1])]
            if not hit:
                flags.append(f"근거{n} 원문 없음")
            if TRAP.search(q):
                flags.append(f"근거{n} 함정낱말")
            if r[f"근거{n}_URL"]:
                urls.add(r[f"근거{n}_URL"].split("?")[0])
        if r["제안_최소주문"] == "2인분이상_추정" and r["손확인_분류"] == "블로그_조건2건이상" and len(urls) < 2:
            flags.append("추정인데 URL 2개 미만")
        print(f"[{sid}] {r['상호']} | {r['손확인_분류']} → {r['제안_최소주문']} {r['제안_인분']} {r['제안_범위']} / 1인입장 {r['제안_1인입장']} {r['제안_시간대제한']}"
              + (f"  ⚠ {', '.join(flags)}" if flags else ""))
        for n in (1, 2):
            if r[f"근거{n}_원문"]:
                print(f"    근거{n}: {r[f'근거{n}_원문'][:110]} ({r[f'근거{n}_출처']}, {r[f'근거{n}_작성일']})")
        if r["메모"]:
            print(f"    메모: {r['메모'][:160]}")
        bad += bool(flags)
    print(f"\n표시된 행: {bad}")


if __name__ == "__main__":
    main()
