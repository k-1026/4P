"""
2단계: 한 구역 기본표 만들기

하는 일
  1. 상가정보(대구 전체)에서 정한 구역의 '식사 음식점'만 골라냄 (카페·주점·빵집 등 제외)
  2. 맛집 API 데이터에 같은 식당이 있으면 영업시간·메뉴·좌석을 붙임 (주소 + 상호로 자동 연결)
  3. 3단계에서 자동으로 채울 빈 칸을 만들어 CSV로 저장

필요한 파일 (같은 폴더에 있어야 함)
  sangga_daegu_all_food.csv   (sangga_daegu_all.py 실행 결과)
  matjib_daegu_all.csv        (matjib_all_daegu.py 실행 결과)

실행
  python step2_build_base.py

구역을 바꾸려면 아래 AREA_GU, AREA_DONG 두 줄만 고치면 됨
결과: base_중구_대봉1동.csv
"""
import csv
import difflib
import html
import re
import sys
from collections import Counter, defaultdict

# ===== 구역 설정 (여기만 바꾸면 다른 구역) =====
AREA_GU = "중구"
AREA_DONG = "대봉1동"   # 행정동 이름 (상가정보의 adongNm 기준)
# =============================================

SANGGA_FILE = "sangga_daegu_all_food.csv"
MATJIB_FILE = "matjib_daegu_all.csv"
OUT_FILE = f"base_{AREA_GU}_{AREA_DONG}.csv"

# 식사 음식점이 아닌 업종 (상가정보 업종 중분류·소분류 기준)
EXCLUDE_MID = {"주점", "비알코올"}
EXCLUDE_SMALL = {"카페", "빵/도넛", "떡/한과", "아이스크림/빙수", "구내식당"}


def read_csv(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    except FileNotFoundError:
        sys.exit(f"{path} 파일이 이 폴더에 없습니다.")


def norm_name(name):
    """상호 비교용: 띄어쓰기·괄호·'본점' 같은 말을 지움"""
    name = html.unescape(name or "")
    return re.sub(r"[\s()\[\]·\-_.,&;]|본점|별관|분점|직영점|식당|대구", "", name).lower()


def jibun_key(addr):
    """지번 주소에서 (동, 번지) 추출. 예: '대봉동 4-1' -> ('대봉동', '4-1')"""
    m = re.search(r"(\S+(?:동|가|리))\s+(?:산\s*)?(\d+(?:-\d+)?)", addr or "")
    return (m.group(1), m.group(2)) if m else None


def road_key(addr):
    """도로명 주소에서 (도로명, 건물번호) 추출. 예: '달구벌대로 2100' -> ('달구벌대로', '2100')"""
    m = re.search(r"(\S+(?:로|길))\s*(\d+(?:-\d+)?)", addr or "")
    return (m.group(1), m.group(2)) if m else None


def similar(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


sangga = read_csv(SANGGA_FILE)
matjib = read_csv(MATJIB_FILE)

# 1) 구역 + 식사 음식점만
area = [
    s for s in sangga
    if s["signguNm"] == AREA_GU and s["adongNm"] == AREA_DONG
    and s["indsMclsNm"].strip() not in EXCLUDE_MID
    and s["indsSclsNm"].strip() not in EXCLUDE_SMALL
]
if not area:
    dongs = sorted({s["adongNm"] for s in sangga if s["signguNm"] == AREA_GU})
    sys.exit(f"{AREA_GU} {AREA_DONG}에 해당하는 식당이 없습니다. 가능한 행정동: {', '.join(dongs)}")

# 2) 맛집 API를 주소로 찾을 수 있게 정리 (같은 구만)
mj_by_jibun = defaultdict(list)
mj_by_road = defaultdict(list)
mj_in_gu = []
for m in matjib:
    if m.get("구군") != AREA_GU:
        continue
    mj_in_gu.append(m)
    addr = m["GNG_CS"].replace("대구광역시", "").replace(AREA_GU, "")
    k = jibun_key(addr)
    if k:
        mj_by_jibun[k].append(m)
    k = road_key(addr)
    if k:
        mj_by_road[k].append(m)


def find_matjib(s):
    """상가정보 식당 1곳에 해당하는 맛집 API 식당을 찾음. (맛집, 연결방법) 반환"""
    name = norm_name(s["bizesNm"] + s["brchNm"])
    cands = []
    k = jibun_key(s["lnoAdr"].replace("대구광역시", "").replace(AREA_GU, ""))
    if k:
        cands += mj_by_jibun.get(k, [])
    k = road_key(s["rdnmAdr"].replace("대구광역시", "").replace(AREA_GU, ""))
    if k:
        cands += mj_by_road.get(k, [])
    for m in cands:
        mn = norm_name(m["BZ_NM"])
        if similar(name, mn) >= 0.5 or (mn and mn in name) or (name and name in mn):
            return m, "주소+상호"
    # 주소가 달라도 같은 구에 같은 이름이 딱 1곳이면 연결
    same = [m for m in mj_in_gu if norm_name(m["BZ_NM"]) == norm_name(s["bizesNm"])]
    if len(same) == 1 and len(norm_name(s["bizesNm"])) >= 3:
        return same[0], "상호"
    return None, ""


# 3) 기본표 만들기
FILL_COLS = ["영업시간", "휴무일", "브레이크타임", "마지막주문", "1인주문", "최소주문", "자동수집_출처", "자동수집_일시"]
rows = []
stat = Counter()
for s in area:
    m, how = find_matjib(s)
    stat["맛집 API 연결" if m else "연결 없음"] += 1
    row = {
        "상가ID": s["bizesId"],
        "상호": s["bizesNm"],
        "지점": s["brchNm"],
        "업종": s["indsSclsNm"],
        "도로명주소": s["rdnmAdr"],
        "지번주소": s["lnoAdr"],
        "위도": s["lat"],
        "경도": s["lon"],
        "맛집ID": m["OPENDATA_ID"] if m else "",
        "맛집_연결방법": how,
        "맛집_영업시간": m["MBZ_HR"] if m else "",
        "맛집_메뉴": html.unescape(m["MNU"]) if m else "",
        "맛집_좌석": m["SEAT_CNT"] if m else "",
        "맛집_전화": m["TLNO"] if m else "",
    }
    for c in FILL_COLS:
        row[c] = ""
    rows.append(row)

with open(OUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print(f"구역: {AREA_GU} {AREA_DONG}")
print(f"식사 음식점: {len(rows)}곳")
print(f"  맛집 API와 연결: {stat['맛집 API 연결']}곳")
print(f"  연결 없음(3단계에서 자동 수집 필요): {stat['연결 없음']}곳")
print("업종 상위:", ", ".join(f"{k} {v}" for k, v in Counter(r['업종'] for r in rows).most_common(5)))
print(f"저장 완료: {OUT_FILE}")
