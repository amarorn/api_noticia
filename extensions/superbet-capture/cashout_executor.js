/**
 * Execução de cash-out na Superbet (API autenticada + clique no botão).
 * Requer aba logada em superbet.com/br/apostas.
 */
(function () {
  "use strict";

  const CASHOUT_BASE =
    "https://production-superbet-cashout.freetls.fastly.net/cashout/api/v2";
  const EXECUTED_KEY = "bolao_cashout_executed";

  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  function parseMoney(str) {
    if (str == null) return null;
    const cleaned = String(str).replace(/[^\d,.-]/g, "").replace(/\./g, "").replace(",", ".");
    const n = parseFloat(cleaned);
    return Number.isFinite(n) ? n : null;
  }

  function getSuperbetAuthHeaders() {
    const headers = { Accept: "application/json", "Content-Type": "application/json" };
    try {
      for (const key of [
        "access_token",
        "authToken",
        "token",
        "jwt",
        "superbet_auth",
        "auth",
      ]) {
        const raw = localStorage.getItem(key);
        if (!raw) continue;
        if (raw.startsWith("{")) {
          const obj = JSON.parse(raw);
          const token = obj.access_token || obj.token || obj.jwt;
          if (token) {
            headers.Authorization = `Bearer ${token}`;
            break;
          }
        } else {
          headers.Authorization = `Bearer ${raw}`;
          break;
        }
      }
    } catch {
      /* localStorage indisponível */
    }
    return headers;
  }

  async function fetchCashoutQuote(ticketCode) {
    const url = `${CASHOUT_BASE}/requestCashoutValue?target=SB_BR&ticketCode=${encodeURIComponent(ticketCode)}`;
    const resp = await fetch(url, {
      method: "GET",
      credentials: "include",
      headers: getSuperbetAuthHeaders(),
    });
    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      return { ok: false, error: `quote_http_${resp.status}`, detail: text.slice(0, 200) };
    }
    const data = await resp.json();
    if (!data?.eligible) {
      return {
        ok: false,
        error: data?.unavailabilityReason || "ineligible",
        data,
      };
    }
    return { ok: true, value: Number(data.value) || 0, data };
  }

  async function postCashoutEndpoint(endpoint, body) {
    const resp = await fetch(`${CASHOUT_BASE}/${endpoint}`, {
      method: "POST",
      credentials: "include",
      headers: getSuperbetAuthHeaders(),
      body: JSON.stringify(body),
    });
    const text = await resp.text();
    let data = {};
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { raw: text.slice(0, 300) };
    }
    return { ok: resp.ok, status: resp.status, data };
  }

  /**
   * Opção B — tenta POST na API de cash-out com sessão do usuário.
   */
  async function executeCashoutViaApi(ticketCode, minValue) {
    const quote = await fetchCashoutQuote(ticketCode);
    if (!quote.ok) return { ok: false, method: "api", ...quote };

    const value = quote.value;
    if (minValue != null && value < minValue) {
      return { ok: false, method: "api", error: "below_min", value, minValue };
    }

    const payload = {
      target: "SB_BR",
      ticketCode,
      value,
      ticket_code: ticketCode,
    };

    const endpoints = ["cashout", "requestCashout", "confirmCashout", "placeCashout"];
    for (const ep of endpoints) {
      const result = await postCashoutEndpoint(ep, payload);
      if (result.ok) {
        return { ok: true, method: "api", endpoint: ep, value, data: result.data };
      }
    }

    return { ok: false, method: "api", error: "api_post_failed", value, quote: quote.data };
  }

  function findBetCardByTicket(ticketCode) {
    if (!ticketCode) return null;
    const norm = String(ticketCode).trim().toUpperCase();
    const candidates = document.querySelectorAll(
      'article, [class*="ticket"], [class*="bet"], [class*="Ticket"], [class*="Bet"], div',
    );
    for (const el of candidates) {
      const text = (el.innerText || el.textContent || "").toUpperCase();
      if (!text.includes(norm)) continue;
      if (text.length > 8000) continue;
      if (/(GANHO|POTENCIAL|CASHOUT|APOSTA)/i.test(text)) return el;
    }
    return null;
  }

  function findCashoutButton(root) {
    const btns = Array.from(root.querySelectorAll('button, [role="button"], a')).filter((b) =>
      /cash\s*-?\s*out/i.test(b.textContent || ""),
    );
    return btns[0] || null;
  }

  async function confirmCashoutModal() {
    await sleep(500);
    const dialogs = document.querySelectorAll('[role="dialog"], [class*="modal"], [class*="Modal"]');
    const scope = dialogs.length ? dialogs[dialogs.length - 1] : document.body;
    const confirmBtns = Array.from(scope.querySelectorAll('button, [role="button"]')).filter((b) => {
      const t = (b.textContent || "").trim();
      if (!t || t.length > 40) return false;
      return (
        /^(confirmar|sim|cash\s*-?\s*out|sacar|ok|fechar aposta)$/i.test(t) ||
        /confirmar/i.test(t)
      );
    });
    if (confirmBtns.length) {
      confirmBtns[confirmBtns.length - 1].click();
      await sleep(400);
      return true;
    }
    return false;
  }

  /**
   * Opção A — clica no botão Cashout do card na página de apostas.
   */
  async function executeCashoutViaClick(ticketCode, minValue) {
    const card = findBetCardByTicket(ticketCode);
    if (!card) return { ok: false, method: "click", error: "card_not_found" };

    const btn = findCashoutButton(card);
    if (!btn) return { ok: false, method: "click", error: "no_cashout_button" };

    const valMatch = (btn.textContent || "").match(/([\d.,]+)/);
    if (valMatch && minValue != null) {
      const displayed = parseMoney(valMatch[1]);
      if (displayed != null && displayed < minValue) {
        return { ok: false, method: "click", error: "below_min", value: displayed, minValue };
      }
    }

    btn.scrollIntoView({ block: "center", behavior: "smooth" });
    await sleep(200);
    btn.click();
    const confirmed = await confirmCashoutModal();

    return {
      ok: true,
      method: "click",
      ticketCode,
      confirmed,
    };
  }

  async function wasRecentlyExecuted(ticketCode) {
    return new Promise((resolve) => {
      chrome.storage.session.get([EXECUTED_KEY], (items) => {
        const map = items[EXECUTED_KEY] || {};
        resolve(Boolean(map[ticketCode]));
      });
    });
  }

  function markExecuted(ticketCode) {
    chrome.storage.session.get([EXECUTED_KEY], (items) => {
      const map = items[EXECUTED_KEY] || {};
      map[ticketCode] = Date.now();
      chrome.storage.session.set({ [EXECUTED_KEY]: map });
    });
  }

  /**
   * Tenta API (B) e depois clique (A).
   */
  async function executeCashout(options) {
    const ticketCode = options?.ticketCode;
    const minValue = options?.minValue ?? null;
    const skipIfDone = options?.skipIfDone !== false;

    if (!ticketCode) return { ok: false, error: "missing_ticket_code" };

    if (skipIfDone && (await wasRecentlyExecuted(ticketCode))) {
      return { ok: false, error: "already_executed_session", ticketCode };
    }

    let apiResult = null;
    try {
      apiResult = await executeCashoutViaApi(ticketCode, minValue);
      if (apiResult.ok) {
        markExecuted(ticketCode);
        return apiResult;
      }
    } catch (err) {
      apiResult = { ok: false, method: "api", error: String(err) };
    }

    try {
      const clickResult = await executeCashoutViaClick(ticketCode, minValue);
      if (clickResult.ok) {
        markExecuted(ticketCode);
        return { ...clickResult, apiAttempt: apiResult };
      }
      return { ok: false, apiAttempt: apiResult, clickAttempt: clickResult };
    } catch (err) {
      return { ok: false, apiAttempt: apiResult, error: String(err) };
    }
  }

  window.__bolaoCashoutExecutor = {
    executeCashout,
    executeCashoutViaApi,
    executeCashoutViaClick,
    fetchCashoutQuote,
  };
})();
