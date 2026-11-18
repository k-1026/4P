"""도구 함수, 도구 명세, 이름으로 실행하는 execute_tool."""
import ast
import csv
import json
import operator
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

from config import SEARCH_MAX_RESULTS, SEARCH_TIMEOUT_SEC, TAVILY_API_KEY

sys.path.append(str(Path(__file__).parent.parent))  # 손효민 폴더의 rag.py(문서 검색)를 쓰기 위해
DOC_INDEX = {}  # 문서 색인 캐시 (search_docs를 처음 쓸 때 한 번만 읽는다)

TAVILY_URL = "https://api.tavily.com/search"  # Tavily 검색 API 엔드포인트 (POST)

# 계산기에서 허용할 연산자만 모은 표 (eval 대신 안전하게 계산)
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.USub: operator.neg}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp):
        return OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp):
        return OPS[type(node.op)](_eval(node.operand))
    raise ValueError("허용되지 않는 식")


def calculator(expression: str):
    """사칙연산 식을 계산한다."""
    return _eval(ast.parse(expression, mode="eval").body)


def get_current_time() -> str:
    """현재 날짜와 시각을 돌려준다."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_results(data: dict) -> str:
    """Tavily 응답(JSON)을 모델이 읽기 좋은 문자열로 바꾼다."""
    lines = []
    if data.get("answer"):
        lines.append(f"요약: {data['answer']}")
    for i, r in enumerate(data.get("results", []), 1):
        lines.append(f"{i}. 제목: {r['title']} / 출처: {r['url']} / 내용: {r['content'][:400]}")
    return "\n".join(lines) or "검색 결과 없음"


def web_search(query: str) -> str:
    """Tavily 검색 API로 실제 웹을 검색한다 (표준 라이브러리 HTTP 호출)."""
    if not TAVILY_API_KEY or not TAVILY_API_KEY.isascii():  # 안내 문구 같은 한글이 키 자리에 있으면 헤더 인코딩 오류가 나므로 미리 막는다
        return "오류: .env의 TAVILY_API_KEY가 없거나 올바른 키가 아니라 웹 검색을 할 수 없다. 검색 없이 확인된 내용만 보고하라."
    body = json.dumps({"query": query, "max_results": SEARCH_MAX_RESULTS,
                       "include_answer": True}).encode("utf-8")
    request = urllib.request.Request(
        TAVILY_URL, data=body, method="POST",
        headers={"Authorization": f"Bearer {TAVILY_API_KEY}",  # 문서: Bearer 토큰 인증
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=SEARCH_TIMEOUT_SEC) as response:
        return format_results(json.load(response))


def search_docs(query: str) -> str:
    """색인한 문서에서 검색어와 비슷한 조각을 찾아 '출처 파일명 + 본문' 문자열로 돌려준다."""
    import rag  # 임포트 때 .env와 임베딩 설정이 필요해서, 이 도구를 쓸 때만 불러온다
    if not DOC_INDEX:
        DOC_INDEX["chunks"], DOC_INDEX["matrix"] = rag.load_index()
    results = rag.search(query, DOC_INDEX["chunks"], DOC_INDEX["matrix"])
    return "\n\n".join(f"[출처: {Path(c['source']).name}]\n{c['text']}" for _, c in results)


TABLE_PATH = Path(__file__).parent / "docs" / "대구_야간관광명소_표.csv"  # 표 조회 대상


def query_table(column: str, keyword: str) -> str:
    """CSV 표에서 column 열에 keyword가 들어 있는 행을 찾는다 (column이 '전체'면 모든 열)."""
    with open(TABLE_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if column != "전체" and column not in rows[0]:  # 열 이름이 틀리면 가능한 열을 알려 준다
        return f"오류: '{column}' 열이 없다. 열 목록: {', '.join(rows[0])}"
    found = [r for r in rows if keyword in (" ".join(r.values()) if column == "전체" else r[column])]
    lines = [" | ".join(f"{k}={v}" for k, v in r.items()) for r in found]
    return f"[출처: {TABLE_PATH.name}] 전체 {len(rows)}행 중 {len(found)}행 일치\n" + "\n".join(lines)


# 이름 -> 실제 함수 (모델이 준 이름으로 함수를 찾는 표)
TOOL_FUNCTIONS = {"calculator": calculator, "get_current_time": get_current_time,
                  "web_search": web_search, "search_docs": search_docs,
                  "query_table": query_table}

# 이름 -> 모델에게 보여줄 명세 (JSON Schema)
TOOL_SPECS = {
    "calculator": {
        "name": "calculator",
        "description": "사칙연산 식을 계산한다. 숫자 계산이 필요할 때 쓴다.",
        "parameters": {"type": "object", "properties": {
            "expression": {"type": "string", "description": "예: (1234*56)+789"}},
            "required": ["expression"]},
    },
    "get_current_time": {
        "name": "get_current_time",
        "description": "현재 날짜와 시각을 조회한다. 오늘 날짜나 현재 시각이 필요할 때만 쓴다.",
        "parameters": {"type": "object", "properties": {}},
    },
    "web_search": {
        "name": "web_search",
        "description": "웹에서 정보를 검색한다. 외부 사실이나 통계가 필요할 때 쓴다.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "검색어"}},
            "required": ["query"]},
    },
    "search_docs": {
        "name": "search_docs",
        "description": "색인된 문서 10개에서 검색어와 관련된 조각을 찾아 본문과 출처 파일명을 돌려준다. 문서 내용이 필요한 질문에 쓴다.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "핵심 키워드로 쓴 검색어"}},
            "required": ["query"]},
    },
    "query_table": {
        "name": "query_table",
        "description": ("대구 야간관광 명소 표(CSV)에서 조건에 맞는 행을 찾는다. "
                        "열: 구, 명소, 주소, 이용요금, 운영시간, 주차, 문의, 출처. 요금·운영시간·주차 같은 표의 값이 필요할 때 쓴다."),
        "parameters": {"type": "object", "properties": {
            "column": {"type": "string", "description": "찾을 열 이름 (예: 구, 명소, 이용요금). 모든 열에서 찾으려면 '전체'"},
            "keyword": {"type": "string", "description": "그 열에 들어 있어야 하는 글자 (예: 수성구)"}},
            "required": ["column", "keyword"]},
    },
}


def get_specs(names: list) -> list:
    """도구 이름 목록 -> 명세 목록."""
    return [TOOL_SPECS[n] for n in names]


def execute_tool(name: str, arguments: dict) -> str:
    try:
        return str(TOOL_FUNCTIONS[name](**arguments))
    except Exception as e:
        # 예외를 올리지 않고 모델이 읽을 수 있는 문장으로 돌려준다
        return f"오류: {type(e).__name__}: {e}. 인자를 확인하거나 다른 방법을 시도하라."
