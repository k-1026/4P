"""가게 이름 꺼내기 · 팀 데이터에서 찾기 · 지도 결과를 팀 가게와 잇기.

오케스트레이터와 탐색 에이전트가 같이 쓴다.
팀 '06_2인분식당_데이터/가게잇기_규칙.md'를 따른다:
  - 상호 + 주소로 잇는다. 이름만 같다고 잇지 않는다 (같은 이름 가게가 여러 곳 있음)
  - 확실하지 않으면 잇지 않는다
"""
import html
import re

import tools

# ---------- 1. 문장에서 가게 이름 · 질문 종류 꺼내기 ----------
# 질문 종류. 탐색 에이전트는 종류와 상관없이 '가게 찾기'만 하고, 종류는 오케스트레이터가 다음 에이전트를 고를 때 쓴다.
INTENTS = [
    ("혼밥 여부", r"혼밥|혼자|1인분|1인|한\s?명|한\s?사람|눈치"),
    ("영업시간", r"몇\s?시|영업|문\s?(열|닫)|오픈|마감|브레이크|쉬는\s?날|휴무"),
    ("위치", r"어디|위치|주소|가는\s?길|주차"),
    ("가격·메뉴", r"얼마|가격|메뉴|뭐\s?(팔|맛있)|대표\s?메뉴"),
    ("평가", r"어때|맛있|괜찮|후기|웨이팅"),
]
# 이런 말이 있으면 가게 하나가 아니라 '조건으로 찾기'다 (단, 문장에 팀 가게 이름이 그대로 있으면 가게 질문)
CONDITION = re.compile(r"추천|맛집|근처|찾아|알려\s?줘|\d+\s*원|[만천]\s*원|\d+\s*분|이하|어디\s?(가|갈)")
PARTICLE = re.compile(r"(에서는|에서|은|는|이|가|을|를|에|도|랑|하고)$")
# '이 · 가 · 을 · 를'은 '을지로골뱅이'처럼 이름 끝 글자일 수 있어서, 이름을 자를 때는 떼지 않는다
SOFT_PARTICLE = re.compile(r"(에서는|에서|은|는|에|도|랑|하고)$")
FILLER = {"대구", "대구광역시", "가게", "식당", "집", "거기", "여기", "저기", "그", "이", "저", "그집", "이집"}
STOP = {"지금", "오늘", "내일", "점심", "저녁", "아침", "밥", "뭐", "날씨", "먹지", "먹을까", "좀", "혹시"}


def detect_intent(text: str):
    """무엇을 묻는지. 못 알아들으면 None."""
    return next((label for label, pat in INTENTS if re.search(pat, text)), None)


def _team_keys():
    """팀 가게 이름(지점 붙인 것 · 뗀 것) 모음. 너무 짧거나 음식 이름뿐인 것은 뺀다."""
    global _TEAM_KEYS
    if _TEAM_KEYS is None:
        _TEAM_KEYS = {k for r in tools.team_data() for k in name_keys(r["name"])
                      if len(k) >= 3 and not is_generic(k)}
    return _TEAM_KEYS


_TEAM_KEYS = None


