/**
 * Popup da extensão Bolão AI — Captura Superbet.
 * Gerencia captura de apostas abertas e exibe status.
 */
(function () {
  "use strict";

  const apiKeyInput = document.getElementById("apiKey");
  const captureBtn = document.getElementById("captureBtn");
  const captureSettledBtn = document.getElementById("captureSettledBtn");
  const statusDiv = document.getElementById("status");
  const betsList = document.getElementById("betsList");

  // Carregar API key salva
  chrome.storage.local.get(["bolao_api_key"], (items) => {
    if (items.bolao_api_key) apiKeyInput.value = items.bolao_api_key;
  });

  // Salvar API key ao alterar
  apiKeyInput.addEventListener("change", () => {
    chrome.storage.local.set({ bolao_api_key: apiKeyInput.value.trim() });
  });

  function setStatus(text, cls) {
    statusDiv.textContent = text;
    statusDiv.className = `status ${cls}`;
  }

  /**
   * Verifica se o content script está ativo na aba, e injeta se necessário.
   */
  async function ensureContentScript(tabId) {
    return new Promise((resolve) => {
      chrome.tabs.sendMessage(tabId, { type: "PING" }, (response) => {
        if (chrome.runtime.lastError || !response?.ok) {
          // Content script não está ativo — injetar via scripting API
          chrome.scripting.executeScript(
            {
              target: { tabId },
              files: ["content_script.js"],
            },
            () => {
              if (chrome.runtime.lastError) {
                resolve({ ok: false, error: chrome.runtime.lastError.message });
              } else {
                // Aguardar um momento para o script carregar
                setTimeout(() => resolve({ ok: true, injected: true }), 300);
              }
            }
          );
        } else {
          resolve({ ok: true, injected: false });
        }
      });
    });
  }

  captureBtn.addEventListener("click", async () => {
    captureBtn.disabled = true;
    setStatus("Verificando aba...", "warn");
    betsList.innerHTML = "";

    // Obter aba ativa
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) {
      setStatus("Nenhuma aba ativa encontrada.", "err");
      captureBtn.disabled = false;
      return;
    }

    // Verificar domínio (superbet.com, superbet.com.br, superbet.bet.br)
    const url = tab.url || "";
    const isSuperbet = /superbet\.(com|com\.br|bet\.br)/i.test(url);
    if (!isSuperbet) {
      setStatus(
        "Abra a página 'Minhas Apostas' na Superbet e tente novamente.\nURL atual: " +
          url.slice(0, 50),
        "err"
      );
      captureBtn.disabled = false;
      return;
    }

    // Garantir que content script está injetado
    const inject = await ensureContentScript(tab.id);
    if (!inject.ok) {
      setStatus("Falha ao injetar script: " + (inject.error || "permissão negada"), "err");
      captureBtn.disabled = false;
      return;
    }

    setStatus("Escaneando apostas abertas...", "warn");

    // Pedir scan ao content script
    chrome.tabs.sendMessage(tab.id, { type: "SCAN_BETS" }, (response) => {
      captureBtn.disabled = false;

      if (chrome.runtime.lastError) {
        setStatus(
          "Erro de comunicação: " + chrome.runtime.lastError.message +
          "\nTente recarregar a página da Superbet.",
          "err"
        );
        return;
      }

      if (!response || !response.bets) {
        setStatus(
          "Nenhuma resposta do content script.\nRecarregue a página da Superbet.",
          "err"
        );
        return;
      }

      const { bets, results } = response;
      if (bets.length === 0) {
        setStatus(
          "Nenhuma aposta aberta encontrada na página.\n" +
          "Certifique-se de estar em 'Minhas Apostas' com apostas ativas.",
          "warn"
        );
        return;
      }

      // Exibir resultados
      const okCount = (results || []).filter((r) => r.ok).length;
      const failCount = bets.length - okCount;

      if (failCount === 0) {
        setStatus(`✓ ${bets.length} aposta(s) capturada(s) e enviada(s) com sucesso!`, "ok");
      } else if (okCount > 0) {
        setStatus(
          `${okCount}/${bets.length} enviadas. ${failCount} falharam (API offline?).`,
          "warn"
        );
      } else {
        setStatus(
          `${bets.length} aposta(s) encontrada(s), mas falha ao enviar.\nVerifique se a API está rodando.`,
          "err"
        );
      }

      // Listar apostas
      betsList.innerHTML = bets
        .map((b) => {
          const status = b.is_live ? "🟢 AO VIVO" : "⏸ Pré-jogo";
          return `
            <div class="bet-item">
              <strong>${b.event_name || "—"}</strong><br>
              <span>${status} · ${b.picks.length} pick(s) · Stake R$ ${b.stake.toFixed(2)}</span>
              ${b.cashout_value ? `<br><span style="color:#fbbf24">Cash-out: R$ ${b.cashout_value.toFixed(2)}</span>` : ""}
            </div>`;
        })
        .join("");
    });
  });

  // ═══════════════════════════════════════════════════════════════════════
  // Capturar apostas finalizadas (tab "Finalizado")
  // ═══════════════════════════════════════════════════════════════════════
  captureSettledBtn.addEventListener("click", async () => {
    captureSettledBtn.disabled = true;
    captureBtn.disabled = true;
    setStatus("Verificando aba...", "warn");
    betsList.innerHTML = "";

    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) {
      setStatus("Nenhuma aba ativa encontrada.", "err");
      captureSettledBtn.disabled = false;
      captureBtn.disabled = false;
      return;
    }

    const url = tab.url || "";
    const isSuperbet = /superbet\.(com|com\.br|bet\.br)/i.test(url);
    if (!isSuperbet) {
      setStatus(
        "Abra 'Minhas Apostas > Finalizados' na Superbet.\nURL atual: " + url.slice(0, 50),
        "err"
      );
      captureSettledBtn.disabled = false;
      captureBtn.disabled = false;
      return;
    }

    const inject = await ensureContentScript(tab.id);
    if (!inject.ok) {
      setStatus("Falha ao injetar script: " + (inject.error || "permissão negada"), "err");
      captureSettledBtn.disabled = false;
      captureBtn.disabled = false;
      return;
    }

    setStatus("Escaneando apostas finalizadas...", "warn");

    chrome.tabs.sendMessage(tab.id, { type: "CAPTURE_SETTLED_BETS" }, (response) => {
      captureSettledBtn.disabled = false;
      captureBtn.disabled = false;

      if (chrome.runtime.lastError) {
        setStatus("Erro: " + chrome.runtime.lastError.message, "err");
        return;
      }

      if (!response || !response.bets) {
        setStatus("Sem resposta do content script.\nRecarregue a página.", "err");
        return;
      }

      const { bets, result } = response;
      if (bets.length === 0) {
        setStatus(
          "Nenhuma aposta finalizada encontrada.\n" +
          "Navegue para a aba 'Finalizados' em Minhas Apostas.",
          "warn"
        );
        return;
      }

      const added = result?.data?.added ?? bets.length;
      if (result?.ok !== false) {
        setStatus(`✓ ${bets.length} aposta(s) finalizada(s) capturada(s)! (${added} novas)`, "ok");
      } else {
        setStatus(
          `${bets.length} encontrada(s), mas falha ao enviar.\n${result.error || "API offline?"}`,
          "err"
        );
      }

      // Listar
      const icons = { won: "✅", lost: "❌", cashout: "💰", void: "⏹️" };
      betsList.innerHTML = bets
        .map((b) => {
          const icon = icons[b.result] || "❓";
          const profitClass = b.profit >= 0 ? "color:#00ff88" : "color:#f87171";
          return `
            <div class="bet-item">
              <strong>${icon} ${b.event_name || "—"}</strong><br>
              <span>${b.result.toUpperCase()} · Stake R$ ${b.stake.toFixed(2)} · <span style="${profitClass}">Lucro R$ ${b.profit.toFixed(2)}</span></span>
              ${b.final_score ? `<br><span>Placar: ${b.final_score}</span>` : ""}
            </div>`;
        })
        .join("");
    });
  });
})();
