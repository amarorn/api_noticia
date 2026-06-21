/**
 * Monitor de anomalias ao vivo.
 *
 * Compara snapshots consecutivos de dados do modelo e emite alertas quando:
 * - Probabilidade de um resultado cai significativamente (≥ DROP_THRESHOLD)
 * - Postura muda de apostar → aguardar/neutro
 * - EV de um pick forte vira negativo
 * - Velocidade de queda é acelerada (2 quedas consecutivas)
 */
import { useEffect, useRef } from "react";

import type { SuperbetLiveAdvice } from "@/domain/entities";

export type AlertSeverity = "critical" | "warning" | "info";

export interface OddsDropAlert {
  id: string;
  severity: AlertSeverity;
  market: string;
  label: string;
  message: string;
  prevProb: number;
  currProb: number;
  delta: number;
  minute: number;
  timestamp: number;
}

interface Snapshot {
  minute: number;
  timestamp: number;
  probHome: number;
  probDraw: number;
  probAway: number;
  posture: string;
  marketProbs: Record<string, { prob: number; ev: number; label: string }>;
}

const DROP_CRITICAL = 0.12; // queda ≥ 12pp → crítico
const DROP_WARNING = 0.07;  // queda ≥ 7pp → aviso
const MAX_SNAPSHOTS = 6;    // janela deslizante de snapshots
const SAME_MINUTE_GUARD = 2; // não repetir alerta no mesmo minuto ± 2

function buildSnapshot(data: SuperbetLiveAdvice): Snapshot {
  const marketProbs: Record<string, { prob: number; ev: number; label: string }> = {};

  // Coleta probs do market_scan
  const scan = (data.strategy as Record<string, unknown>)?.market_scan as
    | Array<{ market: string; outcome: string; model_prob: number; expected_value: number; label: string }>
    | undefined;

  if (Array.isArray(scan)) {
    for (const item of scan) {
      const key = `${item.market}__${item.outcome}`;
      marketProbs[key] = {
        prob: item.model_prob ?? 0,
        ev: item.expected_value ?? 0,
        label: item.label ?? item.market,
      };
    }
  }

  return {
    minute: data.minute ?? 0,
    timestamp: Date.now(),
    probHome: data.inplaySummary?.probFinalHome ?? 0,
    probDraw: data.inplaySummary?.probFinalDraw ?? 0,
    probAway: data.inplaySummary?.probFinalAway ?? 0,
    posture: (data.strategy as Record<string, unknown>)?.posture as string ?? "neutro",
    marketProbs,
  };
}

function detectAlerts(prev: Snapshot, curr: Snapshot): OddsDropAlert[] {
  const alerts: OddsDropAlert[] = [];
  const minute = curr.minute;

  // Ignora se mesmo minuto (nada mudou de fato)
  if (Math.abs(curr.minute - prev.minute) < SAME_MINUTE_GUARD && curr.timestamp - prev.timestamp < 25_000) {
    return alerts;
  }

  // 1. Queda nas probs de resultado FT
  const ftChecks: Array<{ key: string; label: string; prev: number; curr: number }> = [
    { key: "h2h__1", label: "Casa vence (FT)", prev: prev.probHome, curr: curr.probHome },
    { key: "h2h__X", label: "Empate (FT)", prev: prev.probDraw, curr: curr.probDraw },
    { key: "h2h__2", label: "Visitante vence (FT)", prev: prev.probAway, curr: curr.probAway },
  ];

  for (const c of ftChecks) {
    const delta = c.curr - c.prev;
    if (delta <= -DROP_CRITICAL) {
      alerts.push({
        id: `${c.key}_${minute}`,
        severity: "critical",
        market: c.key,
        label: c.label,
        message: `Queda abrupta de ${Math.abs(delta * 100).toFixed(1)}pp em "${c.label}" — considere cash-out ou saída.`,
        prevProb: c.prev,
        currProb: c.curr,
        delta,
        minute,
        timestamp: curr.timestamp,
      });
    } else if (delta <= -DROP_WARNING) {
      alerts.push({
        id: `${c.key}_${minute}`,
        severity: "warning",
        market: c.key,
        label: c.label,
        message: `Probabilidade de "${c.label}" caiu ${Math.abs(delta * 100).toFixed(1)}pp — atenção.`,
        prevProb: c.prev,
        currProb: c.curr,
        delta,
        minute,
        timestamp: curr.timestamp,
      });
    }
  }

  // 2. Postura piorou
  const postureRank: Record<string, number> = { apostar: 3, aporte: 2, moderado: 2, neutro: 1, aguardar: 0 };
  const prevRank = postureRank[prev.posture] ?? 1;
  const currRank = postureRank[curr.posture] ?? 1;
  if (currRank < prevRank && prevRank >= 2) {
    alerts.push({
      id: `posture_${minute}`,
      severity: currRank === 0 ? "critical" : "warning",
      market: "posture",
      label: "Postura do modelo",
      message: `Postura mudou de "${prev.posture}" → "${curr.posture}". Modelo reduz apetite por novas entradas.`,
      prevProb: prevRank / 3,
      currProb: currRank / 3,
      delta: (currRank - prevRank) / 3,
      minute,
      timestamp: curr.timestamp,
    });
  }

  // 3. EV de picks fortes virou negativo
  for (const [key, currItem] of Object.entries(curr.marketProbs)) {
    const prevItem = prev.marketProbs[key];
    if (!prevItem) continue;
    if (prevItem.ev > 0.10 && currItem.ev < -0.05) {
      alerts.push({
        id: `ev_flip_${key}_${minute}`,
        severity: "warning",
        market: key.split("__")[0],
        label: currItem.label,
        message: `EV de "${currItem.label}" virou negativo (${(currItem.ev * 100).toFixed(1)}%) — edge erosão.`,
        prevProb: prevItem.prob,
        currProb: currItem.prob,
        delta: currItem.prob - prevItem.prob,
        minute,
        timestamp: curr.timestamp,
      });
    }
  }

  return alerts;
}

export function useOddsDropMonitor(
  data: SuperbetLiveAdvice | null | undefined,
  onAlerts: (alerts: OddsDropAlert[]) => void,
) {
  const snapshots = useRef<Snapshot[]>([]);

  useEffect(() => {
    if (!data) return;

    const curr = buildSnapshot(data);
    const history = snapshots.current;

    if (history.length > 0) {
      const prev = history[history.length - 1];
      const alerts = detectAlerts(prev, curr);
      if (alerts.length > 0) onAlerts(alerts);
    }

    // Mantém janela deslizante
    snapshots.current = [...history, curr].slice(-MAX_SNAPSHOTS);
  }, [data]); // eslint-disable-line react-hooks/exhaustive-deps
}
