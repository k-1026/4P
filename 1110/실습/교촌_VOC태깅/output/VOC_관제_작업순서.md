# VOC 태깅 관제 — 처음부터 끝까지 작업 순서

이 문서는 VOC(고객 리뷰) 태깅 작업 전체를 순서대로 정리한 것입니다. 서브에이전트가 리뷰를 태깅하고 채점하면, 그 과정을 관제 화면에서 지켜보고, 마지막에 사람이 대조하고 승인합니다.
`실습2` 폴더에서 실제로 돌려 본 구성을 기준으로 썼으며, 다른 프로젝트에 옮길 때 바꿀 곳은 [7장](#7-다른-프로젝트로-옮길-때)에 모았습니다.

---

## 0. 한눈에 보기

```
원문(archive/batchN)
   │  ① 원문 준비
   ▼
review-tagger ──► ax/demo/parts/part_N.csv     ② 태깅   (10건씩 즉시 저장)
   ▼
review-grader ──► ax/demo/grades/grade_N.md    ③ 채점   (범위·근거·형식 점수)
   ▼
관제 서버 판정                                  ④ 점수 판정 (세 점수 80점↑, 검토 5%↓)
   ▼
사용자 대조 10건                                ⑤ 사용자 대조 (9건 이상 동의)
   ▼
사용자 승인                                     ⑥ 최종 승인 (사람만 누름)

훅(log_event.py) ──► ax/demo/logs/events.jsonl ──► 관제 서버 ──► 관제 화면(브라우저)
```

| 단계 | 하는 쪽 | 끝났다고 보는 기준 |
|---|---|---|
| ① 원문 준비 | `archive/batchN/` | 원문 파일 100건이 있음 |
| ② 태깅 | `review-tagger` 서브에이전트 | `part_N.csv`가 100행 (10건 × 10번 저장) |
| ③ 채점 | `review-grader` 서브에이전트 | `grade_N.md`가 생김 |
| ④ 점수 판정 | 관제 서버 | 범위·근거·형식 모두 80점 이상, 검토 5% 이하, 검토 행마다 이유 있음 |
| ⑤ 사용자 대조 | 사용자 | 샘플 10건 중 9건 이상 동의 |
| ⑥ 최종 승인 | 사용자 | 관제 화면에서 승인 버튼을 누름 (Claude는 승인하지 않음) |

---

## 1. 준비물

| 항목 | 확인 방법 | 비고 |
|---|---|---|
| Python 3 | `python --version` | 이 PC에서는 `python3` 명령이 동작하지 않아 `python`을 씁니다 |
| Claude Code CLI | 관제 서버가 자동으로 찾음 | PATH에 `claude`가 없어도 데스크톱 앱 안의 `claude.exe`를 찾습니다. 다른 경로를 쓰려면 환경변수 `CLAUDE_BIN`에 지정 |
| 추가 패키지 | 필요 없음 | 관제 서버는 Python 기본 기능만 씁니다 |

---

## 2. 폴더 구성

```
프로젝트/
├─ CLAUDE.md                         작업 원칙 · VOC 태깅 품질 기준(통과 조건)
├─ painpoint/painpoint_def.md        태그 정의서 (허용 태그 7개)
├─ archive/
│  ├─ batch1/r_001.md … r_100.md     원문 (앞부분에 voc_id·source·date)
│  ├─ batch2/ …  batch3/ …
│  └─ metadata.csv
├─ .claude/
│  ├─ settings.json                  환경변수 · 훅 · 권한
│  ├─ launch.json                    앱 브라우저 창에서 관제 서버를 띄우는 설정
│  ├─ hooks/log_event.py             훅 이벤트 기록기
│  └─ agents/
│     ├─ review-tagger.md            분류 담당
│     └─ review-grader.md            채점 담당
├─ ax/demo/
│  ├─ parts/part_N.csv               태깅 결과
│  ├─ grades/grade_N.md              채점표
│  └─ logs/events.jsonl              훅 로그 (git 제외)
└─ board/
   ├─ control_server.py              관제 서버
   ├─ monitor.html                   관제 화면
   └─ state/                         대조 기록 · 승인 기록 · 실행 기록(jobs/)
```

원문 파일 형식 예시 (`archive/batch1/r_001.md`)

```
---
voc_id: r_001
source: 블로그
date: 2026-08-27
---
현금 5천 원 들고 갔다가 … 매대 앞에 결제 가능 표시라도 붙여 주세요.
```

---

## 3. 설정하기 (처음 한 번)

### 3-1. 태그 정의서 — `painpoint/painpoint_def.md`
- **분류 규칙** 부분에 허용 태그를 한 줄로 적습니다. 예: `허용 태그: P1 · P2 · P3 · H1 · H2 · 해당없음 · 검토`
- 태그마다 판정 힌트(자주 나오는 표현)를 적어 두면 태깅이 안정됩니다.
- 판정이 애매하면 `검토`로 넣고 note에 이유를 적는 규칙을 정합니다. 원인이 섞인 경우, 본인 경험이 아닌 전언, 외국어 등이 해당합니다.

### 3-2. 서브에이전트 2개 — `.claude/agents/`
| 에이전트 | 입력 | 출력 | 꼭 지킬 규칙 |
|---|---|---|---|
| `review-tagger` | `archive/batchN/r_*.md` | `ax/demo/parts/part_N.csv` | **10건 읽을 때마다 바로 저장**. 헤더는 `voc_id,tag,evidence,note`. evidence는 원문 그대로 15자 이내 |
| `review-grader` | part 파일 + 원문 + 기준 문서 | `ax/demo/grades/grade_N.md` | 분류를 고치지 않음. 점수마다 계산 근거를 적음. 스스로 승인하지 않음 |

> 관제 서버가 점수를 읽으려면 채점표 맨 위에 `범위: NN점`, `근거: NN점`, `형식: NN점`, `검토 건수: n건` 형태로 숫자가 있어야 합니다. 실행 버튼으로 돌리면 서버가 이 형식을 지시합니다.

### 3-3. 환경변수 · 훅 — `.claude/settings.json`
```json
{
  "env": { "AX_PROJECT_ROOT": "C:/Users/Green/Desktop/실습2" },
  "hooks": {
    "UserPromptSubmit": [ { "hooks": [ { "type": "command", "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/log_event.py\"" } ] } ],
    "PreToolUse":       [ { "matcher": "*", "hooks": [ { "type": "command", "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/log_event.py\"" } ] } ],
    "PostToolUse":      [ { "matcher": "*", "hooks": [ { "type": "command", "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/log_event.py\"" } ] } ],
    "SubagentStop":     [ { "hooks": [ { "type": "command", "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/log_event.py\"" } ] } ],
    "Stop":             [ { "hooks": [ { "type": "command", "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/log_event.py\"" } ] } ]
  }
}
```
- `log_event.py`는 이벤트마다 한 줄씩 `ax/demo/logs/events.jsonl`에 기록합니다.
- 기록 위치는 `AX_PROJECT_ROOT`로 정합니다. 이 값이 없으면 `CLAUDE_PROJECT_DIR`, 그것도 없으면 스크립트 위치를 씁니다. 로그마다 `root_source` 항목에 어느 값을 썼는지 남습니다.
- 서브에이전트 안에서 생긴 이벤트에는 `agent_id`와 `agent_type`이 붙습니다. 관제 화면은 이 값으로 "어느 에이전트가 어느 묶음에서 무엇을 하는지"를 알아냅니다.
- **설정을 바꾼 뒤에는 새 세션을 열어야 훅이 적용됩니다.**
- 로그는 git에 올리지 않습니다. `.gitignore`에 `ax/demo/logs/`를 넣습니다.

### 3-4. 관제 서버 실행 설정 — `.claude/launch.json`
```json
{
  "version": "0.0.1",
  "configurations": [
    { "name": "voc-board", "runtimeExecutable": "python",
      "runtimeArgs": ["board/control_server.py", "--port", "8765"], "port": 8765 }
  ]
}
```

---

## 4. 실행 순서 (매번)

### 4-1. 관제 서버 켜기
```bash
python board/control_server.py
```
브라우저에서 `http://127.0.0.1:8765`를 엽니다. 이 PC 안에서만 열립니다.
점수만 빠르게 보고 싶을 때는 서버를 켜지 않고 아래처럼 실행하면 됩니다.
```bash
python board/control_server.py --once
```

### 4-2. 관제 화면 보는 법
- **맨 위:** `▶ 전체 실행` / `■ 전체 중지`
- **카드 3개 (batch1·2·3):** 묶음마다 하나씩 있습니다.
  - 상태 표시: 대기, **진행 중**(형광 깜박임), 사용자 차례, 완료, 확인 필요
  - `▶ 실행` 버튼은 실행 중에는 `■ 중지`로 바뀝니다.
  - 6단계 목록: 끝난 단계는 ✓, **지금 진행 중인 단계는 형광으로 깜박**입니다. 파란 테두리는 지금 머문 단계입니다.
  - **10건 단위 막대그래프:** 막대 1개가 원문 10건입니다. 초록은 저장됨, 형광 깜박임은 지금 작업 중, 빨강은 중간에 멈춤입니다. 막대에 마우스를 올리면 범위와 태그별 개수가 나옵니다.
  - 범위 · 근거 · 형식 점수와 검토 건수. 80점 이상은 초록, 미만은 빨강입니다.
  - "지금: review-tagger · Read r_158.md"처럼 에이전트가 방금 한 동작이 한 줄로 나옵니다.
- **접힌 영역:** `확인 · 승인`, `실행 기록`

### 4-3. 태깅 → 채점 실행 (②·③단계)
1. 카드의 `▶ 실행`을 누르거나, 맨 위 `▶ 전체 실행`을 누릅니다.
2. 확인 창에 묶음별로 할 일이 나옵니다. **남은 단계만 실행합니다.**
   - 태깅이 덜 됐으면 → 태깅(처음부터) → 채점
   - 태깅만 끝났으면 → 채점
   - 둘 다 끝났으면 → "처음부터 다시 할까요?" (part·grade 파일을 덮어씁니다)
3. 확인을 누르면 서버가 Claude CLI를 화면 없이(`-p`) 띄우고, 그 CLI가 서브에이전트를 부릅니다.
   - **묶음마다 따로, 동시에** 돕니다.
   - 태깅이 100행을 다 채우지 못하면 채점은 건너뜁니다.
4. 카드에서 진행을 지켜봅니다. 실제로 걸린 시간은 태깅 약 1분 30초, 채점 약 1분 10초였습니다.
5. 멈추려면 `■ 중지`를 누릅니다.
   - 서브에이전트까지 프로세스를 모두 끝내고, 대기 중인 작업은 취소합니다.
   - 이미 저장된 행은 남고, 그 카드에는 빨간 "중단 · 60행만 저장"처럼 표시됩니다.

> 실행 버튼은 실제로 Claude를 돌리므로 사용량이 듭니다.
> 채팅에서 직접 시켜도 됩니다. 예: "review-tagger로 batch1 태깅 실행", "review-grader로 batch1 채점 실행". 이렇게 해도 훅 로그를 통해 관제 화면에 똑같이 표시됩니다.

### 4-4. 점수 판정 (④단계, 자동)
| 점수 | 계산 | 통과 |
|---|---|---|
| 범위 | 정상 voc_id 수 ÷ 원문 수 × 100, 중복 1건당 −5 | 80점 이상 |
| 근거 | evidence가 원문에 그대로 있고 15자 이내인 행의 비율 × 100 | 80점 이상 |
| 형식 | 헤더 25 + 허용 태그 비율×25 + note 규칙 비율×25 + 검토 5% 이하면 25 | 80점 이상 |
| 검토 건수 | 검토 행 수 ÷ 전체 | 5% 이하, 모든 검토 행에 이유 |

- grade 파일이 있으면 **채점관 점수**를, 없으면 **관제 서버 자동 검사 점수**를 씁니다. 카드 아래에 어느 쪽인지 표시됩니다.
- ⚠ **아직 정하지 않은 기준:** evidence 15자에 **띄어쓰기를 포함할지**가 정의서에 없습니다. 지금은 포함해서 셉니다. 실제로 batch1은 포함하면 근거 91점, 빼면 100점이었습니다.

### 4-5. 사용자 대조 (⑤단계, 사람)
1. 아래 `확인 · 승인`을 펼치고 대상 묶음(part_N)을 고릅니다.
2. `샘플 10건 뽑기`를 누릅니다. 태그별로 고르게 무작위로 뽑습니다.
3. 원문(인용 부분은 노란색 표시)과 태그를 비교해 `동의` 또는 `비동의`를 누릅니다. 같은 버튼을 다시 누르면 취소됩니다.
4. 10건 중 **9건 이상 동의**해야 통과입니다.

### 4-6. 최종 승인 (⑥단계, 사람)
1. 조건 3개(점수 80점, 검토 기준, 대조 9/10)가 모두 ✅이면 `승인` 버튼이 켜집니다.
2. 승인자 이름을 적고 누르면 `board/state/approvals.json`에 기록됩니다.
3. 조건을 못 채우면 서버가 승인을 거부합니다. Claude는 승인 버튼을 누르지 않습니다.
4. 잘못 눌렀다면 `승인 취소`를 누릅니다.

---

## 5. 파일이 쌓이는 곳

| 파일 | 만드는 쪽 | 내용 |
|---|---|---|
| `ax/demo/parts/part_N.csv` | review-tagger | 태깅 결과 100행 |
| `ax/demo/grades/grade_N.md` | review-grader | 채점 패널 · 검토 건수 · 감점 내역 · 샘플 · 판정 |
| `ax/demo/logs/events.jsonl` | 훅 | 모든 이벤트 (root_source, agent_type 포함) |
| `board/state/verify_part_N.json` | 관제 서버 | 대조 샘플과 동의/비동의 |
| `board/state/approvals.json` | 관제 서버 | 승인자 · 시각 · 승인 당시 점수 |
| `board/state/jobs/*.log`, `history.json` | 관제 서버 | 실행 버튼 작업의 출력과 기록 |

---

## 6. 자주 막히는 곳

| 증상 | 원인 | 해결 |
|---|---|---|
| 실행 버튼을 눌러도 아무 일이 없음 | 앱 안의 브라우저 창은 `confirm()` 확인 창을 막고 늘 "취소"로 처리함 | 지금 화면은 페이지 안에 직접 그린 확인 창을 써서 해결됨. 화면을 고칠 때 `confirm()`·`alert()`를 다시 쓰지 말 것 |
| 중지했는데 계속 깜박임 | 강제로 끝난 서브에이전트는 훅 로그에 `SubagentStop`이 남지 않음 | 서버가 중지 기록으로 '중지됨' 처리함 (반영됨) |
| 서버를 다시 켰더니 작업이 끊김 | 실행 중인 작업은 서버 안에서 관리됨 | **실행 중에는 서버를 재시작하지 말 것**. 실행 기록에서 끝났는지 먼저 확인 |
| `tail` 명령이 없다고 나옴 (PowerShell) | `tail`은 PowerShell 명령이 아님 | `Get-Content ax/demo/logs/events.jsonl -Tail 5 -Encoding utf8` |
| `python3`가 동작하지 않음 | 이 PC에는 `python`만 있음 | 훅과 실행 설정에 `python` 사용 |
| 훅 기록이 안 쌓임 | 설정은 세션을 시작할 때 읽음 | 새 세션을 열기 |
| "claude 실행 파일을 찾지 못함" | PATH에 없고 앱 경로도 못 찾음 | 환경변수 `CLAUDE_BIN`에 `claude.exe` 전체 경로 지정 |
| 채점관 점수가 화면에 안 나옴 | grade 파일에서 숫자를 못 읽음 | 채점표 맨 위에 `범위: NN점` 형태로 적게 하기 |

---

## 7. 다른 프로젝트로 옮길 때

### 7-1. 복사할 것
- `.claude/hooks/log_event.py`, `.claude/settings.json`(훅·env 부분), `.claude/launch.json`
- `.claude/agents/review-tagger.md`, `.claude/agents/review-grader.md`
- `board/control_server.py`, `board/monitor.html`
- `CLAUDE.md`의 "VOC 태깅 품질 기준" 표

### 7-2. 바꿀 것
| 위치 | 값 | 이번 프로젝트 값 |
|---|---|---|
| `.claude/settings.json` → `env.AX_PROJECT_ROOT` | 새 프로젝트 경로 | `C:/Users/Green/Desktop/실습2` |
| `painpoint/painpoint_def.md` | 태그 정의 | P1·P2·P3·H1·H2·해당없음·검토 |
| `board/control_server.py` → `ALLOWED` | 허용 태그 목록 (정의서와 같게) | 위와 같음 |
| `board/control_server.py` → `PASS_SCORE` | 통과 점수 | 80 |
| `board/control_server.py` → `REVIEW_MAX_RATIO` | 검토 비율 상한 | 0.05 |
| `board/control_server.py` → `EVIDENCE_MAX` | 인용 글자 수 | 15 |
| `board/control_server.py` → `SAMPLE_SIZE`, `AGREE_MIN` | 대조 건수 · 동의 기준 | 10, 9 |
| `board/control_server.py` → `CHUNK` | 저장 단위 (막대 1개) | 10 |
| `board/control_server.py` → `PROMPTS` | 에이전트에게 주는 지시문 | 묶음 N 태깅 / 채점 |
| 원문 폴더 이름 | `archive/batchN/r_*.md` 형식을 유지하거나, 서버의 `batches()`·`originals()`를 고침 | batch1~3, 100건씩 |

### 7-3. 옮긴 뒤 확인 순서
1. 새 세션을 열고 아무 작업이나 한 뒤 `ax/demo/logs/events.jsonl`에 줄이 쌓이는지 봅니다.
2. `python board/control_server.py --once`로 점수 계산이 되는지 봅니다.
3. 관제 서버를 켜고, 묶음 하나만 `▶ 실행`해 형광 깜박임과 10건 막대가 차오르는지 봅니다.
4. 대조 → 승인까지 한 번 끝까지 해 봅니다.

---

## 8. 지켜야 할 원칙 (CLAUDE.md 요약)
- 모든 산출물은 한국어로 씁니다.
- 수치와 사실에는 출처(파일명·페이지)를 적고, 자료에 없는 내용은 추정이라고 밝힙니다.
- 원본(PDF·원문 리뷰)은 수정하지 않습니다.
- **최종 승인은 사용자가 직접 합니다.** Claude와 서브에이전트는 승인하지 않습니다.
