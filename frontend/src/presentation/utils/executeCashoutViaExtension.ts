/** Solicita execução de cash-out via extensão Chrome (Superbet logada). */

export interface ExecuteCashoutPayload {
  ticketCode: string;
  betId?: string;
  minValue?: number;
  skipIfDone?: boolean;
}

export interface ExecuteCashoutResult {
  ok: boolean;
  error?: string | null;
  method?: "api" | "click";
  value?: number;
  result?: Record<string, unknown> | null;
}

export function isExtensionBridgeAvailable(): boolean {
  return typeof window !== "undefined";
}

export function executeCashoutViaExtension(
  payload: ExecuteCashoutPayload,
): Promise<ExecuteCashoutResult> {
  return new Promise((resolve) => {
    if (typeof window === "undefined") {
      resolve({ ok: false, error: "no_window" });
      return;
    }

    const requestId =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `cashout-${Date.now()}`;

    const timeout = window.setTimeout(() => {
      window.removeEventListener("message", onMessage);
      resolve({
        ok: false,
        error: "timeout — abra a extensão Bolão AI e recarregue Minhas Apostas na Superbet",
      });
    }, 28000);

    const onMessage = (event: MessageEvent) => {
      if (event.source !== window) return;
      const data = event.data as {
        source?: string;
        type?: string;
        requestId?: string;
        ok?: boolean;
        error?: string | null;
        result?: Record<string, unknown> | null;
      };
      if (data?.source !== "bolao-ai-extension") return;
      if (data.type !== "BOLAO_EXECUTE_CASHOUT_RESULT") return;
      if (data.requestId !== requestId) return;

      window.clearTimeout(timeout);
      window.removeEventListener("message", onMessage);

      const inner = (data.result || {}) as Record<string, unknown>;
      resolve({
        ok: Boolean(data.ok ?? inner.ok),
        error: data.error ?? (inner.error as string | undefined) ?? null,
        method: inner.method as ExecuteCashoutResult["method"],
        value: typeof inner.value === "number" ? inner.value : undefined,
        result: data.result ?? null,
      });
    };

    window.addEventListener("message", onMessage);
    window.postMessage(
      {
        source: "bolao-ai-app",
        type: "BOLAO_EXECUTE_CASHOUT",
        requestId,
        payload,
      },
      window.location.origin,
    );
  });
}
