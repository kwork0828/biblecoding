import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { db } from '../db/schema';
import { getTodayQueue } from '../db/cards';
import { getSettings } from '../db/seed';
import { schedule } from '../srs/schedule';
import verses from '../data/verses.json';
import type { Card, ReviewQuality, Settings, Verse } from '../types';

const verseById = new Map<string, Verse>((verses as Verse[]).map((v) => [v.id, v]));

const QUALITY_BUTTONS: { q: ReviewQuality; label: string; className: string }[] = [
  { q: 0, label: '다시', className: 'bg-danger' },
  { q: 3, label: '어려움', className: 'bg-warn' },
  { q: 4, label: '보통', className: 'bg-accent' },
  { q: 5, label: '쉬움', className: 'bg-accent-dark' },
];

function nextLabel(card: Card, q: ReviewQuality, steps: number[]): string {
  const next = schedule(card, q, steps);
  if (next.state === 'learning' || next.state === 'lapsed') {
    const minutes = steps[next.learningStep] ?? steps[0];
    return `${minutes}분 후`;
  }
  return `${next.intervalDays}일 후`;
}

export default function ReviewPage() {
  const { deckId } = useParams<{ deckId: string }>();
  const navigate = useNavigate();

  const [settings, setSettings] = useState<Settings | null>(null);
  const [queue, setQueue] = useState<Card[]>([]);
  const [total, setTotal] = useState(0);
  const [index, setIndex] = useState(0);
  const [readTaps, setReadTaps] = useState(0);
  const [history, setHistory] = useState<{ card: Card; index: number }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!deckId) return;
    let cancelled = false;
    (async () => {
      const s = await getSettings();
      const q = await getTodayQueue(deckId, s);
      if (cancelled) return;
      setSettings(s);
      setQueue(q.cards);
      setTotal(q.cards.length);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [deckId]);

  const currentCard = queue[0];
  const currentVerse = currentCard ? verseById.get(currentCard.verseId) : undefined;

  useEffect(() => {
    setReadTaps(0);
  }, [currentCard?.id]);

  const finishReview = useCallback(
    async (q: ReviewQuality) => {
      if (!currentCard || !settings) return;
      const startedAt = currentCard.updatedAt;
      const next = schedule(currentCard, q, settings.learningSteps);

      await db.cards.put(next);
      await db.reviewLogs.add({
        cardId: currentCard.id,
        reviewedAt: Date.now(),
        quality: q,
        mode: 'read',
        elapsedMs: Date.now() - startedAt,
        prevInterval: currentCard.intervalDays,
        nextInterval: next.intervalDays,
      });

      setHistory((h) => [...h, { card: currentCard, index }]);
      setQueue((prev) => prev.slice(1));
      setIndex((i) => i + 1);
    },
    [currentCard, settings, index],
  );

  const undo = useCallback(async () => {
    const last = history[history.length - 1];
    if (!last) return;
    await db.cards.put(last.card);
    const lastLog = await db.reviewLogs.where('cardId').equals(last.card.id).last();
    if (lastLog?.id !== undefined) {
      await db.reviewLogs.delete(lastLog.id);
    }
    setHistory((h) => h.slice(0, -1));
    setQueue((prev) => [last.card, ...prev]);
    setIndex((i) => Math.max(0, i - 1));
  }, [history]);

  const progressPct = total === 0 ? 0 : Math.round((index / total) * 100);

  if (loading) {
    return <div className="flex h-full items-center justify-center text-ink-soft">불러오는 중…</div>;
  }

  if (!currentCard || !currentVerse || !settings) {
    return (
      <div className="mx-auto flex h-full max-w-md flex-col items-center justify-center gap-4 px-8 text-center">
        <div className="text-xl font-bold">오늘 학습을 모두 마쳤어요 🎉</div>
        <div className="text-sm text-ink-soft">내일 또 새로운 말씀으로 만나요.</div>
        <button
          className="mt-2 h-12 rounded-2xl bg-accent px-6 font-bold text-white hover:bg-accent-dark"
          onClick={() => navigate('/')}
        >
          홈으로
        </button>
      </div>
    );
  }

  const ref = `${currentVerse.bookKo} ${currentVerse.chapter}:${currentVerse.verse}`;

  return (
    <div className="mx-auto flex h-full max-w-md flex-col bg-bg">
      <div className="flex items-center gap-3 px-5 pt-5 pb-2">
        <button
          aria-label="홈으로"
          className="text-xl text-ink-soft"
          onClick={() => navigate('/')}
        >
          ✕
        </button>
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-border">
          <div
            className="h-full bg-accent transition-all"
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <div className="text-sm font-semibold text-ink-soft">
          {index} / {total}
        </div>
      </div>

      <div className="flex items-center justify-between px-5 pt-1">
        <div className="rounded-full bg-accent-soft px-2.5 py-1 text-xs font-bold text-accent-dark">
          읽기 모드
        </div>
        <button
          className="flex items-center gap-1 text-sm text-ink-soft disabled:opacity-30"
          disabled={history.length === 0}
          onClick={undo}
        >
          ↩ 되돌리기
        </button>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 py-4">
        <div className="text-sm font-semibold text-ink-soft">{ref}</div>
        <div
          aria-label="구절 본문"
          className="text-center font-serif text-[22px] leading-relaxed"
        >
          {currentVerse.textKo}
        </div>
        <div className="h-px w-14 bg-border" />
        <div className="text-center font-serif text-[15px] leading-relaxed text-ink-soft">
          {currentVerse.textEn}
        </div>

        <button
          className="mt-2 flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm"
          onClick={() => setReadTaps((t) => Math.min(3, t + 1))}
        >
          <span className="text-ink-soft">소리 내어 읽은 횟수</span>
          <span className="flex gap-1">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className={`h-2.5 w-2.5 rounded-full ${i < readTaps ? 'bg-accent' : 'bg-border'}`}
              />
            ))}
          </span>
        </button>
      </div>

      <div className="grid grid-cols-4 gap-2 px-4 pb-6 pt-2">
        {QUALITY_BUTTONS.map(({ q, label, className }) => (
          <button
            key={q}
            className={`flex min-h-[64px] flex-col items-center justify-center gap-0.5 rounded-2xl text-white ${className} hover:brightness-95`}
            onClick={() => finishReview(q)}
          >
            <span className="text-[15px] font-bold">{label}</span>
            <span className="text-[11px] opacity-85">
              {nextLabel(currentCard, q, settings.learningSteps)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
