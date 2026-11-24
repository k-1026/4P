r"""대구 전역 표본 904곳 최종 판정 (2026-11-24).

1차 판정(Aside 지도 수집) + 미상 손확인(블로그 수집 후, 작업자별 손확인_*.csv)을 합쳐
가게별 최종 판정과 구·군별 요약을 만든다. 판정 기준은 수집안내 3장 그대로다.

python -I final_merge_daegu.py --judged 1차판정.csv --dalseo 달서구최종.csv --map-raw 지도수집\out_*.csv 신호수집_Aside\sig_out_*.csv
       [--manual 손확인_codex-1.csv ...] --out 최종판정.csv --summary 구군별요약.csv

- 달서구(DS-/DC-)는 2026-11-21 최종 판정(블로그·손확인·다이닝코드 포함)을 그대로 쓴다.
- 그 밖의 가게는 1차 판정이 미상일 때만 손확인 제안을 적용한다. 1차에서 판정이 난 칸은 건드리지 않는다.
  * 최소주문: 제안이 미상이 아니면 제안 값(인분·범위 포함)을 쓴다.
  * 1인입장: 1차가 미상이고 제안이 미상이 아니면 제안 값을 쓴다(시간대제한 포함).
- --manual을 안 주면 1차 판정만으로 요약한다(기존 1차 요약과 맞는지 확인용).
- 혼밥_유형은 final_merge.py와 같은 규칙으로 다시 계산한다.
- '가게 못 찾음' 칸 = 지도 수집 원본에서 그 가게의 모든 줄이 찾음=아니오, 또는 손확인 분류가 '가게_못찾음'.
  (2026-11-23 1차 요약의 '지도에서 못 찾음'은 기준이 기록되지 않아 이 값과 다를 수 있다. 나머지 칸은 1차 요약과 같게 센다.)
"""
import argparse
import csv
import re
import sys
from collections import Counter, OrderedDict

DSR = "동성로(방문객 동선 층)"
GUGUN_ORDER = ["중구", "동구", "서구", "남구", "북구", "수성구", "달서구", "달성군", "군위군", DSR]
MANUAL_REQUIRED = ["수집ID", "손확인_분류", "제안_최소주문", "제안_인분", "제안_범위", "제안_1인입장", "제안_시간대제한"]
MO_VALUES = {"2인분이상_확정", "2인분이상_추정", "1인분가능_확정", "미상"}
EN_VALUES = {"불가", "가능", "미상"}


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_raw_csv(path):
    """Aside 결과 파일: 앞에 설명 글이나 ```csv 가 있을 수 있어 '"수집ID"' 머리줄부터 읽는다."""
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        t = f.read()
    s = t.find('"수집ID"')
    if s < 0:
        return []
    body = t[s:].split("```")[0]
    return list(csv.DictReader(body.splitlines()))


def col(row, prefix):
    """'최소주문_판정(...)'처럼 설명이 붙은 칸 이름을 앞부분으로 찾는다."""
    for k in row:
        if k == prefix or k.startswith(prefix + "("):
            return k
    raise KeyError(prefix)


def group_of(sid):
    return "2인분 후보" if re.match(r"^[A-Z]+-S-|^DS-", sid) else "비교 업종"


def layer_of(sid, gugun):
    return DSR if sid.startswith("DSR-") else gugun


def honbap_type(mo, en, n, sc, tz):
    nn = f"{n}인분" if n else "N인분"
    if en == "불가" and tz:
        return "특정 시간대 혼자 불가"
    if en == "불가":
        return "혼자 불가" + (" (1인분 메뉴는 있음)" if mo.startswith("1인분") else "")
    if mo.startswith("2인분") and sc == "일부 메뉴":
        return f"일부 메뉴만 {nn} 이상"
    if mo.startswith("2인분"):
        return f"혼자 가능, {nn} 이상 주문" if en == "가능" else f"{nn} 이상 주문 (혼자 입장 미상)"
    if mo.startswith("1인분"):
        return "혼자 1인분 가능" if en == "가능" else "1인분 메뉴 있음 (혼자 입장 미상)"
    if en == "가능":
        return "혼자 입장 가능 (최소주문 미상)"
    return "미상"


