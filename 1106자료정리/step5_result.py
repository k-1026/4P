"""
버틴집 가설 시험 4단계: 사전에 정한 기준으로 판정 (인터넷 접속 없음)

기준 (평점 계산 전에 합의)
  ① 상위군 업력 의심 30곳 중 6곳 이하
  ② 카카오 평점 중앙값 차이 0.3점 이상 (리뷰 5개 이상, 집단별 15곳 이상)
업력 의심은 평점을 보기 전에 상호·업태·메뉴로 사람(Claude)이 추정한 값이며 확인된 사실이 아님
결과: 시험결과_중구.csv
"""
import csv
import json
import os
import statistics as st

STRICT = {"S07", "S08", "S28", "S32", "S34", "S37", "S40"}     # 메뉴·상호가 30년 이상 업력과 강하게 어긋남
BROAD = STRICT | {"S01", "S04", "S19", "S38", "S39", "S43"}    # 추가 의심
MIN_REVIEW = 5

rows = []
with open("시험표본_카카오ID.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        path = f"kakao_raw/{r['카카오ID']}.json"
        s, n, hours, menus = None, 0, False, 0
        if r["카카오ID"] and os.path.exists(path):
            d = json.load(open(path, encoding="utf-8"))
            sc = (d.get("kakaomap_review") or {}).get("score_set") or {}
            n = int(sc.get("review_count") or 0)
            s = sc.get("average_score")
            hours = bool((d.get("open_hours") or {}).get("week_from_today"))
            menus = len(((d.get("menu") or {}).get("menus") or {}).get("items") or [])
        r.update(리뷰수=n, 평점=s if s is not None else "", 영업시간=hours, 메뉴수=menus,
                 업력의심="엄격" if r["시험번호"] in STRICT else ("넓게" if r["시험번호"] in BROAD else ""))
        rows.append(r)

with open("시험결과_중구.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)


def summary(label, items):
    rated = [float(r["평점"]) for r in items if r["평점"] != "" and r["리뷰수"] >= MIN_REVIEW]
    linked = [r for r in items if r["카카오ID"]]
    print(f"[{label}] {len(items)}곳 | 카카오 있음 {len(linked)} | 영업시간 등록 {sum(1 for r in items if r['영업시간'])} | 리뷰 {MIN_REVIEW}개 이상 {len(rated)}곳 | "
          f"평점 중앙 {st.median(rated) if rated else '-'} | 평균 {round(st.mean(rated), 2) if rated else '-'} | 범위 {min(rated) if rated else '-'}~{max(rated) if rated else '-'} | "
          f"리뷰수 중앙 {st.median([r['리뷰수'] for r in linked]) if linked else '-'}")
    return rated


top = [r for r in rows if r["집단"] == "상위"]
ctrl = [r for r in rows if r["집단"] == "비교"]
a = summary("상위", top)
b = summary("비교", ctrl)
print("\n① 업력 의심: 엄격", sum(1 for r in top if r["업력의심"] == "엄격"), "/ 넓게 포함", sum(1 for r in top if r["업력의심"]), "/ 기준 6곳 이하")
if a and b:
    print("② 평점 중앙값 차이:", round(st.median(a) - st.median(b), 2), "/ 기준 0.3 이상 / 표본 기준 집단별 15곳 이상:", len(a), len(b))
print("\n[민감도] 업력 의심을 뺀 상위군")
summary("상위-엄격 제외", [r for r in top if r["업력의심"] != "엄격"])
summary("상위-넓게 제외", [r for r in top if not r["업력의심"]])
print("\n[민감도] 리뷰 기준을 바꿀 때 평점 중앙값 차이")
for m in (1, 3, 5, 10):
    x = [float(r["평점"]) for r in top if r["평점"] != "" and r["리뷰수"] >= m]
    y = [float(r["평점"]) for r in ctrl if r["평점"] != "" and r["리뷰수"] >= m]
    if x and y:
        print(f"리뷰 {m}개 이상: 상위 {len(x)}곳 {st.median(x)} / 비교 {len(y)}곳 {st.median(y)} / 차이 {round(st.median(x) - st.median(y), 2)}")
print("저장 완료: 시험결과_중구.csv")
