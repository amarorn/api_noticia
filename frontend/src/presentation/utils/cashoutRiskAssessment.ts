/**
 * Avaliação de risco de cash-out (espelho do backend cashout_risk_advisor.py).
 */

export type LegLiveStatus = "won" | "lost" | "critical" | "at_risk" | "pending" | "ok";
export type RiskAction = "exit_now" | "protect_stake" | "consider_exit" | "hold" | "dead";

export interface BetPickLike {
  market: string;
  outcome: string;
  label?: string;
  targetValue?: string | null;
}

export interface LegRiskAssessment {
  market: string;
  outcome: string;
  label: string;
  status: LegLiveStatus;
  reason: string;
}

export interface CashoutRiskAssessment {
  betId: string;
  action: RiskAction;
  severity: "critical" | "high" | "medium" | "low";
  title: string;
  message: string;
  stake: number;
  cashoutValue: number | null;
  potentialReturn: number;
  cashoutPctOfStake: number | null;
  cashoutPctOfPotential: number | null;
  legs: LegRiskAssessment[];
  criticalLegs: string[];
  alert: boolean;
}

export interface LiveScoreContext {
  homeScore: number;
  awayScore: number;
  minute?: number;
  htHome?: number | null;
  htAway?: number | null;
  periodLabel?: string | null;
  homeCorners?: number | null;
  awayCorners?: number | null;
  homeCards?: number | null;
  awayCards?: number | null;
}

export interface OpenBetLike {
  id: string;
  stake: number;
  oddsPlaced: number;
  potentialReturn: number;
  cashoutValue?: number | null;
  ticketCode?: string | null;
  picks: BetPickLike[];
}

const LINE_RE =
  /(?:mais|menos|over|under|acima|abaixo)\s*(?:de\s*)?(\d+[.,]?\d*)/i;
const MARKET_LINE_RE = /(?:^|_)(?:over|under|totals)_(\d+)_(\d+)/i;

function maxGoalsForUnder(line: number): number {
  return Math.floor(line);
}

function minGoalsForOver(line: number): number {
  return Math.floor(line) + 1;
}

function normalizeTotalsPick(
  market: string,
  outcome: string,
  targetValue: string | null | undefined,
  label: string,
): { direction: "over" | "under" | null; line: number | null; isFirstHalf: boolean } {
  const mkt = market.toLowerCase();
  const out = outcome.toLowerCase();
  const lbl = label || "";
  const blob = `${mkt} ${out} ${targetValue ?? ""} ${lbl}`;
  const is1h =
    /^(1h|2h|1t|2t)_/i.test(mkt) ||
    lbl.toLowerCase().includes("1º tempo") ||
    lbl.toLowerCase().includes("1o tempo");

  const mm = mkt.replace(/-/g, "_").match(MARKET_LINE_RE);
  if (mm) {
    const line = parseFloat(`${mm[1]}.${mm[2]}`);
    if (["yes", "over", "sim"].includes(out)) return { direction: "over", line, isFirstHalf: is1h };
    if (["no", "under", "não", "nao"].includes(out)) return { direction: "under", line, isFirstHalf: is1h };
  }

  const lm = blob.match(LINE_RE);
  if (lm) {
    const line = parseFloat(lm[1].replace(",", "."));
    const direction = /menos|under|abaixo/i.test(lm[0]) ? "under" : "over";
    return { direction, line, isFirstHalf: is1h };
  }

  return { direction: null, line: null, isFirstHalf: is1h };
}

function evaluateH2HSettled(
  outcome: string,
  homeScore: number,
  awayScore: number,
): boolean | null {
  const o = outcome.toLowerCase();
  if (["1", "home"].includes(o)) return homeScore > awayScore;
  if (["2", "away"].includes(o)) return awayScore > homeScore;
  if (["x", "draw"].includes(o)) return homeScore === awayScore;
  return null;
}

