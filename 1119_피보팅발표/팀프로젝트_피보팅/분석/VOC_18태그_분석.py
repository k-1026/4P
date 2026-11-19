# -*- coding: utf-8 -*-
"""확정된 18태그 분류(분류/tag_V*.csv)를 집계해 분석/VOC_18태그_분석.md를 만든다"""
import csv,collections,re,sys,io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
files={'V0':'결과/V0_기존VOC_재사용.csv','V1b':'결과/V1b_커뮤니티_중립.csv','V2b':'결과/V2b_앱리뷰_무작위.csv','V3':'결과/V3_가기전확인_중립.csv'}
src={}; rows=[]
for n,f in files.items():
    for i,x in enumerate(csv.DictReader(open(f,encoding='utf-8-sig')),1):
        src[x.get('voc_id') or f'{n}_{i:03d}']=x
    for x in csv.DictReader(open(f'분류/tag_{n}.csv',encoding='utf-8-sig')):
        x['파일']=n; x['글종류']=src[x['voc_id']].get('글종류','') or ('후기' if n=='V2b' else '모름'); x['원문']=src[x['voc_id']]['원문_핵심문장']; rows.append(x)
order=['M1','M2','M3','M4','M5','M6','M9','M10','M7','M8','R1','H1','H2','S1','S2','I1','해당없음','검토']
name={'M1':'여러 경로를 번갈아 봄','M2':'앱마다 평가가 달라 헷갈림','M3':'못 믿어 교차 확인','M4':'많아서 고르기 어려움','M5':'앱끼리 가게 정보가 다름','M6':'앱 표시가 틀림','M9':'필요한 정보를 몰랐음','M10':'가기 전에 확인함','M7':'리뷰 · 별점을 못 믿음','M8':'별점으로 1차 거름','R1':'리뷰 · 별점을 믿음','H1':'한 가지 경로로 충분','H2':'비교 끝에 한 곳으로 갈아탐','S1':'물어서 찾음','S2':'고르는 기준 · 요령','I1':'정보 공유','해당없음':'','검토':''}
o=[]; P=o.append
P('# VOC 18태그 분석 (확정, 2026-11-19)\n')
P('> 기준 `../분류기준_18태그.md` · 채점 범위 · 근거 · 형식 모두 100 · 사람 대조 2차 9/10 통과')
P('> **줄 수는 "이런 말이 나온다"를 보는 용도. "몇 %가 그렇다"의 근거로 쓰지 않음** (`../출처_등급_기준.md` — 체감 · 이유 질문에서 A)')
P('> V0는 찾을 것을 정해 두고 모은 참고용 · 질문 글을 문장마다 쪼갠 자료. V1b · V3가 중립 표본\n')
g={n:len({x['voc_id'] for x in rows if x['파일']==n}) for n in files}
P('## 1. 태그별 줄 수\n'); P('| 태그 | 이름 | V0 ('+str(g['V0'])+'글) | V1b ('+str(g['V1b'])+') | V2b ('+str(g['V2b'])+') | V3 ('+str(g['V3'])+') | 합 |'); P('|---|---|---|---|---|---|---|')
c=collections.Counter((x['파일'],x['tag']) for x in rows)
for t in order: P(f"| {t} | {name[t]} | "+' | '.join(str(c[(n,t)]) for n in files)+f" | {sum(c[(n,t)] for n in files)} |")
P('\n## 2. 글 종류별 (중립 표본 V1b · V3) — 본인 경험인가, 조언인가\n'); P('| 태그 | 후기 (본인 경험) | 질문 (본인 필요) | 답변 (남에게 조언) | 기타 |'); P('|---|---|---|---|---|')
mid=[x for x in rows if x['파일'] in('V1b','V3')]; cg=collections.Counter((x['tag'],x['글종류']) for x in mid)
for t in order:
    v=[cg[(t,k)] for k in ('후기','질문','답변')]; etc=sum(cg[(t,k)] for k in set(k for _,k in cg) if k not in('후기','질문','답변'))
    if sum(v)+etc: P(f"| {t} {name[t]} | {v[0]} | {v[1]} | {v[2]} | {etc} |")
info=[x for x in rows if x['tag'] in('M5','M6','M9','M10','I1')]
def kind(v): return re.sub(r'\(.*','',v).strip() or '(빈칸)'
P('\n## 3. 가게 정보 태그(M5 · M6 · M9 · M10 · I1) — 정보 종류 × 정보 성격\n')
for tg in [('M5','M6'),('M9',),('M10',),('I1',)]:
    sub=[x for x in info if x['tag'] in tg]
    if not sub: continue
    P(f"**{' · '.join(tg)}** ({len(sub)}줄)\n"); P('| 정보 종류 | 고정 | 가끔 바뀜 | 그날그날 | 섞임 | 합 |'); P('|---|---|---|---|---|---|')
    cc=collections.Counter((kind(x['정보종류']),x['정보성격'] if x['정보성격'] in('고정','가끔 바뀜','그날그날') else '섞임') for x in sub)
    for k,_ in collections.Counter(kind(x['정보종류']) for x in sub).most_common():
        v=[cc[(k,s)] for s in ('고정','가끔 바뀜','그날그날','섞임')]; P(f"| {k} | "+' | '.join(map(str,v))+f" | {sum(v)} |")
    P('')
