"""메뉴 글을 풀어서 표로 만드는 함수들 (메뉴 갱신 에이전트 1단계).

한 가게의 메뉴는 지금 문장 하나에 뭉쳐 있다.
  대구푸드:  "왕족발(소) 25,000원 <br />왕족발(중) 30,000원"
  수집양식:  "옻닭 10,000원; 추어탕 8,000원; 추어탕 A(2인상) 30,000원"
이걸 메뉴 한 줄 = 한 행으로 푼다.
"""
import re

# 곁들이 메뉴: 대표메뉴와 가격 평균에서 뺀다
SIDE = re.compile(
    r"공기밥|밥\s*추가|사리|추가|음료|주류|소주|맥주|막걸리|와인|하이볼|콜라|사이다"
    r"|토핑|곱빼기|포장|배달|커피|아메리카노|생수"
)
# 메뉴가 아니라 업종 이름만 적힌 칸 (수집양식에 많음: "한식", "분식")
CATEGORY_ONLY = {
    "한식", "분식", "중식", "중국요리", "일식", "양식", "음식점", "일반음식점", "식당",
    "카페", "기타", "뷔페", "퓨전", "세계요리", "술집", "호프", "주점", "패스트푸드",
}
SIZE_WORDS = ("초특대", "특대", "대", "중", "소")

PRICE = r"(\d{1,3}(?:,\d{3})+|\d{4,})"          # 9,000 / 9000
RANGE_RE = re.compile(PRICE + r"\s*원?\s*~\s*" + PRICE + r"\s*원")
ONE_RE = re.compile(PRICE + r"\s*원")
# "(중)30,000원 (대)35,000원" 처럼 크기마다 가격이 붙은 경우
SIZE_PRICE_RE = re.compile(r"\(\s*(초특대|특대|대|중|소|\d\s*인분?|\d\s*마리)\s*\)\s*" + PRICE + r"\s*원")
SERVING_RE = re.compile(r"(\d)\s*인\s*(분|상|이상|부터|세트|용)?")
PAREN_SIZE_RE = re.compile(r"\(\s*(초특대|특대|대|중|소)\s*\)")


def _won(s):
    return int(s.replace(",", ""))


def clean_name(text):
    """가격·괄호 앞뒤 기호를 지운 메뉴 이름."""
    name = RANGE_RE.split(text)[0] if RANGE_RE.search(text) else text
    name = ONE_RE.split(name)[0]
    name = re.sub(r"\s+", " ", name).strip(" -~:·,/(")
    return name[:40]


def core_name(name):
    """비교용 이름: 괄호 안·공백·기호를 지운다. '왕족발(소)' -> '왕족발'."""
    n = re.sub(r"\([^)]*\)|\[[^\]]*\]", "", name or "")
    return re.sub(r"[\s·,./~\-]", "", n)


def serving_of(text):
    """몇 인분인지. '1인분', '2인분부터', '2인상' 같은 표기만 본다. 없으면 ''."""
    m = SERVING_RE.search(text)
    if not m:
        return ""
    n, tail = m.group(1), m.group(2) or ""
    if n == "1":
        return "1인분"
    return f"{n}인분부터" if tail in ("이상", "부터") else f"{n}인"


def size_of(text):
    m = PAREN_SIZE_RE.search(text)
    return m.group(1) if m else ""


def is_description(text):
    """메뉴가 아니라 가게 소개 문장인지."""
    if ONE_RE.search(text):
        return False
    return text.startswith("[") or len(text) > 30 or "입니다" in text


