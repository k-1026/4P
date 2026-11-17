"""
버팀지수 계산 방법 비교 (대구 중구 시험, 인터넷 접속 없음)

비교하는 방법 (같은 업태 안에서 계산)
  평균 배수    영업 기간 ÷ 전체(영업+폐업) 평균
  중위 배수    영업 기간 ÷ 전체(영업+폐업) 중위값
  KM 배수      영업 기간 ÷ 카플란-마이어 생존 중위값 (영업 중 가게를 중도절단으로 처리)
  KM 생존확률  같은 업태에서 이 기간까지 살아남을 확률. 낮을수록 드물게 오래 버틴 가게

그룹이 30곳 미만이면 중구 전체를 기준으로 삼음
단기 신고(30일 이내 폐업)는 뺀 경우와 넣은 경우를 모두 계산

필요한 파일: mois_일반음식점_대구중구.csv
결과: 버팀지수_비교_중구.csv
"""
import csv
import datetime as dt
import re
import statistics as st
from collections import defaultdict

SRC = "mois_일반음식점_대구중구.csv"
OUT = "버팀지수_비교_중구.csv"
TODAY = dt.date(2026, 11, 5)   # 데이터를 받은 날
MIN_GROUP = 30
SHORT_DAYS = 30


def to_date(s):
    s = re.sub(r"\D", "", s or "")
    return dt.date(int(s[:4]), int(s[4:6]), int(s[6:8])) if len(s) >= 8 else None


