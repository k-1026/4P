"""
버틴집 계산 명세 수정안 적용 (인터넷 접속 없음)

행사 신고 기준 두 가지를 나란히 계산
  A  주소에 행사 키워드가 있고 30일 이내 폐업한 기록만 제외
  B  30일 이내 폐업 전부 + 주소에 행사 키워드가 있는 폐업 제외

공통 규칙
  시작일 = 인허가일. 영업 기간 = 기준일 − 인허가일
  기준 평균 = 같은 구·군 × 업태에서 기준일 이전 최근 10년 안에 폐업한 점포의 평균 영업 기간
    30곳 미만 → 대구 전체 × 같은 업태 → 그래도 미만이면 표본 부족
  생존배수 = 영업 기간 ÷ 기준 평균. 업태 '기타'는 계산 안 함
  1단계 = 구·군 생존배수 90백분위수 이상(동점 통과) + 영업 기간 5년 이상 (임시)
          단, 상호 변경이 확인된 점포는 '업력 확인 필요'로 보류
  동년배 현재 영업 비율 = 같은 구·군 × 업태 × 개업 5년 구간의 영업 중 수 ÷ 전체 수 × 100
    30곳 미만 → 대구 전체 × 업태 × 구간. 2000년 이후 개업만 표시. 진행 중 구간은 '집계 중'
  최근 12개월 폐업 비중 = 12개월 폐업 수 ÷ (영업 중 수 + 12개월 폐업 수) × 100
  30년 표시 = 기준일이 인허가일의 30주년 이상

미반영: 전국 프랜차이즈 제외, 대표자 변경(보류), 상호 변경은 확인된 4곳만
자료: 2026-10-28 수집본. 영업상태 불명은 계산에서 제외
결과: 수정안_계산결과_대구전체.csv
"""
import csv
import datetime as dt
import math
import re
import statistics as st
from collections import Counter, defaultdict

SRC = r"..\과제\docs\daegu_pay\6_대구전체_음식점_영업기간\대구전체_일반음식점_WGS84.csv"
OUT = "수정안_계산결과_대구전체.csv"
BASE = dt.date(2026, 10, 28)
WINDOW_START = dt.date(2016, 10, 28)
RATE_START = dt.date(2025, 10, 28)
SHORT_DAYS = 30
MIN_N = 30
MIN_YEARS = 5
EVENT = re.compile(r"일원|축제|행사|페스타|박람회")
CONFIRMED_NAME_CHANGE = {     # 행안부 이력 API로 상호 변경을 확인한 곳
    "3410000-101-1971-00008", "3410000-101-1978-00002", "3410000-101-1978-00006", "3410000-101-1975-00009",
}


def to_date(s):
    s = re.sub(r"\D", "", s or "")
    try:
        return dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return None


def anniversary(d, years):
    try:
        return d.replace(year=d.year + years)
    except ValueError:      # 2월 29일
        return d.replace(year=d.year + years, day=28)


def bin5(y):
    return y // 5 * 5


with open(SRC, encoding="utf-8-sig") as f:
    src = list(csv.DictReader(f))

records, skipped = [], Counter()
for r in src:
    start = to_date(r["인허가일자"])
    if not start or start > BASE:
        skipped["인허가일 누락·오류"] += 1
        continue
    if r["상태"] == "폐업":
        end = to_date(r["폐업일자"])
        if not end or end < start or end > BASE:
            skipped["폐업일 누락·역전"] += 1
            continue
        days = (end - start).days
        event = bool(EVENT.search(r["도로명주소"] + r["지번주소"]))
        records.append({"r": r, "open": False, "start": start, "end": end, "days": days, "A제외": event and days <= SHORT_DAYS, "B제외": event or days <= SHORT_DAYS})
    elif r["상태"] == "영업/정상":
        records.append({"r": r, "open": True, "start": start, "end": None, "days": (BASE - start).days, "A제외": False, "B제외": False})
    else:
        skipped["영업상태 불명"] += 1


