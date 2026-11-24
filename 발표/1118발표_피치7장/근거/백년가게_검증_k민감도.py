"""백년가게 검증 + k 민감도: 생존배수(주변 폐업 k곳 평균 대비) 상위에 백년가게가 얼마나 드는가."""
import csv, math, sys, json, random, re
from collections import defaultdict

base_path, bnk_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
FLOOR = 30 / 365
rows = list(csv.DictReader(open(base_path, encoding="utf-8-sig")))

def xy(r):
    try:
        la, lo = float(r["위도"]), float(r["경도"])
    except ValueError:
        return None
    return (lo * 111320 * math.cos(math.radians(35.87)), la * 110540)

closed, targets = [], []
for r in rows:
    p = xy(r)
    try:
        yrs = float(r["영업연수"])
    except ValueError:
        continue
    if p is None:
        continue
    if r["최종판정"] == "폐업" and r["인허가상태"] == "폐업":
        closed.append((p, max(yrs, FLOOR)))
    elif r["서비스제외_이유"] == "" and r["최종판정"] == "영업중":
        targets.append((r, p, yrs))

CELL = 300
grid = defaultdict(list)
for p, y in closed:
    grid[(int(p[0] // CELL), int(p[1] // CELL))].append((p, y))

def knn_mean(p, k):
    cx, cy = int(p[0] // CELL), int(p[1] // CELL)
    ring, found = 0, []
    while True:
        for dx in range(-ring, ring + 1):
            for dy in range(-ring, ring + 1):
                if max(abs(dx), abs(dy)) != ring:
                    continue
                for q, y in grid.get((cx + dx, cy + dy), ()):
                    found.append(((q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2, y))
        # 반지름 ring*CELL 안은 모두 확인됨
        if len(found) >= k:
            found.sort()
            if math.sqrt(found[k - 1][0]) <= ring * CELL or ring > 40:
                return sum(y for _, y in found[:k]) / k
        ring += 1

def norm(s):
    s = re.sub(r"\(.*?\)|㈜|\s|주식회사", "", s or "")
    return s.lower()

bnk = [r for r in csv.DictReader(open(bnk_path, encoding="utf-8-sig")) if r["상태"] in ("두 판 모두", "2026 신규")]
idx = defaultdict(list)
for i, (r, p, y) in enumerate(targets):
    idx[(norm(r["상호"]), r["구군"])].append(i)
matched = {}
for b in bnk:
    hits = idx.get((norm(b["업체명_2026"]), b["구군"]), [])
    if hits:
        matched[b["업체명_2026"]] = max(hits, key=lambda i: targets[i][2])

def pct_rank(vals):
    order = sorted(range(len(vals)), key=lambda i: vals[i], reverse=True)
    rank = [0] * len(vals)
    for pos, i in enumerate(order):
        rank[i] = (pos + 1) / len(vals) * 100  # 상위 %
    return rank

N = len(targets)
mi = list(matched.values())
random.seed(0)
result = {"서비스대상_영업중_좌표있음": N, "비교풀_폐업": len(closed),
          "백년가게_2026_대구": len(bnk), "매칭": len(mi), "매칭_목록": sorted(matched), "k": {}}

years = [t[2] for t in targets]
ry = pct_rank(years)
def summarize(rank):
    m = sorted(rank[i] for i in mi)
    med = m[len(m) // 2]
    top10 = sum(1 for v in m if v <= 10) / len(m) * 100
    top20 = sum(1 for v in m if v <= 20) / len(m) * 100
    # 무작위 기준선: 같은 수를 1000번 뽑아 중앙값 분포
    sims = []
    for _ in range(1000):
        s = sorted(random.sample(range(N), len(mi)))
        s = sorted(rank[i] for i in s)
        sims.append(s[len(s) // 2])
    p = sum(1 for v in sims if v <= med) / len(sims)
    return {"백년가게_상위%_중앙값": round(med, 1), "상위10%_안_비율": round(top10, 1),
            "상위20%_안_비율": round(top20, 1), "무작위_중앙값_평균": round(sum(sims) / len(sims), 1),
            "무작위보다_같거나_좋을_확률(p)": round(p, 4)}

result["영업연수만"] = summarize(ry)
for k in (5, 10, 20):
    sm = [t[2] / knn_mean(t[1], k) for t in targets]
    r = pct_rank(sm)
    result["k"][k] = summarize(r)
    if k == 10:
        top = sorted(range(N), key=lambda i: sm[i], reverse=True)
        result["k10_상위5_예시"] = [(targets[i][0]["상호"], targets[i][0]["구군"], round(targets[i][2], 1), round(sm[i], 2)) for i in top[:5]]
        result["k10_백년가게_예시"] = [(n, round(targets[i][2], 1), round(sm[i], 2), round(r[i], 1)) for n, i in list(matched.items())[:8]]
        allv = sorted(sm)
        result["k10_생존배수_중앙값"] = round(allv[N // 2], 2)
        result["k10_2배이상_비율"] = round(sum(1 for v in sm if v >= 2) / N * 100, 1)

json.dump(result, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(result, ensure_ascii=False, indent=1))
