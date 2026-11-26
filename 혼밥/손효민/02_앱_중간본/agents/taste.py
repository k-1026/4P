"""취향기록 에이전트: 혼밥일기(별점, 후기)로 사용자의 취향과 최근에 먹은 음식을 알려준다."""
import csv
import json
import os
import re
from datetime import date, datetime

import app_data
import mbti

FOLDER = os.path.dirname(os.path.abspath(__file__))
DIARY = "혼밥일기.json"      # 사용자가 남긴 혼밥일기 (지금은 샘플)
STORES = "가게정보.csv"      # 가게 이름 -> 음식 종류 (메뉴 에이전트가 생기면 그쪽에서 받는다)
PROFILE = "취향요약.json"    # 매일 새로 만드는 취향 요약표
TASTE_PRAISED = 4            # 맛은 칭찬했는데 서비스 때문에 별점이 낮을 때, 음식 종류에 넣는 별점
VERSION = 4                # 요약표 만드는 규칙이 바뀌면 올린다 (같은 날이어도 다시 만듦)

# 음식 종류 11가지. 헷갈리면 ① 국물이 주인공 ② 면이 주인공 ③ 밥 위에 올림 순서로 정한다
CATEGORIES = ("국밥·탕", "찌개", "면", "밥·덮밥", "고기·구이", "튀김·까스",
              "분식", "초밥·회", "빵·패스트푸드", "가벼운 식사", "기타")

# 후기에서 찾을 말 (찾을 글자 모양 -> 보여줄 말). 앞뒤 문맥은 analyze_review()가 본다
GOOD = {r"맛있": "맛있다", r"진하|진해": "진하다", r"든든": "든든하다", r"깔끔": "깔끔하다",
        r"쫄깃": "쫄깃하다", r"푸짐": "푸짐하다", r"(?<!불)친절": "친절하다",
        r"또 가|또 올|또 오": "또 가고 싶다", r"재방문": "재방문", r"최고": "최고",
        r"만족": "만족", r"좋았|좋아요|좋네": "좋다", r"(?<!비)추천": "추천",
        r"맛[은이도]? ?(?:좋|괜찮|훌륭)": "맛이 좋다"}
BAD = {r"짜(?=[고서요다게지네])|짰": "짜다", r"싱겁|싱거": "싱겁다", r"느끼": "느끼하다",
       r"별로": "별로다", r"실망": "실망", r"비싸": "비싸다", r"불친절": "불친절하다",
       r"맛없": "맛없다", r"질기|질겨": "질기다", r"다시는 안|다신 안|두 번은 안": "다시 안 간다",
       r"비추": "비추천", r"그저 그|그냥 그래": "그저 그렇다", r"비리|비려": "비리다",
       r"대기|웨이팅|오래 기다|줄이 길": "오래 기다림", r"좁": "좁다", r"시끄럽|시끄러": "시끄럽다",
       r"지저분|더럽|더러": "지저분하다", r"늦게 나": "늦게 나옴"}
# 맛에 대한 말 / 서비스·가게에 대한 말 ("안 짜다"처럼 '안 '이 붙어도 같은 묶음)
TASTE_WORDS = {"맛있다", "맛이 좋다", "진하다", "쫄깃하다", "짜다", "싱겁다", "느끼하다", "맛없다",
               "질기다", "비리다"}
SERVICE_WORDS = {"불친절하다", "친절하다", "비싸다", "오래 기다림", "좁다", "시끄럽다", "지저분하다",
                 "늦게 나옴"}
IGNORE = ("진짜", "짜장", "짜글", "짜증", "짜리")  # '짜'가 들어가지만 짜다는 뜻이 아닌 말
# 문맥 표시: 앞에 오면 뜻이 뒤집히는 말 / 바로 뒤에 오면 뒤집히는 말 / 뒤에 오면 판단을 미루는 말
NOT_BEFORE = ("안 ", "안", "못 ", "못", "전혀 안 ")
NOT_AFTER = ("지 않", "지않", "진 않", "지는 않", "지도 않", "지 못", "진 못", "지 마", "지 말",
             " 없", "없이", "없어", "가 없", "이 없", "도 없", "는 없")  # "대기 없이", "웨이팅 없어서"