def detect_store(text: str):
    """질문 종류와 상관없이 문장에서 가게 이름을 꺼낸다.
    돌려주는 값: (가게 이름 또는 None, 구 또는 None, 질문 종류 또는 None)

    A. 문장 안에 팀 가게 이름이 그대로 있으면 그 이름  ('혼밥하기 좋은 한씨네대가추어탕')
    B. 아니면 질문 낱말 앞의 말을 이름으로 본다      ('교동짬뽕 몇 시까지 해?')
       단, 조건 검색 말('추천', '만원', '10분')이 있거나 음식 이름뿐이면 가게 질문이 아니다"""
    intent = detect_intent(text)
    clean = re.sub(r"[\"'“”‘’?!.,~]", " ", text)
    gu, toks = None, []
    for tok in clean.split():
        bare = PARTICLE.sub("", tok) if len(tok) > 2 else tok
        if bare in tools.GU:
            gu = bare
        elif bare in tools.AREA:
            gu = tools.AREA[bare]
        else:
            toks.append(tok)

    # A. 이어진 낱말 묶음 중 팀 가게 이름과 같은 것 (긴 것부터). 바로 뒤에 '○○점'이 있으면 지점까지 붙인다
    keys = _team_keys()
    for size in range(min(len(toks), 4), 0, -1):
        for i in range(len(toks) - size + 1):
            words = toks[i:i + size]
            phrase = " ".join(words[:-1] + [PARTICLE.sub("", words[-1]) or words[-1]])
            if norm_name(phrase) in keys or norm_name(" ".join(words)) in keys:
                nxt = toks[i + size] if i + size < len(toks) else ""
                if re.fullmatch(r"[가-힣0-9]+점", PARTICLE.sub("", nxt) or nxt):
                    phrase += " " + (PARTICLE.sub("", nxt) or nxt)
                return phrase, gu, intent

    # B. 질문 낱말(혼밥 · 몇 시 · 어디 …) 앞의 말
    if CONDITION.search(text):
        return None, gu, intent
    starts = [m.start() for _, pat in INTENTS if (m := re.search(pat, clean))]
    head = []
    for tok in clean[:min(starts)].split() if starts else clean.split():
        bare = SOFT_PARTICLE.sub("", tok) if len(tok) > 2 else tok
        if bare in tools.GU or bare in tools.AREA or bare in FILLER or bare in STOP:
            continue
        head.append(tok)
    if not head:
        return None, gu, intent
    # 질문 낱말이 없으면 '교동짬뽕'처럼 짧은 이름만 받는다 ('점심 뭐 먹지?' 같은 문장은 가게 이름이 아님)
    if intent is None and (len(head) > 2 or re.search(r"(지|해|돼|까|요|야|어|니)$", head[-1])):
        return None, gu, intent
    head[-1] = SOFT_PARTICLE.sub("", head[-1]) or head[-1]
    name = " ".join(head)
    return (None, gu, intent) if is_generic(name) else (name, gu, intent)


def extract_store_name(text: str):
    """예전 이름 (가게 이름, 구). detect_store를 쓴다."""
    name, gu, _ = detect_store(text)
    return name, gu


def is_generic(name: str) -> bool:
    """'추어탕집', '국밥', '삼겹살 맛집'처럼 음식 이름일 뿐 가게 이름이 아닌가."""
    n = re.sub(r"(맛집|식당|가게|집)$", "", re.sub(r"\s", "", name))
    if len(n) < 2:
        return True
    for tag, words in tools.TAGS.items():
        if n == tag:
            return True
        if any(len(w) >= 2 and w in n and len(n) - len(w) <= 1 for w in words):
            return True
    return False


# ---------- 2. 상호 · 주소 정리 (비교할 때만, 원본은 그대로 둔다) ----------
def norm_name(s: str) -> str:
    s = html.unescape(s or "")
    s = re.sub(r"\([^)]*\)|\[[^\]]*\]", "", s)
    return re.sub(r"[^0-9a-zA-Z가-힣]", "", s).lower()


def name_keys(s: str) -> set:
    """지점명을 붙인 것과 뗀 것 둘 다. '청밭추어탕 수성구청역점' → {'청밭추어탕수성구청역점', '청밭추어탕'}"""
    parts = re.sub(r"\([^)]*\)", "", html.unescape(s or "")).split()
    keys = {norm_name(s)}
    if len(parts) > 1 and parts[-1].endswith("점"):
        keys.add(norm_name(" ".join(parts[:-1])))
    return keys - {""}


