export interface Verse {
  id: string; // "john-3-16"
  book: string; // "john"
  bookKo: string; // "요한복음"
  chapter: number;
  verse: number;
  textKo: string; // 개역한글 (퍼블릭 도메인)
  textEn: string; // WEB (퍼블릭 도메인)
}

export interface Deck {
  id: string;
  name: string;
  description: string;
  isBuiltIn: boolean;
  verseIds: string[];
  createdAt: number;
}

export type CardLang = 'ko' | 'en' | 'both';
export type CardState = 'new' | 'learning' | 'review' | 'lapsed';

export interface Card {
  id: string; // deckId + verseId
  deckId: string;
  verseId: string;
  lang: CardLang;
  state: CardState;
  ease: number; // EF, 기본 2.5, 최소 1.3
  intervalDays: number;
  repetitions: number;
  learningStep: number;
  dueAt: number; // epoch ms
  lapses: number;
  createdAt: number;
  updatedAt: number;
}

export type ReviewQuality = 0 | 3 | 4 | 5;
export type ReviewMode = 'read' | 'initial' | 'cloze' | 'type' | 'audio';

export interface ReviewLog {
  id?: number;
  cardId: string;
  reviewedAt: number;
  quality: ReviewQuality;
  mode: ReviewMode;
  elapsedMs: number;
  prevInterval: number;
  nextInterval: number;
}

export type DisplayLang = 'ko' | 'en' | 'both';
export type Theme = 'light' | 'dark' | 'sepia';

export interface Settings {
  id: 'singleton';
  displayLang: DisplayLang;
  dailyNewLimit: number; // 기본 5
  dailyReviewLimit: number; // 기본 50
  fontScale: number; // 0.8 ~ 2.0
  theme: Theme;
  audioEnabled: boolean;
  learningSteps: number[]; // 분 단위, 기본 [1, 10]
}
