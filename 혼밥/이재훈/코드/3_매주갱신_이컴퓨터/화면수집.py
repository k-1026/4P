"""화면만 보기 수집(혼밥 수집·팀원 꾸러미와 같은 프로그램): 이 파일이 있는 폴더의 prompt_NNN.txt를 하나씩 Aside로 돌려 out_NNN.csv로 저장한다.

매주 갱신의 후기_다시보기.py가 작업 폴더에 복사해 돌린다. 끊기면 다시 돌리면 이어서 돈다(끝난 묶음은 건너뜀).
멈추려면 이 폴더에 멈춤.txt를 만든다. 로그에 캡차·내부 주소 호출이 보이면 바로 끄고 막힘.txt를 남기고 알림 창을 띄운다.
캡차는 사람이 직접 푼다. 이 프로그램은 풀거나 피해 가지 않는다.
"""
import csv
import glob
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
H = os.path.dirname(os.path.abspath(__file__))
API = re.compile(r"ncaptcha|allSearch|pcmap-api|\bfetch\(|XMLHttpRequest|panel3|mapsearch/map\.daum|\.request\.(get|post)\(|captcha-solver\\+SKILL"
                 r"|graphql|waitForResponse|page\.on\(|page\.route\(|__APOLLO|document\.cookie|\.cookies\(", re.I)
PAGE = re.compile(r"자동입력 방지|보안문자|비정상적인 접근|일시적으로 제한|이용이?\s*제한|접속이?\s*제한|로봇이\s*아닙니다|접속 확인이\s*필요"
                  r"|캡차[가를]?\s*(떴|뜬|나타|보[여이임])|recaptcha|hcaptcha|captcha[_/.]\w|/captcha|captcha['\":\s]+true"
                  r"|(?<!no\s)(?<!any\s)captcha\s+(detected|appeared|is shown|showed up)|unusual traffic", re.I)
NOTE = re.compile(r"^\s*(>\s*)?[-*]?\s*(Observation|Workflow)\b")   # Aside가 처음에 불러온 옛 기록 글
CAP = re.compile(r"captcha|캡차|로봇이|자동입력 방지|보안문자|접속 확인", re.I)
LIMIT = 1500   # 한 묶음 25분


def P(name):
    return os.path.join(H, name)


def find_aside():
    p = shutil.which("aside") or os.path.join(os.environ.get("LOCALAPPDATA", ""), "Aside", "CLI", "current", "aside.exe")
    return p if os.path.exists(p) else None


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
    """알림 창을 띄운다. 창을 닫지 않아도 이 프로그램은 기다리지 않는다."""
    if "멈춤 확인 못 함" in why:
        msg = ("수집을 멈췄지만 Aside 작업이 아직 돌고 있을 수 있습니다.\n\n"
               "Aside 앱에서 도는 작업을 직접 멈춰 주세요. 막힘.txt는 지우지 말고 알려 주세요.\n\n" + why[:150])
    elif CAP.search(why):
        msg = ("캡차(사람 확인)가 뜬 것 같습니다. 수집은 멈췄습니다.\n\n"
               "1) Aside 브라우저에서 캡차 화면을 찾아 직접 풀어 주세요.\n"
               "2) 다 풀었으면 이 폴더의 막힘.txt를 지우고 매주_갱신.bat을 다시 누르세요.\n\n"
               "'이용 제한' 화면이면 아무것도 누르지 말고 몇 시간 뒤에 다시 하세요.")
    else:
        msg = "수집이 멈췄습니다. 막힘.txt를 지우지 말고 이유를 확인하세요.\n\n" + why[:150]
    code = "import ctypes,sys; ctypes.windll.user32.MessageBoxW(0, sys.argv[1], '혼밥 수집 - 도움 요청', 0x41030)"
    try:
        subprocess.Popen([sys.executable, "-I", "-c", code, msg], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=0x00000008 | 0x00000200)
    except (OSError, ValueError):
        print(msg, flush=True)


def read(p):
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()


def ids_of(tag):
    return [r[0] for r in json.loads(read(P(f"prompt_{tag}.txt")).split("입력:\n", 1)[1])]


def got_ids(t):
    """마지막 답 표에서 수집ID 열에 적힌 값들. 앞쪽 생각 글·예시 표와 다른 칸에 나온 ID는 세지 않는다."""
    pos, last = 0, None
    for line in t.splitlines(True):
        if "수집ID" in line and "찾음" in line:
            last = (pos, line)
        pos += len(line)
    if not last:
        return None
    pos, line = last
    body = t[pos + len(line):].split("```")[0]
    n = len(next(csv.reader([line])))
    return {r[0].strip() for r in csv.reader(io.StringIO(body)) if len(r) == n}


def done(tag):
    """머리줄과 맡은 가게가 모두 있고 접속 확인으로 멈춘 것이 아니면 끝난 묶음."""
    out = P(f"out_{tag}.csv")
    if not os.path.exists(out):
        return False
    t = read(out)
    return "중단: 접속 확인" not in t and set(ids_of(tag)) <= (got_ids(t) or set())


