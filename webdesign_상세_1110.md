# 🎮 대구 음식점 생존배수 (Retro Arcade Edition)

> **공공데이터 기반 외식업 생존력 분석 대시보드**  
> 90년대 클래식 OS 및 16-bit 픽셀 RPG HUD 감성으로 재해석한 대구시 상권/음식점 생존 분석 플랫폼

---

## 📌 1. 프로젝트 개요 (Overview)

- **서비스명**: 대구 음식점 생존배수 v1.0 [SURVIVAL FACTOR]
- **데이터 소스**: 행정안전부 일반음식점 인허가 데이터 (data.go.kr 15154916)
- **분석 대상**: 대구광역시 소재 일반음식점 약 97,575곳 (영업 29,277곳 / 폐업 68,298곳)
- **핵심 목표**: 사용자가 관심 있는 가게와 k개 주변 폐업 점포의 영업 기간을 비교하여, 해당 점포가 동종 업계 대비 얼마나 오래 버텨왔는지를 직관적인 게이지와 레트로 RPG 배틀 스탯으로 시각화.

---

## 📐 2. 핵심 알고리즘 (Survival Factor Formula)

$$\text{생존배수 (Survival Factor)} = \frac{\text{선택 점포 영업 기간 (연)}}{\text{가장 인접한 동종 폐업 점포 } k \text{곳의 평균 영업 기간 (연)}}$$

- **거리 계산 기준**: 국가 표준 정밀 지오코딩 좌표계 `EPSG:5174` (단위: 미터)
- **파라미터 ($k$)**: 기본값 $k=20$, 초인접($k=5$), 상권 단위($k=50$), 광역 단위($k=100$)로 가변 설정 가능
- **비교 카테고리 필터**:
  1. 같은 메뉴 (상호명 형태소 분석/추정)
  2. 같은 업태 (행정 인허가 표준 분류)
  3. 모든 음식점 (전체 요식업 통합)
  4. 동일 구·군 행정구역 한정 옵션

---

## 🎨 3. 디자인 시스템 (Retro Arcade & Windows 95 HUD)

### 3.1 비주얼 콘셉트
- **레트로 OS 윈도우 UI**: 90년대 GUI 특유의 엠보싱 3D 베벨 테두리, 클래식 윈도우 타이틀바, 인셋/아웃셋 패널 질감.
- **16-bit 픽셀 RPG 테마**: 도트 그래픽 캐릭터(달구벌 거북 수호자 Lv.99), 경험치(EXP) 및 퀘스트(QUEST 01), 장비 등급 시스템(무딘 강철 검 등).

### 3.2 컬러 팔레트 (Color Palette)
| 구분 | 토큰명 | HEX 코드 | 용도 |
| :--- | :--- | :--- | :--- |
| **Primary** | Arcade Teal | `#008080` | 시스템 윈도우 타이틀바, 주요 액센트, 버튼 |
| **Surface** | Retro Slate Gray | `#F4F3F3` / `#EBE9E9` | 메인 캔버스 및 윈도우 바디 배경 |
| **Panel Dark**| Terminal Black | `#0F2027` / `#162A32` | 배틀 스탯 HUD, 레이더 헤더, 콘솔 영역 |
| **Success/EXP**| Pixel Emerald | `#10B981` / `#00FFCC` | 생존 게이지, 영업 중 상태 표시, 레벨 바 |
| **Danger/Closed**| Pixel Coral Red | `#E11D48` / `#EF4444` | 폐업 점포 마커, 경고 태그, 위험 지표 |
| **Accent Gold**| High Score Gold | `#F59E0B` | 명예의 전당 TOP 100, 퀘스트 배지, 하이라이트 |

### 3.3 타이포그래피 (Typography)
- **Primary Display / Monospace**: `Space Grotesk`, `Press Start 2P`, `DungGeunMo` (레트로 둥근모 스타일)
- **Body & Data**: `Pretendard`, `Noto Sans KR` (수치 데이터 및 표 가독성 최적화)

---

## 🖥️ 4. 주요 화면 구성 및 기능 모듈

### 4.1 상단 글로벌 윈도우 헤더 (System Chrome)
- 클래식 윈도우 컨트롤러 (`[ _ ]` `[ □ ]` `[ X ]`)
- 마스코트 도트 아이콘 및 시스템 가동 상태 (`SYS: EPSG:5174 | READY / DATA ONLINE`)
- 글로벌 내비게이션 탭: `생존배수 대시보드`, `TOP 100 랭킹`, `서바이벌 지도`, `데이터 업로드`

### 4.2 좌측 컨트롤 독 (System Control Dock)
1. **SURVIVAL EXP BAR**: 현재 선택된 상권(예: 북구) 생존율 및 레벨 시각화
2. **DISTRICT TELEMETRY**: 수성구, 중구, 달서구 등 주요 구별 실시간 생존배수 텔레메트리
3. **DATA ENGINE**: 공공데이터 최신 CSV/JSON 파일 드래그 앤 드롭 업로드 지원
4. **RESTAURANT PICKER**: 실시간 29,277개 영업 점포 검색 및 선택 리스트
5. **ALGORITHM PARAMETERS**: $k$값 슬라이더 및 비교 조건 체크박스
6. **TOP 100 HIGH SCORE**: 대구 전체 및 구·군별 생존배수 명예의 전당 리더보드

### 4.3 메인 콘텐츠 영역 (Main Interactive Viewport)
1. **QUEST 01: TARGET SELECTION**
   - 가게명 / 동네 검색창, 빠른 순간이동 칩(`동성로`, `범어동`, `상인동`, `국밥대령`)
   - **달구벌 거북 수호자 (Lv.99)** NPC 튜토리얼 말풍선
2. **BATTLE STATS: 생존 점수 Telemetry**
   - 선택 점포 카드 (예: **우기 생고기** / 대구 상위 62% / '무딘 강철 검' 아이템 등급)
   - 생존 수명 게이지 바: [점포 영업 기간 10.0년] vs [주변 폐업 20곳 평균 8.8년]
   - 요약 수치 카드: 폐업 기간 중앙값(5.0년), 최단~최장(0.1~36.3년), 탐색 반경(287m), 동일 메뉴 후보군(5,990곳)
3. **SURVIVAL RADAR: DAUGU DOWNTOWN GIS**
   - 레트로 스코프 스타일의 인근 287m 반경 맵뷰어
   - 범례: 본 점포(청록 핀), 비교 폐업 점포(인접 순 번호 마커), 영업/폐업 점포 도트 마커
4. **폐업 점포 분석 레지스터 (Combat Log)**
   - 인접 순 1위~20위 점포의 상호명, 업태, 거리, 실제 영업 기간, 개업/폐업일 상세 테이블

---

## 🛠️ 5. 기술 스택 (Tech Stack Reference)

- **Frontend**: HTML5, Modern CSS (TailwindCSS Engine & Custom 95-Bevel CSS Utility), Vanilla JavaScript
- **Vector & Asset Engine**: SVG 기반 레트로 도트 스프라이트 & 아이콘
- **Data Protocol**: GeoJSON, CSV Data Engine (EPSG:5174 미터 좌표계 연동)
- **Deployment**: Vercel Serverless Hosting

---

## 👥 6. 크레딧 (Credits)
- **데이터서비스 4조 (4P)**: 손효민 · 이재훈 · 이찬영 · 이건협
- **기반 데이터**: 공공데이터포털 행정안전부 일반음식점 데이터
