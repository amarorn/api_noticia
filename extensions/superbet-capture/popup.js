/**
 * Popup da extensão Bolão AI — Captura Superbet.
 * Interface simples: captura apostas e envia para a API.
 */
document.addEventListener("DOMContentLoaded", () => {
  const apiKeyInput = document.getElementById("apiKey");
  const captureBtn = document.getElementById("captureBtn");
  const statusEl = document.getElementById("status");
  const betsListEl = document.getElementById("betsList");

  // Carregar API key salva
  chrome.storage.local.get(["bolao_api_key"], (items) => {
    if (items.bolao_api_key) apiKeyInput.value = items.bolao_api_key;
  });

  function setStatus(text, type = "ok") {
    statusEl.textContent = text;
    statusEl.className = `status ${type}`;
  }

  function renderBets(bets) {
    betsListEl.innerHTML = "";
    if (!bets || bets.length === 0) {
      betsListEl.innerHTML = "<p style='margin-top:8px;font-size:11px;color:#64748b;'>Nenhuma aposta aberta encontrada.</p>";
      return;
    }
    const countDiv = document.createElement("div");
    countDiv.className = "count";
    countDiv.textContent = bets.length;
    betsListEl.appendChild(countDiv);
    bets.forEach((b) => {
      const div = document.createElement("div");
      div.className = "bet-item";
      div.innerHTML = `
        <strong>${b.event_name || "Sem nome"}</strong><br>
        <span>Aposta R$ ${b.stake?.toFixed(2) || "—"} · Odd ${b.odds_placed || "—"}</span>
        ${b.ticket_code ? `<br><span>Ticket: ${b.ticket_code}</span>` : ""}
        ${b.cashout_value ? `<br><span style="color:#00ff88">Cash-out: R$ ${b.cashout_value.toFixed(2)}</span>` : ""}
      `;
      betsListEl.appendChild(div);
    });
  }

  captureBtn.addEventListener("click", async () => {
    const apiKey = apiKeyInput.value.trim();
    chrome.storage.local.set({ bolao_api_key: apiKey });

    setStatus("Escaneando página...", "warn");
    captureBtn.disabled = true;

    try {
      // Buscar aba ativa
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.id) {
        setStatus("Nenhuma aba ativa encontrada.", "err");
        captureBtn.disabled = false;
        return;
      }

      // Enviar mensagem para content_script escanear
      chrome.tabs.sendMessage(tab.id, { type: "SCAN_BETS" }, (response) => {
        captureBtn.disabled = false;
        if (chrome.runtime.lastError) {
          setStatus("Não foi possível acessar a página.", "err");
          console.error(chrome.runtime.lastError);
          return;
        }
        if (!response) {
          setStatus("Página não respondeu. Atualize e tente novamente.", "err");
          return;
        }
        const bets = response.bets || [];
        const results = response.results || [];
        const okCount = results.filter((r) => r.ok).length;
        const errCount = results.length - okCount;

        renderBets(bets);
        if (bets.length === 0) {
          setStatus("Nenhuma aposta aberta detectada na página.", "warn");
        } else {
          setStatus(`${okCount} enviada(s) · ${errCount} erro(s)`, okCount > 0 ? "ok" : "warn");
        }
      });
    } catch (e) {
      captureBtn.disabled = false;
      setStatus("Erro: " + String(e), "err");
    }
  });
});
