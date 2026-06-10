/**
 * Content script da extensão Bolão AI — Captura Superbet.
 * Roda na página "Minhas Apostas" da Superbet, extrai os cards de aposta
 * e envia para a background script (que repassa para a API).
 */
(function () {
  "use strict";

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
    const selectors = [
      '[data-qa*="ticket"]',
      '[data-qa*="code"]',
      '[data-testid*="ticket"]',
      '[data-testid*="code"]',
      '[class*="ticket"]',
      '[class*="codigo"]',
      '[class*="code"]',
      '[class*="betslip-id"]',
    ];
    for (const sel of selectors) {
      const el = card.querySelector(sel);
      if (el) {
        const text = el.textContent.trim();
        const m = text.match(/([A-Z0-9]{3,}-[A-Z0-9]{4,})/);
        if (m) return m[1];
      }
    }
    // Fallback: buscar padrão de ticket no texto do card
    const text = card.innerText || card.textContent || "";
    const m = text.match(/([A-Z0-9]{3,}-[A-Z0-9]{4,})/);
    return m ? m[1] : null;
  }

  /**
   * Extrai dados de um card de aposta da Superbet.
   */
  function parseBetCard(card) {
    const text = card.innerText || card.textContent || "";
    const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);

    // Equipes: primeira linha com separador
    let eventName = "";
    let homeTeam = "";
    let awayTeam = "";
    for (const line of lines) {
      for (const sep of ["·", "—", " - ", " vs ", " x ", " X "]) {
        if (line.includes(sep)) {
          const parts = line.split(sep);
          if (parts.length >= 2 && parts[0].length > 1 && parts[1].length > 1) {
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
    const isLive = /AO VIVO|LIVE|Em andamento/i.test(text);
    const isOpen = !/(Concluído|Encerrado|Ganhou|Perdeu|Cashed Out|Cancelad)/i.test(text);

    // Mercado e palpite — formato Superbet: "Mercado — Pick @ Odd"
    const picks = [];
    for (const line of lines) {
      // Formato "Mercado — Pick @ Odd" (ex: "Resultado Final — 2 @ 30.00")
      const mSuperbet = line.match(/(.+?)\s*[—–-]\s*(.+?)\s*@\s*([\d.,]+)/);
      if (mSuperbet) {
        const marketRaw = mSuperbet[1].trim();
        const pickRaw = mSuperbet[2].trim();
        const oddPlaced = parseFloat(mSuperbet[3].replace(",", "."));

        let market = "other";
        let outcome = pickRaw;

        if (/Resultado Final|Match Result|1X2/i.test(marketRaw)) {
          market = "h2h";
          if (/^1$/.test(pickRaw)) outcome = "home";
          else if (/^2$/.test(pickRaw)) outcome = "away";
          else if (/^X$/i.test(pickRaw)) outcome = "draw";
        } else if (/Total de Gols|Over.*Under|Total Goals/i.test(marketRaw)) {
          const isOver = /Mais|Over|Acima|\+/i.test(pickRaw);
          const valMatch = pickRaw.match(/([\d.]+)/);
          market = "totals";
          outcome = isOver ? "over" : "under";
          if (valMatch) market = `totals_${valMatch[1]}`;
        } else if (/Ambas.*Marcam|Both.*Score|BTTS/i.test(marketRaw)) {
          market = "btts";
          outcome = /Sim|Yes/i.test(pickRaw) ? "yes" : "no";
        } else if (/Próximo Gol|Next Goal/i.test(marketRaw)) {
          market = "next_goal";
        } else if (/Vencedor|Winner|Moneyline/i.test(marketRaw)) {
          market = "h2h";
          // Tentar deduzir se é home ou away pelo nome
          if (homeTeam && pickRaw.toLowerCase().includes(homeTeam.toLowerCase().split(" ")[0])) {
            outcome = "home";
          } else {
            outcome = "away";
          }
        }

        picks.push({ market, outcome, odd_placed: oddPlaced, raw: line });
        continue;
      }

      // Fallback: formatos antigos
      if (/Resultado Final|Match Result|1X2/i.test(line)) {
        const m = line.match(/[–\-:]\s*([1X2])/i);
        picks.push({ market: "h2h", outcome: m ? m[1] : "1" });
      } else if (/Ambas.*Marcam|Both.*Score|BTTS/i.test(line)) {
        const yes = /Sim|Yes/i.test(line);
        picks.push({ market: "btts", outcome: yes ? "yes" : "no" });
      } else if (/Total de Gols|Over\/Under|Total Goals/i.test(line)) {
        const more = /Mais|Over|Acima/i.test(line);
        const valMatch = line.match(/([\d.]+)/);
        picks.push({
          market: "totals",
          outcome: more ? "over" : "under",
          target_value: valMatch ? valMatch[1] : "2.5",
        });
      }
    }

    // Stake — pode estar na mesma linha ("APOSTA 20,00 R$") ou na próxima
    let stake = 0;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      // Mesma linha: "APOSTA 20,00 R$" ou "APOSTA: R$ 20,00"
      const m = line.match(/(?:APOSTA|Stake|Valor)\s*:?\s*R?\$?\s*([\d.,]+)/i);
      if (m) {
        stake = parseMoney(m[1]);
        break;
      }
      // Linha isolada "APOSTA" → valor na próxima linha
      if (/^APOSTA$/i.test(line) && i + 1 < lines.length) {
        const nextVal = parseMoney(lines[i + 1]);
        if (nextVal > 0) { stake = nextVal; break; }
      }
    }

    // Odd total — mesma lógica: pode estar junto ou na próxima linha
    let totalOdd = 0;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const m = line.match(/(?:ODDS?\s*TOTAIS?|Total Odds?)\s*:?\s*([\d.,]+)/i);
      if (m) {
        totalOdd = parseFloat(m[1].replace(",", "."));
        break;
      }
      if (/^ODDS?\s*TOTAIS?$/i.test(line) && i + 1 < lines.length) {
        const val = parseFloat(lines[i + 1].replace(",", "."));
        if (val > 0) { totalOdd = val; break; }
      }
    }

    // Ganho potencial
    let potentialReturn = 0;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const m = line.match(/(?:GANHO?\s*POTENCIAL|Potential Return|Retorno)\s*:?\s*R?\$?\s*([\d.,]+)/i);
      if (m) {
        potentialReturn = parseMoney(m[1]);
        break;
      }
      if (/^GANHO\s*POTENCIAL$/i.test(line) && i + 1 < lines.length) {
        const val = parseMoney(lines[i + 1]);
        if (val > 0) { potentialReturn = val; break; }
      }
    }
    if (!potentialReturn && stake && totalOdd) {
      potentialReturn = +(stake * totalOdd).toFixed(2);
    }

    // Cash-out — "Cashout 17,68 R$" ou "Cashout\n17,68 R$"
    let cashoutValue = null;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const m = line.match(/Cash\s*-?\s*out\s*:?\s*R?\$?\s*([\d.,]+)/i);
      if (m) {
        cashoutValue = parseMoney(m[1]);
        break;
      }
      // "Valor do Cashout" na linha, valor na próxima ou mesma
      const m2 = line.match(/Valor\s*do\s*Cash\s*-?\s*out\s*:?\s*R?\$?\s*([\d.,]+)/i);
      if (m2) {
        cashoutValue = parseMoney(m2[1]);
        break;
      }
    }

    // Identificar event_id da Superbet se houver link/data-id
    let superbetEventId = null;
    const linkEl = card.querySelector('a[href*="/event/"], a[href*="/evento/"]');
    if (linkEl) {
      const hrefMatch = linkEl.getAttribute("href")?.match(/(?:event|evento)\/(\d+)/);
      if (hrefMatch) superbetEventId = parseInt(hrefMatch[1], 10);
    }
    // Fallback: data attribute
    if (!superbetEventId) {
      const dataEl = card.querySelector('[data-event-id], [data-eventid]');
      if (dataEl) {
        superbetEventId = parseInt(
          dataEl.getAttribute("data-event-id") || dataEl.getAttribute("data-eventid"),
          10
        );
      }
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
   * Sobe na árvore DOM a partir de um elemento até encontrar o container do card.
   * Critério: contém "APOSTA" E "ODDS" no textContent, e tem apenas 1 botão Cashout.
   */
  function findCardContainer(startEl) {
    let el = startEl;
    for (let i = 0; i < 20 && el && el !== document.body; i++) {
      const text = el.textContent || "";
      const hasAposta = /APOSTA/i.test(text);
      const hasOdds = /ODDS/i.test(text);
      if (hasAposta && hasOdds) {
        // Verificar se é card individual (não container de múltiplos cards)
        const cashoutBtns = el.querySelectorAll('button, [role="button"], a');
        const cashoutCount = Array.from(cashoutBtns).filter(
          (b) => /cashout/i.test(b.textContent || "")
        ).length;
        if (cashoutCount === 1) return el;
        // Se tem mais de 1 cashout, subimos demais — usar o candidato anterior
        if (cashoutCount > 1) return null;
      }
      el = el.parentElement;
    }
    return null;
  }

  /**
   * Escaneia a página e extrai todas as apostas abertas.
   * Usa múltiplas estratégias para encontrar cards de aposta.
   */
  function scanOpenBets() {
    let elements = [];

    // ─── Estratégia 1: Botões de Cashout como âncora ───
    // Cada aposta aberta tem exatamente um botão "Cashout X,XX R$"
    const allButtons = document.querySelectorAll('button, [role="button"], a');
    const cashoutBtns = Array.from(allButtons).filter(
      (btn) => /cashout/i.test(btn.textContent || "")
    );
    console.info(`[Bolão AI] Encontrados ${cashoutBtns.length} botões de Cashout`);

    for (const btn of cashoutBtns) {
      const card = findCardContainer(btn);
      if (card && !elements.includes(card)) {
        elements.push(card);
      }
    }

    // ─── Estratégia 2: Elementos com "AO VIVO" badge ───
    if (elements.length === 0) {
      const allEls = document.querySelectorAll("*");
      const liveMarkers = Array.from(allEls).filter((el) => {
        const t = el.textContent || "";
        return el.children.length === 0 && /AO VIVO/i.test(t) && t.length < 20;
      });
      console.info(`[Bolão AI] Encontrados ${liveMarkers.length} badges AO VIVO`);
      for (const marker of liveMarkers) {
        const card = findCardContainer(marker);
        if (card && !elements.includes(card)) {
          elements.push(card);
        }
      }
    }

    // ─── Estratégia 3: Busca por textContent combinado ───
    if (elements.length === 0) {
      const allDivs = document.querySelectorAll("div, section, article");
      for (const div of allDivs) {
        const text = div.textContent || "";
        if (!/APOSTA/i.test(text)) continue;
        if (!/ODDS/i.test(text)) continue;
        if (!/GANHO/i.test(text)) continue;
        if (!/Cashout/i.test(text)) continue;
        // Contar quantos Cashout tem (para saber se é card individual ou lista)
        const btns = div.querySelectorAll('button, [role="button"], a');
        const cCount = Array.from(btns).filter(
          (b) => /cashout/i.test(b.textContent || "")
        ).length;
        if (cCount === 1) {
          elements.push(div);
        }
      }
      // Remover ancestrais (manter o mais interno)
      elements = elements.filter(
        (el) => !elements.some((other) => other !== el && el.contains(other))
      );
    }

    // ─── Estratégia 4: Último recurso — qualquer div com padrão monetário ───
    if (elements.length === 0) {
      const allDivs = document.querySelectorAll("div");
      const candidates = [];
      for (const div of allDivs) {
        const text = div.textContent || "";
        // Precisa ter: valor R$, ODDS ou @, e algo parecido com time
        const hasValue = /\d+[.,]\d{2}\s*R\$/i.test(text);
        const hasOddOrAt = /@\s*[\d.]+|ODDS/i.test(text);
        const hasSep = /[—–]/.test(text);
        const h = div.offsetHeight || 0;
        if (hasValue && hasOddOrAt && hasSep && h > 100 && h < 450) {
          candidates.push(div);
        }
      }
      elements = candidates.filter(
        (el) => !candidates.some((other) => other !== el && el.contains(other))
      );
    }

    console.info(`[Bolão AI] scanOpenBets: ${elements.length} card(s) encontrado(s)`);
    if (elements.length > 0) {
      console.info("[Bolão AI] Primeiro card textContent:", elements[0].textContent?.slice(0, 200));
    }
    const bets = elements.map(parseBetCard).filter((b) => b.is_open && b.stake > 0);
    console.info(`[Bolão AI] Apostas válidas após parse: ${bets.length}`, bets);
    return bets;
  }

  /**
   * Envia uma aposta para a API via background service worker.
   */
  function sendViaBackground(bet, apiKey) {
    return new Promise((resolve) => {
      const payload = {
        id: bet.ticket_code || `auto_${Date.now()}`,
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
      chrome.runtime.sendMessage(
        { type: "API_POST_OPEN_BET", payload, apiKey },
        (response) => {
          if (chrome.runtime.lastError) {
            resolve({ ok: false, error: chrome.runtime.lastError.message });
          } else {
            resolve(response || { ok: false, error: "Sem resposta do background" });
          }
        }
      );
    });
  }

  /**
   * Escuta mensagens do popup/background.
   */
  chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
    if (request.type === "SCAN_BETS") {
      const bets = scanOpenBets();
      // Enviar cada aposta para a API via background
      chrome.storage.local.get(["bolao_api_key"], async (items) => {
        const apiKey = items.bolao_api_key || "";
        const results = [];
        for (const bet of bets) {
          const r = await sendViaBackground(bet, apiKey);
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
    if (request.type === "PING") {
      sendResponse({ ok: true, url: location.href });
      return true;
    }
    return false;
  });

  console.info("[Bolão AI] Content script carregado. Página:", location.href);
})();
