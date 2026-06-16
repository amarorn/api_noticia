/** Textos e utilitários — foco em probabilidade do modelo, não em odd/EV. */

export type BetTier = "forte" | "moderada" | "leve" | "abaixo_limiar" | string;
export type BetTiming = "agora" | "monitorar" | "aguardar" | string;

export interface BetInsightInput {
  label: string;
  market: string;
  outcome: string;
  modelProb: number;
  impliedProb: number;
  edgePp: number;
  tier?: BetTier;
  rank?: number;
  minute?: number;
  currentScore?: string;
  timing?: BetTiming;
  timingReason?: string;
  fundamentacao?: string;
  confidenceLabel?: string;
  confidenceScore?: number;
}

export const TIER_CONFIG: Record<
  string,
  { label: string; badgeClass: string; cardClass: string }
> = {
  forte: {
    label: "Melhor leitura",
    badgeClass: "bg-neon-green/25 text-neon-green border-neon-green/50",
    cardClass:
      "border-2 border-neon-green/55 bg-gradient-to-br from-neon-green/[0.14] via-neon-green/[0.06] to-transparent shadow-[0_0_28px_rgba(0,255,136,0.12)]",
  },
  moderada: {
    label: "Leitura sólida",
    badgeClass: "bg-emerald-500/20 text-emerald-300 border-emerald-400/40",
    cardClass:
      "border-2 border-emerald-400/45 bg-gradient-to-br from-emerald-500/[0.10] to-transparent shadow-[0_0_16px_rgba(52,211,153,0.08)]",
  },
  leve: {
    label: "Edge marginal",
    badgeClass: "bg-amber-500/15 text-amber-300 border-amber-500/35",
    cardClass: "border border-amber-500/35 bg-amber-500/[0.06]",
  },
};

export const TIMING_CONFIG: Record<
  string,
  { label: string; badgeClass: string; icon: string }
> = {
  agora: {
    label: "Entrar agora",
    badgeClass: "bg-neon-green/20 text-neon-green border-neon-green/40",
    icon: "●",
  },
  monitorar: {
    label: "Monitorar linha",
    badgeClass: "bg-sky-500/15 text-sky-300 border-sky-500/30",
    icon: "◐",
  },
  aguardar: {
    label: "Aguardar",
    badgeClass: "bg-amber-500/15 text-amber-300 border-amber-500/35",
    icon: "○",
  },
};

/** Explicação ancorada no modelo — usa fundamentacao da API quando disponível. */
export function buildBetReason(input: BetInsightInput): string {
  if (input.fundamentacao) {
    const timing = input.timingReason ? ` ${input.timingReason}` : "";
    return `${input.fundamentacao}${timing}`;
  }

  const modelPct = input.modelProb * 100;
  const impliedPct = input.impliedProb * 100;
  const lines: string[] = [];

  lines.push(
    `O ensemble in-play estima ${modelPct.toFixed(0)}% de probabilidade real. ` +
      `O mercado precifica ${impliedPct.toFixed(0)}% — vantagem de +${input.edgePp.toFixed(1)} pp para o modelo.`,
  );

  if (input.confidenceLabel && input.confidenceScore != null) {
    lines.push(
      `Confiança nos dados: ${input.confidenceLabel} (${(input.confidenceScore * 100).toFixed(0)}%).`,
    );
  }

  if (input.timingReason) {
    lines.push(input.timingReason);
  } else if (input.timing === "aguardar") {
    lines.push("Edge ainda insuficiente ou linha enxugando — aguardar próximo refresh.");
  }

  return lines.join(" ");
}

export function rankLabel(rank: number): string {
  if (rank === 1) return "#1 modelo";
  if (rank === 2) return "#2";
  if (rank === 3) return "#3";
  return `#${rank}`;
}

export type Verdict = "apostar" | "quase" | "sem_valor" | "sem_odds";

const VERDICT_ORDER: Record<Verdict, number> = {
  apostar: 0,
  quase: 1,
  sem_valor: 2,
  sem_odds: 3,
};

export function sortByVerdictAndEdge<
  T extends { verdict: Verdict; best: { edgePp: number; modelProb: number } | null },
>(cards: T[]): T[] {
  return [...cards].sort((a, b) => {
    const va = VERDICT_ORDER[a.verdict] ?? 9;
    const vb = VERDICT_ORDER[b.verdict] ?? 9;
    if (va !== vb) return va - vb;
    const edgeA = a.best?.edgePp ?? -999;
    const edgeB = b.best?.edgePp ?? -999;
    if (edgeA !== edgeB) return edgeB - edgeA;
    return (b.best?.modelProb ?? 0) - (a.best?.modelProb ?? 0);
  });
}

/** Barra visual: modelo vs mercado (não EV). */
export function probComparisonLabel(modelProb: number, impliedProb: number): string {
  const gap = (modelProb - impliedProb) * 100;
  const sign = gap >= 0 ? "+" : "";
  return `Modelo ${(modelProb * 100).toFixed(0)}% · Mercado ${(impliedProb * 100).toFixed(0)}% (${sign}${gap.toFixed(1)} pp)`;
}