P('## 4. 결과 (M5 · M6 · M9)\n'); P('| 태그 | 헛걸음 | 가서 당황 | 따로 확인 | 없음 |'); P('|---|---|---|---|---|')
for t in ('M5','M6','M9'):
    cc=collections.Counter(x['결과'] for x in info if x['tag']==t); P(f"| {t} | {cc['헛걸음']} | {cc['가서 당황']} | {cc['따로 확인']} | {cc['없음']} |")
P('\n## 5. 미리 찾아봤나 (M5 · M6 · M9)\n'); P('| 태그 | 봤는데 틀렸음 | 찾았는데 없음 | 그때그때 달라져서 | 안 찾아봄 | 안 적힘 |'); P('|---|---|---|---|---|---|')
for t in ('M5','M6','M9'):
    cc=collections.Counter(x['미리찾아봤나'] for x in info if x['tag']==t); P(f"| {t} | {cc['봤는데 틀렸음']} | {cc['찾았는데 없음']} | {cc['그때그때 달라져서']} | {cc['안 찾아봄']} | {cc['안 적힘']} |")
P('\n## 6. M10 확인하는 이유\n'); P('| 확인하는 이유 | 줄 수 | 우리가 채울 수 있나 |'); P('|---|---|---|')
cc=collections.Counter(x['확인하는이유'] for x in rows if x['tag']=='M10'); why={'정보가 없어서':'있음 (조사해서 채움)','내 사정에 맞는지':'일부 (결국 가게에 물어야 함)','그날그날 달라서':'어려움 (실시간 정보)','이유 안 적힘':'알 수 없음'}
for k in why: P(f"| {k} | {cc[k]} | {why[k]} |")
P('\n## 7. S1 물어서 찾음 — 누구에게\n')
s1=[x for x in rows if x['tag']=='S1']; post=lambda v: re.sub(r'-\d+-\d+$','',v) if v.startswith('V0_Q') else v
P('| 누구에게 | 줄 수 | 글 수 (V0 질문 글은 조각을 묶어 셈) |'); P('|---|---|---|')
for k,v in collections.Counter(x['누구에게'] for x in s1).most_common(): P(f"| {k} | {v} | {len({post(x['voc_id']) for x in s1 if x['누구에게']==k})} |")
P('\n조건 칸에 적힌 것 (일부): '+' / '.join(sorted({x['조건'] for x in s1 if x['조건']},key=len)[:40]))
P('\n## 8. 리뷰 · 별점을 대하는 태도와 갈아타기\n')
multi=collections.defaultdict(list)
for x in rows: multi[x['voc_id']].append(x['tag'])
pair=collections.Counter(' + '.join(sorted(v)) for v in multi.values() if len(v)>1)
P('두 줄 이상으로 나뉜 글의 태그 조합: '+' · '.join(f'{k} {v}글' for k,v in pair.most_common()))
P('\n## 9. 해당없음의 이유\n'); P('| 이유 | V0 | V1b | V2b | V3 |'); P('|---|---|---|---|---|')
cn=collections.Counter((x['파일'],x['해당없음이유']) for x in rows if x['tag']=='해당없음')
for k in ('앱 기능','맛 · 서비스 평가','식당 아님','내용 없음','기타'): P(f"| {k} | "+' | '.join(str(cn[(n,k)]) for n in files)+' |')
P('\nnote에 인용으로 남긴 글: '+' · '.join(f'{k} {v}' for k,v in collections.Counter(m for x in rows for m in ('별점 보고 싶어 함','원하는 곳 못 찾음','보고 갔다가 실망','식당 이용 · 현장 상황') if m in x['note']).items()))
P('\n## 10. 글쓴이 상황 · 지역 (해당없음 · 검토 뺀 줄)\n')
t=[x for x in rows if x['tag'] not in('해당없음','검토')]
P('글쓴이 상황: '+' · '.join(f'{k} {v}' for k,v in collections.Counter(x['글쓴이_상황'] for x in t).most_common()))
P('\n지역: '+' · '.join(f'{k} {v}' for k,v in collections.Counter(x['지역'] for x in t).most_common()))
open('분석/VOC_18태그_분석.md','w',encoding='utf-8').write('\n'.join(o)+'\n')
print('\n'.join(o))