UNSURE_AFTER = ("던데", "다고 해", "다고 들", "길래", "다는데", "줄 알았", "을까", "ㄹ까", "나요?", "다더니")

NO_RECORD = 6  # 그 가게도, 같은 음식 종류도 기록이 없을 때 주는 기본 점수
REPEAT_PENALTY = {0: 3, 1: 3, 2: 1}  # 며칠 전에 같은 종류를 먹었나 -> 빼는 점수 (오늘·어제 -3, 그제 -1)
# 혼밥 MBTI 보정: 탐험파는 안 가본 곳을, 단골파는 가봤던 곳(혼밥일기 별점 4점 이상)을 더 밀어 준다
EXPLORER_NEW, EXPLORER_VISITED = 3, -2   # 탐험파: 안 가본 곳 +3, 가본 곳 -2
REGULAR_VISITED, REGULAR_NEW = 3, -1     # 단골파: 가봤던 곳(별점 4점 이상) +3, 안 가본 곳 -1
REGULAR_OK = 1                           # 단골파: 가봤던 곳(별점 3점 이상 4점 미만) +1, 3점 미만은 0
REPEAT_WORDS = {0: "오늘 이미", 1: "어제", 2: "그제"}


# 받침에 맞는 조사 붙이기: josa("국밥", "은", "는") -> "국밥은"
def josa(word, with_final, without_final):
    last = word[-1] if word else ""
    if not "가" <= last <= "힣":
        return f"{word}{with_final}({without_final})"
    return word + (with_final if (ord(last) - 0xAC00) % 28 else without_final)


# 1. 파일 읽기
def load_stores(folder):
    with open(os.path.join(folder, STORES), encoding="utf-8-sig") as file:
        stores = {row["가게"].strip(): row["음식종류"].strip() for row in csv.DictReader(file)}
    wrong = [name for name, kind in stores.items() if kind not in CATEGORIES]
    if wrong:
        raise ValueError(f"음식 종류가 분류표에 없어요: {', '.join(wrong)}")
    return stores


def load_diary(folder):
    path = os.path.join(folder, DIARY)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as file:
        return json.load(file)


# 2. 후기 분석: 정해진 말을 찾고, 그 말의 앞뒤를 보고 뜻이 뒤집혔는지 판단한다
#    "안 짜서", "느끼하지 않고" -> 뜻이 뒤집힘 / "맛있다던데", "맛있을 줄 알았는데" -> 판단 미룸
def analyze_review(text):
    text = text or ""
    for word in IGNORE:
        text = text.replace(word, " " * len(word))
    good, bad, unsure = [], [], False

    for table, same, other, flip in ((GOOD, good, bad, "안 "), (BAD, bad, good, "안 ")):
        for pattern, label in table.items():
            for match in re.finditer(pattern, text):
                start, end = match.span()
                before = text[max(0, start - 5):start]
                after = re.split(r"[.!?,\n]", text[end:end + 12])[0]  # 같은 문장 안만 본다
                after_stem = after[1:] if after.startswith("하") else after  # 느끼'하'지 않
                if label == "별로다" and re.search(r"안|않|못", after):
                    continue  # "별로 안 짜요"의 '별로'는 '그다지'라는 뜻
                if any(mark in after[:8] for mark in UNSURE_AFTER):
                    continue  # 남의 말이나 기대였던 말은 사용자 생각이 아니라서 빼고 본다
                negated = before.endswith(NOT_BEFORE) or after_stem.startswith(NOT_AFTER)
                target, word = (other, flip + label) if negated else (same, label)
                if word not in target:
                    target.append(word)
    if good and bad:  # 좋은 말과 나쁜 말이 섞여 있으면 판단이 어렵다 -> 별점을 믿는다
        unsure = True
    tone = 0 if unsure else (1 if good else -1 if bad else 0)

    def base(word):
        return word[2:] if word.startswith("안 ") else word
    taste_good = any(base(w) in TASTE_WORDS for w in good)
    taste_bad = any(base(w) in TASTE_WORDS for w in bad)
    service_bad = [w for w in bad if base(w) in SERVICE_WORDS]
    other_bad = [w for w in bad if base(w) not in TASTE_WORDS | SERVICE_WORDS]
    # "맛은 좋았지만 직원이 불친절해요": 맛은 칭찬, 불만은 서비스뿐 -> 낮은 별점은 가게 탓
    service_only = taste_good and not taste_bad and bool(service_bad) and not other_bad
    return {"좋은말": good, "나쁜말": bad, "애매함": unsure, "느낌": tone,
            "서비스불만": service_bad, "맛은좋음_서비스탓": service_only}


