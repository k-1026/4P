// research/data/의 노트 5개를 research/data_sources_all.md 한 파일로 합친다
// 실행: node scripts/build_all.js
const fs = require("fs");
const path = require("path");
const { RESEARCH_DIR, NOTE_NAMES, readNote, noteTitle } = require("./notes");

const OUTPUT = path.join(RESEARCH_DIR, "data_sources_all.md");
const SURVEY_DATE = "2026-10-27";

const notes = NOTE_NAMES.map((name) => ({ name, text: readNote(name) }));

const lines = [
  "# 대구 푸드 상권 탐색 서비스: 데이터 소스 후보 통합본",
  "",
  `- 조사 기준일: ${SURVEY_DATE}`,
  "- 원본: `research/data/`의 노트 5개를 한 파일로 합친 것 (원본 파일은 그대로 둠)",
  "",
  "## 목차",
  "",
];

notes.forEach(({ name, text }, i) => {
  lines.push(`${i + 1}. ${noteTitle(text)} (원본: [data/${name}.md](data/${name}.md))`);
});

for (const { text } of notes) {
  // 통합본 안에서 각 노트가 한 단계 아래 제목이 되도록 #을 하나씩 더한다
  const body = text.replace(/^(#{1,5}) /gm, "#$1 ").replace(/\n$/, "");
  lines.push("", "---", "", body);
}

fs.writeFileSync(OUTPUT, lines.join("\n") + "\n", "utf8");
console.log(`통합본 작성: ${path.relative(process.cwd(), OUTPUT)} (노트 ${notes.length}개)`);
