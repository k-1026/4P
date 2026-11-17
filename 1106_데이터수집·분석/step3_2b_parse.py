"""
3-2단계 정리: 저장된 카카오맵 원본에서 영업 정보를 뽑아 식당별 표로 만듦 (인터넷 접속 없음)

필요한 것: base_중구_대봉1동.csv, kakao_연결정리_중구_대봉1동.csv, kakao_raw 폴더
실행: python step3_2b_parse.py
결과: kakao_영업정보_중구_대봉1동.csv (기본표 전체 식당, 기본표 파일은 수정하지 않음)

빈칸의 뜻: '정보 없음'. '해당 사항 없음'이 아님 (예: 브레이크타임이 비어 있어도 없다고 단정 못 함)
요일별 칸은 수집 시점에서 앞으로 7일의 표(week_from_today) 기준
"""
import csv
import datetime
import json
import os
import re
from collections import Counter

AREA = "중구_대봉1동"
RAW_DIR = "kakao_raw"
WEEK = ["월", "화", "수", "목", "금", "토", "일"]


def read(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def summarize(by_day):
    """{요일: 값} → 모든 영업일이 같으면 값 하나, 다르면 '월 값; 화 값'"""
    vals = {d: v for d, v in by_day.items() if v}
    if not vals:
        return ""
    if len(set(vals.values())) == 1 and len(vals) == len(by_day):
        return next(iter(vals.values()))
    return "; ".join(f"{d} {vals[d]}" for d in WEEK if d in vals)


def clean(items, word):
    return ", ".join(re.sub(rf"\s*{word}\s*$", "", x).strip() for x in (items or []))


def parse(data):
    h = data.get("open_hours") or {}
    add = h.get("headline_addition") or {}
    full = h.get("all") or {}
    out = {d: "" for d in WEEK}
    breaks, lasts, off = {}, {}, []
    for per in (h.get("week_from_today") or {}).get("week_periods") or []:
        for x in per.get("days") or []:
            day = (x.get("day_of_the_week_desc") or "")[:1]
            if day not in out:
                continue
            on = x.get("on_days") or {}
            if on:
                out[day] = on.get("start_end_time_desc", "")
                breaks[day] = clean(on.get("break_times_desc"), "브레이크타임")
                lasts[day] = clean(on.get("last_order_times_desc"), "라스트오더")
            elif "off_days_desc" in x:
                out[day] = "휴무"
                off.append(day)

    days_off = add.get("days_off_desc") or full.get("days_off_desc") or ""
    holiday = ""
    for per in full.get("periods") or []:
        if per.get("period_title") == "공휴일":
            holiday = ", ".join((x.get("on_days") or {}).get("start_end_time_desc", "") or x.get("off_days_desc", "")
                                for x in per.get("days") or [])
    notes = [add.get("business_hours_desc") or full.get("business_hours_desc") or "", add.get("current_off_day_desc") or ""]
    menus = ((data.get("menu") or {}).get("menus") or {}).get("items") or []
    score = (data.get("kakaomap_review") or {}).get("score_set") or {}
    return {
        **{f"{d}요일": out[d] for d in WEEK},
        "휴무일": ", ".join(d for d in WEEK if d in off) or days_off,
        "브레이크타임": summarize(breaks),
        "마지막주문": summarize(lasts),
        "공휴일영업": holiday,
        "영업안내": " / ".join(n.replace("\n", " ").strip() for n in notes if n),
        "메뉴수": len(menus),
        # 카카오는 가격이 없는 메뉴의 price를 -1로 줌 → 가격 칸을 비움
        "메뉴": " / ".join(f"{m.get('name', '')} {m.get('price') if (m.get('price') or -1) > 0 else ''}".strip() for m in menus),
        "가격있는메뉴수": sum(1 for m in menus if (m.get("price") or -1) > 0),
        "리뷰수": score.get("review_count", ""),
        "평점": score.get("average_score", ""),
    }


# 술집 표시 식당 판단: 메뉴 이름에 식사 단어가 있으면 유지
# '탕'·'전골'은 술안주인 경우가 많아(어묵탕, 오뎅탕, 스지전골 등) 식사 근거로 쓰지 않음
MEAL_WORDS = re.compile(r"밥|국수|면|찌개|파스타|우동|소바|정식|리조또|카레")


def bar_decision(menu_text):
    """(판단, 근거 메뉴) 반환. 메뉴가 없거나 이름이 '메뉴'뿐이면 판단하지 않음"""
    names = [re.sub(r"\s+[\d,]+원?$", "", m).strip() for m in menu_text.split(" / ") if m.strip()]
    names = [n for n in names if n != "메뉴"]
    if not names:
        return "확인 필요", ""
    meals = [n for n in names if MEAL_WORDS.search(n) and "전골" not in n]
    return ("유지", ", ".join(meals[:5])) if meals else ("제외 후보", "")


base = {b["상가ID"]: b for b in read(f"base_{AREA}.csv")}
links = read(f"kakao_연결정리_{AREA}.csv")
empty = {k: "" for k in parse({})}

rows = []
for r in links:
    b = base[r["상가ID"]]
    row = {
        "상가ID": r["상가ID"], "상호": r["상호"], "지점": r["지점"], "상가업종": b["업종"],
        "도로명주소": b["도로명주소"], "위도": b["위도"], "경도": b["경도"],
        "연결상태": r["상태"], "카카오ID": r["카카오ID"], "카카오상호": r["카카오상호"],
        "카카오분류": r["카카오분류"], "술집표시": r["술집표시"], "중복ID": r["중복ID"],
        **empty, "자동수집_출처": "", "자동수집_일시": "", "place_url": r["place_url"],
    }
    path = os.path.join(RAW_DIR, f"{r['카카오ID']}.json")
    if r["카카오ID"] and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            row.update(parse(json.load(f)))
        row["자동수집_출처"] = "카카오맵"
        row["자동수집_일시"] = datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
    row["식사판단"], row["식사판단_근거"] = bar_decision(row["메뉴"]) if row["술집표시"] else ("", "")
    # 사용자 확정(2026-11-05): 제외 후보는 범위 밖으로 표시. 데이터는 표에 남김
    row["범위"] = "제외" if row["식사판단"] == "제외 후보" else "포함"
    rows.append(row)

out_file = f"kakao_영업정보_{AREA}.csv"
with open(out_file, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

has_hours = [r for r in rows if any(r[f"{d}요일"] not in ("", "휴무") for d in WEEK)]
print(f"전체 {len(rows)}곳 / 카카오 원본 있음 {sum(1 for r in rows if r['자동수집_출처'])}곳")
print(f"영업시간 있음 {len(has_hours)}곳 (연결 {sum(1 for r in has_hours if r['연결상태'] == '연결')}, 확인 필요 {sum(1 for r in has_hours if r['연결상태'] == '확인 필요')})")
for col in ("휴무일", "브레이크타임", "마지막주문", "공휴일영업", "영업안내", "메뉴"):
    print(f"{col} 있음 {sum(1 for r in rows if r[col])}곳")
print("휴무일 값 상위:", Counter(r["휴무일"] for r in rows if r["휴무일"]).most_common(6))
print(f"가격 있는 메뉴가 1개 이상: {sum(1 for r in rows if r['가격있는메뉴수'])}곳")
keep = [r for r in rows if r["범위"] == "포함"]
print(f"범위 포함 {len(keep)}행, 제외 {len(rows) - len(keep)}행: " + ", ".join(r["상호"] for r in rows if r["범위"] == "제외"))
print(f"범위 포함 중 영업시간 있음 {sum(1 for r in keep if any(r[f'{d}요일'] not in ('', '휴무') for d in WEEK))}행, 카카오 못 찾음 {sum(1 for r in keep if not r['카카오ID'])}행, 확인 필요 {sum(1 for r in keep if r['연결상태'] == '확인 필요')}행")
print("술집 표시 판단:", dict(Counter(r["식사판단"] for r in rows if r["술집표시"])))
for r in rows:
    if r["술집표시"]:
        print(f"- [{r['식사판단']}] {r['카카오상호']} | 근거: {r['식사판단_근거']} | 메뉴: {r['메뉴'][:90]}")
print(f"저장 완료: {out_file}")
