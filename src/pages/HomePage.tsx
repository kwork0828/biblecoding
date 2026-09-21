import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getTodayQueue } from '../db/cards';
import { getSettings } from '../db/seed';
import { getStreak } from '../db/stats';
import decksJson from '../data/decks.json';
import type { Deck } from '../types';

const builtInDecks = decksJson as Deck[];
const mainDeck = builtInDecks[0];

export default function HomePage() {
  const navigate = useNavigate();
  const [newCount, setNewCount] = useState(0);
  const [reviewCount, setReviewCount] = useState(0);
  const [streak, setStreak] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const settings = await getSettings();
      const [queue, streakDays] = await Promise.all([
        getTodayQueue(mainDeck.id, settings),
        getStreak(),
      ]);
      if (cancelled) return;
      setNewCount(queue.newCount);
      setReviewCount(queue.reviewCount);
      setStreak(streakDays);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const totalToday = newCount + reviewCount;

  return (
    <div className="mx-auto flex h-full max-w-md flex-col bg-bg">
      <div className="flex items-center justify-between px-5 pt-5 pb-2">
        <div className="text-sm text-ink-soft">오늘도 말씀과 함께</div>
        <div className="flex items-center gap-1 rounded-full bg-accent-soft px-3 py-1.5 text-sm font-semibold text-accent-dark">
          🔥 {streak}일 연속
        </div>
      </div>

      <div className="px-5 pt-2">
        <div className="text-2xl font-extrabold leading-snug">
          오늘도 말씀을
          <br />
          마음에 새겨요
        </div>
      </div>

      <div className="flex gap-3 px-5 py-5">
        <div className="flex-1 rounded-2xl border border-border bg-surface p-4">
          <div className="text-xs font-semibold text-ink-soft">새 구절</div>
          <div className="mt-1 text-3xl font-extrabold text-accent">{loading ? '·' : newCount}</div>
        </div>
        <div className="flex-1 rounded-2xl border border-border bg-surface p-4">
          <div className="text-xs font-semibold text-ink-soft">복습할 구절</div>
          <div className="mt-1 text-3xl font-extrabold text-warn">{loading ? '·' : reviewCount}</div>
        </div>
      </div>

      <div className="px-5">
        <button
          className="h-14 w-full rounded-2xl bg-accent text-lg font-bold text-white transition-colors hover:bg-accent-dark disabled:opacity-50"
          disabled={loading || totalToday === 0}
          onClick={() => navigate(`/review/${mainDeck.id}`)}
        >
          {loading
            ? '불러오는 중…'
            : totalToday === 0
              ? '오늘 학습을 모두 마쳤어요'
              : '오늘의 암송 시작'}
        </button>
      </div>

      <div className="px-5 pt-8 pb-2 text-sm font-bold text-ink-soft">진행 중인 묶음</div>
      <div className="flex flex-col gap-2.5 px-5">
        {builtInDecks.map((deck) => (
          <div
            key={deck.id}
            className="flex items-center gap-3 rounded-2xl border border-border bg-surface p-3.5"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-[10px] bg-accent-soft text-lg">
              ✝️
            </div>
            <div className="flex-1">
              <div className="text-[15px] font-bold">{deck.name}</div>
              <div className="text-xs text-ink-soft">{deck.verseIds.length}구절</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
