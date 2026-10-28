// 데이터 소스 노트 5개를 읽는 공통 모듈
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const RESEARCH_DIR = path.join(ROOT, "research");
const DATA_DIR = path.join(RESEARCH_DIR, "data");

// 통합본과 목록에 들어가는 순서
const NOTE_NAMES = [
  "food_businesses",
  "traditional_markets",
  "food_districts",
  "food_prices",
  "local_food_access",
];

function readNote(name) {
  const text = fs.readFileSync(path.join(DATA_DIR, `${name}.md`), "utf8");
  return text.replace(/\r\n/g, "\n");
}

function noteTitle(text) {
  const first = text.split("\n")[0];
  return first.replace(/^# /, "");
}

function splitRow(line) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

// "데이터셋명"과 "공식 출처 URL" 열이 있는 표의 행을 모두 꺼낸다
function readSourceRows(text) {
  const rows = [];
  let header = null;

  for (const line of text.split("\n")) {
    if (!line.trim().startsWith("|")) {
      header = null;
      continue;
    }
    const cells = splitRow(line);
    if (!header) {
      if (cells.includes("데이터셋명") && cells.includes("공식 출처 URL")) {
        header = cells;
      }
      continue;
    }
    if (cells.every((cell) => /^-+$/.test(cell))) continue;

    const row = {};
    header.forEach((name, i) => (row[name] = cells[i] || ""));
    rows.push(row);
  }
  return rows;
}

function firstUrl(text) {
  const match = text.match(/https?:\/\/[^\s)]+/);
  return match ? match[0] : "";
}

module.exports = {
  RESEARCH_DIR,
  DATA_DIR,
  NOTE_NAMES,
  readNote,
  noteTitle,
  readSourceRows,
  firstUrl,
};