def load(drop_short):
    out = []
    with open(SRC, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            start = to_date(r["LCPMT_YMD"])
            closed = r["SALS_STTS_CD"] == "03"
            end = to_date(r["CLSBIZ_YMD"]) if closed else TODAY
            if not start or not end or end < start:
                continue
            days = (end - start).days
            if closed and drop_short and days <= SHORT_DAYS:
                continue
            out.append({"id": r["MNG_NO"], "name": r["BPLC_NM"], "type": r["SNTTN_BZSTAT_NM"], "closed": closed,
                        "start": start, "years": days / 365.25})
    return out


def km(rows):
    """카플란-마이어: (시점, 생존확률) 목록과 생존 중위값 반환. 중위값에 못 미치면 None"""
    events = defaultdict(lambda: [0, 0])   # 시점: [폐업 수, 절단 수]
    for r in rows:
        events[r["years"]][0 if r["closed"] else 1] += 1
    at_risk, s, curve, median = len(rows), 1.0, [], None
    for t in sorted(events):
        d, c = events[t]
        if d:
            s *= 1 - d / at_risk
            curve.append((t, s))
            if median is None and s <= 0.5:
                median = t
        at_risk -= d + c
    return curve, median


def surv_at(curve, t):
    s = 1.0
    for ct, cs in curve:
        if ct > t:
            break
        s = cs
    return s


def stats(rows):
    curve, med = km(rows)
    closed = [r["years"] for r in rows if r["closed"]]
    return {"n": len(rows), "open": sum(1 for r in rows if not r["closed"]), "mean": st.mean(r["years"] for r in rows),
            "median": st.median(r["years"] for r in rows), "closed_mean": st.mean(closed) if closed else None,
            "km_median": med, "curve": curve}


def score(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[r["type"]].append(r)
    base_all = stats(rows)
    base = {k: (stats(v) if len(v) >= MIN_GROUP else base_all) for k, v in groups.items()}
    result = {}
    for r in rows:
        if r["closed"]:
            continue
        b = base[r["type"]]
        result[r["id"]] = {
            "평균배수": r["years"] / b["mean"],
            "중위배수": r["years"] / b["median"],
            "폐업평균배수": r["years"] / b["closed_mean"] if b["closed_mean"] else None,
            "KM배수": r["years"] / b["km_median"] if b["km_median"] else None,
            "KM생존확률": surv_at(b["curve"], r["years"]),
            "기준": r["type"] if len(groups[r["type"]]) >= MIN_GROUP else "중구 전체",
        }
    return result, base, groups


def ranks(values):
    """평균 순위 (값이 클수록 1등)"""
    items = sorted(values.items(), key=lambda p: -p[1])
    out, i = {}, 0
    while i < len(items):
        j = i
        while j + 1 < len(items) and items[j + 1][1] == items[i][1]:
            j += 1
        for k in range(i, j + 1):
            out[items[k][0]] = (i + j) / 2 + 1
        i = j + 1
    return out


def spearman(a, b):
    keys = sorted(set(a) & set(b))
    ra, rb = ranks({k: a[k] for k in keys}), ranks({k: b[k] for k in keys})
    x, y = [ra[k] for k in keys], [rb[k] for k in keys]
    mx, my = st.mean(x), st.mean(y)
    num = sum((p - mx) * (q - my) for p, q in zip(x, y))
    return num / (sum((p - mx) ** 2 for p in x) * sum((q - my) ** 2 for q in y)) ** 0.5


def top(values, n):
    return [k for k, _ in sorted(values.items(), key=lambda p: -p[1])[:n]]


rows = load(True)
raw = load(False)
info = {r["id"]: r for r in rows}
res, base, groups = score(rows)
res_raw, base_raw, _ = score(raw)

print(f"전체 {len(raw)}건 / 30일 이내 폐업 제외 후 {len(rows)}건 / 점수 대상(영업 중) {len(res)}곳")
print("\n[업태별 기준값, 년] 건수 | 영업 | 전체 평균 | 전체 중위 | 폐업만 평균 | KM 중위 | (단기 포함 시 KM 중위)")
for k, v in sorted(groups.items(), key=lambda p: -len(p[1]))[:12]:
    b, br = base[k], base_raw[k]
    fmt = lambda x: f"{x:.1f}" if x is not None else "미달"
    print(f"{k} | {b['n']} | {b['open']} | {fmt(b['mean'])} | {fmt(b['median'])} | {fmt(b['closed_mean'])} | {fmt(b['km_median'])} | {fmt(br['km_median'])}")
print("KM 중위 미달 업태:", [k for k, v in groups.items() if len(v) >= MIN_GROUP and base[k]["km_median"] is None])

m = {
    "평균배수": {k: v["평균배수"] for k, v in res.items()},
    "중위배수": {k: v["중위배수"] for k, v in res.items()},
    "KM배수": {k: v["KM배수"] for k, v in res.items() if v["KM배수"] is not None},
    # 생존확률은 낮을수록 드묾. 같은 값이면 업력이 긴 쪽을 위로
    "KM확률": {k: (1 - v["KM생존확률"]) + info[k]["years"] * 1e-6 for k, v in res.items()},
}
names = list(m)
print("\n[순위 상관, 1이면 순서가 같음]")
for i, a in enumerate(names):
    for b in names[i + 1:]:
        print(f"{a} vs {b}: {spearman(m[a], m[b]):.3f}")
print("\n[상위 100곳 중 겹치는 수]")
tops = {a: set(top(m[a], 100)) for a in names}
for i, a in enumerate(names):
    for b in names[i + 1:]:
        print(f"{a} vs {b}: {len(tops[a] & tops[b])}")

print("\n[단기 신고 포함/제외 민감도]")
for a, f in [("평균배수", lambda d: {k: v["평균배수"] for k, v in d.items()}),
             ("KM배수", lambda d: {k: v["KM배수"] for k, v in d.items() if v["KM배수"] is not None})]:
    x, y = f(res), f(res_raw)
    print(f"{a}: 상위 100 겹침 {len(set(top(x, 100)) & set(top(y, 100)))}, 순위 상관 {spearman(x, y):.3f}")

print("\n[방법별 상위 10곳] 상호 | 업태 | 업력 | 지수")
for a in names:
    print(f"-- {a}")
    for k in top(m[a], 10):
        v = res[k]
        val = f"생존확률 {v['KM생존확률']:.3f}" if a == "KM확률" else f"{v[a]:.1f}배"
        print(f"  {info[k]['name']} | {info[k]['type']} | {info[k]['years']:.1f}년 | {val} | 기준 {v['기준']}")

print("\n[KM확률 상위 100 업태]", sorted(((sum(1 for k in tops['KM확률'] if info[k]['type'] == t), t) for t in {info[k]['type'] for k in tops['KM확률']}), reverse=True)[:8])
print("[평균배수 상위 100 업태]", sorted(((sum(1 for k in tops['평균배수'] if info[k]['type'] == t), t) for t in {info[k]['type'] for k in tops['평균배수']}), reverse=True)[:8])
ones = [v["KM생존확률"] for v in res.values()]
print("\nKM 생존확률이 업태의 가장 낮은 값인 가게 수(동점 규모):", sum(1 for k, v in res.items() if v["KM생존확률"] == min(s for _, s in base[info[k]["type"]]["curve"])))

with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["관리번호", "상호", "업태", "인허가일", "업력_년", "평균배수", "중위배수", "폐업평균배수", "KM배수", "KM생존확률", "기준그룹"])
    for k, v in sorted(res.items(), key=lambda p: p[1]["KM생존확률"]):
        i = info[k]
        rd = lambda x: round(x, 3) if x is not None else ""
        w.writerow([k, i["name"], i["type"], i["start"], round(i["years"], 2), rd(v["평균배수"]), rd(v["중위배수"]), rd(v["폐업평균배수"]), rd(v["KM배수"]), rd(v["KM생존확률"]), v["기준"]])
print(f"\n저장 완료: {OUT}")
