/** Payload enviado à extensão Chrome Bolão AI — Captura Superbet. */
export interface SuperbetExtensionTicketLeg {
  market: string;
  outcome: string;
  label: string;
  marketOdd: number;
  modelProb?: number;
}

export interface SuperbetExtensionTicket {
  id: string;
  superbetEventId: number;
  homeTeam: string;
  awayTeam: string;
  title: string;
  stake: number;
  combinedOdd: number;
  potentialReturn: number;
  combinedProb?: number;
  legs: SuperbetExtensionTicketLeg[];
  source: "longshot" | "inplay_combo" | "bolao_proposal";
}

export interface SendSuperbetTicketResult {
  ok: boolean;
  error?: string;
  tabId?: number;
}

const EXTENSION_MSG = "BOLAO_QUEUE_SUPERBET_TICKET";
const EXTENSION_REPLY = "BOLAO_QUEUE_SUPERBET_TICKET_RESULT";
const TIMEOUT_MS = 4000;

/** Envia bilhete ao content script da extensão (localhost → Chrome). */
export function sendSuperbetTicketToExtension(
  ticket: SuperbetExtensionTicket,
): Promise<SendSuperbetTicketResult> {
  return new Promise((resolve) => {
    const requestId =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `req-${Date.now()}`;

    const timeout = window.setTimeout(() => {
      window.removeEventListener("message", handler);
      resolve({
        ok: false,
        error:
          "Extensão não respondeu. Recarregue Bolão AI — Captura Superbet em chrome://extensions e a página (F5).",
      });
    }, TIMEOUT_MS);

    const handler = (event: MessageEvent) => {
      if (event.source !== window) return;
      const data = event.data as {
        source?: string;
        type?: string;
        requestId?: string;
        ok?: boolean;
        error?: string;
        tabId?: number;
      };
      if (data?.source !== "bolao-ai-extension") return;
      if (data.type !== EXTENSION_REPLY) return;
      if (data.requestId !== requestId) return;

      window.clearTimeout(timeout);
      window.removeEventListener("message", handler);
      resolve({
        ok: Boolean(data.ok),
        error: data.error,
        tabId: data.tabId,
      });
    };

    window.addEventListener("message", handler);
    window.postMessage(
      {
        source: "bolao-ai-app",
        type: EXTENSION_MSG,
        requestId,
        payload: ticket,
      },
      window.location.origin,
    );
  });
}
