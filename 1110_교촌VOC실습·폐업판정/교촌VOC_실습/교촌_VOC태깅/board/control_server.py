#!/usr/bin/env python3
"""VOC 태깅 관제 서버 (표준 라이브러리만 사용).

실행:  python board/control_server.py        → http://127.0.0.1:8765
옵션:  --port 9000

하는 일
- 화면 제공: board/monitor.html
- 상태 조회 (GET /api/status)
    · 묶음별 진행률: archive/batchN 원문 수 대비 ax/demo/parts/part_N.csv 행 수
    · 자동 검사 점수: CLAUDE.md 기준(범위·근거·형식)을 그대로 계산
    · 채점관 점수: ax/demo/grades/grade_N.md 에서 범위·근거·형식 숫자를 읽어 옴
    · 검토 건수 · 태그 분포 · 문제 행 목록
    · 훅 로그(ax/demo/logs/events.jsonl): 이벤트 수, 최근 이벤트, 에이전트 활동
    · 사용자 대조 진행 · 승인 기록
- 관제 액션 (POST)
    · /api/sample   {target}                  대조용 샘플 10건 뽑기 (태그별 고르게)
    · /api/verify   {target, voc_id, verdict} 샘플 1건에 동의/비동의 기록
    · /api/approve  {target, approver}        사용자 승인 기록 (통과 조건을 모두 채워야 함)
    · /api/revoke   {target}                  승인 취소
    · /api/run      {batches:[1,2], mode}     에이전트 실행. 묶음마다 따로·동시에 돈다
                                              (mode: auto=남은 단계만 / all=태깅→채점 / tag / grade)
    · /api/stop     {batches:[2]}             중지 (batches 를 비우면 전체). 프로세스 트리 종료 · 대기 작업 취소

원칙
- 원문 · part · grade 파일은 읽기만 합니다. 쓰는 곳은 board/state/ 뿐입니다.
- 승인은 사람이 화면에서 버튼을 눌러야만 기록됩니다. 서버가 스스로 승인하지 않습니다.
- 127.0.0.1 에만 열립니다.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import random
import re
import sys
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# ── 경로 ──────────────────────────────────────────────────────────
BOARD_DIR = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("AX_PROJECT_ROOT") or BOARD_DIR.parent)
ROOT_SOURCE = "AX_PROJECT_ROOT" if os.environ.get("AX_PROJECT_ROOT") else "board 상위 폴더"
ARCHIVE = ROOT / "archive"
PARTS = ROOT / "ax" / "demo" / "parts"
GRADES = ROOT / "ax" / "demo" / "grades"
EVENTS = ROOT / "ax" / "demo" / "logs" / "events.jsonl"
TAGGED_ALL = BOARD_DIR / "voc_tagged.csv"
STATE = BOARD_DIR / "state"
HTML = BOARD_DIR / "monitor.html"

# ── 기준 (CLAUDE.md · painpoint_def.md) ───────────────────────────
ALLOWED = ["P1", "P2", "P3", "H1", "H2", "해당없음", "검토"]
HEADER = ["voc_id", "tag", "evidence", "note"]
PASS_SCORE = 80
REVIEW_MAX_RATIO = 0.05
EVIDENCE_MAX = 15
SAMPLE_SIZE = 10
AGREE_MIN = 9


# ── 공통 유틸 ─────────────────────────────────────────────────────
def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8-sig", errors="replace")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def load_json(p: Path, default):
    try:
        return json.loads(read_text(p))
    except Exception:
        return default


def save_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


# ── 원문 ──────────────────────────────────────────────────────────
_orig_cache: dict = {"mtime": None, "data": {}}


def originals() -> dict:
    """voc_id → {batch, body, source, date, file}"""
    files = sorted(ARCHIVE.glob("batch*/r_*.md"))
    mtime = max((f.stat().st_mtime for f in files), default=0), len(files)
    if _orig_cache["mtime"] == mtime:
        return _orig_cache["data"]
    data = {}
    for f in files:
        text = read_text(f)
        meta, body = {}, text
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
        if m:
            for line in m.group(1).splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            body = m.group(2)
        vid = meta.get("voc_id") or f.stem
        data[vid] = {
            "batch": f.parent.name,
            "body": body.strip(),
            "source": meta.get("source", ""),
            "date": meta.get("date", ""),
            "file": f.relative_to(ROOT).as_posix(),
        }
    _orig_cache.update(mtime=mtime, data=data)
    return data


def batches() -> dict:
    out = {}
    for d in sorted(ARCHIVE.glob("batch*")):
        if d.is_dir():
            out[d.name] = sorted(f.stem for f in d.glob("r_*.md"))
    return out


# ── 분류 결과 파일 ────────────────────────────────────────────────
def targets() -> list[dict]:
    """채점 대상 목록: part_N.csv, 그 밖의 parts/*.csv, board/voc_tagged.csv(통합본)"""
    out = []
    for p in sorted(PARTS.glob("*.csv")):
        m = re.fullmatch(r"part_(\d+)", p.stem)
        out.append({
            "id": p.stem,
            "path": p,
            "label": f"part_{m.group(1)} (batch{m.group(1)})" if m else f"{p.stem} (연습 파일)",
            "batch": f"batch{m.group(1)}" if m else None,
            "kind": "part" if m else "extra",
        })
    if TAGGED_ALL.exists():
        out.append({"id": "voc_tagged", "path": TAGGED_ALL, "label": "voc_tagged (통합본 300건)",
                    "batch": "ALL", "kind": "merged"})
    return out


def find_target(tid: str) -> dict | None:
    return next((t for t in targets() if t["id"] == tid), None)


def read_rows(path: Path) -> tuple[list[str], list[dict]]:
    text = read_text(path)
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return [], []
    header = [h.strip() for h in rows[0]]
    recs = []
    for i, r in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        rec = {header[j]: (r[j] if j < len(r) else "") for j in range(len(header))}
        # 통합본은 evidence 대신 quote 열을 쓴다
        if "evidence" not in rec and "quote" in rec:
            rec["evidence"] = rec["quote"]
        rec["_line"] = i
        recs.append(rec)
    return header, recs


def expected_ids(t: dict, recs: list[dict]) -> list[str]:
    b = batches()
    if t["batch"] == "ALL":
        return sorted(v for ids in b.values() for v in ids)
    if t["batch"] in b:
        return b[t["batch"]]
    # 연습 파일: 행이 속한 묶음 전체를 기준으로 삼는다
    orig = originals()
    touched = {orig[r["voc_id"]]["batch"] for r in recs if r.get("voc_id") in orig}
    return sorted(v for name in touched for v in b.get(name, []))


# ── 자동 검사 (CLAUDE.md 기준과 같은 계산) ────────────────────────
def check(t: dict) -> dict:
    header, recs = read_rows(t["path"])
    orig = originals()
    expected = expected_ids(t, recs)
    exp_set = set(expected)
    issues = []

    ids = [r.get("voc_id", "").strip() for r in recs]
    cnt = Counter(ids)
    dups = sorted(v for v, c in cnt.items() if v and c > 1)
    valid = {v for v in ids if v in exp_set}
    missing = sorted(exp_set - valid)
    unknown = sorted({v for v in ids if v and v not in exp_set})
    for v in dups:
        issues.append({"voc_id": v, "type": "범위", "reason": f"중복 {cnt[v]}회"})
    for v in unknown:
        issues.append({"voc_id": v, "type": "범위", "reason": "원문 묶음에 없는 voc_id"})
    scope = (len(valid) / len(expected) * 100 if expected else 0) - 5 * sum(cnt[v] - 1 for v in dups)
    scope = max(0.0, round(scope, 1))

    # 근거: evidence 가 있고, 15자 이내이고, 원문에 그대로 있음
    ev_ok = 0
    for r in recs:
        v, ev = r.get("voc_id", "").strip(), (r.get("evidence") or "").strip()
        why = None
        if not ev:
            why = "인용 없음"
        elif len(ev) > EVIDENCE_MAX:
            why = f"인용 {len(ev)}자 (15자 초과)"
        elif v not in orig:
            why = "원문 없음"
        elif norm(ev) not in norm(orig[v]["body"]):
            why = "원문과 글자가 다름"
        if why:
            issues.append({"voc_id": v, "type": "근거", "reason": why, "evidence": ev})
        else:
            ev_ok += 1
    evidence = round(ev_ok / len(recs) * 100, 1) if recs else 0.0

    # 형식: 헤더 · 허용 태그 · note 규칙 · 검토 비율 (각 25점)
    tags = [(r.get("tag") or "").strip() for r in recs]
    n = len(recs) or 1
    header_ok = header == HEADER
    tag_ok = sum(1 for x in tags if x in ALLOWED)
    note_ok = 0
    for r, tag in zip(recs, tags):
        note = (r.get("note") or "").strip()
        good = bool(note) if tag == "검토" else not note
        if good:
            note_ok += 1
        else:
            issues.append({"voc_id": r.get("voc_id", ""), "type": "형식",
                           "reason": "검토인데 이유(note) 없음" if tag == "검토" else "검토가 아닌데 note 있음"})
    for r, tag in zip(recs, tags):
        if tag not in ALLOWED:
            issues.append({"voc_id": r.get("voc_id", ""), "type": "형식", "reason": f"허용되지 않은 태그 '{tag}'"})
    review_n = tags.count("검토")
    review_ratio = review_n / n if recs else 0
    review_ok = review_ratio <= REVIEW_MAX_RATIO
    fmt_parts = {
        "header": 25 if header_ok else 0,
        "tags": round(tag_ok / n * 25, 1),
        "note": round(note_ok / n * 25, 1),
        "review": 25 if review_ok else 0,
    }
    fmt = round(sum(fmt_parts.values()), 1)
    if not header_ok:
        issues.insert(0, {"voc_id": "-", "type": "형식", "reason": f"헤더가 {','.join(header)} (기준: {','.join(HEADER)})"})

    review_rows = [{"voc_id": r.get("voc_id", ""), "evidence": r.get("evidence", ""), "note": r.get("note", "")}
                   for r, tag in zip(recs, tags) if tag == "검토"]
    return {
        "rows": len(recs),
        "expected": len(expected),
        "progress": round(len(valid) / len(expected) * 100, 1) if expected else 0,
        "scores": {"범위": scope, "근거": evidence, "형식": fmt},
        "format_parts": fmt_parts,
        "header": header,
        "missing": len(missing),
        "missing_sample": missing[:15],
        "duplicates": dups,
        "tag_counts": {k: tags.count(k) for k in ALLOWED},
        "other_tags": len(tags) - tag_ok,
        "review": {"count": review_n, "ratio": round(review_ratio * 100, 1), "ok": review_ok,
                   "missing_note": sum(1 for x in review_rows if not x["note"].strip()), "rows": review_rows},
        "issues": issues[:200],
        "issue_count": len(issues),
        "mtime": int(t["path"].stat().st_mtime),
    }


# ── 채점관(review-grader) 점수표 읽기 ─────────────────────────────
def grader_scores(t: dict) -> dict | None:
    m = re.fullmatch(r"part_(\d+)", t["id"])
    if not m:
        return None
    p = GRADES / f"grade_{m.group(1)}.md"
    if not p.exists():
        return {"file": p.relative_to(ROOT).as_posix(), "exists": False}
    text = read_text(p)
    scores = {}
    for k in ("범위", "근거", "형식"):
        mm = re.search(k + r"[^\d\n]{0,40}?(\d{1,3}(?:\.\d+)?)", text)
        scores[k] = float(mm.group(1)) if mm else None
    rv = re.search(r"검토[^\d\n]{0,20}?(\d+)\s*건", text)
    return {"file": p.relative_to(ROOT).as_posix(), "exists": True, "scores": scores,
            "review_count": int(rv.group(1)) if rv else None, "mtime": int(p.stat().st_mtime)}


# ── 훅 로그 ───────────────────────────────────────────────────────
def events_summary(limit: int = 60) -> dict:
    if not EVENTS.exists():
        return {"exists": False}
    lines = read_text(EVENTS).splitlines()
    recs = []
    for ln in lines:
        try:
            recs.append(json.loads(ln))
        except Exception:
            pass
    by_event = Counter(r.get("event", "") for r in recs)
    tools = Counter(r.get("tool_name") for r in recs if r.get("event") == "PreToolUse" and r.get("tool_name"))

    # 에이전트 활동: agent_id 단위로 묶어 순서대로 쌓는다
    agents: dict = {}
    for r in recs:
        aid = r.get("agent_id")
        if not aid:
            continue
        a = agents.setdefault(aid, {"agent_id": aid, "agent_type": r.get("agent_type", ""), "first": r["ts"],
                                    "last": r["ts"], "tools": 0, "status": "실행 중", "writes": [],
                                    "batches": Counter(), "steps": [], "reads": 0, "write_count": 0})
        a["last"] = r["ts"]
        ti = r.get("tool_input") if isinstance(r.get("tool_input"), dict) else {}
        target = ti.get("file_path") or ti.get("pattern") or ti.get("path") or ""
        for m in re.finditer(r"batch(\d+)|part_(\d+)|grade_(\d+)", str(target)):
            a["batches"][next(g for g in m.groups() if g)] += 1
        if r.get("event") == "PreToolUse":
            a["tools"] += 1
            tool = r.get("tool_name", "")
            if tool == "Read":
                a["reads"] += 1
            if tool in ("Write", "Edit"):
                a["write_count"] += 1
                a["writes"].append(Path(target).name)
            a["steps"].append({"ts": r["ts"], "tool": tool, "target": Path(str(target)).name if target else ""})
        if r.get("event") == "SubagentStop":
            a["status"] = "완료"
            a["steps"].append({"ts": r["ts"], "tool": "종료", "target": "SubagentStop"})
    now = time.time()
    for a in agents.values():
        if a["status"] == "실행 중" and now - a["last"] > 600:
            a["status"] = "응답 없음(10분+)"
        a["writes"] = sorted(set(a["writes"]))[-5:]
        a["batch"] = a["batches"].most_common(1)[0][0] if a["batches"] else None
        del a["batches"]
        a["steps"] = a["steps"][-14:]
    agent_list = sorted(agents.values(), key=lambda a: a["last"], reverse=True)[:12]

    recent = []
    for r in recs[-limit:][::-1]:
        ti = r.get("tool_input") or {}
        detail = ""
        if isinstance(ti, dict):
            detail = ti.get("file_path") or ti.get("description") or ti.get("command") or ti.get("pattern") or ""
        if r.get("event") == "UserPromptSubmit":
            detail = r.get("prompt", "")
        recent.append({
            "ts": r.get("ts"), "event": r.get("event"), "tool": r.get("tool_name") or "",
            "agent": r.get("agent_type") or "", "detail": norm(str(detail))[:140],
            "root_source": r.get("root_source", ""),
        })
    sessions = Counter(r.get("session_id") for r in recs)
    root_src = Counter(r.get("root_source", "(기록 없음)") for r in recs)
    return {
        "exists": True,
        "total": len(recs),
        "by_event": dict(by_event),
        "tools": dict(tools.most_common(8)),
        "agents": agent_list,
        "recent": recent,
        "sessions": len(sessions),
        "root_source": dict(root_src),
        "last_ts": recs[-1].get("ts") if recs else None,
    }


# ── 사용자 대조 · 승인 상태 ───────────────────────────────────────
def verify_path(tid: str) -> Path:
    return STATE / f"verify_{tid}.json"


def approvals() -> dict:
    return load_json(STATE / "approvals.json", {})


def verify_state(tid: str) -> dict | None:
    v = load_json(verify_path(tid), None)
    if not v:
        return None
    verdicts = [i.get("verdict") for i in v["items"]]
    v["agree"] = verdicts.count("agree")
    v["disagree"] = verdicts.count("disagree")
    v["pending"] = verdicts.count(None)
    return v


def gate(chk: dict, ver: dict | None, grader: dict | None) -> dict:
    """최종 통과 조건 판단 (CLAUDE.md '최종 통과 조건')"""
    s = chk["scores"]
    use = s
    src = "자동 검사"
    if grader and grader.get("exists") and all(v is not None for v in grader["scores"].values()):
        use, src = grader["scores"], "채점관"
    score_ok = all(v >= PASS_SCORE for v in use.values())
    review_ok = chk["review"]["ok"] and chk["review"]["missing_note"] == 0
    verify_ok = bool(ver) and ver["pending"] == 0 and ver["agree"] >= AGREE_MIN
    return {
        "score_source": src,
        "score_ok": score_ok,
        "review_ok": review_ok,
        "verify_ok": verify_ok,
        "ready": score_ok and review_ok and verify_ok,
    }


def status() -> dict:
    out_targets = []
    appr = approvals()
    for t in targets():
        chk = check(t)
        gr = grader_scores(t)
        ver = verify_state(t["id"])
        out_targets.append({
            "id": t["id"], "label": t["label"], "kind": t["kind"], "batch": t["batch"],
            "file": t["path"].relative_to(ROOT).as_posix(),
            "check": chk, "grader": gr, "verify": ver,
            "gate": gate(chk, ver, gr), "approval": appr.get(t["id"]),
        })
    ev = events_summary()
    # '중지'로 끊긴 서브에이전트는 SubagentStop 이 남지 않으므로, 중지 기록으로 상태를 바로잡는다
    stopped = [j for j in RUNNER.history if j.get("status") == "중지됨"]
    for a in ev.get("agents", []):
        if a["status"] != "완료" and any(j["batch"] == a["batch"] and j.get("started", 0) - 5 <= a["first"]
                                         and a["last"] <= j.get("ended", 0) + 5 for j in stopped):
            a["status"] = "중지됨"
    b = batches()
    batch_rows = []
    for name, ids in b.items():
        n = name.replace("batch", "")
        part = next((x for x in out_targets if x["id"] == f"part_{n}"), None)
        # 이 묶음에서 지금 일하는 서브에이전트의 마지막 동작
        live = next((a for a in ev.get("agents", []) if a["batch"] == n and a["status"] == "실행 중"), None)
        now_step = None
        if live and live["steps"]:
            s_ = live["steps"][-1]
            now_step = {"agent": live["agent_type"], "tool": s_["tool"], "target": s_["target"], "ts": s_["ts"]}
        gr = part["grader"] if part else None
        scores = gr["scores"] if gr and gr.get("exists") else (part["check"]["scores"] if part else None)
        chunks = chunk_progress(n, ids, live)
        batch_rows.append({"batch": name, "n": n, "originals": len(ids), "part": f"part_{n}.csv",
                           "rows": part["check"]["rows"] if part else 0,
                           "progress": part["check"]["progress"] if part else 0,
                           "graded": bool(gr and gr.get("exists")),
                           "scores": scores,
                           "score_source": "채점관" if gr and gr.get("exists") else ("자동 검사" if part else None),
                           "review": part["check"]["review"]["count"] if part else None,
                           "review_ratio": part["check"]["review"]["ratio"] if part else None,
                           "now_step": now_step,
                           "chunks": chunks,
                           "pipeline": pipeline(n, len(ids), part, ev.get("agents", []))})
    return {
        "now": int(time.time()),
        "root": str(ROOT), "root_source": ROOT_SOURCE,
        "criteria": {"pass": PASS_SCORE, "review_max": REVIEW_MAX_RATIO * 100, "sample": SAMPLE_SIZE,
                     "agree_min": AGREE_MIN, "allowed": ALLOWED},
        "stages": STAGES,
        "runner": RUNNER.snapshot(),
        "batches": batch_rows,
        "targets": out_targets,
        "events": ev,
    }


# ── 10건 단위 진행 (막대그래프용) ─────────────────────────────────
CHUNK = 10


def chunk_progress(n: str, ids: list[str], live: dict | None) -> list[dict]:
    """원문 순서대로 10건씩 나눠, 묶음마다 저장된 행 수 · 태그 수 · 지금 읽는 중인지를 돌려준다."""
    part = PARTS / f"part_{n}.csv"
    saved = {}
    if part.exists():
        for r in read_rows(part)[1]:
            saved[(r.get("voc_id") or "").strip()] = (r.get("tag") or "").strip()
    # 태깅 에이전트가 마지막으로 읽은 원문 → 지금 작업 중인 10건 묶음
    reading_idx = None
    if live and live.get("agent_type") == "review-tagger":
        pos = {v: i for i, v in enumerate(ids)}
        for s_ in reversed(live.get("steps", [])):
            vid = Path(s_.get("target") or "").stem
            if s_.get("tool") == "Read" and vid in pos:
                reading_idx = pos[vid]
                break
    out = []
    for c in range(0, len(ids), CHUNK):
        group = ids[c:c + CHUNK]
        tags = Counter(saved[v] for v in group if v in saved)
        k = c // CHUNK
        reading = 0
        if reading_idx is not None and reading_idx // CHUNK == k and sum(tags.values()) < len(group):
            reading = reading_idx % CHUNK + 1
        out.append({"no": k + 1, "range": f"{group[0]}~{group[-1]}", "size": len(group),
                    "saved": sum(tags.values()), "reading": reading, "tags": dict(tags)})
    return out


# ── 6단계 파이프라인 ──────────────────────────────────────────────
# 서브에이전트가 실제로 일하는 순서 그대로: 원문 → 태깅 → 채점 → 판정 → 대조 → 승인
STAGES = [
    {"key": "source", "name": "원문 준비", "who": "archive/batchN"},
    {"key": "tag", "name": "태깅", "who": "review-tagger"},
    {"key": "grade", "name": "채점", "who": "review-grader"},
    {"key": "judge", "name": "점수 판정", "who": "관제 서버"},
    {"key": "verify", "name": "사용자 대조", "who": "사용자"},
    {"key": "approve", "name": "최종 승인", "who": "사용자"},
]


def pipeline(n: str, originals_n: int, part: dict | None, agents: list) -> dict:
    """단계마다 state = done | active | wait | fail 와 한 줄 설명. current = 지금 머문 단계 번호(0부터)."""
    def running(kind):
        return next((a for a in agents if a["agent_type"] == kind and a["status"] == "실행 중" and a["batch"] == n), None)

    tagger, grader = running("review-tagger"), running("review-grader")
    # '실행' 버튼으로 띄운 작업은 서브에이전트가 뜨기 전부터 진행 중으로 본다
    job_kind = RUNNER.running_kind(n)
    if job_kind == "tag" and not tagger:
        tagger = {"tools": 0}
    if job_kind == "grade" and not grader:
        grader = {"tools": 0}
    rows = part["check"]["rows"] if part else 0
    st = []
    st.append(("done", f"원문 {originals_n}건") if originals_n else ("wait", "원문 없음"))

    # 태깅: 10건 단위 저장 → 몇 번째 묶음까지 저장됐는지
    chunks = f"{rows // 10}/{originals_n // 10 or 10} 저장"
    if tagger:
        st.append(("active", f"실행 중 · {chunks} · 도구 {tagger['tools']}회"))
    elif part and rows >= originals_n:
        st.append(("done", f"{rows}행 · {chunks}"))
    elif rows:
        st.append(("fail", f"중단 · {rows}행만 저장"))
    else:
        st.append(("wait", "part 파일 없음"))

    gr = part["grader"] if part else None
    if grader:
        st.append(("active", f"실행 중 · 도구 {grader['tools']}회"))
    elif gr and gr.get("exists"):
        st.append(("done", Path(gr["file"]).name))
    else:
        st.append(("wait", "grade 파일 없음"))

    if gr and gr.get("exists"):
        g = part["gate"]
        sc = gr["scores"]
        txt = " · ".join(f"{k} {v:g}" if v is not None else f"{k} ?" for k, v in sc.items())
        st.append(("done" if g["score_ok"] and g["review_ok"] else "fail", txt))
    else:
        st.append(("wait", "채점 전"))

    ver = part["verify"] if part else None
    if ver and ver["pending"] == 0:
        st.append(("done" if ver["agree"] >= AGREE_MIN else "fail", f"동의 {ver['agree']}/{len(ver['items'])}"))
    elif ver:
        st.append(("active", f"동의 {ver['agree']} · 남음 {ver['pending']}"))
    else:
        st.append(("wait", "샘플 전"))

    ap = part["approval"] if part else None
    st.append(("done", f"{ap['approver']} 승인") if ap else ("wait", "승인 전"))

    # 지금 머문 단계: 실행 중 > 실패 > 첫 번째 미완료
    states = [s for s, _ in st]
    if "active" in states:
        cur = states.index("active")
    elif "fail" in states:
        cur = states.index("fail")
    elif "wait" in states:
        cur = states.index("wait")
    else:
        cur = len(states) - 1
    return {"current": cur, "done_all": all(s == "done" for s in states),
            "steps": [{"state": s, "detail": d} for s, d in st]}


# ── 관제 액션 ─────────────────────────────────────────────────────
def act_sample(body: dict) -> dict:
    t = find_target(body.get("target", ""))
    if not t:
        raise ValueError("대상이 없습니다")
    _, recs = read_rows(t["path"])
    if not recs:
        raise ValueError("행이 없습니다")
    orig = originals()
    rng = random.Random(body.get("seed") or time.time_ns())
    by_tag: dict = {}
    for r in recs:
        by_tag.setdefault((r.get("tag") or "").strip(), []).append(r)
    for lst in by_tag.values():
        rng.shuffle(lst)
    picked, order = [], sorted(by_tag)
    while len(picked) < min(SAMPLE_SIZE, len(recs)):  # 태그를 돌아가며 한 건씩 → 고르게
        for tag in order:
            if by_tag[tag] and len(picked) < SAMPLE_SIZE:
                picked.append(by_tag[tag].pop())
    items = [{
        "voc_id": r.get("voc_id", ""), "tag": r.get("tag", ""), "evidence": r.get("evidence", ""),
        "note": r.get("note", ""), "original": orig.get(r.get("voc_id", ""), {}).get("body", "(원문 없음)"),
        "verdict": None, "comment": "",
    } for r in sorted(picked, key=lambda x: x.get("voc_id", ""))]
    data = {"target": t["id"], "created": int(time.time()), "items": items}
    save_json(verify_path(t["id"]), data)
    return {"ok": True, "message": f"{t['id']} 대조 샘플 {len(items)}건을 새로 뽑았습니다"}


def act_verify(body: dict) -> dict:
    tid, vid, verdict = body.get("target", ""), body.get("voc_id", ""), body.get("verdict")
    if verdict not in ("agree", "disagree", None):
        raise ValueError("verdict 는 agree / disagree / null")
    v = load_json(verify_path(tid), None)
    if not v:
        raise ValueError("먼저 샘플을 뽑으세요")
    for it in v["items"]:
        if it["voc_id"] == vid:
            it["verdict"] = verdict
            it["comment"] = (body.get("comment") or "")[:300]
            it["at"] = int(time.time())
            break
    else:
        raise ValueError("샘플에 없는 voc_id")
    save_json(verify_path(tid), v)
    return {"ok": True}


def act_approve(body: dict) -> dict:
    t = find_target(body.get("target", ""))
    approver = (body.get("approver") or "").strip()
    if not t:
        raise ValueError("대상이 없습니다")
    if not approver:
        raise ValueError("승인자 이름을 적어 주세요")
    chk, gr, ver = check(t), grader_scores(t), verify_state(t["id"])
    g = gate(chk, ver, gr)
    if not g["ready"]:
        labels = {"score_ok": "점수 80점", "review_ok": "검토 비율·이유", "verify_ok": "대조 9/10"}
        raise PermissionError("통과 조건을 아직 채우지 못했습니다: " + ", ".join(
            label for k, label in labels.items() if not g[k]))
    appr = approvals()
    appr[t["id"]] = {"approver": approver, "at": int(time.time()), "scores": (
        gr["scores"] if g["score_source"] == "채점관" else chk["scores"]), "score_source": g["score_source"],
        "agree": ver["agree"], "review": chk["review"]["count"]}
    save_json(STATE / "approvals.json", appr)
    return {"ok": True, "message": f"{t['id']} 승인 기록: {approver}"}


def act_revoke(body: dict) -> dict:
    appr = approvals()
    if appr.pop(body.get("target", ""), None) is None:
        raise ValueError("승인 기록이 없습니다")
    save_json(STATE / "approvals.json", appr)
    return {"ok": True, "message": "승인을 취소했습니다"}


# ── 에이전트 실행 · 중지 ──────────────────────────────────────────
# '실행' 버튼 → claude CLI를 헤드리스(-p)로 띄워 review-tagger / review-grader 서브에이전트를 호출한다.
# 서브에이전트로 부르기 때문에 훅 로그에 agent_id 가 남아 관제 화면 단계에 그대로 잡힌다.
# 묶음(batch)마다 실행 줄(lane)이 따로 있어 batch1·2·3 을 동시에 돌릴 수 있다.
import shutil
import subprocess
import threading

JOBS_DIR = STATE / "jobs"
PROMPTS = {
    "tag": ("review-tagger 서브에이전트를 Agent 도구로 한 번만 호출해 묶음 N={n} 을 태깅하게 하세요. "
            "직접 태깅하거나 파일을 쓰지 말고, 서브에이전트가 보고한 한 줄만 그대로 출력하세요."),
    "grade": ("review-grader 서브에이전트를 Agent 도구로 한 번만 호출해 묶음 N={n} 을 채점하게 하세요. "
              "점수표 맨 위에 '범위: NN점', '근거: NN점', '형식: NN점', '검토 건수: n건'을 적게 하고, "
              "evidence 15자는 띄어쓰기 포함으로 세게 하세요. 승인은 하지 마세요. "
              "직접 채점하거나 파일을 쓰지 말고, 서브에이전트가 보고한 결과만 출력하세요."),
}
KIND_NAME = {"tag": "태깅", "grade": "채점"}


def claude_bin() -> str | None:
    """CLAUDE_BIN 환경변수 → PATH 의 claude → 데스크톱 앱에 들어 있는 최신 claude.exe"""
    if os.environ.get("CLAUDE_BIN") and Path(os.environ["CLAUDE_BIN"]).exists():
        return os.environ["CLAUDE_BIN"]
    found = shutil.which("claude")
    if found:
        return found
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "Claude-Data"
    cands = sorted(base.glob("*/claude-code/*/*/claude.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
    return str(cands[0]) if cands else None