# C안: 30일 이내 폐업 중 넓은 행사 키워드이거나, 같은 장소에서 단기 폐업이 k건 이상이면 제외
EVENT_BROAD = re.compile(r"일원|축제|행사|페스타|페스티벌|박람회|장터")


def base_addr(r):
    a = r["도로명주소"] or r["지번주소"]
    return re.sub(r"\s+", " ", re.sub(r"\(.*?\)", "", a).split(",")[0]).strip()


short_at = Counter(base_addr(x["r"]) for x in records if not x["open"] and x["days"] <= SHORT_DAYS)
for x in records:
    is_short = not x["open"] and x["days"] <= SHORT_DAYS
    broad = bool(EVENT_BROAD.search(x["r"]["도로명주소"] + x["r"]["지번주소"]))
    for k in (3, 5, 10):
        x[f"C{k}제외"] = is_short and (broad or short_at[base_addr(x["r"])] >= k)


def compute(col):
    """col 기준으로 제외한 뒤 구·업태 기준값과 동년배, 폐업 비중을 계산"""
    group, by_type = defaultdict(list), defaultdict(list)
    coh, coh_t = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    rate = defaultdict(lambda: [0, 0])
    for x in records:
        if x[col]:
            continue
        gu, kind, b = x["r"]["구군"], x["r"]["업태"], bin5(x["start"].year)
        for t, k in ((coh, (gu, kind, b)), (coh_t, (kind, b))):
            t[k][0] += 1
            t[k][1] += x["open"]
        if x["open"]:
            rate[(gu, kind)][1] += 1
        else:
            if x["end"] >= RATE_START:
                rate[(gu, kind)][0] += 1
                rate[(gu, kind)][1] += 1
            if x["end"] >= WINDOW_START:
                group[(gu, kind)].append(x["days"])
                by_type[kind].append(x["days"])
    res = {}
    for x in records:
        if not x["open"]:
            continue
        r = x["r"]
        gu, kind, b = r["구군"], r["업태"], bin5(x["start"].year)
        item = {"배수": None, "기준": "기타(계산 안 함)" if kind == "기타" else "표본 부족", "표본": 0, "평균": None}
        if kind != "기타":
            base, label = group.get((gu, kind), []), "같은 구·업태"
            if len(base) < MIN_N:
                base, label = by_type.get(kind, []), "대구 전체 같은 업태"
            if len(base) >= MIN_N and st.mean(base) > 0:
                m = st.mean(base)
                item.update(배수=x["days"] / m, 기준=label, 표본=len(base), 평균=m / 365.25)
        c, c_label = coh[(gu, kind, b)], "같은 구·업태"
        if c[0] < MIN_N:
            c, c_label = coh_t[(kind, b)], "대구 전체 같은 업태"
        if kind == "기타":
            item["동년배"], item["동년배기준"] = None, "기타"
        elif x["start"].year < 2000:
            item["동년배"], item["동년배기준"] = None, "2000년 이전"
        elif c[0] < MIN_N:
            item["동년배"], item["동년배기준"] = None, "표본 부족"
        elif b + 4 >= BASE.year:
            item["동년배"], item["동년배기준"] = round(c[1] / c[0] * 100, 1), "집계 중"
        else:
            item["동년배"], item["동년배기준"] = round(c[1] / c[0] * 100, 1), c_label
        rt = rate[(gu, kind)]
        item["폐업비중"] = round(rt[0] / rt[1] * 100, 1) if rt[1] and kind != "기타" else None
        res[r["관리번호"]] = item
    # 구별 90백분위수 (최근접 순위법), 동점 모두 통과
    vals = defaultdict(list)
    for x in records:
        if x["open"]:
            v = res[x["r"]["관리번호"]]["배수"]
            if v is not None:
                vals[x["r"]["구군"]].append(v)
    cut = {g: sorted(v)[math.ceil(len(v) * 0.9) - 1] for g, v in vals.items()}
    return res, cut


