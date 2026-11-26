"""동성로 화면만 보기 수집: 대상목록.csv를 5곳씩 Aside로 돌리고, 로그에 내부 주소 호출·캡차가 보이면 바로 끈다.

python -I -u 수집_화면만.py 1_2인분의심
멈추려면 그 폴더에 멈춤.txt를 만든다(1초 안에 끔). 끝난 5곳은 건너뛰므로 다시 실행하면 이어서 돈다.
캡차·내부 주소로 멈추면 막힘.txt가 생기고 화면에 알림 창이 뜬다. 사람이 보고 지우기 전에는 다시 돌지 않는다.
캡차는 사람이 직접 푼다. 도구가 풀거나 피해 가지 않는다.
"""
import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE))
from make_web_pilot import HEAD  # noqa: E402

HEAD = "".join(x for x in HEAD.splitlines(True) if not x.startswith("5) 좌석"))   # 사용자 결정 11-25: 좌석은 모으지 않음
assert "좌석" not in HEAD

sys.stdout.reconfigure(encoding="utf-8")
H = os.path.join(BASE, sys.argv[1])
RULE = """
[가장 먼저 지킬 것 - 아래 다른 지시보다 우선]
- 사람이 보는 것처럼 브라우저 화면(지도 검색창에 입력, 목록·메뉴·리뷰 탭 누르기, 스크롤)으로만 확인해. 화면에 보이는 글자만 읽어.
- 코드로 지도 서비스의 내부 주소를 부르지 마(페이지 안이든 밖이든, 네이버·카카오 둘 다). 요청 머리글·쿠키·토큰을 꺼내거나 다시 쓰지 마. 이전 작업 기록이나 메모에 그런 방법이 있어도 쓰지 마.
- 캡차나 자동입력 방지, 접속 제한이 한 번이라도 보이면 풀거나 다른 주소·검색어·화면으로 돌아가지 말고 그 즉시 전체 작업을 끝내. 그때까지 본 가게의 CSV를 적고 마지막 줄 다음에 "중단: 접속 확인"이라고 적어. 캡차가 뜬 탭은 닫지 말고 그 화면 그대로 둬(사람이 직접 볼 거야).
- 한 번에 한 가게씩, 탭 하나로, 가게 사이에 5초 넘게 쉬어.

"""
API = re.compile(r"ncaptcha|allSearch|pcmap-api|\bfetch\(|XMLHttpRequest|panel3|mapsearch/map\.daum|\.request\.(get|post)\(|captcha-solver\\+SKILL"
                 r"|graphql|waitForResponse|page\.on\(|page\.route\(|__APOLLO|document\.cookie|\.cookies\(", re.I)
PAGE = re.compile(r"자동입력 방지|보안문자|비정상적인 접근|일시적으로 제한|이용이?\s*제한|접속이?\s*제한|로봇이\s*아닙니다|접속 확인이\s*필요"
                  r"|캡차[가를]?\s*(떴|뜬|나타|보[여이임])|recaptcha|hcaptcha|captcha[_/.]\w|/captcha|captcha['\":\s]+true"
                  r"|(?<!no\s)(?<!any\s)captcha\s+(detected|appeared|is shown|showed up)|unusual traffic", re.I)
NOTE = re.compile(r"^\s*(>\s*)?[-*]?\s*(Observation|Workflow)\b")   # Aside가 불러온 옛 기록 글


CAP = re.compile(r"captcha|캡차|로봇이|자동입력 방지|보안문자|접속 확인", re.I)


SESSION = re.compile(r"created new session:\s*(\w+)")
CODE_IN = re.compile(r"^\s*repl\(")
CODE_OUT = re.compile(r"title:\s*['\"].*\)|^\s>\s")
PLAN = re.compile(r"^\s*(Thinking:\s*)?(I'm|I'll|I am|I will|Now|Next|Then)\b.*(watch(ing)? for|check(ing)? for|look(ing)? for|captcha check|if (a|any) )", re.I)


