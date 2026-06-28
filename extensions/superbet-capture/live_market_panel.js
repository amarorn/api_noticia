/**
 * Painel Bolão AI sobre a página de evento ao vivo Superbet.
 * Cruza mercados da API com palpite do modelo (verde = edge, vermelho = evitar).
 */
(function () {
  "use strict";

  if (window.__bolaoLivePanelInit) return;
  window.__bolaoLivePanelInit = true;

  const PANEL_ID = "bolao-ai-live-panel";
  const STORAGE_MINIMIZED = "bolao_live_panel_minimized";
  const POLL_MS = 20_000;
  const FETCH_TIMEOUT_MS = 180_000;
  const FRONTEND_BASE = "http://localhost:5173";
  const API_BASES = ["http://127.0.0.1:8000", "http://localhost:8000"];

  let pollTimer = null;
  let lastEventId = null;
  let refreshInFlight = false;
  let loadingStartedAt = 0;
  let loadingTicker = null;
  let panelMinimized = false;

  function storageGet(keys) {
    return new Promise((resolve) => {
      chrome.storage.local.get(keys, resolve);
    });
  }

  function parseApiError(data, status) {
    const detail = data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
    if (detail && typeof detail === "object") return detail.message || detail.msg || JSON.stringify(detail);
    return data?.message || `HTTP ${status}`;
  }

  async function fetchLiveAdvice(eventId, apiKey) {
    if (!apiKey) {
      return {
        error: "API Key ausente — cole no popup da extensão (mesma do .env).",
      };
    }

    const qs = new URLSearchParams({ phase: "friendly", bankroll: "1000", fast: "true" });
    const path = `/worldcup/superbet/live/${eventId}/advice?${qs}`;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

    let lastError = "API indisponível em localhost:8000";
    for (const base of API_BASES) {
      try {
        const resp = await fetch(`${base}${path}`, {
          headers: { "X-API-Key": apiKey },
          signal: controller.signal,
        });
        clearTimeout(timeout);
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          return { error: parseApiError(data, resp.status) };
        }
        return data;
      } catch (err) {
        if (err?.name === "AbortError") {
          return {
            error: `API demorou mais de ${FETCH_TIMEOUT_MS / 1000}s. Abra o painel completo ↓`,
          };
        }
        lastError = String(err?.message || err);
      }
    }
    clearTimeout(timeout);
    return { error: lastError };
  }

  function extractEventId() {
    if (typeof window.bolaoExtractSuperbetEventId === "function") {
      const id = window.bolaoExtractSuperbetEventId();
      if (id) return id;
    }
    const hay = location.href;
    const patterns = [
      /\/(?:event|evento)\/(\d+)/i,
      /\/e-(\d+)/i,
      /[?&]event(?:Id|_id)=(\d+)/i,
      /#\/(?:event|evento)\/(\d+)/i,
    ];
    for (const p of patterns) {
      const m = hay.match(p);
      if (m) return parseInt(m[1], 10);
    }
    const seg = location.pathname.split("/").filter(Boolean).pop() || "";
    const slug = seg.match(/-(\d{5,})$/);
    if (slug) return parseInt(slug[1], 10);
    const el = document.querySelector("[data-event-id], [data-eventid]");
    if (el) {
      const v = el.getAttribute("data-event-id") || el.getAttribute("data-eventid");
      const n = parseInt(v || "", 10);
      if (Number.isFinite(n)) return n;
    }
    return null;
  }

  function stopLoadingTicker() {
    if (loadingTicker) {
      clearInterval(loadingTicker);
      loadingTicker = null;
    }
  }

  function startLoadingTicker(eventId) {
    stopLoadingTicker();
    loadingStartedAt = Date.now();
    loadingTicker = setInterval(() => {
      const root = document.getElementById(PANEL_ID);
      if (!root || !root.querySelector(".bolao-loading")) {
        stopLoadingTicker();
        return;
      }
      const sec = Math.floor((Date.now() - loadingStartedAt) / 1000);
      const el = root.querySelector(".bolao-loading");
      if (el) {
        el.textContent =
          sec < 15
            ? `Carregando mercados #${eventId}… (${sec}s)`
            : `Modelo rodando… (${sec}s — pode levar até 60s)`;
      }
    }, 1000);
  }

  function tierClass(tier, meets, against) {
    if (against) return "bolao-row-red";
    if (tier === "forte" && meets) return "bolao-row-green";
    if (tier === "moderada" && meets) return "bolao-row-green";
    if (meets) return "bolao-row-yellow";
    return "bolao-row-muted";
  }

  function isAgainstH2h(outcome, pregame, inplay) {
    const o = String(outcome || "").toUpperCase();
    const norm = o === "HOME" || o === "1" ? "1" : o === "AWAY" || o === "2" ? "2" : o === "DRAW" || o === "X" ? "X" : o;
    if (!["1", "X", "2"].includes(norm)) return false;
    return norm !== pregame && norm !== inplay;
  }

  function panelHeaderHtml(opts = {}) {
    const { title = "Bolão AI", subtitle = "", live = false } = opts;
    return `
      <header class="bolao-panel-header" data-bolao-drag-handle>
        <div class="bolao-header-brand">
          <span class="bolao-logo-mark" aria-hidden="true"></span>
          <div class="bolao-header-text">
            <span class="bolao-logo">${title}</span>
            ${subtitle ? `<span class="bolao-sub">${subtitle}</span>` : ""}
          </div>
          ${live ? '<span class="bolao-live-pill"><span class="bolao-live-dot"></span>AO VIVO</span>' : ""}
        </div>
        <div class="bolao-header-actions">
          <button type="button" class="bolao-btn-icon bolao-minimize" title="Minimizar" aria-label="Minimizar painel">−</button>
          <button type="button" class="bolao-btn-icon bolao-expand" title="Expandir" aria-label="Expandir painel">▢</button>
          <button type="button" class="bolao-btn-icon bolao-close" title="Fechar" aria-label="Fechar painel">×</button>
        </div>
      </header>`;
  }

  function miniBarHtml(data, eventId) {
    if (data?.error) {
      return `
        <div class="bolao-panel-mini" role="button" tabindex="0" aria-label="Expandir painel Bolão AI">
          <span class="bolao-mini-logo"></span>
          <span class="bolao-mini-text bolao-mini-err">Erro API — clique para ver</span>
          <span class="bolao-mini-chevron">›</span>
        </div>`;
    }
    if (data?.loading) {
      return `
        <div class="bolao-panel-mini" role="button" tabindex="0" aria-label="Expandir painel Bolão AI">
          <span class="bolao-mini-logo bolao-mini-pulse"></span>
          <span class="bolao-mini-text">Carregando #${eventId}…</span>
          <span class="bolao-mini-chevron">›</span>
        </div>`;
    }

    const guard = data.bet_guardrails || {};
    const strat = data.strategy || {};
    const inplayPal = guard.inplay_palpite || strat.posture || "—";
    const score = (data.current_score || "0x0").replace("x", "·");
    const minute = data.minute ?? 0;
    const block = guard.block_new_bets;
    const opps = (strat.opportunities || []).length;

    return `
      <div class="bolao-panel-mini" role="button" tabindex="0" aria-label="Expandir painel Bolão AI">
        <span class="bolao-mini-logo"></span>
        <div class="bolao-mini-stack">
          <span class="bolao-mini-score">${score} <em>${minute}'</em></span>
          <span class="bolao-mini-palpite">Palpite <strong>${inplayPal}</strong>${opps ? ` · ${opps} edge` : ""}</span>
        </div>
        ${block ? '<span class="bolao-mini-badge">⛔</span>' : '<span class="bolao-mini-chevron">›</span>'}
      </div>`;
  }

  function applyMinimizedState(root, minimized) {
    panelMinimized = minimized;
    root.classList.toggle("bolao-minimized", minimized);
    chrome.storage.local.set({ [STORAGE_MINIMIZED]: minimized });
  }

  function bindPanelControls(root) {
    const minimizeBtn = root.querySelector(".bolao-minimize");
    const expandBtn = root.querySelector(".bolao-expand");
    const miniBar = root.querySelector(".bolao-panel-mini");

    minimizeBtn?.addEventListener("click", (e) => {
      e.stopPropagation();
      applyMinimizedState(root, true);
    });

    expandBtn?.addEventListener("click", (e) => {
      e.stopPropagation();
      applyMinimizedState(root, false);
    });

    const openPanel = () => applyMinimizedState(root, false);
    miniBar?.addEventListener("click", openPanel);
    miniBar?.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openPanel();
      }
    });

    root.querySelector(".bolao-close")?.addEventListener("click", () => {
      stopPanel();
      root.remove();
      chrome.storage.local.set({ bolao_live_panel_enabled: false });
    });

    bindDrag(root);
  }

  function bindDrag(root) {
    const handle = root.querySelector("[data-bolao-drag-handle]");
    if (!handle) return;

    let dragging = false;
    let startX = 0;
    let startY = 0;
    let startLeft = 0;
    let startTop = 0;

    handle.addEventListener("mousedown", (e) => {
      if (e.button !== 0 || e.target.closest("button")) return;
      dragging = true;
      const rect = root.getBoundingClientRect();
      startX = e.clientX;
      startY = e.clientY;
      startLeft = rect.left;
      startTop = rect.top;
      root.style.right = "auto";
      root.style.bottom = "auto";
      root.style.left = `${startLeft}px`;
      root.style.top = `${startTop}px`;
      handle.style.cursor = "grabbing";
      e.preventDefault();
    });

    const onMove = (e) => {
      if (!dragging) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      const maxLeft = Math.max(8, window.innerWidth - root.offsetWidth - 8);
      const maxTop = Math.max(8, window.innerHeight - root.offsetHeight - 8);
      root.style.left = `${Math.min(maxLeft, Math.max(8, startLeft + dx))}px`;
      root.style.top = `${Math.min(maxTop, Math.max(8, startTop + dy))}px`;
    };

    const onUp = () => {
      if (!dragging) return;
      dragging = false;
      handle.style.cursor = "grab";
    };

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }

  function renderPanel(data, eventId) {
    let root = document.getElementById(PANEL_ID);
    if (!root) {
      root = document.createElement("div");
      root.id = PANEL_ID;
      document.body.appendChild(root);
      injectStyles();
      chrome.storage.local.get([STORAGE_MINIMIZED], (items) => {
        panelMinimized = Boolean(items[STORAGE_MINIMIZED]);
        root.classList.toggle("bolao-minimized", panelMinimized);
      });
    }

    if (data.error) {
      stopLoadingTicker();
      root.innerHTML = `
        <div class="bolao-panel-inner">
          ${panelHeaderHtml({ subtitle: `Evento #${eventId}` })}
          <div class="bolao-panel-body">
            <div class="bolao-alert bolao-alert-err">
              <span class="bolao-alert-icon">⚠</span>
              <p>${data.error}</p>
            </div>
            <p class="bolao-hint">Confirme API em localhost:8000 e API Key no popup.</p>
            <footer class="bolao-footer">
              <a class="bolao-link" href="${FRONTEND_BASE}/ao-vivo/${eventId}" target="_blank" rel="noopener">Painel completo →</a>
            </footer>
          </div>
          ${miniBarHtml(data, eventId)}
        </div>`;
      bindPanelControls(root);
      root.classList.toggle("bolao-minimized", panelMinimized);
      return;
    }

    if (data.loading) {
      root.innerHTML = `
        <div class="bolao-panel-inner">
          ${panelHeaderHtml({ subtitle: `Evento #${eventId}` })}
          <div class="bolao-panel-body">
            <div class="bolao-loading-wrap">
              <div class="bolao-spinner" aria-hidden="true"></div>
              <p class="bolao-loading">Carregando mercados #${eventId}…</p>
              <p class="bolao-hint">Consultando modelo × Superbet (até 60s)</p>
            </div>
            <footer class="bolao-footer">
              <a class="bolao-link" href="${FRONTEND_BASE}/ao-vivo/${eventId}" target="_blank" rel="noopener">Painel completo →</a>
            </footer>
          </div>
          ${miniBarHtml(data, eventId)}
        </div>`;
      bindPanelControls(root);
      root.classList.toggle("bolao-minimized", panelMinimized);
      startLoadingTicker(eventId);
      return;
    }

    stopLoadingTicker();

    const strat = data.strategy || {};
    const guard = data.bet_guardrails || {};
    const pre = guard.pregame_palpite || strat.posture || "—";
    const inplayPal = guard.inplay_palpite || pre;
    const opps = (strat.opportunities || []).slice(0, 5);
    const scan = (strat.market_scan || []).filter((m) => m.meets_threshold).slice(0, 6);
    const fullScan = strat.market_scan || [];
    const teamTotals = fullScan
      .filter((m) => /^(home|away)_over_/.test(m.market || "") && m.meets_threshold)
      .slice(0, 4);
    const handicaps = fullScan
      .filter((m) => /_(hcap|ah)_/.test(m.market || "") && m.meets_threshold)
      .slice(0, 4);
    const combo = strat.combo_ticket;
    const block = guard.block_new_bets;
    const score = data.current_score || "0x0";
    const minute = data.minute ?? 0;
    const hardStop = minute >= (guard.hard_stop_minute || 88);

    const h2hScan = (strat.market_scan || []).filter((m) => m.market === "h2h");
    const avoid = h2hScan.filter((m) => isAgainstH2h(m.outcome, pre, inplayPal));
    const scoreParts = score.split(/x/i);
    const scoreDisplay =
      scoreParts.length === 2
        ? `<span class="bolao-score-home">${scoreParts[0]}</span><span class="bolao-score-sep">:</span><span class="bolao-score-away">${scoreParts[1]}</span>`
        : score;

    root.innerHTML = `
      <div class="bolao-panel-inner">
        ${panelHeaderHtml({
          subtitle: `${data.home_team || ""} × ${data.away_team || ""}`,
          live: true,
        })}
        <div class="bolao-panel-body">
          <div class="bolao-hero">
            <div class="bolao-hero-score">${scoreDisplay}</div>
            <div class="bolao-hero-meta">
              <span class="bolao-minute">${minute}<small>'</small></span>
              ${block ? '<span class="bolao-status bolao-status-warn">Sem novos aportes</span>' : '<span class="bolao-status bolao-status-ok">Janela aberta</span>'}
            </div>
          </div>

          <div class="bolao-palpite-card">
            <span class="bolao-palpite-label">Palpite modelo</span>
            <span class="bolao-palpite-value">${inplayPal}</span>
            ${
              guard.pregame_prob != null
                ? `<span class="bolao-palpite-meta">${(guard.pregame_prob * 100).toFixed(0)}% pré-jogo</span>`
                : ""
            }
          </div>

          ${
            block
              ? `<div class="bolao-alert bolao-alert-warn">
            <span class="bolao-alert-icon">⛔</span>
            <p>Após ${guard.block_minute || 45}' — só cash-out em bilhetes abertos.${hardStop ? " Fim de jogo: bloqueio total." : ""}</p>
          </div>`
              : ""
          }

          <section class="bolao-section">
            <h3><span class="bolao-section-icon bolao-icon-green">✓</span> Melhores opções</h3>
            <div class="bolao-section-body">
            ${
              opps.length
                ? opps
                    .map(
                      (o) => `
              <div class="bolao-row ${tierClass(o.tier, true, false)}">
                <span class="bolao-label">${o.label}</span>
                <span class="bolao-meta">@${Number(o.market_odd).toFixed(2)} · +${Number(o.edge_pp).toFixed(1)}pp · <em>${o.tier}</em></span>
              </div>`
                    )
                    .join("")
                : scan.length
                  ? scan
                      .map(
                        (m) => `
              <div class="bolao-row bolao-row-yellow">
                <span class="bolao-label">${m.label}</span>
                <span class="bolao-meta">EV +${(Number(m.expected_value) * 100).toFixed(1)}%</span>
              </div>`
                      )
                      .join("")
                  : `<p class="bolao-muted">Nenhuma oportunidade forte agora — aguardar.</p>`
            }
            </div>
          </section>

          ${
            teamTotals.length
              ? `<section class="bolao-section">
            <h3><span class="bolao-section-icon">⚽</span> Total por time</h3>
            <div class="bolao-section-body">
            ${teamTotals
              .map(
                (m) => `
              <div class="bolao-row bolao-row-green">
                <span class="bolao-label">${m.label}</span>
                <span class="bolao-meta">@${Number(m.market_odd).toFixed(2)} · +${Number(m.edge_pp).toFixed(1)}pp</span>
              </div>`
              )
              .join("")}
            </div>
          </section>`
              : ""
          }

          ${
            handicaps.length
              ? `<section class="bolao-section">
            <h3><span class="bolao-section-icon">📊</span> Handicap / AH</h3>
            <div class="bolao-section-body">
            ${handicaps
              .map(
                (m) => `
              <div class="bolao-row bolao-row-yellow">
                <span class="bolao-label">${m.label}</span>
                <span class="bolao-meta">@${Number(m.market_odd).toFixed(2)} · +${Number(m.edge_pp).toFixed(1)}pp</span>
              </div>`
              )
              .join("")}
            </div>
          </section>`
              : ""
          }

          ${
            avoid.length
              ? `<section class="bolao-section">
            <h3><span class="bolao-section-icon bolao-icon-red">⛔</span> Evitar</h3>
            <div class="bolao-section-body">
            ${avoid
              .map(
                (m) => `
              <div class="bolao-row bolao-row-red">
                <span class="bolao-label">${m.label}</span>
                <span class="bolao-meta">@${Number(m.market_odd).toFixed(2)} · contra ${inplayPal}</span>
              </div>`
              )
              .join("")}
            </div>
          </section>`
              : ""
          }

          ${
            combo?.available
              ? `<section class="bolao-section bolao-section-combo">
            <h3><span class="bolao-section-icon">🎯</span> Combo sugerido</h3>
            <div class="bolao-section-body">
            <p class="bolao-combo-title">${combo.title || "Bilhete cruzado"}</p>
            <ul class="bolao-combo-legs">
              ${(combo.main_bets || [])
                .slice(0, 3)
                .map((leg) => `<li>${leg.label} <span>(${(leg.hit_rate * 100).toFixed(0)}% hist.)</span></li>`)
                .join("")}
            </ul>
            ${
              combo.combo_odd
                ? `<p class="bolao-meta">Odd ~${Number(combo.combo_odd).toFixed(2)} · stake ~${combo.suggested_stake_pct}%</p>`
                : ""
            }
            </div>
          </section>`
              : ""
          }

          <footer class="bolao-footer">
            <a class="bolao-link" href="${FRONTEND_BASE}/ao-vivo/${eventId}" target="_blank" rel="noopener">Painel completo →</a>
            <span class="bolao-ts">${new Date().toLocaleTimeString("pt-BR")}</span>
          </footer>
        </div>
        ${miniBarHtml(data, eventId)}
      </div>`;

    bindPanelControls(root);
    root.classList.toggle("bolao-minimized", panelMinimized);
  }

  function injectStyles() {
    if (document.getElementById("bolao-ai-live-panel-styles")) return;
    const style = document.createElement("style");
    style.id = "bolao-ai-live-panel-styles";
    style.textContent = `
      #${PANEL_ID} {
        --bolao-bg: #0b1220;
        --bolao-surface: #111827;
        --bolao-surface-2: #1a2332;
        --bolao-border: rgba(148, 163, 184, 0.18);
        --bolao-text: #e8eef7;
        --bolao-muted: #94a3b8;
        --bolao-accent: #00e676;
        --bolao-accent-dim: rgba(0, 230, 118, 0.12);
        --bolao-warn: #fbbf24;
        --bolao-danger: #f87171;
        position: fixed;
        top: 72px;
        left: 12px;
        z-index: 2147483647;
        width: min(360px, calc(100vw - 24px));
        max-height: calc(100vh - 96px);
        font-family: "SF Pro Text", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: var(--bolao-text);
        filter: drop-shadow(0 20px 50px rgba(0, 0, 0, 0.45));
        transition: width 0.22s ease, max-height 0.22s ease;
      }
      #${PANEL_ID}.bolao-minimized {
        width: min(300px, calc(100vw - 24px));
        max-height: none;
      }
      #${PANEL_ID} .bolao-panel-inner {
        background: linear-gradient(165deg, var(--bolao-bg) 0%, #0f172a 55%, #0b1324 100%);
        border: 1px solid var(--bolao-border);
        border-radius: 16px;
        overflow: hidden;
        backdrop-filter: blur(12px);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
      }
      #${PANEL_ID} .bolao-panel-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        padding: 12px 12px 12px 14px;
        border-bottom: 1px solid var(--bolao-border);
        background: linear-gradient(135deg, rgba(0,230,118,0.08), transparent 60%);
        cursor: grab;
        user-select: none;
      }
      #${PANEL_ID} .bolao-header-brand {
        display: flex;
        align-items: center;
        gap: 10px;
        min-width: 0;
        flex: 1;
      }
      #${PANEL_ID} .bolao-logo-mark,
      #${PANEL_ID} .bolao-mini-logo {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: var(--bolao-accent);
        box-shadow: 0 0 12px rgba(0,230,118,0.65);
        flex-shrink: 0;
      }
      #${PANEL_ID} .bolao-mini-logo.bolao-mini-pulse {
        animation: bolao-pulse 1.2s ease-in-out infinite;
      }
      @keyframes bolao-pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.45; transform: scale(0.85); }
      }
      #${PANEL_ID} .bolao-header-text { min-width: 0; }
      #${PANEL_ID} .bolao-logo {
        color: var(--bolao-accent);
        font-weight: 800;
        font-size: 13px;
        letter-spacing: 0.02em;
        display: block;
      }
      #${PANEL_ID} .bolao-sub {
        color: var(--bolao-muted);
        font-size: 10px;
        display: block;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 180px;
      }
      #${PANEL_ID} .bolao-live-pill {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 0.06em;
        color: #fca5a5;
        background: rgba(248,113,113,0.12);
        border: 1px solid rgba(248,113,113,0.25);
        padding: 3px 7px;
        border-radius: 999px;
        flex-shrink: 0;
      }
      #${PANEL_ID} .bolao-live-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: #ef4444;
        animation: bolao-live-blink 1.4s ease-in-out infinite;
      }
      @keyframes bolao-live-blink {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.35; }
      }
      #${PANEL_ID} .bolao-header-actions {
        display: flex;
        gap: 4px;
        flex-shrink: 0;
      }
      #${PANEL_ID} .bolao-btn-icon {
        width: 28px;
        height: 28px;
        border: 1px solid var(--bolao-border);
        border-radius: 8px;
        background: rgba(15, 23, 42, 0.6);
        color: var(--bolao-muted);
        font-size: 16px;
        line-height: 1;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        transition: background 0.15s, color 0.15s, border-color 0.15s;
      }
      #${PANEL_ID} .bolao-btn-icon:hover {
        background: var(--bolao-surface-2);
        color: var(--bolao-text);
        border-color: rgba(148,163,184,0.35);
      }
      #${PANEL_ID} .bolao-expand { display: none; }
      #${PANEL_ID}.bolao-minimized .bolao-minimize { display: none; }
      #${PANEL_ID}.bolao-minimized .bolao-expand { display: inline-flex; }
      #${PANEL_ID} .bolao-panel-body {
        max-height: calc(100vh - 180px);
        overflow: auto;
        scrollbar-width: thin;
        scrollbar-color: #334155 transparent;
      }
      #${PANEL_ID}.bolao-minimized .bolao-panel-body {
        display: none;
      }
      #${PANEL_ID} .bolao-panel-mini {
        display: none;
        align-items: center;
        gap: 10px;
        padding: 10px 12px;
        cursor: pointer;
        border-top: 1px solid var(--bolao-border);
        background: rgba(15, 23, 42, 0.85);
        transition: background 0.15s;
      }
      #${PANEL_ID}.bolao-minimized .bolao-panel-mini {
        display: flex;
      }
      #${PANEL_ID}.bolao-minimized .bolao-panel-header {
        display: none;
      }
      #${PANEL_ID} .bolao-panel-mini:hover {
        background: rgba(26, 35, 50, 0.95);
      }
      #${PANEL_ID} .bolao-mini-stack { min-width: 0; flex: 1; }
      #${PANEL_ID} .bolao-mini-score {
        display: block;
        font-weight: 800;
        font-size: 14px;
        color: var(--bolao-warn);
      }
      #${PANEL_ID} .bolao-mini-score em {
        font-style: normal;
        color: var(--bolao-muted);
        font-weight: 600;
        font-size: 12px;
      }
      #${PANEL_ID} .bolao-mini-palpite {
        display: block;
        font-size: 11px;
        color: var(--bolao-muted);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      #${PANEL_ID} .bolao-mini-palpite strong { color: var(--bolao-accent); }
      #${PANEL_ID} .bolao-mini-chevron {
        color: var(--bolao-accent);
        font-size: 18px;
        font-weight: 700;
        line-height: 1;
      }
      #${PANEL_ID} .bolao-mini-badge { font-size: 14px; }
      #${PANEL_ID} .bolao-mini-err { color: var(--bolao-danger); font-size: 11px; }
      #${PANEL_ID} .bolao-hero {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 14px 10px;
        gap: 12px;
      }
      #${PANEL_ID} .bolao-hero-score {
        font-size: 28px;
        font-weight: 800;
        letter-spacing: 0.04em;
        font-variant-numeric: tabular-nums;
      }
      #${PANEL_ID} .bolao-score-sep { color: var(--bolao-muted); margin: 0 2px; }
      #${PANEL_ID} .bolao-hero-meta {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 6px;
      }
      #${PANEL_ID} .bolao-minute {
        font-size: 22px;
        font-weight: 800;
        color: var(--bolao-text);
        font-variant-numeric: tabular-nums;
      }
      #${PANEL_ID} .bolao-minute small { font-size: 14px; color: var(--bolao-muted); }
      #${PANEL_ID} .bolao-status {
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        padding: 4px 8px;
        border-radius: 999px;
        border: 1px solid transparent;
      }
      #${PANEL_ID} .bolao-status-ok {
        color: var(--bolao-accent);
        background: var(--bolao-accent-dim);
        border-color: rgba(0,230,118,0.25);
      }
      #${PANEL_ID} .bolao-status-warn {
        color: #fecaca;
        background: rgba(127,29,29,0.35);
        border-color: rgba(248,113,113,0.35);
      }
      #${PANEL_ID} .bolao-palpite-card {
        margin: 0 14px 12px;
        padding: 10px 12px;
        border-radius: 12px;
        background: var(--bolao-surface-2);
        border: 1px solid var(--bolao-border);
        display: grid;
        grid-template-columns: auto 1fr auto;
        gap: 8px 10px;
        align-items: center;
      }
      #${PANEL_ID} .bolao-palpite-label {
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--bolao-muted);
      }
      #${PANEL_ID} .bolao-palpite-value {
        font-size: 22px;
        font-weight: 800;
        color: var(--bolao-accent);
        justify-self: start;
      }
      #${PANEL_ID} .bolao-palpite-meta {
        font-size: 10px;
        color: var(--bolao-muted);
        justify-self: end;
      }
      #${PANEL_ID} .bolao-alert {
        display: flex;
        gap: 10px;
        align-items: flex-start;
        margin: 0 14px 12px;
        padding: 10px 12px;
        border-radius: 12px;
        font-size: 11px;
        line-height: 1.45;
      }
      #${PANEL_ID} .bolao-alert p { margin: 0; }
      #${PANEL_ID} .bolao-alert-err {
        background: rgba(127,29,29,0.35);
        border: 1px solid rgba(248,113,113,0.3);
        color: #fecaca;
      }
      #${PANEL_ID} .bolao-alert-warn {
        background: rgba(120,53,15,0.28);
        border: 1px solid rgba(251,191,36,0.28);
        color: #fde68a;
      }
      #${PANEL_ID} .bolao-alert-icon { flex-shrink: 0; font-size: 14px; }
      #${PANEL_ID} .bolao-section {
        padding: 10px 14px 4px;
        border-top: 1px solid rgba(30, 41, 59, 0.65);
      }
      #${PANEL_ID} .bolao-section h3 {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--bolao-muted);
        margin: 0 0 8px;
        font-weight: 700;
      }
      #${PANEL_ID} .bolao-section-icon {
        width: 20px;
        height: 20px;
        border-radius: 6px;
        background: var(--bolao-surface-2);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 11px;
      }
      #${PANEL_ID} .bolao-icon-green { color: var(--bolao-accent); }
      #${PANEL_ID} .bolao-icon-red { color: var(--bolao-danger); }
      #${PANEL_ID} .bolao-section-body { padding-bottom: 6px; }
      #${PANEL_ID} .bolao-row {
        padding: 9px 11px;
        border-radius: 10px;
        margin-bottom: 6px;
        border: 1px solid transparent;
        border-left-width: 3px;
        transition: transform 0.12s ease;
      }
      #${PANEL_ID} .bolao-row:hover { transform: translateX(2px); }
      #${PANEL_ID} .bolao-row-green {
        background: rgba(0,230,118,0.08);
        border-left-color: var(--bolao-accent);
        border-color: rgba(0,230,118,0.12);
      }
      #${PANEL_ID} .bolao-row-yellow {
        background: rgba(251,191,36,0.08);
        border-left-color: var(--bolao-warn);
        border-color: rgba(251,191,36,0.12);
      }
      #${PANEL_ID} .bolao-row-red {
        background: rgba(248,113,113,0.1);
        border-left-color: var(--bolao-danger);
        border-color: rgba(248,113,113,0.15);
      }
      #${PANEL_ID} .bolao-row-muted {
        background: var(--bolao-surface-2);
        border-left-color: #475569;
      }
      #${PANEL_ID} .bolao-label {
        display: block;
        font-weight: 600;
        color: var(--bolao-text);
        font-size: 12px;
      }
      #${PANEL_ID} .bolao-meta {
        font-size: 10px;
        color: var(--bolao-muted);
        margin-top: 2px;
        display: block;
      }
      #${PANEL_ID} .bolao-meta em { font-style: normal; color: var(--bolao-accent); }
      #${PANEL_ID} .bolao-muted { color: #64748b; font-size: 11px; padding: 4px 0 8px; }
      #${PANEL_ID} .bolao-combo-title { font-weight: 600; margin: 0 0 6px; font-size: 12px; }
      #${PANEL_ID} .bolao-combo-legs { margin: 0 0 6px 16px; padding: 0; font-size: 11px; }
      #${PANEL_ID} .bolao-combo-legs li { margin-bottom: 4px; }
      #${PANEL_ID} .bolao-combo-legs span { color: var(--bolao-muted); }
      #${PANEL_ID} .bolao-footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 14px;
        border-top: 1px solid var(--bolao-border);
        font-size: 11px;
        background: rgba(15, 23, 42, 0.5);
      }
      #${PANEL_ID} .bolao-link {
        color: var(--bolao-accent);
        text-decoration: none;
        font-weight: 700;
      }
      #${PANEL_ID} .bolao-link:hover { text-decoration: underline; }
      #${PANEL_ID} .bolao-ts { color: #64748b; font-variant-numeric: tabular-nums; }
      #${PANEL_ID} .bolao-hint { color: #64748b; padding: 0 14px 12px; font-size: 10px; margin: 0; }
      #${PANEL_ID} .bolao-loading-wrap {
        padding: 20px 14px 8px;
        text-align: center;
      }
      #${PANEL_ID} .bolao-spinner {
        width: 28px;
        height: 28px;
        margin: 0 auto 12px;
        border: 3px solid rgba(0,230,118,0.15);
        border-top-color: var(--bolao-accent);
        border-radius: 50%;
        animation: bolao-spin 0.8s linear infinite;
      }
      @keyframes bolao-spin { to { transform: rotate(360deg); } }
      #${PANEL_ID} .bolao-loading {
        color: var(--bolao-accent);
        font-weight: 700;
        font-size: 12px;
        margin: 0 0 6px;
      }
    `;
    document.head.appendChild(style);
  }

  async function refreshPanel() {
    const eventId = extractEventId();
    if (!eventId || refreshInFlight) return;
    refreshInFlight = true;
    lastEventId = eventId;

    try {
      const { bolao_api_key: apiKey } = await storageGet(["bolao_api_key"]);
      const data = await fetchLiveAdvice(eventId, (apiKey || "").trim());
      renderPanel(data, eventId);

      if (!data.error) {
        chrome.storage.local.set({
          [`bolao_live_snapshot_${eventId}`]: {
            saved_at: new Date().toISOString(),
            event_id: eventId,
            home_team: data.home_team,
            away_team: data.away_team,
            strategy: data.strategy,
            bet_guardrails: data.bet_guardrails,
          },
        });
      }
    } finally {
      refreshInFlight = false;
    }
  }

  function stopPanel() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    stopLoadingTicker();
  }

  function startPanel() {
    stopPanel();
    const eventId = extractEventId();
    if (!eventId) {
      // Página sem evento específico (ex: /apostas/ao-vivo) — painel não aplicável
      return;
    }
    renderPanel({ loading: true }, eventId);
    refreshPanel();
    pollTimer = setInterval(refreshPanel, POLL_MS);
  }

  chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
    if (request.type === "ENABLE_LIVE_PANEL") {
      chrome.storage.local.set({ bolao_live_panel_enabled: true });
      startPanel();
      sendResponse({ ok: true, eventId: extractEventId() });
      return true;
    }
    if (request.type === "DISABLE_LIVE_PANEL") {
      chrome.storage.local.set({ bolao_live_panel_enabled: false });
      stopPanel();
      document.getElementById(PANEL_ID)?.remove();
      sendResponse({ ok: true });
      return true;
    }
    if (request.type === "GET_LIVE_PANEL_STATUS") {
      sendResponse({
        ok: true,
        enabled: Boolean(document.getElementById(PANEL_ID)),
        minimized: panelMinimized,
        eventId: extractEventId(),
      });
      return true;
    }
    return false;
  });

  chrome.storage.local.get(["bolao_live_panel_enabled", STORAGE_MINIMIZED], (items) => {
    panelMinimized = Boolean(items[STORAGE_MINIMIZED]);
    if (items.bolao_live_panel_enabled && extractEventId()) {
      startPanel();
    }
  });

  window.addEventListener("popstate", () => {
    if (pollTimer || document.getElementById(PANEL_ID)) {
      startPanel();
    }
  });

  console.info("[Bolão AI] Live market panel pronto. EventId:", extractEventId());
})();
