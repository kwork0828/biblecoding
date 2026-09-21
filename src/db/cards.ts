import type { Card, Deck, Settings } from '../types';
import { db } from './schema';

function newCard(deckId: string, verseId: string, lang: Card['lang']): Card {
  const now = Date.now();
  return {
    id: `${deckId}__${verseId}`,
    deckId,
    verseId,
    lang,
    state: 'new',
    ease: 2.5,
    intervalDays: 0,
    repetitions: 0,
    learningStep: 0,
    dueAt: now,
    lapses: 0,
    createdAt: now,
    updatedAt: now,
  };
}

export async function ensureCardsForDeck(deck: Deck, settings: Settings): Promise<void> {
  const existing = await db.cards.where('deckId').equals(deck.id).toArray();
  const existingVerseIds = new Set(existing.map((c) => c.verseId));
  const missing = deck.verseIds.filter((vid) => !existingVerseIds.has(vid));
  if (missing.length === 0) return;
  const toAdd = missing.map((vid) => newCard(deck.id, vid, settings.displayLang));
  // bulkPut (아닌 bulkAdd)을 사용해, 동시 호출(예: React StrictMode의 effect 이중 실행)로
  // 같은 카드가 두 번 생성되려 할 때도 충돌 없이 덮어쓰도록 한다.
  await db.cards.bulkPut(toAdd);
}

/** 새벽 4시를 하루 경계로 삼는, 지금 시각이 속한 "오늘"의 시작 epoch ms. */
export function rolloverBoundary(nowMs: number = Date.now()): number {
  const d = new Date(nowMs);
  const hour = d.getHours();
  const boundary = new Date(d);
  boundary.setHours(4, 0, 0, 0);
  if (hour < 4) {
    boundary.setDate(boundary.getDate() - 1);
  }
  return boundary.getTime();
}

export interface TodayQueue {
  cards: Card[];
  newCount: number;
  reviewCount: number;
}

export async function getTodayQueue(deckId: string, settings: Settings): Promise<TodayQueue> {
  const now = Date.now();
  const boundary = rolloverBoundary(now);

  const deck = await db.decks.get(deckId);
  if (!deck) return { cards: [], newCount: 0, reviewCount: 0 };
  await ensureCardsForDeck(deck, settings);

  const allCards = await db.cards.where('deckId').equals(deckId).toArray();
  const logsToday = await db.reviewLogs.where('reviewedAt').aboveOrEqual(boundary).toArray();

  const todayCountByCard = new Map<string, number>();
  for (const log of logsToday) {
    todayCountByCard.set(log.cardId, (todayCountByCard.get(log.cardId) ?? 0) + 1);
  }

  let newIntroducedToday = 0;
  for (const [cardId, countToday] of todayCountByCard) {
    const totalCount = await db.reviewLogs.where('cardId').equals(cardId).count();
    if (totalCount === countToday) newIntroducedToday += 1;
  }
  const reviewsDoneToday = Math.max(0, logsToday.length - newIntroducedToday);

  const dueNonNew = allCards
    .filter((c) => c.state !== 'new' && c.dueAt <= now)
    .sort((a, b) => a.dueAt - b.dueAt);
  const learningDue = dueNonNew.filter((c) => c.state === 'learning' || c.state === 'lapsed');
  const reviewDue = dueNonNew.filter((c) => c.state === 'review');

  const reviewBudget = Math.max(0, settings.dailyReviewLimit - reviewsDoneToday);
  const reviewDueCapped = reviewDue.slice(0, reviewBudget);

  const newBudget = Math.max(0, settings.dailyNewLimit - newIntroducedToday);
  const newCards = allCards.filter((c) => c.state === 'new').slice(0, newBudget);

  const cards = [...learningDue, ...reviewDueCapped, ...newCards];

  return {
    cards,
    newCount: newCards.length,
    reviewCount: learningDue.length + reviewDueCapped.length,
  };
}
