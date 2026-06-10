/**
 * Service worker da extensão Bolão AI — Captura Superbet.
 * Recebe mensagens do popup/content_script e faz chamadas à API.
 */

// Tenta localhost e 127.0.0.1 — em caso de falha no primeiro, usa o segundo
const API_BASES = ["http://127.0.0.1:8000", "http://localhost:8000"];

async function apiFetch(path, options = {}) {
  let lastError = null;
  for (const base of API_BASES) {
    try {
      const resp = await fetch(`${base}${path}`, options);
      const data = await resp.json().catch(() => ({}));
      return { ok: resp.ok, status: resp.status, data };
    } catch (err) {
      lastError = err;
    }
  }
  return { ok: false, error: `API indisponível: ${String(lastError)}` };
}

chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
  if (request.type === "API_POST_OPEN_BET") {
    const { payload, apiKey } = request;
    apiFetch("/user/open-bets", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(apiKey ? { "X-API-Key": apiKey } : {}),
      },
      body: JSON.stringify(payload),
    }).then(sendResponse);
    return true; // async
  }

  if (request.type === "API_GET_OPEN_BETS") {
    const { apiKey } = request;
    apiFetch("/user/open-bets", {
      headers: apiKey ? { "X-API-Key": apiKey } : {},
    }).then(sendResponse);
    return true; // async
  }

  return false;
});

// Log de instalação/ativação
chrome.runtime.onInstalled.addListener(() => {
  console.info("[Bolão AI] Extensão instalada/atualizada.");
});
