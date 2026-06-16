import type { HalftimeAdjustReport, LiveMatchStats, SuperbetLiveAdvice, WcComboTicket } from "@/domain/entities";
import { qualifyKxlCombo } from "@/presentation/utils/comboProposalQualification";

type ComboLeg = WcComboTicket["mainBets"][number];

export type ComboLegRiskStatus = "pending" | "ok" | "at_risk" | "won" | "lost";

export interface ComboLegRisk {
  legIndex: number;
  label: string;
  status: ComboLegRiskStatus;
  observed: number | null;
  message: string;
}

export interface ComboHedgePlan {
  title: string;
  reason: string;
  action: "reserve_single" | "strategy_shield" | "reduce_exposure";
  reserveLeg?: ComboLeg;
  shield?: {
    title: string;
    reason: string;
    market?: string;
    outcome?: string;
    odd?: number;
  };
}

export interface DefensiveLiveContext {
  minute: number;
  periodLabel?: string | null;
  liveStats?: LiveMatchStats | null;
  halftimeReport?: HalftimeAdjustReport | null;
  shields?: NonNullable<SuperbetLiveAdvice["strategy"]>["shields"];
}

export interface DefensiveComboView {
  mode: "defensive";
  qualified: boolean;
  disqualifyReason: string | null;
  defensiveLegs: ComboLeg[];
  comboOdd: number | null;
  comboEv: number | null;
  combinedHitRate: number;
  suggestedStakePct: number;
  suggestedStakeValue: number;
  legRisks: ComboLegRisk[];
  hedgePlan: ComboHedgePlan | null;
  rules: string[];
}

const MIN_MARKET_ODD = 1.01;

function overThreshold(line: number): number {
  return line % 1 === 0.5 ? Math.floor(line) + 1 : line;
}

function underThreshold(line: number): number {
  return line % 1 === 0.5 ? Math.floor(line) : line;
}

function legPassesDefensiveFilter(leg: ComboLeg): boolean {
  if (leg.bookChecked && leg.availableOnBook === false) return false;
  if (leg.marketOdd == null || leg.marketOdd < MIN_MARKET_ODD) return false;
  if (leg.expectedValue != null && leg.expectedValue <= 0) return false;
  if (leg.hitRate <= 0) return false;
  return true;
}

function getObservedTotal(
  leg: ComboLeg,
  ctx: DefensiveLiveContext,
): number | null {
  const ht = ctx.halftimeReport?.frozenStats;
  const ls = ctx.liveStats;
  const minute = ctx.minute;

  if (leg.stat === "yellow_cards") {
    if (leg.period === "1h") {
      if (minute >= 45 && ht) return ht.homeYellows1h + ht.awayYellows1h;
      if (ls?.homeYellowCards != null && ls.awayYellowCards != null) {
        return ls.homeYellowCards + ls.awayYellowCards;
      }
    } else if (ls?.homeYellowCards != null && ls.awayYellowCards != null) {
      return ls.homeYellowCards + ls.awayYellowCards;
    }
    return null;
  }

  if (leg.stat === "corners") {
    if (leg.period === "1h") {
      if (minute >= 45 && ht) return ht.homeCorners1h + ht.awayCorners1h;
      if (ls?.homeCorners != null && ls.awayCorners != null) {
        return ls.homeCorners + ls.awayCorners;
      }
    } else if (ls?.homeCorners != null && ls.awayCorners != null) {
      return ls.homeCorners + ls.awayCorners;
    }
    return null;
  }

  if (leg.stat === "shots_on_target") {
    if (ls?.homeShotsOnTarget != null && ls.awayShotsOnTarget != null) {
      return ls.homeShotsOnTarget + ls.awayShotsOnTarget;
    }
  }

  return null;
}

function periodEnded(leg: ComboLeg, minute: number): boolean {
  if (leg.period === "1h") return minute >= 45;
  return minute >= 90;
}

function minutesRemaining(leg: ComboLeg, minute: number): number {
  if (leg.period === "1h") return Math.max(0, 45 - minute);
  return Math.max(0, 90 - minute);
}

export function assessComboLegRisk(leg: ComboLeg, legIndex: number, ctx: DefensiveLiveContext): ComboLegRisk {
  const observed = getObservedTotal(leg, ctx);
  const line = leg.line;

  if (line == null || observed == null) {
    return {
      legIndex,
      label: leg.label,
      status: "pending",
      observed,
      message:
        ctx.minute < 10
          ? "Aguardando dados ao vivo para monitorar esta perna."
          : "Métrica ao vivo indisponível — acompanhe manualmente.",
    };
  }

  const ended = periodEnded(leg, ctx.minute);
  const direction = leg.direction.toLowerCase();

  if (direction === "over") {
    const need = overThreshold(line);
    if (observed >= need) {
      return {
        legIndex,
        label: leg.label,
        status: "won",
        observed,
        message: ended
          ? `Perna confirmada: ${observed} ≥ ${need} (Over ${line}).`
          : `Over ${line} já bateu (${observed}) — combo segue vivo.`,
      };
    }
    if (ended) {
      return {
        legIndex,
        label: leg.label,
        status: "lost",
        observed,
        message: `1ª perna falhou: ${observed} < ${need} (Over ${line}).`,
      };
    }
    const minsLeft = minutesRemaining(leg, ctx.minute);
    const gap = need - observed;
    if (gap >= 2 && minsLeft <= 20) {
      return {
        legIndex,
        label: leg.label,
        status: "at_risk",
        observed,
        message: `Risco alto: faltam ${gap} para Over ${line} com ~${minsLeft} min.`,
      };
    }
    return {
      legIndex,
      label: leg.label,
      status: "ok",
      observed,
      message: `Em jogo: ${observed}/${need} para Over ${line} · ~${minsLeft} min restantes.`,
    };
  }

  if (direction === "under") {
    const maxOk = underThreshold(line);
    if (ended) {
      const won = observed <= maxOk;
      return {
        legIndex,
        label: leg.label,
        status: won ? "won" : "lost",
        observed,
        message: won
          ? `Perna confirmada: ${observed} ≤ ${maxOk} (Under ${line}).`
          : `Perna falhou: ${observed} > ${maxOk} (Under ${line}).`,
      };
    }
    if (observed > maxOk) {
      return {
        legIndex,
        label: leg.label,
        status: "lost",
        observed,
        message: `Under ${line} já estourou (${observed} > ${maxOk}).`,
      };
    }
    return {
      legIndex,
      label: leg.label,
      status: "ok",
      observed,
      message: `Under ${line} ok por enquanto (${observed} ≤ ${maxOk}).`,
    };
  }

  return {
    legIndex,
    label: leg.label,
    status: "pending",
    observed,
    message: "Direção não monitorada automaticamente.",
  };
}

