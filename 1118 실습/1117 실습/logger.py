"""실행 로그: 이벤트를 한 줄씩 logs/<run_id>.jsonl 에 기록한다."""
import json
import threading
import time
import uuid
from pathlib import Path

LOG_DIR = Path(__file__).parent / "logs"
_lock = threading.Lock()  # 병렬 스레드가 동시에 써도 줄이 섞이지 않게 한다


def new_run_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]


def make_logger(run_id: str):
    """이벤트 하나를 받아 JSONL 한 줄로 저장하는 함수를 만든다."""
    LOG_DIR.mkdir(exist_ok=True)
    path = LOG_DIR / f"{run_id}.jsonl"

    def log(event: dict) -> None:
        record = {"ts": time.time(), "run_id": run_id, **event}
        with _lock, path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return log
