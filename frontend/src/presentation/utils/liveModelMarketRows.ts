import type { SuperbetLiveAdvice } from "@/domain/entities";

export interface ModelMarketRow {
  id: string;
  group: "h2h" | "market";
  label: string;
  shortLabel?: string;
  modelProb: number;
  marketOdd: number;
  expectedValue: number;
  meetsThreshold: boolean;
}

export const EV_STRONG_THRESHOLD = 0.07;
export const EV_WEAK_THRESHOLD = -0.1;

export function evFromProb(prob: number, odd: number): number {
  return prob * odd - 1;
}

export function evDisplayTone(
  ev: number,
  minEdge = 0.04,
): { bg: string; text: string; icon: string } {
  if (ev >= EV_STRONG_THRESHOLD) {
    return { bg: "bg-neon-green/20", text: "text-neon-green", icon: "✅" };
  }
  if (ev < EV_WEAK_THRESHOLD) {
    return { bg: "bg-red-500/15", text: "text-red-400", icon: "❌" };
  }
  if (ev >= minEdge) {
    return { bg: "bg-emerald-500/10", text: "text-emerald-300", icon: "🟢" };
  }
  return { bg: "bg-amber-500/10", text: "text-amber-300", icon: "🟡" };
}

function pushRow(
  rows: ModelMarketRow[],
  spec: {
    id: string;
    group: "h2h" | "market";
    label: string;
    shortLabel?: string;
    prob: number | undefined;
    odd: number | undefined;
    threshold: number;
  },
) {
  const { prob, odd } = spec;
  if (prob == null || prob <= 0 || odd == null || odd <= 1) return;
  const ev = evFromProb(prob, odd);
  rows.push({
    id: spec.id,
    group: spec.group,
    label: spec.label,
    shortLabel: spec.shortLabel,
    modelProb: prob,
    marketOdd: odd,
    expectedValue: ev,
    meetsThreshold: ev >= spec.threshold,
  });
}

/** Linhas 1X2 a partir de odds + probabilidades in-play. */
export function buildH2hMarketRows(
  data: SuperbetLiveAdvice,
  threshold: number,
): ModelMarketRow[] {
  const s = data.inplaySummary;
  const rows: ModelMarketRow[] = [];
  pushRow(rows, {
    id: "h2h-1",
    group: "h2h",
    label: data.homeTeam,
    shortLabel: "1",
    prob: s.probFinalHome,
    odd: data.h2hOdds["1"],
    threshold,
  });
  pushRow(rows, {
    id: "h2h-X",
    group: "h2h",
    label: "Empate",
    shortLabel: "X",
    prob: s.probFinalDraw,
    odd: data.h2hOdds["X"],
    threshold,
  });
  pushRow(rows, {
    id: "h2h-2",
    group: "h2h",
    label: data.awayTeam,
    shortLabel: "2",
    prob: s.probFinalAway,
    odd: data.h2hOdds["2"],
    threshold,
  });
  return rows;
}

/** Mercados-chave (totais, BTTS, próximo gol) — scan ou fallback. */
export function buildExtraMarketRows(
  data: SuperbetLiveAdvice,
  threshold: number,
  maxRows = 6,
): ModelMarketRow[] {
  const scan = data.strategy?.marketScan ?? [];
  const fromScan = scan
    .filter((r) => r.market !== "h2h" && r.marketOdd > 1 && r.modelProb > 0)
    .sort((a, b) => b.expectedValue - a.expectedValue)
    .slice(0, maxRows)
    .map((r) => ({
      id: `${r.market}-${r.outcome}`,
      group: "market" as const,
      label: r.label,
      modelProb: r.modelProb,
      marketOdd: r.marketOdd,
      expectedValue: r.expectedValue,
      meetsThreshold: r.meetsThreshold,
    }));

  if (fromScan.length > 0) return fromScan;

  const s = data.inplaySummary;
  const fallback: ModelMarketRow[] = [];
  const aporteOver = data.aportes.find((a) => a.market === "over_2_5");
  pushRow(fallback, {
    id: "over_2_5-yes",
    group: "market",
    label: "Mais de 2.5 gols",
    prob: s.over25,
    odd: aporteOver?.marketOdd,
    threshold,
  });
  pushRow(fallback, {
    id: "btts-yes",
    group: "market",
    label: "Ambos marcam",
    prob: s.btts,
    odd: data.bttsOdds.yes,
    threshold,
  });
  pushRow(fallback, {
    id: "btts-no",
    group: "market",
    label: "Ambos não marcam",
    prob: s.btts != null ? 1 - s.btts : undefined,
    odd: data.bttsOdds.no,
    threshold,
  });
  pushRow(fallback, {
    id: "next_goal-home",
    group: "market",
    label: `Próximo gol ${data.homeTeam}`,
    prob: s.probNextGoalHome,
    odd: data.nextGoalOdds.home,
    threshold,
  });
  pushRow(fallback, {
    id: "next_goal-away",
    group: "market",
    label: `Próximo gol ${data.awayTeam}`,
    prob: s.probNextGoalAway,
    odd: data.nextGoalOdds.away,
    threshold,
  });

  return fallback
    .sort((a, b) => b.expectedValue - a.expectedValue)
    .slice(0, maxRows);
}

export function bestMarketRow(rows: ModelMarketRow[]): ModelMarketRow | null {
  if (!rows.length) return null;
  return rows.reduce((best, row) =>
    row.expectedValue > best.expectedValue ? row : best,
  );
}

/** EV se a odd cair para `targetOdd` mantendo a mesma prob do modelo. */
export function evAtOdd(modelProb: number, targetOdd: number): number {
  return evFromProb(modelProb, targetOdd);
}

export function sensitivityOddSteps(
  modelProb: number,
  currentOdd: number,
  steps: number[] = [-0.15, -0.1, -0.05, 0.05],
): Array<{ odd: number; ev: number }> {
  return steps
    .map((delta) => {
      const odd = Math.max(1.01, currentOdd + delta);
      return { odd, ev: evAtOdd(modelProb, odd) };
    })
    .filter((s) => s.odd > 1);
}
