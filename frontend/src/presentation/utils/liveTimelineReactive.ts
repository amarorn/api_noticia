import type { ScorealarmTimelineEvent } from "@/domain/entities";

/** Tipo ScoreAlarm para gol (overview ``live_events``). */
export const SCOREALARM_GOAL_EVENT_TYPE = 4;

export interface TimelineSnapshot {
  fingerprint: string;
  goalCount: number;
  latestGoalMinute: number | null;
  totalEvents: number;
}

export interface TimelineGoalChange {
  hasNewGoal: boolean;
  deltaGoals: number;
  latestGoalMinute: number | null;
}

export function snapshotTimeline(events: ScorealarmTimelineEvent[]): TimelineSnapshot {
  const goals = events.filter((e) => e.type === SCOREALARM_GOAL_EVENT_TYPE);
  const fingerprint = goals
    .map((g) => `${g.minute}:${g.side}:${g.team}:${g.score ?? ""}`)
    .join("|");
  return {
    fingerprint: fingerprint || `events:${events.length}`,
    goalCount: goals.length,
    latestGoalMinute: goals.length > 0 ? Math.max(...goals.map((g) => g.minute)) : null,
    totalEvents: events.length,
  };
}

export function detectTimelineGoalChange(
  previous: TimelineSnapshot | null,
  events: ScorealarmTimelineEvent[],
): TimelineGoalChange | null {
  if (!previous || events.length === 0) return null;
  const current = snapshotTimeline(events);
  const deltaGoals = current.goalCount - previous.goalCount;
  if (deltaGoals > 0) {
    return {
      hasNewGoal: true,
      deltaGoals,
      latestGoalMinute: current.latestGoalMinute,
    };
  }
  if (
    current.fingerprint !== previous.fingerprint &&
    current.goalCount === previous.goalCount &&
    current.goalCount > 0
  ) {
    return {
      hasNewGoal: true,
      deltaGoals: 0,
      latestGoalMinute: current.latestGoalMinute,
    };
  }
  return null;
}

/** Janela pós-gol com poll acelerado (ms). */
export const REACTIVE_GOAL_BOOST_MS = 90_000;

export function isReactivePollBoostActive(boostUntilMs: number, nowMs = Date.now()): boolean {
  return boostUntilMs > nowMs;
}