def batch_state(n: str) -> tuple[int, int, bool]:
    """(part 행 수, 원문 수, grade 파일 있음)"""
    part = PARTS / f"part_{n}.csv"
    rows = len(read_rows(part)[1]) if part.exists() else 0
    expected = len(batches().get(f"batch{n}", []))
    return rows, expected, (GRADES / f"grade_{n}.md").exists()


class Lane:
    """묶음 하나의 실행 줄. 작업을 순서대로 하나씩 돌린다."""

    def __init__(self, n: str, runner: "Runner"):
        self.n, self.runner = n, runner
        self.queue: list[dict] = []
        self.current: dict | None = None
        self.proc: subprocess.Popen | None = None
        self.stop_flag = False

    def busy(self) -> bool:
        return self.current is not None or bool(self.queue)

    def loop(self):
        while True:
            with self.runner.lock:
                if self.stop_flag or not self.queue:
                    self.current = None
                    return
                job = self.queue.pop(0)
                self.current = job
            if job["kind"] == "grade":
                rows, expected, _ = batch_state(self.n)
                if rows < expected:
                    self.finish(job, "건너뜀", f"part_{self.n}.csv 가 {rows}/{expected}행이라 채점하지 않음")
                    continue
            self.run(job)

    def run(self, job: dict):
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        log_path = JOBS_DIR / f"{job['id']}.log"
        cmd = [claude_bin(), "-p", PROMPTS[job["kind"]].format(n=self.n),
               "--permission-mode", "acceptEdits",
               "--allowedTools", "Agent", "Read", "Glob", "Grep", "Write", "Edit",
               "--output-format", "text"]
        env = dict(os.environ, AX_PROJECT_ROOT=str(ROOT))
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        job.update(status="실행 중", started=int(time.time()), log=log_path.relative_to(BOARD_DIR).as_posix())
        try:
            with open(log_path, "w", encoding="utf-8") as log:
                p = subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL, stdout=log,
                                     stderr=subprocess.STDOUT, creationflags=flags)
                with self.runner.lock:
                    self.proc = p
                    job["pid"] = p.pid
                code = p.wait()
        except Exception as e:
            self.finish(job, "실패", f"{type(e).__name__}: {e}")
            return
        finally:
            with self.runner.lock:
                self.proc = None
        out = read_text(log_path).strip()
        if self.stop_flag:
            self.finish(job, "중지됨", "사용자가 중지")
        elif code == 0:
            self.finish(job, "완료", out.splitlines()[-1][:300] if out else "")
        else:
            self.finish(job, "실패", f"종료 코드 {code} · " + (out[-300:] if out else ""))

    def finish(self, job: dict, status_: str, msg: str):
        job.update(status=status_, ended=int(time.time()), message=msg)
        with self.runner.lock:
            self.runner.record(job)
            if status_ in ("실패", "중지됨"):  # 뒤 작업은 돌리지 않는다
                for j in self.queue:
                    j.update(status="취소", ended=int(time.time()), message="앞 작업이 끝나지 못해 취소")
                    self.runner.record(j)
                self.queue = []
            if self.current is job:
                self.current = None

    def stop(self):
        with self.runner.lock:
            self.stop_flag = True
            p = self.proc
            for j in self.queue:
                j.update(status="취소", ended=int(time.time()), message="중지로 취소")
                self.runner.record(j)
            self.queue = []
        if p and p.poll() is None:
            if os.name == "nt":  # 서브에이전트까지 프로세스 트리 전체 종료
                subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
            else:
                p.terminate()


