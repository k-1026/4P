"""
대구 전체 생존배수 계산 (인터넷 접속 없음)

적용 규칙 (2026-11-05 사용자 확정)
  생존배수 = 영업 기간 ÷ 같은 구·업태에서 최근 10년 안에 폐업한 가게의 평균 영업 기간
  기준값에서 제외: 30일 이내 폐업, 주소에 일원·축제·행사·페스타·박람회
  업태 '기타': 생존배수 계산 안 함
비교 대상 폐업 가게가 30곳 미만이면 같은 업태의 대구 전체를 기준으로 사용 (제안값, 동년배 규칙과 맞춤)

아직 반영하지 않은 것: 프랜차이즈 제외, 대표자·상호 변경 보정
데이터 기준일: 2026-10-28 수집본
필요한 파일: ..\\과제\\docs\\daegu_pay\\6_대구전체_음식점_영업기간\\대구전체_일반음식점_WGS84.csv
결과: 생존배수_대구전체.csv
"""
import csv
import datetime as dt
import re
import statistics as st
from collections import Counter, defaultdict

SRC = r"..\과제\docs\daegu_pay\6_대구전체_음식점_영업기간\대구전체_일반음식점_WGS84.csv"
OUT = "생존배수_대구전체.csv"
BASE = dt.date(2026, 10, 28)
WINDOW_START = dt.date(2016, 10, 28)
SHORT_DAYS = 30
MIN_GROUP = 30
EVENT = re.compile(r"일원|축제|행사|페스타|박람회")


def to_date(s):
    s = re.sub(r"\D", "", s or "")
    return dt.date(int(s[:4]), int(s[4:6]), int(s[6:8])) if len(s) >= 8 else None


with open(SRC, encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

STAGE1_TOP = 0.10          # 임시 기준 (2026-11-05): 구별 생존배수 상위 10%. 구마다 기록 구조가 달라 구 안에서만 비교. 보정 후 다시 검토
LONG_YEARS = 30
COHORT_FROM = 2000         # 그 이전 개업은 폐업 기록 누락으로 생존율을 표시하지 않음
RATE_START = BASE - dt.timedelta(days=365)


def bin5(year):
    return year // 5 * 5


group, by_type, open_rows = defaultdict(list), defaultdict(list), []
dropped = Counter()
cohort, cohort_type = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])   # [전체, 영업 중]
rate = defaultdict(lambda: [0, 0])                                               # [기간 내 폐업, 전체 점포]
for r in rows:
    start = to_date(r["인허가일자"])
    if not start:
        dropped["인허가일 없음"] += 1
        continue
    gu, kind = r["구군"], r["업태"]
    if r["상태"] == "폐업":
        end = to_date(r["폐업일자"])
        if not end or end < start:
            dropped["폐업일 오류"] += 1
            continue
        days = (end - start).days
        if days <= SHORT_DAYS or EVENT.search(r["도로명주소"] + r["지번주소"]):
            dropped["단기·행사"] += 1
            continue
        cohort[(gu, kind, bin5(start.year))][0] += 1
        cohort_type[(kind, bin5(start.year))][0] += 1
        if end >= RATE_START:
            rate[(gu, kind)][0] += 1
            rate[(gu, kind)][1] += 1
        if end < WINDOW_START:
            dropped["10년 이전 폐업"] += 1
            continue
        group[(gu, kind)].append(days)
        by_type[kind].append(days)
    else:
        open_rows.append((r, start))
        for table, key in ((cohort, (gu, kind, bin5(start.year))), (cohort_type, (kind, bin5(start.year)))):
            table[key][0] += 1
            table[key][1] += 1
        rate[(gu, kind)][1] += 1

out = []
for r, start in open_rows:
    kind = r["업태"]
    item = {"관리번호": r["관리번호"], "상호": r["사업장명"], "구군": r["구군"], "업태": kind, "인허가일": start,
            "업력_년": round((BASE - start).days / 365.25, 2), "생존배수": "", "기준": "", "기준_폐업수": "", "기준_평균년": ""}
    if kind != "기타":
        g = group.get((r["구군"], kind), [])
        if len(g) >= MIN_GROUP:
            base, label = g, "같은 구·업태"
        elif len(by_type.get(kind, [])) >= MIN_GROUP:
            base, label = by_type[kind], "대구 전체 같은 업태"
        else:
            base, label = [], "비교 불가"
        if base:
            mean = st.mean(base)
            item.update(생존배수=round((BASE - start).days / mean, 3), 기준_평균년=round(mean / 365.25, 2))
        item.update(기준=label, 기준_폐업수=len(base))
    else:
        item["기준"] = "기타(계산 안 함)"
    # 보조 지표
    b = bin5(start.year)
    c = cohort[(r["구군"], kind, b)]
    c_label = "같은 구·업태"
    if c[0] < MIN_GROUP:
        c, c_label = cohort_type[(kind, b)], "대구 전체 같은 업태"
    show = start.year >= COHORT_FROM and c[0] >= MIN_GROUP and kind != "기타"
    item.update({"개업구간": f"{b}~{b + 4}", "동년배_전체": c[0], "동년배_영업중": c[1], "동년배_생존율": round(c[1] / c[0] * 100, 1) if show else "",
                 "동년배_기준": c_label if show else ("기록 제한" if start.year < COHORT_FROM else "표시 안 함")})
    rt = rate[(r["구군"], kind)]
    item.update({"업태_폐업수_12개월": rt[0], "업태_점포수": rt[1], "업태_폐업률": round(rt[0] / rt[1] * 100, 1) if rt[1] and kind != "기타" else "",
                 "인허가30년이상": "O" if item["업력_년"] >= LONG_YEARS else "",
                 "1단계_오래버틴집": "", "구별_상위10%_기준배수": "",
                 "보정상태": "프랜차이즈·대표자 변경 미반영"})
    out.append(item)

