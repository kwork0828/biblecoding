import Dexie, { type Table } from 'dexie';
import type { Card, Deck, ReviewLog, Settings } from '../types';

export class AppDatabase extends Dexie {
  decks!: Table<Deck, string>;
  cards!: Table<Card, string>;
  reviewLogs!: Table<ReviewLog, number>;
  settings!: Table<Settings, string>;

  constructor() {
    super('bible-memorization');
    this.version(1).stores({
      decks: 'id, isBuiltIn',
      cards: 'id, deckId, verseId, state, dueAt',
      reviewLogs: '++id, cardId, reviewedAt',
      settings: 'id',
    });
  }
}

export const db = new AppDatabase();