class Runner:
    def __init__(self):
        self.lock = threading.Lock()
        self.lanes: dict[str, Lane] = {}
        self.history: list[dict] = load_json(JOBS_DIR / "history.json", [])[-40:]

    def record(self, job: dict):  # lock 안에서 부른다
        self.history.append(dict(job))
        self.history = self.history[-40:]
        save_json(JOBS_DIR / "history.json", self.history)

    def lane(self, n: str) -> Lane:
        if n not in self.lanes:
            self.lanes[n] = Lane(n, self)
        return self.lanes[n]

    def snapshot(self) -> dict:
        with self.lock:
            lanes = {n: {"current": dict(l.current) if l.current else None, "queue": [dict(q) for q in l.queue]}
                     for n, l in self.lanes.items()}
            return {"running": any(l.busy() for l in self.lanes.values()), "lanes": lanes,
                    "history": list(reversed(self.history[-15:])), "claude_bin": claude_bin()}

    def running_kind(self, n: str) -> str | None:
        l = self.lanes.get(n)
        return l.current["kind"] if l and l.current else None

    def plan(self, n: str, mode: str) -> list[str]:
        if mode == "tag":
            return ["tag"]
        if mode == "grade":
            return ["grade"]
        if mode == "all":
            return ["tag", "grade"]
        # auto: 남은 단계만
        rows, expected, graded = batch_state(n)
        if rows < expected:
            return ["tag", "grade"]
        if not graded:
            return ["grade"]
        return []

    def start(self, batches_: list[str], mode: str) -> dict:
        if not claude_bin():
            raise ValueError("claude 실행 파일을 찾지 못했습니다. CLAUDE_BIN 환경변수로 경로를 지정하세요")
        valid = set(batches().keys())
        started, skipped = [], []
        for n in batches_:
            if f"batch{n}" not in valid:
                raise ValueError(f"batch{n} 이 없습니다")
            kinds = self.plan(n, mode)
            with self.lock:
                lane = self.lane(n)
                if lane.busy():
                    skipped.append(f"batch{n}(실행 중)")
                    continue
                if not kinds:
                    skipped.append(f"batch{n}(이미 완료)")
                    continue
                lane.queue = [{"id": f"{int(time.time()*1000)}_{n}_{k}", "batch": n, "kind": k,
                               "label": f"batch{n} {KIND_NAME[k]}", "status": "대기"} for k in kinds]
                lane.stop_flag = False
                threading.Thread(target=lane.loop, daemon=True).start()
                started.append(f"batch{n} " + "→".join(KIND_NAME[k] for k in kinds))
        if not started:
            raise PermissionError("시작한 작업이 없습니다: " + ", ".join(skipped))
        msg = "실행 시작: " + " / ".join(started)
        if skipped:
            msg += " · 건너뜀: " + ", ".join(skipped)
        return {"ok": True, "message": msg}

    def stop(self, batches_: list[str] | None) -> dict:
        targets_ = [n for n, l in self.lanes.items() if l.busy() and (not batches_ or n in batches_)]
        if not targets_:
            raise ValueError("실행 중인 작업이 없습니다")
        for n in targets_:
            self.lanes[n].stop()
        return {"ok": True, "message": f"{', '.join('batch'+n for n in targets_)} 중지. 이미 저장된 행은 남습니다"}


