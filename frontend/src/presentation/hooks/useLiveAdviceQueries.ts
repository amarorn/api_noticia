import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSuperbetEventUseCase, getSuperbetLiveAdviceUseCase } from "@/application/container";
import type { SuperbetEventSnapshot, SuperbetLiveAdvice } from "@/domain/entities";
import { mergeLiveAdvice } from "@/presentation/utils/liveRecalibration";

const FAST_POLL_MS = 10_000;
const FULL_POLL_MS = 60_000;
const SCORE_POLL_MS = 5_000;
const STALE_MS = 8_000;

export function useLiveAdviceQueries(
  eventId: number,
  bankroll = 1000,
  kickoff?: string | null,
  phase = "group",
) {
  const enabled = Number.isFinite(eventId) && eventId > 0;
  const kickoffKey = kickoff ?? "";
  const phaseKey = phase || "group";

  // 1. Score tick — mais rápido, mostra placar imediatamente
  const scoreTickQuery = useQuery({
    queryKey: ["superbet-event-score", eventId],
    queryFn: () => getSuperbetEventUseCase.execute({ eventId, saveBronze: false }),
    enabled,
    staleTime: STALE_MS,
    refetchInterval: (q) => {
      const d = q.state.data;
      return d?.isLive ? SCORE_POLL_MS : false;
    },
  });

  // 2. Fast advice — mostra dados básicos rapidamente
  const fastAdviceQuery = useQuery({
    queryKey: ["superbet-live-advice", eventId, bankroll, kickoffKey, phaseKey, "fast"],
    queryFn: () =>
      getSuperbetLiveAdviceUseCase.execute({
        eventId,
        bankroll,
        phase: phaseKey,
        fast: true,
        ...(kickoff ? { kickoff } : {}),
      }),
    enabled,
    staleTime: STALE_MS,
    refetchInterval: (q) => {
      const d = q.state.data as SuperbetLiveAdvice | undefined;
      return d?.isLive && !d?.isFinished ? FAST_POLL_MS : false;
    },
  });

  // 3. Full advice — só carrega depois do fast, em background
  const fullAdviceQuery = useQuery({
    queryKey: ["superbet-live-advice", eventId, bankroll, kickoffKey, phaseKey, "full"],
    queryFn: () =>
      getSuperbetLiveAdviceUseCase.execute({
        eventId,
        bankroll,
        phase: phaseKey,
        fast: false,
        ...(kickoff ? { kickoff } : {}),
      }),
    enabled: enabled && Boolean(fastAdviceQuery.data),
    staleTime: STALE_MS,
    refetchInterval: (q) => {
      const d = q.state.data as SuperbetLiveAdvice | undefined;
      return d?.isLive && !d?.isFinished ? FULL_POLL_MS : false;
    },
  });

  const data = useMemo(() => {
    const merged = mergeLiveAdvice(fastAdviceQuery.data, fullAdviceQuery.data);
    return merged.data;
  }, [fastAdviceQuery.data, fullAdviceQuery.data]);

  const adviceSource = useMemo(() => {
    const merged = mergeLiveAdvice(fastAdviceQuery.data, fullAdviceQuery.data);
    return merged.source ?? ("fast" as const);
  }, [fastAdviceQuery.data, fullAdviceQuery.data]);

  const liveHeader = useMemo(() => {
    const tick = scoreTickQuery.data;
    if (!data && tick) {
      return {
        currentScore: tick.currentScore,
        minute: tick.minute,
        periodLabel: tick.periodLabel,
        h2hOdds: tick.h2hOdds,
        rawMarketCount: tick.rawMarketCount,
        capturedAt: tick.capturedAt,
        scoreIsFresh: true,
      };
    }
    if (!tick || !data) return null;
    const scoreIsFresh =
      tick.capturedAt != null &&
      data.capturedAt != null &&
      tick.capturedAt >= data.capturedAt;
    return {
      currentScore: tick.currentScore ?? data.currentScore,
      minute: tick.minute ?? data.minute,
      periodLabel: tick.periodLabel ?? data.periodLabel,
      h2hOdds: tick.h2hOdds ?? data.h2hOdds,
      rawMarketCount: tick.rawMarketCount ?? data.rawMarketCount,
      capturedAt: tick.capturedAt ?? data.capturedAt,
      scoreIsFresh,
    };
  }, [scoreTickQuery.data, data]);

  const scoreTick = scoreTickQuery.data ?? null;

  // Loading progressivo: mostra algo assim que score ou fast chegar
  const hasAnyData = Boolean(scoreTick || fastAdviceQuery.data);
  const isLoading = !hasAnyData && (scoreTickQuery.isLoading || fastAdviceQuery.isLoading);
  const isAdvicePending = !data && fastAdviceQuery.isLoading;

  return {
    data,
    scoreTick,
    liveHeader,
    adviceSource,
    isLoading,
    isAdvicePending,
    isError: fastAdviceQuery.isError && scoreTickQuery.isError,
    error: fastAdviceQuery.error ?? scoreTickQuery.error,
    isFetching: fastAdviceQuery.isFetching || fullAdviceQuery.isFetching,
    refetch: () => {
      void scoreTickQuery.refetch();
      void fastAdviceQuery.refetch();
      void fullAdviceQuery.refetch();
    },
    pollMs: { fast: FAST_POLL_MS, full: FULL_POLL_MS, score: SCORE_POLL_MS },
  };
}

export type LiveAdviceScoreTick = SuperbetEventSnapshot | null;