def keep_old(p):
    """지우지 않고 이름만 바꿔 남긴다."""
    if os.path.exists(p):
        os.replace(p, p + time.strftime(".%m%d_%H%M%S.bak"))


def kill(p):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
    else:
        p.kill()
    p.wait()


def run(aside, tag):
    """한 묶음을 돌린다. 멈춘 이유를 돌려준다(정상이면 빈 문자열)."""
    out, err, text = P(f"out_{tag}.csv"), P(f"err_{tag}.txt"), read(P(f"prompt_{tag}.txt"))
    part = out + ".part"   # 끝까지 정상일 때만 out으로 이름을 바꾼다
    for x in (out, err, part):
        keep_old(x)
    ids = ids_of(tag)
    t0, why, block, pos, w = time.time(), "", False, 0, Watch()
    with open(part, "wb") as o, open(err, "wb") as e:
        p = subprocess.Popen([aside, "exec", "--effort", "medium", text], stdout=o, stderr=e, stdin=subprocess.DEVNULL)
        try:
            while True:
                over = p.poll() is not None   # 끝난 뒤에도 남은 로그를 한 번 더 본다
                with open(err, "rb") as f:
                    f.seek(pos)
                    data = f.read()
                cut = len(data) if over else data.rfind(b"\n") + 1
                pos += cut
                for line in data[:cut].decode("utf-8", "replace").splitlines():
                    h = w.hit(line)
                    if h:
                        why, block = f"감시 중단: {h} | {line.strip()[:160]}", True
                        break
                if not why and not over and os.path.exists(P("멈춤.txt")):
                    why = "멈춤.txt"
                if not why and not over and time.time() - t0 > LIMIT:
                    why = "감시 중단: 25분 넘음"
                if why or over:
                    break
                time.sleep(1)
        finally:
            if why or p.poll() != 0:   # 정상으로 끝난 것이 아니면 작업까지 멈췄는지 확인하고 명령 창을 끈다
                st = stop_session(aside, session_id(err))
                if p.poll() is None:
                    kill(p)
                why = (why or f"Aside가 오류로 끝남 (종료 값 {p.returncode})") + " | " + st
                block = block or "멈춤 확인 못 함" in st
    txt = read(part)
    got = got_ids(txt)
    n = len(set(ids) & (got or set()))
    if not why and "중단: 접속 확인" in txt:
        why, block = "Aside가 접속 확인을 보고 중단", True
    elif not why and got is None:
        why = "결과 없음"
    elif not why and n < len(ids):
        why = f"빠진 가게 {len(ids) - n}곳"
    if why:
        keep_old(part)
    else:
        os.replace(part, out)
    line = f"{tag} {why or '정상'} {n}/{len(ids)}곳 {(time.time() - t0) / 60:.1f}분 {time.strftime('%m-%d %H:%M:%S')}"
    print(line, flush=True)
    with open(P("진행.txt"), "a", encoding="utf-8") as f:
        f.write(line + "\n")
    if block:
        with open(P("막힘.txt"), "w", encoding="utf-8") as f:
            f.write(line + "\n")
        ask_help(why)
    return why


def main():
    if os.path.exists(P("막힘.txt")):
        print("막힘.txt가 있어 돌리지 않습니다.")
        return
    if os.path.exists(P("멈춤.txt")):
        print("멈춤.txt가 있어 돌리지 않습니다. 이어서 하려면 멈춤.txt를 지우세요.")
        return
    aside = find_aside()
    if not aside:
        print("aside 명령을 찾지 못했습니다. Aside 앱을 설치하고 로그인한 뒤 다시 실행하세요.")
        return
    for tag in sorted(os.path.basename(p)[4:-4] for p in glob.glob(P("err_*.txt"))):
        if not done(tag):   # 지난번에 창을 닫아 끝나지 않은 작업이 남았으면 먼저 멈춘다
            st = stop_session(aside, session_id(P(f"err_{tag}.txt")))
            print(tag, st, flush=True)
            if "멈춤 확인 못 함" in st:
                with open(P("막힘.txt"), "w", encoding="utf-8") as f:
                    f.write(st + "\n")
                keep_old(P(f"err_{tag}.txt"))   # 사람이 확인하고 막힘.txt를 지우면 다음에는 이 묶음부터 다시 한다
                ask_help(st)
                return
    tags = sorted(os.path.basename(p)[7:-4] for p in glob.glob(P("prompt_*.txt")))
    left = [t for t in tags if not done(t)]
    print(f"묶음 {len(tags)}개 중 {len(left)}개 남음 (한 묶음 5곳, 약 3~6분)", flush=True)
    for t in left:
        if run(aside, t):
            print("여기서 멈춤.", flush=True)
            return
    print("모두 끝", flush=True)


if __name__ == "__main__":
    main()