RUNNER = Runner()


def _batch_list(body: dict) -> list[str]:
    bs = body.get("batches") or []
    if isinstance(bs, str):
        bs = [bs]
    return [str(b).replace("batch", "") for b in bs]


def act_run(body: dict) -> dict:
    bs = _batch_list(body) or [b.replace("batch", "") for b in batches()]
    return RUNNER.start(bs, body.get("mode", "auto"))


def act_stop(body: dict) -> dict:
    return RUNNER.stop(_batch_list(body))


ACTIONS = {"/api/sample": act_sample, "/api/verify": act_verify,
           "/api/approve": act_approve, "/api/revoke": act_revoke,
           "/api/run": act_run, "/api/stop": act_stop}


# ── HTTP ──────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, data) -> None:
        self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        path = self.path.split("?")[0]
        try:
            if path in ("/", "/monitor.html"):
                self._send(200, HTML.read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/status":
                self._json(200, status())
            else:
                self._json(404, {"error": "없는 경로"})
        except Exception as e:
            self._json(500, {"error": str(e)})

    def do_POST(self):
        fn = ACTIONS.get(self.path)
        if not fn:
            return self._json(404, {"error": "없는 액션"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            self._json(200, fn(body))
        except PermissionError as e:
            self._json(409, {"error": str(e)})
        except ValueError as e:
            self._json(400, {"error": str(e)})
        except Exception as e:
            self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def log_message(self, fmt, *args):
        if self.command == "POST":
            sys.stderr.write("[관제] %s %s\n" % (self.command, self.path))


def main() -> None:
    ap = argparse.ArgumentParser(description="VOC 태깅 관제 서버")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--once", action="store_true", help="상태를 한 번 계산해 출력하고 끝냄")
    args = ap.parse_args()
    if args.once:
        s = status()
        for t in s["targets"]:
            c = t["check"]
            print(f"{t['id']:<12} 행 {c['rows']:>3}/{c['expected']:<3} 점수 {c['scores']} "
                  f"검토 {c['review']['count']}건({c['review']['ratio']}%)")
        e = s["events"]
        print("이벤트:", e.get("total"), e.get("by_event"))
        return
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"관제 서버: http://127.0.0.1:{args.port}  (루트 {ROOT} · {ROOT_SOURCE})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
