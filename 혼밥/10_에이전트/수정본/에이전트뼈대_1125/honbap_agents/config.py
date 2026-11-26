"""API 키와 기본값. 키는 코드에 적지 말고 .env 파일에 넣는다 (.env.example 참고).

키가 없으면 그 도구는 건너뛰고 나머지로만 동작한다.
"""
import os
from pathlib import Path

HERE = Path(__file__).parent


def _load_env():
    env = HERE / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_env()

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
KAKAO_KEY = os.getenv("KAKAO_REST_KEY", "")   # 장소 검색 + 블로그 검색 (키 하나)
KMA_KEY = os.getenv("KMA_SERVICE_KEY", "")    # 공공데이터포털 기상청 단기예보 (디코딩 키)
TMAP_KEY = os.getenv("TMAP_APP_KEY", "")      # TMAP 보행자 경로 (선택)
NAVER_ID = os.getenv("NAVER_CLIENT_ID", "")   # 네이버 지역 검색 (선택, 카카오 보조)
NAVER_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")

# 팀 데이터: 챗봇 완성본 HTML 또는 같은 내용의 JSON.
# 저장소에 '혼밥/09_에이전트'로 넣으면 옆 폴더 07_챗봇의 완성본을 그대로 읽는다.
_CANDIDATES = [HERE / "data" / "혼밥챗봇_완성본.html", HERE.parent / "07_챗봇" / "혼밥챗봇_완성본.html"]
DATA_PATH = Path(os.getenv("HONBAP_DATA") or next((p for p in _CANDIDATES if p.exists()), _CANDIDATES[0]))

# 기본 출발지: 달서구청 근처 (경도, 위도). 사용자 위치를 받으면 바꾼다.
DEFAULT_ORIGIN = (128.5326, 35.8299)

MAX_ROUNDS = 3        # 재계획 최대 횟수
MIN_RESULTS = 3       # 이만큼 못 채우면 검증이 반려
TOP_N = 10            # 외부 API(지도·블로그·길찾기)를 부를 후보 수. 비용 보호용
DEFAULT_WALK_MIN = 15 # 점심 기준 걸어서 갈 수 있는 최대 분
