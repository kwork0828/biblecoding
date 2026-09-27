# research.md — 성경암송 앱 제작 기록 조사 (STEP 1)

조사일: 2026-09-27 / 대상: kwork0828/biblecoding (브랜치 claude/bible-memorization-stage-1-3p7b4u 와 동일 히스토리)

## 0. 먼저 알아둘 사실 (확인됨)

- 이 저장소에는 **앱인토스(Apps in Toss) 관련 파일이 하나도 없다.** `granite.config*` 없음, `@apps-in-toss/*` 의존성 없음, 코드·문서 어디에도 "toss/granite/앱인토스" 문자열 없음.
- SPEC.md의 배포 목표는 **GitHub Pages PWA + 단일 HTML 파일**이다.
- 사용자가 "biblecoding이 그 앱이 맞다"고 확인(2026-09-27)했으므로 이 저장소를 기준으로 진행한다.
  앱인토스 등록·배포 과정은 기록이 없어 전부 **[확인 필요]**.
- 문서 파일은 `SPEC.md` 하나뿐이다. prd/task/시나리오/CLAUDE.md/AGENTS.md/WORKLOG는 **없음**.
- 앱 화면 캡처 이미지(png/jpg)는 **없음**.

## 1. 기술 스택 (package.json · 설정 파일 기준, 확인됨)

| 구분 | 내용 |
|---|---|
| 빌드 | Vite 5 + TypeScript 5 (`npm run dev / build / preview / typecheck`) |
| UI | React 18, react-router-dom 6 (HashRouter), Tailwind CSS 3 |
| 저장 | Dexie 4 (IndexedDB 래퍼), dexie-react-hooks |
| 상태 | zustand (의존성만 있음, 1단계 코드에선 미사용) |
| 배포 설정 | `vite.config.ts`의 `base: process.env.VITE_BASE_PATH ?? '/'` (GitHub Pages 서브경로 대응) |
| 미구현 | vite-plugin-pwa(서비스 워커), vite-plugin-singlefile — SPEC에는 있으나 package.json에 없음 |

## 2. 시간순 작업 흐름 (git log --reverse --stat)

| 순서 | 날짜(UTC) | 커밋 | 내용 |
|---|---|---|---|
| 1 | 2026-09-21 20:30 | 56e1ea7 | `SPEC.md`(160줄) + `src/data/verses.json`(요한복음 24구절, 개역한글/WEB) |
| 2 | 2026-09-21 20:39 | 42e18b8 | 1단계: Vite 뼈대, Dexie 스키마, 읽기 모드 + SM-2 복습 루프 (21개 파일, +3,579줄) |

- 두 커밋 모두 작성자는 Claude(Claude Code 세션), 간격은 약 9분.
- 커밋 2 메시지에 "Playwright로 끝까지 검증: 세션 완료 후 새로고침해도 진도 유지, 홈 화면 카운트/연속일 갱신 확인"이라고 적혀 있다.
- SPEC의 구현 순서(1~4단계) 중 **1단계만 완료**. 2단계(초성/빈칸/언어 전환/설정), 3단계(PWA·내보내기·단일 HTML), 4단계(통계·타이핑·오디오)는 미완료.

## 3. 1단계에서 만들어진 것 (확인됨)

| 파일 | 역할 |
|---|---|
| `SPEC.md` | 12개 절: 개요, 스택, 데이터 모델, SM-2 알고리즘, 5가지 암송 모드, 화면, 오프라인/배포, 저작권, 접근성, 프라이버시, 구현 순서, 인수 조건 |
| `src/data/verses.json` | 요한복음 24구절 (id, bookKo, chapter, verse, textKo, textEn) |
| `src/data/decks.json` | 기본 묶음 1개 "요한복음 핵심 구절" (24구절) |
| `src/db/schema.ts` | Dexie DB `bible-memorization`: decks / cards / reviewLogs / settings |
| `src/db/seed.ts` | 기본 설정(하루 새 카드 5, 복습 50, 학습 단계 [1,10]분) + 기본 묶음 투입 |
| `src/db/cards.ts` | 카드 생성, 새벽 4시 경계, 오늘의 학습 큐 계산 |
| `src/srs/schedule.ts` | SM-2 스케줄러 (다시0/어려움3/보통4/쉬움5), 최대 365일 |
| `src/pages/HomePage.tsx` | 오늘 새 구절 수, 복습 수, 연속일, "오늘의 암송 시작" 버튼 |
| `src/pages/ReviewPage.tsx` | 한/영 본문, 읽기 탭 카운터, 4버튼 평가 + 다음 간격 표시, 되돌리기 |

## 4. 실제로 쓴 프롬프트·명령어

- **사용자가 Claude Code에 입력한 프롬프트 원문: 기록 없음 → [확인 필요]**
  (단서: SPEC.md 자체가 "명세서를 먼저 쓰고 단계별로 구현" 방식. 첫 프롬프트가 SPEC.md를 붙여넣은 것인지는 [확인 필요])
- 저장소에서 확인되는 명령어:
  - `npm install` (package-lock.json 존재로 추정되는 설치 단계)
  - `npm run dev` / `npm run build` / `npm run typecheck` (package.json scripts)
  - 배포 시 `VITE_BASE_PATH=/biblecoding/ npm run build` 형태 (vite.config.ts 근거, 실제 실행 여부는 [확인 필요])

## 5. 막혔던 문제와 해결법 (코드 주석에 남은 것만)

| 문제 | 해결 | 근거 |
|---|---|---|
| 밤늦게 복습하면 날짜가 바뀌어 오늘 분량을 두 번 받음 | 하루 경계를 자정이 아닌 **새벽 4시**로 | `schedule.ts`, `cards.ts` 주석, SPEC 4절 |
| React StrictMode에서 effect가 두 번 실행돼 카드 중복 생성 충돌 | `bulkAdd` 대신 **`bulkPut`** 사용 | `cards.ts` 주석 |
| GitHub Pages 서브경로 / file:// 에서 라우팅 깨짐 | BrowserRouter 대신 **HashRouter** | SPEC 2절 |
| 저작권 | 개역한글(2011년 말 만료)·WEB(퍼블릭 도메인)만 사용 | SPEC 8절 |

그 외 실제 오류 로그·디버깅 과정: **[확인 필요]** (커밋 전 과정은 기록에 없음)

## 6. 비밀정보 점검

- `src/` 전체에서 API 키·토큰·비밀번호·이메일 패턴 검색 결과 **없음**. `.env` 파일 없음.
- git 커밋 작성자 이메일은 `noreply@anthropic.com`(공개 noreply). 화면에 git log를 보일 때는 그래도 ****로 가린다.

## 7. [확인 필요] 목록

1. 앱인토스 등록·심사·배포를 실제로 했는지, 했다면 어느 저장소/폴더에서 했는지
2. Claude Code에 입력한 첫 프롬프트 원문 (SPEC.md를 직접 썼는지, AI로 생성했는지)
3. GitHub Pages 배포 여부와 URL
4. 개발 중 실제로 겪은 오류 (커밋에는 결과만 남음)
5. 앱 실행 화면 캡처 (저장소에 이미지 없음)
6. 2단계 이후 작업이 다른 곳에 있는지
