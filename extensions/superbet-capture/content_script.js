/**
 * Content script da extensão Bolão AI — Captura Superbet.
 * Roda na página "Minhas Apostas" da Superbet, extrai os cards de aposta
 * e envia para a background script.
 */
(function () {
  "use strict";

  const API_BASE = "http://127.0.0.1:8000";

  /**
   * Converte texto de valor (R$ 15,00) → número.
   */
  function parseMoney(text) {
    const cleaned = text.replace(/R\$/, "").replace(/\./g, "").replace(",", ".").trim();
    const num = parseFloat(cleaned);
    return isNaN(num) ? 0 : num;
  }

  /**
   * Extrai código do ticket (ex: 892P-1YINSZ) de um card.
   */
  function extractTicketCode(card) {
    // Seletores mais robustos baseados em prováveis padrões Superbet:
    const selectors = [
      '[data-qa*="ticket"]',
      '[data-qa*="code"]',
      '[class*="ticket"]',
      '[class*="codigo"]',
      '[class*="code"]',
      '[class*="id"]',
    ];
    for (const sel of selectors) {
      const el = card.querySelector(sel);
      if (el) {
        const text = el.textContent.trim();
        // ticket code: letras/numeros + hífen
        const m = text.match(/([A-Z0-9]{3,}-[A-Z0-9]{5,})/);
        if (m) return m[1];
      }
    }
    // Fallback: buscar no texto do card
    const text = card.innerText || card.textContent || "";
    const m = text.match(/([A-Z0-9]{3,}-[A-Z0-9]{5,})/);
    return m ? m[1] : null;
  }

  /**
   * Extrai dados de um card de aposta da Superbet.
   */
  function parseBetCard(card) {
    const text = card.innerText || card.textContent || "";
    const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);

    // Equipes: primeira linha com ·, —, -, vs
    let eventName = "";
    let homeTeam = "";
    let awayTeam = "";
    for (const line of lines) {
      for (const sep of ["·", "—", " - ", " vs ", " x "]) {
        if (line.includes(sep)) {
          const parts = line.split(sep);
          if (parts.length >= 2) {
            homeTeam = parts[0].trim();
            awayTeam = parts[1].trim();
            eventName = line;
            break;
          }
        }
      }
      if (eventName) break;
    }

    // Ticket code
    const ticketCode = extractTicketCode(card);

    // Status
    const isLive = /AO VIVO/i.test(text);
    const isOpen = !/(Concluído|Encerrado|Ganhou|Perdeu|Cashed Out)/i.test(text);

    // Mercado e palpite
    const picks = [];
    for (const line of lines) {
      const ln = line;
      if (/Resultado Final/i.test(ln)) {
        const m = ln.match(/[–-]\s*([1X2])/i);
        picks.push({ market: "h2h", outcome: m ? m[1] : "1" });
      } else if (/Ambas as Equipes Marcam/i.test(ln)) {
        const yes = /Sim/i.test(ln);
        picks.push({ market: "btts", outcome: yes ? "yes" : "no" });
      } else if (/Total de Gols/i.test(ln)) {
        const more = /Mais/i.test(ln);
        const valMatch = ln.match(/([\d.]+)/);
        picks.push({
          market: "over_2_5",
          outcome: more ? "yes" : "no",
          target_value: valMatch ? valMatch[1] : "2.5",
        });
      } else if (/Vence/i.test(ln)) {
        const teamMatch = ln.match(/(.+?)\s*-\s*Vence/i);
        if (teamMatch) {
          const team = teamMatch[1].trim();
          const outcome =
            team.toLowerCase().includes(homeTeam.toLowerCase().split(" ")[0]) ? "home" : "away";
          picks.push({ market: "h2h", outcome });
        }
      } else if (/CRIAR APOSTA/i.test(ln)) {
        picks.push({ market: "combo", outcome: "combo" });
      }
    }

    // Stake
    let stake = 0;
    for (const line of lines) {
      const m = line.match(/APOSTA\s*([\d.,\s]+)/i);
      if (m) {
        stake = parseMoney(m[1]);
        break;
      }
    }

    // Odd total
    let totalOdd = 0;
    for (const line of lines) {
      const m = line.match(/ODDS\s*TOTAIS\s*([\d.,]+)/i);
      if (m) {
        totalOdd = parseFloat(m[1].replace(",", "."));
        break;
      }
    }

    // Ganho potencial
    let potentialReturn = 0;
    for (const line of lines) {
      const m = line.match(/GANHO?\s*POTENCIAL\s*R?\$?\s*([\d.,]+)/i);
      if (m) {
        potentialReturn = parseMoney(m[1]);
        break;
      }
    }
    if (!potentialReturn && stake && totalOdd) {
      potentialReturn = +(stake * totalOdd).toFixed(2);
    }

    // Cash-out
    let cashoutValue = null;
    for (const line of lines) {
      const m = line.match(/Cashout\s+([\d.,]+)/i);
      if (m) {
        cashoutValue = parseMoney(m[1]);
        break;
      }
    }

    // Identificar event_id da Superbet se houver link/data-id
    let superbetEventId = null;
    const linkEl = card.querySelector('a[href*="/event/"]');
    if (linkEl) {
      const hrefMatch = linkEl.getAttribute("href")?.match(/event\/(\d+)/);
      if (hrefMatch) superbetEventId = parseInt(hrefMatch[1], 10);
    }

    return {
      event_name: eventName || `${homeTeam} · ${awayTeam}`,
      home_team: homeTeam,
      away_team: awayTeam,
      ticket_code: ticketCode,
      picks,
      stake,
      odds_placed: totalOdd,
      potential_return: potentialReturn,
      cashout_value: cashoutValue,
      superbet_event_id: superbetEventId,
      is_live: isLive,
      is_open: isOpen,
    };
  }

  /**
   * Escaneia a página e extrai todas as apostas abertas.
   */
  function scanOpenBets() {
    // Seletores que cobrem os cards visuais da Superbet (podem mudar)
    const cards = document.querySelectorAll(
      '[data-testid*="ticket"], [class*="ticket"], [class*="bet-card"], [class*="aposta"], [class*="open-bet"]'
    );

    // Se não encontrar com seletores específicos, tentar card genérico
    let elements = Array.from(cards);
    if (elements.length === 0) {
      // Fallback: buscar divs que contenham "AO VIVO" ou "ÚNICO" e "APOSTA"
      const allDivs = document.querySelectorAll("div");
      elements = Array.from(allDivs).filter((div) => {
        const text = div.innerText || "";
        return (
          text.includes("APOSTA") &&
          (text.includes("AO VIVO") || text.includes("ÚNICO") || text.includes("Cashout"))
        );
      });
    }

    const bets = elements.map(parseBetCard).filter((b) => b.is_open && b.stake > 0);
    return bets;
  }

  /**
   * Envia apostas para a API Bolão AI.
   */
  async function sendToApi(bet, apiKey) {
    const payload = {
      id: bet.ticket_code,
      superbet_event_id: bet.superbet_event_id,
      event_name: bet.event_name,
      home_team: bet.home_team,
      away_team: bet.away_team,
      picks: bet.picks,
      stake: bet.stake,
      odds_placed: bet.odds_placed,
      potential_return: bet.potential_return,
      cashout_value: bet.cashout_value,
      ticket_code: bet.ticket_code,
      source: "superbet_extension",
    };

    try {
      const headers = { "Content-Type": "application/json" };
      if (apiKey) headers["X-API-Key"] = apiKey;

      const resp = await fetch(`${API_BASE}/user/open-bets`, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const err = await resp.text();
        console.warn("[Bolão AI] Erro ao enviar aposta:", err);
        return { ok: false, error: err };
      }

      const result = await resp.json();
      console.info("[Bolão AI] Aposta enviada:", result);
      return { ok: true, result };
    } catch (e) {
      console.warn("[Bolão AI] Falha de rede:", e);
      return { ok: false, error: String(e) };
    }
  }

  /**
   * Escuta mensagens do popup/background.
   */
  chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
    if (request.type === "SCAN_BETS") {
      const bets = scanOpenBets();
      // Enviar para API
      chrome.storage.local.get(["bolao_api_key"], async (items) => {
        const apiKey = items.bolao_api_key || "";
        const results = [];
        for (const bet of bets) {
          const r = await sendToApi(bet, apiKey);
          results.push({ ticket: bet.ticket_code, ...r });
        }
        sendResponse({ bets, results });
      });
      return true; // async response
    }
    if (request.type === "GET_BETS") {
      sendResponse({ bets: scanOpenBets() });
      return true;
    }
    return false;
  });

  console.info("[Bolão AI] Content script carregado. Página:", location.href);
})();
