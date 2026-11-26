"""도구 (그림의 회색 칸). 에이전트가 손으로 쓰는 것들.

- 팀 데이터 검색      → 탐색
- 카카오 장소 검색    → 탐색 (네이버 지역 검색은 보조)
- 카카오 블로그 검색  → 혼밥 분석
- 기상청 초단기실황   → 상황
- TMAP 보행자 경로    → 상황
(규칙 체크리스트는 agents/verify.py 안에 있다)

외부 API는 키가 없거나 실패하면 None을 돌려준다. 에이전트는 None이면 그 칸을 비워 둔다.
"""
import json
import math
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from functools import lru_cache

import config

# ---------- 말 사전 (챗봇_빈틀.html과 같은 값) ----------
GU = ["중구", "동구", "서구", "남구", "북구", "수성구", "달서구", "달성군", "군위군"]
AREA = {
    "동성로": "중구", "반월당": "중구", "서문시장": "중구", "교동": "중구", "대봉": "중구", "삼덕": "중구",
    "성서": "달서구", "상인": "달서구", "월배": "달서구", "두류": "달서구", "죽전": "달서구", "감삼": "달서구",
    "본리": "달서구", "월성": "달서구", "이곡": "달서구", "용산": "달서구", "진천": "달서구", "계명대": "달서구",
    "범어": "수성구", "수성못": "수성구", "들안길": "수성구", "황금": "수성구", "만촌": "수성구", "시지": "수성구",
    "칠곡": "북구", "복현": "북구", "침산": "북구", "경대": "북구", "경북대": "북구", "산격": "북구",
    "동대구": "동구", "신천": "동구", "효목": "동구", "안심": "동구", "율하": "동구", "혁신도시": "동구",
    "평리": "서구", "비산": "서구", "내당": "서구", "서대구": "서구",
    "대명": "남구", "봉덕": "남구", "앞산": "남구",
    "다사": "달성군", "화원": "달성군", "현풍": "달성군", "옥포": "달성군", "가창": "달성군", "군위": "군위군",
}
TAGS = {
    "고기": ["고기", "삼겹", "갈비", "막창", "곱창", "고깃집", "구이", "한우", "돼지"],
    "국밥·탕·찌개": ["국밥", "탕", "찌개", "해장", "순두부", "곰탕", "설렁탕", "추어탕", "전골", "국물"],
    "면": ["면", "국수", "칼국수", "냉면", "라멘", "라면", "우동", "짬뽕", "짜장", "쌀국수", "파스타"],
    "백반·정식": ["백반", "정식", "한상", "밥상", "쌈밥", "비빔밥", "덮밥", "도시락", "솥밥", "집밥"],
    "분식": ["분식", "떡볶이", "김밥", "만두", "어묵", "순대"],
    "해산물·회": ["회", "해물", "해산물", "아구", "쭈꾸미", "주꾸미", "낙지", "생선", "초밥", "스시"],
    "찜": ["찜", "찜닭", "갈비찜"],
    "샤브샤브": ["샤브"],
    "치킨": ["치킨", "닭강정"],
    "돈가스": ["돈가스", "돈까스", "카츠"],
    "한식": ["한식"], "일식": ["일식"], "중식": ["중식", "중국집"], "양식": ["양식"],
}
# 팀 1인분 판정 (status) 순서. 앞일수록 혼자 가기 확실하다.
STATUS_RANK = {"ok": 0, "nomin": 1, "hint": 2, "part": 3, "unk": 4, "two": 5}


# ---------- 팀 데이터 ----------
_DATA = None


def team_data():
    """챗봇 완성본 HTML 안의 `const DATA = [...]` 또는 JSON 파일을 읽는다."""
    global _DATA
    if _DATA is None:
        text = config.DATA_PATH.read_text(encoding="utf-8")
        if config.DATA_PATH.suffix == ".html":
            start = text.index("const DATA = ") + len("const DATA = ")
            _DATA, _ = json.JSONDecoder().raw_decode(text, start)
        else:
            _DATA = json.loads(text)
    return _DATA


def search_team_data(cond: dict):
    """조건에 맞는 팀 데이터 가게. 2인분 이상(two)은 inc_two가 아니면 뺀다."""
    gu, tags, kw = cond.get("gu"), cond.get("tags") or [], cond.get("keywords") or []
    max_p = cond.get("max_price")
    out = []
    for r in team_data():
        if gu and r.get("gu") != gu:
            continue
        if tags and not any(t in r.get("tags", []) for t in tags):
            continue
        if kw:
            hay = r["name"] + " " + " ".join(m.get("n", "") for m in r.get("menus", []))
            if not any(w in hay for w in kw):
                continue
        if max_p and r.get("minP") and r["minP"] > max_p:
            continue
        if r.get("status") == "two" and not cond.get("inc_two"):
            continue
        out.append(r)
    out.sort(key=lambda r: (STATUS_RANK.get(r.get("status"), 9), r.get("minP") or 10**9, r["name"]))
    return out


# ---------- 공통 HTTP ----------
def _get_json(url, headers=None, data=None):
    req = urllib.request.Request(url, headers=headers or {}, data=data, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)
    except Exception as e:
        print(f"  (API 실패: {url.split('?')[0]} · {e})")
        return None


