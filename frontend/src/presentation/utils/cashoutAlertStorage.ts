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
const RISK_ALERTS_KEY = "bolao-cashout-risk-alerts-v1";
const AUTO_EXECUTE_KEY = "bolao-cashout-auto-execute-v1";

export const CASHOUT_RISK_ALERTS_CHANGED = "cashout-risk-alerts-changed";
export const CASHOUT_AUTO_EXECUTE_CHANGED = "cashout-auto-execute-changed";

export type CashoutAutoExecuteMode = "off" | "critical_only" | "protect_and_critical";

export interface CashoutAutoExecuteConfig {
  enabled: boolean;
  /** Quais alertas disparam execução automática. */
  mode: CashoutAutoExecuteMode;
  /** Só executa se cash-out ≥ este % da stake (0.5 = 50%). */
  minPctOfStake: number;
}
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

/** Alertas automáticos de risco (perna crítica + cash-out disponível). Ativo por padrão. */
export function readCashoutRiskAlertsEnabled(): boolean {
  try {
    return localStorage.getItem(RISK_ALERTS_KEY) !== "0";
  } catch {
    return true;
  }
}

export function writeCashoutRiskAlertsEnabled(enabled: boolean): void {
  localStorage.setItem(RISK_ALERTS_KEY, enabled ? "1" : "0");
  window.dispatchEvent(new Event(CASHOUT_RISK_ALERTS_CHANGED));
}

const DEFAULT_AUTO_EXECUTE: CashoutAutoExecuteConfig = {
  enabled: false,
  mode: "critical_only",
  minPctOfStake: 0.5,
};

export function readCashoutAutoExecuteConfig(): CashoutAutoExecuteConfig {
  try {
    const raw = localStorage.getItem(AUTO_EXECUTE_KEY);
    if (!raw) return { ...DEFAULT_AUTO_EXECUTE };
    return { ...DEFAULT_AUTO_EXECUTE, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT_AUTO_EXECUTE };
  }
}

export function writeCashoutAutoExecuteConfig(patch: Partial<CashoutAutoExecuteConfig>): CashoutAutoExecuteConfig {
  const next = { ...readCashoutAutoExecuteConfig(), ...patch };
  localStorage.setItem(AUTO_EXECUTE_KEY, JSON.stringify(next));
  window.dispatchEvent(new Event(CASHOUT_AUTO_EXECUTE_CHANGED));
  return next;
}

export function shouldAutoExecuteForAction(
  action: string,
  config: CashoutAutoExecuteConfig,
): boolean {
  if (!config.enabled) return false;
  if (config.mode === "critical_only") {
    return action === "exit_now" || action === "protect_stake";
  }
  if (config.mode === "protect_and_critical") {
    return action === "exit_now" || action === "protect_stake" || action === "consider_exit";
  }
  return false;
}