res_a, cut_a = compute("A제외")
res_b, cut_b = compute("B제외")
res_c, cut_c = compute("C5제외")
res_c3, cut_c3 = compute("C3제외")
res_c10, cut_c10 = compute("C10제외")


def verdict(x, res, cut):
    v = res[x["r"]["관리번호"]]["배수"]
    if v is None:
        return "대상 아님"
    if v < cut[x["r"]["구군"]]:
        return "미달"
    if x["days"] < anniversary(x["start"], MIN_YEARS).toordinal() - x["start"].toordinal():
        return "최소 업력 미달"
    if x["r"]["관리번호"] in CONFIRMED_NAME_CHANGE:
        return "업력 확인 필요"
    return "통과"


rows = []
for x in records:
    if not x["open"]:
        continue
    r, a, b = x["r"], res_a[x["r"]["관리번호"]], res_b[x["r"]["관리번호"]]
    rd = lambda n, k=3: round(n, k) if n is not None else ""
    rows.append({
        "관리번호": r["관리번호"], "상호": r["사업장명"], "구군": r["구군"], "업태": r["업태"], "인허가일": x["start"], "영업기간_년": round(x["days"] / 365.25, 2),
        "인허가30년이상": "O" if BASE >= anniversary(x["start"], 30) else "",
        "행사키워드_주소_검토": "O" if EVENT.search(r["도로명주소"] + r["지번주소"]) else "",
        "상호변경_확인": "O" if r["관리번호"] in CONFIRMED_NAME_CHANGE else "",
        "A_생존배수": rd(a["배수"]), "A_기준": a["기준"], "A_표본": a["표본"], "A_기준평균_년": rd(a["평균"], 2), "A_판정": verdict(x, res_a, cut_a),
        "A_동년배비율": a["동년배"] if a["동년배"] is not None else "", "A_동년배기준": a["동년배기준"], "A_폐업비중": a["폐업비중"] if a["폐업비중"] is not None else "",
        "B_생존배수": rd(b["배수"]), "B_판정": verdict(x, res_b, cut_b), "B_동년배비율": b["동년배"] if b["동년배"] is not None else "", "B_폐업비중": b["폐업비중"] if b["폐업비중"] is not None else "",
        "C_생존배수": rd(res_c[r["관리번호"]]["배수"]), "C_기준": res_c[r["관리번호"]]["기준"], "C_표본": res_c[r["관리번호"]]["표본"], "C_기준평균_년": rd(res_c[r["관리번호"]]["평균"], 2), "C_판정": verdict(x, res_c, cut_c),
        "C_동년배비율": res_c[r["관리번호"]]["동년배"] if res_c[r["관리번호"]]["동년배"] is not None else "", "C_동년배기준": res_c[r["관리번호"]]["동년배기준"], "C_폐업비중": res_c[r["관리번호"]]["폐업비중"] if res_c[r["관리번호"]]["폐업비중"] is not None else "",
        "C3_판정": verdict(x, res_c3, cut_c3), "C10_판정": verdict(x, res_c10, cut_c10),
        "보정상태": "전국 프랜차이즈·대표자 변경 미반영, 상호 변경은 확인된 곳만",
    })

with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print("전체", len(src), "/ 유효", len(records), "/ 제외", dict(skipped))
print("제외 건수: A", sum(x["A제외"] for x in records), "/ B", sum(x["B제외"] for x in records))
print("영업 중", len(rows), "/ 행사 키워드 주소(검토 대상)", sum(1 for r in rows if r["행사키워드_주소_검토"]))
for name, v, c in (("A", "A_판정", cut_a), ("B", "B_판정", cut_b)):
    print(f"\n[{name}] 판정:", dict(Counter(r[v] for r in rows)))
    print("  합격선:", {g: round(c[g], 2) for g in sorted(c)})
