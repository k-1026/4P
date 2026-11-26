"""PC에서 실행: python run_local.py  ->  http://localhost:8770
.env 파일(.env.example 참고)의 값을 환경 변수로 읽는다."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "agents"))

env = os.path.join(HERE, ".env")
if os.path.exists(env):
    with open(env, encoding="utf-8-sig") as file:
        for line in file:
            key, sep, value = line.strip().partition("=")
            if sep and key and not key.startswith("#"):
                os.environ.setdefault(key.strip(), value.strip())

import phone_app  # noqa: E402

port = int(sys.argv[1]) if len(sys.argv) > 1 else phone_app.PORT
print(f"http://localhost:{port} 에서 실행 중")
phone_app.ThreadingHTTPServer(("127.0.0.1", port), phone_app.Handler).serve_forever()