function parseLineValue(raw: string | null | undefined): number | null {
  if (!raw) return null;
  const n = parseFloat(String(raw).replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

function evaluateUnderOverLive(
  current: number,
  line: number,
  direction: "over" | "under",
  unit: string,
  scope: string,
  minute: number,
): { status: LegLiveStatus; reason: string } | null {
  if (direction === "under") {
    const limit = maxGoalsForUnder(line);
    if (current >= limit + 1) {
      return { status: "lost", reason: `Acima de ${line} ${unit} ${scope}.` };
    }
    if (current === limit) {
      return {
        status: "critical",
        reason: `${current} ${unit} — um a mais mata (${scope}).`,
      };
    }
    if (current === limit - 1 && minute >= 60) {
      return {
        status: "at_risk",
        reason: `Perto do limite (${current} ${unit}, max ${limit}).`,
      };
    }
  } else {
    const need = minGoalsForOver(line);
    if (current >= need) {
      return { status: "won", reason: `Over ${line} ${unit} batido.` };
    }
    if (need - current === 1 && minute >= 70) {
      return { status: "at_risk", reason: `Falta 1 com pouco tempo (${minute}').` };
    }
  }
  return null;
}

export function evaluateLegLive(
  pick: BetPickLike,
  ctx: LiveScoreContext,
): LegRiskAssessment {
  const market = pick.market || "";
  const outcome = pick.outcome || "";
  const label = pick.label || pick.outcome || market;
  const { homeScore, awayScore, minute = 0, htHome, htAway, periodLabel } = ctx;
  const homeCorners = ctx.homeCorners ?? null;
  const awayCorners = ctx.awayCorners ?? null;
  const homeCards = ctx.homeCards ?? null;
  const awayCards = ctx.awayCards ?? null;
  const mktL = market.toLowerCase();
  const lblL = label.toLowerCase();

  if (mktL === "corners_total" || lblL.includes("escanteio")) {
    let line = parseLineValue(pick.targetValue);
    if (line == null) {
      const norm = normalizeTotalsPick(market, outcome, pick.targetValue, label);
      line = norm.line;
    }
    if (line != null && homeCorners != null && awayCorners != null) {
      const total = homeCorners + awayCorners;
      const direction =
        outcome.toLowerCase() === "over" || outcome.toLowerCase() === "yes"
          ? "over"
          : "under";
      const live = evaluateUnderOverLive(
        total,
        line,
        direction,
        "escanteios",
        "no jogo",
        minute,
      );
      if (live) return { market, outcome, label, ...live };
    }
  }

  if ((mktL === "cards_total" || mktL === "other") && (lblL.includes("cartão") || lblL.includes("cartao"))) {
    let line = parseLineValue(pick.targetValue);
    if (line == null) {
      const norm = normalizeTotalsPick(market, outcome, pick.targetValue, label);
      line = norm.line;
    }
    if (line != null && homeCards != null && awayCards != null) {
      const total = homeCards + awayCards;
      let direction: "over" | "under" = lblL.includes("mais") ? "over" : "under";
      if (["over", "yes", "sim"].includes(outcome.toLowerCase())) direction = "over";
      if (["under", "no", "não", "nao"].includes(outcome.toLowerCase())) direction = "under";
      const live = evaluateUnderOverLive(total, line, direction, "cartões", "no jogo", minute);
      if (live) return { market, outcome, label, ...live };
    }
  }

  const mktLH2h = market.toLowerCase();
  if (
    mktLH2h === "h2h" ||
    mktLH2h === "moneyline" ||
    mktLH2h === "f5_moneyline" ||
    mktLH2h === "inning_1x2" ||
    ["1", "2", "x"].includes(mktLH2h)
  ) {
    const side = ["1", "2", "x"].includes(mktLH2h) ? mktLH2h : outcome.toLowerCase();
    const settled = evaluateH2HSettled(side, homeScore, awayScore);
    if (settled === true) return { market, outcome, label, status: "won", reason: "Perna já ganha." };
    if (settled === false) return { market, outcome, label, status: "lost", reason: "Perna perdida." };
  }

  if (
    mktL === "total_runs" ||
    mktL === "f5_total" ||
    mktL === "inning_total" ||
    mktL === "team_total_runs"
  ) {
    const outMatch = outcome.match(/^(over|under)_(\d+)_(\d+)$/i);
    let direction: "over" | "under" | null = null;
    let line: number | null = null;
    if (outMatch) {
      direction = outMatch[1].toLowerCase() as "over" | "under";
      line = parseFloat(`${outMatch[2]}.${outMatch[3]}`);
    } else {
      const norm = normalizeTotalsPick(market, outcome, pick.targetValue, label);
      direction = norm.direction;
      line = norm.line;
    }
    if (direction && line != null) {
      const scope =
        mktL === "f5_total"
          ? "no F5"
          : mktL === "team_total_runs"
            ? "do time"
            : "no jogo";
      const teamSide = outcome.startsWith("home_") ? "home" : outcome.startsWith("away_") ? "away" : null;
      const current =
        mktL === "team_total_runs" && teamSide === "home"
          ? homeScore
          : mktL === "team_total_runs" && teamSide === "away"
            ? awayScore
            : homeScore + awayScore;
      const lateInning = minute >= 70;
      const live = evaluateUnderOverLive(
        current,
        line,
        direction,
        "corridas",
        scope,
        lateInning ? 75 : minute,
      );
      if (live) return { market, outcome, label, ...live };
    }
  }

  const { direction, line, isFirstHalf } = normalizeTotalsPick(
    market,
    outcome,
    pick.targetValue,
    label,
  );

  if (direction && line != null) {
    const period = (periodLabel || "").toLowerCase();
    const inFirstHalf = minute <= 45 || period.startsWith("1");
    let goals: number;
    let scope: string;
    if (isFirstHalf && htHome != null && htAway != null) {
      goals = htHome + htAway;
      scope = "no 1º tempo";
    } else if (isFirstHalf && inFirstHalf) {
      goals = homeScore + awayScore;
      scope = "no 1º tempo";
    } else {
      goals = homeScore + awayScore;
      scope = "no jogo";
    }

    if (direction === "under") {
      const limit = maxGoalsForUnder(line);
      if (goals >= limit + 1) {
        return { market, outcome, label, status: "lost", reason: `Acima de ${line} gols ${scope}.` };
      }
      if (goals === limit) {
        return {
          market,
          outcome,
          label,
          status: "critical",
          reason: `${goals} gols — um gol a mais mata (${scope}).`,
        };
      }
      if (goals === limit - 1 && minute >= 60) {
        return {
          market,
          outcome,
          label,
          status: "at_risk",
          reason: `Perto do limite (${goals} gols, max ${limit}).`,
        };
      }
    } else {
      const need = minGoalsForOver(line);
      if (goals >= need) {
        return { market, outcome, label, status: "won", reason: `Over ${line} batido.` };
      }
      if (need - goals === 1 && minute >= 70) {
        return {
          market,
          outcome,
          label,
          status: "at_risk",
          reason: `Falta 1 gol com pouco tempo (${minute}').`,
        };
      }
    }
  }

  return { market, outcome, label, status: "pending", reason: "" };
}

export function buildCashoutLiveContext(params: {
  currentScore: string | null;
  minute?: number;
  htHome?: number | null;
  htAway?: number | null;
  periodLabel?: string | null;
  liveStats?: {
    homeCorners?: number | null;
    awayCorners?: number | null;
    homeYellowCards?: number | null;
    awayYellowCards?: number | null;
    homeRedCards?: number | null;
    awayRedCards?: number | null;
  } | null;
}): LiveScoreContext {
  const { home, away } = parseScore(params.currentScore);
  const ls = params.liveStats;
  const homeCards =
    ls != null ? (ls.homeYellowCards ?? 0) + (ls.homeRedCards ?? 0) : null;
  const awayCards =
    ls != null ? (ls.awayYellowCards ?? 0) + (ls.awayRedCards ?? 0) : null;
  return {
    homeScore: home,
    awayScore: away,
    minute: params.minute ?? 0,
    htHome: params.htHome,
    htAway: params.htAway,
    periodLabel: params.periodLabel,
    homeCorners: ls?.homeCorners ?? null,
    awayCorners: ls?.awayCorners ?? null,
    homeCards,
    awayCards,
  };
}

export function parseScore(score: string | null | undefined): { home: number; away: number } {
  if (!score) return { home: 0, away: 0 };
  const parts = score.split(/[x×:\-]/i);
  if (parts.length !== 2) return { home: 0, away: 0 };
  const home = parseInt(parts[0].trim(), 10);
  const away = parseInt(parts[1].trim(), 10);
  return {
    home: Number.isFinite(home) ? home : 0,
    away: Number.isFinite(away) ? away : 0,
  };
}

export function assessCashoutRisk(
  bet: OpenBetLike,
  ctx: LiveScoreContext,
  minProtectPct = 0.5,
): CashoutRiskAssessment {
  const stake = bet.stake;
  const potential = bet.potentialReturn || stake * bet.oddsPlaced;
  const cashoutValue =
    bet.cashoutValue != null && bet.cashoutValue > 0 ? bet.cashoutValue : null;

  const legs = (bet.picks.length ? bet.picks : [{ market: "h2h", outcome: "X" }]).map((p) =>
    evaluateLegLive(p, ctx),
  );

  const critical = legs.filter((l) => l.status === "critical").map((l) => l.label);
  const lost = legs.filter((l) => l.status === "lost");
  const atRisk = legs.filter((l) => l.status === "at_risk").map((l) => l.label);

  const pctStake = cashoutValue != null && stake > 0 ? cashoutValue / stake : null;
  const pctPot = cashoutValue != null && potential > 0 ? cashoutValue / potential : null;

  const base = {
    betId: bet.id,
    stake,
    cashoutValue,
    potentialReturn: potential,
    cashoutPctOfStake: pctStake,
    cashoutPctOfPotential: pctPot,
    legs,
    criticalLegs: critical,
  };

  if (lost.length > 0) {
    return {
      ...base,
      action: "dead",
      severity: "critical",
      title: "Bilhete perdido",
      message: "Uma ou mais pernas já falharam. Cash-out tende a zero.",
      alert: false,
    };
  }

  if (critical.length > 0 && cashoutValue != null && cashoutValue >= stake) {
    return {
      ...base,
      action: "exit_now",
      severity: "critical",
      title: "Cash-out recomendado — perna em risco",
      message: `A casa oferece R$ ${cashoutValue.toFixed(2)} (lucro). Perna(s) crítica(s): ${critical.slice(0, 2).join(", ")}. Um gol pode zerar o bilhete.`,
      alert: true,
    };
  }

  if (
    critical.length > 0 &&
    cashoutValue != null &&
    pctStake != null &&
    pctStake >= minProtectPct
  ) {
    return {
      ...base,
      action: "protect_stake",
      severity: "high",
      title: "Proteja parte do valor",
      message: `Cash-out R$ ${cashoutValue.toFixed(2)} (${Math.round(pctStake * 100)}% da aposta). Risco em: ${critical.slice(0, 2).join(", ")}. Melhor recuperar parte do que perder tudo.`,
      alert: true,
    };
  }

  if (critical.length > 0 && cashoutValue != null && cashoutValue > 0) {
    return {
      ...base,
      action: "consider_exit",
      severity: "high",
      title: "Risco alto no bilhete",
      message: `Perna(s) a um passo de perder: ${critical.slice(0, 2).join(", ")}. Cash-out: R$ ${cashoutValue.toFixed(2)}.`,
      alert: true,
    };
  }

  if (atRisk.length > 0 && cashoutValue != null && cashoutValue >= stake * 1.05) {
    return {
      ...base,
      action: "consider_exit",
      severity: "medium",
      title: "Considere cash-out",
      message: `Lucro disponível (R$ ${cashoutValue.toFixed(2)}) com pressão em: ${atRisk.slice(0, 2).join(", ")}.`,
      alert: true,
    };
  }

  const odds = bet.oddsPlaced || 1;
  if (
    cashoutValue != null &&
    cashoutValue > 0 &&
    pctStake != null &&
    pctStake < 0.45 &&
    odds >= 8 &&
    critical.length === 0
  ) {
    return {
      ...base,
      action: "consider_exit",
      severity: "high",
      title: "Cash-out caindo — zera fácil",
      message: `Cash-out R$ ${cashoutValue.toFixed(2)} (${Math.round(pctStake * 100)}% da aposta) num bilhete @ ${odds.toFixed(1)}. Recupere antes de perder tudo.`,
      alert: true,
    };
  }

  if (
    cashoutValue != null &&
    stake > 0 &&
    cashoutValue >= stake * 1.08 &&
    critical.length === 0 &&
    atRisk.length === 0
  ) {
    return {
      ...base,
      action: "consider_exit",
      severity: "medium",
      title: "Garanta o lucro",
      message: `Cash-out R$ ${cashoutValue.toFixed(2)} — acima da aposta (R$ ${stake.toFixed(2)}). Considere travar o ganho.`,
      alert: true,
    };
  }

  return {
    ...base,
    action: "hold",
    severity: "low",
    title: "Sem alerta de saída",
    message: "Nenhuma perna crítica ou cash-out indisponível.",
    alert: false,
  };
}

export function formatBrl(value: number): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}