def parse_item(text):
    """메뉴 한 칸을 행 목록으로. 크기별 가격이 있으면 크기마다 한 행."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    if not text or is_description(text):
        return []

    base = {"원문": text, "메뉴명": clean_name(text), "가격": "", "가격_최대": "",
            "가격종류": "없음", "크기": size_of(text), "인분": serving_of(text)}

    sized = SIZE_PRICE_RE.findall(text)
    if len(sized) >= 2:
        name = clean_name(SIZE_PRICE_RE.split(text)[0]) or base["메뉴명"]
        rows = []
        for size, price in sized:
            size = size.replace(" ", "")
            r = dict(base, 메뉴명=name, 가격=_won(price), 가격종류="고정")
            if size in SIZE_WORDS:
                r["크기"] = size
            else:
                r["크기"] = ""
                r["인분"] = serving_of(size) or r["인분"]
            rows.append(r)
        return rows

    m = RANGE_RE.search(text)
    if m:
        base.update(가격=_won(m.group(1)), 가격_최대=_won(m.group(2)), 가격종류="범위")
    else:
        m = ONE_RE.search(text)
        if m:
            base.update(가격=_won(m.group(1)), 가격종류="고정")
        elif re.search(r"변동|시가|싯가", text):
            base["가격종류"] = "변동"

    if base["가격종류"] == "없음" and base["메뉴명"] in CATEGORY_ONLY:
        return []  # "한식", "분식" 같은 업종 이름은 메뉴가 아니다
    if re.search(r"가격\s*변동", text) and base["가격종류"] == "변동":
        base["메뉴명"] = re.sub(r"\s*가격\s*변동.*$", "", base["메뉴명"]).strip()
    if not core_name(base["메뉴명"]) or core_name(base["메뉴명"]) in SIZE_WORDS:
        return []  # "중", "대"처럼 크기만 남은 칸은 메뉴가 아니다
    return [base]


def split_daegufood(mnu):
    """대구푸드 MNU 칸: <br />로 나뉜다."""
    return re.split(r"<br\s*/?>", mnu or "")


def split_form(text):
    """수집양식 대표메뉴 칸: ';'로 나뉜다. 가격이 하나도 없으면 ','도 나눈다 ('돈까스,우동')."""
    parts = (text or "").split(";")
    if len(parts) == 1 and not ONE_RE.search(text or ""):
        parts = re.split(r"\s*,\s*", text or "")
    return parts


def parse_menus(parts):
    rows = []
    for p in parts:
        rows += parse_item(p)
    for i, r in enumerate(rows, 1):
        r["순서"] = i
        r["곁들이"] = "Y" if SIDE.search(r["메뉴명"]) else ""
    return rows


# ---------- 대표메뉴 고르기 ----------
STORE_NOISE = re.compile(r"본점|직영점|\S+점$|식당|전문점|맛집|하우스|\(.*?\)|[A-Za-z]+")


def _common_len(a, b):
    """두 글자열에서 가장 긴 공통 부분의 길이."""
    best = 0
    for i in range(len(a)):
        for j in range(i + best + 1, len(a) + 1):
            if a[i:j] in b:
                best = j - i
            else:
                break
    return best


def pick_signature(store_name, rows):
    """대표메뉴 한 개를 골라 (행 번호, 근거)를 돌려준다. 없으면 (None, '').

    1) 가게 이름과 겹치는 메뉴  ('OO돼지국밥' -> 돼지국밥)
    2) 메뉴판 맨 앞의 가격 있는 메뉴
    3) 메뉴판 맨 앞의 메뉴 (가격 없음)
    곁들이 메뉴(공기밥·사리·음료·술)는 고르지 않는다.
    """
    cands = [(i, r) for i, r in enumerate(rows) if not r["곁들이"] and r["가격종류"] != "변동"]
    if not cands:
        return None, ""

    store = re.sub(r"\s", "", STORE_NOISE.sub("", store_name or ""))
    best_i, best_len = None, 1
    for i, r in cands:
        n = _common_len(core_name(r["메뉴명"]), store)
        if n > best_len:
            best_i, best_len = i, n
    if best_i is not None:
        return best_i, "가게이름"

    for i, r in cands:
        if r["가격"] != "":
            return i, "메뉴판첫번째"
    return cands[0][0], "메뉴판첫번째(가격없음)"
