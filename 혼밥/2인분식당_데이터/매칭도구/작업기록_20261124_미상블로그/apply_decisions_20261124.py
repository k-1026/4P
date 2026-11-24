"""Codex 4명의 손확인 결과를 하나로 합치고, 2026-11-24 사용자 결정을 반영한다.

python -I apply_decisions_20261124.py 손확인_codex-1.csv 손확인_codex-2.csv 손확인_codex-3.csv 손확인_codex-4.csv --out 손확인_통합_사용자결정반영_20261124.csv

Codex 원본 파일은 고치지 않는다. 바뀐 행은 메모 끝에 [사용자결정 11-24: ...]를 붙인다.

사용자 결정 (2026-11-24)
1. DG-C-007 1인입장: 미상 유지 (바꾸지 않음)
2. GW-S-011 '1인 1메뉴 4/대 3/중 2/소': 미상 (1인 1메뉴와 최소 크기 2명이 부딪힘)
3. 블로그 글 속 메뉴판 사진만으로 낸 '확정'은 블로그 근거로 센다(달서구 11-21과 같은 방식):
   조건 글 2건 이상 → 2인분이상_추정, 1건 → 미상. 1인분가능_확정도 매장 지도 근거가 없으면 미상.
4. 크기메뉴_최소2인의 범위는 모두 '가게 전체' (달서구 11-21 final_merge.py와 같은 기준)
"""
import argparse
import csv
from collections import Counter

TAG = "사용자결정 11-24"


def is_map_source(s):
    """지도(네이버·카카오 매장 페이지) 출처인지. 블로그에 실린 사진은 지도 출처가 아니다."""
    return bool(s) and s.startswith(("네이버", "카카오")) and "블로그" not in s


def note(r, why):
    r["메모"] = (r["메모"] + " " if r["메모"] else "") + f"[{TAG}: {why}]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs=4)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    rows, head = [], None
    for p in a.inputs:
        with open(p, encoding="utf-8-sig", newline="") as f:
            rd = csv.DictReader(f)
            head = head or rd.fieldnames
            if rd.fieldnames != head:
                raise SystemExit(f"{p}: 칸 순서가 다릅니다")
            rows.extend(rd)
    ids = [r["수집ID"] for r in rows]
    if len(ids) != len(set(ids)):
        raise SystemExit("수집ID 중복: " + ", ".join(k for k, v in Counter(ids).items() if v > 1))

    changed = Counter()
    for r in rows:
        sid, mo = r["수집ID"], r["제안_최소주문"]
        # 결정 2
        if sid == "GW-S-011" and mo != "미상":
            r.update(제안_최소주문="미상", 제안_인분="", 제안_범위="")
            note(r, "'1인 1메뉴'와 '가장 작은 크기 소=2명'이 부딪혀 미상")
            changed["결정2 GW-S-011 미상"] += 1
            continue
        # 결정 3
        if mo.endswith("확정") and not (is_map_source(r["근거1_출처"]) or is_map_source(r["근거2_출처"])):
            try:
                n = int(r["근거건수_조건"] or 0)
            except ValueError:
                n = 0
            if mo == "2인분이상_확정" and n >= 2:
                r["제안_최소주문"] = "2인분이상_추정"
                note(r, f"블로그 속 메뉴판 사진은 블로그 근거로 셈. 조건 글 {n}건 → 추정")
                changed["결정3 확정→추정"] += 1
            else:
                r.update(제안_최소주문="미상", 제안_인분="", 제안_범위="")
                note(r, f"블로그 속 메뉴판 사진은 블로그 근거로 셈. 조건 글 {n}건(2건 미만) → 미상")
                changed["결정3 확정→미상"] += 1
            continue
        # 결정 4
        if r["손확인_분류"] == "크기메뉴_최소2인" and r["제안_최소주문"].startswith("2인분") and r["제안_범위"] != "가게 전체":
            r["제안_범위"] = "가게 전체"
            note(r, "크기메뉴 범위는 가게 전체로 통일(달서구 기준)")
            changed["결정4 크기메뉴 범위→가게 전체"] += 1

    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=head, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows)
    print(f"통합 {len(rows)}행 -> {a.out}")
    for k, v in sorted(changed.items()):
        print(f"  {k}: {v}")
    print("최소주문:", dict(Counter(r["제안_최소주문"] for r in rows)))


if __name__ == "__main__":
    main()
