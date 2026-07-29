import type { SuperbetLiveAdvice } from "@/domain/entities";
import type { MarketOperationalRow } from "./useMarketOperationalRows";

export type DataQualityStatus = "Excelente" | "Boa" | "Atenção" | "Fraca" | "Crítica";

export interface DataQualityReport {
  score: number;
  status: DataQualityStatus;
  avgConfidence: number;
  avgUpdateSec: number | null;
  completePct: number;
  positiveEvPct: number;
  alerts: string[];
}

function statusFromScore(score: number): DataQualityStatus {
  if (score >= 80) return "Excelente";
  if (score >= 65) return "Boa";
  if (score >= 45) return "Atenção";
  if (score >= 25) return "Fraca";
  return "Crítica";
}

function isAdviceStale(data: SuperbetLiveAdvice): boolean {
  return Boolean((data as SuperbetLiveAdvice & { superbetStale?: boolean }).superbetStale);
}

export function buildDataQualityReport(
  data: SuperbetLiveAdvice,
  rows: MarketOperationalRow[],
  dataAgeSec: number | null,
): DataQualityReport {
  const total = rows.length;
  const positiveEvPct = total
    ? Math.round((rows.filter((r) => r.expectedValue > 0).length / total) * 100)
    : 0;
  const completePct = total
    ? Math.round((rows.filter((r) => r.modelProb > 0 && r.marketOdd > 1).length / total) * 100)
    : data.rawMarketCount > 0
      ? Math.min(100, Math.round((total / data.rawMarketCount) * 100))
      : 0;
  const avgConfidence = total
    ? rows.reduce((sum, r) => sum + r.confidenceScore, 0) / total
    : data.confidence?.score ?? 0;

  const avgUpdateSec = dataAgeSec;
  const avoidCount = rows.filter((r) => r.status === "evitar").length;
  const lowConfidence = avgConfidence < 0.5;
  const fastMoving = rows.filter((r) => r.direction === "esticando").length;
  const highEvLowConf = rows.filter((r) => r.expectedValue > 0.08 && r.confidenceScore < 0.45).length;

  const alerts: string[] = [];
  if (dataAgeSec != null && dataAgeSec > 90) {
    alerts.push("Dados potencialmente desatualizados.");
  }
  if (dataAgeSec != null && dataAgeSec > 120) {
    alerts.push("Frequência de atualização abaixo do ideal.");
  }
  if (completePct < 70 && total > 0) {
    alerts.push("Há muitos mercados com campos incompletos.");
  }
  if (total > 0 && avoidCount > total * 0.35) {
    alerts.push("Muitos mercados em estado de evitar/revisar.");
  }
  if (total > 0 && fastMoving > total * 0.4) {
    alerts.push("Odds mudando rápido demais em múltiplos mercados.");
  }
  if (lowConfidence) {
    alerts.push("Baixa confiança média dos sinais.");
  }
  if (highEvLowConf > 0) {
    alerts.push("Há inconsistência entre EV alto e baixa confiança.");
  }
  if (data.scoreStale?.scoreStale || (data.scoreStale?.warnings?.length ?? 0) > 0) {
    alerts.push("Placar ou fonte pode estar divergente.");
  }
  if (isAdviceStale(data)) {
    alerts.push("Resposta Superbet veio de fallback/stale.");
  }
  for (const warning of data.liveStats?.warnings ?? []) {
    if (!alerts.includes(warning)) alerts.push(warning);
  }

  let score = 0;
  score += Math.round(avgConfidence * 35);
  score += Math.round((positiveEvPct / 100) * 20);
  score += Math.round((completePct / 100) * 20);
  if (dataAgeSec != null && dataAgeSec <= 30) score += 15;
  else if (dataAgeSec != null && dataAgeSec <= 90) score += 8;
  if (data.liveStats?.sofascoreAvailable) score += 5;
  if (data.liveStats?.scorealarmAvailable && !data.liveStats?.scorealarmStale) score += 5;
  if (!isAdviceStale(data)) score += 5;
  score -= alerts.length * 4;
  score = Math.max(0, Math.min(100, score));

  return {
    score,
    status: statusFromScore(score),
    avgConfidence,
    avgUpdateSec,
    completePct,
    positiveEvPct,
    alerts,
  };
}
