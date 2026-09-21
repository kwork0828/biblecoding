import decksJson from '../data/decks.json';
import type { Deck, Settings } from '../types';
import { db } from './schema';

const defaultSettings: Settings = {
  id: 'singleton',
  displayLang: 'both',
  dailyNewLimit: 5,
  dailyReviewLimit: 50,
  fontScale: 1,
  theme: 'light',
  audioEnabled: false,
  learningSteps: [1, 10],
};

export async function ensureSeeded(): Promise<void> {
  await db.transaction('rw', db.decks, db.settings, async () => {
    const existingSettings = await db.settings.get('singleton');
    if (!existingSettings) {
      await db.settings.put(defaultSettings);
    }

    const builtInDecks = decksJson as Deck[];
    for (const deck of builtInDecks) {
      const existing = await db.decks.get(deck.id);
      if (!existing) {
        await db.decks.put(deck);
      }
    }
  });
}

export async function getSettings(): Promise<Settings> {
  const s = await db.settings.get('singleton');
  return s ?? defaultSettings;
}
