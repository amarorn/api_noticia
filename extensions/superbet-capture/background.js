/**
 * Service worker da extensão Bolão AI — Captura Superbet.
 * Orquestra capturas em background, persiste resultado e notifica o usuário.
 */

const API_BASES = ["http://127.0.0.1:8000", "http://localhost:8000"];
const STORAGE_LAST = "bolao_last_capture";
const STORAGE_PROGRESS = "bolao_capture_in_progress";

async function apiFetch(path, options = {}) {
  let lastError = null;
  for (const base of API_BASES) {
    try {
      const resp = await fetch(`${base}${path}`, options);
      const data = await resp.json().catch(() => ({}));
      const detail = data.detail;
      let errorMsg = null;
      if (!resp.ok) {
        if (typeof detail === "string") errorMsg = detail;
        else if (Array.isArray(detail)) {
          errorMsg = detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
        } else if (detail && typeof detail === "object") {
          errorMsg = detail.message || detail.msg || JSON.stringify(detail);
        } else {
          errorMsg = data.message || `HTTP ${resp.status}`;
        }
      }
      return { ok: resp.ok, status: resp.status, data, error: errorMsg, detail: typeof detail === "object" ? detail : null };
    } catch (err) {
      lastError = err;
    }
  }
  return { ok: false, status: 0, error: `API indisponível: ${String(lastError)}` };
}

async function ensureContentScript(tabId) {
  try {
    const ping = await chrome.tabs.sendMessage(tabId, { type: "PING" });
    if (ping?.ok) return { ok: true };
  } catch {
    /* injetar abaixo */
  }
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["event_id.js", "cashout_executor.js", "content_script.js"],
    });
    await new Promise((r) => setTimeout(r, 350));
    return { ok: true, injected: true };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

const LIVE_PANEL_FILES = ["event_id.js", "cashout_executor.js", "content_script.js", "live_market_panel.js"];
const TICKET_BUILDER_FILES = ["event_id.js", "cashout_executor.js", "content_script.js", "ticket_builder.js"];
const CASHOUT_SCRIPT_FILES = ["event_id.js", "cashout_executor.js", "content_script.js"];

const SUPERBET_BETS_URLS = [
  "https://superbet.bet.br/apostas*",
  "https://www.superbet.bet.br/apostas*",
  "https://superbet.com/br/apostas*",
  "https://www.superbet.com/br/apostas*",
];

const SUPERBET_EVENT_URLS = (eventId) => [
  `https://superbet.bet.br/evento/${eventId}`,
  `https://www.superbet.bet.br/evento/${eventId}`,
  `https://superbet.bet.br/odds/futebol/e-${eventId}`,
];

async function ensureTicketBuilderScripts(tabId) {
  try {
    const ping = await chrome.tabs.sendMessage(tabId, { type: "PING" });
    if (ping?.ok) {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ["ticket_builder.js"],
      });
      await new Promise((r) => setTimeout(r, 300));
      return { ok: true };
    }
  } catch {
    /* injetar abaixo */
  }
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: TICKET_BUILDER_FILES,
    });
    await new Promise((r) => setTimeout(r, 450));
    return { ok: true, injected: true };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

async function findSuperbetTabForEvent(eventId) {
  const tabs = await chrome.tabs.query({});
  for (const tab of tabs) {
    const url = tab.url || "";
    if (!/superbet\.(com|bet\.br)/i.test(url)) continue;
    if (url.includes(String(eventId))) return tab;
  }
  return null;
}

async function openSuperbetEventTab(eventId) {
  const existing = await findSuperbetTabForEvent(eventId);
  if (existing?.id) {
    await chrome.tabs.update(existing.id, { active: true });
    if (existing.windowId != null) {
      await chrome.windows.update(existing.windowId, { focused: true });
    }
    return existing;
  }
  const url = SUPERBET_EVENT_URLS(eventId)[0];
  return chrome.tabs.create({ url, active: true });
}

async function findSuperbetBetsTab() {
  const tabs = await chrome.tabs.query({ url: SUPERBET_BETS_URLS });
  return tabs[0] || null;
}

