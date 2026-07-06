/**
 * Isolated world — repassa mensagens do hook MAIN para o service worker.
 */
(function () {
  "use strict";

  if (window.__bolaoBacboBridgeInit) return;
  window.__bolaoBacboBridgeInit = true;

  const queue = [];
  let flushTimer = null;
  let lastTableId = null;
  let lastWsUrl = null;
  let msgCount = 0;
  let captureEnabled = true;

  chrome.storage.local.get(["bolao_bacbo_capture_enabled"], (items) => {
    if (items.bolao_bacbo_capture_enabled === false) captureEnabled = false;
  });

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local" || !changes.bolao_bacbo_capture_enabled) return;
    captureEnabled = changes.bolao_bacbo_capture_enabled.newValue !== false;
  });

  function flushQueue() {
    flushTimer = null;
    if (!queue.length) return;
    const batch = queue.splice(0, queue.length);
    chrome.runtime.sendMessage({
      type: "BACBO_WS_BATCH",
      tableId: lastTableId,
      wsUrl: lastWsUrl,
      messages: batch,
    });
  }

  function scheduleFlush() {
    if (flushTimer) return;
    flushTimer = setTimeout(flushQueue, 1200);
  }

  window.addEventListener("message", (event) => {
    if (event.source !== window) return;
    const data = event.data;
    if (!data || data.source !== "bolao-bacbo-hook" || data.type !== "BACBO_WS_MESSAGE") {
      return;
    }
    if (!captureEnabled) return;
    if (data.tableId) lastTableId = data.tableId;
    if (data.wsUrl) lastWsUrl = data.wsUrl;
    const text = typeof data.data === "string" ? data.data.trim() : "";
    if (!text || (text[0] !== "{" && text[0] !== "[")) return;
    msgCount += 1;
    queue.push(text);
    if (queue.length >= 20) flushQueue();
    else scheduleFlush();
  });

  chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
    if (request.type === "PING_BACBO") {
      sendResponse({
        ok: true,
        hostname: location.hostname,
        tableId: lastTableId,
        queueSize: queue.length,
        msgCount,
        patched: Boolean(window.__bolaoBacboWsPatched),
      });
      return true;
    }
    return false;
  });

  console.info("[Bolão AI] Bac Bo bridge em", location.hostname);
})();
