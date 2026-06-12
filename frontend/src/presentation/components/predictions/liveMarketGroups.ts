/** Grupos de mercado ao vivo — compartilhado entre cards e guia. */

export interface MarketGroup {
  id: string;
  superbetName: string;
  matchMarket: (market: string) => boolean;
  note?: string;
}

export interface MarketSection {
  id: string;
  title: string;
  groups: MarketGroup[];
}

export const CORE_MARKET_GROUPS: MarketGroup[] = [
  {
    id: "h2h",
    superbetName: "Resultado Final",
    matchMarket: (m) => m === "h2h",
    note: "Pode suspender ao vivo — use Total ou 2º Gol se sumir.",
  },
  {
    id: "next_goal",
    superbetName: "2º Gol",
    matchMarket: (m) => m === "next_goal",
  },
  {
    id: "totals",
    superbetName: "Total de Gols",
    matchMarket: (m) =>
      m.startsWith("over_") &&
      !m.startsWith("home_") &&
      !m.startsWith("away_") &&
      !m.startsWith("1h_") &&
      !m.startsWith("2h_"),
  },
  {
    id: "btts",
    superbetName: "Ambas as Equipes Marcam",
    matchMarket: (m) => m === "btts",
  },
  {
    id: "team_totals",
    superbetName: "Total por Time",
    matchMarket: (m) => m.startsWith("home_over_") || m.startsWith("away_over_"),
  },
  {
    id: "combos",
    superbetName: "Combos",
    matchMarket: (m) => m.startsWith("combo_"),
    note: "Mercados combinados: BTTS+Gols, Time+BTTS",
  },
];

function halfGroups(period: "1h" | "2h", label: string): MarketGroup[] {
  return [
    {
      id: `${period}_totals`,
      superbetName: `${label} — Total de Gols`,
      matchMarket: (m) => m.startsWith(`${period}_over_`),
    },
    {
      id: `${period}_h2h`,
      superbetName: `${label} — Resultado Final`,
      matchMarket: (m) => m === `${period}_h2h`,
    },
    {
      id: `${period}_cs`,
      superbetName: `${label} — Resultado Correto`,
      matchMarket: (m) => m.startsWith(`${period}_cs_`),
    },
    {
      id: `${period}_exact`,
      superbetName: `${label} — Número Exato de Gols`,
      matchMarket: (m) => m.startsWith(`${period}_exact_`),
    },
    {
      id: `${period}_hcap`,
      superbetName: `${label} — Handicap`,
      matchMarket: (m) => m.startsWith(`${period}_hcap_`),
    },
  ];
}

export const MARKET_SECTIONS: MarketSection[] = [
  { id: "core", title: "Jogo completo", groups: CORE_MARKET_GROUPS },
  { id: "1h", title: "1º Tempo", groups: halfGroups("1h", "1º Tempo") },
  { id: "2h", title: "2º Tempo", groups: halfGroups("2h", "2º Tempo") },
];

export type Verdict = "apostar" | "quase" | "sem_valor" | "sem_odds";

export const VERDICT_CONFIG: Record<
  Verdict,
  { label: string; cardClass: string; badgeClass: string; icon: string }
> = {
  apostar: {
    label: "Apostar",
    cardClass: "border-neon-green/50 bg-neon-green/[0.07] shadow-[0_0_20px_rgba(0,255,136,0.06)]",
    badgeClass: "bg-neon-green/20 text-neon-green border border-neon-green/40",
    icon: "●",
  },
  quase: {
    label: "Quase",
    cardClass: "border-amber-500/40 bg-amber-500/[0.05]",
    badgeClass: "bg-amber-500/15 text-amber-300 border border-amber-500/35",
    icon: "◐",
  },
  sem_valor: {
    label: "Sem valor",
    cardClass: "border-white/10 bg-white/[0.02]",
    badgeClass: "bg-white/5 text-slate-400 border border-white/10",
    icon: "○",
  },
  sem_odds: {
    label: "Sem odds",
    cardClass: "border-white/6 bg-transparent opacity-60",
    badgeClass: "bg-white/[0.03] text-slate-600 border border-white/8",
    icon: "—",
  },
};
