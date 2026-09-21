# 성경 암송 앱 명세서 (Offline-First PWA)

## 1. 제품 개요
인터넷 없이 완전히 동작하는 성경 암송 웹앱이다. 한국어와 영어 본문을 나란히 보며 간격반복(spaced repetition)으로 구절을 암송한다. 계정, 서버, 외부 네트워크 호출이 일절 없고 모든 데이터는 기기 내부에만 저장된다. 최초 1회 접속 후에는 비행기 모드에서도 모든 기능이 정상 작동해야 한다. 주 사용자는 개인 묵상자와 국내 교회 소그룹이며, 저사양 안드로이드 기기와 구형 브라우저에서도 끊김 없이 돌아가는 것을 성능 목표로 삼는다.

## 2. 기술 스택
React 18 + TypeScript + Vite로 구성하고, 스타일은 Tailwind CSS를 사용한다. 로컬 저장은 Dexie.js(IndexedDB 래퍼)를 쓰고, 서비스 워커는 `vite-plugin-pwa`(Workbox 기반)로 생성한다. 라우팅은 `react-router-dom`의 HashRouter를 사용한다. GitHub Pages 서브경로 배포와 `file://` 직접 실행을 동시에 지원해야 하므로 BrowserRouter는 쓰지 않는다. 상태 관리는 Zustand 정도로 가볍게 유지하고, 외부 폰트·CDN·분석 스크립트·광고 SDK는 어떤 형태로도 포함하지 않는다. 빌드 산출물 전체 용량은 오디오를 제외하고 2MB 이하를 목표로 한다.

## 3. 데이터 모델
Dexie 스키마는 다음 인터페이스를 기준으로 작성한다.

```ts
// 성경 본문 (읽기 전용, 빌드 시 JSON으로 번들)
interface Verse {
  id: string;          // "john-3-16"
  book: string;        // "john"
  bookKo: string;      // "요한복음"
  chapter: number;
  verse: number;
  textKo: string;      // 개역한글 (퍼블릭 도메인)
  textEn: string;      // WEB 또는 ASV (퍼블릭 도메인)
}

// 암송 묶음
interface Deck {
  id: string;
  name: string;        // "구원의 확신 30구절"
  description: string;
  isBuiltIn: boolean;  // 기본 제공 여부
  verseIds: string[];
  createdAt: number;
}

// 암송 카드 (SM-2 학습 상태)
interface Card {
  id: string;          // deckId + verseId
  deckId: string;
  verseId: string;
  lang: 'ko' | 'en' | 'both';
  state: 'new' | 'learning' | 'review' | 'lapsed';
  ease: number;        // EF, 기본 2.5, 최소 1.3
  intervalDays: number;
  repetitions: number;
  learningStep: number;// learning 단계 인덱스
  dueAt: number;       // epoch ms
  lapses: number;
  createdAt: number;
  updatedAt: number;
}

// 복습 로그 (통계·되돌리기용)
interface ReviewLog {
  id?: number;
  cardId: string;
  reviewedAt: number;
  quality: 0 | 3 | 4 | 5;
  mode: 'read' | 'initial' | 'cloze' | 'type' | 'audio';
  elapsedMs: number;
  prevInterval: number;
  nextInterval: number;
}

interface Settings {
  id: 'singleton';
  displayLang: 'ko' | 'en' | 'both';
  dailyNewLimit: number;     // 기본 5
  dailyReviewLimit: number;  // 기본 50
  fontScale: number;         // 0.8 ~ 2.0
  theme: 'light' | 'dark' | 'sepia';
  audioEnabled: boolean;
  learningSteps: number[];   // 분 단위, 기본 [1, 10]
}
```

## 4. 간격반복 알고리즘
SM-2를 4버튼 평가로 단순화해 구현한다. 사용자는 "다시(0) / 어려움(3) / 보통(4) / 쉬움(5)"을 누른다.

```ts
function schedule(card: Card, q: 0|3|4|5, steps: number[]): Card {
  const next = { ...card, updatedAt: Date.now() };
  if (q === 0) {
    next.state = card.state === 'new' ? 'learning' : 'lapsed';
    next.learningStep = 0;
    next.repetitions = 0;
    next.lapses += 1;
    next.ease = Math.max(1.3, card.ease - 0.2);
    next.intervalDays = 0;
    next.dueAt = Date.now() + steps[0] * 60_000;
    return next;
  }
  // EF 갱신 (SM-2 원식)
  next.ease = Math.max(1.3, card.ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)));

  if (next.state === 'new' || next.state === 'learning' || next.state === 'lapsed') {
    const step = card.learningStep + 1;
    if (step < steps.length) {
      next.state = 'learning';
      next.learningStep = step;
      next.dueAt = Date.now() + steps[step] * 60_000;
      return next;
    }
    next.state = 'review';
    next.repetitions = 1;
    next.intervalDays = q === 5 ? 4 : 1;
  } else {
    next.repetitions = card.repetitions + 1;
    const base = card.intervalDays * next.ease;
    next.intervalDays = Math.round(
      q === 3 ? Math.max(card.intervalDays + 1, card.intervalDays * 1.2) : base
    );
  }
  next.intervalDays = Math.min(next.intervalDays, 365);
  next.dueAt = Date.now() + next.intervalDays * 86_400_000;
  return next;
}
```

