"""핸드폰에서 여는 혼밥 앱 서버: 앱 화면(혼밥_홈화면_v2.html)과 AI 추천(조율자 + 에이전트)을 한 주소로 준다.

  GET  /                 앱 화면
  POST /api/recommend    {"location": {"lat", "lng", "accuracy_m"}, "mbti", "mbti_pct", "hurry", "budget", "budget_any", "category", "mbti_order", "choice"}
                         -> 조율자가 이끈 상의 내용과 최종 답 (JSON)

에이전트: 🌡️ 날씨(실제, 내 위치 격자) · 🚶 거리(실제, 내 위치에서 잰 거리) · 📒 취향(실제, 핸드폰 앱의 내 혼밥일기)
          📋 메뉴(실제, 혼밥DB의 주요 메뉴를 정리해서 공유)
          💰 가격(실제, 후보끼리 1인 가격 비교 · price_agent.py)
          🪑 혼밥(실제, 후보 안 '혼밥하기 좋아요' 순위 8점 + 1인석 2점 · solo_agent.py)
가게: 실제 데이터 real_stores.py (혼밥DB 동성로 최종본). 내 위치 1km 안에 가게가 없으면 동성로 가운데에서 잰다

실행: python phone_app.py   (http://localhost:8770, 핸드폰은 cloudflared 터널 주소로)
"""
import json
import os
import re
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import coordinator
import distance_agent
import mbti
import menu_agent
import app_data
import price_agent
import real_stores
import solo_agent
import taste
import taste_agent
import user_location
import weather_agent

PORT = 8770
HERE = os.path.dirname(os.path.abspath(__file__))
APP_HTML = os.path.join(os.path.dirname(HERE), "public", "index.html")
MAX_BODY = 300000  # 혼밥일기(사진 없이) 포함
# 내 PC(localhost)와 cloudflared 빠른 터널 주소만 받는다
HOST_OK = re.compile(r"^(localhost|127\.0\.0\.1)(:\d+)?$|^[a-z0-9-]+\.trycloudflare\.com$")
DEV_ORIGINS = {"http://localhost:8010", "http://127.0.0.1:8010"}  # PC에서 미리보기로 연 앱


def wrap(module, state):
    """실제 에이전트를 그대로 쓰되, 준비(prepare)만 미리 만든 값으로 바꾼다 (취향: 샘플 혼밥일기)"""
    names = ("opinion", "share", "candidates", "describe", "check", "score", "propose", "rebut")
    parts = {name: staticmethod(getattr(module, name)) for name in names if hasattr(module, name)}
    return type("Agent", (), {**parts, "prepare": staticmethod(lambda ctx: state)})


class rough_weather:
    """날씨 에이전트는 결과 파일(weather_result.json)에 위치를 적으므로, 소수 둘째 자리(약 1km)로 줄인 위치만 넘긴다.
    격자 한 칸이 5km라 날씨 값은 같다."""
    opinion, score, rebut = (staticmethod(getattr(weather_agent, n)) for n in ("opinion", "score", "rebut"))

    @staticmethod
    def prepare(ctx):
        place = ctx.get("origin")
        rough = {**place, "lat": round(place["lat"], 2), "lng": round(place["lng"], 2), "accuracy_m": None} if place else None
        return weather_agent.prepare({**ctx, "origin": rough})


