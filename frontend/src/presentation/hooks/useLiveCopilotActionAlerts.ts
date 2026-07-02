import { useEffect, useRef } from "react";
import type { LiveCopilot } from "@/domain/entities";
import { useToast } from "@/presentation/components/ui/toast/ToastContext";
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
  const { addToast } = useToast();
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
          const message = `Copiloto — cash-out: ${matchLabel}. ${copilot.momento || pickText}`;
          addToast(message, "info");
          showCopilotAlert({
            eventId,
            title: "Copiloto: considerar cash-out",
            body: pickText || copilot.momento,
            acao: "cashout",
          });
        } else {
          const message = `Momento ideal — ${matchLabel}: ${pickText}`;
          addToast(message, "success");
          showCopilotAlert({
            eventId,
            title: "Momento ideal para apostar",
            body: pickText || copilot.momento,
            acao: "apostar",
          });
        }
      }
    }

    prevRef.current = { acao: copilot.acaoAgora, picks };
  }, [copilot, enabled, eventId, homeTeam, awayTeam, addToast]);
}
