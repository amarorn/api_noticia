/** Ranqueia mercados ao vivo por retorno esperado (stake × EV). */

export interface TopReturnRowInput {
  market: string;
  outcome: string;
  label: string;
  modelProb: number;
  marketOdd: number;
  expectedValue: number;
  edgePp: number;
  suggestedStakePct: number;
  suggestedStakeValue: number;
  meetsThreshold: boolean;
}

export interface TopReturnRow extends TopReturnRowInput {
  rank: number;
  expectedProfit: number;
  winProfit: number;
  potentialReturn: number;
}

export interface TopReturnOptions {
  minOdd?: number;
  evOnly?: boolean;
  maxRows?: number;
  defaultStake?: number;
}

export const MIN_ODD_PRESETS = [
  { value: 1, label: "Todas" },
  { value: 1.5, label: "≥ 1.50" },
  { value: 2, label: "≥ 2.00" },
  { value: 3, label: "≥ 3.00" },
  { value: 5, label: "≥ 5.00" },
] as const;

export function expectedProfit(stake: number, ev: number): number {
  if (stake <= 0 || ev <= 0) return 0;
  return stake * ev;
}

export function winProfit(stake: number, odd: number): number {
  if (stake <= 0 || odd <= 1) return 0;
  return stake * (odd - 1);
}

export function buildTopReturnRows(
  scan: TopReturnRowInput[] | undefined,
  options: TopReturnOptions = {},
): TopReturnRow[] {
  const {
    minOdd = 1,
    evOnly = true,
    maxRows = 8,
    defaultStake = 25,
  } = options;

  if (!scan?.length) return [];

  const filtered = scan.filter((row) => {
    if (row.marketOdd < minOdd) return false;
    if (row.expectedValue <= 0) return false;
    if (evOnly && !row.meetsThreshold) return false;
    return true;
  });

  const ranked = filtered
    .map((row) => {
      const stake = row.suggestedStakeValue > 0 ? row.suggestedStakeValue : defaultStake;
      return {
        ...row,
        rank: 0,
        expectedProfit: expectedProfit(stake, row.expectedValue),
        winProfit: winProfit(stake, row.marketOdd),
        potentialReturn: stake * row.marketOdd,
      };
    })
    .sort((a, b) => {
      const profitDiff = b.expectedProfit - a.expectedProfit;
      if (Math.abs(profitDiff) > 0.01) return profitDiff;
      const evDiff = b.expectedValue - a.expectedValue;
      if (Math.abs(evDiff) > 1e-6) return evDiff;
      return b.marketOdd - a.marketOdd;
    })
    .slice(0, maxRows);

  return ranked.map((row, idx) => ({ ...row, rank: idx + 1 }));
}