def load_manual(paths, problems):
    manual = {}
    for p in paths:
        rows = read_csv(p)
        if rows:
            missing = [c for c in MANUAL_REQUIRED if c not in rows[0]]
            if missing:
                sys.exit(f"{p}: 칸이 없습니다 {missing}")
        for m in rows:
            sid = m["수집ID"].strip()
            if sid in manual:
                problems.append(f"손확인 중복 수집ID {sid} ({p})")
                continue
            # 규칙 밖 값은 적용하지 않는다(미상으로 두고 알린다).
            if m["제안_최소주문"] not in MO_VALUES:
                problems.append(f"{sid}: 제안_최소주문 값이 규칙 밖 '{m['제안_최소주문']}' (적용 안 함)")
                m["제안_최소주문"] = "미상"
            if m["제안_1인입장"] not in EN_VALUES:
                problems.append(f"{sid}: 제안_1인입장 값이 규칙 밖 '{m['제안_1인입장']}' (적용 안 함)")
                m["제안_1인입장"] = "미상"
            manual[sid] = m
    return manual


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judged", required=True)
    ap.add_argument("--dalseo", default="", help="빼면 달서구도 1차 값으로 둔다(1차 요약 대조용)")
    ap.add_argument("--map-raw", nargs="+", required=True, dest="map_raw")
    ap.add_argument("--manual", nargs="*", default=[])
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary", required=True)
    a = ap.parse_args()

    J = read_csv(a.judged)
    k_mo, k_en = col(J[0], "최소주문_판정"), col(J[0], "1인입장_판정")
    k_tz, k_sc = col(J[0], "시간대제한"), col(J[0], "조건_적용범위")
    D = {r["수집ID"]: r for r in read_csv(a.dalseo)} if a.dalseo else None

    # 지도 수집 원본(out_*.csv, sig_out_*.csv)의 '찾음' 칸. 한 가게의 모든 줄이 '아니오'면 지도에서 못 찾은 곳.
    found = {}
    for p in a.map_raw:
        for e in read_raw_csv(p):
            k_found = next((k for k in e if k.startswith("찾음")), None)
            if k_found and e.get("수집ID"):
                found.setdefault(e["수집ID"].strip(), set()).add((e[k_found] or "").strip())
    notfound = {sid for sid, v in found.items() if v and v <= {"아니오"}}

    problems = []
    manual = load_manual(a.manual, problems)
    judged_ids = {r["수집ID"] for r in J}
    for sid in manual:
        if sid not in judged_ids:
            problems.append(f"{sid}: 손확인에 있지만 표본에 없음")

    out = []
    for r in J:
        sid = r["수집ID"]
        f = OrderedDict(
            수집ID=sid, 묶음=group_of(sid), 층=layer_of(sid, r["구군"]), 구군=r["구군"], 상호=r["상호"],
            상권_업종소분류=r["상권_업종소분류"],
            차1_최소주문=r[k_mo], 차1_1인입장=r[k_en],
            최종_최소주문=r[k_mo], 최종_인분=r["최소주문_인분"], 최종_범위=r[k_sc],
            최종_1인입장=r[k_en], 최종_시간대제한=r[k_tz],
            판정경로="1차(지도)", 손확인_분류="", 근거건수_조건="", 근거1_원문="", 근거1_URL="", 근거2_원문="", 근거2_URL="",
            지도_못찾음="예" if sid in notfound else "", 최종_메모="",
        )
        if sid.startswith(("DS-", "DC-")):
            if D is None:
                pass
            elif (d := D.get(sid)) is None:
                problems.append(f"{sid}: 달서구 최종 판정에 없음")
            else:
                f.update(최종_최소주문=d["최종_최소주문"], 최종_인분=d["최종_인분"], 최종_범위=d["최종_범위"],
                         최종_1인입장=d["최종_1인입장"], 최종_시간대제한=d["최종_시간대제한"],
                         판정경로="달서구 최종(11-21): " + (d["판정경로"] or ""), 손확인_분류=d["손확인_분류"],
                         최종_메모=d["최종_메모"])
        elif sid in manual:
            m = manual[sid]
            f.update(손확인_분류=m["손확인_분류"], 근거건수_조건=m.get("근거건수_조건", ""),
                     근거1_원문=m.get("근거1_원문", ""), 근거1_URL=m.get("근거1_URL", ""),
                     근거2_원문=m.get("근거2_원문", ""), 근거2_URL=m.get("근거2_URL", ""), 최종_메모=m.get("메모", ""))
            if r[k_mo] == "미상" and m["제안_최소주문"] != "미상":
                f.update(최종_최소주문=m["제안_최소주문"], 최종_인분=m["제안_인분"], 최종_범위=m["제안_범위"],
                         판정경로="손확인: " + m["손확인_분류"])
            elif r[k_mo] != "미상" and m["제안_최소주문"] != r[k_mo]:
                problems.append(f"{sid}: 1차 판정이 '{r[k_mo]}'인데 손확인 제안 '{m['제안_최소주문']}' (1차 유지)")
            if r[k_en] == "미상" and m["제안_1인입장"] != "미상":
                f.update(최종_1인입장=m["제안_1인입장"], 최종_시간대제한=m["제안_시간대제한"])
                if f["판정경로"] == "1차(지도)":
                    f["판정경로"] = "손확인(1인입장): " + m["손확인_분류"]
        elif a.manual and r[k_mo] == "미상":
            problems.append(f"{sid}: 1차 미상인데 손확인 결과가 없음")
        if f["판정경로"].startswith("손확인:") and f["최종_최소주문"].startswith("2인분") and not f["최종_범위"]:
            problems.append(f"{sid}: 2인분이상인데 범위가 비어 있음")
        f["최종_혼밥유형"] = honbap_type(f["최종_최소주문"], f["최종_1인입장"], str(f["최종_인분"] or ""),
                                     f["최종_범위"], f["최종_시간대제한"])
        out.append(f)

    with open(a.out, "w", encoding="utf-8-sig", newline="") as fo:
        w = csv.DictWriter(fo, fieldnames=list(out[0].keys()), quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(out)

    head = ["구군", "묶음", "표본", "2인분이상", "가게 전체", "가게전체 3인분+", "일부 메뉴만", "1인분가능", "미상",
            "1인입장 불가", "1인입장 가능", "가게 못 찾음"]

    def summarize(rows):
        two = [x for x in rows if x["최종_최소주문"].startswith("2인분")]
        whole = [x for x in two if x["최종_범위"] != "일부 메뉴"]
        big = [x for x in whole if str(x["최종_인분"]).isdigit() and int(x["최종_인분"]) >= 3]
        return [len(rows), len(two), len(whole), len(big), len(two) - len(whole),
                sum(x["최종_최소주문"].startswith("1인분") for x in rows),
                sum(x["최종_최소주문"] == "미상" for x in rows),
                sum(x["최종_1인입장"] == "불가" for x in rows), sum(x["최종_1인입장"] == "가능" for x in rows),
                sum(x["지도_못찾음"] == "예" or x["손확인_분류"] == "가게_못찾음" for x in rows)]

    lines = []
    for g in GUGUN_ORDER:
        for b in ("2인분 후보", "비교 업종"):
            rows = [x for x in out if x["층"] == g and x["묶음"] == b]
            if rows:
                lines.append([g, b] + summarize(rows))
    for b in ("2인분 후보", "비교 업종"):
        lines.append(["합계(동성로 제외)", b] + summarize([x for x in out if x["층"] != DSR and x["묶음"] == b]))
    with open(a.summary, "w", encoding="utf-8-sig", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(head)
        w.writerows(lines)

    print(f"가게 {len(out)}곳, 손확인 {len(manual)}곳 적용")
    for b in ("2인분 후보", "비교 업종"):
        x = [f for f in out if f["층"] != DSR and f["묶음"] == b]
        print(f"== {b} (동성로 제외) {len(x)}곳 | 최소주문 {dict(Counter(f['최종_최소주문'] for f in x))}")
        print(f"   판정경로 {dict(Counter(f['판정경로'].split(':')[0] for f in x))}")
    if problems:
        print(f"\n확인 필요 {len(problems)}건:")
        for p in problems:
            print("  -", p)


if __name__ == "__main__":
    main()
