/**
 * Service worker da extensão Bolão AI — Captura Superbet.
 * Recebe mensagens do popup/content_script e faz chamadas à API.
 */
const API_BASE = "http://127.0.0.1:8000";

chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
  if (request.type === "API_POST_OPEN_BET") {
    const { payload, apiKey } = request;
    fetch(`${API_BASE}/user/open-bets`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(apiKey ? { "X-API-Key": apiKey } : {}),
      },
      body: JSON.stringify(payload),
    })
      .then(async (resp) => {
        const data = await resp.json().catch(() => ({}));
        sendResponse({ ok: resp.ok, status: resp.status, data });
      })
      .catch((err) => {
        sendResponse({ ok: false, error: String(err) });
      });
    return true; // async
  }

  if (request.type === "API_GET_OPEN_BETS") {
    const { apiKey } = request;
    fetch(`${API_BASE}/user/open-bets`, {
      headers: apiKey ? { "X-API-Key": apiKey } : {},
    })
      .then(async (resp) => {
        const data = await resp.json().catch(() => ({}));
        sendResponse({ ok: resp.ok, data });
      })
      .catch((err) => {
        sendResponse({ ok: false, error: String(err) });
      });
    return true; // async
  }

  return false;
});
