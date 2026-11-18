"""환경설정. .env에서 값을 읽고, 가드레일 상한값을 한 곳에 모은다."""
import os

from dotenv import load_dotenv

load_dotenv()  # 작업 폴더의 .env 파일을 읽는다

MODEL_NAME = os.environ["MODEL_NAME"]  # 사용할 Gemini 모델명
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]  # API 키 (코드에 직접 쓰지 않는다)

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")  # 검색 API 키 (없으면 검색 도구가 오류를 알린다)
SEARCH_MAX_RESULTS = 5  # 검색 결과 최대 개수
SEARCH_TIMEOUT_SEC = 30  # 검색 API 타임아웃(초)

# 가드레일 상한 (상한에 걸리면 예외로 죽지 않고 중단 사유를 반환한다)
MAX_TURNS_ORCHESTRATOR = 10  # 오케스트레이터 최대 턴 수
MAX_TURNS_SUBAGENT = 8  # 서브에이전트 최대 턴 수
MAX_CALL_AGENT = 8  # 요청 한 건당 call_agent 최대 호출 수
LLM_TIMEOUT_SEC = 60  # LLM 호출 타임아웃(초)