async function waitForTabComplete(tabId, timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const tab = await chrome.tabs.get(tabId);
    if (tab.status === "complete") return tab;
    await new Promise((r) => setTimeout(r, 400));
  }
  return chrome.tabs.get(tabId);
}

async function ensureCashoutScripts(tabId) {
  try {
    const ping = await chrome.tabs.sendMessage(tabId, { type: "PING" });
    if (ping?.ok) return { ok: true };
  } catch {
    /* injetar */
  }
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: CASHOUT_SCRIPT_FILES,
    });
    await new Promise((r) => setTimeout(r, 450));
    return { ok: true, injected: true };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

/** Executa cash-out na aba Minhas Apostas (API autenticada → clique no botão). */
async function executeCashoutOnSuperbet(payload) {
  let tab = await findSuperbetBetsTab();
  if (!tab?.id) {
    tab = await chrome.tabs.create({
      url: "https://superbet.bet.br/apostas",
      active: false,
    });
    await waitForTabComplete(tab.id);
  }

  const ready = await ensureCashoutScripts(tab.id);
  if (!ready.ok) {
    return { ok: false, error: ready.error || "scripts_not_ready" };
  }

  try {
    const result = await chrome.tabs.sendMessage(tab.id, {
      type: "EXECUTE_CASHOUT",
      payload,
    });
    return result || { ok: false, error: "no_response" };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

function legEventId(leg, fallbackEventId) {
  return leg?.superbetEventId ?? leg?.superbet_event_id ?? fallbackEventId ?? null;
}

function isCrossGameTicket(payload) {
  const legs = payload?.legs || [];
  if (payload?.crossGame === true) return legs.length >= 2;
  if (legs.length < 2) return false;
  const rootEventId = payload?.superbetEventId ?? null;
  const eventIds = new Set(
    legs.map((leg) => legEventId(leg, rootEventId)).filter((id) => id != null),
  );
  return eventIds.size > 1;
}

async function applyTicketLegsOnTab(tabId, payload) {
  try {
    return await chrome.tabs.sendMessage(tabId, {
      type: "APPLY_TICKET_LEGS",
      payload,
    });
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
}

/** Múltipla cross-game: visita cada evento e clica a perna correspondente no cupom. */
async function applyCrossGameTicket(payload) {
  const legs = payload?.legs || [];
  if (legs.length < 2) {
    return { ok: false, error: "Cross-game exige ao menos 2 pernas." };
  }

  const rootEventId = payload?.superbetEventId ?? legEventId(legs[0], null);
  const byEvent = new Map();
  for (const leg of legs) {
    const eventId = legEventId(leg, rootEventId);
    if (!eventId) {
      return { ok: false, error: "Perna sem superbetEventId." };
    }
    if (!byEvent.has(eventId)) byEvent.set(eventId, []);
    byEvent.get(eventId).push(leg);
  }

  const eventIds = [...byEvent.keys()];
  await chrome.storage.local.set({
    bolao_pending_ticket: {
      ...payload,
      crossGame: true,
      queuedAt: new Date().toISOString(),
    },
  });

  const aggregatedResults = [];
  let lastTabId = null;

  for (let index = 0; index < eventIds.length; index += 1) {
    const eventId = eventIds[index];
    const eventLegs = byEvent.get(eventId) || [];
    const isLast = index === eventIds.length - 1;

    const tab = await openSuperbetEventTab(eventId);
    if (!tab?.id) {
      return { ok: false, error: `Não foi possível abrir evento #${eventId}.` };
    }
    lastTabId = tab.id;

    await waitForTabComplete(tab.id, 20000);
    const ensured = await ensureTicketBuilderScripts(tab.id);
    if (!ensured.ok) {
      return {
        ok: true,
        tabId: tab.id,
        crossGame: true,
        warning: ensured.error || `Evento #${eventId}: recarregue (F5) e tente de novo.`,
      };
    }

    await new Promise((r) => setTimeout(r, 1400));

    const step = await applyTicketLegsOnTab(tab.id, {
      legs: eventLegs,
      stake: isLast ? payload.stake : null,
      eventIndex: index + 1,
      eventTotal: eventIds.length,
    });

    if (step?.results?.length) {
      aggregatedResults.push(...step.results);
    } else if (eventLegs.length) {
      aggregatedResults.push(
        ...eventLegs.map((leg) => ({
          leg,
          ok: Boolean(step?.ok),
        })),
      );
    }

    if (!isLast) {
      await new Promise((r) => setTimeout(r, 900));
    }
  }

  if (lastTabId) {
    await applyTicketLegsOnTab(lastTabId, {
      legs: [],
      showSummary: true,
      summary: {
        ticket: payload,
        allResults: aggregatedResults,
      },
    });
  }

  const okCount = aggregatedResults.filter((r) => r.ok).length;
  showNotification(
    "Bolão AI — múltipla cross-game",
    `${okCount}/${legs.length} perna(s) · ${eventIds.length} jogos · R$ ${Number(payload.stake || 0).toFixed(2)}`,
  );

  return {
    ok: true,
    tabId: lastTabId,
    crossGame: true,
    okCount,
    total: legs.length,
    eventCount: eventIds.length,
  };
}

async function queueSuperbetTicket(payload) {
  if (isCrossGameTicket(payload)) {
    return applyCrossGameTicket(payload);
  }

  const eventId = payload?.superbetEventId;
  if (!eventId) {
    return { ok: false, error: "superbetEventId ausente no bilhete." };
  }

  await chrome.storage.local.set({
    bolao_pending_ticket: { ...payload, queuedAt: new Date().toISOString() },
  });

  const tab = await openSuperbetEventTab(eventId);
  if (!tab?.id) {
    return { ok: false, error: "Não foi possível abrir aba Superbet." };
  }

  const ensured = await ensureTicketBuilderScripts(tab.id);
  if (!ensured.ok) {
    return {
      ok: true,
      tabId: tab.id,
      warning: ensured.error || "Abra o evento na Superbet e recarregue (F5).",
    };
  }

  chrome.tabs.sendMessage(tab.id, { type: "APPLY_PENDING_TICKET" }, () => {
    if (chrome.runtime.lastError) {
      /* ticket_builder auto-aplica ao carregar */
    }
  });

  showNotification(
    "Bolão AI — bilhete enfileirado",
    `${payload.legs?.length || 0} perna(s) · R$ ${Number(payload.stake || 0).toFixed(2)} → Superbet #${eventId}`,
  );

  return { ok: true, tabId: tab.id };
}

async function ensureLivePanelScripts(tabId) {
  try {
    const status = await chrome.tabs.sendMessage(tabId, { type: "GET_LIVE_PANEL_STATUS" });
    if (status?.ok) return { ok: true };
  } catch {
    /* injetar abaixo */
  }
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: LIVE_PANEL_FILES,
    });
    await new Promise((r) => setTimeout(r, 450));
    return { ok: true, injected: true };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

async function setProgress(kind, tabId) {
  await chrome.storage.local.set({
    [STORAGE_PROGRESS]: { kind, tabId, startedAt: new Date().toISOString() },
  });
}

async function clearProgress() {
  await chrome.storage.local.remove(STORAGE_PROGRESS);
}

async function saveLastCapture(record) {
  await chrome.storage.local.set({ [STORAGE_LAST]: record });
}

function showNotification(title, message) {
  chrome.notifications.create(`bolao-capture-${Date.now()}`, {
    type: "basic",
    iconUrl: "icon128.png",
    title,
    message: String(message).slice(0, 240),
    priority: 1,
  });
}

function summarizeOpenBets(bets, results) {
  const okCount = (results || []).filter((r) => r.ok).length;
  const skippedCount = (results || []).filter((r) => r.skipped).length;
  const failCount = bets.length - okCount - skippedCount;
  let status = "ok";
  let message = "";

  if (bets.length === 0) {
    status = "warn";
    message = "Nenhuma aposta aberta encontrada na página.";
  } else if (failCount === 0 && skippedCount === 0) {
    message = `${bets.length} aposta(s) enviada(s) com sucesso!`;
  } else if (okCount > 0) {
    status = "warn";
    message = `${okCount}/${bets.length} enviadas.`;
    if (skippedCount) message += ` ${skippedCount} ignorada(s).`;
    if (failCount) message += ` ${failCount} rejeitada(s) pela API.`;
  } else {
    status = "err";
    const firstErr =
      (results || []).find((r) => r.skipped)?.error ||
      (results || []).find((r) => !r.ok)?.error ||
      "Verifique API Key e se a API está rodando.";
    message = `${bets.length} encontrada(s), nenhuma enviada. ${firstErr}`;
  }

  return { okCount, skippedCount, failCount, status, message };
}

function serializeOpenCapture(bets, results, summary, debug) {
  return {
    kind: "open",
    finishedAt: new Date().toISOString(),
    status: summary.status,
    message: summary.message,
    summary: {
      total: bets.length,
      ok: summary.okCount,
      skipped: summary.skippedCount,
      fail: summary.failCount,
      tickets_on_page: debug?.tickets_on_page ?? null,
      cashout_buttons: debug?.cashout_buttons ?? null,
    },
    debug: debug || null,
    bets: bets.map((b, i) => ({
      event_name: b.event_name,
      stake: b.stake,
      picks_count: b.picks?.length || 0,
      is_live: b.is_live,
      cashout_value: b.cashout_value,
      send: results[i] || null,
      against_model: results[i]?.against_model_alert || null,
    })),
  };
}

async function runOpenBetsCapture(tabId, apiKey) {
  if (apiKey) {
    await chrome.storage.local.set({ bolao_api_key: apiKey });
  }
  await setProgress("open", tabId);
  try {
    const inj = await ensureContentScript(tabId);
    if (!inj.ok) {
      throw new Error(inj.error || "Falha ao injetar script na aba Superbet");
    }

    const response = await chrome.tabs.sendMessage(tabId, {
      type: "SCAN_BETS",
      apiKey: apiKey || "",
    });
    const bets = response?.bets || [];
    const results = response?.results || [];
    const debug = response?.debug || null;
    const summary = summarizeOpenBets(bets, results);
    let message = summary.message;
    if (debug?.tickets_on_page && debug.tickets_on_page > bets.length) {
      message += ` (${debug.tickets_on_page} bilhetes visíveis — role a lista se faltarem)`;
    }
    const againstCount = (results || []).filter((r) => r.against_model_alert).length;
    if (againstCount > 0) {
      message += ` · ${againstCount} contra o modelo!`;
    }
    summary.message = message;
    const record = serializeOpenCapture(bets, results, summary, debug);
    await saveLastCapture(record);

    const notifTitle =
      summary.status === "ok"
        ? "Bolão AI — captura OK"
        : summary.status === "warn"
          ? "Bolão AI — captura parcial"
          : "Bolão AI — captura falhou";
    showNotification(notifTitle, summary.message);

    return { ok: summary.status !== "err", ...record };
  } catch (err) {
    const record = {
      kind: "open",
      finishedAt: new Date().toISOString(),
      status: "err",
      message: String(err.message || err),
      summary: { total: 0, ok: 0, skipped: 0, fail: 0 },
      bets: [],
    };
    await saveLastCapture(record);
    showNotification("Bolão AI — erro na captura", record.message);
    return { ok: false, ...record };
  } finally {
    await clearProgress();
  }
}

async function runSettledCapture(tabId, apiKey) {
  if (apiKey) await chrome.storage.local.set({ bolao_api_key: apiKey });
  await setProgress("settled", tabId);
  try {
    const inj = await ensureContentScript(tabId);
    if (!inj.ok) throw new Error(inj.error || "Falha ao injetar script");

    const response = await chrome.tabs.sendMessage(tabId, {
      type: "CAPTURE_SETTLED_BETS",
      apiKey: apiKey || "",
    });
    const bets = response?.bets || [];
    const result = response?.result || {};
    const added = result?.data?.added ?? bets.length;
    const ok = result?.ok !== false && bets.length >= 0;

    let status = "ok";
    let message = "";
    if (bets.length === 0) {
      status = "warn";
      message = "Nenhuma aposta finalizada encontrada.";
    } else if (ok) {
      message = `${bets.length} finalizada(s) capturada(s)! (${added} novas)`;
    } else {
      status = "err";
      message = result.error || "Falha ao enviar para a API.";
    }

    const record = {
      kind: "settled",
      finishedAt: new Date().toISOString(),
      status,
      message,
      summary: { total: bets.length, ok: ok ? bets.length : 0, added },
      bets: bets.map((b) => ({
        event_name: b.event_name,
        stake: b.stake,
        result: b.result,
        profit: b.profit,
        final_score: b.final_score,
      })),
    };
    await saveLastCapture(record);
    showNotification(
      ok ? "Bolão AI — finalizadas OK" : "Bolão AI — finalizadas falhou",
      message
    );
    return { ok, ...record };
  } catch (err) {
    const record = {
      kind: "settled",
      finishedAt: new Date().toISOString(),
      status: "err",
      message: String(err.message || err),
      summary: { total: 0, ok: 0 },
      bets: [],
    };
    await saveLastCapture(record);
    showNotification("Bolão AI — erro (finalizadas)", record.message);
    return { ok: false, ...record };
  } finally {
    await clearProgress();
  }
}

async function runWalletCapture(tabId, apiKey, userId) {
  const uid = userId || "jamarorn";
  if (apiKey) await chrome.storage.local.set({ bolao_api_key: apiKey });
  await chrome.storage.local.set({ bolao_user_id: uid });
  await setProgress("wallet", tabId);
  try {
    const inj = await ensureContentScript(tabId);
    if (!inj.ok) throw new Error(inj.error || "Falha ao injetar script");

    const response = await chrome.tabs.sendMessage(tabId, {
      type: "CAPTURE_WALLET_CSV",
      apiKey: apiKey || "",
      userId: uid,
    });
    const rows = response?.rows || [];
    const upload = response?.result;

    let status = "ok";
    let message = "";
    if (rows.length === 0) {
      status = "warn";
      message = "Nenhuma transação encontrada no extrato.";
    } else if (upload?.ok) {
      const n = upload.upload?.n_rows || rows.length;
      const pairs = upload.reconcile?.n_pairs;
      message = `${n} linhas enviadas` + (pairs != null ? ` · ${pairs} pares reconciliados` : "");
    } else {
      status = "err";
      message = upload?.error || "Upload do extrato falhou.";
    }

    const record = {
      kind: "wallet",
      finishedAt: new Date().toISOString(),
      status,
      message,
      summary: { total: rows.length, ok: upload?.ok ? rows.length : 0 },
      bets: rows.slice(0, 12).map((r) => ({
        event_name: r.type,
        stake: r.amount,
        datetime: r.datetime,
      })),
    };
    await saveLastCapture(record);
    showNotification(
      status === "ok" ? "Bolão AI — extrato OK" : "Bolão AI — extrato falhou",
      message
    );
    return { ok: status === "ok", ...record };
  } catch (err) {
    const record = {
      kind: "wallet",
      finishedAt: new Date().toISOString(),
      status: "err",
      message: String(err.message || err),
      summary: { total: 0, ok: 0 },
      bets: [],
    };
    await saveLastCapture(record);
    showNotification("Bolão AI — erro (extrato)", record.message);
    return { ok: false, ...record };
  } finally {
    await clearProgress();
  }
}

chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
  if (request.type === "START_CAPTURE_OPEN") {
    runOpenBetsCapture(request.tabId, request.apiKey).then(sendResponse);
    return true;
  }

  if (request.type === "START_CAPTURE_SETTLED") {
    runSettledCapture(request.tabId, request.apiKey).then(sendResponse);
    return true;
  }

  if (request.type === "START_CAPTURE_WALLET") {
    runWalletCapture(request.tabId, request.apiKey, request.userId).then(sendResponse);
    return true;
  }

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
    return true;
  }

  if (request.type === "API_GET_OPEN_BETS") {
    const { apiKey } = request;
    apiFetch("/user/open-bets", {
      headers: apiKey ? { "X-API-Key": apiKey } : {},
    }).then(sendResponse);
    return true;
  }

  if (request.type === "API_DEDUPE_OPEN_BETS") {
    const { apiKey } = request;
    apiFetch("/user/open-bets/dedupe", {
      method: "POST",
      headers: apiKey ? { "X-API-Key": apiKey } : {},
    }).then(sendResponse);
    return true;
  }

  if (request.type === "API_CHECK_AGAINST_MODEL") {
    const { payload, apiKey } = request;
    apiFetch("/user/bets/check-against-model", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(apiKey ? { "X-API-Key": apiKey } : {}),
      },
      body: JSON.stringify(payload),
    }).then(sendResponse);
    return true;
  }

  if (request.type === "START_LIVE_PANEL") {
    (async () => {
      const tabId = request.tabId;
      const fallbackEventId = request.eventId;
      const ensured = await ensureLivePanelScripts(tabId);
      if (!ensured.ok) {
        sendResponse({ ok: false, error: ensured.error || "Não foi possível injetar o painel." });
        return;
      }
      chrome.tabs.sendMessage(tabId, { type: "ENABLE_LIVE_PANEL" }, (resp) => {
        if (chrome.runtime.lastError) {
          sendResponse({
            ok: false,
            error: chrome.runtime.lastError.message || "Recarregue a página (F5) e tente de novo.",
          });
          return;
        }
        sendResponse({
          ok: true,
          eventId: resp?.eventId || fallbackEventId || null,
          injected: ensured.injected || false,
        });
      });
    })();
    return true;
  }

  if (request.type === "API_GET_LIVE_ADVICE") {
    const { eventId, apiKey, bankroll = 1000, phase = "friendly" } = request;
    const qs = new URLSearchParams({
      phase,
      bankroll: String(bankroll),
    });
    apiFetch(`/worldcup/superbet/live/${eventId}/advice?${qs}`, {
      headers: apiKey ? { "X-API-Key": apiKey } : {},
    }).then(sendResponse);
    return true;
  }

  if (request.type === "SHOW_AGAINST_MODEL_NOTIFICATION") {
    showNotification(
      "⛔ Bolão AI — contra o palpite",
      request.message || "Aposta 1X2 diverge do modelo"
    );
    sendResponse({ ok: true });
    return true;
  }

  if (request.type === "API_POST_SETTLED_BETS") {
    const { payload, apiKey } = request;
    apiFetch("/user/settled-bets/batch", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(apiKey ? { "X-API-Key": apiKey } : {}),
      },
      body: JSON.stringify({ bets: payload }),
    }).then(sendResponse);
    return true;
  }

  if (request.type === "API_UPLOAD_WALLET_CSV") {
    const { csvText, apiKey, userId } = request;
    (async () => {
      const blob = new Blob([csvText], { type: "text/csv;charset=utf-8" });
      const form = new FormData();
      form.append("file", blob, "superbet_carteira_extension.csv");

      let uploadResult = null;
      for (const base of API_BASES) {
        try {
          const resp = await fetch(
            `${base}/user/transactions/upload?user_id=${encodeURIComponent(userId || "jamarorn")}`,
            {
              method: "POST",
              headers: apiKey ? { "X-API-Key": apiKey } : {},
              body: form,
            }
          );
          uploadResult = {
            ok: resp.ok,
            status: resp.status,
            data: await resp.json().catch(() => ({})),
          };
          if (resp.ok) break;
        } catch (err) {
          uploadResult = { ok: false, error: String(err) };
        }
      }

      if (!uploadResult?.ok) {
        sendResponse(uploadResult || { ok: false, error: "Upload falhou" });
        return;
      }

      const reconcile = await apiFetch(
        `/user/transactions/reconcile?user_id=${encodeURIComponent(userId || "jamarorn")}`,
        {
          method: "POST",
          headers: apiKey ? { "X-API-Key": apiKey } : {},
        }
      );
      sendResponse({ ok: true, upload: uploadResult.data, reconcile: reconcile.data || reconcile });
    })();
    return true;
  }

  if (request.type === "QUEUE_SUPERBET_TICKET") {
    queueSuperbetTicket(request.payload).then(sendResponse);
    return true;
  }

  if (request.type === "EXECUTE_CASHOUT") {
    executeCashoutOnSuperbet(request.payload || {}).then((result) => {
      if (result?.ok) {
        showNotification(
          "Bolão AI — cash-out executado",
          `Ticket ${request.payload?.ticketCode || ""} · R$ ${Number(result.value || request.payload?.minValue || 0).toFixed(2)}`,
        );
      }
      sendResponse(result);
    });
    return true;
  }

  if (request.type === "CASHOUT_ALERT") {
    const p = request.payload || {};
    showNotification(p.title || "Bolão AI — cash-out", p.body || "Meta de cash-out atingida.");
    sendResponse({ ok: true });
    return true;
  }

  if (request.type === "TICKET_BUILDER_RESULT") {
    const { okCount, total, crossGame } = request.payload || {};
    if (!crossGame && okCount != null && total != null) {
      showNotification(
        "Bolão AI — cupom montado",
        `${okCount}/${total} perna(s) clicadas — confira stake e confirme na Superbet.`,
      );
    }
    sendResponse({ ok: true });
    return true;
  }

  if (request.type === "BACBO_WS_BATCH") {
    (async () => {
      const { messages, tableId, wsUrl } = request;
      if (!Array.isArray(messages) || !messages.length) {
        sendResponse({ ok: true, inserted: 0 });
        return;
      }
      const items = await chrome.storage.local.get(["bolao_api_key"]);
      const apiKey = items.bolao_api_key || "";
      const resp = await apiFetch("/casino/bacbo/ingest", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(apiKey ? { "X-API-Key": apiKey } : {}),
        },
        body: JSON.stringify({
          messages,
          table_id: tableId || null,
          ws_url: wsUrl || null,
        }),
      });
      if (resp.ok && resp.data?.inserted > 0) {
        await chrome.storage.local.set({
          bolao_bacbo_last_ingest: {
            at: new Date().toISOString(),
            inserted: resp.data.inserted,
            tableId: resp.data.table_id,
          },
        });
      }
      sendResponse({ ok: resp.ok, ...resp.data, error: resp.error });
    })();
    return true;
  }

  if (request.type === "CHECK_BACBO_STATUS") {
    (async () => {
      const tabId = request.tabId;
      if (!tabId) {
        sendResponse({ ok: false, error: "Aba não informada." });
        return;
      }
      let frames = [];
      try {
        frames = await chrome.webNavigation.getAllFrames({ tabId });
      } catch (err) {
        sendResponse({ ok: false, error: String(err) });
        return;
      }
      const hits = [];
      for (const frame of frames) {
        try {
          const resp = await chrome.tabs.sendMessage(
            tabId,
            { type: "PING_BACBO" },
            { frameId: frame.frameId },
          );
          if (resp?.ok) {
            hits.push({
              frameId: frame.frameId,
              url: frame.url || "",
              ...resp,
            });
          }
        } catch {
          /* frame sem content script */
        }
      }
      const evo = hits.filter((h) => /evo-games\.com/i.test(h.url || h.hostname || ""));
      const active = evo.find((h) => h.tableId) || evo[0] || hits[0];
      sendResponse({
        ok: true,
        framesChecked: frames.length,
        hooks: hits.length,
        evoFrames: evo.length,
        active,
        hits,
      });
    })();
    return true;
  }

  return false;
});

chrome.runtime.onInstalled.addListener(() => {
  console.info("[Bolão AI] Extensão instalada/atualizada.");
});
