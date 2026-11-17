"""
3-1단계 정리: 1차·2차 카카오 연결 결과를 합쳐 3-2단계 수집 대상을 만듦 (인터넷 접속 없음)

하는 일
  1. 1차 결과에 2차에서 찾은 곳을 합침 (단, REJECT_2ND에 적은 잘못된 연결은 제외)
  2. 카카오 분류가 술집인 곳에 '술집표시' = O (제외하지 않음, 메뉴를 본 뒤 판단)
  3. 같은 카카오 ID를 가리키는 식당에 '중복ID' = O
  4. 수집 대상은 카카오 ID 기준으로 중복 제거

필요한 파일: kakao_ids_중구_대봉1동.csv, kakao_ids_2차_중구_대봉1동.csv
결과
  kakao_연결정리_중구_대봉1동.csv   기본표 전체 식당의 연결 상태
  kakao_수집대상_중구_대봉1동.csv   3-2단계에서 수집할 카카오 장소 목록

실행: python step3_1c_merge.py
"""
import csv
from collections import Counter

AREA = "중구_대봉1동"

# 2차 검색에서 상호를 대조해 잘못 찾은 것으로 판단한 곳 (상호 기준)
REJECT_2ND = {"집밥이좋다대백", "미채담대백", "보양밥상현미김밥대백", "막창도둑"}


def read(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


first = read(f"kakao_ids_{AREA}.csv")
second = {r["상가ID"]: r for r in read(f"kakao_ids_2차_{AREA}.csv")}

rows = []
for r in first:
    row = {
        "상가ID": r["상가ID"], "상호": r["상호"], "지점": r["지점"], "상태": r["상태"], "검색차수": "1차",
        "카카오ID": r["카카오ID"], "카카오상호": r["카카오상호"], "거리_m": r["거리_m"],
        "카카오분류": r["카카오분류"], "카카오주소": r["카카오주소"], "place_url": r["place_url"],
    }
    s = second.get(r["상가ID"])
    if s and s["상태"] == "확인 필요" and s["상호"] not in REJECT_2ND:
        row.update({k: s[k] for k in ("상태", "카카오ID", "카카오상호", "거리_m", "카카오분류", "카카오주소", "place_url")})
        row["검색차수"] = "2차"
    if not row["카카오ID"]:
        row["검색차수"] = ""
    rows.append(row)

id_count = Counter(r["카카오ID"] for r in rows if r["카카오ID"])
for r in rows:
    r["술집표시"] = "O" if "술집" in r["카카오분류"] else ""
    r["중복ID"] = "O" if id_count[r["카카오ID"]] > 1 else ""

with open(f"kakao_연결정리_{AREA}.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

targets, seen = [], set()
for r in rows:
    if r["카카오ID"] and r["카카오ID"] not in seen:
        seen.add(r["카카오ID"])
        targets.append({k: r[k] for k in ("카카오ID", "카카오상호", "상태", "술집표시", "카카오분류", "카카오주소", "place_url")})

with open(f"kakao_수집대상_{AREA}.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(targets[0].keys()))
    w.writeheader()
    w.writerows(targets)

stat = Counter(r["상태"] for r in rows)
print(f"기본표 {len(rows)}곳: " + ", ".join(f"{k} {v}곳" for k, v in stat.items()))
print(f"같은 카카오 ID를 가리키는 식당: {sum(1 for r in rows if r['중복ID'])}곳")
print(f"수집 대상 카카오 장소: {len(targets)}곳")
print(f"  그중 연결 {sum(1 for t in targets if t['상태'] == '연결')}곳, 확인 필요 {sum(1 for t in targets if t['상태'] == '확인 필요')}곳")
print(f"  그중 술집 표시 {sum(1 for t in targets if t['술집표시'])}곳")
