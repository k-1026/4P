# -*- coding: utf-8 -*-
"""폐업 신고된 대구 식당의 지도 앱 표시 실측 집계 (결과/P?_폐업표시실측.csv)"""
import csv,glob,collections,sys,io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
smp={r['번호']:r for r in csv.DictReader(open('폐업표시실측_표본100.csv',encoding='utf-8-sig'))}
rows=[]
for f in sorted(glob.glob('결과/P?_폐업표시실측.csv')):
    rows+=[r for r in csv.DictReader(open(f,encoding='utf-8-sig')) if r.get('번호')]
apps=['네이버','카카오','구글']
F=lambda r,a: r[a+'_찾음'].strip()=='찾음'
CL=lambda r,a: F(r,a) and r[a+'_폐업표시'].strip().upper()=='O'
OPEN=lambda r,a: F(r,a) and r[a+'_영업표시'].strip().startswith('영업 중')
grp=lambda r: smp[r['번호']]['묶음']
groups=sorted(set(grp(r) for r in rows))
out=[];P=out.append
P(f'# 폐업 신고 가게의 지도 앱 표시 실측 — {len(rows)}곳\n')
P('표본: 인허가에 폐업으로 신고된 대구 식당 100곳 무작위 (seed 1120). 화면은 2026-11-20에 Aside가 확인\n')
P('묶음별 가게 수: '+' · '.join(f'{g} {sum(1 for r in rows if grp(r)==g)}' for g in groups)+'\n')
def tbl(sub,title):
    n=len(sub)
    P(f'\n## {title} ({n}곳)\n')
    P('| 내용 | 네이버 | 카카오 | 구글 |'); P('|---|---|---|---|')
    P('| 그 주소에서 그 가게를 찾음 (앱에 남아 있음) | '+' | '.join(f'{sum(F(r,a) for r in sub)}' for a in apps)+' |')
    P('| 그중 폐업 표시 있음 | '+' | '.join(f'{sum(CL(r,a) for r in sub)}' for a in apps)+' |')
    P('| 그중 폐업 표시 없음 | '+' | '.join(f'{sum(F(r,a) and not CL(r,a) for r in sub)}' for a in apps)+' |')
    P('| 그중 "영업 중"으로 보임 | '+' | '.join(f'{sum(OPEN(r,a) for r in sub)}' for a in apps)+' |')
    anyf=[r for r in sub if any(F(r,a) for a in apps)]
    P(f'\n- 세 앱 중 어느 앱에든 남아 있음: {len(anyf)}곳 / 어디에도 없음: {n-len(anyf)}곳')
    P(f'- 남아 있는 곳 중 폐업 표시가 없는 앱이 하나라도 있음: {sum(1 for r in anyf if any(F(r,a) and not CL(r,a) for a in apps))}곳')
    P(f'- 어느 앱에서든 "영업 중"으로 보임: {sum(1 for r in sub if any(OPEN(r,a) for a in apps))}곳')
tbl(rows,'전체')
for g in groups: tbl([r for r in rows if grp(r)==g],g)
P('\n## 앱별 영업 상태 문구 (찾은 가게)\n')
for a in apps:
    c=collections.Counter(r[a+'_영업표시'].strip() or '(빈칸)' for r in rows if F(r,a))
    P(f'- {a}: '+' · '.join(f'{k} {v}' for k,v in c.most_common()))
P('\n## 읽을 때 주의\n')
P('- 상태 문구는 본 시각에 따라 달라짐 ("영업 전" · "영업 종료"는 그 시각 기준)')
P('- "없음"은 그 주소에서 그 가게를 못 찾았다는 뜻. 같은 자리에 다른 가게가 있는 경우가 많음 (메모 칸)')
P('- 인허가 폐업 신고 뒤 같은 자리에서 주인만 바뀐 경우가 섞일 수 있음 (메모 칸)')
P('- 표본 수가 작아 비율은 참고용')
open('분석/폐업표시_분석.md','w',encoding='utf-8').write('\n'.join(out)+'\n')
print('\n'.join(out))
