import type { SuperbetLiveAdvice } from "@/domain/entities";
import {
  buildScannedCombos,
  LONGSHOT_STAKE_BRL,
  type ComboBuildConfig,
  type ComboSortMode,
  type LongshotCombo,
} from "@/presentation/utils/longshotCombos";

export type ComboProfileId = "safe" | "balanced" | "longshot";

/** Passos do slider de odd mínima combinada. */
export const COMBO_MIN_ODD_STEPS = [3, 5, 8, 10, 20, 50, 100] as const;

export type ComboMinOddStep = (typeof COMBO_MIN_ODD_STEPS)[number];

export interface ComboProfileDefinition {
  id: ComboProfileId;
  label: string;
  hint: string;
  defaultMinOdd: ComboMinOddStep;
  maxCombinedOdd?: number;
  minCombinedProb?: number;
  minCombinedEv?: number;
  maxLegs: number;
  minLegOdd: number;
  sortBy: ComboSortMode;
  maxCombos: number;
}

export const COMBO_PROFILES: Record<ComboProfileId, ComboProfileDefinition> = {
  safe: {
    id: "safe",
    label: "Seguro",
    hint: "Odd @3–@8 · prioriza maior chance de bater",
    defaultMinOdd: 3,
    maxCombinedOdd: 8,
    minCombinedProb: 0.28,
    maxLegs: 2,
    minLegOdd: 1.2,
    sortBy: "prob",
    maxCombos: 4,
  },
  balanced: {
    id: "balanced",
    label: "Equilibrado",
    hint: "Odd @5–@50 · melhor EV combinado com pernas decorrelacionadas",
    defaultMinOdd: 5,
    maxCombinedOdd: 50,
    minCombinedEv: 0.05,
    maxLegs: 4,
    minLegOdd: 1.35,
    sortBy: "ev",
    maxCombos: 4,
  },
  longshot: {
    id: "longshot",
    label: "Longshot",
    hint: "Odd alta · maior hit est. entre as opções do patamar escolhido",
    defaultMinOdd: 20,
    maxLegs: 6,
    minLegOdd: 1.8,
    sortBy: "prob",
    maxCombos: 4,
  },
};

export const COMBO_PROFILE_UI: Record<
  ComboProfileId,
  { tabClass: string; activeTabClass: string; cardClass: string; badgeClass: string }
> = {
  safe: {
    tabClass: "border-white/10 text-slate-400 hover:border-emerald-400/30 hover:text-emerald-200",
    activeTabClass: "border-emerald-400/45 bg-emerald-500/15 text-emerald-100",
    cardClass:
      "border-emerald-400/30 bg-gradient-to-br from-emerald-500/[0.12] to-teal-800/[0.05]",
    badgeClass: "border-emerald-400/35 bg-emerald-500/15 text-emerald-200",
  },
  balanced: {
    tabClass: "border-white/10 text-slate-400 hover:border-sky-400/30 hover:text-sky-200",
    activeTabClass: "border-sky-400/45 bg-sky-500/15 text-sky-100",
    cardClass:
      "border-sky-400/25 bg-gradient-to-br from-sky-500/[0.10] to-indigo-800/[0.05]",
    badgeClass: "border-sky-400/30 bg-sky-500/15 text-sky-200",
  },
  longshot: {
    tabClass: "border-white/10 text-slate-400 hover:border-violet-400/30 hover:text-violet-200",
    activeTabClass: "border-violet-400/45 bg-violet-500/15 text-violet-100",
    cardClass:
      "border-violet-400/25 bg-gradient-to-br from-violet-500/[0.10] to-fuchsia-900/[0.05]",
    badgeClass: "border-violet-400/30 bg-violet-500/15 text-violet-200",
  },
};

type MarketScan = NonNullable<SuperbetLiveAdvice["strategy"]>["marketScan"];

export function buildProfileCombos(
  scan: MarketScan | undefined,
  profileId: ComboProfileId,
  options?: {
    minCombinedOdd?: number;
    stake?: number;
    halfMarkets?: SuperbetLiveAdvice["halfMarkets"];
  },
): LongshotCombo[] {
  const profile = COMBO_PROFILES[profileId];
  const minCombinedOdd = options?.minCombinedOdd ?? profile.defaultMinOdd;
  let maxCombinedOdd = profile.maxCombinedOdd;
  if (maxCombinedOdd != null && minCombinedOdd > maxCombinedOdd) {
    maxCombinedOdd = undefined;
  }

  const config: ComboBuildConfig = {
    stake: options?.stake ?? LONGSHOT_STAKE_BRL,
    minCombinedOdd,
    maxCombinedOdd,
    minCombinedProb: profile.minCombinedProb,
    minCombinedEv: profile.minCombinedEv,
    maxLegs: profile.maxLegs,
    minLegOdd: profile.minLegOdd,
    maxCombos: profile.maxCombos,
    sortBy: profile.sortBy,
    halfMarkets: options?.halfMarkets,
  };

  return buildScannedCombos(scan, config);
}

export function nearestMinOddStep(value: number): ComboMinOddStep {
  let best: ComboMinOddStep = COMBO_MIN_ODD_STEPS[0];
  let bestDist = Math.abs(value - best);
  for (const step of COMBO_MIN_ODD_STEPS) {
    const dist = Math.abs(value - step);
    if (dist < bestDist) {
      best = step;
      bestDist = dist;
    }
  }
  return best;
}
