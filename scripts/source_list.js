// 노트 5개의 데이터셋 후보 표를 모아 research/data/source_list.csv로 저장한다
// 실행: node scripts/source_list.js          (목록만 만들기)
//       node scripts/source_list.js --check  (공식 URL 접속 상태도 확인)
const fs = require("fs");
const path = require("path");
const { DATA_DIR, NOTE_NAMES, readNote, readSourceRows, firstUrl } = require("./notes");

const OUTPUT = path.join(DATA_DIR, "source_list.csv");
const CHECK_URLS = process.argv.includes("--check");

const COLUMNS = ["노트", "데이터셋명", "제공기관", "제공 형식", "공식 URL", "대구 지역 데이터 여부", "URL 상태"];

function csvCell(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

async function urlStatus(url) {
  if (!url) return "URL 없음";
  try {
    const res = await fetch(url, { redirect: "follow", signal: AbortSignal.timeout(15000) });
    return String(res.status);
  } catch (err) {
    return `오류: ${err.name}`;
  }
}

async function main() {
  const records = [];

  for (const name of NOTE_NAMES) {
    for (const row of readSourceRows(readNote(name))) {
      records.push({
        노트: `${name}.md`,
        데이터셋명: row["데이터셋명"],
        제공기관: row["제공기관"],
        "제공 형식": row["제공 형식(CSV/API)"],
        "공식 URL": firstUrl(row["공식 출처 URL"]),
        "대구 지역 데이터 여부": row["대구 지역 데이터 여부"],
        "URL 상태": "",
      });
    }
  }

  if (CHECK_URLS) {
    for (const record of records) {
      record["URL 상태"] = await urlStatus(record["공식 URL"]);
      console.log(`${record["URL 상태"]}\t${record["데이터셋명"]}`);
    }
  }

  const lines = [COLUMNS.join(",")];
  for (const record of records) {
    lines.push(COLUMNS.map((col) => csvCell(record[col])).join(","));
  }

  // 엑셀에서 한글이 깨지지 않도록 BOM을 붙인다
  fs.writeFileSync(OUTPUT, "﻿" + lines.join("\r\n") + "\r\n", "utf8");
  console.log(`데이터셋 ${records.length}개 → ${path.relative(process.cwd(), OUTPUT)}`);
}

main();