하루 단위 경계는 사용자 로컬 자정 기준이 아니라 "새벽 4시 롤오버"로 처리한다. 밤늦게 복습하는 사용자가 날짜가 바뀌었다는 이유로 오늘 분량을 두 번 받지 않게 하기 위함이다.

## 5. 암송 모드 (5단계)
하나의 카드를 다섯 가지 방식으로 연습할 수 있어야 하고, 사용자가 모드를 고정하거나 "난이도 자동 상승"을 켤 수 있다. 자동 상승은 같은 카드에서 연속 2회 "보통" 이상을 받으면 다음 모드로 올라가는 방식이다.

읽기(read) 단계는 전문을 그대로 보여주고 소리 내어 3회 읽도록 안내한다. 화면에는 읽은 횟수를 세는 탭 카운터를 둔다.

초성 힌트(initial) 단계는 각 어절의 첫 글자만 남긴다. 한국어는 유니코드 한글 음절을 분해해 초성만 노출한다. `(code - 0xAC00) / 588`로 초성 인덱스를 구해 `ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ` 배열에서 뽑아 쓴다. 예를 들어 "하나님이 세상을 이처럼 사랑하사"는 "ㅎㄴㄴㅇ ㅅㅅㅇ ㅇㅊㄹ ㅅㄹㅎㅅ"로 표시된다. 영어는 각 단어의 첫 글자와 나머지 길이를 점으로 표기한다("F.. G.. s. l.... t.. w....").

빈칸 채우기(cloze) 단계는 어절 단위로 일정 비율(기본 30%, 사용자가 20~70% 조절)을 가려 탭하면 정답이 드러나게 한다. 가릴 어절은 카드 id를 시드로 한 결정적 난수로 선택해, 같은 카드를 다시 열었을 때 같은 자리가 나오도록 한다. 조사만 남은 어절이나 한 글자 어절은 가리지 않는다.

타이핑(type) 단계는 전문을 직접 입력받고 정답과 비교한다. 채점은 공백과 문장부호를 정규화한 뒤 어절 단위로 비교하고, 틀린 어절을 빨갛게, 맞은 어절을 회색으로 표시한다. 오타 관용을 위해 어절 간 Levenshtein 거리가 1 이하면 "근접"으로 처리해 노란색으로 표기하되 정답으로는 인정하지 않는다. 모바일 입력 부담을 고려해 이 모드는 기본 비활성으로 두고 설정에서 켜게 한다.

듣기(audio) 단계는 미리 생성된 MP3를 재생하며 본문을 가린 상태로 따라 말하게 한다. 브라우저 TTS는 오프라인에서 음성 데이터가 없는 기기가 많아 신뢰할 수 없으므로 주 경로로 쓰지 않는다. `public/audio/{verseId}.mp3`가 존재하면 이 모드를 노출하고, 없으면 메뉴에서 감춘다. 오디오는 별도 다운로드 팩으로 분리해 기본 번들 용량을 지킨다.

## 6. 화면 구성
홈 화면은 오늘 할 새 카드 수와 복습 카드 수, 연속 학습 일수, 그리고 "오늘의 암송 시작" 버튼 하나로 단순하게 구성한다. 복습 세션 화면은 상단에 진행도 바, 중앙에 구절, 하단에 4버튼 평가를 두고, 각 버튼에는 다음 복습이 언제인지(예: "3일 후")를 작게 표시한다. 직전 평가를 되돌리는 버튼도 둔다. 구절 화면에서는 좌우 스와이프로 한국어·영어·병기 표시를 전환할 수 있어야 한다.

묶음 관리 화면에서는 기본 제공 묶음을 담고, 사용자가 직접 구절을 검색해 자기 묶음을 만들 수 있게 한다. 기본 제공 묶음은 초신자용 복음서 30구절, 구원의 확신, 시편 위로 구절, 주기도문과 십계명, 영한 병기 핵심 50구절 정도로 구성하고, 각 구절마다 한두 문장의 짧은 배경 설명과 암송 팁 필드를 둔다.

통계 화면은 최근 30일 복습 히트맵, 암송 완료(interval 21일 이상) 구절 수, 취약 구절 상위 10개를 보여준다. 설정 화면에는 표시 언어, 일일 한도, 글자 크기, 테마, 데이터 내보내기·불러오기·초기화를 배치한다.

