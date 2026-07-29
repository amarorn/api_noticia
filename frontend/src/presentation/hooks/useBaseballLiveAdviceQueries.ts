import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getBaseballSuperbetEventUseCase,
  getBaseballSuperbetLiveAdviceUseCase,
} from "@/application/container";
import type { BaseballSuperbetLiveAdvice, SuperbetEventSnapshot } from "@/domain/entities";
import { getDataPulseSnapshot, useDataPulse } from "@/infrastructure/api/dataPulseStore";
import { useAdaptivePollClock } from "@/presentation/hooks/useAdaptivePollClock";
import {
  applyReactivePollBoost,
  resolveAdaptiveLivePollMs,
} from "@/presentation/utils/adaptiveLivePoll";
import {
  mergeBaseballLiveAdvice,
  type BaseballAdviceSource,
} from "@/presentation/utils/baseballLiveMerge";
import {
  isReactivePollBoostActive,
  REACTIVE_GOAL_BOOST_MS,
} from "@/presentation/utils/liveTimelineReactive";

const STALE_MS = 8_000;
const SCORE_REFETCH_DEBOUNCE_MS = 2_000;

function resolvePollForQuery(
  eventId: number,
  localCapturedAt: string | null | undefined,
  reactiveBoostUntil: number,
  pulse = getDataPulseSnapshot()?.superbetLive,
) {
  return applyReactivePollBoost(
    resolveAdaptiveLivePollMs(pulse, { eventId, localCapturedAt }),
    reactiveBoostUntil,
  );
}

