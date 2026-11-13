"""
버틴집 가설 시험 보강: 상위군 30곳의 인허가 변경 이력 확인 (식약처 15145167)

개인정보 보호: 변경 전후 내용(대표자 이름이 들어 있을 수 있음)은 파일에 저장하지 않고,
               형태로 유형만 추정해 날짜와 함께 저장
유형 추정: 이 API에는 변경 구분 칸이 없어 내용 형태로 판단하며, 확정 정보가 아님
  상호 추정     변경 후 내용이 현재 상호와 겹침
  주소 추정     숫자나 로·길·동이 들어간 긴 글
  대표자 추정   전후 모두 한글 2~4자
필요한 것: 환경변수 DATA_GO_KR_KEY, 시험결과_중구.csv
결과: 시험_변경이력_상위군.csv
"""
import csv
import os
import re
import sys
import time
from collections import Counter

import requests

KEY = os.environ.get("DATA_GO_KR_KEY")
if not KEY:
    sys.exit("DATA_GO_KR_KEY 환경변수가 없습니다.")
URL = "https://apis.data.go.kr/1471000/FoodRstrtLcnsChgInfo01/getFoodRstrtLcnsChgInfo01"


def clean(s):
    return re.sub(r"\(.*?\)|\s", "", s or "")


def kind(name, bf, af):
    a, b = (af or "").strip(), (bf or "").strip()
    n = clean(name)
    if n and (n in clean(a) or clean(a) in n and clean(a)):
        return "상호 추정"
    if re.fullmatch(r"[가-힣]{2,4}", a) and re.fullmatch(r"[가-힣]{2,4}", b):
        return "대표자 추정"
    if re.search(r"\d", a + b) and re.search(r"[로길동가리]", a + b) and len(a + b) > 12:
        return "주소 추정"
    return "기타"


def fetch(name):
    out, page = [], 1
    while True:
        for attempt in range(4):   # 서버 연결이 끊기면 기다렸다가 최대 3번 더 시도
            try:
                r = requests.get(URL, timeout=(15, 60), params={"serviceKey": KEY, "type": "json", "numOfRows": 100, "pageNo": page, "BSSH_NM": name})
                break
            except requests.RequestException as e:
                if attempt == 3:
                    sys.exit(f"요청 실패: {type(e).__name__}")
                time.sleep(20 * (attempt + 1))
        if r.status_code != 200:
            sys.exit(f"상태 {r.status_code}: {r.text[:150].replace(KEY, '***')}")
        body = r.json()["body"]
        items = body.get("items") or []
        out += items
        if int(body.get("totalCount") or 0) > 3000:   # '원'처럼 짧은 상호는 전국 기록이 너무 많아 건너뜀
            print("기록 과다, 건너뜀", name, body.get("totalCount"), flush=True)
            return [], int(body.get("totalCount") or 0)
        if len(out) >= int(body.get("totalCount") or 0) or not items:
            return out, int(body.get("totalCount") or 0)
        page += 1
        time.sleep(0.3)


with open("시험결과_중구.csv", encoding="utf-8-sig") as f:
    top = [r for r in csv.DictReader(f) if r["집단"] == "상위"]

OUT = "시험_변경이력_상위군.csv"
COLS = ["시험번호", "상호", "업력_년", "업력의심", "전국_같은상호_변경건수", "중구_변경건수", "인허가번호종류", "대표자추정_건수", "상호추정_건수", "가장_이른_변경", "마지막_대표자_상호변경", "변경후_업력_년", "유형"]
rows = []
if os.path.exists(OUT):     # 이미 받은 가게는 다시 요청하지 않음
    with open(OUT, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
done = {r["시험번호"] for r in rows}
for t in sorted(top, key=lambda r: r["시험번호"]):
    if t["시험번호"] in done:
        continue
    print("조회", t["시험번호"], flush=True)
    name = re.sub(r"\(.*?\)", "", t["상호"]).strip()
    items, total = fetch(name)
    time.sleep(0.3)
    near = [i for i in items if "대구" in str(i.get("BSN_LCTN_ADDR")) and "중구" in str(i.get("BSN_LCTN_ADDR")) and clean(i.get("BSSH_NM")) == clean(name)]
    kinds = [(str(i.get("CHNG_DT")), kind(name, i.get("CHNG_BF_CN"), i.get("CHNG_AF_CN"))) for i in near]
    owner = sorted(d for d, k in kinds if k == "대표자 추정")
    named = sorted(d for d, k in kinds if k == "상호 추정")
    last = max(owner + named) if owner + named else ""
    age_since = round((2026 + 10 / 12) - (int(last[:4]) + (int(last[4:6]) - 1) / 12), 1) if last else ""
    rows.append({"시험번호": t["시험번호"], "상호": t["상호"], "업력_년": t["업력_년"], "업력의심": t["업력의심"], "전국_같은상호_변경건수": total, "중구_변경건수": len(near),
                 "인허가번호종류": len({i.get("PRMT_NO") for i in near}), "대표자추정_건수": len(owner), "상호추정_건수": len(named), "가장_이른_변경": min((d for d, _ in kinds), default=""),
                 "마지막_대표자_상호변경": last, "변경후_업력_년": age_since, "유형": dict(Counter(k for _, k in kinds))})
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:   # 한 곳 받을 때마다 저장
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)

for r in rows:
    print(f"{r['시험번호']} {r['상호']} | {float(r['업력_년']):.0f}년 | 의심 {r['업력의심'] or '-'} | 중구 {r['중구_변경건수']}건 번호 {r['인허가번호종류']} | 대표 {r['대표자추정_건수']} 상호 {r['상호추정_건수']} | 첫 {r['가장_이른_변경'] or '-'} | 마지막 {r['마지막_대표자_상호변경'] or '-'} | 변경후 {r['변경후_업력_년'] or '-'}년 | {r['유형']}")
hit = [r for r in rows if int(r["중구_변경건수"])]
dates = sorted(r["가장_이른_변경"] for r in hit if r["가장_이른_변경"])
print(f"\n변경 기록 있음 {len(hit)}/{len(rows)}, 대표자 추정 변경 {sum(1 for r in rows if int(r['대표자추정_건수']))}곳, 가장 이른 기록 {dates[0] if dates else '-'}")
print("저장 완료: 시험_변경이력_상위군.csv (변경 내용은 저장하지 않음)")
