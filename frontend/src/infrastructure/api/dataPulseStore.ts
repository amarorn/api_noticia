import { useSyncExternalStore } from "react";

export interface SuperbetLivePulse {
  lastCaptureAt: string | null;
  liveEventsCount: number;
  primaryEventId: number | null;
  stale: boolean;
  pollIntervalSec: number;
}

export interface DataPulse {
  pulseAt: string;
  articlesSilver: number;
  fixtures: number;
  wcModelsReady: boolean;
  collectionsLastRun: string | null;
  latestSilverAt: string | null;
  superbetLive: SuperbetLivePulse | null;
}

let snapshot: DataPulse | null = null;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((fn) => fn());
}

function parseSuperbetLiveFromHeaders(headers: Headers): SuperbetLivePulse {
  const lastCaptureAt = headers.get("X-Superbet-Last-Capture-At");
  const primaryEventRaw = headers.get("X-Superbet-Primary-Event-Id");
  const primaryEventId =
    primaryEventRaw && primaryEventRaw.length > 0
      ? Number.parseInt(primaryEventRaw, 10)
      : null;

  return {
    lastCaptureAt: lastCaptureAt && lastCaptureAt.length > 0 ? lastCaptureAt : null,
    liveEventsCount: Number.parseInt(headers.get("X-Superbet-Live-Events") ?? "0", 10) || 0,
    primaryEventId: Number.isFinite(primaryEventId) ? primaryEventId : null,
    stale: headers.get("X-Superbet-Stale") === "true",
    pollIntervalSec:
      Number.parseInt(headers.get("X-Superbet-Poll-Interval-Sec") ?? "0", 10) || 0,
  };
}

export function applyDataPulseFromHeaders(headers: Headers): void {
  const pulseAt = headers.get("X-Data-Pulse-At");
  const articles = headers.get("X-Articles-Silver");
  if (!pulseAt || articles === null) return;

  const fixtures = headers.get("X-Fixtures");
  const lastRun = headers.get("X-Collections-Last-Run");
  const latestSilver = headers.get("X-Latest-Silver-At");

  snapshot = {
    pulseAt,
    articlesSilver: Number.parseInt(articles, 10) || 0,
    fixtures: Number.parseInt(fixtures ?? "0", 10) || 0,
    wcModelsReady: headers.get("X-WC-Models-Ready") === "true",
    collectionsLastRun: lastRun && lastRun.length > 0 ? lastRun : null,
    latestSilverAt: latestSilver && latestSilver.length > 0 ? latestSilver : null,
    superbetLive: parseSuperbetLiveFromHeaders(headers),
  };
  emit();
}

export function getDataPulseSnapshot(): DataPulse | null {
  return snapshot;
}

export function useDataPulse(): DataPulse | null {
  return useSyncExternalStore(
    (onStoreChange) => {
      listeners.add(onStoreChange);
      return () => listeners.delete(onStoreChange);
    },
    () => snapshot,
    () => snapshot,
  );
}

export function formatSuperbetCaptureAge(
  lastCaptureAt: string | null,
  nowMs: number = Date.now(),
): string | null {
  if (!lastCaptureAt) return null;
  const capturedMs = Date.parse(lastCaptureAt);
  if (!Number.isFinite(capturedMs)) return null;
  const ageSec = Math.max(0, Math.round((nowMs - capturedMs) / 1000));
  if (ageSec < 60) return `${ageSec}s`;
  const minutes = Math.floor(ageSec / 60);
  const seconds = ageSec % 60;
  return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`;
}
