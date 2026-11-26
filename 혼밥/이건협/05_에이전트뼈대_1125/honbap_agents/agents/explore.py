"""탐색 에이전트: 후보 가게 모으기. 판단(1인분 · 혼밥 지수)은 하지 않는다.

할 일 두 가지
1. find_store(board, name, gu)  ← "○○가게 혼밥 가능해?"인데 팀 데이터에 없을 때
   카카오(없으면 네이버)에서 그 가게를 찾고, 찾은 가게가 사실 팀 가게인지 상호+주소로 한 번 더 확인한다.
2. run(board)                   ← "달서구 국밥 만원"처럼 조건으로 찾을 때
   팀 데이터에서 조건에 맞는 가게를 고르고 지도 위치를 붙인다.

도구: 팀 데이터 · 카카오 로컬 API · (선택) 네이버 지역 검색
"""
import config
import store_lookup as sl
import tools
from board import Board, new_candidate

MAX_CANDIDATES = 30
MAX_ASK = 5  # 되물을 때 보여 줄 가게 수


# ---------- 1. 가게 이름으로 찾기 ----------
def find_store(board: Board, name: str, gu: str | None = None) -> str:
    """돌려주는 값 (오케스트레이터가 다음에 할 일을 정함)
      "found"     후보 1곳 → 혼밥 분석으로
      "ambiguous" 여러 곳 → board.ask로 사용자에게 되묻기
      "not_found" 대구 음식점 중에 없음
      "no_key"    지도 API 키가 없어 찾을 수 없음
    """
    board.mode = "store"
    query = " ".join(f"대구 {gu or ''} {name}".split())

    places, used = _search(query)
    if places is None:
        board.note("탐색", "카카오 · 네이버 키가 없어 지도에서 찾을 수 없음")
        return "no_key"
    raw = len(places)
    places = _keep_matching(places, name)
    if gu:
        places = [p for p in places if gu in (p["road_address"] + p["address"])] or places
    board.note("탐색", f"{used} 검색 '{query}': 결과 {raw}곳 → 대구 · 음식점 · 이름이 맞는 곳 {len(places)}곳")
    if not places:
        board.note("탐색", f"'{name}': {used}에서 대구 음식점 중 맞는 가게 없음")
        return "not_found"

    # 지도에서 찾은 가게가 사실 팀 데이터에 있는지 상호+주소로 확인 (오케스트레이터가 이름을 다르게 받았을 수 있음)
    cands, seen = [], set()
    for p in places:
        store, stage = sl.link_to_team(p)
        c = new_candidate(store, p, found_by=used, link=stage) if store else \
            new_candidate(store_from_place(p), p, found_by=used)
        key = c["store"]["id"]
        if key not in seen:
            seen.add(key)
            cands.append(c)
    board.candidates = cands
    in_team = sum(c["in_team"] for c in cands)
    board.note("탐색", f"'{name}': {used}에서 {len(cands)}곳 찾음 (그중 팀 데이터와 이어진 곳 {in_team}곳)")

    if len(cands) == 1:
        return "found"
    board.ask = _ask_text(name, cands)
    return "ambiguous"


def _search(query: str):
    """카카오 먼저, 0곳이면 네이버. (결과, 쓴 곳) — 둘 다 키가 없으면 (None, '')."""
    places = tools.kakao_search(query)
    if places:
        return places, "카카오"
    naver = tools.naver_local(query)
    if naver:
        return naver, "네이버"
    if places is None and naver is None:
        return None, ""
    return [], "카카오" if places is not None else "네이버"


def _keep_matching(places: list, name: str) -> list:
    """대구에 있는 음식점이고, 사용자가 말한 낱말이 상호에 모두 들어 있는 것만 남긴다.
    ('한씨네 추어탕' → '한씨네', '추어탕'이 모두 들어 있는 '한씨네대가추어탕 종로점'은 남김)"""
    words = [w for w in (sl.norm_name(t) for t in name.split()) if len(w) >= 2] or [sl.norm_name(name)]
    out = []
    for p in places:
        addr = p["road_address"] + " " + p["address"]
        if not addr.strip().startswith("대구"):
            continue
        if not p["is_food"]:
            continue
        n = sl.norm_name(p["name"])
        if all(w in n for w in words):
            out.append(p)
    return out


def store_from_place(p: dict) -> dict:
    """지도에서 찾은 가게를 팀 데이터와 같은 칸으로 바꾼다. 1인분 판정은 없으므로 status='unk'."""
    addr = p["road_address"] or p["address"]
    gu = next((g for g in sorted(tools.GU, key=len, reverse=True) if g in addr), "")
    cat = p.get("category", "")
    tags = sorted({tag for tag, words in tools.TAGS.items() if any(len(w) >= 2 and w in cat for w in words)})
    return {
        "id": p["id"], "name": p["name"], "gu": gu, "addr": addr,
        "fd": cat.split(">")[-1].strip() if cat else "", "tags": tags,
        "menus": [], "minP": None, "hours": "", "seats": "", "sbw": "", "note": "",
        "status": "unk", "why": "팀 데이터에 없는 가게 — 1인분 판정 없음",
        "src": f"{p['source']} 지도 검색",
    }


def _ask_text(name: str, cands: list) -> str:
    lines = [f"'{name}'(으)로 {len(cands)}곳이 나왔어요. 어느 가게인가요?"]
    for i, c in enumerate(cands[:MAX_ASK], 1):
        lines.append(f"{i}. {c['store']['name']} — {c['store'].get('addr', '')}")
    if len(cands) > MAX_ASK:
        lines.append(f"(그 밖에 {len(cands) - MAX_ASK}곳)")
    lines.append("목록에 없으면 지점 이름이나 동네를 같이 알려 주세요. (예: ○○ 반월당점)")
    return "\n".join(lines)


# ---------- 2. 조건으로 찾기 ----------
def run(board: Board):
    found = tools.search_team_data(board.conditions)
    board.candidates = [new_candidate(r) for r in found[:MAX_CANDIDATES]]
    board.note("탐색", f"팀 데이터에서 {len(found)}곳 → 상위 {len(board.candidates)}곳을 후보로 올림")

    # 좌표는 상위 몇 곳만 찾는다 (API 비용 보호).
    # 단, 사용자가 '걸어서 N분'을 말했으면 거리를 모르는 가게는 검증에서 빠지므로 후보 전부 찾는다.
    if not config.KAKAO_KEY:
        board.note("탐색", "카카오 키 없음 → 좌표 없이 진행 (걷는 시간은 모름으로 남음)")
        return
    n = len(board.candidates) if board.conditions.get("walk_limit") else config.TOP_N
    hit = 0
    for c in board.candidates[:n]:
        c["map"] = sl.locate_team_store(c["store"])
        hit += c["map"] is not None
    board.note("탐색", f"카카오 지도에서 {hit}/{min(n, len(board.candidates))}곳 위치 확인 (상호+주소가 맞는 것만)")
