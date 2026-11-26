"""혼밥DB 스스로 갱신: 다운로드 폴더에 새 혼밥DB가 오면 확인하고 마이/data/혼밥_동성로.db를 바꾼다.

찾는 것 (다운로드 폴더, 가장 최근 것 하나)
  - 이름에 '혼밥DB'가 들어간 .zip  -> 안의 .db 파일 하나만 읽는다 (다른 파일은 풀거나 실행하지 않는다)
  - 혼밥_동성로*.db 파일

바꾸기 전에 확인하는 것: SQLite 파일이 깨지지 않았는지, 필요한 표(식당·근거·주요메뉴·설정)와 보기(혼밥가게)가 있는지,
가게가 1곳 이상인지. 하나라도 틀리면 바꾸지 않고 이유를 남긴다.
바꿀 때는 지금 DB를 data/backup/에 남기고, 무엇을 언제 넣었는지 data/db_source.json에 적는다.

  check()                  한 번 확인 (핸드폰 서버가 켜질 때와 10분마다 부른다)
  python db_update.py      지금 바로 한 번 확인
"""
import glob
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime

import real_stores

DATA = os.path.dirname(real_stores.DB)
SOURCE = os.path.join(DATA, "db_source.json")
BACKUP = os.path.join(DATA, "backup")
DOWNLOADS = os.path.join(os.path.expanduser("~"), "Downloads")
MAX_DB = 50 * 1024 * 1024
NEEDED = {"식당", "근거", "주요메뉴", "설정", "혼밥가게"}


def _name(info):
    """압축 안 파일 이름 (한글 이름이 cp437로 읽힌 경우를 되돌린다)"""
    if info.flag_bits & 0x800:
        return info.filename
    raw = info.filename.encode("cp437")
    for enc in ("utf-8", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return info.filename


def candidates(folder=DOWNLOADS):
    files = glob.glob(os.path.join(folder, "*혼밥DB*.zip")) + glob.glob(os.path.join(folder, "혼밥_동성로*.db"))
    return sorted((f for f in files if os.path.isfile(f)), key=os.path.getmtime, reverse=True)


def _read_db(path):
    """후보 파일에서 DB 내용(바이트)을 꺼낸다. 압축이면 .db 하나만 읽는다."""
    if path.lower().endswith(".db"):
        if os.path.getsize(path) > MAX_DB:
            raise ValueError("DB 파일이 너무 커요")
        with open(path, "rb") as file:
            return file.read(), os.path.basename(path)
    with zipfile.ZipFile(path) as z:
        dbs = [i for i in z.infolist() if _name(i).lower().endswith(".db") and not i.is_dir()]
        if len(dbs) != 1:
            raise ValueError(f"압축 안에 .db 파일이 {len(dbs)}개예요 (1개여야 해요)")
        if dbs[0].file_size > MAX_DB:
            raise ValueError("DB 파일이 너무 커요")
        return z.read(dbs[0]), _name(dbs[0])


def validate(path):
    """DB가 쓸 만한지 확인한다. 괜찮으면 (가게 수, 만든날), 아니면 ValueError"""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("DB 파일이 깨졌어요")
        names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
        if not NEEDED <= names:
            raise ValueError(f"필요한 표가 없어요: {', '.join(sorted(NEEDED - names))}")
        count = con.execute("SELECT count(*) FROM 혼밥가게").fetchone()[0]
        if count < 1:
            raise ValueError("가게가 하나도 없어요")
        made = dict(con.execute("SELECT 이름, 값 FROM 설정").fetchall()).get("만든날")
    except sqlite3.DatabaseError as error:
        raise ValueError(f"SQLite DB가 아니에요 ({error})") from error
    finally:
        con.close()
    return count, made


def _record():
    try:
        with open(SOURCE, encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError):
        return {}


def check(folder=DOWNLOADS, target=real_stores.DB, log=print):
    """다운로드 폴더에 새 혼밥DB가 있으면 바꾼다. 결과를 글로 돌려준다."""
    found = candidates(folder)
    if not found:
        return "새 혼밥DB 없음"
    path = found[0]
    stamp = f"{os.path.basename(path)}|{os.path.getsize(path)}|{os.path.getmtime(path):.0f}"
    record = _record()
    if record.get("stamp") == stamp:
        return "이미 넣은 혼밥DB"
    try:
        data, inner = _read_db(path)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        msg = f"⚠️ {os.path.basename(path)}을 읽지 못해서 바꾸지 않았어요: {error}"
        log(msg)
        return msg
    digest = hashlib.sha256(data).hexdigest()
    if record.get("sha256") == digest:  # 같은 내용이 이름만 바뀌어 다시 온 경우
        _save_record({**record, "stamp": stamp})
        return "이미 넣은 혼밥DB (내용 같음)"
    with tempfile.TemporaryDirectory() as tmp:
        new = os.path.join(tmp, "new.db")
        with open(new, "wb") as file:
            file.write(data)
        try:
            count, made = validate(new)
        except ValueError as error:
            msg = f"⚠️ {os.path.basename(path)}의 DB를 확인했더니 문제가 있어서 바꾸지 않았어요: {error}"
            log(msg)
            return msg
        if os.path.exists(target):
            os.makedirs(BACKUP, exist_ok=True)
            shutil.copy2(target, os.path.join(BACKUP, f"혼밥_동성로_{datetime.now():%Y%m%d_%H%M%S}.db"))
        part = target + ".new"
        shutil.copyfile(new, part)
        os.replace(part, target)
    _save_record({"stamp": stamp, "sha256": digest, "file": os.path.basename(path), "inner": inner,
                  "stores": count, "made": made, "put_at": f"{datetime.now():%Y-%m-%d %H:%M:%S}"})
    msg = f"✅ 혼밥DB를 갱신했어요: {os.path.basename(path)} · 가게 {count}곳 · 만든날 {made}"
    log(msg)
    return msg


def _save_record(record):
    os.makedirs(DATA, exist_ok=True)
    tmp = SOURCE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as file:
        json.dump(record, file, ensure_ascii=False, indent=2)
    os.replace(tmp, SOURCE)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(check())