def addr_key(addr: str):
    """주소를 비교용 열쇠로. 도로명 ('R', 구, 도로, 번호) 또는 지번 ('J', 구, 동, 번지). 못 읽으면 None."""
    a = html.unescape(addr or "")
    a = re.sub(r"\(.*?\)", "", a).split(",")[0].replace("대구광역시", "대구")
    a = re.sub(r"\s지하\s", " ", a)
    a = re.sub(r"(로|길)\s+(\d+길)", r"\1\2", a)  # 비슬로 512길 → 비슬로512길
    gu = next((g for g in sorted(tools.GU, key=len, reverse=True) if g in a), None)
    if not gu:
        return None
    rest = a.split(gu, 1)[1]
    m = re.search(r"([가-힣]+\d*(?:동|가|리))\s*(산?\d+(?:-\d+)?)\s*$", rest)
    if m:
        return ("J", gu, m[1], m[2])
    m = re.search(r"([가-힣]+\d*(?:로|길)(?:\d+길)?)\s*(\d+(?:-\d+)?)?", rest)
    if m:
        return ("R", gu, m[1], m[2] or "")
    return None


# ---------- 3. 팀 데이터에서 이름으로 찾기 (오케스트레이터가 먼저 부름) ----------
def find_team_by_name(name: str, gu: str | None = None) -> list:
    """이름이 같은 팀 가게 목록 (지점명 붙인 것 · 뗀 것 모두 비교).
    1곳이면 채택, 여러 곳이면 어느 가게인지 되물어야 하고, 0곳이면 탐색 에이전트로 넘긴다."""
    q = name_keys(name)
    if len(q) > 1:  # 지점을 말했으면 ('청밭추어탕 지산범물점') 그 지점만. 팀에 그 지점이 없으면 0곳 → 탐색으로
        full = norm_name(name)
        hits = [r for r in tools.team_data() if full in name_keys(r["name"])]
    else:
        hits = [r for r in tools.team_data() if name_keys(r["name"]) & q]
    if gu and len(hits) > 1:
        hits = [r for r in hits if r.get("gu") == gu] or hits
    return hits


# ---------- 4. 지도에서 찾은 가게 ↔ 팀 가게 잇기 ----------
def place_addr_keys(p: dict) -> set:
    return {k for k in (addr_key(p.get("road_address")), addr_key(p.get("address"))) if k}


def link_stage(p: dict, store: dict):
    """팀 규칙의 연결 단계. A: 주소+상호, B: 주소+상호 일부, C: 상호+같은 도로. 아니면 None."""
    tk = addr_key(store.get("addr"))
    if not tk:
        return None
    pks = place_addr_keys(p)
    np_, nt = name_keys(p["name"]), name_keys(store["name"])
    same_addr = tk[3] != "" and tk in pks
    if same_addr and np_ & nt:
        return "A_주소+상호"
    if same_addr and any(len(a) >= 2 and (a in b or b in a) for a in np_ for b in nt):
        return "B_주소+상호일부"
    same_road = tk[0] == "R" and any(k[0] == "R" and k[1:3] == tk[1:3] for k in pks)
    if same_road and np_ & nt:
        return "C_상호+도로명"
    return None


def link_to_team(p: dict):
    """지도 가게와 같은 팀 가게를 찾는다. (팀 가게, 단계) 또는 (None, None).
    C 단계는 그런 팀 가게가 1곳뿐일 때만 잇는다 (규칙 3장)."""
    gu = next((k[1] for k in place_addr_keys(p)), None)
    found = [(r, s) for r in tools.team_data()
             if (not gu or r.get("gu") == gu) and (s := link_stage(p, r))]
    strong = [x for x in found if not x[1].startswith("C")]
    if len(strong) == 1:
        return strong[0]
    if not strong and len(found) == 1:
        return found[0]
    return None, None  # 없거나, 여러 곳이라 확실하지 않음 → 잇지 않는다


def locate_team_store(store: dict):
    """팀 가게의 지도 위치를 찾는다 (좌표가 필요할 때). 상호+주소로 맞는 지도 결과만 쓴다."""
    places = tools.kakao_search(f"대구 {store.get('gu', '')} {store['name']}".strip())
    for p in places or []:
        if link_stage(p, store):
            return p
    return None
