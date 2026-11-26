"""공유 상태 (작업 보드).

모든 에이전트가 이 보드 하나를 읽고 쓴다. 에이전트끼리 직접 말하지 않고,
보드에 적어 두면 다음 에이전트가 읽는다.
"""
from dataclasses import dataclass, field


@dataclass
class Board:
    request: str                                    # 사용자가 한 말 그대로
    conditions: dict = field(default_factory=dict)  # 오케스트레이터가 뽑은 조건
    candidates: list = field(default_factory=list)  # 후보 가게 (탐색이 넣고, 다른 에이전트가 칸을 채움)
    rejections: list = field(default_factory=list)  # 검증이 남긴 반려 사유 (보드 전체 단위)
    final: list = field(default_factory=list)       # 검증을 통과한 가게
    round: int = 0                                  # 몇 번째 계획인지 (재계획하면 +1)
    log: list = field(default_factory=list)         # 누가 무엇을 했는지 기록
    mode: str = "search"                            # "search": 조건으로 찾기 / "store": 가게 하나를 물어봄
    ask: str = ""                                   # 사용자에게 되물을 말 (예: 어느 지점인지)
    intent: str = ""                                # 질문 종류 (혼밥 여부 · 영업시간 · 위치 · 가격·메뉴 · 평가)

    def note(self, who: str, msg: str):
        line = f"[{self.round}회차 · {who}] {msg}"
        self.log.append(line)
        print(line)


def new_candidate(store: dict, place: dict | None = None, found_by: str = "팀 데이터", link: str | None = None):
    """후보 한 곳을 만든다. 팀 가게든 지도에서 찾은 가게든 모양이 같아야 다음 에이전트가 똑같이 다룬다."""
    return {
        "store": store,
        "map": place if place and place.get("x") is not None else None,
        "found_by": found_by,
        "in_team": not str(store.get("id", "")).startswith(("K", "N")),
        "link": link,
        "score": None, "evidence": [], "flags": [], "context": {}, "rejected": [],
    }


# 후보 한 곳의 모양 (new_candidate가 만든다)
#
# {
#   "store":    가게 정보. 팀 데이터 한 줄 그대로 (id, name, gu, addr, tags, menus, minP, hours, status, why ...)
#               팀 데이터에 없는 가게도 같은 칸을 쓰고, status는 "unk"(1인분 확인 안 됨)
#   "map":      지도 검색 결과 {source, id, name, category, road_address, address, x, y, url} 또는 None
#   "found_by": 어디서 찾았나 ("팀 데이터" / "카카오" / "네이버")
#   "in_team":  팀 데이터에 있는 가게인가
#   "link":     지도 가게를 팀 가게와 이은 단계 ("A_주소+상호" 등) 또는 None
#   "score":    혼밥 지수 0~100 (혼밥 분석이 채움)
#   "evidence": 근거 목록 ["팀 판정: ...", "블로그: ..."]
#   "flags":    팀이 다시 확인할 것 ["블로그에 2인분 언급"]
#   "context":  {"open_now": bool|None, "walk_min": int|None, "weather": {...}} (상황이 채움)
#   "rejected": 이 가게가 걸린 규칙 목록 (검증이 채움)
# }
