/**
 * Content script da extensão Bolão AI — Captura Superbet.
 * Roda na página "Minhas Apostas" da Superbet, extrai os cards de aposta
 * e envia para a background script (que repassa para a API).
 */
(function () {
  "use strict";

  const TICKET_RE = /\b([A-Z0-9]{3,}-[A-Z0-9]{4,})\b/;

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

  const PERIOD_1H_RE = /1\s*[º°o]?\s*tempo|primeiro\s*tempo|\b1\s*t\b|1st\s*half|total de gols\s*\(\s*1/i;
  const PERIOD_2H_RE = /2\s*[º°o]?\s*tempo|segundo\s*tempo|\b2\s*t\b|2nd\s*half|total de gols\s*\(\s*2/i;
  const LINE_RE = /([+\-−]?\s*\d+[.,]\d+|[+\-−]?\s*\d+)/;

  function detectPeriod(...texts) {
    const combined = texts.filter(Boolean).join(" ");
    if (PERIOD_2H_RE.test(combined)) return "2h";
    if (PERIOD_1H_RE.test(combined)) return "1h";
    return "ft";
  }

  function handicapLineKey(line) {
    if (Math.abs(line) < 1e-9) return "0";
    if (line < 0) return "m" + String(Math.abs(line)).replace(".", "_");
    return "p" + String(line).replace(".", "_");
  }

  function parseLineValue(text) {
    const match = (text || "").match(LINE_RE);
    if (!match) return null;
    const raw = match[1].replace(/−/g, "-").replace(",", ".").replace(/\s/g, "");
    const val = parseFloat(raw);
    return Number.isFinite(val) ? val : null;
  }

  function detectSide(text, homeTeam, awayTeam) {
    const lower = (text || "").toLowerCase();
    const homeL = (homeTeam || "").toLowerCase().trim();
    const awayL = (awayTeam || "").toLowerCase().trim();
    if (homeL && lower.includes(homeL)) return "home";
    if (awayL && lower.includes(awayL)) return "away";
    if (homeL) {
      const token = homeL.split(/\s+/)[0];
      if (token.length >= 4 && lower.includes(token)) return "home";
    }
    if (awayL) {
      const token = awayL.split(/\s+/)[0];
      if (token.length >= 4 && lower.includes(token)) return "away";
    }
    if (/\b(casa|mandante|home)\b/i.test(lower)) return "home";
    if (/\b(fora|visitante|away)\b/i.test(lower)) return "away";
    return null;
  }

  function classifyPick(marketRaw, pickRaw, homeTeam = "", awayTeam = "") {
    const period = detectPeriod(marketRaw, pickRaw);
    const combined = `${marketRaw} ${pickRaw}`;

    if (/Resultado Final|Match Result|1X2|Vencedor|Winner|Moneyline|Resultado\s*\(?1X2\)?/i.test(combined)) {
      const market = period === "1h" || period === "2h" ? `${period}_h2h` : "h2h";
      let outcome = pickRaw;
      if (/^1$/.test(pickRaw)) outcome = "home";
      else if (/^2$/.test(pickRaw)) outcome = "away";
      else if (/^X$/i.test(pickRaw) || /empate/i.test(pickRaw)) outcome = "draw";
      else if (/^1X$/i.test(pickRaw)) outcome = "home_or_draw";
      else if (/^X2$/i.test(pickRaw)) outcome = "draw_or_away";
      else if (/^12$/i.test(pickRaw)) outcome = "home_or_away";
      return { market, outcome };
    }

    if (/Total de Gols|Over.*Under|Total Goals|\bGols\b/i.test(combined) &&
        !/Escanteio|Corner|Cart[aã]o|Chute/i.test(combined)) {
      const isOver = /Mais|Over|Acima|\+/i.test(pickRaw);
      const lineVal = parseLineValue(pickRaw) ?? parseLineValue(marketRaw);
      const lineStr = lineVal != null ? String(lineVal) : "2.5";
      if (period === "1h" || period === "2h") {
        const lineKey = lineStr.replace(".", "_");
        return {
          market: `${period}_over_${lineKey}`,
          outcome: isOver ? "yes" : "no",
          target_value: lineStr,
        };
      }
      return {
        market: `totals_${lineStr}`,
        outcome: isOver ? "over" : "under",
        target_value: lineStr,
      };
    }

    if (/Handicap/i.test(combined)) {
      const isAsian = /Asi[aá]tico|Asian/i.test(combined);
      const lineVal = parseLineValue(pickRaw) ?? parseLineValue(marketRaw);
      const side = detectSide(pickRaw, homeTeam, awayTeam) || detectSide(marketRaw, homeTeam, awayTeam);
      const hcapKind = isAsian ? "ah" : "hcap";
      const lineStr = lineVal != null ? String(lineVal) : null;
      if (side && lineVal != null) {
        return {
          market: `${period}_${hcapKind}_${side}_${handicapLineKey(lineVal)}`,
          outcome: "yes",
          target_value: lineStr,
        };
      }
      if (lineVal != null) {
        return { market: "handicap", outcome: "yes", target_value: lineStr };
      }
      return { market: "handicap", outcome: pickRaw };
    }

    if (/Escanteio|Corner/i.test(combined)) {
      const isOver = /Mais|Over|Acima|\+/i.test(pickRaw);
      const lineVal = parseLineValue(pickRaw) ?? parseLineValue(marketRaw);
      return {
        market: "corners_total",
        outcome: isOver ? "over" : "under",
        target_value: lineVal != null ? String(lineVal) : undefined,
      };
    }

    if (/Par.*Ímpar|Odd.*Even|Par\/Ímpar/i.test(combined)) {
      return {
        market: /Escanteio|Corner/i.test(combined) ? "odd_even_corners" : "odd_even_goals",
        outcome: /Ímpar|Impar|Odd/i.test(pickRaw) && !/^Par$/i.test(pickRaw.trim()) ? "odd" : "even",
      };
    }

    if (/Ambas.*Marcam|Both.*Score|BTTS/i.test(combined)) {
      const market = /algum dos tempos|any half/i.test(combined) ? "btts_any_half" : "btts";
      return { market, outcome: /Sim|Yes/i.test(pickRaw) ? "yes" : "no" };
    }

    if (/Pr[oó]ximo Gol|Next Goal|2\s*[º°o]?\s*Gol/i.test(combined)) {
      const side = detectSide(pickRaw, homeTeam, awayTeam);
      return { market: "next_goal", outcome: side || pickRaw };
    }

    if (/Dupla\s*Chance/i.test(combined)) {
      return { market: "double_chance", outcome: pickRaw };
    }

    return { market: "other", outcome: pickRaw };
  }

  function pushParsedPick(picks, marketRaw, pickRaw, oddPlaced, rawLine, homeTeam = "", awayTeam = "") {
    const classified = classifyPick(marketRaw, pickRaw, homeTeam, awayTeam);
    const market = classified.market;
    const outcome = classified.outcome;
    const pick = {
      market,
      outcome,
      odd_placed: oddPlaced,
      raw: rawLine || `${marketRaw} — ${pickRaw}`,
    };
    if (classified.target_value) {
      pick.target_value = classified.target_value;
    }
    picks.push(pick);
  }

  /**
   * Extrai dados de um card de aposta da Superbet.
   */
  function parseBetCard(card) {
    const text = card.innerText || card.textContent || "";
    const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);

    // Equipes / evento (jogo ao vivo ou longo prazo)
    let eventName = "";
    let homeTeam = "";
    let awayTeam = "";
    for (const line of lines) {
      if (/Longo\s*Prazo|Outright|Vencedor.*Copa/i.test(line)) {
        eventName = line;
        homeTeam = "Longo Prazo";
        awayTeam = "Copa 2026";
        break;
      }
      for (const sep of ["·", "—", " - ", " vs ", " x ", " X "]) {
        if (line.includes(sep)) {
          const parts = line.split(sep);
          if (parts.length >= 2 && parts[0].length > 1 && parts[1].length > 1) {
            // Ignorar linhas de mercado tipo "Handicap - ..."
            if (/^Handicap|^Total|^Grupo|^Ambas/i.test(parts[0])) continue;
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

    // Mercado e palpite — formatos Superbet
    const picks = [];
    for (const line of lines) {
      const mSuperbet = line.match(/(.+?)\s*[—–-]\s*(.+?)\s*@\s*([\d.,]+)/);
      if (mSuperbet) {
        pushParsedPick(
          picks,
          mSuperbet[1].trim(),
          mSuperbet[2].trim(),
          parseFloat(mSuperbet[3].replace(",", ".")),
          line,
          homeTeam,
          awayTeam
        );
        continue;
      }

      const mEndAt = line.match(/^(.+?)\s*@\s*([\d.,]+)$/);
      if (mEndAt && !/^ODDS/i.test(mEndAt[1])) {
        const left = mEndAt[1].trim();
        const oddPlaced = parseFloat(mEndAt[2].replace(",", "."));
        const dash = left.match(/^(.+?)\s*[—–-]\s*(.+)$/);
        if (dash) {
          pushParsedPick(picks, dash[1].trim(), dash[2].trim(), oddPlaced, line, homeTeam, awayTeam);
        } else if (/^[12X]$|^1X$|^X2$|^12$/i.test(left)) {
          pushParsedPick(picks, "Resultado Final", left, oddPlaced, line, homeTeam, awayTeam);
        } else {
          pushParsedPick(picks, "Mercado", left, oddPlaced, line, homeTeam, awayTeam);
        }
        continue;
      }

      const dashPick = line.match(/^(.+?)\s*[—–-]\s*(.+)$/);
      if (dashPick) {
        const classified = classifyPick(dashPick[1].trim(), dashPick[2].trim(), homeTeam, awayTeam);
        picks.push({ ...classified, raw: line });
      } else if (/Resultado Final|Match Result|1X2/i.test(line)) {
        const m = line.match(/[–\-:]\s*([1X2]|1X|X2|12)/i);
        if (m) {
          const classified = classifyPick("Resultado Final", m[1], homeTeam, awayTeam);
          picks.push({ ...classified, raw: line });
        }
      } else if (/Ambas.*Marcam|Both.*Score|BTTS/i.test(line)) {
        const classified = classifyPick("Ambas as Equipes Marcam", line, homeTeam, awayTeam);
        picks.push({ ...classified, raw: line });
      } else if (/Total de Gols|Over\/Under|Total Goals/i.test(line)) {
        const classified = classifyPick("Total de Gols", line, homeTeam, awayTeam);
        picks.push({ ...classified, raw: line });
      } else if (/Handicap/i.test(line)) {
        const classified = classifyPick("Handicap", line, homeTeam, awayTeam);
        picks.push({ ...classified, raw: line });
      }
    }

    // Palpite em linha anterior ao "@ odd" isolado
    if (picks.length === 0) {
      for (let i = 0; i < lines.length; i++) {
        const mAt = lines[i].match(/^@\s*([\d.,]+)$/);
        if (!mAt || i === 0) continue;
        const pickRaw = lines[i - 1];
        const marketRaw = i > 1 ? lines[i - 2] : "Mercado";
        if (/APOSTA|ODDS|GANHO|Cashout|AO VIVO/i.test(pickRaw)) continue;
        pushParsedPick(
          picks,
          marketRaw,
          pickRaw,
          parseFloat(mAt[1].replace(",", ".")),
          `${marketRaw} / ${pickRaw} @ ${mAt[1]}`,
          homeTeam,
          awayTeam
        );
      }
    }

    // Stake — pode estar na mesma linha ("APOSTA 20,00 R$") ou em linhas seguintes
    let stake = 0;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      // Mesma linha: "APOSTA 20,00 R$" ou "APOSTA: R$ 20,00"
      const m = line.match(/(?:APOSTA|Stake|Valor)\s*:?\s*R?\$?\s*([\d.,]+)/i);
      if (m) {
        stake = parseMoney(m[1]);
        break;
      }
      // Linha isolada "APOSTA" → valor pode estar 1-3 linhas abaixo
      // (a próxima pode ser "ODDS TOTAIS" num layout de duas colunas)
      if (/^APOSTA$/i.test(line)) {
        for (let j = i + 1; j < Math.min(i + 4, lines.length); j++) {
          const val = parseMoney(lines[j]);
          if (val > 0) { stake = val; break; }
        }
        if (stake > 0) break;
      }
    }
    // Último fallback: primeiro valor monetário isolado no card que não seja ganho/cashout
    if (stake === 0) {
      for (const line of lines) {
        if (/GANHO|POTENCIAL|Cashout|ODDS|RETORNO/i.test(line)) continue;
        const m = line.match(/^R?\$?\s*([\d]+[.,]\d{2})\s*R?\$?$/i);
        if (m) { stake = parseMoney(m[1]); break; }
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

    // Fallback: linha só com palpite @ odd (sem nome de mercado)
    if (picks.length === 0) {
      for (const line of lines) {
        const mAt = line.match(/^([1X2]|Sim|Não|Yes|No|1X|X2|12)\s*@\s*([\d.,]+)/i);
        if (mAt) {
          pushParsedPick(
            picks,
            "Resultado Final",
            mAt[1].trim(),
            parseFloat(mAt[2].replace(",", ".")),
            line
          );
          if (!totalOdd) totalOdd = parseFloat(mAt[2].replace(",", "."));
          break;
        }
      }
    }

    // Último recurso: qualquer @ odd no card → mercado genérico (melhor que 0 picks)
    if (picks.length === 0 && totalOdd > 1) {
      for (const line of lines) {
        if (/APOSTA|ODDS TOTAIS|GANHO|Cashout/i.test(line)) continue;
        const gm = line.match(/@\s*([\d.,]+)/);
        if (gm) {
          pushParsedPick(picks, "Mercado", line.split("@")[0].trim() || "palpite", totalOdd, line);
          break;
        }
      }
    }

    // Handicap, grupos WC (longo prazo) e pernas de combo
    for (const line of lines) {
      if (/^Handicap/i.test(line)) {
        const pickPart = line.replace(/^Handicap:?\s*/i, "").trim();
        if (pickPart && !picks.some((p) => p.raw === line)) {
          pushParsedPick(picks, "Handicap", pickPart, totalOdd || 0, line);
        }
        continue;
      }
      if (
        /Grupo\s+[A-L]\b|Classifica(?:ç|c)ão|classificar|Vencedor do Grupo/i.test(line) &&
        !/APOSTA|ODDS|GANHO|Cashout|AO VIVO|Longo Prazo|SuperMúltipla/i.test(line) &&
        line.length > 8 &&
        line.length < 120
      ) {
        if (!picks.some((p) => p.raw === line)) {
          pushParsedPick(picks, "outright", line.trim(), 0, line);
        }
      }
    }

    const comboMore = text.match(/\+\s*(\d+)\s*(more|mais)\s*sele/i);
    if (comboMore && picks.length > 0) {
      picks.push({
        market: "combo",
        outcome: `legs_${comboMore[1]}`,
        raw: comboMore[0],
      });
    }

    if (!eventName && picks.length > 0) {
      eventName = (picks[0].raw || "Aposta").slice(0, 80);
      homeTeam = homeTeam || "Aposta";
      awayTeam = awayTeam || "Superbet";
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

    let liveMinute = null;
    const minuteMatch = text.match(/(?:^|\s)(\d{1,3})\s*[''′](?:\s|$)/m);
    if (minuteMatch) {
      const m = parseInt(minuteMatch[1], 10);
      if (Number.isFinite(m) && m >= 0 && m <= 120) liveMinute = m;
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
      live_minute: liveMinute,
    };
  }

  /**
   * Sobe na árvore DOM a partir de um elemento até encontrar o container do card.
   * Guarda o candidato mais interno com exatamente 1 botão Cashout.
   */
  function findCardContainer(startEl) {
    let el = startEl;
    let best = null;
    for (let i = 0; i < 25 && el && el !== document.body; i++) {
      const text = el.textContent || "";
      const hasAposta = /APOSTA/i.test(text);
      const hasOdds = /ODDS/i.test(text);
      if (hasAposta && hasOdds) {
        const cashoutBtns = el.querySelectorAll('button, [role="button"], a');
        const cashoutCount = Array.from(cashoutBtns).filter(
          (b) => /cashout/i.test(b.textContent || "")
        ).length;
        if (cashoutCount === 1) {
          best = el;
        } else if (cashoutCount > 1 && best) {
          return best;
        }
      }
      el = el.parentElement;
    }
    return best;
  }

  /**
   * Verifica se um elemento parece um card individual de aposta aberta.
   */
  function isBetCardElement(el) {
    if (!el || el === document.body) return false;
    const text = el.innerText || "";
    if (!/\bAPOSTA\b/i.test(text)) return false;
    if (!/ODDS/i.test(text)) return false;
    if (!/(GANHO|Cashout|Cash.?out|indisponível)/i.test(text)) return false;
    if (/(Ganhou|Perdeu|Encerrado|Concluído|SACADO)/i.test(text)) return false;
    const hasTeamSep = /[—–·]/.test(text);
    const isOutright =
      /Longo\s*Prazo|Copa do Mundo 2026|SuperMúltipla|SuperMultipla|Grupo\s+[A-L]\b/i.test(text);
    const isHandicapCombo = /Handicap/i.test(text);
    if (!hasTeamSep && !isOutright && !isHandicapCombo) return false;
    const h = el.offsetHeight || 0;
    if (h < 65 || h > 950) return false;
    const apostaLabels = (text.match(/\bAPOSTA\b/gi) || []).length;
    return apostaLabels >= 1 && apostaLabels <= 6;
  }

  /**
   * Lista containers com scroll (a lista de apostas costuma ser interna, não a página).
   */
  function findScrollableContainers() {
    const out = new Set();
    out.add(document.scrollingElement || document.documentElement);
    for (const el of document.querySelectorAll("*")) {
      const style = getComputedStyle(el);
      const oy = style.overflowY;
      if ((oy === "auto" || oy === "scroll" || oy === "overlay") && el.scrollHeight > el.clientHeight + 30) {
        out.add(el);
      }
    }
    return Array.from(out).sort((a, b) => b.scrollHeight - a.scrollHeight);
  }

  /**
   * Rola todos os containers scrolláveis + janela para lazy-load.
   */
  async function scrollToLoadAllBets() {
    const containers = findScrollableContainers();
    console.info(`[Bolão AI] Containers scrolláveis: ${containers.length}`);

    for (const container of containers) {
      let lastPos = -1;
      let stable = 0;
      const step = Math.max(280, (container.clientHeight || window.innerHeight) * 0.85);

      for (let i = 0; i < 55; i++) {
        if (container === document.documentElement || container === document.body) {
          window.scrollBy(0, step);
        } else {
          container.scrollTop += step;
        }
        await new Promise((r) => setTimeout(r, 180));
        const pos =
          container === document.documentElement || container === document.body
            ? window.scrollY
            : container.scrollTop;
        if (pos === lastPos) {
          stable += 1;
          if (stable >= 2) break;
        } else {
          stable = 0;
          lastPos = pos;
        }
      }

      if (container === document.documentElement || container === document.body) {
        window.scrollTo(0, 0);
      } else {
        container.scrollTop = 0;
      }
    }
    await new Promise((r) => setTimeout(r, 350));
  }

  function collectAllTicketCodesOnPage() {
    const codes = new Set();
    const re = new RegExp(TICKET_RE.source, "g");
    const bodyText = document.body.innerText || "";
    let m;
    while ((m = re.exec(bodyText)) !== null) codes.add(m[1]);
    return Array.from(codes);
  }

  function findCardByTicket(ticketCode) {
    let best = null;
    let bestH = Infinity;
    for (const el of document.querySelectorAll("div, article, section, li")) {
      const t = el.innerText || "";
      if (!t.includes(ticketCode)) continue;
      if (!isBetCardElement(el)) continue;
      const h = el.offsetHeight || 9999;
      if (h < bestH) {
        best = el;
        bestH = h;
      }
    }
    return best;
  }

  function findOpenBetCardsWithoutCashout() {
    const found = [];
    for (const el of document.querySelectorAll("div, article, section, li")) {
      if (!isBetCardElement(el)) continue;
      const btns = el.querySelectorAll('button, [role="button"], a');
      const cashoutCount = Array.from(btns).filter((b) =>
        /cashout/i.test(b.textContent || "")
      ).length;
      if (cashoutCount === 0) found.push(el);
    }
    return found.filter(
      (el) => !found.some((other) => other !== el && el.contains(other))
    );
  }

  /**
   * Escaneia a página e extrai todas as apostas abertas.
   * Usa múltiplas estratégias para encontrar cards de aposta.
   */
  async function scanOpenBets() {
    await scrollToLoadAllBets();

    let elements = [];
    const seenCards = new Set();

    function addCard(card) {
      if (!card || seenCards.has(card)) return;
      seenCards.add(card);
      elements.push(card);
    }

    // ─── Estratégia 1: Botões de Cashout como âncora ───
    const allButtons = document.querySelectorAll('button, [role="button"], a');
    const cashoutBtns = Array.from(allButtons).filter(
      (btn) => /cashout/i.test(btn.textContent || "")
    );
    console.info(`[Bolão AI] Encontrados ${cashoutBtns.length} botões de Cashout`);

    for (const btn of cashoutBtns) {
      addCard(findCardContainer(btn));
    }

    // ─── Estratégia 2: Elementos com "AO VIVO" badge ───
    const allEls = document.querySelectorAll("*");
    const liveMarkers = Array.from(allEls).filter((el) => {
      const t = el.textContent || "";
      return el.children.length === 0 && /AO VIVO/i.test(t) && t.length < 20;
    });
    console.info(`[Bolão AI] Encontrados ${liveMarkers.length} badges AO VIVO`);
    for (const marker of liveMarkers) {
      addCard(findCardContainer(marker));
    }

    // ─── Estratégia 3: Busca por textContent combinado ───
    if (elements.length < cashoutBtns.length) {
      const allDivs = document.querySelectorAll("div, section, article");
      for (const div of allDivs) {
        const text = div.textContent || "";
        if (!/APOSTA/i.test(text)) continue;
        if (!/ODDS/i.test(text)) continue;
        if (!/GANHO/i.test(text)) continue;
        if (!/Cashout/i.test(text)) continue;
        const btns = div.querySelectorAll('button, [role="button"], a');
        const cCount = Array.from(btns).filter(
          (b) => /cashout/i.test(b.textContent || "")
        ).length;
        if (cCount === 1) {
          addCard(div);
        }
      }
      elements = elements.filter(
        (el) => !elements.some((other) => other !== el && el.contains(other))
      );
    }

    // ─── Estratégia 4: Código de ticket visível ───
    const ticketCodes = collectAllTicketCodesOnPage();
    console.info(`[Bolão AI] Tickets visíveis na página: ${ticketCodes.length}`, ticketCodes);
    for (const code of ticketCodes) {
      addCard(findCardByTicket(code));
    }

    // ─── Estratégia 5: Cards abertos sem botão Cashout (pré-jogo / cashout indisponível) ───
    const noCashout = findOpenBetCardsWithoutCashout();
    console.info(`[Bolão AI] Cards sem cashout: ${noCashout.length}`);
    for (const card of noCashout) addCard(card);

    // ─── Estratégia 6: Longo prazo / SuperMúltipla ───
    for (const el of document.querySelectorAll("div, article, section, li")) {
      const t = el.innerText || "";
      if (!/Longo\s*Prazo|SuperMúltipla|SuperMultipla/i.test(t)) continue;
      if (isBetCardElement(el)) addCard(el);
    }

    // Remover cards ancestrais (manter o mais específico)
    elements = elements.filter(
      (el) => !elements.some((other) => other !== el && el.contains(other))
    );

    console.info(`[Bolão AI] scanOpenBets: ${elements.length} card(s) encontrado(s)`);
    if (elements.length > 0) {
      console.info("[Bolão AI] Primeiro card textContent:", elements[0].textContent?.slice(0, 200));
    }

    const parsed = elements.map(parseBetCard).filter((b) => b.is_open && b.stake > 0);

    // Deduplicar — mesma stake+odd em eventos diferentes são apostas distintas
    const byTicket = new Map();
    for (const b of parsed) {
      const pickKey = (b.picks || []).map((p) => p.raw || p.outcome).join("|");
      const key =
        b.ticket_code ||
        `${b.event_name}|${b.stake}|${b.odds_placed}|${pickKey}|${b.potential_return}`;
      if (!byTicket.has(key)) byTicket.set(key, b);
    }
    const bets = Array.from(byTicket.values());

    const debug = {
      cashout_buttons: cashoutBtns.length,
      live_badges: liveMarkers.length,
      tickets_on_page: ticketCodes.length,
      cards_no_cashout: noCashout.length,
      cards_found: elements.length,
      bets_parsed: bets.length,
    };
    console.info(`[Bolão AI] Apostas válidas após parse: ${bets.length}`, bets, debug);

    if (ticketCodes.length > bets.length) {
      console.warn(
        `[Bolão AI] Faltam ${ticketCodes.length - bets.length} bilhete(s): role a lista de apostas na Superbet e capture de novo.`
      );
    }

    return { bets, debug };
  }

  // ════════════════════════════════════════════════════════════════════════════
  // APOSTAS FINALIZADAS (tab "Finalizado" / "Encerrado")
  // ════════════════════════════════════════════════════════════════════════════

  /**
   * Detecta o resultado de uma aposta finalizada a partir do texto do card.
   * Retorna: "won" | "lost" | "cashout" | "void"
   */
  function detectResult(text) {
    if (/SACADO|CASHED?\s*-?\s*OUT|Cash\s*Out\s*feito/i.test(text)) return "cashout";
    if (/GANHOU|WON|ACERTOU|VITÓRIA/i.test(text)) return "won";
    if (/PERDEU|LOST|ERROU|DERROTA/i.test(text)) return "lost";
    if (/CANCELAD|VOID|ANULAD|REEMBOLSAD/i.test(text)) return "void";
    // Indicadores visuais: ✅ ou ❌ (emojis no DOM)
    if (/✅|✓/.test(text)) return "won";
    if (/❌|✗/.test(text)) return "lost";
    return "lost"; // default se nenhum padrão reconhecido
  }

  /**
   * Extrai o placar final do card (ex: "2 - 0", "1 : 1").
   */
  function extractFinalScore(text) {
    // "Placar final: 2 - 0" ou "2:1" ou "2 x 1"
    const patterns = [
      /(?:Placar|Score|Final)\s*:?\s*(\d+)\s*[-:xX×]\s*(\d+)/i,
      /(\d+)\s*[-:×]\s*(\d+)\s*(?:FT|Full|Final)/i,
    ];
    for (const p of patterns) {
      const m = text.match(p);
      if (m) return `${m[1]}x${m[2]}`;
    }
    return null;
  }

  /**
   * Calcula o lucro/prejuízo de uma aposta finalizada.
   */
  function calculateProfit(result, stake, potentialReturn, cashoutValue) {
    switch (result) {
      case "won":
        return +(potentialReturn - stake).toFixed(2);
      case "cashout":
        return +((cashoutValue || 0) - stake).toFixed(2);
      case "void":
        return 0;
      case "lost":
      default:
        return -stake;
    }
  }

  /**
   * Identifica o container de card para apostas finalizadas.
   * Diferente de apostas abertas: não tem botão Cashout, mas tem resultado (GANHOU/PERDEU).
   */
  function findSettledCardContainer(startEl) {
    let el = startEl;
    for (let i = 0; i < 20 && el && el !== document.body; i++) {
      const text = el.textContent || "";
      const hasAposta = /APOSTA/i.test(text);
      const hasOdds = /ODDS/i.test(text);
      const hasResult = /GANHOU|PERDEU|SACADO|WON|LOST|CASHED/i.test(text);
      if (hasAposta && (hasOdds || hasResult)) {
        // Verificar se é card individual — deve ter exatamente 1 indicador de resultado
        const innerText = el.innerText || "";
        const resultMatches = innerText.match(/GANHOU|PERDEU|SACADO|✅|❌/gi);
        // Cards simples: 1 resultado; combos: podem ter mais
        if (resultMatches && resultMatches.length >= 1 && resultMatches.length <= 6) {
          // Verificar que não é container de múltiplos cards (muitos "APOSTA")
          const apostaCount = (innerText.match(/^APOSTA$/gmi) || []).length;
          if (apostaCount <= 1) return el;
        }
      }
      el = el.parentElement;
    }
    return null;
  }

  /**
   * Extrai dados de um card de aposta finalizada.
   */
  function parseSettledBetCard(card) {
    const base = parseBetCard(card);
    const text = card.innerText || card.textContent || "";

    const result = detectResult(text);
    const finalScore = extractFinalScore(text);

    // Para cards finalizados, cashout_value pode indicar quanto recebeu (SACADO)
    let cashoutValue = base.cashout_value;
    if (result === "cashout" && !cashoutValue) {
      // Tentar extrair "Valor sacado: R$ 17,68"
      const m = text.match(/(?:Valor\s*(?:do\s*)?(?:saque|sacado|cash))\s*:?\s*R?\$?\s*([\d.,]+)/i);
      if (m) cashoutValue = parseMoney(m[1]);
    }

    // Ganho potencial pode estar como "GANHO POTENCIAL" ou "RETORNO"
    let potentialReturn = base.potential_return;
    if (!potentialReturn && result === "won") {
      // Se ganhou mas não temos retorno, tentar extrair do texto
      const m = text.match(/(?:RETORNO|GANHO|LUCRO)\s*:?\s*R?\$?\s*([\d.,]+)/i);
      if (m) potentialReturn = parseMoney(m[1]);
    }

    const profit = calculateProfit(result, base.stake, potentialReturn, cashoutValue);

    return {
      id: base.ticket_code || `settled_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      event_name: base.event_name,
      home_team: base.home_team,
      away_team: base.away_team,
      picks: base.picks,
      stake: base.stake,
      odds_placed: base.odds_placed,
      potential_return: potentialReturn,
      result,
      profit,
      cashout_value: cashoutValue,
      ticket_code: base.ticket_code,
      source: "superbet_extension",
      superbet_event_id: base.superbet_event_id,
      final_score: finalScore,
      settled_at: new Date().toISOString(),
    };
  }

  /**
   * Escaneia a página "Finalizado" e extrai apostas encerradas.
   */
  function scanSettledBets() {
    let elements = [];

    // ─── Estratégia 1: Elementos com indicadores de resultado ───
    // Cards finalizados têm GANHOU/PERDEU/SACADO em destaque
    const allEls = document.querySelectorAll("*");
    const resultMarkers = Array.from(allEls).filter((el) => {
      const t = (el.textContent || "").trim();
      return (
        el.children.length === 0 &&
        /^(GANHOU|PERDEU|SACADO|WON|LOST|CASHED OUT)$/i.test(t) &&
        t.length < 30
      );
    });
    console.info(`[Bolão AI] Encontrados ${resultMarkers.length} indicadores de resultado`);

    for (const marker of resultMarkers) {
      const card = findSettledCardContainer(marker);
      if (card && !elements.includes(card)) {
        elements.push(card);
      }
    }

    // ─── Estratégia 2: Busca por padrão visual ✅/❌ ───
    if (elements.length === 0) {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode())) {
        const t = node.textContent || "";
        if (/[✅❌✓✗]/.test(t)) {
          const card = findSettledCardContainer(node.parentElement);
          if (card && !elements.includes(card)) {
            elements.push(card);
          }
        }
      }
    }

    // ─── Estratégia 3: Divs com "APOSTA" + "ODDS" + sem Cashout button ───
    if (elements.length === 0) {
      const allDivs = document.querySelectorAll("div, section, article");
      for (const div of allDivs) {
        const text = div.textContent || "";
        if (!/APOSTA/i.test(text)) continue;
        if (!/ODDS/i.test(text)) continue;
        // Deve ter resultado mas NÃO ter botão de cashout ativo
        const hasResult = /GANHOU|PERDEU|SACADO|WON|LOST/i.test(text);
        if (!hasResult) continue;
        const btns = div.querySelectorAll('button, [role="button"]');
        const hasCashoutBtn = Array.from(btns).some(
          (b) => /cashout/i.test(b.textContent || "")
        );
        if (hasCashoutBtn) continue; // É aposta aberta, não finalizada
        // Verificar tamanho razoável
        const h = div.offsetHeight || 0;
        if (h > 80 && h < 500) {
          elements.push(div);
        }
      }
      // Remover ancestrais
      elements = elements.filter(
        (el) => !elements.some((other) => other !== el && el.contains(other))
      );
    }

    console.info(`[Bolão AI] scanSettledBets: ${elements.length} card(s) encontrado(s)`);
    if (elements.length > 0) {
      console.info("[Bolão AI] Primeiro settled card:", elements[0].textContent?.slice(0, 200));
    }

    const bets = elements
      .map(parseSettledBetCard)
      .filter((b) => b.stake > 0 && b.result);

    console.info(`[Bolão AI] Apostas finalizadas válidas: ${bets.length}`, bets);
    return bets;
  }

  /**
   * Escaneia página de carteira/extrato e monta CSV no formato Superbet.
   */
  function scanWalletTransactions() {
    const rows = [];
    const seen = new Set();
    const txKeywords = [
      "bilhete colocado",
      "bilhete confirmado",
      "valor ganhado",
      "depósito",
      "saque",
      "reembolso",
      "cancelamento",
    ];

    function addRow(datetime, type, amount, game) {
      const key = `${datetime}|${type}|${amount}|${game}`;
      if (seen.has(key)) return;
      seen.add(key);
      rows.push({ datetime, type, amount, game: game || "UNKNOWN" });
    }

    // Estratégia 1: linhas de tabela HTML
    document.querySelectorAll("tr").forEach((tr) => {
      const text = (tr.innerText || "").replace(/\s+/g, " ").trim();
      if (!text || text.length < 10) return;
      const dt = text.match(/(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)/);
      if (!dt) return;
      const lower = text.toLowerCase();
      const type = txKeywords.find((k) => lower.includes(k));
      if (!type) return;
      const amounts = [...text.matchAll(/([\d]+[.,]\d{2})/g)].map((m) => parseMoney(m[1]));
      const amount = amounts.length ? amounts[0] : 0;
      const gameMatch = text.match(/(me-[A-Z0-9-]+|INPLAY[^\s,]*)/i);
      addRow(dt[1], type, amount, gameMatch ? gameMatch[1] : "UNKNOWN");
    });

    // Estratégia 2: blocos de texto sequencial
    if (rows.length === 0) {
      const lines = (document.body.innerText || "").split("\n").map((l) => l.trim()).filter(Boolean);
      for (let i = 0; i < lines.length; i++) {
        const dt = lines[i].match(/^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)/);
        if (!dt) continue;
        let type = null;
        let amount = null;
        let game = "UNKNOWN";
        for (let j = i; j < Math.min(i + 6, lines.length); j++) {
          const lower = lines[j].toLowerCase();
          if (!type) type = txKeywords.find((k) => lower.includes(k)) || null;
          if (amount === null) {
            const m = lines[j].match(/R?\$?\s*([\d.,]+)/);
            if (m) amount = parseMoney(m[1]);
          }
          if (/me-|INPLAY/i.test(lines[j])) game = lines[j].slice(0, 80);
        }
        if (type && amount !== null) addRow(dt[1], type, amount, game);
      }
    }

    console.info(`[Bolão AI] scanWalletTransactions: ${rows.length} linha(s)`);
    return rows;
  }

  function buildWalletCsv(rows) {
    const header =
      "DataHoraDaTransação,Transação,Método de Pagamento,Valor,SaldoEmDinheiro,SaldoEmDinheiroAnterior,SaldoBônus,SaldoBônusAnterior,NomeDoJogo";
    const body = rows
      .map((r) => `${r.datetime},${r.type},,${r.amount.toFixed(2)},,,,,${r.game}`)
      .join("\n");
    return `Dados da carteira — Bolão AI extension\n${header}\n${body}\n`;
  }

  function sendWalletCsvViaBackground(csvText, apiKey, userId) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(
        { type: "API_UPLOAD_WALLET_CSV", csvText, apiKey, userId },
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
   * Envia apostas finalizadas para a API via background.
   */
  function sendSettledBetsViaBackground(bets, apiKey) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(
        { type: "API_POST_SETTLED_BETS", payload: bets, apiKey },
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

  function validateBetPayload(bet) {
    const issues = [];
    if (!bet.picks || bet.picks.length === 0) {
      issues.push("palpite não reconhecido (0 picks)");
    }
    if (!bet.odds_placed || bet.odds_placed <= 1) {
      issues.push(`odd inválida (${bet.odds_placed || 0})`);
    }
    if (!bet.potential_return || bet.potential_return <= 0) {
      issues.push("retorno potencial ausente");
    }
    if ((!bet.home_team || !bet.away_team) && !bet.event_name) {
      issues.push("evento não identificado");
    }
    return issues;
  }

  function normalizeBetPayload(bet) {
    const event = bet.event_name || "Aposta Superbet";
    return {
      ...bet,
      event_name: event,
      home_team: bet.home_team || event.split(/[—–·-]/)[0]?.trim() || "Aposta",
      away_team: bet.away_team || event.split(/[—–·-]/)[1]?.trim() || "Superbet",
    };
  }

  function betFingerprint(bet) {
    const normalized = normalizeBetPayload(bet);
    const pick = normalized.picks?.[0] || {};
    const eventKey =
      normalized.superbet_event_id ||
      `${normalized.home_team}|${normalized.away_team}`.toLowerCase();
    return `${eventKey}::${pick.market || ""}::${String(pick.outcome || "").toLowerCase()}`;
  }

  function fetchOpenBetsViaBackground(apiKey) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: "API_GET_OPEN_BETS", apiKey }, (response) => {
        if (chrome.runtime.lastError) {
          resolve([]);
          return;
        }
        resolve(response?.data?.bets || []);
      });
    });
  }

  function dedupeOpenBetsViaBackground(apiKey) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: "API_DEDUPE_OPEN_BETS", apiKey }, (response) => {
        resolve(response || { ok: false });
      });
    });
  }

  function checkAgainstModelViaBackground(bet, apiKey) {
    const pick = bet.picks?.[0];
    if (!pick || pick.market !== "h2h") {
      return Promise.resolve(null);
    }
    const normalized = normalizeBetPayload(bet);
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(
        {
          type: "API_CHECK_AGAINST_MODEL",
          apiKey,
          payload: {
            market: "h2h",
            outcome: pick.outcome,
            home_team: normalized.home_team,
            away_team: normalized.away_team,
            superbet_event_id: normalized.superbet_event_id,
            stake: normalized.stake,
            odds_placed: normalized.odds_placed,
            phase: "friendly",
          },
        },
        (response) => {
          if (chrome.runtime.lastError || !response?.ok) {
            resolve(null);
            return;
          }
          resolve(response.data?.alert || null);
        }
      );
    });
  }

  function resolveGuardrailResponse(response) {
    if (response?.ok) return response;
    if (response?.status !== 409) return response;

    const code = response.detail?.code || response.data?.detail?.code;
    const message =
      response.detail?.message ||
      response.data?.detail?.message ||
      response.error ||
      "Regra P0 bloqueou o cadastro";

    if (code === "duplicate_market") {
      return {
        ...response,
        ok: true,
        skipped: true,
        guardrail: code,
        error: message,
      };
    }

    return {
      ...response,
      ok: false,
      skipped: true,
      guardrail: code || "guardrail",
      error: message,
    };
  }

  /**
   * Envia uma aposta para a API via background service worker.
   */
  async function sendViaBackground(bet, apiKey) {
    const issues = validateBetPayload(bet);
    if (issues.length) {
      return {
        ok: false,
        skipped: true,
        error: issues.join("; "),
        status: 0,
      };
    }

    const normalized = normalizeBetPayload(bet);
    const againstModelAlert = await checkAgainstModelViaBackground(normalized, apiKey);

    const payload = {
      id: normalized.ticket_code || `auto_${Date.now()}`,
      superbet_event_id: normalized.superbet_event_id,
      event_name: normalized.event_name,
      home_team: normalized.home_team,
      away_team: normalized.away_team,
      picks: normalized.picks.map((p) => ({
        market: p.market,
        outcome: p.outcome,
        target_value: p.target_value || null,
      })),
      stake: normalized.stake,
      odds_placed: normalized.odds_placed,
      potential_return: normalized.potential_return,
      cashout_value: normalized.cashout_value,
      ticket_code: normalized.ticket_code,
      source: "superbet_extension",
      minute: normalized.live_minute ?? null,
    };

    return new Promise((resolve) => {
      chrome.runtime.sendMessage(
        { type: "API_POST_OPEN_BET", payload, apiKey },
        (response) => {
          if (chrome.runtime.lastError) {
            resolve({ ok: false, error: chrome.runtime.lastError.message });
            return;
          }
          const base = resolveGuardrailResponse(
            response || { ok: false, error: "Sem resposta do background" }
          );
          if (againstModelAlert) {
            base.against_model_alert = againstModelAlert;
            base.against_model = true;
          }
          resolve(base);
        }
      );
    });
  }

  /**
   * Escuta mensagens do popup/background.
   */
  chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
    if (request.type === "SCAN_BETS") {
      (async () => {
        const { bets, debug } = await scanOpenBets();
        const apiKey =
          request.apiKey ||
          (await new Promise((resolve) => {
            chrome.storage.local.get(["bolao_api_key"], (items) => {
              resolve(items.bolao_api_key || "");
            });
          }));

        await dedupeOpenBetsViaBackground(apiKey);
        const existing = await fetchOpenBetsViaBackground(apiKey);
        const seen = new Set(
          existing.map((b) => {
            const pick = b.picks?.[0] || {};
            const eventKey =
              b.superbet_event_id || `${b.home_team}|${b.away_team}`.toLowerCase();
            return `${eventKey}::${pick.market || ""}::${String(pick.outcome || "").toLowerCase()}`;
          })
        );

        const results = [];
        let againstModelCount = 0;
        for (const bet of bets) {
          const fp = betFingerprint(bet);
          if (seen.has(fp)) {
            results.push({
              ticket: bet.ticket_code,
              event: bet.event_name,
              ok: true,
              skipped: true,
              guardrail: "duplicate_local",
              error: "Aposta já cadastrada (mesmo mercado/jogo)",
              status: 0,
            });
            continue;
          }
          const r = await sendViaBackground(bet, apiKey);
          if (r.against_model_alert) againstModelCount += 1;
          if (r.ok && !r.skipped) seen.add(fp);
          results.push({ ticket: bet.ticket_code, event: bet.event_name, ...r });
        }
        if (againstModelCount > 0) {
          chrome.runtime.sendMessage({
            type: "SHOW_AGAINST_MODEL_NOTIFICATION",
            count: againstModelCount,
            message: `${againstModelCount} aposta(s) 1X2 contra o palpite do modelo`,
          });
        }
        sendResponse({ bets, results, debug, against_model_count: againstModelCount });
      })();
      return true; // async response
    }
    if (request.type === "GET_BETS") {
      (async () => {
        const out = await scanOpenBets();
        sendResponse(out);
      })();
      return true;
    }
    if (request.type === "CAPTURE_WALLET_CSV") {
      const rows = scanWalletTransactions();
      if (rows.length === 0) {
        sendResponse({ rows: [], csv: "", result: { ok: false, error: "Nenhuma transação encontrada" } });
        return true;
      }
      const csv = buildWalletCsv(rows);
      chrome.storage.local.get(["bolao_api_key", "bolao_user_id"], async (items) => {
        const apiKey = items.bolao_api_key || request.apiKey || "";
        const userId = items.bolao_user_id || request.userId || "jamarorn";
        const result = await sendWalletCsvViaBackground(csv, apiKey, userId);
        sendResponse({ rows, csv, result });
      });
      return true;
    }
    if (request.type === "CAPTURE_SETTLED_BETS") {
      (async () => {
        const bets = scanSettledBets();
        const apiKey =
          request.apiKey ||
          (await new Promise((resolve) => {
            chrome.storage.local.get(["bolao_api_key"], (items) => {
              resolve(items.bolao_api_key || "");
            });
          }));
        if (bets.length === 0) {
          sendResponse({ bets: [], result: { ok: true, added: 0 } });
          return;
        }
        const result = await sendSettledBetsViaBackground(bets, apiKey);
        sendResponse({ bets, result });
      })();
      return true; // async response
    }
    if (request.type === "PING") {
      sendResponse({ ok: true, url: location.href });
      return true;
    }
    return false;
  });

  console.info("[Bolão AI] Content script carregado. Página:", location.href);

  // ── P2: alerta contra palpite na página do evento (bet slip) ──
  function extractEventIdFromUrl() {
    if (typeof window.bolaoExtractSuperbetEventId === "function") {
      const id = window.bolaoExtractSuperbetEventId();
      if (id) return id;
    }
    const m = location.pathname.match(/\/(?:event|evento)\/(\d+)/i);
    if (m) return parseInt(m[1], 10);
    const q = new URLSearchParams(location.search).get("eventId");
    return q ? parseInt(q, 10) : null;
  }

  function extractH2hOutcomeFromBetSlip() {
    const roots = document.querySelectorAll(
      '[class*="betslip" i], [class*="bet-slip" i], [class*="Betslip" i], [data-qa*="betslip" i]'
    );
    const scanRoots = roots.length ? [...roots] : [document.body];
    for (const root of scanRoots) {
      const text = root.innerText || "";
      if (!/APOSTAR|Fazer aposta|Confirmar|Cupom/i.test(text)) continue;

      const lineMatch = text.match(
        /Resultado Final[^\n]*?[—–-]\s*([^\n@]+?)\s*@/i
      );
      if (lineMatch) {
        const classified = classifyPick("Resultado Final", lineMatch[1].trim());
        if (classified.market === "h2h") return classified.outcome;
      }

      for (const line of text.split("\n")) {
        const trimmed = line.trim();
        if (/^Resultado Final/i.test(trimmed)) {
          const m = trimmed.match(/[—–-]\s*([1X2]|Empate)/i);
          if (m) {
            const classified = classifyPick("Resultado Final", m[1]);
            if (classified.market === "h2h") return classified.outcome;
          }
        }
      }
    }
    return null;
  }

  function renderAgainstModelBanner(alert) {
    const existing = document.getElementById("bolao-ai-against-banner");
    if (!alert) {
      existing?.remove();
      return;
    }
    let el = existing;
    if (!el) {
      el = document.createElement("div");
      el.id = "bolao-ai-against-banner";
      el.setAttribute("role", "alert");
      el.style.cssText =
        "position:fixed;top:0;left:0;right:0;z-index:2147483647;padding:14px 18px;" +
        "background:linear-gradient(180deg,#991b1b,#7f1d1d);color:#fff;" +
        "font:700 14px/1.45 system-ui,-apple-system,sans-serif;" +
        "box-shadow:0 6px 24px rgba(0,0,0,.45);border-bottom:2px solid #fca5a5;";
      document.body.prepend(el);
    }
    el.textContent = `⛔ Bolão AI — APOSTA CONTRA O MODELO: ${alert.message}`;
  }

  let _slipCheckKey = "";
  let _slipNotifiedKey = "";

  function pollBetSlipAgainstModel() {
    const eventId = extractEventIdFromUrl();
    const outcome = extractH2hOutcomeFromBetSlip();
    if (!eventId || !outcome) {
      _slipCheckKey = "";
      renderAgainstModelBanner(null);
      return;
    }

    const checkKey = `${eventId}:${outcome}`;
    if (checkKey === _slipCheckKey) return;
    _slipCheckKey = checkKey;

    chrome.storage.local.get(["bolao_api_key"], (items) => {
      const apiKey = items.bolao_api_key || "";
      chrome.runtime.sendMessage(
        {
          type: "API_CHECK_AGAINST_MODEL",
          apiKey,
          payload: {
            market: "h2h",
            outcome,
            superbet_event_id: eventId,
            phase: "friendly",
          },
        },
        (response) => {
          const alert = response?.data?.alert;
          renderAgainstModelBanner(alert);
          if (
            alert &&
            (alert.severity === "critical" || alert.severity === "high") &&
            _slipNotifiedKey !== checkKey
          ) {
            _slipNotifiedKey = checkKey;
            chrome.runtime.sendMessage({
              type: "SHOW_AGAINST_MODEL_NOTIFICATION",
              count: 1,
              message: alert.message,
            });
          }
        }
      );
    });
  }

  if (extractEventIdFromUrl()) {
    setInterval(pollBetSlipAgainstModel, 4000);
    setTimeout(pollBetSlipAgainstModel, 1200);
  }
})();
