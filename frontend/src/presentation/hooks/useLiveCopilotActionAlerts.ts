import { useEffect, useRef } from "react";
import type { LiveCopilot } from "@/domain/entities";
import { useNotifications } from "@/presentation/components/ui/notifications";
import { showCopilotAlert } from "@/presentation/utils/browserNotifications";

interface UseLiveCopilotActionAlertsOptions {
  eventId: number;
  homeTeam?: string;
  awayTeam?: string;
  enabled?: boolean;
}

function pickFingerprint(copilot: LiveCopilot): string {
  return copilot.picks.map((p) => `${p.market}:${p.outcome}`).join("|");
}

export function useLiveCopilotActionAlerts(
  copilot: LiveCopilot | undefined,
  options: UseLiveCopilotActionAlertsOptions,
) {
  const { addNotification } = useNotifications();
  const prevRef = useRef<{ acao: LiveCopilot["acaoAgora"]; picks: string } | null>(null);
  const { eventId, homeTeam, awayTeam, enabled = true } = options;

  useEffect(() => {
    if (!enabled || !copilot) return;

    const picks = pickFingerprint(copilot);
    const prev = prevRef.current;

    if (prev) {
      const becameApostar = prev.acao !== "apostar" && copilot.acaoAgora === "apostar";
      const becameCashout = prev.acao !== "cashout" && copilot.acaoAgora === "cashout";
      const newPickWhileApostar =
        copilot.acaoAgora === "apostar" &&
        prev.acao === "apostar" &&
        picks !== prev.picks &&
        picks.length > 0;

      if (becameApostar || becameCashout || newPickWhileApostar) {
        const top = copilot.picks[0];
        const matchLabel =
          homeTeam && awayTeam ? `${homeTeam} x ${awayTeam}` : `Evento ${eventId}`;
        const oddText =
          top?.marketOdd != null ? ` @ ${top.marketOdd.toFixed(2)}` : "";
        const pickText = top ? `${top.label}${oddText}` : copilot.momento;

        if (becameCashout) {
          const body = pickText || copilot.momento;
          addNotification({
            title: `Copiloto — cash-out · ${matchLabel}`,
            body,
            type: "info",
            source: "copilot",
          });
          showCopilotAlert({
            eventId,
            title: "Copiloto: considerar cash-out",
            body,
            acao: "cashout",
          });
        } else {
          const body = pickText || copilot.momento;
          addNotification({
            title: `Momento ideal · ${matchLabel}`,
            body,
            type: "success",
            source: "copilot",
          });
          showCopilotAlert({
            eventId,
            title: "Momento ideal para apostar",
            body,
            acao: "apostar",
          });
        }
      }
    }

    prevRef.current = { acao: copilot.acaoAgora, picks };
  }, [copilot, enabled, eventId, homeTeam, awayTeam, addNotification]);
}