pa = {r["관리번호"] for r in rows if r["A_판정"] == "통과"}
pb = {r["관리번호"] for r in rows if r["B_판정"] == "통과"}
print("\n통과 겹침", len(pa & pb), "/ A만", len(pa - pb), "/ B만", len(pb - pa))
ka = {r["관리번호"]: float(r["A_기준평균_년"]) for r in rows if r["A_기준평균_년"] != ""}
kb = [(r["구군"], r["업태"], float(r["A_기준평균_년"]), round(float(r["영업기간_년"]) / float(r["B_생존배수"]), 2)) for r in rows if r["B_생존배수"] != "" and float(r["B_생존배수"]) > 0 and r["A_기준평균_년"] != ""]
seen = {}
for g, k, a, b in kb:
    seen[(g, k)] = (a, b)
diff = sorted(((abs(a - b), g, k, a, b) for (g, k), (a, b) in seen.items()), reverse=True)[:6]
print("기준 평균 차이 큰 구·업태 (A년, B년):", [(g, k, a, b) for _, g, k, a, b in diff])
t = [float(r["영업기간_년"]) for r in rows if r["A_판정"] == "통과"]
print("A 통과 영업기간: 최소", min(t), "/ 중앙", st.median(t), "/ 5년 미만 탈락", sum(1 for r in rows if r["A_판정"] == "최소 업력 미달"))
print("A 통과 구군:", Counter(r["구군"] for r in rows if r["A_판정"] == "통과").most_common())
print("A 통과 업태:", Counter(r["업태"] for r in rows if r["A_판정"] == "통과").most_common(6))
print("동년배 표시 구분:", dict(Counter(r["A_동년배기준"] for r in rows)))
print("30년 표시:", sum(1 for r in rows if r["인허가30년이상"]))
print("\n===== C안 =====")
shorts = [x for x in records if not x["open"] and x["days"] <= SHORT_DAYS]
print("30일 이내 폐업", len(shorts), "/ C3 제외", sum(x["C3제외"] for x in records), "/ C5 제외", sum(x["C5제외"] for x in records), "/ C10 제외", sum(x["C10제외"] for x in records))
print("C5 합격선:", {g: round(cut_c[g], 2) for g in sorted(cut_c)})
print("C5 판정:", dict(Counter(r["C_판정"] for r in rows)))
sets = {k: {r["관리번호"] for r in rows if r[k] == "통과"} for k in ("A_판정", "B_판정", "C_판정", "C3_판정", "C10_판정")}
for k in ("A_판정", "B_판정", "C3_판정", "C10_판정"):
    print(f"C5와 {k[:-3]} 통과 겹침 {len(sets['C_판정'] & sets[k])} / C5만 {len(sets['C_판정'] - sets[k])} / {k[:-3]}만 {len(sets[k] - sets['C_판정'])}")
for g, kind in (("달서구", "호프/통닭"), ("수성구", "한식"), ("군위군", "한식"), ("중구", "한식")):
    row = next((r for r in rows if r["구군"] == g and r["업태"] == kind and r["A_기준평균_년"] != ""), None)
    if row:
        print(f"{g} {kind} 기준 평균: A {row['A_기준평균_년']} / C5 {row['C_기준평균_년']} / B {round(float(row['영업기간_년']) / float(row['B_생존배수']), 2) if row['B_생존배수'] and float(row['B_생존배수']) > 0 else '-'}")
keep = [x for x in shorts if not x["C5제외"]]
print("C5에서 남은 단기 폐업", len(keep), "/ 업태 상위", Counter(x["r"]["업태"] for x in keep).most_common(5), "/ 개업 월", sorted(Counter(x["start"].month for x in keep).items()))
top = [(a, n) for a, n in short_at.most_common() if n >= 5]
print("5건 이상 장소", len(top), "/ 상위 12", top[:12])
print("5~6건 장소 표본", [a for a, n in top if n <= 6][:14])
openers = Counter(base_addr(x["r"]) for x in records if x["open"])
print("5건 이상 장소 중 영업 중 가게 있는 곳", sum(1 for a, _ in top if openers[a]), "/ 그 영업 가게 수", sum(openers[a] for a, _ in top))
print("저장 완료:", OUT)