function buildHedgePlan(
  ticket: WcComboTicket,
  legRisks: ComboLegRisk[],
  ctx: DefensiveLiveContext,
): ComboHedgePlan | null {
  const first = legRisks[0];
  if (!first || (first.status !== "at_risk" && first.status !== "lost")) return null;

  const reserve = ticket.reserveBets.find(legPassesDefensiveFilter);
  if (reserve) {
    return {
      title: first.status === "lost" ? "Plano B — reserva" : "Proteção — perna 1 em risco",
      reason:
        first.status === "lost"
          ? "A 1ª perna do combo falhou. Não empilhe mais no bilhete original — use a reserva como single."
          : "A 1ª perna está atrasada. Considere reserva EV+ ou reduza stake antes do intervalo.",
      action: "reserve_single",
      reserveLeg: reserve,
    };
  }

  const shield = ctx.shields?.find(
    (s) =>
      s.action === "hedge_opcional" ||
      s.action === "cashout" ||
      s.action === "cashout_parcial",
  );
  if (shield) {
    return {
      title: "Proteção sugerida",
      reason: shield.reason,
      action: "strategy_shield",
      shield: {
        title: shield.title,
        reason: shield.reason,
        market: shield.market,
        outcome: shield.outcome,
        odd: shield.odd,
      },
    };
  }

  return {
    title: "Reduzir exposição",
    reason:
      "Sem reserva EV+ na casa. Não dobre o combo — aguarde intervalo ou cash-out parcial se tiver aposta aberta.",
    action: "reduce_exposure",
  };
}

export function buildDefensiveComboView(
  ticket: WcComboTicket,
  ctx?: DefensiveLiveContext | null,
): DefensiveComboView | null {
  if (!ticket.available || ticket.mainBets.length < 2) return null;

  const defensiveLegs = ticket.mainBets.filter(legPassesDefensiveFilter);
  const comboOdd =
    defensiveLegs.length >= 2
      ? defensiveLegs.reduce((acc, leg) => acc * (leg.marketOdd ?? 1), 1)
      : null;
  const combinedHitRate =
    defensiveLegs.length >= 2
      ? defensiveLegs.reduce((acc, leg) => acc * leg.hitRate, 1)
      : 0;
  const comboEv =
    comboOdd != null && comboOdd > 1 ? combinedHitRate * comboOdd - 1 : null;

  const defensiveTicket = {
    ...ticket,
    mainBets: defensiveLegs,
    comboOdd: comboOdd != null ? Math.round(comboOdd * 1000) / 1000 : null,
    comboEv: comboEv != null ? Math.round(comboEv * 10000) / 10000 : null,
  };

  const baseQual = qualifyKxlCombo(defensiveTicket);
  const qualified = baseQual.qualified && defensiveLegs.length >= 2;

  const legRisks = ctx
    ? defensiveLegs.map((leg, idx) => assessComboLegRisk(leg, idx, ctx))
    : [];

  const hedgePlan =
    ctx && legRisks.length > 0 ? buildHedgePlan(ticket, legRisks, ctx) : null;

  const rules = [
    "Modo defensivo: só pernas com odd Superbet e EV positivo (modelo KXL × mercado).",
    "Stake máxima sugerida: metade do combo KXL padrão — preserve banca.",
    "Se a 1ª perna falhar, use reserva single EV+ — não empilhe no mesmo bilhete.",
    "Reavalie após intervalo ou gol; hedge automático quando perna 1 estiver em risco.",
  ];

  let disqualifyReason = baseQual.reason;
  if (defensiveLegs.length < ticket.mainBets.length && !qualified) {
    disqualifyReason =
      disqualifyReason ??
      `${ticket.mainBets.length - defensiveLegs.length} perna(s) sem EV+ na Superbet — combo defensivo incompleto.`;
  }

  const stakeScale = qualified ? 0.5 : 0.35;
  const suggestedStakePct = Math.round(ticket.suggestedStakePct * stakeScale * 10) / 10;
  const suggestedStakeValue = Math.round(ticket.suggestedStakeValue * stakeScale);

  return {
    mode: "defensive",
    qualified,
    disqualifyReason: qualified ? null : disqualifyReason,
    defensiveLegs,
    comboOdd: defensiveTicket.comboOdd,
    comboEv: defensiveTicket.comboEv,
    combinedHitRate,
    suggestedStakePct,
    suggestedStakeValue,
    legRisks,
    hedgePlan,
    rules,
  };
}
