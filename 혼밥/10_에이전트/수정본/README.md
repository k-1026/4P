# 10_에이전트 — 수정본

이 폴더는 최종본에 이르기까지의 **초안 · 검토판 · 점검 기록**이다. 최종본은 한 단계 위 폴더(`../`)에 있다.

- 파일 이름의 날짜(`_20261121`, `_1123` 등)는 그 판을 만든 날이다.
- 문서 안의 파일 경로는 작업할 때의 위치라 지금 폴더와 다를 수 있다.
- 에이전트를 만들어 가는 중간 코드다. 최종 통합본은 `../멀티에이전트_통합프롬프트/`에 있다.

## 11-26 팀원 작업 추가

| 폴더 · 파일 | 내용 | 만든 사람 |
|---|---|---|
| `에이전트뼈대_1125` | 오케스트레이터 + 탐색·혼밥분석·상황·검증 에이전트 뼈대, 탐색 에이전트 대화 기록 | 이건협 |
| `메뉴에이전트_1126` | 메뉴 에이전트 1단계: 대표메뉴·대표가격 고르기 | 이건협 |
| `날씨_취향_에이전트_1125-26` | 날씨 · 취향 에이전트, 조율자, 앱 서버, 시험 코드 | 이찬영 |

## 파일 (61개)

- `날씨_취향_에이전트_1125-26/README.md`
- `날씨_취향_에이전트_1125-26/agent_template.py`
- `날씨_취향_에이전트_1125-26/api_key.txt`
- `날씨_취향_에이전트_1125-26/app.py`
- `날씨_취향_에이전트_1125-26/app_data.py`
- `날씨_취향_에이전트_1125-26/coordinator.py`
- `날씨_취향_에이전트_1125-26/db_update.py`
- `날씨_취향_에이전트_1125-26/distance_agent.py`
- `날씨_취향_에이전트_1125-26/mbti.py`
- `날씨_취향_에이전트_1125-26/mbti_percent_demo.py`
- `날씨_취향_에이전트_1125-26/menu_agent.py`
- `날씨_취향_에이전트_1125-26/mock_agents.py`
- `날씨_취향_에이전트_1125-26/phone_app.py`
- `날씨_취향_에이전트_1125-26/real_stores.py`
- `날씨_취향_에이전트_1125-26/role_check.json`
- `날씨_취향_에이전트_1125-26/role_check.py`
- `날씨_취향_에이전트_1125-26/run.bat`
- `날씨_취향_에이전트_1125-26/sample_stores.py`
- `날씨_취향_에이전트_1125-26/scenario_demo.py`
- `날씨_취향_에이전트_1125-26/simulate.py`
- `날씨_취향_에이전트_1125-26/taste.py`
- `날씨_취향_에이전트_1125-26/taste_agent.py`
- `날씨_취향_에이전트_1125-26/test_coordinator.py`
- `날씨_취향_에이전트_1125-26/test_menu.py`
- `날씨_취향_에이전트_1125-26/test_real_stores.py`
- `날씨_취향_에이전트_1125-26/test_taste.py`
- `날씨_취향_에이전트_1125-26/test_total.py`
- `날씨_취향_에이전트_1125-26/test_weather.py`
- `날씨_취향_에이전트_1125-26/total.py`
- `날씨_취향_에이전트_1125-26/user_location.py`
- `날씨_취향_에이전트_1125-26/weather.py`
- `날씨_취향_에이전트_1125-26/weather_agent.py`
- `날씨_취향_에이전트_1125-26/weather_result.json`
- `날씨_취향_에이전트_1125-26/가게정보.csv`
- `날씨_취향_에이전트_1125-26/앱데이터.json`
- `날씨_취향_에이전트_1125-26/취향요약.json`
- `날씨_취향_에이전트_1125-26/혼밥일기.json`
- `메뉴에이전트_1126/README.md`
- `메뉴에이전트_1126/build_menus.py`
- `메뉴에이전트_1126/menu_parse.py`
- `메뉴에이전트_1126/test_menu_parse.py`
- `메뉴에이전트_1126/결과/menus.csv`
- `메뉴에이전트_1126/결과/stores_signature.csv`
- `에이전트뼈대_1125/honbap_agents/.env.example`
- `에이전트뼈대_1125/honbap_agents/.gitignore`
- `에이전트뼈대_1125/honbap_agents/README.md`
- `에이전트뼈대_1125/honbap_agents/agents/__init__.py`
- `에이전트뼈대_1125/honbap_agents/agents/context.py`
- `에이전트뼈대_1125/honbap_agents/agents/explore.py`
- `에이전트뼈대_1125/honbap_agents/agents/honbap.py`
- `에이전트뼈대_1125/honbap_agents/agents/orchestrator.py`
- `에이전트뼈대_1125/honbap_agents/agents/verify.py`
- `에이전트뼈대_1125/honbap_agents/board.py`
- `에이전트뼈대_1125/honbap_agents/config.py`
- `에이전트뼈대_1125/honbap_agents/llm.py`
- `에이전트뼈대_1125/honbap_agents/main.py`
- `에이전트뼈대_1125/honbap_agents/server.py`
- `에이전트뼈대_1125/honbap_agents/store_lookup.py`
- `에이전트뼈대_1125/honbap_agents/tools.py`
- `에이전트뼈대_1125/honbap_agents/web/index.html`
- `에이전트뼈대_1125/대화기록_탐색에이전트.md`
