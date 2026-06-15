import type { SuperbetLiveAdvice } from "@/domain/entities";

export type RecalibrationReason = "goal" | "halftime" | "minute" | "refresh";

export interface LiveRecalibrationEvent {
  reason: RecalibrationReason;
  atMinute: number;
  previousScore: string;
  currentScore: string;
  message: string;
  detail?: string;
  goalsHomeDelta: number;
  goalsAwayDelta: number;
  maxProbShiftPp: number;
  detectedAt: number;
}

export function parseLiveScore(score: string | null | undefined): [number, number] {
  if (!score) return [0, 0];
  const parts = score.toLowerCase().split("x");
  if (parts.length !== 2) return [0, 0];
  return [Number.parseInt(parts[0] ?? "0", 10) || 0, Number.parseInt(parts[1] ?? "0", 10) || 0];
}

export function formatLiveScore(home: number, away: number): string {
  return `${home}×${away}`;
}

export type LiveAdviceSource = "fast" | "full";

export function mergeLiveAdvice(
  fast: SuperbetLiveAdvice | undefined,
  full: SuperbetLiveAdvice | undefined,
): { data: SuperbetLiveAdvice | undefined; source: LiveAdviceSource | null } {
  if (!fast && !full) return { data: undefined, source: null };
  if (!full) return { data: fast, source: "fast" };
  if (!fast) return { data: full, source: "full" };
  const fastTs = Date.parse(fast.capturedAt ?? "") || 0;
  const fullTs = Date.parse(full.capturedAt ?? "") || 0;
  if (fullTs >= fastTs) return { data: full, source: "full" };
  return {
    data: {
      ...fast,
      halfTickets: fast.halfTickets ?? full.halfTickets,
      strategy: fast.strategy
        ? {
            ...fast.strategy,
            comboTicket: fast.strategy.comboTicket ?? full.strategy?.comboTicket ?? null,
          }
        : full.strategy,
    },
    source: "fast",
  };
}

function maxProbShiftPp(prev: SuperbetLiveAdvice, next: SuperbetLiveAdvice): number {
  const pairs: [number, number][] = [
    [prev.inplaySummary.probFinalHome, next.inplaySummary.probFinalHome],
    [prev.inplaySummary.probFinalDraw, next.inplaySummary.probFinalDraw],
    [prev.inplaySummary.probFinalAway, next.inplaySummary.probFinalAway],
  ];
  return Math.max(...pairs.map(([a, b]) => Math.abs(b - a) * 100), 0);
}

function goalMessage(
  data: SuperbetLiveAdvice,
  scoreLabel: string,
  minute: number,
  homeDelta: number,
  awayDelta: number,
): string {
  if (homeDelta > 0 && awayDelta === 0) {
    return `Recalibrado após gol de ${data.homeTeam} — ${scoreLabel} aos ${minute}'`;
  }
  if (awayDelta > 0 && homeDelta === 0) {
    return `Recalibrado após gol de ${data.awayTeam} — ${scoreLabel} aos ${minute}'`;
  }
  return `Recalibrado após gol — ${scoreLabel} aos ${minute}'`;
}

export function detectLiveRecalibration(
  previous: SuperbetLiveAdvice | null,
  current: SuperbetLiveAdvice,
): LiveRecalibrationEvent | null {
  if (!previous || previous.superbetEventId !== current.superbetEventId) {
    return null;
  }

  const [prevH, prevA] = parseLiveScore(previous.currentScore);
  const [curH, curA] = parseLiveScore(current.currentScore);
  const homeDelta = curH - prevH;
  const awayDelta = curA - prevA;
  const scoreChanged = homeDelta !== 0 || awayDelta !== 0;
  const minuteChanged = current.minute !== previous.minute;
  const capturedChanged =
    Boolean(current.capturedAt) &&
    Boolean(previous.capturedAt) &&
    current.capturedAt !== previous.capturedAt;

  if (!scoreChanged && !minuteChanged && !capturedChanged) {
    return null;
  }

  const probShift = maxProbShiftPp(previous, current);
  const scoreLabel = formatLiveScore(curH, curA);
  const now = Date.now();

  if (scoreChanged && (homeDelta > 0 || awayDelta > 0)) {
    const detail =
      probShift >= 1
        ? `Probabilidades 1X2 ajustadas (até ${probShift.toFixed(1)} pp)`
        : undefined;
    return {
      reason: "goal",
      atMinute: current.minute,
      previousScore: previous.currentScore ?? "0x0",
      currentScore: current.currentScore ?? "0x0",
      message: goalMessage(current, scoreLabel, current.minute, homeDelta, awayDelta),
      detail,
      goalsHomeDelta: homeDelta,
      goalsAwayDelta: awayDelta,
      maxProbShiftPp: probShift,
      detectedAt: now,
    };
  }

  const enteredSecondHalf =
    previous.minute <= 45 && current.minute > 45 && !scoreChanged;
  if (enteredSecondHalf || (current.minute > 45 && current.halftimeReport?.applied && !previous.halftimeReport?.applied)) {
    return {
      reason: "halftime",
      atMinute: current.minute,
      previousScore: previous.currentScore ?? "0x0",
      currentScore: current.currentScore ?? "0x0",
      message: `Intervalo — modelo 2T recalibrado com dados do 1T (${scoreLabel})`,
      detail: current.halftimeReport?.summary,
      goalsHomeDelta: 0,
      goalsAwayDelta: 0,
      maxProbShiftPp: probShift,
      detectedAt: now,
    };
  }

  if (minuteChanged && capturedChanged) {
    return {
      reason: "minute",
      atMinute: current.minute,
      previousScore: previous.currentScore ?? "0x0",
      currentScore: current.currentScore ?? "0x0",
      message: `Modelo atualizado — ${scoreLabel} aos ${current.minute}'`,
      detail:
        probShift >= 2
          ? `Probabilidades 1X2 moveram até ${probShift.toFixed(1)} pp`
          : undefined,
      goalsHomeDelta: 0,
      goalsAwayDelta: 0,
      maxProbShiftPp: probShift,
      detectedAt: now,
    };
  }

  if (capturedChanged) {
    return {
      reason: "refresh",
      atMinute: current.minute,
      previousScore: previous.currentScore ?? "0x0",
      currentScore: current.currentScore ?? "0x0",
      message: `Palpite recalculado — ${scoreLabel} aos ${current.minute}'`,
      detail: undefined,
      goalsHomeDelta: 0,
      goalsAwayDelta: 0,
      maxProbShiftPp: probShift,
      detectedAt: now,
    };
  }

  return null;
}