def review_words(text):
    result = analyze_review(text)
    return result["좋은말"], result["나쁜말"]


# 후기는 별점을 살짝만 고친다: 좋은 후기 +0.5, 나쁜 후기 -0.5, 판단이 어려우면 0 (별점이 우선)
def adjusted_stars(stars, tone):
    return min(5, max(1, stars + 0.5 * tone))


# 날짜 읽기: 앱마다 모양이 조금씩 달라도 읽는다. 못 읽으면 None
DATE_FORMATS = ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M",
                "%Y/%m/%d", "%Y.%m.%d %H:%M", "%Y.%m.%d", "%Y. %m. %d.")
def read_date(value):
    if isinstance(value, (int, float)):  # 숫자로 된 시각 (1970년부터 센 초)
        try:
            return datetime.fromtimestamp(value).date()
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value or "").strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()  # 2026-11-25T12:20:00+09:00
    except ValueError:
        pass
    for form in DATE_FORMATS:
        try:
            return datetime.strptime(text, form).date()
        except ValueError:
            continue
    return None


def read_entry(entry):
    """일기 하나를 확인한다. 날짜·가게·별점(1~5) 중 하나라도 이상하면 None (그 일기만 건너뜀)."""
    if not isinstance(entry, dict):
        return None
    when, name, stars = read_date(entry.get("날짜")), str(entry.get("가게") or "").strip(), entry.get("별점")
    if when is None or not name or isinstance(stars, bool) or not isinstance(stars, (int, float)) \
            or not 1 <= stars <= 5:
        return None
    return when, name, stars


# 3. 취향 요약표 만들기 (매일 최신화할 때 쓴다)
def build_profile(diary, stores, today):
    """stores: 가게 이름 -> 음식 종류. 지금은 가게정보.csv, 메뉴 에이전트가 생기면 거기서 받는다."""
    kinds, shops, points, recent = {}, {}, {}, []
    bad_count, unknown = {}, []
    used = skipped = 0
    entries = []
    for entry in diary:
        checked = read_entry(entry)
        if checked is None:
            skipped += 1
        else:
            entries.append((checked, entry))
    for (when, name, stars), entry in sorted(entries, key=lambda item: item[0][0]):
        if when > today:  # 미래 날짜는 쓰지 않는다
            continue
        used += 1
        kind = stores.get(name, "기타")
        if name not in stores and name not in unknown:
            unknown.append(name)  # 음식 종류를 모르는 가게 (메뉴 에이전트에게 물어볼 목록)
        review = analyze_review(entry.get("후기"))
        good, bad = review["좋은말"], review["나쁜말"]
        value = adjusted_stars(stars, review["느낌"])
        # 맛은 좋았고 불만이 서비스뿐이면, 음식 종류 선호에는 '맛 좋음(4점)'으로 넣는다.
        # 낮은 별점은 그 가게 점수에만 남는다
        kind_value = max(value, TASTE_PRAISED) if review["맛은좋음_서비스탓"] else value

        k = kinds.setdefault(kind, {"횟수": 0, "별점합": 0})
        k["횟수"] += 1
        k["별점합"] += kind_value

        s = shops.setdefault(name, {"종류": kind, "횟수": 0, "별점합": 0})
        s["횟수"] += 1
        s["별점합"] += value
        s.update({"마지막날": when.isoformat(), "마지막별점": stars,
                  "마지막후기": entry.get("후기", ""), "좋은말": good, "나쁜말": bad,
                  "서비스불만": review["서비스불만"]})

        for point in entry.get("혼밥포인트", []):
            points[point] = points.get(point, 0) + 1
        for word in bad:
            bad_count[word] = bad_count.get(word, 0) + 1

        days = (today - when).days
        if days in REPEAT_PENALTY:
            recent.append({"며칠전": days, "가게": name, "종류": kind})

    for table in (kinds, shops):
        for item in table.values():
            item["평균별점"] = round(item.pop("별점합") / item["횟수"], 1)

    real = {kind: item for kind, item in kinds.items() if kind != "기타"}
    liked = sorted((kind for kind, item in real.items() if item["평균별점"] >= 4 and item["횟수"] >= 2),
                   key=lambda kind: (-real[kind]["평균별점"], -real[kind]["횟수"]))
    disliked = [kind for kind, item in real.items() if item["평균별점"] <= 2.5]
    # 자주 고른 혼밥 포인트: 3번 이상, 그리고 일기의 절반 이상에서 골랐을 때
    often = [point for point, count in sorted(points.items(), key=lambda p: -p[1])
             if count >= 3 and count * 2 >= used]
    return {"버전": VERSION, "만든날": today.isoformat(), "기록수": used, "읽지못한일기": skipped,
            "종류를모르는가게": unknown, "종류별": kinds, "가게별": shops,
            "좋아하는종류": liked, "덜좋아하는종류": disliked, "최근": recent,
            "자주고른포인트": {point: points[point] for point in often},
            "자주나온불만": [word for word, count in bad_count.items() if count >= 2]}


