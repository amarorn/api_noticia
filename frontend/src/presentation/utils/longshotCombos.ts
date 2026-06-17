import type { SuperbetLiveAdvice } from "@/domain/entities";

export const LONGSHOT_STAKE_BRL = 5;
export const LONGSHOT_MIN_RETURN_BRL = 500;
export const LONGSHOT_MIN_COMBINED_ODD =
  LONGSHOT_MIN_RETURN_BRL / LONGSHOT_STAKE_BRL;

type MarketScanRow = NonNullable<SuperbetLiveAdvice["strategy"]>["marketScan"][number];

export type LongshotRiskTier = "best" | "moderate" | "extreme";

export interface LongshotLeg {
  market: string;
  outcome: string;
  label: string;
  marketOdd: number;
  modelProb: number;
}

export interface LongshotCombo {
  id: string;
  legs: LongshotLeg[];
  combinedOdd: number;
  stake: number;
  potentialReturn: number;
  combinedProb: number;
  combinedEv: number;
  riskTier: LongshotRiskTier;
  rank: number;
}

function periodOf(market: string): string {
  if (market.startsWith("1h_")) return "1h";
  if (market.startsWith("2h_")) return "2h";
  return "ft";
}

function totalsBucket(market: string): { period: string; family: string } | null {
  let period = "ft";
  let body = market;
  if (market.startsWith("1h_")) {
    period = "1h";
    body = market.slice(3);
  } else if (market.startsWith("2h_")) {
    period = "2h";
    body = market.slice(3);
  }

  if (body.startsWith("home_over_")) return { period, family: "home" };
  if (body.startsWith("away_over_")) return { period, family: "away" };
  if (body.startsWith("corners_over_")) return { period, family: "corners" };
  if (body.startsWith("cards_over_")) return { period, family: "cards" };
  if (body.startsWith("over_")) return { period, family: "goals" };
  return null;
}

function legFamily(market: string): string {
  if (market.endsWith("_h2h") || market === "h2h") return "h2h";
  if (market.includes("cs_") || market.includes("exact") || market.includes("over_")) {
    return "goals";
  }
  if (market.includes("hcap") || market.includes("_ah_")) return "handicap";
  return "other";
}

/** Mercados aceitos no Criar Aposta Superbet (exclui AH e handicap de período). */
export function isSuperbetBetBuilderMarket(market: string): boolean {
  if (market.includes("_ah_")) return false;
  if (/^(1h|2h)_hcap_/.test(market)) return false;
  if (market.includes("hcap") && !market.startsWith("ft_hcap_")) return false;
  return true;
}

function isCorrectScoreMarket(market: string): boolean {
  return market.includes("_cs_");
}

function isBttsMarket(market: string): boolean {
  return market === "btts";
}

/** Superbet rejeita BTTS + Resultado Correto no Criar Aposta. */
function bttsConflictsCorrectScore(aMarket: string, bMarket: string): boolean {
  return (
    (isBttsMarket(aMarket) && isCorrectScoreMarket(bMarket)) ||
    (isBttsMarket(bMarket) && isCorrectScoreMarket(aMarket))
  );
}

function correctScoresConflict(aMarket: string, bMarket: string): boolean {
  if (!isCorrectScoreMarket(aMarket) || !isCorrectScoreMarket(bMarket)) return false;
  return periodOf(aMarket) === periodOf(bMarket);
}

function correctScoreLegCount(legs: LongshotLeg[]): number {
  return legs.filter((leg) => isCorrectScoreMarket(leg.market)).length;
}

function handicapLegCount(legs: LongshotLeg[]): number {
  return legs.filter((leg) => legFamily(leg.market) === "handicap").length;
}

function isH2hMarket(market: string): boolean {
  return market === "h2h" || market.endsWith("_h2h");
}

function h2hPeriod(market: string): string {
  return market === "h2h" ? "ft" : periodOf(market);
}

function h2hOutcomeSide(outcome: string): "home" | "away" | "draw" | null {
  const o = outcome.toLowerCase();
  if (o === "1" || o === "home") return "home";
  if (o === "2" || o === "away") return "away";
  if (o === "x" || o === "draw") return "draw";
  return null;
}

interface ParsedHandicap {
  period: string;
  side: "home" | "away";
  line: number;
}