cut = {}
for g in {x["구군"] for x in out}:
    vals = sorted(float(x["생존배수"]) for x in out if x["구군"] == g and x["생존배수"] != "")
    cut[g] = vals[int(len(vals) * (1 - STAGE1_TOP))]
for x in out:
    x["구별_상위10%_기준배수"] = cut[x["구군"]]
    if x["생존배수"] != "" and float(x["생존배수"]) >= cut[x["구군"]]:
        x["1단계_오래버틴집"] = "O"

with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(out)

scored = [x for x in out if x["생존배수"] != ""]
v = sorted(float(x["생존배수"]) for x in scored)
n = len(v)
print("영업 중", len(out), "/ 점수 대상", n, "/ 기준 구분", dict(Counter(x["기준"] for x in out)))
print("기준값 제외", dict(dropped))
print("백분위: 중앙", v[n // 2], "/ 상위25%", v[int(n * .75)], "/ 상위10%", v[int(n * .9)], "/ 상위5%", v[int(n * .95)], "/ 상위1%", v[int(n * .99)], "/ 최대", v[-1])
for t in (1, 1.5, 2, 3, 4, 5):
    k = sum(a >= t for a in v)
    print(f"{t}배 이상: {k}곳 ({k / n:.1%})")
print("30년 이상:", sum(1 for x in scored if x["업력_년"] >= 30), "/ 20년 이상:", sum(1 for x in scored if x["업력_년"] >= 20))
two = [x for x in scored if float(x["생존배수"]) >= 2]
print("2배 이상의 업력 최소·중앙:", min(x["업력_년"] for x in two), st.median(x["업력_년"] for x in two))
print("2배 이상 구군:", Counter(x["구군"] for x in two).most_common())
print("2배 이상 업태 상위:", Counter(x["업태"] for x in two).most_common(8))
print("구별 상위 10% 기준(3배 등과 비교용):")
for g in sorted({x["구군"] for x in scored}):
    y = sorted(float(x["생존배수"]) for x in scored if x["구군"] == g)
    print(f"  {g}: {len(y)}곳, 상위10% {y[int(len(y) * .9)]}, 2배 이상 {sum(a >= 2 for a in y) / len(y):.0%}")
stage = [x for x in scored if x["1단계_오래버틴집"]]
print("\n[보조 지표]")
print("1단계 임시 판정:", len(stage), "/ 30년 표시 전체:", sum(1 for x in out if x["인허가30년이상"]), "(기타 포함)")
coh = [x for x in out if x["동년배_생존율"] != ""]
print("동년배 표시:", len(coh), "/ 기록 제한:", sum(x["동년배_기준"] == "기록 제한" for x in out), "/ 대구 전체 기준:", sum(x["동년배_기준"] == "대구 전체 같은 업태" for x in out))
for b in range(2000, 2030, 5):
    y = [x["동년배_생존율"] for x in coh if x["개업구간"].startswith(str(b))]
    if y:
        print(f"  {b}~{b + 4} 개업: {len(y)}곳, 생존율 중앙 {st.median(y)}% (범위 {min(y)}~{max(y)})")
rt = [x["업태_폐업률"] for x in scored if x["업태_폐업률"] != ""]
print("업태 폐업률: 중앙", st.median(rt), "/ 범위", min(rt), "~", max(rt))
print("1단계 업태 상위:", Counter(x["업태"] for x in stage).most_common(6))
print("1단계 구군:", Counter(x["구군"] for x in stage).most_common())
print("1단계 업력: 최소", min(x["업력_년"] for x in stage), "/ 중앙", st.median(x["업력_년"] for x in stage))
print("구별 1단계 기준배수·곳 수·업력 중앙:")
for g in sorted(cut):
    y = [x for x in stage if x["구군"] == g]
    print(f"  {g}: {cut[g]}배, {len(y)}곳, 업력 중앙 {st.median(x['업력_년'] for x in y)}년, 1단계 중 30년 이상 {sum(1 for x in y if x['인허가30년이상'])}곳")
print(f"저장 완료: {OUT}")
