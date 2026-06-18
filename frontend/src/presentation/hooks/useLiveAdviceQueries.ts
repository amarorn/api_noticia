import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSuperbetEventUseCase, getSuperbetLiveAdviceUseCase } from "@/application/container";
import type { ScorealarmTimelineEvent, SuperbetLiveAdvice } from "@/domain/entities";
import { getDataPulseSnapshot, useDataPulse } from "@/infrastructure/api/dataPulseStore";
import { useAdaptivePollClock } from "@/presentation/hooks/useAdaptivePollClock";
import { useTimelineReactiveRefetch } from "@/presentation/hooks/useTimelineReactiveRefetch";
import {
  applyReactivePollBoost,
  resolveAdaptiveLivePollMs,
} from "@/presentation/utils/adaptiveLivePoll";
import { mergeLiveAdvice } from "@/presentation/utils/liveRecalibration";
import {
  isReactivePollBoostActive,
  REACTIVE_GOAL_BOOST_MS,
} from "@/presentation/utils/liveTimelineReactive";

const STALE_MS = 8_000;
const SCORE_REFETCH_DEBOUNCE_MS = 2_000;
const EMPTY_TIMELINE: ScorealarmTimelineEvent[] = [];

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
      return resolvePollForQuery(eventId, d.capturedAt, reactiveBoostUntilRef.current).score;
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
      return resolvePollForQuery(eventId, d.capturedAt, reactiveBoostUntilRef.current).fast;
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
      return resolvePollForQuery(eventId, d.capturedAt, reactiveBoostUntilRef.current).full;
    },
  });

  const isLiveSession = Boolean(
    scoreTickQuery.data?.isLive ||
      (fastAdviceQuery.data?.isLive && !fastAdviceQuery.data?.isFinished),
  );
  const pollClock = useAdaptivePollClock(enabled && isLiveSession);
  const [reactiveBoostUntil, setReactiveBoostUntil] = useState(0);
  const reactiveBoostUntilRef = useRef(0);
  const lastScoreRefetchAtRef = useRef(0);

  const bumpReactiveBoost = useCallback(() => {
    const until = Date.now() + REACTIVE_GOAL_BOOST_MS;
    reactiveBoostUntilRef.current = until;
    setReactiveBoostUntil(until);
  }, []);

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

  const triggerReactiveRefetch = useCallback(() => {
    void scoreTickQuery.refetch();
    void fastAdviceQuery.refetch();
    void fullAdviceQuery.refetch();
  }, [scoreTickQuery, fastAdviceQuery, fullAdviceQuery]);

  const timelineEvents =
    fullAdviceQuery.data?.scorealarm?.timeline ??
    data?.scorealarm?.timeline ??
    EMPTY_TIMELINE;

  const timelineReactive = useTimelineReactiveRefetch({
    enabled: enabled && isLiveSession,
    isFetching: fastAdviceQuery.isFetching || fullAdviceQuery.isFetching,
    isFinished: Boolean(data?.isFinished),
    timeline: timelineEvents,
    onReactiveRefetch: () => {
      bumpReactiveBoost();
      triggerReactiveRefetch();
    },
  });

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
    timelineReactive: {
      ...timelineReactive,
      boosted: reactiveBoosted,
    },
  };
}

export type LiveAdviceScoreTick = import("@/domain/entities").SuperbetEventSnapshot | null;
