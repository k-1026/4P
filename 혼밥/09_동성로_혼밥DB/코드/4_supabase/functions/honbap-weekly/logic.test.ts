// 파이썬(갱신/*.py)이 뽑은 시험 자료와 logic.ts 결과를 비교한다.
// node logic.test.ts <fixture.json> [<compare.json>]
import { readFileSync } from "node:fs";
import { addrKey, baseName, compare, day, dueRechecks, meters, nameKey, sameName, toWgs84 } from "./logic.ts";

const fx = JSON.parse(readFileSync(process.argv[2], "utf-8"));
let fails = 0;
const bad = (label: string, detail: unknown) => { fails++; if (fails <= 15) console.log("틀림", label, JSON.stringify(detail)); };

let n = 0;
for (const [a, b, same, base, key, ak] of fx.pairs) {
  n++;
  if (sameName(a, b) !== same) bad("같은 이름", [a, b, same]);
  if (baseName(a) !== base) bad("지점명 뗀 이름", [a, base, baseName(a)]);
  if (nameKey(a) !== key) bad("이름 열쇠", [a, key, nameKey(a)]);
}
console.log("이름 쌍", n);
for (const [x, ak] of fx.addr) if (addrKey(x) !== ak) bad("주소 열쇠", [x, ak, addrKey(x)]);
console.log("주소", fx.addr.length);
let worst = 0;
for (const [x, y, want] of fx.coords) {
  const got = toWgs84(x, y);
  if ((got === null) !== (want === null)) { bad("좌표 있음/없음", [x, y, want, got]); continue; }
  if (got && want) worst = Math.max(worst, Math.abs(got[0] - want[0]), Math.abs(got[1] - want[1]));
}
if (worst > 1e-9) bad("좌표 차이", worst);
console.log("좌표", fx.coords.length, "최대 차이(도)", worst);
for (const [a, b, want] of fx.dist) if (Math.abs(meters(a, b) - want) > 1e-6) bad("거리", [a, b, want]);
for (const [d, want] of fx.day) if (day(d) !== want) bad("날짜", [d, want, day(d)]);

if (process.argv[3]) {   // 비교 전체: 파이썬 인허가_비교와 같은 새 가게·폐업이 나오는지
  const cf = JSON.parse(readFileSync(process.argv[3], "utf-8"));
  for (const t of cf.cases) {
    const got = compare(t.rows, fx.known, fx.shops, t.since);
    const k1 = (x: { mng_no: string }) => x.mng_no;
    const gotNew = got.fresh.map(k1).sort(), wantNew = t.new.map((x: { 관리번호: string }) => x.관리번호).sort();
    if (JSON.stringify(gotNew) !== JSON.stringify(wantNew)) bad(`새 가게(${t.since})`, { 파이썬: wantNew.length, 새코드: gotNew.length });
    const byNo = new Map(got.fresh.map((x) => [x.mng_no, x]));
    for (const w of t.new) {
      const g = byNo.get(w.관리번호);
      if (!g) continue;
      if (w.위도 && (Math.abs(Number(w.위도) - (g.lat ?? 0)) > 1e-6 || w.행정동_추정 !== g.dong)) bad("새 가게 좌표·동", [w, g]);
      if (w.메모 !== g.memo) bad("새 가게 메모", [w.메모, g.memo]);
    }
    const gotC = got.closed.map((x) => x.restaurant_id + "/" + x.mng_no).sort();
    const wantC = t.closed.map((x: { 식당ID: string; 관리번호: string }) => x.식당ID + "/" + x.관리번호).sort();
    if (JSON.stringify(gotC) !== JSON.stringify(wantC)) bad(`폐업(${t.since})`, { 파이썬: wantC, 새코드: gotC });
    console.log(`비교 ${t.since}: 줄 ${t.rows.length}, 새 가게 ${gotNew.length}(파이썬 ${wantNew.length}), 폐업 ${gotC.length}(파이썬 ${wantC.length})`);
  }
}

// 후기 다시 보기: 후기_다시보기.py 시험과 같은 장면
{
  const T = [
    { target_key: "L1", kind: "새가게" as const, name: "새1", road_address: "", map_url: "", first_seen: "2026-11-26" },
    { target_key: "MA1", kind: "기존" as const, name: "기1", road_address: "", map_url: "", first_seen: "2026-11-25" },
    { target_key: "MA2", kind: "기존" as const, name: "기2", road_address: "", map_url: "", first_seen: "2026-11-25" },
  ];
  const keys = (r: { picked: { target_key: string }[] }) => r.picked.map((x) => x.target_key).join(",");
  const chk = (label: string, got: string, want: string) => { if (got !== want) bad(label, [want, got]); };
  chk("13일째 없음", keys(dueRechecks(T, [], new Set(), "2026-12-09")), "");
  chk("14일째 새 가게", keys(dueRechecks(T, [], new Set(), "2026-12-10")), "L1");
  const log1 = [{ target_key: "L1", seen_on: "2026-12-10", found: "예", memo: "" }];
  chk("2번째는 28일째", keys(dueRechecks(T, log1, new Set(), "2026-12-23")), "");
  chk("28일째", keys(dueRechecks(T, log1, new Set(), "2026-12-24")), "L1");
  chk("DB에 들어간 새 가게는 안 봄", keys(dueRechecks(T, log1, new Set(["L1"]), "2026-12-24")), "");
  chk("기존은 30일째, 새 가게 먼저", keys(dueRechecks(T, log1, new Set(), "2026-12-25")), "L1,MA1,MA2");
  chk("최대 2곳", keys(dueRechecks(T, log1, new Set(), "2026-12-25", 2)), "L1,MA1");
  const log2 = [...log1, { target_key: "MA1", seen_on: "2026-12-25", found: "아니오", memo: "" }, { target_key: "MA2", seen_on: "2026-12-25", found: "예", memo: "폐업 표시" }];
  chk("못 찾음·폐업은 그만", keys(dueRechecks(T, log2, new Set(), "2027-03-01")), "L1");
  const log3 = [{ target_key: "MA1", seen_on: "2026-12-25", found: "예", memo: "" }];
  chk("기존은 마지막 본 날 + 30일", keys(dueRechecks(T, log3, new Set(), "2027-01-23")) , "L1,MA2");
}

console.log(fails ? `실패 ${fails}` : "모두 통과");
process.exit(fails ? 1 : 0);
