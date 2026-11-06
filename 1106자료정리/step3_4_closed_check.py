"""
3-4단계: 행안부 일반음식점 인허가 데이터로 폐업 식당 확인

하는 일
  1. 대구 중구(자치단체코드 3410000) 일반음식점 전체를 받아 저장 (폐업 업소 포함)
     이미 받은 파일이 있으면 다시 받지 않음. 새로 받으려면 그 파일을 지우고 실행
  2. 기본표와 주소 + 상호로 대조해 영업 / 폐업 / 휴업 / 대조 실패로 표시

주의: '대조 실패'는 폐업이라는 뜻이 아님. 인허가 상호가 다르거나 일반음식점이 아닐 수 있음

필요한 것: 환경변수 DATA_GO_KR_KEY, base_중구_대봉1동.csv
실행: python step3_4_closed_check.py
결과: mois_일반음식점_대구중구.csv, 폐업대조_중구_대봉1동.csv (기본표는 수정하지 않음)
"""
import csv
import difflib
import os
import re
import sys
import time
from collections import Counter, defaultdict

import requests

AREA = "중구_대봉1동"
ATMY_CODE = "3410000"
RAW_FILE = "mois_일반음식점_대구중구.csv"
URL = "https://apis.data.go.kr/1741000/general_restaurants/info"
COLS = ["MNG_NO", "BPLC_NM", "ROAD_NM_ADDR", "LOTNO_ADDR", "SALS_STTS_CD", "SALS_STTS_NM", "DTL_SALS_STTS_NM",
        "CLSBIZ_YMD", "LCPMT_YMD", "SNTTN_BZSTAT_NM", "TELNO", "DAT_UPDT_PNT"]
NAME_OK = 0.6

KEY = os.environ.get("DATA_GO_KR_KEY")


def fetch_all():
    if not KEY:
        sys.exit("DATA_GO_KR_KEY 환경변수가 없습니다. 새 명령 프롬프트 창에서 실행해 보세요.")
    rows, page, total = [], 1, None
    while total is None or len(rows) < total:
        try:
            r = requests.get(URL, timeout=60, params={
                "serviceKey": KEY, "pageNo": page, "numOfRows": 100, "returnType": "json",
                "cond[OPN_ATMY_GRP_CD::EQ]": ATMY_CODE,
            })
        except requests.RequestException as e:
            sys.exit(f"{page}쪽 요청 실패: {type(e).__name__}")
        if r.status_code != 200:
            sys.exit(f"{page}쪽 상태 {r.status_code}: {r.text[:200].replace(KEY, '***')}")
        res = r.json()["response"]
        if str(res["header"]["resultCode"]) != "0":
            sys.exit(f"{page}쪽 오류: {res['header']}")
        total = int(res["body"]["totalCount"])
        items = (res["body"].get("items") or {}).get("item") or []
        if not items:
            break
        rows += [{c: i.get(c, "") for c in COLS} for i in items]
        page += 1
        time.sleep(0.2)
    with open(RAW_FILE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"행안부 수집: {len(rows)}건 (전체 {total}건)")
    return rows


def norm(name):
    # 건물·지점 이름은 다른 업소끼리도 겹치므로 상호 비교에서 뺌 (예: 알마튜나 대백프라자점 ≠ 요바나시 대백프라자)
    name = re.sub(r"대구백화점|대백프라자점?|대백\s*프라자점?|프라자점|대봉점", "", name or "")
    return re.sub(r"[\s()\[\]·\-_.,&;]|본점|별관|분점|직영점|식당|대구|대백|주식회사|\(주\)", "", name).lower()