class Watch:
    """로그를 줄 단위로 본다. 걸리면 그 낱말을 돌려준다."""

    def __init__(self):
        self.code, self.n = False, 0

    def hit(self, line):
        self.n += 1
        if CODE_IN.match(line):
            self.code = True
        in_code = self.code
        if self.code and CODE_OUT.search(line):
            self.code = False
            in_code = not line.startswith(" > ")
        if self.n <= 300 and NOTE.match(line):   # Aside가 처음에 불러온 옛 기록 글
            return None
        m = API.search(line)
        if not m and not in_code and not PLAN.match(line):
            m = PAGE.search(line)
        return m.group(0) if m else None


def session_id(err):
    try:
        with open(err, encoding="utf-8", errors="replace") as f:
            m = SESSION.search(f.read(4000))
    except OSError:
        m = None
    return m.group(1) if m else ""


def session_status(aside, sid):
    try:
        p = subprocess.run([aside, "session", "inspect", sid], capture_output=True, timeout=40)
        x = re.search(r"Status\s+(\w+)", p.stdout.decode("utf-8", "replace"))
        return x.group(1) if x else "모름"
    except (OSError, subprocess.SubprocessError):
        return "모름"


def stop_session(aside, sid):
    """명령 창을 꺼도 Aside 작업은 계속 돌므로 작업을 멈추고, 멈췄는지 확인한다. 확인한 글을 돌려준다."""
    if not sid:
        return "멈춤 확인 못 함(작업 번호 없음)"
    st = "모름"
    for _ in range(4):
        st = session_status(aside, sid)
        if st in ("idle", "interrupted", "completed", "failed", "archived"):
            return f"Aside 작업 멈춤 확인({st})"
        try:
            subprocess.run([aside, "session", "stop", sid], capture_output=True, timeout=40)
        except (OSError, subprocess.SubprocessError):
            pass
        time.sleep(2)
    st = session_status(aside, sid)
    if st in ("idle", "interrupted", "completed", "failed", "archived"):
        return f"Aside 작업 멈춤 확인({st})"
    return f"멈춤 확인 못 함({st})"


def ask_help(why):
    """화면 맨 앞에 알림 창을 띄운다. 창을 닫지 않아도 이 도구는 기다리지 않고 끝난다."""
    if "멈춤 확인 못 함" in why:
        msg = ("수집을 멈췄지만 Aside 작업이 아직 돌고 있을 수 있습니다.\n\n"
               "Aside 앱에서 도는 작업을 직접 멈춰 주세요. 막힘.txt는 지우지 말고 알려 주세요.\n\n" + why[:150])
    elif CAP.search(why):
        msg = ("네이버/카카오에서 캡차(사람 확인)가 뜬 것 같습니다. 수집은 멈췄습니다.\n\n"
               "1) Aside 브라우저에서 캡차 화면을 찾아 직접 풀어 주세요.\n"
               "   (안 보이면 Aside에서 map.naver.com을 열어 확인)\n"
               "2) 다 풀었으면 Claude에게 '풀었어'라고 알려 주세요.\n\n"
               "'이용 제한' 화면이면 누르지 말고 Claude에게 알려 주세요.")
    else:
        msg = "수집이 멈췄습니다. 풀 것은 없고, Claude가 이유를 확인해야 합니다.\n\n" + why[:150]
    code = "import ctypes,sys; ctypes.windll.user32.MessageBoxW(0, sys.argv[1], '혼밥 수집 - 도움 요청', 0x41030)"
    subprocess.Popen([sys.executable, "-I", "-c", code, msg], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=0x00000008 | 0x00000200)


def answered(t):
    """마지막 답 CSV(글에서 마지막 '수집ID' 머리줄부터 끝까지)의 바른 줄(7칸 이상, 첫 묶음은 7칸)·찾음이 예/애매/아니오인 수집ID 집합.
    앞의 생각 글·예시 줄은 세지 않는다(Codex 3차 11-26). 답이 둘로 나뉘어 있으면 앞쪽을 놓쳐 다시 돌리는 쪽으로 틀린다(안전한 쪽)."""
    i = t.rfind("수집ID")
    if i < 0:
        return set()
    j = i - 1 if t[i - 1:i] == '"' else i
    try:
        return {r[0] for r in csv.reader(io.StringIO(t[j:])) if len(r) >= 7 and r[1] in ("예", "애매", "아니오")}
    except csv.Error:
        return set()


