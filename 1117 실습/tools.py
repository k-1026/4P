"""도구 함수, 도구 명세, 이름으로 실행하는 execute_tool."""
import ast
import json
import operator
import urllib.request
from datetime import datetime

from config import SEARCH_MAX_RESULTS, SEARCH_TIMEOUT_SEC, TAVILY_API_KEY

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
    if not TAVILY_API_KEY:
        return "오류: .env에 TAVILY_API_KEY가 없어 검색할 수 없다. 검색 없이 확인된 내용만 보고하라."
    body = json.dumps({"query": query, "max_results": SEARCH_MAX_RESULTS,
                       "include_answer": True}).encode("utf-8")
    request = urllib.request.Request(
        TAVILY_URL, data=body, method="POST",
        headers={"Authorization": f"Bearer {TAVILY_API_KEY}",  # 문서: Bearer 토큰 인증
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=SEARCH_TIMEOUT_SEC) as response:
        return format_results(json.load(response))


# 이름 -> 실제 함수 (모델이 준 이름으로 함수를 찾는 표)
TOOL_FUNCTIONS = {"calculator": calculator, "get_current_time": get_current_time,
                  "web_search": web_search}

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
