"""날씨·취향기록 에이전트를 브라우저에서 버튼으로 실행하는 화면 (내 PC에서만 접속)."""
import contextlib
import html
import io
import json
import os
import re
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

import app_data
import coordinator
import mbti
import taste
import taste_agent
import total
import weather

PORT = 8765
FOODS = ("따뜻한 국물", "따뜻한 요리", "차가운 요리", "모름")
AUTO = "자동 (가게정보에서 찾기)"
KINDS = (AUTO,) + taste.CATEGORIES  # 취향용 음식 종류
ROWS = (1, 2, 3)  # 비교할 가게 칸
ALLOWED_HOSTS = {f"localhost:{PORT}", f"127.0.0.1:{PORT}"}

PAGE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>날씨·취향기록 에이전트</title>
<style>
  body {{ font-family: sans-serif; max-width: 420px; margin: 40px auto; padding: 0 16px; }}
  button {{ font-size: 18px; padding: 12px; width: 100%; cursor: pointer; }}
  label {{ display: block; margin-bottom: 10px; }}
  input, select {{ font-size: 16px; padding: 6px; width: 100%; box-sizing: border-box; }}
  fieldset {{ margin-bottom: 12px; }}
  pre {{ white-space: pre-wrap; word-break: break-all; font-size: 16px; line-height: 1.7;
        border: 1px solid #ccc; border-radius: 8px; padding: 16px; }}
</style>
</head>
<body>
<h1>날씨·취향기록 에이전트</h1>
<p>대구 · 체감온도 기준 / 혼밥일기 기준</p>
<p><small>{app_status}</small></p>
<h2>조율자: 오늘 점심 추천</h2>
<form method="post" action="/coordinate">
  <label><input type="checkbox" name="hurry" value="1" style="width:auto"> 시간이 없어요</label>
  <label><input type="checkbox" name="assume" value="1" style="width:auto"> 아직 없는 에이전트는 있다고 가정하기</label>
  <button>에이전트끼리 상의해서 추천받기</button>
</form>
{coordinated}
<h2>에이전트 하나씩 보기</h2>
<form method="post" action="/"><button>날씨 확인하기</button></form>
{result}
<form method="post" action="/taste"><button>취향기록 확인하기</button></form>
{taste_result}
<h2>다른 에이전트 말에 답하기</h2>
<form method="post" action="/reply">
  <label>말한 에이전트
    <select name="sender"><option>거리</option><option>혼밥편의</option><option>예산</option><option>날씨</option><option>취향기록</option></select>
  </label>
  <label>가게 이름 <input name="store" required maxlength="30" placeholder="B 라멘집"></label>
  <label>가게 음식 종류 (날씨용)
    <select name="food_type"><option>따뜻한 국물</option><option>따뜻한 요리</option><option>차가운 요리</option><option>모름</option></select>
  </label>
  <label>가게 음식 종류 (취향용) <select name="kind">{kinds}</select></label>
  <p>반론을 들으려면 지금 1순위 가게도 적어요. 비워 두면 맞는지만 답해요.</p>
  <label>지금 1순위 가게 이름 <input name="current" maxlength="30" placeholder="A 국밥집"></label>
  <label>지금 1순위 음식 종류 (날씨용)
    <select name="current_type"><option>따뜻한 국물</option><option>따뜻한 요리</option><option>차가운 요리</option><option>모름</option></select>
  </label>
  <label>지금 1순위 음식 종류 (취향용) <select name="current_kind">{kinds}</select></label>
  <label><input type="checkbox" name="hurry" value="1" style="width:auto"> 사용자가 "시간이 없어요"라고 함</label>
  <button>날씨·취향기록 에이전트 답 듣기</button>
</form>
{answer}
<h2>가중치 정하고 순위 보기</h2>
{rank_form}
{ranking}
</body>
</html>"""


def run_agent():
    """에이전트를 한 번 실행하고 화면에 출력된 글을 돌려준다."""
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        try:
            weather.main()
        except Exception as error:
            print("실행 중 오류가 났어요:", type(error).__name__, error)
    return output.getvalue()


def fresh_report():
    """사용할 때마다 날씨를 새로 가져온다. 실패하면 이전 값을 쓰지 않고 (None, 안내)."""
    output = io.StringIO()
    report = None
    with contextlib.redirect_stdout(output):
        try:
            report = weather.main()
        except Exception as error:
            print("실행 중 오류가 났어요:", type(error).__name__, error)
    if report is None:
        return None, "날씨를 새로 가져오지 못해서 계산하지 않았어요.\n" + output.getvalue()
    return report, ""


def kind_options(selected=""):
    return "".join(f"<option{' selected' if kind == selected else ''}>{kind}</option>" for kind in KINDS)


def taste_data():
    """취향 요약표(그날 처음이면 혼밥일기로 새로 만듦)와 가게정보. 실패하면 (None, None, 안내)."""
    try:
        return taste.load_profile(), taste.sources()[1], ""  # 가게 종류: 앱 가게 목록 + 가게정보.csv
    except Exception as error:
        return None, None, f"혼밥일기를 읽지 못했어요: {type(error).__name__} {error}"


def kind_of(stores, name, chosen):
    """취향용 음식 종류: 직접 고른 값이 있으면 그것, 아니면 가게정보에서 찾는다 (없으면 기타)."""
    return chosen if chosen in taste.CATEGORIES else stores.get(name.strip(), "기타")


def mbti_text(code):
    return mbti.label(code) if mbti.parse(code) else "없음 (앱에서 혼밥 MBTI 테스트를 하면 반영돼요)"


def user_mbti():
    """앱이 보낸 혼밥 MBTI (앱에서 테스트를 안 했거나 앱 데이터가 없으면 None)"""
    data = app_data.load()
    return data.get("mbti") if data else None


def run_taste():
    profile, _, notice = taste_data()
    if profile is None:
        return notice
    code = user_mbti()  # 탐험파/단골파는 taste_agent.opinion이 덧붙인다
    return (f"📒 {taste_agent.opinion(profile, {'mbti': code})}\n"
            f"(취향 요약표: {profile['만든날']} 기준, {profile.get('출처', '일기')} {profile['기록수']}개"
            f" · 혼밥 MBTI {mbti_text(code)})")


def app_origin_ok(origin):
    """앱을 파일로 열면 Origin이 'null', 내 PC 서버로 열면 localhost/127.0.0.1"""
    if origin in (None, "null"):
        return True
    return bool(re.fullmatch(r"http://(localhost|127\.0\.0\.1)(:\d+)?", origin))


def app_status():
    data = app_data.load()
    if data is None:
        return "앱 데이터 없음: 혼밥 앱 '마이' 탭에서 '지금 보내기'를 눌러 주세요. (그 전에는 샘플 일기를 써요)"
    when = datetime.fromtimestamp(os.path.getmtime(data["path"])).strftime("%m월 %d일 %H:%M")
    return (f"앱 데이터 연결됨: 내 일기 {len(data['posts'])}개, 가게 {len(data['restaurants'])}곳, "
            f"혼밥 MBTI {mbti_text(data.get('mbti'))} ({when} 받음)")


def run_coordinator(form):
    hurry = form.get("hurry", [""])[0] == "1"
    try:
        assume = form.get("assume", [""])[0] == "1"
        return coordinator.run({"hurry": hurry}, assume_missing=assume)["text"]
    except Exception as error:
        return f"조율자 실행 중 오류가 났어요: {type(error).__name__} {error}"


def rank_form(values):
    """가중치와 가게를 적는 칸. 보낸 값은 그대로 남겨 둔다."""
    def value(name):
        return values.get(name, [""])[0]

    def number(name, label, top):
        return (f'<label>{label} <input type="number" name="{name}" min="0" max="{top}" step="any" '
                f'value="{html.escape(value(name))}"></label>')

    parts = ['<form method="post" action="/rank">', "<fieldset><legend>가중치 (%, 합 100)</legend>"]
    parts += [number(f"weight_{name}", name, 100) for name in total.FACTORS]
    parts.append("</fieldset>")
    for row in ROWS:
        options = "".join(f"<option{' selected' if value(f'food{row}') == food else ''}>{food}</option>"
                          for food in FOODS)
        parts += [f"<fieldset><legend>가게 {row}</legend>",
                  f'<label>이름 <input name="name{row}" maxlength="30" '
                  f'value="{html.escape(value(f"name{row}"))}"></label>',
                  f'<label>음식 종류 (날씨 점수는 자동) <select name="food{row}">{options}</select></label>',
                  f'<label>음식 종류 (취향 점수는 자동) <select name="kind{row}">'
                  f'{kind_options(value(f"kind{row}"))}</select></label>',
                  number(f"price{row}", "가격 점수 (0~10)", 10),
                  "</fieldset>"]
    parts.append("<button>순위 계산하기</button></form>")
    return "\n".join(parts)


def run_rank(form):
    """가게별 점수에 가중치를 곱해 순위를 글로 만든다."""
    report, notice = fresh_report()
    if report is None:
        return notice
    profile, shop_kinds, notice = taste_data()
    if profile is None:
        return notice
    code = user_mbti()

    def value(name):
        return form.get(name, [""])[0].strip()

    try:
        weights = {name: float(value(f"weight_{name}")) for name in total.FACTORS}
        stores = []
        for row in ROWS:
            name = value(f"name{row}")
            if not name:
                continue
            points = weather.score(report, value(f"food{row}"))
            kind = kind_of(shop_kinds, name, value(f"kind{row}"))
            liking = taste.score(profile, name, kind, code)
            why = taste.reason(profile, name, kind) + (f" ({liking['mbti']})" if liking.get("mbti") else "")
            stores.append({"name": name, "confirmed": points["confirmed"],
                           "taste_sure": liking["확실도"],
                           "taste_why": why, "scores": {
                               "날씨": points["score"],
                               "취향": liking["score"],
                               "가격": float(value(f"price{row}"))}})
    except ValueError:
        return "퍼센트와, 이름을 적은 가게의 가격 점수를 모두 숫자로 적어 주세요."
    if not stores:
        return "가게를 하나 이상 적어 주세요."
    try:
        results = total.rank(stores, weights)
    except ValueError as error:
        return str(error)

    lines = ["가중치: " + " · ".join(f"{name} {weights[name]:g}%" for name in total.FACTORS)]
    for item in results:
        detail = " + ".join(f"{name} {item['scores'][name]:g}×{weights[name] / 100:g}"
                            for name in total.FACTORS)
        note = "" if item["confirmed"] else " (음식 종류 확인 안 됨: 날씨는 5점)"
        if item["taste_sure"] == "낮음":
            note += f" (취향 기록 없음: 취향은 기본 {taste.NO_RECORD}점)"
        lines.append(f"{item['place']}순위 {item['name']}: {item['total']:g}점{note}\n  = {detail}"
                     f"\n  취향: {item['taste_why']} (확실도 {item['taste_sure']})")
    lines.append(f"날씨 확인 시각: {report['time']} / 취향 요약표: {profile['만든날']} 기준")
    return "\n".join(lines)


def run_reply(form):
    """날씨 에이전트와 취향기록 에이전트가 각각 답한다. 말한 에이전트 자신은 답하지 않는다."""
    def value(name):
        return form.get(name, [""])[0].strip()

    sender, store, current = value("sender"), value("store"), value("current")
    parts = []
    if sender != "날씨":
        parts.append(weather_reply(sender, store, value("food_type"), current, value("current_type")))
    if sender != "취향기록":
        parts.append(taste_reply(sender, store, value("kind"), current, value("current_kind"),
                                 value("hurry") == "1"))
    return "\n\n".join(parts)


def weather_reply(sender, store, food_type, current, current_type):
    """날씨를 새로 가져와서 답한다."""
    report, notice = fresh_report()
    if report is None:
        return "🌡️ " + notice
    if current:
        answer = weather.rebut(report, sender, store, food_type, current, current_type)
    else:
        answer = weather.reply(report, sender, store, food_type)
    points = weather.score(report, food_type)
    note = "" if points["confirmed"] else " (음식 종류 확인 안 됨)"
    return (f"🌡️ {answer['message']}\n{store} 날씨 점수: {points['score']}점{note}\n"
            f"날씨 확인 시각: {report['time']}")


def taste_reply(sender, store, kind, current, current_kind, hurry):
    """혼밥일기 기록으로 답한다."""
    profile, shop_kinds, notice = taste_data()
    if profile is None:
        return "📒 " + notice
    kind = kind_of(shop_kinds, store, kind)
    code = user_mbti()
    if current:
        answer = taste.rebut(profile, sender, store, kind, current,
                             kind_of(shop_kinds, current, current_kind), hurry, code)
    else:
        answer = taste.reply(profile, sender, store, kind, code)
    points = taste.score(profile, store, kind, code)
    return (f"📒 {answer['message']}\n{store}({kind}) 취향 점수: {points['score']:g}점\n"
            f"취향 요약표: {profile['만든날']} 기준 · 혼밥 MBTI {mbti_text(code)}")


class Handler(BaseHTTPRequestHandler):
    def show(self, result="", answer="", ranking="", values=None, taste_result="", coordinated=""):
        body = PAGE.format(result=result, answer=answer, ranking=ranking, taste_result=taste_result,
                           coordinated=coordinated, app_status=html.escape(app_status()),
                           kinds=kind_options(), rank_form=rank_form(values or {})).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # 화면만 보여준다 (날씨를 가져오지 않음)
        self.show()

    def app_sync(self, host, origin):
        """혼밥 앱이 보낸 내 혼밥일기와 가게 목록을 앱데이터.json에 저장한다.
        내 PC에서 연 앱(파일로 연 앱, localhost)만 받는다."""
        if host not in ALLOWED_HOSTS or not app_origin_ok(origin):
            self.send_error(403)
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > app_data.MAX_BYTES:
            self.send_error(413)
            return
        try:
            saved = app_data.save(json.loads(self.rfile.read(length).decode("utf-8")))
            status, body = 200, {"ok": True, "posts": len(saved["posts"])}
        except (ValueError, UnicodeDecodeError) as error:
            status, body = 400, {"ok": False, "error": str(error)}
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):  # 버튼을 누를 때마다 날씨를 새로 가져온다
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        if self.path == "/app-sync":
            self.app_sync(host, origin)
            return
        if host not in ALLOWED_HOSTS or (origin and origin != f"http://{host}"):
            self.send_error(403)
            return
        length = min(int(self.headers.get("Content-Length") or 0), 5000)
        form = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
        if self.path == "/reply":
            self.show(answer=f"<pre>{html.escape(run_reply(form))}</pre>")
        elif self.path == "/coordinate":
            self.show(coordinated=f"<pre>{html.escape(run_coordinator(form))}</pre>")
        elif self.path == "/taste":
            self.show(taste_result=f"<pre>{html.escape(run_taste())}</pre>")
        elif self.path == "/rank":
            self.show(ranking=f"<pre>{html.escape(run_rank(form))}</pre>", values=form)
        else:
            self.show(f"<pre>{html.escape(run_agent())}</pre>")


if __name__ == "__main__":
    print(f"http://localhost:{PORT} 에서 실행 중")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
