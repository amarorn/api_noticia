import { useEffect, useMemo, useState } from "react";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import type { HandicapOddsSide } from "@/presentation/hooks/useLiveHandicapHistory";
import { detectGoalEvents, parseScore, type GoalEvent } from "@/presentation/utils/liveChartUtils";

export interface LivePredictionTick {
  minute: number;
  label: string;
  capturedAt: string | null;
  currentScore: string | null;
  homeScore: number;
  awayScore: number;
  h2hOdds: Record<string, number>;
  h2hImplied: Record<string, number>;
  modelHomePct: number;
  modelDrawPct: number;
  modelAwayPct: number;
  over25ModelPct: number | null;
  over25Odd: number | null;
  over25ImpliedPct: number | null;
  handicap: Record<string, HandicapOddsSide>;
  asianHandicap: Record<string, HandicapOddsSide>;
  modelHandicap?: Record<string, number>;
  modelAsian?: Record<string, number>;
}

function tickKey(t: LivePredictionTick): string {
  return `${t.minute}|${t.currentScore}|${t.capturedAt}|${JSON.stringify(t.h2hOdds)}`;
}

/** Histórico unificado: 1X2, totals, handicap e placar para gráficos ECharts. */
export function useLivePredictionHistory(data: SuperbetLiveAdvice | undefined) {
  const [history, setHistory] = useState<LivePredictionTick[]>([]);

  useEffect(() => {
    if (!data) return;

    const score = parseScore(data.currentScore);
    const overScan = data.strategy?.marketScan?.find(
      (m) => m.market === "over_2_5" && (m.outcome === "yes" || m.outcome === "over"),
    );

    const sample: LivePredictionTick = {
      minute: data.minute,
      label: `${data.minute}'`,
      capturedAt: data.capturedAt,
      currentScore: data.currentScore,
      homeScore: score?.home ?? 0,
      awayScore: score?.away ?? 0,
      h2hOdds: data.h2hOdds ?? {},
      h2hImplied: data.h2hImplied ?? {},
      modelHomePct: (data.inplaySummary.probFinalHome ?? 0) * 100,
      modelDrawPct: (data.inplaySummary.probFinalDraw ?? 0) * 100,
      modelAwayPct: (data.inplaySummary.probFinalAway ?? 0) * 100,
      over25ModelPct:
        data.inplaySummary.over25 != null ? data.inplaySummary.over25 * 100 : null,
      over25Odd: overScan?.marketOdd ?? null,
      over25ImpliedPct: overScan?.impliedProb != null ? overScan.impliedProb * 100 : null,
      handicap: data.halfMarkets?.ft?.handicap ?? {},
      asianHandicap: data.halfMarkets?.ft?.asian_handicap ?? {},
      modelHandicap: data.inplaySummary.ftHandicapProbs,
      modelAsian: data.inplaySummary.ftAsianHandicapProbs,
    };

    setHistory((prev) => {
      const last = prev[prev.length - 1];
      if (last && tickKey(last) === tickKey(sample)) return prev;
      return [...prev, sample].slice(-48);
    });
  }, [data]);

  useEffect(() => {
    setHistory([]);
  }, [data?.superbetEventId]);

  const goalEvents = useMemo(
    () =>
      detectGoalEvents(
        history.map((h) => ({
          minute: h.minute,
          label: h.label,
          homeScore: h.homeScore,
          awayScore: h.awayScore,
        })),
      ),
    [history],
  );

  return { history, goalEvents };
}

export type { GoalEvent };
