"""Gemini SDK 어댑터. SDK 고유 형식 변환은 이 파일 안에서만 처리한다."""
from dataclasses import dataclass, field

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, LLM_TIMEOUT_SEC, MODEL_NAME

client = genai.Client(
    api_key=GEMINI_API_KEY,  # 키는 config.py(.env)에서 가져온다
    # HttpOptions.timeout 단위는 밀리초 (설치된 SDK 필드 설명 기준)
    http_options=types.HttpOptions(timeout=LLM_TIMEOUT_SEC * 1000),
)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    text: str  # 최종 텍스트 (없으면 빈 문자열)
    tool_calls: list[ToolCall]
    usage: dict  # 입력·출력 토큰 수
    raw: object = field(repr=False, default=None)  # SDK 원본 Content (다음 호출에 재사용)

    def as_assistant_message(self) -> dict:
        """모델 응답을 메시지 목록에 붙일 공통 형태로 변환."""
        return {"role": "assistant", "content": self.text, "raw": self.raw}


def to_contents(messages: list) -> list:
    """공통 메시지 목록 -> Gemini Content 목록."""
    contents = []
    for m in messages:
        if m["role"] == "user":
            contents.append(types.Content(
                role="user", parts=[types.Part.from_text(text=m["content"])]))
        elif m["role"] == "assistant":
            # 모델이 보낸 원본 Content를 그대로 되돌려 보낸다 (도구 요청 포함)
            # 원본이 없는 이전 대화(웹 대화 이력)는 텍스트만으로 만든다
            contents.append(m.get("raw") or types.Content(
                role="model", parts=[types.Part.from_text(text=m["content"])]))
        elif m["role"] == "tool":
            # 한 응답의 도구 결과들을 하나의 tool Content에 모은다
            parts = [types.Part.from_function_response(
                name=r["name"], response={"result": r["result"]})
                for r in m["results"]]
            # API가 'tool' 역할을 거부해(user/model만 허용) user 역할로 보낸다
            contents.append(types.Content(role="user", parts=parts))
    return contents


def to_tools(tools: list | None) -> list | None:
    """공통 도구 명세(name, description, parameters) -> Gemini Tool."""
    if not tools:
        return None
    decls = [types.FunctionDeclaration(
        name=t["name"], description=t["description"],
        parameters_json_schema=t["parameters"]) for t in tools]
    return [types.Tool(function_declarations=decls)]


def parse_response(response) -> LLMResponse:
    """Gemini 응답 -> LLMResponse."""
    content = response.candidates[0].content
    text = "".join(p.text for p in content.parts if p.text)
    calls = [ToolCall(id=c.id or c.name, name=c.name, arguments=dict(c.args or {}))
             for c in (response.function_calls or [])]
    u = response.usage_metadata
    usage = {"input": u.prompt_token_count, "output": u.candidates_token_count}
    return LLMResponse(text=text, tool_calls=calls, usage=usage, raw=content)


def chat(system: str, messages: list, tools: list | None = None) -> LLMResponse:
    config = types.GenerateContentConfig(
        system_instruction=system,
        tools=to_tools(tools),
        # 도구 실행은 우리 코드가 하므로 SDK 자동 호출을 끈다
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    response = client.models.generate_content(
        model=MODEL_NAME, contents=to_contents(messages), config=config)
    return parse_response(response)
