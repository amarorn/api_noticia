import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSuperbetEventUseCase, getSuperbetLiveAdviceUseCase } from "@/application/container";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import { getDataPulseSnapshot, useDataPulse } from "@/infrastructure/api/dataPulseStore";
import { useAdaptivePollClock } from "@/presentation/hooks/useAdaptivePollClock";
import { resolveAdaptiveLivePollMs } from "@/presentation/utils/adaptiveLivePoll";
import { mergeLiveAdvice } from "@/presentation/utils/liveRecalibration";

const STALE_MS = 8_000;

function resolvePollForQuery(
  eventId: number,
  localCapturedAt: string | null | undefined,
  pulse = getDataPulseSnapshot()?.superbetLive,
) {
  return resolveAdaptiveLivePollMs(pulse, { eventId, localCapturedAt });
}

export function useLiveAdviceQueries(
  eventId: number,
  bankroll = 1000,
  kickoff?: string | null,
  phase = "group",
) {
  const enabled = Number.isFinite(eventId) && eventId > 0;
  const kickoffKey = kickoff ?? "";
  const phaseKey = phase || "group";
  const pulse = useDataPulse();

  const scoreTickQuery = useQuery({
    queryKey: ["superbet-event-score", eventId],
    queryFn: () => getSuperbetEventUseCase.execute({ eventId, saveBronze: false }),
    enabled,
    staleTime: STALE_MS,
    refetchInterval: (q) => {
      const d = q.state.data;
      if (!d?.isLive) return false;
      return resolvePollForQuery(eventId, d.capturedAt).score;
    },
  });

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
      if (!d?.isLive || d?.isFinished) return false;
      return resolvePollForQuery(eventId, d.capturedAt).fast;
    },
  });

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
      if (!d?.isLive || d?.isFinished) return false;
      return resolvePollForQuery(eventId, d.capturedAt).full;
    },
  });

  const isLiveSession = Boolean(
    scoreTickQuery.data?.isLive ||
      (fastAdviceQuery.data?.isLive && !fastAdviceQuery.data?.isFinished),
  );
  const pollClock = useAdaptivePollClock(enabled && isLiveSession);

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

  const pollMs = useMemo(() => {
    void pollClock;
    void pulse;
    return resolveAdaptiveLivePollMs(pulse?.superbetLive, {
      eventId,
      localCapturedAt:
        liveHeader?.capturedAt ??
        data?.capturedAt ??
        scoreTick?.capturedAt ??
        fastAdviceQuery.data?.capturedAt ??
        null,
    });
  }, [
    pollClock,
    pulse,
    eventId,
    liveHeader?.capturedAt,
    data?.capturedAt,
    scoreTick?.capturedAt,
    fastAdviceQuery.data?.capturedAt,
  ]);

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
    pollMs,
  };
}

export type LiveAdviceScoreTick = import("@/domain/entities").SuperbetEventSnapshot | null;