def score(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0
    if a in b or b in a:
        return max(0.9, difflib.SequenceMatcher(None, a, b).ratio())
    return difflib.SequenceMatcher(None, a, b).ratio()


def jibun_key(addr):
    m = re.search(r"(\S+(?:동|가))\s+(?:산\s*)?(\d+)(?:-(\d+))?", addr or "")
    if not m:
        return None
    return m.group(1), int(m.group(2)), int(m.group(3) or 0)


def road_key(addr):
    m = re.search(r"(\S+(?:로|길))\s*(\d+)(?:-(\d+))?", addr or "")
    if not m:
        return None
    return m.group(1), int(m.group(2)), int(m.group(3) or 0)


def read(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


mois = read(RAW_FILE) if os.path.exists(RAW_FILE) else fetch_all()
print("행안부 영업상태:", dict(Counter(m["SALS_STTS_NM"] for m in mois)))

by_jibun, by_road, by_name = defaultdict(list), defaultdict(list), defaultdict(list)
for m in mois:
    k = jibun_key(m["LOTNO_ADDR"].replace("대구광역시", "").replace("중구", "", 1))
    if k:
        by_jibun[k].append(m)
    k = road_key(m["ROAD_NM_ADDR"].replace("대구광역시", "").replace("중구", "", 1))
    if k:
        by_road[k].append(m)
    by_name[norm(m["BPLC_NM"])].append(m)

kakao = {r["상가ID"]: r for r in read(f"kakao_영업정보_{AREA}.csv")}
rows = []
for b in read(f"base_{AREA}.csv"):
    name = b["상호"] + b["지점"]
    cands = []
    k = jibun_key(b["지번주소"].replace("대구광역시", "").replace("중구", "", 1))
    if k:
        cands += by_jibun.get(k, [])
    k = road_key(b["도로명주소"].replace("대구광역시", "").replace("중구", "", 1))
    if k:
        cands += by_road.get(k, [])
    uniq = {c["MNG_NO"]: c for c in cands}.values()

    hits = sorted(((score(name, c["BPLC_NM"]), c) for c in uniq), key=lambda p: -p[0])
    good = [c for s, c in hits if s >= NAME_OK]
    how = "주소+상호" if good else ""
    if not good:      # 주소가 달라도 중구에 같은 상호가 1건뿐이면 참고로 연결
        same = by_name.get(norm(b["상호"]), [])
        if len(same) == 1 and len(norm(b["상호"])) >= 3:
            good, how = same, "상호만"

    open_ = [c for c in good if c["SALS_STTS_CD"] == "01"]
    if not good:
        status, pick = "대조 실패", None
    elif open_:
        status, pick = "영업", open_[0]
    else:
        pick = sorted(good, key=lambda c: c["CLSBIZ_YMD"] or "", reverse=True)[0]
        status = pick["SALS_STTS_NM"]

    same_addr_open = [c["BPLC_NM"] for s, c in hits if s < NAME_OK and c["SALS_STTS_CD"] == "01"]
    kr = kakao.get(b["상가ID"], {})
    rows.append({
        "상가ID": b["상가ID"], "상호": b["상호"], "지점": b["지점"], "도로명주소": b["도로명주소"],
        "카카오연결": kr.get("연결상태", ""), "범위": kr.get("범위", ""),
        "행안부판정": status, "대조방법": how,
        "행안부상호": pick["BPLC_NM"] if pick else "",
        "상세상태": pick["DTL_SALS_STTS_NM"] if pick else "",
        "폐업일자": pick["CLSBIZ_YMD"] if pick else "",
        "행안부업태": pick["SNTTN_BZSTAT_NM"] if pick else "",
        "행안부주소": (pick["ROAD_NM_ADDR"] or pick["LOTNO_ADDR"]) if pick else "",
        "같은주소_영업중_다른상호": " / ".join(same_addr_open[:4]),
    })

out = f"폐업대조_{AREA}.csv"
with open(out, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print("기본표 판정:", dict(Counter(r["행안부판정"] for r in rows)))
print("대조방법:", dict(Counter(r["대조방법"] for r in rows)))
print("표:", dict(Counter((r["카카오연결"], r["행안부판정"]) for r in rows)))
print("카카오 있는데 행안부 폐업:")
for r in rows:
    if r["카카오연결"] != "없음" and r["행안부판정"] not in ("영업", "대조 실패"):
        print(f"  {r['상호']} {r['지점']} | {r['행안부판정']} {r['폐업일자']} | {r['행안부상호']} | {r['대조방법']} | 같은주소 영업: {r['같은주소_영업중_다른상호']}")
print("카카오 없음 + 행안부 대조 실패:")
for r in rows:
    if r["카카오연결"] == "없음" and r["행안부판정"] == "대조 실패":
        print(f"  {r['상호']} {r['지점']} | 같은주소 영업: {r['같은주소_영업중_다른상호']}")
print("카카오 없음 + 행안부 영업/폐업:")
for r in rows:
    if r["카카오연결"] == "없음" and r["행안부판정"] != "대조 실패":
        print(f"  {r['상호']} {r['지점']} → {r['행안부판정']} {r['폐업일자']} | {r['행안부상호']} | {r['대조방법']}")
print(f"저장 완료: {out}")
