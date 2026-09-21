import type { Card, ReviewQuality } from '../types';

export function schedule(card: Card, q: ReviewQuality, steps: number[]): Card {
  const next: Card = { ...card, updatedAt: Date.now() };

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
      q === 3 ? Math.max(card.intervalDays + 1, card.intervalDays * 1.2) : base,
    );
  }

  next.intervalDays = Math.min(next.intervalDays, 365);
  next.dueAt = Date.now() + next.intervalDays * 86_400_000;
  return next;
}

/**
 * 새벽 4시를 하루의 경계로 삼는다. 자정 이후~오전 4시 사이의 복습은
 * "전날"로 취급해, 밤늦게 학습한 사용자가 오늘 분량을 두 번 받지 않게 한다.
 */
export function dayKeyWith4amRollover(epochMs: number): string {
  const d = new Date(epochMs);
  d.setHours(d.getHours() - 4);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function todayKey(): string {
  return dayKeyWith4amRollover(Date.now());
}
