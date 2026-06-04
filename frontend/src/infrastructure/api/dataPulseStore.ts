import { useSyncExternalStore } from "react";

export interface DataPulse {
  pulseAt: string;
  articlesSilver: number;
  fixtures: number;
  wcModelsReady: boolean;
  collectionsLastRun: string | null;
  latestSilverAt: string | null;
}

let snapshot: DataPulse | null = null;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((fn) => fn());
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