def recommend(body, now=None):
    now = now or datetime.now()
    place = user_location.parse(body.get("location"))
    if place is None:
        return {"ok": False, "need_location": True, "text": "위치 정보가 없어서 추천을 시작하지 않았어요."}
    code = str(body.get("mbti") or "").upper() or None
    code = code if mbti.parse(code) else None
    stores = real_stores.agent_stores(place)
    origin, moved = place, False
    if not any(s["dist_m"] <= coordinator.RADIUS_M for s in stores):  # 동성로에서 멀면 동성로 가운데 기준
        origin = {"lat": real_stores.AREA["lat"], "lng": real_stores.AREA["lng"], "accuracy_m": None,
                  "source": "area", "area": real_stores.AREA["name"]}
        stores, moved = real_stores.agent_stores(origin), True
    diary = app_data.diary({"posts": clean_posts(body.get("posts")),
                            "restaurants": [{"id": s["id"], "name": s["name"]} for s in stores]})
    kinds = {s["name"]: app_data.food_kind(s) for s in stores}
    profile = taste.build_profile(diary, kinds, now.date())
    wanted = body.get("category") if body.get("category") in real_stores.CATEGORIES else None
    if wanted:  # 고른 음식 종류의 가게만 후보로 (일기를 읽은 뒤에 거른다)
        stores = [s for s in stores if s["category"] == wanted]
    menus, menus_day = real_stores.menus()
    agents = [
        {"name": "혼밥", "weight": 35, "module": solo_agent},
        {"name": "거리", "weight": 20, "module": distance_agent},
        {"name": "가격", "weight": 20, "module": price_agent},
        {"name": "취향", "weight": 15, "module": wrap(taste_agent, profile)},
        {"name": "날씨", "weight": 10, "module": rough_weather},
        {"name": "메뉴", "weight": 0, "module": menu_agent},
    ]
    ctx = {"now": now, "hurry": bool(body.get("hurry")), "mbti": code, "mbti_pct": body.get("mbti_pct"),
           "order": mbti.parse_order(body.get("mbti_order")),
           "choice": str(body.get("choice") or "")[:90] or None,   # raise:가게 / keep:가게
           "origin": origin, "diary": diary, "category": wanted, "budget": clean_budget(body.get("budget")), "budget_any": body.get("budget_any") is True,
           "menus": menus, "menus_updated": f"혼밥DB {menus_day}"}
    result = coordinator.run(ctx, stores, agents, [], assumed=[])
    names = ("혼밥", "거리", "가격", "취향", "날씨")
    return {
        "ok": result["ok"], "text": result["text"], "log": result["log"], "final": result.get("final", []),
        "notes": result.get("notes", []), "table": result.get("table", []), "lacking": result.get("lacking", []),
        "weights": result.get("weights", {}), "failed": result.get("failed", []),
        "ranking": [{"name": r["store"]["name"], "total": r["total"],
                     "scores": {n: r["scores"][n]["score"] for n in names if n in r["scores"]}}
                    for r in result.get("ranking", [])],
        "choice": result.get("choice"), "chosen": result.get("chosen"),
        "location": {"lat": place["lat"], "lng": place["lng"], "accuracy_m": place["accuracy_m"],
                     "label": user_location.label(place)},
        "sample_stores": False, "moved_to_area": moved, "area": real_stores.AREA["name"], "diary_count": len(diary),
    }


def config_js():
    """브라우저가 읽는 카카오맵 JavaScript 키 (환경 변수 KAKAO_JS_KEY)"""
    return f"window.KAKAO_JS_KEY = {json.dumps(os.environ.get('KAKAO_JS_KEY', ''))};\n"


def clean_budget(value):
    """사용자가 말한 예산(원). 숫자가 아니거나 말이 안 되는 값이면 없는 것으로 본다."""
    ok = isinstance(value, (int, float)) and not isinstance(value, bool) and 1000 <= value <= 1_000_000
    return int(value) if ok else None


def clean_posts(posts):
    """핸드폰이 보낸 내 혼밥일기 (별점·후기·혼밥 포인트·가게·시각만, 사진은 받지 않음)"""
    out = []
    for p in posts if isinstance(posts, list) else []:
        if not isinstance(p, dict):
            continue
        try:
            out.append({"id": str(p.get("id", ""))[:40], "ts": float(p.get("ts") or 0), "rid": int(p.get("rid")),
                        "rate": max(1, min(5, int(p.get("rate") or 5))), "text": str(p.get("text") or "")[:500],
                        "points": [str(t)[:30] for t in (p.get("points") or [])[:10] if isinstance(t, str)]})
        except (TypeError, ValueError):
            continue
    return out[:300]


class Handler(BaseHTTPRequestHandler):
    def host_ok(self):
        return bool(HOST_OK.match(self.headers.get("Host", "").lower()))

    def send(self, status, body, kind="application/json; charset=utf-8", origin=None):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.host_ok():
            self.send_error(403)
            return
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            with open(APP_HTML, "rb") as file:
                self.send(200, file.read(), "text/html; charset=utf-8")
        elif path == "/config.js":  # 카카오맵 JavaScript 키 (브라우저에서 쓰는 키라 화면에 보내도 되는 값)
            self.send(200, config_js().encode("utf-8"), "application/javascript; charset=utf-8")
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        origin = self.headers.get("Origin")
        if origin not in DEV_ORIGINS:
            self.send_error(403)
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "POST")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        origin = self.headers.get("Origin")
        same = origin in (None, f"http://{self.headers.get('Host')}", f"https://{self.headers.get('Host')}")
        if self.path != "/api/recommend" or not self.host_ok() or not (same or origin in DEV_ORIGINS):
            self.send_error(403)
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self.send_error(413)
            return
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("JSON 객체가 아니에요")
        except (ValueError, UnicodeDecodeError):
            self.send(400, {"ok": False, "text": "보낸 값을 읽지 못했어요."}, origin=origin if origin in DEV_ORIGINS else None)
            return
        try:
            answer = recommend(body)
        except Exception as error:  # 에이전트 오류도 화면에 알린다
            answer = {"ok": False, "text": f"에이전트 실행 중 오류가 났어요: {type(error).__name__}"}
        self.send(200, answer, origin=origin if origin in DEV_ORIGINS else None)

    def log_message(self, fmt, *args):  # 위치가 찍히지 않게 요청 줄만 짧게
        print(f"{datetime.now():%H:%M:%S} {self.command} {self.path.split('?')[0]}")


if __name__ == "__main__":
    print(f"http://localhost:{PORT} 에서 실행 중")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