# 4. 매일 최신화: 오늘 만든 요약표가 없거나, 그 뒤에 새 일기가 생겼으면 다시 만든다
def sources(folder=FOLDER):
    """일기와 가게 종류를 어디서 읽을지: 앱이 보낸 데이터가 있으면 앱, 없으면 샘플 파일."""
    data = app_data.load(folder)
    stores = load_stores(folder) if os.path.exists(os.path.join(folder, STORES)) else {}
    if data is not None:
        return app_data.diary(data), {**stores, **app_data.kinds(data)}, data["path"], "앱 혼밥일기"
    return load_diary(folder), stores, os.path.join(folder, DIARY), "샘플 일기"


def load_profile(folder=FOLDER, today=None):
    today = today or date.today()
    path = os.path.join(folder, PROFILE)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as file:
            profile = json.load(file)
        source = app_data.find(folder) or os.path.join(folder, DIARY)
        newer_diary = os.path.exists(source) and os.path.getmtime(source) > os.path.getmtime(path)
        if profile.get("만든날") == today.isoformat() and not newer_diary \
                and profile.get("버전") == VERSION and profile.get("출처파일") == source:
            return profile
    return refresh(folder, today)


def refresh(folder=FOLDER, today=None):
    today = today or date.today()
    diary, stores, source, label = sources(folder)
    profile = build_profile(diary, stores, today)
    profile.update({"출처": label, "출처파일": source})
    with open(os.path.join(folder, PROFILE), "w", encoding="utf-8") as file:
        json.dump(profile, file, ensure_ascii=False, indent=2)
    return profile


# 5. 처음 하는 말: 좋아하는 음식 + 최근에 먹은 음식
def opinion(profile):
    if not profile["기록수"]:
        return "아직 혼밥일기가 없어서 취향을 판단할 수 없어요."
    parts = []
    for kind in profile["좋아하는종류"][:2]:
        item = profile["종류별"][kind]
        parts.append(f"{josa(kind, '을', '를')} 좋아하세요({item['횟수']}번, 평균 {item['평균별점']}점).")
    for kind in profile["덜좋아하는종류"]:
        parts.append(f"{kind} 별점은 낮았어요(평균 {profile['종류별'][kind]['평균별점']}점).")
    for meal in profile["최근"]:
        if meal["종류"] == "기타":
            continue
        when = REPEAT_WORDS[meal["며칠전"]]
        parts.append(f"{when} {meal['가게']}에서 {josa(meal['종류'], '을', '를')} 드셨어요. "
                     f"{josa(meal['종류'], '은', '는')} 후순위로 할게요.")
    for word in profile["자주나온불만"]:
        parts.append(f"후기에 '{word}'라는 말이 자주 나와요.")
    for point, count in profile["자주고른포인트"].items():
        mark = josa(point, "을", "를")[len(point):]
        parts.append(f"'{point}'{mark} 자주 고르셨어요({count}번). 참고로 알려드려요.")
    note = unknown_note(profile)
    if note:
        parts.append(note)
    if profile.get("읽지못한일기"):
        parts.append(f"(날짜나 별점이 이상한 일기 {profile['읽지못한일기']}개는 빼고 봤어요.)")
    return " ".join(parts) or "기록이 적어서 아직 뚜렷한 취향이 보이지 않아요."


