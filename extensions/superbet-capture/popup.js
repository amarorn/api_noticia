/**
 * Popup da extensão Bolão AI — Captura Superbet.
 * Dispara capturas via background (continua com popup fechado) e exibe último resultado.
 */
(function () {
  "use strict";

  const apiKeyInput = document.getElementById("apiKey");
  const captureBtn = document.getElementById("captureBtn");
  const captureSettledBtn = document.getElementById("captureSettledBtn");
  const captureWalletBtn = document.getElementById("captureWalletBtn");
  const livePanelBtn = document.getElementById("livePanelBtn");
  const livePanelAuto = document.getElementById("livePanelAuto");
  const userIdInput = document.getElementById("userId");
  const statusDiv = document.getElementById("status");
  const betsList = document.getElementById("betsList");
  const lastRunDiv = document.getElementById("lastRun");

  const KIND_LABEL = { open: "abertas", settled: "finalizadas", wallet: "extrato" };

  chrome.storage.local.get(["bolao_api_key", "bolao_user_id", "bolao_live_panel_enabled"], (items) => {
    if (items.bolao_api_key) apiKeyInput.value = items.bolao_api_key;
    if (items.bolao_user_id) userIdInput.value = items.bolao_user_id;
    if (livePanelAuto) livePanelAuto.checked = Boolean(items.bolao_live_panel_enabled);
  });

  apiKeyInput.addEventListener("change", () => {
    chrome.storage.local.set({ bolao_api_key: apiKeyInput.value.trim() });
  });
  userIdInput.addEventListener("change", () => {
    chrome.storage.local.set({ bolao_user_id: userIdInput.value.trim() || "jamarorn" });
  });

  function setStatus(text, cls) {
    statusDiv.textContent = text;
    statusDiv.className = `status ${cls || ""}`;
  }

  function formatWhen(iso) {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  }

  function renderLastCapture(record) {
    if (!record) {
      lastRunDiv.textContent = "";
      return;
    }
    const kind = KIND_LABEL[record.kind] || record.kind;
    let extra = "";
    if (record.kind === "open" && record.summary?.tickets_on_page != null) {
      extra = ` · ${record.summary.tickets_on_page} bilhete(s) na página`;
    }
    lastRunDiv.textContent = `Última captura (${kind}): ${formatWhen(record.finishedAt)}${extra}`;
    setStatus(record.message, record.status);
    renderBetList(record);
  }

  function renderBetList(record) {
    if (!record?.bets?.length) {
      betsList.innerHTML = "";
      return;
    }

    if (record.kind === "open") {
      betsList.innerHTML = record.bets
        .map((b) => {
          const live = b.is_live ? "🟢 AO VIVO" : "⏸ Pré-jogo";
          const r = b.send;
          let sendTag = "";
          if (r?.ok) sendTag = ' <span style="color:#00e676">✓ enviada</span>';
          else if (r?.skipped) sendTag = ` <span style="color:#fbbf24">⚠ ${r.error}</span>`;
          else if (r) sendTag = ` <span style="color:#f87171">✗ ${r.error || "erro API"}</span>`;
          const againstTag = b.against_model
            ? `<br><span style="color:#f87171;font-weight:600">⛔ Contra modelo: ${b.against_model.message || ""}</span>`
            : r?.against_model_alert
              ? `<br><span style="color:#f87171;font-weight:600">⛔ ${r.against_model_alert.message || ""}</span>`
              : "";
          return `
            <div class="bet-item">
              <strong>${b.event_name || "—"}</strong><br>
              <span>${live} · ${b.picks_count} pick(s) · Stake R$ ${Number(b.stake).toFixed(2)}${sendTag}</span>
              ${againstTag}
              ${b.cashout_value ? `<br><span style="color:#fbbf24">Cash-out: R$ ${Number(b.cashout_value).toFixed(2)}</span>` : ""}
            </div>`;
        })
        .join("");
      return;
    }

    if (record.kind === "settled") {
      const icons = { won: "✅", lost: "❌", cashout: "💰", void: "⏹️" };
      betsList.innerHTML = record.bets
        .map((b) => {
          const icon = icons[b.result] || "❓";
          const profitClass = b.profit >= 0 ? "color:#00e676" : "color:#f87171";
          return `
            <div class="bet-item">
              <strong>${icon} ${b.event_name || "—"}</strong><br>
              <span>${(b.result || "").toUpperCase()} · Stake R$ ${Number(b.stake).toFixed(2)} · <span style="${profitClass}">Lucro R$ ${Number(b.profit).toFixed(2)}</span></span>
              ${b.final_score ? `<br><span>Placar: ${b.final_score}</span>` : ""}
            </div>`;
        })
        .join("");
      return;
    }

    if (record.kind === "wallet") {
      betsList.innerHTML = record.bets
        .map(
          (r) =>
            `<div class="bet-item"><strong>${r.event_name}</strong><br><span>${r.datetime || ""} · R$ ${Number(r.stake).toFixed(2)}</span></div>`
        )
        .join("");
    }
  }

  function setButtonsDisabled(disabled) {
    captureBtn.disabled = disabled;
    captureSettledBtn.disabled = disabled;
    captureWalletBtn.disabled = disabled;
  }

  function showProgress(progress) {
    if (!progress) return;
    const kind = KIND_LABEL[progress.kind] || progress.kind;
    setStatus(
      `Captura (${kind}) em andamento…\nPode fechar esta janela — avisaremos quando terminar.`,
      "warn"
    );
    setButtonsDisabled(true);
  }

  chrome.storage.local.get(["bolao_last_capture", "bolao_capture_in_progress"], (items) => {
    if (items.bolao_capture_in_progress) {
      showProgress(items.bolao_capture_in_progress);
    } else if (items.bolao_last_capture) {
      renderLastCapture(items.bolao_last_capture);
    }
  });

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local") return;
    if (changes.bolao_capture_in_progress) {
      const p = changes.bolao_capture_in_progress.newValue;
      if (p) showProgress(p);
      else setButtonsDisabled(false);
    }
    if (changes.bolao_last_capture?.newValue) {
      renderLastCapture(changes.bolao_last_capture.newValue);
      setButtonsDisabled(false);
    }
  });

  async function getSuperbetTab() {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) return { error: "Nenhuma aba ativa encontrada." };
    const url = tab.url || "";
    if (!/superbet\.(com|com\.br|bet\.br)/i.test(url)) {
      return {
        error:
          "Abra a Superbet (jogo ao vivo ou Minhas Apostas).\nURL atual: " + url.slice(0, 55),
      };
    }
    return { tab };
  }

  function extractEventIdFromUrl(url) {
    if (!url) return null;
    const patterns = [
      /\/(?:event|evento)\/(\d+)/i,
      /\/e-(\d+)/i,
      /[?&]event(?:Id|_id)=(\d+)/i,
      /\/odds\/(?:[^?#]+\/)*[^/?#]+-(\d{5,})(?:\?|#|$)/i,
    ];
    for (const p of patterns) {
      const m = url.match(p);
      if (m) return parseInt(m[1], 10);
    }
    try {
      const seg = new URL(url).pathname.split("/").filter(Boolean).pop() || "";
      const slug = seg.match(/-(\d{5,})$/);
      if (slug) return parseInt(slug[1], 10);
    } catch {
      /* ignore */
    }
    return null;
  }

  function startBackgroundCapture(type, tabId, extra = {}) {
    const apiKey = apiKeyInput.value.trim();
    if (apiKey) chrome.storage.local.set({ bolao_api_key: apiKey });

    const msgType = {
      open: "START_CAPTURE_OPEN",
      settled: "START_CAPTURE_SETTLED",
      wallet: "START_CAPTURE_WALLET",
    }[type];

    chrome.runtime.sendMessage(
      {
        type: msgType,
        tabId,
        apiKey,
        userId: extra.userId,
      },
      () => {
        /* resultado via storage + notificação — popup pode estar fechado */
        if (chrome.runtime.lastError) {
          setStatus("Erro ao iniciar: " + chrome.runtime.lastError.message, "err");
          setButtonsDisabled(false);
        }
      }
    );
  }

  captureBtn.addEventListener("click", async () => {
    betsList.innerHTML = "";
    const { tab, error } = await getSuperbetTab();
    if (error) {
      setStatus(error, "err");
      return;
    }
    setStatus("Iniciando captura de apostas abertas…", "warn");
    setButtonsDisabled(true);
    startBackgroundCapture("open", tab.id);
  });

  captureSettledBtn.addEventListener("click", async () => {
    betsList.innerHTML = "";
    const { tab, error } = await getSuperbetTab();
    if (error) {
      setStatus(error, "err");
      return;
    }
    setStatus("Iniciando captura de finalizadas…", "warn");
    setButtonsDisabled(true);
    startBackgroundCapture("settled", tab.id);
  });

  captureWalletBtn.addEventListener("click", async () => {
    betsList.innerHTML = "";
    const { tab, error } = await getSuperbetTab();
    if (error) {
      setStatus(error, "err");
      return;
    }
    const userId = userIdInput.value.trim() || "jamarorn";
    chrome.storage.local.set({ bolao_user_id: userId });
    setStatus("Iniciando envio do extrato…", "warn");
    setButtonsDisabled(true);
    startBackgroundCapture("wallet", tab.id, { userId });
  });

  if (livePanelAuto) {
    livePanelAuto.addEventListener("change", () => {
      chrome.storage.local.set({ bolao_live_panel_enabled: livePanelAuto.checked });
    });
  }

  livePanelBtn?.addEventListener("click", async () => {
    const { tab, error } = await getSuperbetTab();
    if (error) {
      setStatus(error, "err");
      return;
    }
    const eventId = extractEventIdFromUrl(tab.url);
    if (!eventId) {
      setStatus(
        "Abra a página de UM jogo ao vivo (URL termina com -13367973) e clique de novo.",
        "warn"
      );
      return;
    }
    const apiKey = apiKeyInput.value.trim();
    if (!apiKey) {
      setStatus("Cole a API Key acima (mesma do .env) antes de ativar o painel.", "warn");
      return;
    }
    chrome.storage.local.set({ bolao_api_key: apiKey, bolao_live_panel_enabled: true });
    if (livePanelAuto) livePanelAuto.checked = true;
    setStatus(`Iniciando painel — evento #${eventId}…`, "warn");
    chrome.runtime.sendMessage(
      { type: "START_LIVE_PANEL", tabId: tab.id, eventId },
      (resp) => {
        if (chrome.runtime.lastError || !resp?.ok) {
          setStatus(
            resp?.error ||
              chrome.runtime.lastError?.message ||
              "Recarregue a página (F5) e tente de novo.",
            "err"
          );
          return;
        }
        const msg = resp.injected
          ? `Painel injetado — evento #${resp.eventId || eventId}. Atualiza a cada 20s.`
          : `Painel ativo — evento #${resp.eventId || eventId}. Atualiza a cada 20s.`;
        setStatus(msg, "ok");
      }
    );
  });
})();
