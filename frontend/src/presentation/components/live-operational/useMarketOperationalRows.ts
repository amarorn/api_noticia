import { useEffect, useMemo, useState } from "react";
import type { SuperbetLiveAdvice } from "@/domain/entities";

export interface OddsHistoryPoint {
  odd: number;
  capturedAt: string;
}

export interface MarketOperationalRow {
  key: string;
  label: string;
  market: string;
  outcome: string;
  type: string;
  period: string;
  marketOdd: number;
  fairOdd: number | null;
  modelProb: number;
  impliedProb: number;
  expectedValue: number;
  edgePp: number;
  suggestedStakeValue: number;
  pressureEstimate: number;
  pressureLabel: string;
  direction: "encurtando" | "esticando" | "estavel" | "novo";
  lastChangedAt: string | null;
  lastChangedAgeSec: number | null;
  confidenceScore: number;
  status: "ativo" | "aguardar" | "evitar";
  action: string;
}

type ScanRow = NonNullable<SuperbetLiveAdvice["strategy"]>["marketScan"][number];

function inferMarketType(market: string, label: string): string {
  const blob = `${market} ${label}`.toLowerCase();
  if (blob.includes("falta") || market.startsWith("fouls_")) return "Faltas";
  if (blob.includes("dupla chance") || /^(?:1h_|2h_)?dc_/.test(market)) return "Dupla chance";
  if (blob.includes("empate anula") || /^(?:1h_|2h_)?dnb_/.test(market)) return "DNB";
  if (blob.includes("hcap3") || blob.includes("3-way")) return "Handicap 3-way";
  if (blob.includes("corner") || blob.includes("escanteio")) return "Escanteios";
  if (blob.includes("yellow") || blob.includes("cartão") || blob.includes("cartao")) return "Cartões";
  if (blob.includes("handicap")) return "Handicap";
  if (market === "h2h") return "Resultado";
  if (
    blob.includes("over") ||
    blob.includes("under") ||
    blob.includes("total") ||
    blob.includes("gol")
  ) {
    return "Gols";
  }
  return "Outros";
}

function inferPeriod(market: string, label: string): string {
  const blob = `${market} ${label}`.toLowerCase();
  if (blob.includes("1t") || blob.includes("1º tempo") || blob.includes("first_half")) return "1T";
  if (blob.includes("2t") || blob.includes("2º tempo") || blob.includes("second_half")) return "2T";
  return "Jogo";
}

function impliedPressureLabel(pct: number): string {
  if (pct >= 60) return "alta";
  if (pct >= 40) return "média";
  return "baixa";
}

function resolveDirection(
  key: string,
  odd: number,
  history: Record<string, OddsHistoryPoint[]>,
): MarketOperationalRow["direction"] {
  const points = history[key] ?? [];
  if (points.length <= 1) return points.length === 1 ? "novo" : "estavel";
  const prev = points[points.length - 2]?.odd;
  if (prev == null) return "estavel";
  const delta = odd - prev;
  if (Math.abs(delta) < 0.02) return "estavel";
  return delta < 0 ? "encurtando" : "esticando";
}

function rowConfidence(data: SuperbetLiveAdvice, row: ScanRow): number {
  const base = data.confidence?.score ?? 0.45;
  const edgeBoost = Math.min(0.25, Math.max(0, row.expectedValue) * 0.8);
  const thresholdBoost = row.meetsThreshold ? 0.1 : 0;
  return Math.min(0.98, Math.max(0.05, base * 0.55 + edgeBoost + thresholdBoost));
}

function rowStatus(row: ScanRow, minEdge: number): MarketOperationalRow["status"] {
  if (row.expectedValue < -0.04) return "evitar";
  if (row.meetsThreshold && row.expectedValue >= minEdge) return "ativo";
  if (row.expectedValue > 0) return "aguardar";
  return "evitar";
}

function scanToRow(
  data: SuperbetLiveAdvice,
  row: ScanRow,
  history: Record<string, OddsHistoryPoint[]>,
): MarketOperationalRow {
  const key = `${row.market}:${row.outcome}`;
  const minEdge = data.strategy?.minEdgeThreshold ?? 0.04;
  const fairOdd = row.modelProb > 0 ? 1 / row.modelProb : null;
  const pressureEstimate = Math.min(
    100,
    Math.max(
      0,
      Math.round(Math.abs(row.impliedProb - row.modelProb) * 100 + Math.max(0, row.expectedValue) * 40),
    ),
  );
  const dataAgeSec = data.capturedAt
    ? Math.max(0, Math.floor((Date.now() - Date.parse(data.capturedAt)) / 1000))
    : null;

  return {
    key,
    label: row.label,
    market: row.market,
    outcome: row.outcome,
    type: inferMarketType(row.market, row.label),
    period: inferPeriod(row.market, row.label),
    marketOdd: row.marketOdd,
    fairOdd,
    modelProb: row.modelProb,
    impliedProb: row.impliedProb,
    expectedValue: row.expectedValue,
    edgePp: row.edgePp,
    suggestedStakeValue: row.suggestedStakeValue,
    pressureEstimate,
    pressureLabel: impliedPressureLabel(pressureEstimate),
    direction: resolveDirection(key, row.marketOdd, history),
    lastChangedAt: data.capturedAt,
    lastChangedAgeSec: dataAgeSec,
    confidenceScore: rowConfidence(data, row),
    status: rowStatus(row, minEdge),
    action: row.meetsThreshold && row.expectedValue >= minEdge ? "apostar" : "monitorar",
  };
}

function buildRowsFromAdvice(
  data: SuperbetLiveAdvice,
  history: Record<string, OddsHistoryPoint[]>,
): MarketOperationalRow[] {
  const scan = data.strategy?.marketScan ?? [];
  const fromScan = scan
    .filter((r) => r.marketOdd > 1 && r.modelProb > 0)
    .map((r) => scanToRow(data, r, history));

  if (fromScan.length > 0) {
    return fromScan.sort((a, b) => b.expectedValue - a.expectedValue);
  }

  return (data.aportes ?? [])
    .filter((a) => a.marketOdd > 1 && a.modelProb > 0)
    .map((a) => {
      const impliedProb = 1 / a.marketOdd;
      const row: ScanRow = {
        market: a.market,
        outcome: a.outcome,
        label: a.label,
        modelProb: a.modelProb,
        marketOdd: a.marketOdd,
        impliedProb,
        expectedValue: a.expectedValue,
        edgePp: a.edgePp,
        suggestedStakePct: a.suggestedStakePct ?? 0,
        suggestedStakeValue: a.suggestedStakeValue ?? 0,
        meetsThreshold: a.action === "apostar",
      };
      return scanToRow(data, row, history);
    })
    .sort((a, b) => b.expectedValue - a.expectedValue);
}

export function useMarketOperationalRows(data: SuperbetLiveAdvice) {
  const [history, setHistory] = useState<Record<string, OddsHistoryPoint[]>>({});

  const rows = useMemo(() => buildRowsFromAdvice(data, history), [data, history]);

  useEffect(() => {
    if (!data?.capturedAt) return;
    const capturedAt = data.capturedAt;
    setHistory((prev) => {
      const next = { ...prev };
      for (const row of buildRowsFromAdvice(data, prev)) {
        const points = [...(next[row.key] ?? [])];
        const last = points[points.length - 1];
        if (!last || last.odd !== row.marketOdd) {
          points.push({ odd: row.marketOdd, capturedAt });
        }
        next[row.key] = points.slice(-32);
      }
      return next;
    });
  }, [data]);

  useEffect(() => {
    setHistory({});
  }, [data?.superbetEventId]);

  return { rows, history };
}
