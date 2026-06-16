import { useEffect, useState } from "react";
import type { SuperbetLiveAdvice } from "@/domain/entities";

export interface PossessionSample {
  minute: number;
  home: number;
  away: number;
  capturedAt: string | null;
}

/** Acumula amostras de posse ao longo dos polls para gráfico de linha. */
export function useLivePossessionHistory(data: SuperbetLiveAdvice | undefined) {
  const [history, setHistory] = useState<PossessionSample[]>([]);

  useEffect(() => {
    const homePct = data?.liveStats?.homePossessionPct;
    if (homePct == null || !data) return;
    const awayPct = data.liveStats?.awayPossessionPct ?? Math.max(0, 100 - homePct);

    setHistory((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.minute === data.minute && last.home === homePct) return prev;
      const next = [...prev, { minute: data.minute, home: homePct, away: awayPct, capturedAt: data.capturedAt }];
      return next.slice(-36);
    });
  }, [data, data?.minute, data?.liveStats?.homePossessionPct, data?.liveStats?.awayPossessionPct, data?.capturedAt]);

  useEffect(() => {
    setHistory([]);
  }, [data?.superbetEventId]);

  return history;
}
