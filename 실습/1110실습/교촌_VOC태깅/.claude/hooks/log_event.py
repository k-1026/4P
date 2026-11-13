#!/usr/bin/env python3
"""Claude Code 훅 이벤트 기록기.

Claude Code가 훅으로 stdin에 넘겨주는 JSON을 읽어,
이벤트마다 초 단위 타임스탬프(ts)를 붙여 JSON Lines 파일에 한 줄씩 추가 기록한다.

- 프로젝트 루트: 환경변수 AX_PROJECT_ROOT
  (없으면 Claude Code가 주는 CLAUDE_PROJECT_DIR, 그것도 없으면 이 파일 기준 두 단계 위 폴더)
- 기록 파일: <프로젝트 루트>/ax/demo/logs/events.jsonl
- tool_response: 길 수 있으므로 문자열로 바꾼 뒤 앞 600자만 남긴다.
- 훅 때문에 Claude Code 작업이 막히지 않도록, 오류가 나도 항상 exit 0으로 끝낸다.
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT_ENV = "AX_PROJECT_ROOT"
MAX_RESPONSE_CHARS = 600


def project_root() -> tuple[Path, str]:
    """(루트 경로, 어디서 정했는지) 를 돌려준다."""
    if os.environ.get(ROOT_ENV):
        return Path(os.environ[ROOT_ENV]), ROOT_ENV
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        return Path(os.environ["CLAUDE_PROJECT_DIR"]), "CLAUDE_PROJECT_DIR"
    return Path(__file__).resolve().parents[2], "script_path"


def to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def main() -> None:
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        data = {"raw": raw[:MAX_RESPONSE_CHARS]}

    record = {
        "ts": int(time.time()),  # 초 단위 유닉스 타임스탬프
        "event": data.get("hook_event_name", ""),
        "session_id": data.get("session_id", ""),
        "tool_name": data.get("tool_name", ""),
        "tool_input": data.get("tool_input"),
        "tool_response": to_text(data.get("tool_response"))[:MAX_RESPONSE_CHARS],
    }
    # 그 밖의 항목(prompt, message, agent 관련 필드 등)도 함께 남긴다
    skip = {"hook_event_name", "session_id", "tool_name", "tool_input", "tool_response", "transcript_path"}
    for key, value in data.items():
        if key not in skip:
            record[key] = value

    # 어떤 환경변수로 기록 위치가 정해졌는지 눈으로 확인할 수 있게 남긴다
    root, root_source = project_root()
    record["root_source"] = root_source
    record["root"] = str(root)

    log_file = root / "ax" / "demo" / "logs" / "events.jsonl"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # 기록 실패가 작업을 막지 않게 한다
        print(f"log_event 오류: {exc}", file=sys.stderr)
    sys.exit(0)
