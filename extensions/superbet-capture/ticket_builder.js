/**
 * Monta bilhete enfileirado pelo painel Bolão AI na página do evento Superbet.
 */
(function () {
  "use strict";

  if (window.__bolaoTicketBuilderInit) return;
  window.__bolaoTicketBuilderInit = true;

  const PANEL_ID = "bolao-ai-ticket-builder";

  function legDirection(leg) {
    const blob = [
      leg.superbetPick,
      leg.outcome,
      leg.label,
      leg.market,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    if (/menos|under/i.test(blob)) return "under";
    if (/mais|over/i.test(blob)) return "over";
    return null;
  }

  function legSearchTerms(leg) {
    const terms = [];
    const push = (value) => {
      if (!value) return;
      const text = String(value).toLowerCase().trim();
      if (text.length >= 2) terms.push(text);
    };

    push(leg.superbetMarket);
    push(leg.superbetPick);
    push(leg.outcome);
    push(leg.market);

    const label = String(leg.label || "").toLowerCase();
    for (const n of label.match(/\d+[.,]\d+|\d+/g) || []) {
      terms.push(n.replace(",", "."));
      terms.push(n.replace(".", ","));
    }
    if (/menos|under/i.test(label)) terms.push("menos", "under");
    if (/mais|over/i.test(label)) terms.push("mais", "over");
    if (/1º tempo|1o tempo|primeiro tempo/i.test(label)) {
      terms.push("1º tempo", "1o tempo", "primeiro tempo");
    }
    if (/cart/i.test(label)) terms.push("cartões", "cartoes", "cartão", "cartao");
    if (/chutes no gol|chutes a gol/i.test(label)) {
      terms.push("chutes no gol", "chutes a gol");
    } else if (/chutes/i.test(label)) {
      terms.push("chutes", "total de chutes");
    }
    if (/gols/i.test(label)) terms.push("gols", "total de gols");

    if (leg.superbetMarket) {
      const market = String(leg.superbetMarket).toLowerCase();
      if (market.includes("chutes no gol")) terms.push("chutes no gol");
      if (market.includes("total de chutes")) terms.push("total de chutes");
      const team = market.split("-")[0]?.trim();
      if (team && team.length > 3) terms.push(team);
    }

    return [...new Set(terms.filter(Boolean))];
  }

  function tryClickLeg(leg) {
    const oddVariants = [
      leg.marketOdd.toFixed(2),
      leg.marketOdd.toFixed(2).replace(".", ","),
      String(leg.marketOdd),
    ];
    const terms = legSearchTerms(leg);
    const wantDir = legDirection(leg);
    const candidates = document.querySelectorAll(
      'button, [role="button"], a, span[class*="odd" i], div[class*="odd" i]',
    );

    let best = null;
    let bestScore = 0;

    for (const el of candidates) {
      const text = (el.textContent || "").trim();
      if (!text || text.length > 80) continue;
      if (!oddVariants.some((o) => text.includes(o))) continue;

      const block =
        el.closest('[class*="market" i], [class*="Market" i], section, article') ||
        el.parentElement?.parentElement?.parentElement;
      const blockText = (block?.innerText || el.closest("div")?.innerText || "").toLowerCase();

      let score = terms.filter((term) => blockText.includes(String(term).toLowerCase())).length;

      if (wantDir === "under" && /menos|under/i.test(blockText)) score += 2;
      if (wantDir === "over" && /mais|over/i.test(blockText)) score += 2;
      if (wantDir === "under" && /mais|over/i.test(blockText) && !/menos|under/i.test(text)) {
        score -= 3;
      }
      if (wantDir === "over" && /menos|under/i.test(blockText) && !/mais|over/i.test(text)) {
        score -= 3;
      }
      if (leg.superbetMarket) {
        const marketNeedle = String(leg.superbetMarket).toLowerCase();
        if (blockText.includes(marketNeedle)) score += 4;
        else if (marketNeedle.includes("total de chutes") && blockText.includes("chutes no gol")) {
          score -= 4;
        } else if (marketNeedle.includes("chutes no gol") && blockText.includes("total de chutes")) {
          score -= 4;
        }
      }

      if (score > bestScore) {
        bestScore = score;
        best = el;
      }
    }

    if (best && bestScore >= 3) {
      best.click();
      return true;
    }
    return false;
  }

  function trySetStake(stake) {
    const inputs = document.querySelectorAll('input[type="number"], input[inputmode="decimal"], input');
    for (const input of inputs) {
      const ctx = (input.closest('[class*="betslip" i], [class*="bet-slip" i]')?.innerText || "").toLowerCase();
      if (!ctx && inputs.length > 8) continue;
      input.focus();
      input.value = String(stake).replace(".", ",");
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
      return true;
    }
    return false;
  }

  function renderPanel(ticket, results) {
    let root = document.getElementById(PANEL_ID);
    if (!root) {
      root = document.createElement("div");
      root.id = PANEL_ID;
      root.style.cssText =
        "position:fixed;bottom:16px;right:16px;z-index:2147483647;width:min(360px,calc(100vw - 32px));" +
        "background:#0f172a;border:1px solid #334155;border-radius:12px;color:#e2e8f0;" +
        "font:12px/1.45 system-ui,sans-serif;box-shadow:0 12px 40px rgba(0,0,0,.55);";
      document.body.appendChild(root);
    }

    const okCount = results.filter((r) => r.ok).length;
    root.innerHTML = `
      <div style="padding:12px 14px;border-bottom:1px solid #1e293b;display:flex;justify-content:space-between;align-items:flex-start;">
        <div>
          <div style="color:#00ff88;font-weight:800;font-size:13px;">Bolão AI — Criar bilhete</div>
          <div style="color:#94a3b8;font-size:10px;margin-top:2px;">${ticket.title || "Múltipla"}</div>
        </div>
        <button type="button" id="bolao-ticket-close" style="background:transparent;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">×</button>
      </div>
      <div style="padding:10px 14px;">
        <div style="font-weight:700;color:#fbbf24;margin-bottom:8px;">
          R$ ${Number(ticket.stake).toFixed(2)} → R$ ${Number(ticket.potentialReturn).toFixed(2)} @${Number(ticket.combinedOdd).toFixed(2)}
        </div>
        <ul style="margin:0;padding:0;list-style:none;">
          ${results
            .map(
              (r) => `
            <li style="margin-bottom:6px;padding:8px;border-radius:8px;background:${r.ok ? "rgba(0,255,136,.08)" : "rgba(248,113,113,.1)"};border-left:3px solid ${r.ok ? "#00ff88" : "#f87171"};">
              ${r.ok ? "✓" : "○"} ${r.leg.superbetMarket ? `${r.leg.superbetMarket} → ${r.leg.superbetPick || ""}` : r.leg.label}
              <span style="color:#94a3b8;font-size:10px;display:block;">@${Number(r.leg.marketOdd).toFixed(2)}${r.ok ? " — clicado" : " — clique manualmente"}</span>
            </li>`,
            )
            .join("")}
        </ul>
        <p style="margin:8px 0 0;color:#64748b;font-size:10px;">
          ${okCount}/${results.length} pernas no cupom · confira stake R$ ${Number(ticket.stake).toFixed(2)} antes de apostar.
        </p>
      </div>`;

    root.querySelector("#bolao-ticket-close")?.addEventListener("click", () => root.remove());
  }

  async function applyTicket(ticket) {
    const results = [];
    for (const leg of ticket.legs || []) {
      await new Promise((r) => setTimeout(r, 450));
      const ok = tryClickLeg(leg);
      results.push({ leg, ok });
    }
    await new Promise((r) => setTimeout(r, 300));
    trySetStake(ticket.stake);
    renderPanel(ticket, results);

    chrome.runtime.sendMessage({
      type: "TICKET_BUILDER_RESULT",
      payload: {
        ticketId: ticket.id,
        okCount: results.filter((r) => r.ok).length,
        total: results.length,
      },
    });
  }

  chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
    if (request.type === "APPLY_PENDING_TICKET") {
      chrome.storage.local.get(["bolao_pending_ticket"], (items) => {
        const ticket = items.bolao_pending_ticket;
        if (!ticket) {
          sendResponse({ ok: false, error: "Nenhum bilhete pendente." });
          return;
        }
        applyTicket(ticket)
          .then(() => sendResponse({ ok: true }))
          .catch((err) => sendResponse({ ok: false, error: String(err?.message || err) }));
      });
      return true;
    }
    return false;
  });

  chrome.storage.local.get(["bolao_pending_ticket"], (items) => {
    const ticket = items.bolao_pending_ticket;
    if (!ticket?.superbetEventId) return;
    const pageId =
      typeof window.bolaoExtractSuperbetEventId === "function"
        ? window.bolaoExtractSuperbetEventId()
        : null;
    if (pageId && pageId === ticket.superbetEventId) {
      setTimeout(() => applyTicket(ticket), 1200);
    }
  });
})();