function parseHandicapLine(lineKey: string): number | null {
  if (lineKey === "0") return 0;
  if (lineKey.startsWith("m")) {
    const n = parseFloat(lineKey.slice(1).replace("_", "."));
    return Number.isFinite(n) ? -n : null;
  }
  if (lineKey.startsWith("p")) {
    const n = parseFloat(lineKey.slice(1).replace("_", "."));
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function parseHandicapMarket(market: string): ParsedHandicap | null {
  const match = market.match(/^(ft|1h|2h)_hcap_(home|away)_(.+)$/);
  if (!match) return null;
  const line = parseHandicapLine(match[3]);
  if (line == null) return null;
  return { period: match[1], side: match[2] as "home" | "away", line };
}

type HalfMarkets = SuperbetLiveAdvice["halfMarkets"];

/** Só aceita handicap se o botão exato existir no snapshot Superbet. */
export function isHandicapLegOnBook(
  halfMarkets: HalfMarkets | undefined,
  market: string,
): boolean {
  const match = market.match(/^(ft|1h|2h)_(hcap|ah)_(home|away)_(.+)$/);
  if (!match) return true;
  const [, period, kind, side, lineKey] = match;
  const bucket = kind === "ah" ? "asian_handicap" : "handicap";
  const pm = halfMarkets?.[period] as
    | Record<string, Record<string, Record<string, number>>>
    | undefined;
  const lines = pm?.[bucket];
  return lines?.[lineKey]?.[side] != null;
}

/** Espelhos (-1.5 casa vs +1.5 fora) e múltiplos handicaps no mesmo período. */
function handicapsConflict(aMarket: string, bMarket: string): boolean {
  const ha = parseHandicapMarket(aMarket);
  const hb = parseHandicapMarket(bMarket);
  if (!ha || !hb || ha.period !== hb.period) return false;

  if (ha.side === hb.side && ha.line !== hb.line) return true;
  if (ha.side !== hb.side && Math.abs(ha.line + hb.line) < 0.01) return true;
  if (ha.side !== hb.side && ha.line <= -0.5 && hb.line <= -0.5) return true;
  return true;
}

function h2hConflictsHandicap(
  h2hMarket: string,
  h2hOutcome: string,
  hcapMarket: string,
): boolean {
  const h = parseHandicapMarket(hcapMarket);
  if (!h || h2hPeriod(h2hMarket) !== h.period) return false;

  const side = h2hOutcomeSide(h2hOutcome);
  if (!side) return false;
  if (side === "draw") return h.line <= -0.5;
  // Superbet Criar Aposta: 1X2 no mesmo time do handicap anula/rejeita a outra perna
  if (side === h.side) return true;
  if (side === "home" && h.side === "away" && h.line <= -0.5) return true;
  if (side === "away" && h.side === "home" && h.line <= -0.5) return true;
  return false;
}

const OPPONENT_GOALS_ANNUL_WIN_HCAP = 4;

function handicapRequiresWin(market: string): { period: string; side: "home" | "away" } | null {
  const h = parseHandicapMarket(market);
  if (!h || h.line > -0.5) return null;
  return { period: h.period, side: h.side };
}

function marketBody(market: string): { period: string; body: string } {
  if (market.startsWith("1h_")) return { period: "1h", body: market.slice(3) };
  if (market.startsWith("2h_")) return { period: "2h", body: market.slice(3) };
  if (market.startsWith("ft_")) return { period: "ft", body: market.slice(3) };
  return { period: periodOf(market), body: market };
}

function parseTeamOverLine(market: string): { period: string; side: "home" | "away"; line: number } | null {
  const { period, body } = marketBody(market);
  for (const side of ["home", "away"] as const) {
    const prefix = `${side}_over_`;
    if (!body.startsWith(prefix)) continue;
    const raw = body.slice(prefix.length).replace("_", ".");
    const line = parseFloat(raw);
    if (!Number.isFinite(line)) return null;
    return { period, side, line };
  }
  return null;
}

function parseExactTeamGoals(market: string): { period: string; side: "home" | "away"; goals: number } | null {
  const { period, body } = marketBody(market);
  for (const side of ["home", "away"] as const) {
    const prefix = `exact_${side}_`;
    if (!body.startsWith(prefix)) continue;
    const raw = body.slice(prefix.length).replace("_", ".");
    const goals = parseInt(raw, 10);
    if (!Number.isFinite(goals)) return null;
    return { period, side, goals };
  }
  return null;
}

function offenseSide(market: string, outcome: string): "home" | "away" | null {
  const toOffense = (side: "home" | "away" | "draw" | null): "home" | "away" | null =>
    side === "draw" ? null : side;

  if (market === "next_goal") return toOffense(h2hOutcomeSide(outcome));
  if (market.startsWith("combo_home")) return "home";
  if (market.startsWith("combo_away")) return "away";
  if (isH2hMarket(market)) return toOffense(h2hOutcomeSide(outcome));
  const teamOver = parseTeamOverLine(market);
  if (teamOver && ["yes", "sim"].includes(outcome.toLowerCase())) return teamOver.side;
  const exact = parseExactTeamGoals(market);
  if (exact && ["yes", "sim"].includes(outcome.toLowerCase())) return exact.side;
  return null;
}

/** Handicap “precisa vencer” vs perna que empurra o adversário a 4+ gols (anula o bilhete cedo). */
function handicapConflictsOppositeOffense(
  hcapMarket: string,
  otherMarket: string,
  otherOutcome: string,
): boolean {
  const winReq = handicapRequiresWin(hcapMarket);
  if (!winReq) return false;

  const opp: "home" | "away" = winReq.side === "home" ? "away" : "home";
  const otherPeriod = periodOf(otherMarket);
  if (winReq.period !== otherPeriod && !(winReq.period === "ft" && otherPeriod === "ft")) {
    return false;
  }

  const offense = offenseSide(otherMarket, otherOutcome);
  if (offense !== opp) return false;

  if (otherMarket === "next_goal") return true;

  const teamOver = parseTeamOverLine(otherMarket);
  if (teamOver && teamOver.side === opp && ["yes", "sim"].includes(otherOutcome.toLowerCase())) {
    if (teamOver.line >= OPPONENT_GOALS_ANNUL_WIN_HCAP - 0.5) return true;
  }

  const exact = parseExactTeamGoals(otherMarket);
  if (exact && exact.side === opp && ["yes", "sim"].includes(otherOutcome.toLowerCase())) {
    if (exact.goals >= OPPONENT_GOALS_ANNUL_WIN_HCAP) return true;
  }

  if (winReq.side === "away" && otherMarket === "combo_home_btts" && ["yes", "sim"].includes(otherOutcome.toLowerCase())) {
    return true;
  }
  if (winReq.side === "home" && otherMarket === "combo_away_btts" && ["yes", "sim"].includes(otherOutcome.toLowerCase())) {
    return true;
  }

  return false;
}

function samePeriod(a: string, b: string): boolean {
  return a === b || (a === "ft" && b === "ft");
}

/** Handicap + gols do mesmo time — Superbet descarta uma perna no Criar Aposta. */
function handicapConflictsSameTeamOffense(
  hcapMarket: string,
  otherMarket: string,
  otherOutcome: string,
): boolean {
  const h = parseHandicapMarket(hcapMarket);
  if (!h) return false;
  if (!["yes", "sim"].includes(otherOutcome.toLowerCase())) return false;

  const teamOver = parseTeamOverLine(otherMarket);
  if (teamOver && teamOver.side === h.side && samePeriod(h.period, teamOver.period)) {
    return true;
  }

  const exact = parseExactTeamGoals(otherMarket);
  if (exact && exact.side === h.side && samePeriod(h.period, exact.period)) {
    return true;
  }

  return false;
}

function legsCompatible(a: LongshotLeg, b: LongshotLeg): boolean {
  if (a.market === b.market) return a.outcome === b.outcome;
  if (bttsConflictsCorrectScore(a.market, b.market)) return false;

  const periodA = periodOf(a.market);
  const periodB = periodOf(b.market);

  if (isH2hMarket(a.market) && isH2hMarket(b.market) && periodA === periodB) {
    return false;
  }

  if (periodA === periodB) {
    const fa = legFamily(a.market);
    const fb = legFamily(b.market);
    if (fa === "h2h" && fb === "goals") return false;
    if (fa === "goals" && fb === "h2h") return false;

    const ta = totalsBucket(a.market);
    const tb = totalsBucket(b.market);
    if (ta && tb && ta.period === tb.period && ta.family === tb.family) {
      return false;
    }

    if (fa === "goals" && fb === "goals") {
      if (a.market.includes("over_") && b.market.includes("over_")) return false;
      if (correctScoresConflict(a.market, b.market)) return false;
      const aCs = a.market.includes("cs_") || a.market.includes("exact");
      const bCs = b.market.includes("cs_") || b.market.includes("exact");
      if (aCs && (b.market.includes("over_") || b.market.includes("exact"))) return false;
      if (bCs && (a.market.includes("over_") || a.market.includes("exact"))) return false;
    }

    if (handicapsConflict(a.market, b.market)) return false;

    if (isH2hMarket(a.market) && fb === "handicap") {
      if (h2hConflictsHandicap(a.market, a.outcome, b.market)) return false;
    }
    if (isH2hMarket(b.market) && fa === "handicap") {
      if (h2hConflictsHandicap(b.market, b.outcome, a.market)) return false;
    }
  }

  if (legFamily(a.market) === "handicap" && handicapConflictsOppositeOffense(a.market, b.market, b.outcome)) {
    return false;
  }
  if (legFamily(b.market) === "handicap" && handicapConflictsOppositeOffense(b.market, a.market, a.outcome)) {
    return false;
  }

  if (legFamily(a.market) === "handicap" && handicapConflictsSameTeamOffense(a.market, b.market, b.outcome)) {
    return false;
  }
  if (legFamily(b.market) === "handicap" && handicapConflictsSameTeamOffense(b.market, a.market, a.outcome)) {
    return false;
  }

  return true;
}

function comboCompatible(legs: LongshotLeg[]): boolean {
  if (handicapLegCount(legs) > 1) return false;
  if (correctScoreLegCount(legs) > 1) return false;
  for (let i = 0; i < legs.length; i += 1) {
    for (let j = i + 1; j < legs.length; j += 1) {
      if (!legsCompatible(legs[i], legs[j])) return false;
    }
  }
  return true;
}

function* combinations<T>(items: T[], size: number): Generator<T[]> {
  if (size <= 0 || items.length < size) return;
  if (size === 1) {
    for (const item of items) yield [item];
    return;
  }
  for (let i = 0; i <= items.length - size; i += 1) {
    const head = items[i];
    for (const tail of combinations(items.slice(i + 1), size - 1)) {
      yield [head, ...tail];
    }
  }
}

function toLeg(row: MarketScanRow): LongshotLeg {
  return {
    market: row.market,
    outcome: row.outcome,
    label: row.label,
    marketOdd: row.marketOdd,
    modelProb: row.modelProb,
  };
}

/** Prioriza pernas com boa prob. individual e odd útil para montar @80+. */
function collectCandidateLegs(
  scan: MarketScanRow[],
  halfMarkets?: HalfMarkets,
): LongshotLeg[] {
  const byKey = new Map<string, LongshotLeg>();
  for (const row of scan) {
    if (row.marketOdd < 1.8 || row.modelProb <= 0) continue;
    if (!isSuperbetBetBuilderMarket(row.market)) continue;
    if (!isHandicapLegOnBook(halfMarkets, row.market)) continue;
    const key = `${row.market}:${row.outcome}`;
    const leg = toLeg(row);
    const prev = byKey.get(key);
    if (!prev || leg.modelProb > prev.modelProb) {
      byKey.set(key, leg);
    }
  }
  return [...byKey.values()].sort((a, b) => {
    const scoreA = a.modelProb * Math.log(a.marketOdd);
    const scoreB = b.modelProb * Math.log(b.marketOdd);
    return scoreB - scoreA || b.modelProb - a.modelProb;
  });
}

function assignRiskTiers(combos: LongshotCombo[]): LongshotCombo[] {
  if (combos.length === 0) return combos;

  const probs = combos.map((c) => c.combinedProb);
  const maxProb = Math.max(...probs);
  const minProb = Math.min(...probs);
  const span = maxProb - minProb;

  return combos.map((combo, index) => {
    let riskTier: LongshotRiskTier = "moderate";
    if (span <= 0 || combos.length === 1) {
      riskTier = "moderate";
    } else {
      const ratio = (combo.combinedProb - minProb) / span;
      if (ratio >= 0.66) riskTier = "best";
      else if (ratio >= 0.33) riskTier = "moderate";
      else riskTier = "extreme";
    }
    return { ...combo, riskTier, rank: index + 1 };
  });
}

function diversifyCombos(combos: LongshotCombo[], maxCombos: number): LongshotCombo[] {
  const picked: LongshotCombo[] = [];
  const usedLegSets = new Set<string>();

  for (const combo of combos) {
    if (picked.length >= maxCombos) break;
    const signature = combo.legs
      .map((leg) => `${leg.market}:${leg.outcome}`)
      .sort()
      .join("|");
    if (usedLegSets.has(signature)) continue;
    usedLegSets.add(signature);
    picked.push(combo);
  }
  return picked;
}

/** Monta múltiplas @80+ ordenadas pela probabilidade do modelo (maior chance primeiro). */
export function buildLongshotCombos(
  scan: MarketScanRow[] | undefined,
  options?: {
    stake?: number;
    minReturn?: number;
    maxCombos?: number;
    maxLegs?: number;
    halfMarkets?: HalfMarkets;
  },
): LongshotCombo[] {
  if (!scan?.length) return [];

  const stake = options?.stake ?? LONGSHOT_STAKE_BRL;
  const minReturn = options?.minReturn ?? LONGSHOT_MIN_RETURN_BRL;
  const minOdd = minReturn / stake;
  const maxCombos = options?.maxCombos ?? 6;
  const maxLegs = options?.maxLegs ?? 6;

  const pool = collectCandidateLegs(scan, options?.halfMarkets).slice(0, 22);
  if (pool.length < 2) return [];

  const seen = new Set<string>();
  const results: LongshotCombo[] = [];

  for (let size = 2; size <= Math.min(maxLegs, pool.length); size += 1) {
    for (const legs of combinations(pool, size)) {
      if (!comboCompatible(legs)) continue;

      const combinedOdd = legs.reduce((acc, leg) => acc * leg.marketOdd, 1);
      if (combinedOdd < minOdd) continue;

      const key = legs
        .map((leg) => `${leg.market}:${leg.outcome}`)
        .sort()
        .join("|");
      if (seen.has(key)) continue;
      seen.add(key);

      const combinedProb = legs.reduce((acc, leg) => acc * leg.modelProb, 1);
      const combinedEv = combinedProb * combinedOdd - 1;

      results.push({
        id: key,
        legs,
        combinedOdd: Math.round(combinedOdd * 100) / 100,
        stake,
        potentialReturn: Math.round(stake * combinedOdd * 100) / 100,
        combinedProb,
        combinedEv,
        riskTier: "moderate",
        rank: 0,
      });
    }
  }

  results.sort((a, b) => {
    if (b.combinedProb !== a.combinedProb) return b.combinedProb - a.combinedProb;
    if (a.combinedOdd !== b.combinedOdd) return a.combinedOdd - b.combinedOdd;
    return a.legs.length - b.legs.length;
  });

  const diversified = diversifyCombos(results, maxCombos);
  return assignRiskTiers(diversified);
}

/** Formata probabilidade pequena sem arredondar para 0,00%. */
export function formatLongshotProbPct(prob: number): string {
  if (prob <= 0) return "0%";
  const pct = prob * 100;
  if (pct >= 1) return `${pct.toFixed(1)}%`;
  if (pct >= 0.01) return `${pct.toFixed(2)}%`;
  if (pct >= 0.0001) return `${pct.toFixed(4)}%`;
  return `${pct.toExponential(1)}%`;
}

export function formatLongshotComboTicket(combo: LongshotCombo): string {
  const lines = combo.legs.map(
    (leg, idx) =>
      `${idx + 1}. ${leg.label} @${leg.marketOdd.toFixed(2)} (modelo ${formatLongshotProbPct(leg.modelProb)})`,
  );
  lines.push(
    `Múltipla @${combo.combinedOdd.toFixed(2)} · hit est. ${formatLongshotProbPct(combo.combinedProb)} · R$ ${combo.stake.toFixed(2)} → R$ ${combo.potentialReturn.toFixed(2)}`,
  );
  return lines.join("\n");
}

export const LONGSHOT_TIER_CONFIG: Record<
  LongshotRiskTier,
  {
    label: string;
    hint: string;
    cardClass: string;
    badgeClass: string;
    accentClass: string;
    oddClass: string;
  }
> = {
  best: {
    label: "Menor risco",
    hint: "Maior chance entre as opções @R$400+",
    cardClass:
      "border-emerald-400/35 bg-gradient-to-br from-emerald-500/[0.14] to-teal-700/[0.06] shadow-[0_0_24px_rgba(16,185,129,0.08)]",
    badgeClass: "border-emerald-400/35 bg-emerald-500/15 text-emerald-200",
    accentClass: "text-emerald-200",
    oddClass: "text-emerald-300",
  },
  moderate: {
    label: "Risco médio",
    hint: "Chance intermediária — longshot equilibrado",
    cardClass:
      "border-amber-400/25 bg-gradient-to-br from-amber-500/[0.10] to-orange-600/[0.05]",
    badgeClass: "border-amber-400/30 bg-amber-500/10 text-amber-200",
    accentClass: "text-amber-200",
    oddClass: "text-amber-200",
  },
  extreme: {
    label: "Risco extremo",
    hint: "Odd altíssima — probabilidade muito baixa",
    cardClass:
      "border-red-400/25 bg-gradient-to-br from-red-500/[0.10] to-orange-900/[0.05]",
    badgeClass: "border-red-400/30 bg-red-500/10 text-red-200",
    accentClass: "text-red-200",
    oddClass: "text-red-300",
  },
};