def _repeat(profile, kind):
    """같은 종류를 가장 최근에 며칠 전에 먹었는지 (3일 안에 없으면 None)"""
    days = [meal["며칠전"] for meal in profile["최근"] if meal["종류"] == kind and kind != "기타"]
    return min(days) if days else None


def unknown_recent(profile):
    """최근 3일 안에 간 곳 중 음식 종류를 모르는 가게 (겹치는지 확인할 수 없음)"""
    return [meal for meal in profile["최근"] if meal["종류"] == "기타"]


def unknown_note(profile):
    meals = unknown_recent(profile)
    if not meals:
        return ""
    names = ", ".join(f"{REPEAT_WORDS[meal['며칠전']]} 간 {meal['가게']}" for meal in meals)
    return f"{names}의 음식 종류를 몰라서 겹치는지 확인하지 못했어요."


# 혼밥 MBTI의 탐험파/단골파 (점수는 위 EXPLORER_*, REGULAR_*)
#   탐험파: 안 가본 곳 +3 · 가본 곳 -2
#   단골파: 혼밥일기에서 가봤고 별점 4점 이상인 곳 +3 · 3점 이상 +1 · 3점 미만 0 · 안 가본 곳 -1
def mbti_bonus(profile, store, code):
    shop = profile["가게별"].get(store)
    if mbti.has(code, "탐험파"):
        if shop:
            return EXPLORER_VISITED, f"탐험파라 가본 곳은 {EXPLORER_VISITED}점"
        return EXPLORER_NEW, f"탐험파라 안 가본 곳은 +{EXPLORER_NEW}점"
    if mbti.has(code, "단골파"):
        if shop and shop["평균별점"] >= 4:
            return REGULAR_VISITED, f"단골파라 가봤던 곳(별점 {shop['평균별점']:g}점)은 +{REGULAR_VISITED}점"
        if shop and shop["평균별점"] >= 3:
            return REGULAR_OK, f"단골파라 가봤던 곳(별점 {shop['평균별점']:g}점)은 +{REGULAR_OK}점"
        if not shop:
            return REGULAR_NEW, f"단골파라 안 가본 곳은 {REGULAR_NEW}점"
    return 0, ""


# 6. 가게의 취향 점수 (0~10). 퍼센트를 곱해 합치는 일은 조율자가 한다
def score(profile, store, food_type, code=None):
    """가게에 간 기록이 있으면 그 별점, 없으면 같은 종류의 평균 별점을 쓴다 (별점 x 2).
    code는 혼밥 MBTI (없으면 MBTI 보정 없음)."""
    shop = profile["가게별"].get(store)
    kind = profile["종류별"].get(food_type) if food_type != "기타" else None
    if shop:
        base, sure = shop["평균별점"] * 2, "높음"
    elif kind:
        base, sure = kind["평균별점"] * 2, "높음" if kind["횟수"] >= 3 else "중간"
    else:
        base, sure = NO_RECORD, "낮음"
    if sure == "높음" and unknown_recent(profile):  # 최근에 겹쳤을 수도 있으니 낮춘다
        sure = "중간"
    days = _repeat(profile, food_type)
    bonus, why = mbti_bonus(profile, store, code)
    points = min(10, max(0, base - REPEAT_PENALTY.get(days, 0) + bonus))
    return {"agent": "취향", "score": round(points, 1), "confirmed": sure != "낮음", "확실도": sure,
            "mbti": why}


