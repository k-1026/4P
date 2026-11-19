# -*- coding: utf-8 -*-
"""R6 정보 격차 실측 분석: 결과/R6-?_정보격차.csv를 합쳐 앱별 정보 유무를 구군 가중치로 계산"""
import csv,glob,collections,sys,io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
pop={'달서구':6482,'북구':5239,'수성구':5115,'동구':4503,'중구':3596,'달성군':3059,'서구':2400,'남구':2273,'군위군':408}
smp={r['번호']:r for r in csv.DictReader(open('별점실측_표본100.csv',encoding='utf-8-sig'))}
rows=[]
for f in sorted(glob.glob('결과/R6-?_정보격차.csv')):
    rows+=[r for r in csv.DictReader(open(f,encoding='utf-8-sig')) if r.get('번호')]
n=collections.Counter(smp[r['번호']]['구군'] for r in rows)
W=lambda r: pop[smp[r['번호']]['구군']]/n[smp[r['번호']]['구군']]
apps=['네이버','카카오','구글']; items=['주차','메뉴','가격','영업시간','휴무','예약편의','최신']
found=lambda r,a: r[a+'_찾음'].strip().startswith('찾음') or r[a+'_찾음'].strip().upper()=='O'  # R6-2는 찾음을 O로 적음
has=lambda r,a,k: r[f'{a}_{k}'].strip().upper().startswith('O')
def pct(sub,fn):
    den=sum(W(r) for r in sub); num=sum(W(r) for r in sub if fn(r)); c=sum(1 for r in sub if fn(r))
    return (f'{num/den*100:.0f}% ({c}/{len(sub)})' if den else '-')
out=[]; P=out.append
P(f'# 정보 격차 실측 분석 — {len(rows)}곳 (구군 가게 수 가중)\n')
P('구군별 표본: '+' · '.join(f'{k} {v}' for k,v in n.items())+'\n')
P('## 1. 같은 가게를 찾음\n'); P('| 앱 | 찾음 |'); P('|---|---|')
for a in apps: P(f'| {a} | {pct(rows,lambda r:found(r,a))} |')
P('\n## 2. 그 앱에서 찾은 가게 중 정보가 있는 비율\n'); P('| 정보 | 네이버 | 카카오 | 구글 |'); P('|---|---|---|---|')
for k in items:
    P(f'| {k} | '+' | '.join(pct([r for r in rows if found(r,a)],lambda r,a=a:has(r,a,k)) for a in apps)+' |')
P('\n## 3. 전체 가게 기준: 어느 앱에든 그 정보가 있는가 (모아 보면 얼마나 채워지나)\n'); P('| 정보 | 네이버만 봤을 때 | 세 앱을 모으면 | 모아서 늘어나는 가게 | 어느 앱에도 없음 |'); P('|---|---|---|---|---|')
for k in items:
    nav=lambda r:found(r,'네이버') and has(r,'네이버',k); anyf=lambda r:any(found(r,a) and has(r,a,k) for a in apps)
    P(f'| {k} | {pct(rows,nav)} | {pct(rows,anyf)} | {pct(rows,lambda r:anyf(r) and not nav(r))} | {pct(rows,lambda r:not anyf(r))} |')
two=[r for r in rows if sum(found(r,a) for a in apps)>=2]
P(f'\n## 4. 두 앱 이상에서 찾은 가게 {len(two)}곳: 한 앱에만 있는 정보\n'); P('| 정보 | 찾은 앱 중 일부에만 있음 | 찾은 앱 모두에 있음 | 찾은 앱 모두에 없음 |'); P('|---|---|---|---|')
for k in items:
    def st(r):
        v=[has(r,a,k) for a in apps if found(r,a)]; return 'all' if all(v) else ('none' if not any(v) else 'some')
    P(f'| {k} | {pct(two,lambda r:st(r)=="some")} | {pct(two,lambda r:st(r)=="all")} | {pct(two,lambda r:st(r)=="none")} |')
mm=[r for r in rows if '불일치' in r['한앱에만_있는_정보']]; pr=[r for r in rows if '가격 차이' in r['한앱에만_있는_정보']]
P(f'\n## 5. 앱끼리 영업시간 · 휴무가 서로 다른 가게\n\n- 두 앱 이상에서 찾은 {len(two)}곳 중 **{pct(two,lambda r:"불일치" in r["한앱에만_있는_정보"])}**\n- 같은 메뉴의 가격이 다른 가게: {len(pr)}곳\n')
P('| 번호 | 상호 | 구군 | 무엇이 다른가 |'); P('|---|---|---|---|')
for r in mm:
    t=[x.strip() for x in r['한앱에만_있는_정보'].split('/') if '불일치' in x]
    P(f"| {r['번호']} | {r['상호']} | {smp[r['번호']]['구군']} | {' / '.join(t)[:140]} |")
P('\n## 6. 주차 안내 문구 (있는 가게만)\n'); P('| 번호 | 상호 | 네이버 | 카카오 | 구글 |'); P('|---|---|---|---|---|')
for r in rows:
    v=[r[f'{a}_주차'].strip() if found(r,a) and has(r,a,'주차') else '' for a in apps]
    if any(v): P(f"| {r['번호']} | {r['상호']} | "+' | '.join(x[2:62] for x in v)+' |')
open('분석/정보격차_분석.md','w',encoding='utf-8').write('\n'.join(out)+'\n')
print('\n'.join(out[:60]))
