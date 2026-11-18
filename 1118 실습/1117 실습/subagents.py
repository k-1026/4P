"""서브에이전트 3종(조사·작성·검토) 정의. 에이전트별 역할 설명을 이 파일에 모은다."""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from tools import get_specs

AGENTS_DIR = Path(__file__).parent / "agents"  # yaml 에이전트 정의 폴더

# 서브에이전트 공통 시스템 프롬프트 템플릿
TEMPLATE = """너는 {role} 전문 에이전트다. 오케스트레이터에게서
업무 지시서를 받아 수행하고 결과를 보고한다.
사용자와 직접 대화하지 않는다.

[작업 규칙]
- 지시서의 범위 안에서만 작업한다.
- {rules}
- 정보가 부족하면 추측으로 채우지 말고, 무엇이 부족한지 보고에 적는다.
- 도구가 오류를 내면 한 번 다른 방법으로 시도하고, 그래도 안 되면 실패를 보고한다.

[보고 양식] 마지막 답변은 반드시 이 형식으로 쓴다.
## 결과
## 근거
## 불확실하거나 확인하지 못한 점
"""


@dataclass
class Agent:
    name: str
    description: str  # 역할 설명: 오케스트레이터가 읽고 위임 여부를 판단한다
    system_prompt: str  # 서브에이전트 자신이 읽는 지침
    tools: list = field(default_factory=list)  # 이 에이전트 전용 도구 명세


def make_agent(name: str, role: str, description: str, rules: str,
               tools: list) -> Agent:
    prompt = TEMPLATE.format(role=role, rules=rules)
    return Agent(name, description, prompt, get_specs(tools))


SUBAGENTS = {
    # 조사: 외부 정보를 찾아 출처와 함께 보고
    "researcher": make_agent(
        name="researcher",
        role="조사",
        description=("웹 검색으로 사실, 통계, 최신 동향을 조사한다. "
                     "외부 정보가 필요한 요청에 쓴다. "
                     "글 작성이나 초안 검토에는 쓰지 않는다."),
        rules="주장마다 출처(URL)를 붙인다. 검색으로 확인한 것과 추정을 구분한다.",
        tools=["web_search", "get_current_time"],
    ),
    # 작성: 확보된 자료를 읽기 좋은 문서로 정리
    "writer": make_agent(
        name="writer",
        role="작성",
        description=("주어진 자료를 보고서, 요약, 메일 등 읽기 좋은 문서로 작성한다. "
                     "내용이 확보된 뒤에 쓴다. "
                     "사실 조사나 초안 검토에는 쓰지 않는다."),
        rules="지시서에 없는 사실을 더하지 않는다. 독자와 분량은 지시서에서 확인한다.",
        tools=[],
    ),
    # 검토: 초안을 근거 자료와 대조해 문제점을 보고 (직접 고쳐 쓰지 않음)
    "reviewer": make_agent(
        name="reviewer",
        role="검토",
        description=("작성된 초안을 근거 자료와 대조해 오류, 누락, 과장, 계산 실수를 검토한다. "
                     "초안과 근거 자료가 함께 있을 때 쓴다. "
                     "새 정보를 조사하거나 초안을 새로 쓰는 데는 쓰지 않는다."),
        rules=("초안을 직접 고쳐 쓰지 않고 문제점과 수정 제안만 보고한다. "
               "숫자는 계산기로 다시 계산해 확인한다. "
               "근거 자료에 없는 내용은 근거 없음으로 표시한다."),
        tools=["calculator"],
    ),
}


def load_yaml_agents() -> dict:
    """agents/*.yaml 정의 파일을 읽어 make_agent로 만든다 (공용 템플릿·보고 양식이 그대로 적용된다)."""
    agents = {}
    for path in sorted(AGENTS_DIR.glob("*.yaml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))  # 키: name, role, description, rules, tools
        agents[spec["name"]] = make_agent(**spec)
    return agents


SUBAGENTS.update(load_yaml_agents())  # 파이썬 정의 3종 뒤에 yaml 정의 에이전트를 합친다