## 7. 오프라인 및 배포 요건
서비스 워커는 앱 셸과 성경 JSON 전체를 precache 하고, 런타임 fetch 전략은 cache-first로 둔다. 네트워크 요청이 실패해도 어떤 화면에서도 에러나 빈 화면이 나오지 않아야 한다. `navigator.onLine` 값에 따라 기능을 분기하는 코드는 넣지 않는다. 항상 오프라인인 것처럼 동작하는 것이 기본값이다.

빌드는 두 가지 산출물을 만든다. 하나는 GitHub Pages용 표준 PWA 빌드(`base` 옵션을 환경변수로 주입)이고, 다른 하나는 `vite-plugin-singlefile`을 이용한 단일 HTML 산출물이다. 단일 HTML은 JS·CSS·본문 JSON·폰트를 모두 인라인해 파일 하나만으로 브라우저에서 열 수 있어야 한다. 이때 서비스 워커와 IndexedDB가 `file://`에서 제한될 수 있으므로, IndexedDB 사용 불가 시 localStorage로 자동 폴백하는 저장 계층 추상화를 넣는다.

데이터 내보내기는 카드 진도와 사용자 묶음을 담은 단일 JSON 파일 다운로드로 구현하고, 불러오기는 같은 스키마를 검증 후 병합한다. 기기 교체나 브라우저 데이터 삭제에 대비한 유일한 백업 수단이므로 이 기능은 필수다.

## 8. 저작권 처리
한국어 본문은 개역한글판만 사용한다. 이 번역의 저작권은 2011년 말로 만료되어 자유롭게 쓸 수 있다. 개역개정판, 새번역, 쉬운성경 등은 대한성서공회의 저작권 대상이므로 저장소나 번들에 절대 포함하지 않는다. 영어는 World English Bible(WEB) 또는 American Standard Version(ASV)을 쓴다. 본문 JSON 파일 헤더와 앱 내 "정보" 화면에 사용 번역본과 퍼블릭 도메인 근거를 명시한다. 추후 다른 번역본을 추가할 수 있도록 번역본 식별자를 데이터 구조에 넣되, 기본 배포본에는 퍼블릭 도메인만 담는다.

## 9. 접근성과 성능
글자 크기는 설정에서 80%부터 200%까지 조절되고, 본문 폰트는 시스템 폰트 스택을 사용해 웹폰트 다운로드를 피한다. 색상 대비는 WCAG AA를 충족하고, 모든 인터랙티브 요소의 터치 영역은 최소 44×44px로 둔다. 화면 낭독기 사용자를 위해 구절 텍스트에 적절한 aria-label을 붙이고, 빈칸 채우기 모드에서는 가려진 부분을 "가려진 단어"로 읽어준다. 성능 기준은 저사양 기기에서 초기 로드 3초 이내, 카드 전환 100ms 이내다.

## 10. 프라이버시
계정, 로그인, 서버 동기화, 분석, 오류 리포팅, 푸시 알림을 모두 넣지 않는다. 앱은 어떤 상황에서도 외부로 네트워크 요청을 보내지 않아야 하며, 이를 CI에서 검증할 수 있도록 빌드 산출물에 외부 도메인 문자열이 없는지 확인하는 스크립트를 포함한다. "정보" 화면에 데이터가 기기 밖으로 나가지 않는다는 점을 한 문장으로 명시한다.

## 11. 구현 순서
1단계는 프로젝트 셋업과 Dexie 스키마, 개역한글 + WEB 요한복음 데이터 투입, 기본 제공 묶음 하나로 읽기 모드와 4버튼 SM-2 복습 루프를 완성하는 것까지다. 2단계에서 초성 힌트와 빈칸 채우기 모드, 언어 전환, 설정 화면을 붙인다. 3단계에서 PWA 서비스 워커, 내보내기·불러오기, 단일 HTML 빌드를 완성하고 비행기 모드 테스트를 통과시킨다. 4단계에서 통계 화면, 사용자 묶음 편집, 타이핑 모드, 오디오 모드, 전체 성경 데이터 확장을 진행한다. 각 단계 끝에서 반드시 동작하는 상태를 유지하고, 다음 단계로 넘어가기 전에 커밋을 분리한다.

## 12. 인수 조건
와이파이와 데이터를 모두 끈 상태에서 앱을 새로 열어 복습 세션을 끝까지 완주할 수 있어야 한다. 브라우저를 완전히 종료한 뒤 재실행했을 때 진도가 그대로 남아 있어야 한다. 내보낸 JSON을 다른 브라우저에서 불러왔을 때 카드 상태가 동일하게 복원되어야 한다. 단일 HTML 파일을 데스크톱에서 더블클릭해 열었을 때 모든 모드가 동작해야 한다. DevTools 네트워크 탭에서 최초 로드 이후 외부 요청이 0건이어야 한다. 크롬 Lighthouse PWA 점수와 접근성 점수가 각각 90점 이상이어야 한다.
