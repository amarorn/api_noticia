/**
 * Ponte Bolão AI (localhost:5173) → extensão Chrome.
 * Escuta postMessage do frontend e enfileira bilhete na Superbet.
 */
(function () {
  "use strict";

  if (window.__bolaoFrontendBridgeInit) return;
  window.__bolaoFrontendBridgeInit = true;

  window.addEventListener("message", (event) => {
    if (event.source !== window) return;
    const data = event.data;
    if (!data || data.source !== "bolao-ai-app") return;
    if (data.type !== "BOLAO_QUEUE_SUPERBET_TICKET") return;

    chrome.runtime.sendMessage(
      {
        type: "QUEUE_SUPERBET_TICKET",
        payload: data.payload,
      },
      (response) => {
        window.postMessage(
          {
            source: "bolao-ai-extension",
            type: "BOLAO_QUEUE_SUPERBET_TICKET_RESULT",
            requestId: data.requestId,
            ok: Boolean(response?.ok),
            error: response?.error || chrome.runtime.lastError?.message || null,
            tabId: response?.tabId ?? null,
          },
          window.location.origin,
        );
      },
    );
  });

  console.info("[Bolão AI] Frontend bridge ativo em", location.origin);
})();
