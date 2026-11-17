"""
버틴집 가설 시험 1단계: 표본 고정 (인터넷 접속 없음)

상위군  중구 영업 중 가게 중 생존배수(폐업 평균 대비) 상위 30곳
비교군  상위군과 같은 업태 구성으로, 생존배수 1 미만 가게에서 무작위 30곳 (난수 시드 고정)

제외: 업태 '기타'·'까페' (같은 업종 비교가 안 되거나 식사 범위 밖),
      2026년 이력으로 상호 변경을 확인한 가게와 브랜드 시기가 맞지 않는 '설빙'
한계: 프랜차이즈는 아직 제외하지 못함. 2026년 이전 상호 변경은 상위군에 남아 있을 수 있음

필요한 파일: 버팀지수_비교_중구.csv
결과: 시험표본_중구.csv (같은 입력이면 항상 같은 표본)
"""
import csv
import random
from collections import Counter

SEED = 20261105
N = 30
EXCLUDE_TYPES = {"기타", "까페"}
EXCLUDE_IDS = {
    "3410000-101-1971-00008",  # 핸즈 → 컴포즈커피 (2026 변경 확인)
    "3410000-101-1978-00002",  # 돌담 → 카페 무던 (2026 변경 확인)
    "3410000-101-1978-00006",  # 자야 → 르폴뒤 (2026 변경 확인)
    "3410000-101-1975-00009",  # 성주 → 서문닭강정 (2026 변경 확인)
    "3410000-101-1992-00055",  # 설빙 동성로점 (브랜드 시기 불일치 의심)
}

with open("버팀지수_비교_중구.csv", encoding="utf-8-sig") as f:
    rows = [r for r in csv.DictReader(f) if r["폐업평균배수"]]
pool = [r for r in rows if r["업태"] not in EXCLUDE_TYPES and r["관리번호"] not in EXCLUDE_IDS]
pool.sort(key=lambda r: -float(r["폐업평균배수"]))
top = pool[:N]
top_ids = {r["관리번호"] for r in top}

rng = random.Random(SEED)
low = [r for r in pool if float(r["폐업평균배수"]) < 1 and r["관리번호"] not in top_ids]
need = Counter(r["업태"] for r in top)
control, short = [], 0
for kind, n in sorted(need.items()):
    cands = sorted((r for r in low if r["업태"] == kind), key=lambda r: r["관리번호"])
    pick = rng.sample(cands, min(n, len(cands)))
    control += pick
    short += n - len(pick)
if short:   # 같은 업태가 모자라면 나머지 후보에서 채움
    used = {r["관리번호"] for r in control}
    rest = sorted((r for r in low if r["관리번호"] not in used), key=lambda r: r["관리번호"])
    control += rng.sample(rest, short)

sample = [("상위", r) for r in top] + [("비교", r) for r in control]
rng.shuffle(sample)
with open("시험표본_중구.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["시험번호", "집단", "관리번호", "상호", "업태", "업력_년", "생존배수"])
    for i, (g, r) in enumerate(sample, 1):
        w.writerow([f"S{i:02d}", g, r["관리번호"], r["상호"], r["업태"], r["업력_년"], r["폐업평균배수"]])

def desc(items):
    y = sorted(float(r["업력_년"]) for r in items)
    m = sorted(float(r["폐업평균배수"]) for r in items)
    return f"{len(items)}곳, 업력 {y[0]:.1f}~{y[-1]:.1f}년(중앙 {y[len(y)//2]:.1f}), 생존배수 {m[0]:.2f}~{m[-1]:.2f}"

print("후보", len(pool), "/ 생존배수 1 미만 후보", len(low), "/ 같은 업태 부족으로 대체", short)
print("상위:", desc(top))
print("비교:", desc(control))
print("상위 업태:", Counter(r["업태"] for r in top).most_common())
print("비교 업태:", Counter(r["업태"] for r in control).most_common())
print("저장 완료: 시험표본_중구.csv (상호는 출력하지 않음)")
