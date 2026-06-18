import { useEffect, useRef, useState } from "react";
import type { ScorealarmTimelineEvent } from "@/domain/entities";
import {
  detectTimelineGoalChange,
  snapshotTimeline,
  type TimelineSnapshot,
} from "@/presentation/utils/liveTimelineReactive";

const REFETCH_DEBOUNCE_MS = 2_000;

interface UseTimelineReactiveRefetchOptions {
  enabled: boolean;
  isFetching: boolean;
  isFinished: boolean;
  timeline: ScorealarmTimelineEvent[];
  onReactiveRefetch: () => void;
}

/**
 * Detecta gol novo na timeline ScoreAlarm e dispara refetch imediato.
 */
export function useTimelineReactiveRefetch({
  enabled,
  isFetching,
  isFinished,
  timeline,
  onReactiveRefetch,
}: UseTimelineReactiveRefetchOptions): { latestGoalMinute: number | null } {
  const snapshotRef = useRef<TimelineSnapshot | null>(null);
  const lastRefetchAtRef = useRef(0);
  const [latestGoalMinute, setLatestGoalMinute] = useState<number | null>(null);

  useEffect(() => {
    if (!enabled || isFinished || timeline.length === 0) return;

    const previous = snapshotRef.current;
    const current = snapshotTimeline(timeline);
    snapshotRef.current = current;

    if (!previous) return;

    const change = detectTimelineGoalChange(previous, timeline);
    if (!change?.hasNewGoal || isFetching) return;

    const now = Date.now();
    if (now - lastRefetchAtRef.current < REFETCH_DEBOUNCE_MS) return;
    lastRefetchAtRef.current = now;

    if (change.latestGoalMinute != null) {
      setLatestGoalMinute(change.latestGoalMinute);
    }
    onReactiveRefetch();
  }, [enabled, isFinished, isFetching, timeline, onReactiveRefetch]);

  return { latestGoalMinute };
}
