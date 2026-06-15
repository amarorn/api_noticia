import { useEffect, useState } from "react";
import type { SuperbetLiveAdvice } from "@/domain/entities";

export interface HandicapOddsSide {
  home?: number;
  away?: number;
}

export interface HandicapHistorySample {
  minute: number;
  capturedAt: string | null;
  handicap: Record<string, HandicapOddsSide>;
  asianHandicap: Record<string, HandicapOddsSide>;
  modelHandicap?: Record<string, number>;
  modelAsian?: Record<string, number>;
}

function snapshotKey(sample: HandicapHistorySample): string {
  return `${sample.minute}|${JSON.stringify(sample.handicap)}|${JSON.stringify(sample.asianHandicap)}`;
}

/** Acumula odds e probabilidades de handicap FT ao longo dos polls. */
export function useLiveHandicapHistory(data: SuperbetLiveAdvice | undefined) {
  const [history, setHistory] = useState<HandicapHistorySample[]>([]);

  useEffect(() => {
    const ft = data?.halfMarkets?.ft;
    const handicap = ft?.handicap;
    const asianHandicap = ft?.asian_handicap;
    if (!data || (!handicap && !asianHandicap)) return;

    const sample: HandicapHistorySample = {
      minute: data.minute,
      capturedAt: data.capturedAt,
      handicap: handicap ?? {},
      asianHandicap: asianHandicap ?? {},
      modelHandicap: data.inplaySummary.ftHandicapProbs,
      modelAsian: data.inplaySummary.ftAsianHandicapProbs,
    };

    setHistory((prev) => {
      const last = prev[prev.length - 1];
      if (last && snapshotKey(last) === snapshotKey(sample)) return prev;
      return [...prev, sample].slice(-36);
    });
  }, [
    data,
    data?.minute,
    data?.capturedAt,
    data?.halfMarkets?.ft,
    data?.inplaySummary.ftHandicapProbs,
    data?.inplaySummary.ftAsianHandicapProbs,
  ]);

  useEffect(() => {
    setHistory([]);
  }, [data?.superbetEventId]);

  return history;
}
