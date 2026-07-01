import { useEffect, useRef } from "react";
import type { RegisteredBetEntry } from "@/presentation/components/predictions/LiveOpenBetMonitor";
import {
  getCashoutAlertConfig,
  CASHOUT_APPROACH_RATIO,
  type CashoutAlertConfig,
} from "@/presentation/utils/cashoutAlertStorage";
import { showCashoutAlert } from "@/presentation/utils/browserNotifications";

const APPROACH_RATIO = CASHOUT_APPROACH_RATIO;

type FiredMap = Record<string, { approach?: boolean; reach?: boolean }>;

function pickLabel(bet: RegisteredBetEntry, homeTeam: string, awayTeam: string): string {
  if (bet.market === "h2h") {
    if (bet.outcome === "1") return homeTeam;
    if (bet.outcome === "2") return awayTeam;
    if (bet.outcome === "X") return "Empate";
  }
  return bet.outcome;
}

function evaluateAlert(
  bet: RegisteredBetEntry,
  config: CashoutAlertConfig,
  current: number,
  homeTeam: string,
  awayTeam: string,
  fired: FiredMap,
  onAlert?: UseCashoutTargetAlertsOptions["onAlert"],
): void {
  const target = config.target;
  if (!config.enabled || target == null || target <= 0 || current <= 0) return;

  const pick = pickLabel(bet, homeTeam, awayTeam);
  const state = fired[bet.id] ?? {};

  if (
    config.notifyApproach &&
    !state.approach &&
    current >= target * APPROACH_RATIO &&
    current < target
  ) {
    fired[bet.id] = { ...state, approach: true };
    const payload = {
      betId: bet.id,
      kind: "approach" as const,
      currentValue: current,
      targetValue: target,
      title: "Cash-out se aproximando da meta",
      body: `${pick}: R$ ${current.toFixed(2)} (${Math.round((current / target) * 100)}% da meta R$ ${target.toFixed(2)})`,
    };
    showCashoutAlert(payload);
    onAlert?.({ title: payload.title, body: payload.body, kind: "approach" });
  }

  if (config.notifyReach && !state.reach && current >= target) {
    fired[bet.id] = { ...state, reach: true };
    const payload = {
      betId: bet.id,
      kind: "reach" as const,
      currentValue: current,
      targetValue: target,
      title: "Meta de cash-out atingida",
      body: `${pick}: R$ ${current.toFixed(2)} — atingiu ou ultrapassou R$ ${target.toFixed(2)}`,
    };
    showCashoutAlert(payload);
    onAlert?.({ title: payload.title, body: payload.body, kind: "reach" });
  }
}

interface UseCashoutTargetAlertsOptions {
  bets: RegisteredBetEntry[];
  homeTeam: string;
  awayTeam: string;
  enabled: boolean;
  configVersion?: number;
  onAlert?: (payload: { title: string; body: string; kind: "approach" | "reach" }) => void;
}

/** Dispara alertas quando o cash-out Superbet se aproxima ou atinge a meta do usuário. */
export function useCashoutTargetAlerts({
  bets,
  homeTeam,
  awayTeam,
  enabled,
  configVersion = 0,
  onAlert,
}: UseCashoutTargetAlertsOptions): void {
  const firedRef = useRef<FiredMap>({});
  const configSigRef = useRef<string>("");

  useEffect(() => {
    if (!enabled || !homeTeam) return;

    const configSig = bets
      .map((b) => {
        const c = getCashoutAlertConfig(b.id);
        return `${b.id}:${c.enabled}:${c.target}:${c.notifyApproach}:${c.notifyReach}:${b.offeredCashout}`;
      })
      .join("|");

    if (configSig !== configSigRef.current) {
      firedRef.current = {};
      configSigRef.current = configSig;
    }

    for (const bet of bets) {
      const config = getCashoutAlertConfig(bet.id);
      const current = bet.offeredCashout ?? bet.cashoutValue ?? null;
      if (current == null || current <= 0) continue;
      evaluateAlert(bet, config, current, homeTeam, awayTeam, firedRef.current, onAlert);
    }
  }, [bets, homeTeam, awayTeam, enabled, configVersion, onAlert]);
}