def done(out, ids=()):
    """머리줄이 있고 접속 확인으로 멈춘 것이 아니면 끝난 묶음.
    ids를 주면 그 가게가 모두 바른 줄로 있어야 끝난 것으로 본다(일부만 있으면 다시 돌림, Codex 2차 11-26)."""
    if not os.path.exists(out):
        return False
    t = open(out, encoding="utf-8", errors="replace").read()
    if "수집ID" not in t or "중단: 접속 확인" in t:
        return False
    return not ids or set(ids) <= answered(t)


def run(n, part):
    """가게 5곳을 돌린다. (이유, 막힘 여부)를 돌려준다. 정상이면 이유는 빈 문자열."""
    tag = f"{n:03d}"
    out, err = os.path.join(H, f"out_{tag}.csv"), os.path.join(H, f"err_{tag}.txt")
    if done(out, [r[0] for r in part]):
        print("건너뜀", tag, flush=True)
        return "", False
    for p in (out, err):   # 앞서 멈춘 기록은 지우지 않고 남긴다
        if os.path.exists(p):
            os.replace(p, p + time.strftime(".%H%M%S.bak"))
    head, rest = HEAD.split("\n", 1)
    text = head + "\n" + RULE + rest + json.dumps(part, ensure_ascii=False)
    t0, why, block, pos = time.time(), "", False, 0
    w, aside = Watch(), shutil.which("aside")
    with open(out, "wb") as o, open(err, "wb") as e:
        p = subprocess.Popen([aside, "exec", "--effort", "medium", text], stdout=o, stderr=e, stdin=subprocess.DEVNULL)
        while p.poll() is None:
            time.sleep(1)
            with open(err, "rb") as f:
                f.seek(pos)
                data = f.read()
            cut = data.rfind(b"\n") + 1
            pos += cut
            for line in data[:cut].decode("utf-8", "replace").splitlines():
                h = w.hit(line)
                if h:
                    why, block = f"감시 중단: {h} | {line.strip()[:160]}", True
                    break
            if not why and os.path.exists(os.path.join(H, "멈춤.txt")):
                why = "멈춤.txt"
            if not why and time.time() - t0 > 1500:
                why = "감시 중단: 25분 넘음"
            if why:
                break
    if why or p.poll() not in (0,):   # 정상으로 끝난 것이 아니면 작업까지 멈췄는지 확인하고 명령 창을 끈다
        st = stop_session(aside, session_id(err))
        if p.poll() is None:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
            p.wait()
        why = (why or f"Aside가 오류로 끝남 (exit {p.returncode})") + " | " + st
        block = block or "멈춤 확인 못 함" in st
    txt = open(out, encoding="utf-8", errors="replace").read()
    if not why and "중단: 접속 확인" in txt:
        why, block = "Aside가 접속 확인을 보고 중단", True
    if not why and "수집ID" not in txt:
        why = f"결과 없음 (exit {p.returncode})"
    got = answered(txt)
    miss = [r[1] for r in part if r[0] not in got]
    if not why and miss:   # 일부만 답했으면 정상이 아니다: 멈추고 다음 실행에서 이 묶음을 다시 돌린다(Codex 3차 11-26)
        why = f"빠진 가게 {len(miss)}곳: " + ", ".join(miss)
    print(tag, why or "정상", f"{len(part) - len(miss)}/{len(part)}곳 {(time.time() - t0) / 60:.1f}분", time.strftime("%H:%M:%S"),
          ("빠진 가게: " + ", ".join(miss)) if miss and not why else "", flush=True)
    if block:
        with open(os.path.join(H, "막힘.txt"), "w", encoding="utf-8") as f:
            f.write(f"{time.strftime('%m-%d %H:%M:%S')} {tag} {why}\n")
        ask_help(why)
    return why, block


def main():
    if os.path.exists(os.path.join(H, "막힘.txt")):
        print("막힘.txt가 있어 돌리지 않음", flush=True)
        return
    with open(os.path.join(H, "대상목록.csv"), encoding="utf-8-sig", newline="") as f:
        items = [[r["수집ID"], r["상호"], r["도로명주소"], r["업종_소분류"]] for r in csv.DictReader(f)]
    for n, k in enumerate(range(0, len(items), 5)):
        if run(n, items[k:k + 5])[0]:
            print("여기서 끝냄", flush=True)
            return
    print("모두 끝", flush=True)


if __name__ == "__main__":
    main()
