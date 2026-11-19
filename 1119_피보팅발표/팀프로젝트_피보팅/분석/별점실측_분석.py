# 별점 실측 R1~R4 합쳐 분석. 대구 전체 값은 구군 가게 수로 가중.
import csv, glob, os, statistics as st
B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pop = {'달서구':6482,'북구':5239,'수성구':5115,'동구':4503,'중구':3596,'달성군':3059,'서구':2400,'남구':2273,'군위군':408}  # 서비스 대상 (11-19 기본 파일, 영업중+미확인)
smp = {r['번호']: r for r in csv.DictReader(open(f'{B}/별점실측_표본100.csv', encoding='utf-8-sig'))}
rows = []
for f in sorted(glob.glob(f'{B}/결과/R?_별점실측.csv')):
    rd = list(csv.reader(open(f, encoding='utf-8-sig')))
    h = rd[0]
    for r in rd[1:]:
        if len(r) == 22 and not any(r[16:21]): del r[16]
        assert len(r) == len(h), (f, r)
        d = dict(zip(h, r)); d['구군'] = smp[d['번호']]['구군']; rows.append(d)
ng = {}
for d in rows: ng[d['구군']] = ng.get(d['구군'], 0) + 1
for d in rows: d['w'] = pop[d['구군']] / ng[d['구군']]
W = sum(d['w'] for d in rows)
def pct(cond, base=None):
    base = base or rows
    b = sum(d['w'] for d in base)
    return (100 * sum(d['w'] for d in base if cond(d)) / b) if b else float('nan'), sum(1 for d in base if cond(d)), len(base)
def num(x):
    try: return float(x)
    except: return None
out = [f'# 별점 실측 분석 (표본 {len(rows)}곳, 구군 가중)\n', '| 항목 | 네이버 | 카카오 | 구글 |', '|---|---|---|---|']
A = ['네이버', '카카오', '구글']
rc = {'네이버': '네이버_방문자리뷰', '카카오': '카카오_후기', '구글': '구글_리뷰'}
def cell(t): return f'{t[0]:.0f}% ({t[1]}/{t[2]})'
out.append('| 같은 가게를 찾음 | ' + ' | '.join(cell(pct(lambda d, a=a: d[f'{a}_찾음'] == '찾음')) for a in A) + ' |')
out.append('| 별점이 보임 | ' + ' | '.join(cell(pct(lambda d, a=a: num(d[f'{a}_별점']) is not None)) for a in A) + ' |')
out.append('| 리뷰 태그가 보임 | ' + ' | '.join(cell(pct(lambda d, a=a: d[f'{a}_태그3'].strip() != '')) for a in A) + ' |')
med = []
for a in A:
    v = [num(d[rc[a]]) for d in rows if d[f'{a}_찾음'] == '찾음' and num(d[rc[a]]) is not None]
    med.append(f'{st.median(v):.0f} (n={len(v)})' if v else '-')
out.append('| 리뷰 수 중앙값 (찾은 곳) | ' + ' | '.join(med) + ' |')
out.append('')
two = [d for d in rows if sum(num(d[f'{a}_별점']) is not None for a in A) >= 2]
def gap(d):
    v = [num(d[f'{a}_별점']) for a in A if num(d[f'{a}_별점']) is not None]; return max(v) - min(v)
out.append(f'## 별점이 두 앱 이상에서 보이는 가게: {len(two)}곳 ({pct(lambda d: d in two)[0]:.0f}%, 가중)\n')
if two:
    out.append(f'- 앱 사이 별점 차이 0.5점 이상: {cell(pct(lambda d: gap(d) >= 0.5, two))}')
    out.append(f'- 1.0점 이상: {cell(pct(lambda d: gap(d) >= 1.0, two))}')
    out.append(f'- 차이 중앙값: {st.median(gap(d) for d in two):.2f}점')
    out.append('- 단, 리뷰 5개 미만 별점 포함. 리뷰 5개 이상인 앱만 쓴 경우:')
    def ok(d, a): return num(d[f'{a}_별점']) is not None and (num(d[rc[a]]) or 0) >= 5
    two5 = [d for d in rows if sum(ok(d, a) for a in A) >= 2]
    if two5:
        g5 = lambda d: (lambda v: max(v) - min(v))([num(d[f'{a}_별점']) for a in A if ok(d, a)])
        out.append(f'  - 해당 {len(two5)}곳, 0.5점 이상 차이 {cell(pct(lambda d: g5(d) >= 0.5, two5))}')
out.append('\n## 영업 표시\n')
for a in A:
    out.append(f'- {a}: 폐업 · 휴업 표시 {sum(1 for d in rows if any(k in d[f"{a}_영업표시"] for k in ("폐업","휴업")))}곳, 휴무 표시 {sum(1 for d in rows if "휴무" in d[f"{a}_영업표시"])}곳')
out.append('\n## 구군별 찾음 (네이버 / 카카오 / 구글)\n')
for g in pop:
    s = [d for d in rows if d['구군'] == g]
    if s: out.append(f'- {g} ({len(s)}곳): ' + ' / '.join(str(sum(d[f"{a}_찾음"] == "찾음" for d in s)) for a in A))
open(f'{B}/분석/별점실측_분석.md', 'w', encoding='utf-8').write('\n'.join(out) + '\n')
print('\n'.join(out))
