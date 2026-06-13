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
          errorMsg = JSON.stringify(detail);
        } else {
          errorMsg = data.message || `HTTP ${resp.status}`;
        }
      }
      return { ok: resp.ok, status: resp.status, data, error: errorMsg };
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
      files: ["content_script.js"],
    });
    await new Promise((r) => setTimeout(r, 350));
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

  return false;
});

chrome.runtime.onInstalled.addListener(() => {
  console.info("[Bolão AI] Extensão instalada/atualizada.");
});
