import { useEffect, useRef } from "react";
import { useNotifications } from "@/presentation/components/ui/notifications";
import { showCashoutAlert } from "@/presentation/utils/browserNotifications";
import {
  assessCashoutRisk,
  buildCashoutLiveContext,
  type OpenBetLike,
} from "@/presentation/utils/cashoutRiskAssessment";
import {
  readCashoutAutoExecuteConfig,
  shouldAutoExecuteForAction,
} from "@/presentation/utils/cashoutAlertStorage";
import { executeCashoutViaExtension } from "@/presentation/utils/executeCashoutViaExtension";
import { useCashoutRiskAlertsPreference } from "@/presentation/hooks/useCashoutRiskAlertsPreference";

interface UseCashoutRiskAlertsOptions {
  bets: OpenBetLike[];
  currentScore: string | null;
  minute?: number;
  periodLabel?: string | null;
  htHome?: number | null;
  htAway?: number | null;
  liveStats?: {
    homeCorners?: number | null;
    awayCorners?: number | null;
    homeYellowCards?: number | null;
    awayYellowCards?: number | null;
    homeRedCards?: number | null;
    awayRedCards?: number | null;
  } | null;
  enabled?: boolean;
  eventLabel?: string;
}

/** Alerta quando perna crítica + cash-out disponível — evita perder tudo como no combo under 2.5. */
export function useCashoutRiskAlerts({
  bets,
  currentScore,
  minute = 0,
  periodLabel,
  htHome,
  htAway,
  liveStats,
  enabled = true,
  eventLabel,
}: UseCashoutRiskAlertsOptions) {
  const { addNotification } = useNotifications();
  const { riskAlertsEnabled } = useCashoutRiskAlertsPreference();
  const firedRef = useRef<Record<string, string>>({});
  const executedRef = useRef<Record<string, boolean>>({});

  useEffect(() => {
    if (!enabled || !riskAlertsEnabled) return;

    const autoConfig = readCashoutAutoExecuteConfig();
    const ctx = buildCashoutLiveContext({
      currentScore,
      minute,
      htHome,
      htAway,
      periodLabel,
      liveStats,
    });

    for (const bet of bets) {
      if (!bet.id || bet.cashoutValue == null || bet.cashoutValue <= 0) continue;

      const assessment = assessCashoutRisk(bet, ctx);
      if (!assessment.alert) continue;

      const sig = `${assessment.action}:${assessment.cashoutValue?.toFixed(2)}:${assessment.criticalLegs.join("|")}`;
      if (firedRef.current[bet.id] === sig) continue;
      firedRef.current[bet.id] = sig;

      const prefix = eventLabel ? `${eventLabel} · ` : "";
      const type =
        assessment.action === "exit_now" || assessment.action === "protect_stake"
          ? "error"
          : "info";

      addNotification({
        title: `${prefix}${assessment.title}`,
        body: assessment.message,
        type,
        source: "cashout",
      });

      showCashoutAlert({
        betId: bet.id,
        kind: assessment.action === "protect_stake" ? "approach" : "reach",
        title: assessment.title,
        body: assessment.message.slice(0, 180),
        currentValue: assessment.cashoutValue ?? 0,
        targetValue: assessment.stake,
      });

      const ticketCode = bet.ticketCode?.trim();
      const minValue =
        assessment.cashoutValue != null && autoConfig.minPctOfStake > 0
          ? bet.stake * autoConfig.minPctOfStake
          : undefined;

      if (
        ticketCode &&
        shouldAutoExecuteForAction(assessment.action, autoConfig) &&
        !executedRef.current[bet.id]
      ) {
        executedRef.current[bet.id] = true;
        void executeCashoutViaExtension({
          ticketCode,
          betId: bet.id,
          minValue,
        }).then((result) => {
          if (result.ok) {
            addNotification({
              title: `${prefix}Cash-out executado`,
              body: `Ticket ${ticketCode} · ${result.method === "api" ? "API" : "clique"} · R$ ${(result.value ?? assessment.cashoutValue ?? 0).toFixed(2)}`,
              type: "success",
              source: "cashout",
            });
          } else {
            addNotification({
              title: `${prefix}Falha no cash-out automático`,
              body: result.error || "Tente manualmente na Superbet (aba Minhas Apostas aberta).",
              type: "info",
              source: "cashout",
            });
            executedRef.current[bet.id] = false;
          }
        });
      }
    }
  }, [
    bets,
    currentScore,
    minute,
    periodLabel,
    htHome,
    htAway,
    liveStats,
    enabled,
    riskAlertsEnabled,
    eventLabel,
    addNotification,
  ]);
}
