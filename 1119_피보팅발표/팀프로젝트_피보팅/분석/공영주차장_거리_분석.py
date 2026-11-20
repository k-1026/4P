# -*- coding: utf-8 -*-
"""실측 100곳 x 대구 공영주차장(전국주차장정보표준데이터 대구분) 가장 가까운 거리.
거리 값은 data.go.kr 화면에서 받은 대구 1,086곳으로 계산한 결과를 붙여 넣은 것 (2026-11-20)."""
import csv,glob,collections,sys,io,json
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
D=json.load(open('분석/공영주차장_거리_100곳.json',encoding='utf-8'))
dist={str(r[0]):r for r in D}
rows=[]
for f in sorted(glob.glob('결과/R6-?_정보격차.csv')):
    rows+=[r for r in csv.DictReader(open(f,encoding='utf-8-sig')) if r.get('번호')]
found=lambda r,a: r[a+'_찾음'].strip().startswith('찾음') or r[a+'_찾음'].strip().upper()=='O'
def park(r,a):
    v=r[a+'_주차'].strip()
    if not v.upper().startswith('O'): return False
    if a=='카카오' and ('AI' in v or '요약' in v): return False
    if a=='구글' and '휠체어' in v: return False
    return True
smp={r['번호']:r for r in csv.DictReader(open('별점실측_표본100.csv',encoding='utf-8-sig'))}
has=[r for r in rows if any(found(r,a) and park(r,a) for a in ['네이버','카카오','구글'])]
no=[r for r in rows if r not in has]
print('주차 안내 있음',len(has),'없음',len(no),'전체',len(rows))
def summ(sub,name):
    s=[dist[r['번호']] for r in sub if r['번호'] in dist]
    b=lambda f:sum(1 for x in s if f(x))
    print(f'{name} (좌표 {len(s)}곳): 공영 300m 안 {b(lambda x:x[2]>0)} · 500m 안 {b(lambda x:x[3]>0)} · 500m 밖 {b(lambda x:x[3]==0)} · 가장 가까운 공영 거리 중앙값 {sorted(x[1] for x in s)[len(s)//2]}m')
summ(rows,'전체'); summ(has,'앱에 주차 안내 있음'); summ(no,'어느 앱에도 주차 안내 없음')
gu=collections.defaultdict(list)
for r in no:
    if r['번호'] in dist: gu[smp[r['번호']]['구군']].append(dist[r['번호']])
for g,v in gu.items(): print(g,len(v),'300m 안',sum(1 for x in v if x[2]>0))