export function useBaseballLiveAdviceQueries(eventId: number, bankroll = 1000) {
  const enabled = Number.isFinite(eventId) && eventId > 0;
  const pulse = useDataPulse();
  const [reactiveBoostUntil, setReactiveBoostUntil] = useState(0);
  const reactiveBoostUntilRef = useRef(0);
  const lastScoreRefetchAtRef = useRef(0);

  const bumpReactiveBoost = useCallback(() => {
    const until = Date.now() + REACTIVE_GOAL_BOOST_MS;
    reactiveBoostUntilRef.current = until;
    setReactiveBoostUntil(until);
  }, []);

  const scoreTickQuery = useQuery({
    queryKey: ["baseball-superbet-event-score", eventId],
    queryFn: () => getBaseballSuperbetEventUseCase.execute({ eventId, saveBronze: false }),
    enabled,
    staleTime: STALE_MS,
    refetchInterval: (q) => {
      const d = q.state.data;
      if (!d?.isLive) return false;
      return resolvePollForQuery(eventId, d.capturedAt, reactiveBoostUntilRef.current).score;
    },
  });

  const fastAdviceQuery = useQuery({
    queryKey: ["baseball-superbet-live-advice", eventId, bankroll, "fast"],
    queryFn: () =>
      getBaseballSuperbetLiveAdviceUseCase.execute({
        eventId,
        bankroll,
        fast: true,
      }),
    enabled,
    staleTime: STALE_MS,
    refetchInterval: (q) => {
      const d = q.state.data as BaseballSuperbetLiveAdvice | undefined;
      if (!d?.isLive || d?.isFinished) return false;
      return resolvePollForQuery(eventId, d.capturedAt, reactiveBoostUntilRef.current).fast;
    },
  });

  const fullAdviceQuery = useQuery({
    queryKey: ["baseball-superbet-live-advice", eventId, bankroll, "full"],
    queryFn: () =>
      getBaseballSuperbetLiveAdviceUseCase.execute({
        eventId,
        bankroll,
        fast: false,
      }),
    enabled: enabled && Boolean(fastAdviceQuery.data),
    staleTime: STALE_MS,
    refetchInterval: (q) => {
      const d = q.state.data as BaseballSuperbetLiveAdvice | undefined;
      if (!d?.isLive || d?.isFinished) return false;
      return resolvePollForQuery(eventId, d.capturedAt, reactiveBoostUntilRef.current).full;
    },
  });

  const isLiveSession = Boolean(
    scoreTickQuery.data?.isLive ||
      (fastAdviceQuery.data?.isLive && !fastAdviceQuery.data?.isFinished),
  );
  const pollClock = useAdaptivePollClock(enabled && isLiveSession);

  const data = useMemo(() => {
    return mergeBaseballLiveAdvice(fastAdviceQuery.data, fullAdviceQuery.data).data;
  }, [fastAdviceQuery.data, fullAdviceQuery.data]);

  const adviceSource = useMemo((): BaseballAdviceSource | null => {
    return mergeBaseballLiveAdvice(fastAdviceQuery.data, fullAdviceQuery.data).source;
  }, [fastAdviceQuery.data, fullAdviceQuery.data]);

  const liveHeader = useMemo(() => {
    const tick = scoreTickQuery.data;
    if (!data && tick) {
      return {
        currentScore: tick.currentScore,
        inning: tick.minute,
        periodLabel: tick.periodLabel,
        h2hOdds: tick.h2hOdds,
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
      inning: tick.minute ?? data.inning,
      periodLabel: tick.periodLabel ?? data.periodLabel,
      h2hOdds: tick.h2hOdds ?? data.h2hOdds,
      capturedAt: tick.capturedAt ?? data.capturedAt,
      scoreIsFresh,
    };
  }, [scoreTickQuery.data, data]);

  const scoreTick = scoreTickQuery.data ?? null;

  const triggerReactiveRefetch = useCallback(() => {
    void scoreTickQuery.refetch();
    void fastAdviceQuery.refetch();
    void fullAdviceQuery.refetch();
  }, [scoreTickQuery, fastAdviceQuery, fullAdviceQuery]);

  useEffect(() => {
    if (!scoreTick?.currentScore || !data?.currentScore) return;
    if (scoreTick.currentScore === data.currentScore) return;
    if (fastAdviceQuery.isFetching || fullAdviceQuery.isFetching || data.isFinished) return;
    const now = Date.now();
    if (now - lastScoreRefetchAtRef.current < SCORE_REFETCH_DEBOUNCE_MS) return;
    lastScoreRefetchAtRef.current = now;
    bumpReactiveBoost();
    triggerReactiveRefetch();
  }, [
    scoreTick?.currentScore,
    data?.currentScore,
    data?.isFinished,
    fastAdviceQuery.isFetching,
    fullAdviceQuery.isFetching,
    triggerReactiveRefetch,
    bumpReactiveBoost,
  ]);

  const pollMs = useMemo(() => {
    void pollClock;
    void pulse;
    return applyReactivePollBoost(
      resolveAdaptiveLivePollMs(pulse?.superbetLive, {
        eventId,
        localCapturedAt:
          liveHeader?.capturedAt ??
          data?.capturedAt ??
          scoreTick?.capturedAt ??
          fastAdviceQuery.data?.capturedAt ??
          null,
      }),
      reactiveBoostUntil,
    );
  }, [
    pollClock,
    pulse,
    eventId,
    liveHeader?.capturedAt,
    data?.capturedAt,
    scoreTick?.capturedAt,
    fastAdviceQuery.data?.capturedAt,
    reactiveBoostUntil,
  ]);

  const hasAnyData = Boolean(scoreTick || fastAdviceQuery.data);
  const isLoading = !hasAnyData && (scoreTickQuery.isLoading || fastAdviceQuery.isLoading);
  const isAdvicePending = !data && fastAdviceQuery.isLoading;
  const reactiveBoosted = useMemo(
    () => isReactivePollBoostActive(reactiveBoostUntil),
    [reactiveBoostUntil, pollClock],
  );

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
    refetch: triggerReactiveRefetch,
    pollMs,
    reactiveBoosted,
  };
}

export type BaseballLiveScoreTick = SuperbetEventSnapshot | null;
