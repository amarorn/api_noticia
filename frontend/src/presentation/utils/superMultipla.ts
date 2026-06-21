import type { LongshotCombo } from "@/presentation/utils/longshotCombos";

/** Promo Superbet — espelha config backend (SUPER_MULTIPLA_*). */
export const SUPER_MULTIPLA_MIN_LEG_ODD = 1.35;
export const SUPER_MULTIPLA_BONUS_PCT = 0.05;

export interface SuperMultiplaEnrichedCombo extends LongshotCombo {
  bonusEligible: boolean;
  bonusPercentage: number;
  finalReturn: number;
}

export interface SuperMultiplaCalculateLeg {
  id?: string;
  market: string;
  outcome: string;
  market_odd: number;
  model_prob?: number;
  superbet_event_id?: number;
  event_name?: string;
  selection_label?: string;
  is_live?: boolean;
  minute?: number;
}

export interface SuperMultiplaCalculateResult {
  slipId: string | null;
  totalOdds: number;
  productOdds: number | null;
  pricingMode: "product" | "bet_builder_sgm" | "bet_builder_heuristic";
  potentialPayout: number;
  bonusEligible: boolean;
  bonusPercentage: number;
  finalPayout: number;
  combinedProb: number | null;
  combinedEv: number | null;
  currency: string;
  warnings: string[];
  builderValidation: Record<string, unknown> | null;
  betType: "SIMPLE" | "MULTIPLE";
  legsCount: number;
}

function roundMoney(value: number): number {
  return Math.round(value * 100) / 100;
}

/** Elegibilidade promo quando todas as pernas têm odd >= 1.35. */
export function isSuperMultiplaBonusEligible(legs: { marketOdd: number }[]): boolean {
  return legs.length >= 2 && legs.every((leg) => leg.marketOdd >= SUPER_MULTIPLA_MIN_LEG_ODD);
}

/** Enriquece combo longshot com retorno final (+5% se elegível). */
export function applySuperMultiplaBonus(combo: LongshotCombo): SuperMultiplaEnrichedCombo {
  const bonusEligible = isSuperMultiplaBonusEligible(combo.legs);
  const bonusPercentage = bonusEligible ? SUPER_MULTIPLA_BONUS_PCT : 0;
  const finalReturn = bonusEligible
    ? roundMoney(combo.potentialReturn * (1 + SUPER_MULTIPLA_BONUS_PCT))
    : combo.potentialReturn;
  return {
    ...combo,
    bonusEligible,
    bonusPercentage,
    finalReturn,
  };
}

export function mapSuperMultiplaCalculate(raw: Record<string, unknown>): SuperMultiplaCalculateResult {
  return {
    slipId: (raw.slip_id as string | null) ?? null,
    totalOdds: Number(raw.total_odds),
    productOdds: raw.product_odds != null ? Number(raw.product_odds) : null,
    pricingMode:
      (raw.pricing_mode as SuperMultiplaCalculateResult["pricingMode"]) ?? "product",
    potentialPayout: Number(raw.potential_payout),
    bonusEligible: Boolean(raw.bonus_eligible),
    bonusPercentage: Number(raw.bonus_percentage ?? 0),
    finalPayout: Number(raw.final_payout),
    combinedProb: raw.combined_prob != null ? Number(raw.combined_prob) : null,
    combinedEv: raw.combined_ev != null ? Number(raw.combined_ev) : null,
    currency: String(raw.currency ?? "BRL"),
    warnings: Array.isArray(raw.warnings) ? (raw.warnings as string[]) : [],
    builderValidation: (raw.builder_validation as Record<string, unknown>) ?? null,
    betType: (raw.bet_type as "SIMPLE" | "MULTIPLE") ?? "MULTIPLE",
    legsCount: Number(raw.legs_count ?? 0),
  };
}
