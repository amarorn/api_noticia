/** Odd Criar Aposta Superbet — SGM correlacionado vs produto das simples. */

export type CombinedOddsLeg = {
  market: string;
  outcome: string;
  marketOdd: number;
  modelProb?: number;
  superbetEventId?: number;
};

export type CombinedOddsResult = {
  combinedOdd: number;
  productOdd: number;
  pricingMode: "product" | "bet_builder_sgm" | "bet_builder_heuristic";
};

function isYesOutcome(outcome: string): boolean {
  const o = outcome.toLowerCase();
  return ["yes", "sim", "over", "1", "home", "away"].includes(o);
}

function isUnderOutcome(outcome: string): boolean {
  const o = outcome.toLowerCase();
  return ["no", "não", "nao", "under", "2", "x", "draw"].includes(o);
}

function periodOf(market: string): string {
  if (market.startsWith("1h_")) return "1h";
  if (market.startsWith("2h_")) return "2h";
  return "ft";
}

function isGoalsTotalMarket(market: string): boolean {
  const body = market.startsWith("1h_") || market.startsWith("2h_") ? market.slice(3) : market;
  return body.startsWith("over_") || body.startsWith("home_over_") || body.startsWith("away_over_");
}

/** Espelha models/bet_builder_odds.narrative_correlation_boost */
export function narrativeCorrelationBoost(legs: CombinedOddsLeg[]): number {
  if (legs.length < 2) return 1;

  const markets = legs.map((l) => l.market);
  const outcomes = legs.map((l) => l.outcome);
  let boost = 1;

  if (
    outcomes.every(isUnderOutcome) &&
    markets.every(isGoalsTotalMarket)
  ) {
    const periods = new Set(markets.map(periodOf));
    boost = Math.max(boost, periods.size >= 2 || (periods.has("1h") && periods.has("ft")) ? 1.38 : 1.22);
  }

  if (markets.some((m) => m === "btts") && markets.some(isGoalsTotalMarket)) {
    const bttsYes = markets.some(
      (m, i) => m === "btts" && isYesOutcome(outcomes[i] ?? ""),
    );
    const overYes = markets.some(
      (m, i) => isGoalsTotalMarket(m) && isYesOutcome(outcomes[i] ?? ""),
    );
    if (bttsYes && overYes) boost = Math.max(boost, 1.28);
  }

  return boost;
}

function productOdd(legs: CombinedOddsLeg[]): number {
  const p = legs.reduce((acc, leg) => acc * leg.marketOdd, 1);
  return Math.round(p * 100) / 100;
}

/** Mesmo evento + 2+ pernas: assume Criar Aposta (validação completa no backend). */
function sameEventBuilder(legs: CombinedOddsLeg[]): boolean {
  const ids = legs.map((l) => l.superbetEventId).filter((id) => id != null);
  if (ids.length !== legs.length) return false;
  return new Set(ids).size === 1;
}

export function resolveCombinedOdds(legs: CombinedOddsLeg[]): CombinedOddsResult {
  const simple = productOdd(legs);
  if (legs.length < 2 || !sameEventBuilder(legs)) {
    return { combinedOdd: simple, productOdd: simple, pricingMode: "product" };
  }

  const probs = legs.map((l) => l.modelProb);
  if (probs.every((p) => p != null && p > 0)) {
    const indepProb = probs.reduce<number>((acc, p) => acc * (p as number), 1);
    const boost = narrativeCorrelationBoost(legs);
    const jointProb = Math.min(0.95, indepProb * boost);
    const sgmOdd = Math.round((1 / jointProb) * 100) / 100;
    const final = Math.min(simple, sgmOdd);
    return { combinedOdd: final, productOdd: simple, pricingMode: "bet_builder_sgm" };
  }

  const boost = narrativeCorrelationBoost(legs);
  if (boost > 1.05) {
    return {
      combinedOdd: Math.round(simple * (1 / boost) * 100) / 100,
      productOdd: simple,
      pricingMode: "bet_builder_heuristic",
    };
  }

  return { combinedOdd: simple, productOdd: simple, pricingMode: "product" };
}

export function jointModelProb(legs: CombinedOddsLeg[], pricingMode: CombinedOddsResult["pricingMode"]): number | null {
  if (!pricingMode.startsWith("bet_builder")) return null;
  const probs = legs.map((l) => l.modelProb);
  if (!probs.every((p) => p != null && p > 0)) return null;
  const indep = probs.reduce<number>((acc, p) => acc * (p as number), 1);
  return Math.min(0.95, indep * narrativeCorrelationBoost(legs));
}
