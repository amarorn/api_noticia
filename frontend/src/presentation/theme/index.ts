import type { OutcomeLabel } from "@/domain/entities";

export const outcomeLabels: Record<OutcomeLabel, string> = {
  "1": "Vitória mandante",
  X: "Empate",
  "2": "Vitória visitante",
};

export function predictedWinner(
  prediction: OutcomeLabel,
  homeTeam: string,
  awayTeam: string,
): string {
  if (prediction === "1") return homeTeam;
  if (prediction === "2") return awayTeam;
  return "Empate";
}

export const outcomeColors: Record<string, string> = {
  "1": "#00ff88",
  X: "#00d4ff",
  "2": "#a855f7",
};

export const phases = [
  { value: "group", label: "Fase de grupos" },
  { value: "round_16", label: "Oitavas de final" },
  { value: "quarter", label: "Quartas de final" },
  { value: "semi", label: "Semifinal" },
  { value: "final", label: "Final" },
];

export function formatPercent(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function confidenceLevel(confidence: number): "low" | "medium" | "high" {
  if (confidence >= 0.55) return "high";
  if (confidence >= 0.4) return "medium";
  return "low";
}

export function confidenceColor(level: ReturnType<typeof confidenceLevel>): string {
  const map = { low: "#64748b", medium: "#00d4ff", high: "#00ff88" };
  return map[level];
}
