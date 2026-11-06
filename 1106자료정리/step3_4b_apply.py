"""
3-4단계 정리: 카카오 영업정보와 행안부 폐업 대조를 합쳐 통합표를 만듦 (인터넷 접속 없음)

영업판단 기준 (2026-11-05 사용자 확정, 행은 삭제하지 않음)
  폐업 제외        카카오 없음 + 행안부 폐업 + 주소·상호 일치
  폐업 확인 필요   카카오 있음 + 행안부 폐업, 또는 상호만 일치한 폐업
  영업 불명        카카오 없음 + 행안부 대조 실패
  영업, 정보 없음  카카오 없음 + 행안부 영업
  유지             카카오 있음 + 행안부 영업 또는 대조 실패

필요한 파일: kakao_영업정보_중구_대봉1동.csv, 폐업대조_중구_대봉1동.csv
실행: python step3_4b_apply.py
결과: 식당통합_중구_대봉1동.csv
"""
import csv
from collections import Counter

AREA = "중구_대봉1동"
WEEK = ["월", "화", "수", "목", "금", "토", "일"]


def read(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def decide(kakao, mois, how):
    if mois == "폐업":
        return "폐업 제외" if kakao == "없음" and how == "주소+상호" else "폐업 확인 필요"
    if kakao == "없음":
        return "영업 불명" if mois == "대조 실패" else "영업, 정보 없음"
    return "유지"


info = read(f"kakao_영업정보_{AREA}.csv")
check = {r["상가ID"]: r for r in read(f"폐업대조_{AREA}.csv")}
if len(check) != len(info):
    raise SystemExit(f"행 수가 맞지 않습니다: 영업정보 {len(info)}, 폐업대조 {len(check)}")

rows = []
for r in info:
    c = check[r["상가ID"]]
    row = dict(r)
    row["행안부판정"] = c["행안부판정"]
    row["행안부대조방법"] = c["대조방법"]
    row["행안부상호"] = c["행안부상호"]
    row["폐업일자"] = c["폐업일자"]
    row["영업판단"] = decide(r["연결상태"], c["행안부판정"], c["대조방법"])
    reasons = []
    if r["범위"] == "제외":
        reasons.append("술집(식사 메뉴 없음)")
    if row["영업판단"] == "폐업 제외":
        reasons.append("폐업")
    row["범위"] = "제외" if reasons else "포함"
    row["제외사유"] = ", ".join(reasons)
    rows.append(row)

out = f"식당통합_{AREA}.csv"
with open(out, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

has_hours = lambda r: any(r[f"{d}요일"] not in ("", "휴무") for d in WEEK)
keep = [r for r in rows if r["범위"] == "포함"]
print("영업판단 (174행):", dict(Counter(r["영업판단"] for r in rows)))
print("범위:", dict(Counter(r["범위"] for r in rows)), "/ 제외사유:", dict(Counter(r["제외사유"] for r in rows if r["제외사유"])))
print("범위 포함 영업판단:", dict(Counter(r["영업판단"] for r in keep)))
print("범위 포함 + 영업시간 있음:", dict(Counter(r["영업판단"] for r in keep if has_hours(r))), "합계", sum(1 for r in keep if has_hours(r)))
print("범위 포함 + 휴무일/브레이크/마지막주문 있음:", sum(1 for r in keep if r["휴무일"]), sum(1 for r in keep if r["브레이크타임"]), sum(1 for r in keep if r["마지막주문"]))
print("폐업 확인 필요:", ", ".join(r["상호"] for r in rows if r["영업판단"] == "폐업 확인 필요"))
print(f"저장 완료: {out}")
