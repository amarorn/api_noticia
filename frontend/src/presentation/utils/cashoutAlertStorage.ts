/** Preferências de alerta de cash-out por bilhete (persistidas no browser). */

export const CASHOUT_APPROACH_RATIO = 0.95;

export interface CashoutAlertConfig {
  enabled: boolean;
  /** Valor alvo (R$) definido pelo usuário. */
  target: number | null;
  /** Avisar quando cash-out ≥ 95% da meta (aproximando). */
  notifyApproach: boolean;
  /** Avisar quando cash-out ≥ meta (atingiu ou ultrapassou). */
  notifyReach: boolean;
}

const STORAGE_KEY = "bolao-cashout-alerts-v1";
const DEFAULT_CONFIG: CashoutAlertConfig = {
  enabled: false,
  target: null,
  notifyApproach: true,
  notifyReach: true,
};

function readAll(): Record<string, CashoutAlertConfig> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as Record<string, CashoutAlertConfig>;
  } catch {
    return {};
  }
}

function writeAll(all: Record<string, CashoutAlertConfig>): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
}

export function getCashoutAlertConfig(betId: string): CashoutAlertConfig {
  return { ...DEFAULT_CONFIG, ...readAll()[betId] };
}

export function setCashoutAlertConfig(betId: string, patch: Partial<CashoutAlertConfig>): CashoutAlertConfig {
  const all = readAll();
  const next = { ...DEFAULT_CONFIG, ...all[betId], ...patch };
  all[betId] = next;
  writeAll(all);
  return next;
}

export function removeCashoutAlertConfig(betId: string): void {
  const all = readAll();
  delete all[betId];
  writeAll(all);
}