# ---------- 카카오 (장소 검색 · 블로그 검색, 키 하나) ----------
# 재계획 때 같은 가게를 또 묻지 않게 결과를 기억해 둔다 (API 비용 보호)
@lru_cache(maxsize=2000)
def kakao_search(query: str, size: int = 15):
    """카카오 키워드 장소 검색. 결과를 공통 모양(place)으로 바꿔 돌려준다. 키 없거나 실패하면 None.
    place = {source, id, name, category, road_address, address, x, y, url}"""
    if not config.KAKAO_KEY:
        return None
    q = urllib.parse.quote(query)
    j = _get_json(f"https://dapi.kakao.com/v2/local/search/keyword.json?query={q}&size={size}",
                  {"Authorization": f"KakaoAK {config.KAKAO_KEY}"})
    if j is None:
        return None
    return [{
        "source": "카카오", "id": "K" + d["id"], "name": d["place_name"],
        "category": d.get("category_name", ""), "is_food": d.get("category_group_code") == "FD6",
        "road_address": d.get("road_address_name", ""), "address": d.get("address_name", ""),
        "x": float(d["x"]), "y": float(d["y"]), "url": d.get("place_url", ""),
    } for d in j.get("documents", [])]


@lru_cache(maxsize=2000)
def naver_local(query: str):
    """네이버 지역 검색 (최대 5곳). 카카오에서 못 찾았을 때 보조로 쓴다. 키 없으면 None."""
    if not (config.NAVER_ID and config.NAVER_SECRET):
        return None
    q = urllib.parse.quote(query)
    j = _get_json(f"https://openapi.naver.com/v1/search/local.json?query={q}&display=5",
                  {"X-Naver-Client-Id": config.NAVER_ID, "X-Naver-Client-Secret": config.NAVER_SECRET})
    if j is None:
        return None
    strip = lambda s: re.sub(r"<[^>]+>", "", s or "")
    out = []
    for d in j.get("items", []):
        mx, my = int(d.get("mapx") or 0), int(d.get("mapy") or 0)
        wgs = mx > 10**8  # 지금 형식은 경위도 × 10^7. 옛 형식(카텍 좌표)이면 좌표를 비워 둔다
        out.append({
            "source": "네이버", "id": "N" + str(abs(hash(d.get("link") or d["title"])) % 10**10),
            "name": strip(d["title"]), "category": d.get("category", ""),
            "is_food": not re.search(r"카페|디저트|술집|편의점", d.get("category", "")),
            "road_address": d.get("roadAddress", ""), "address": d.get("address", ""),
            "x": mx / 1e7 if wgs else None, "y": my / 1e7 if wgs else None, "url": d.get("link", ""),
        })
    return out


@lru_cache(maxsize=2000)
def kakao_blog(name: str, gu: str = "", size: int = 5):
    """'가게 이름 + 혼밥'으로 블로그 글 요약을 가져온다. 원문은 저장하지 않는다."""
    if not config.KAKAO_KEY:
        return None
    q = urllib.parse.quote(f"대구 {gu} {name} 혼밥".strip())
    j = _get_json(f"https://dapi.kakao.com/v2/search/blog?query={q}&size={size}",
                  {"Authorization": f"KakaoAK {config.KAKAO_KEY}"})
    if not j:
        return None
    strip = lambda s: re.sub(r"<[^>]+>", "", s or "")
    return [{"title": strip(d["title"]), "snippet": strip(d["contents"]), "url": d["url"]}
            for d in j.get("documents", [])]


# ---------- 기상청 초단기실황 (공공데이터포털) ----------
def kma_weather(nx: int = 89, ny: int = 90):
    """지금 날씨. 대구 중심 격자 nx=89, ny=90. {"rain": bool, "temp": float}."""
    if not config.KMA_KEY:
        return None
    t = datetime.now() - timedelta(minutes=45)  # 정시 자료는 40분쯤 뒤에 나온다
    qs = urllib.parse.urlencode({
        "serviceKey": config.KMA_KEY, "pageNo": 1, "numOfRows": 10, "dataType": "JSON",
        "base_date": t.strftime("%Y%m%d"), "base_time": t.strftime("%H00"), "nx": nx, "ny": ny,
    })
    j = _get_json(f"https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst?{qs}")
    try:
        items = {i["category"]: i["obsrValue"] for i in j["response"]["body"]["items"]["item"]}
        return {"rain": items.get("PTY", "0") != "0", "temp": float(items.get("T1H", "nan"))}
    except Exception:
        return None


# ---------- 걷는 시간 ----------
def tmap_walk_min(origin, dest):
    """TMAP 보행자 경로로 걷는 분. origin/dest = (경도, 위도). 키 없으면 직선거리로 어림."""
    if config.TMAP_KEY:
        body = json.dumps({"startX": origin[0], "startY": origin[1], "endX": dest[0], "endY": dest[1],
                           "startName": "출발", "endName": "도착"}).encode()
        j = _get_json("https://apis.openapi.sk.com/tmap/routes/pedestrian?version=1",
                      {"appKey": config.TMAP_KEY, "Content-Type": "application/json"}, body)
        try:
            return round(j["features"][0]["properties"]["totalTime"] / 60)
        except Exception:
            pass
    return round(_meters(origin, dest) * 1.3 / 67)  # 길이 굽은 걸 1.3배, 분당 67m


def _meters(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(h))


# ---------- 영업시간 ----------
def open_now(hours: str, now: datetime | None = None):
    """'11:00~21:00' 꼴만 읽는다. 읽을 수 없으면 None (모름).
    TODO: 브레이크타임 · 요일별 휴무 · '라스트오더' 처리."""
    m = re.search(r"(\d{1,2}):(\d{2})\s*[~\-]\s*(\d{1,2}):(\d{2})", hours or "")
    if not m:
        return None
    now = now or datetime.now()
    h1, m1, h2, m2 = map(int, m.groups())
    cur, start, end = now.hour * 60 + now.minute, h1 * 60 + m1, h2 * 60 + m2
    return start <= cur < end if end > start else (cur >= start or cur < end)  # 자정 넘김
