# 성경 암송 앱 (biblecoding)

> **상태: 1단계 완료 / 전체 4단계 중 진행 중**
> `npm run build` 통과 확인 (2026-09-27)

인터넷 없이 동작하는 성경 암송 웹앱입니다. 한국어(개역한글)와 영어(WEB) 본문을 나란히 보며
간격반복(SM-2) 방식으로 구절을 외웁니다. 계정·서버·외부 네트워크 호출 없이 모든 데이터를 기기(IndexedDB)에 저장합니다.

전체 명세는 [SPEC.md](SPEC.md)에 있습니다.

## 진행 현황

| 단계 | 내용 | 상태 |
|---|---|---|
| 1단계 | 프로젝트 셋업, Dexie 스키마, 요한복음 핵심 구절 24개, 읽기 모드, 4버튼 SM-2 복습 루프 | 완료 |
| 2단계 | 초성 힌트·빈칸 채우기 모드, 언어 전환, 설정 화면 | 미착수 |
| 3단계 | PWA 서비스 워커, 내보내기/불러오기, 단일 HTML 빌드, 비행기 모드 테스트 | 미착수 |
| 4단계 | 통계 화면, 사용자 묶음 편집, 타이핑·오디오 모드, 전체 성경 데이터 | 미착수 |

## 기술 스택

React 18, TypeScript, Vite, Tailwind CSS, Dexie.js(IndexedDB), React Router(HashRouter), Zustand

## 실행 방법

```bash
npm install
npm run dev        # 개발 서버
npm run build      # 타입체크 + 프로덕션 빌드 (dist/)
npm run typecheck  # 타입체크만
```

## 폴더 구조

```text
src/
├─ data/      # verses.json(본문), decks.json(기본 묶음)
├─ db/        # Dexie 스키마, 시드, 카드·통계 조회
├─ srs/       # SM-2 스케줄 계산
├─ pages/     # HomePage, ReviewPage
└─ App.tsx
```

## 참고

- 기본 브랜치가 `claude/bible-memorization-stage-1-3p7b4u`로 되어 있습니다. `main` 브랜치를 만들어 기본 브랜치로 바꾸는 것을 권장합니다.
- 비슷한 주제의 저장소: `bible-memo-assistant`(FastAPI + AI 코칭), `daily-declaration`(앱인토스 묵상 앱)
