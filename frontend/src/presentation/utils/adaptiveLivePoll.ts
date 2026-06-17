import type { SuperbetLivePulse } from "@/infrastructure/api/dataPulseStore";

export type LivePollTier = "normal" | "accelerated" | "urgent";

export interface LivePollIntervals {
  score: number;
  fast: number;
  full: number;
  list: number;
  tier: LivePollTier;
}

export const LIVE_POLL_BASE: Omit<LivePollIntervals, "tier"> = {
  score: 5_000,
  fast: 10_000,
  full: 60_000,
  list: 30_000,
};

export const LIVE_POLL_ACCELERATED: Omit<LivePollIntervals, "tier"> = {
  score: 3_000,
  fast: 5_000,
  full: 30_000,
  list: 15_000,
};

export const LIVE_POLL_URGENT: Omit<LivePollIntervals, "tier"> = {
  score: 2_000,
  fast: 4_000,
  full: 20_000,
  list: 10_000,
};

const DEFAULT_POLL_INTERVAL_SEC = 120;
const LAG_MULTIPLIER_ACCELERATED = 1.25;
const LAG_MULTIPLIER_URGENT = 2;

export interface AdaptivePollContext {
  eventId?: number;
  localCapturedAt?: string | null;
  nowMs?: number;
}

function captureAgeSec(capturedAt: string | null | undefined, nowMs: number): number | null {
  if (!capturedAt) return null;
  const capturedMs = Date.parse(capturedAt);
  if (!Number.isFinite(capturedMs)) return null;
  return Math.max(0, (nowMs - capturedMs) / 1000);
}

function effectiveCapturedAt(
  pulse: SuperbetLivePulse | null | undefined,
  ctx: AdaptivePollContext,
): string | null {
  if (ctx.localCapturedAt) return ctx.localCapturedAt;
  if (!pulse?.lastCaptureAt) return null;
  if (
    ctx.eventId != null &&
    pulse.primaryEventId != null &&
    pulse.primaryEventId !== ctx.eventId
  ) {
    return null;
  }
  return pulse.lastCaptureAt;
}

export function classifyLivePollTier(
  pulse: SuperbetLivePulse | null | undefined,
  ctx: AdaptivePollContext = {},
): LivePollTier {
  const nowMs = ctx.nowMs ?? Date.now();
  const pollSec =
    pulse?.pollIntervalSec && pulse.pollIntervalSec > 0
      ? pulse.pollIntervalSec
      : DEFAULT_POLL_INTERVAL_SEC;

  if (pulse?.stale) return "urgent";

  const capturedAt = effectiveCapturedAt(pulse, ctx);
  const ageSec = captureAgeSec(capturedAt, nowMs);

  if (ageSec == null) {
    return pulse?.lastCaptureAt ? "accelerated" : "accelerated";
  }

  if (ageSec >= pollSec * LAG_MULTIPLIER_URGENT) return "urgent";
  if (ageSec >= pollSec * LAG_MULTIPLIER_ACCELERATED) return "accelerated";
  return "normal";
}

export function resolveAdaptiveLivePollMs(
  pulse: SuperbetLivePulse | null | undefined,
  ctx: AdaptivePollContext = {},
): LivePollIntervals {
  const tier = classifyLivePollTier(pulse, ctx);
  const preset =
    tier === "urgent"
      ? LIVE_POLL_URGENT
      : tier === "accelerated"
        ? LIVE_POLL_ACCELERATED
        : LIVE_POLL_BASE;
  return { ...preset, tier };
}

export function livePollTierLabel(tier: LivePollTier): string {
  switch (tier) {
    case "urgent":
      return "poll acelerado (stale)";
    case "accelerated":
      return "poll acelerado";
    default:
      return "poll normal";
  }
}