# 반론에 쓰는 근거 한 문장 (강한 근거부터: 연속 먹기 > 가게 기록 > 종류 기록 > 기록 없음)
def reason(profile, store, food_type):
    days = _repeat(profile, food_type)
    shop = profile["가게별"].get(store)
    kind = profile["종류별"].get(food_type) if food_type != "기타" else None
    if days is not None:
        if days == 1:
            return f"{josa(store, '은', '는')} 어제에 이어 또 {josa(food_type, '이에요', '예요')}."
        return f"{josa(store, '은', '는')} {REPEAT_WORDS[days]} 드신 {food_type} 종류예요."
    if shop:
        when = date.fromisoformat(shop["마지막날"])
        text = f"{josa(store, '은', '는')} {when.month}월 {when.day}일에 별점 {shop['마지막별점']}점을 준 곳이에요"
        review = shop["마지막후기"]
        if review:
            short = review if len(review) <= 20 else review[:20] + "…"
            text += f". '{short}'라고 남기셨어요"
        if shop.get("서비스불만") and shop["마지막별점"] <= 3:
            text += f". 맛보다는 서비스({', '.join(shop['서비스불만'])}) 때문에 별점이 낮았어요"
        return text + "."
    if kind:
        return (f"{josa(food_type, '은', '는')} {kind['횟수']}번 드셨고 "
                f"평균 별점이 {kind['평균별점']}점이에요.")
    return f"{store}({food_type})에 대한 기록은 없어요."


# 7. 다른 에이전트의 말에 답하기: 이 가게가 취향에 맞는지만 판단한다
def reply(profile, sender, store, food_type, code=None):
    result = score(profile, store, food_type, code)
    repeated = _repeat(profile, food_type) is not None
    if repeated or (result["confirmed"] and result["score"] < 5):
        fits = False
    elif not result["confirmed"]:
        fits = None
    else:
        fits = True
    note = unknown_note(profile)
    if result.get("mbti"):
        note = (note + " " if note else "") + f"({result['mbti']})"
    message = (f"{sender} 의견 확인했어요. {reason(profile, store, food_type)}"
               f"{' ' + note if note else ''} (확실도 {result['확실도']})")
    return {"agent": "취향", "to": sender, "store": store, "fits": fits, "message": message}


# 8. 반론하기: 상대가 미는 가게와 지금 1순위 가게를 취향 점수로 비교한다
def rebut(profile, sender, proposed, proposed_type, current, current_type, hurry=False, code=None):
    """proposed는 상대가 미는 가게, current는 지금 1순위 가게.
    hurry=True(사용자가 '시간이 없어요')면 반대하지 않고 참고할 점만 말한다."""
    new = score(profile, proposed, proposed_type, code)
    old = score(profile, current, current_type, code)
    why_new = reason(profile, proposed, proposed_type)
    why_old = reason(profile, current, current_type)
    repeated = _repeat(profile, proposed_type) is not None
    sure = new["확실도"] if new["확실도"] == old["확실도"] else "중간"

    if not new["confirmed"] and not old["confirmed"]:
        stance, text, sure = "판단 안 함", "두 곳 다 기록이 없어서 취향으로는 비교할 수 없어요.", "낮음"
    elif hurry:
        stance = "동의"
        note = f" 다만 {why_new}" if repeated or new["score"] < old["score"] else ""
        text = f"급하시면 {proposed}도 괜찮아요.{note}"
    elif abs(new["score"] - old["score"]) < 2 and not repeated:
        stance, text = "판단 안 함", f"취향으로는 {josa(proposed, '과', '와')} {current}의 차이가 작아요."
    elif new["score"] < old["score"]:
        stance, text = "반대", f"{why_new} {why_old} {josa(current, '을', '를')} 지지합니다."
    else:
        stance, text = "동의", f"{why_new} 취향으로는 {proposed} 쪽이 더 맞아요."
    note = unknown_note(profile)
    message = f"{sender} 의견에 대해: {text}{' ' + note if note else ''} (확실도 {sure})"
    return {"agent": "취향", "to": sender, "stance": stance, "확실도": sure, "message": message}


# 9. 실행하기: 실행할 때 오늘 최신화가 안 됐으면 혼밥일기를 다시 읽는다
def main(today=None, folder=FOLDER):
    profile = load_profile(folder, today)
    print(f"[취향 요약표: {profile['만든날']} 기준, {profile.get('출처', '일기')} {profile['기록수']}개]")
    print("📒 취향기록:", opinion(profile))
    return profile


if __name__ == "__main__":
    main()
