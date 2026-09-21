import { dayKeyWith4amRollover } from '../srs/schedule';
import { db } from './schema';

/** 새벽 4시 롤오버 기준으로, 오늘 또는 어제까지 이어진 연속 학습일수. */
export async function getStreak(): Promise<number> {
  const logs = await db.reviewLogs.toArray();
  if (logs.length === 0) return 0;

  const dayKeys = new Set(logs.map((l) => dayKeyWith4amRollover(l.reviewedAt)));

  let cursorMs = Date.now();
  const todayKey = dayKeyWith4amRollover(cursorMs);
  if (!dayKeys.has(todayKey)) {
    // 오늘 아직 학습하지 않았다면 어제부터 역산한다.
    cursorMs -= 86_400_000;
    if (!dayKeys.has(dayKeyWith4amRollover(cursorMs))) return 0;
  }

  let streak = 0;
  while (dayKeys.has(dayKeyWith4amRollover(cursorMs))) {
    streak += 1;
    cursorMs -= 86_400_000;
  }
  return streak;
}
