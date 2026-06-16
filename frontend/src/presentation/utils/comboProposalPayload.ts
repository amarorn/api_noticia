import type {
  ComboProposalApiBody,
  ComboProposalContext,
  ComboProposalLeg,
} from "@/application/dtos/comboProposal";
import type { InplayTicketCombo, InplayTicketLeg } from "@/domain/entities";
import {
  qualifyInplayCombo,
  qualifyKxlCombo,
  qualifyStrategyOpportunity,
} from "@/presentation/utils/comboProposalQualification";

export type { ComboProposalApiBody, ComboProposalContext, ComboProposalLeg };

function legFromInplay(leg: InplayTicketLeg): ComboProposalLeg {
  return {
    market: leg.market,
    outcome: leg.outcome,
    label: leg.label,
    modelProb: leg.modelProb,
    marketOdd: leg.marketOdd,
    expectedValue: leg.expectedValue,
    edgePp: leg.edgePp,
  };
}

/** Converte perna KXL (pré-jogo) para payload da estação. */
export function legFromKxlPattern(leg: {
  label: string;
  hitRate: number;
  stat?: string;
  period?: string;
  direction?: string;
  line?: number | null;
  superbetMarket?: string | null;
  superbetPick?: string | null;
  marketOdd?: number | null;
  expectedValue?: number | null;
  edgePp?: number | null;
}): ComboProposalLeg {
  const market = leg.superbetMarket ?? `${leg.stat ?? "pattern"}_${leg.period ?? "ft"}`;
  const outcome = leg.superbetPick ?? leg.direction ?? "yes";
  const marketOdd = leg.marketOdd ?? 0;
  const modelProb = leg.hitRate;
  const expectedValue =
    leg.expectedValue ?? (marketOdd > 1 ? modelProb * marketOdd - 1 : 0);
  const edgePp =
    leg.edgePp ??
    (marketOdd > 1 ? (modelProb - 1 / marketOdd) * 100 : 0);
  return {
    market,
    outcome,
    label: leg.label,
    targetValue: leg.line != null ? String(leg.line) : null,
    modelProb,
    marketOdd,
    expectedValue,
    edgePp,
  };
}

export function buildProposalFromInplayCombo(
  combo: InplayTicketCombo,
  ctx: Omit<
    ComboProposalContext,
    | "title"
    | "combinedOdd"
    | "combinedProb"
    | "combinedEv"
    | "suggestedStake"
    | "modelSource"
    | "qualified"
    | "disqualifyReason"
    | "legs"
  >,
): ComboProposalContext {
  const qualification = qualifyInplayCombo(combo);
  return {
    ...ctx,
    title: combo.title,
    combinedOdd: combo.combinedOdd,
    combinedProb: combo.combinedProb,
    combinedEv: combo.combinedEv,
    suggestedStake: combo.suggestedStakeValue,
    modelSource: "inplay_market_scan",
    qualified: qualification.qualified,
    disqualifyReason: qualification.reason,
    legs: combo.legs.map(legFromInplay),
  };
}

/** Palpite simples ou oportunidade do painel “O que fazer agora”. */
export function buildProposalFromStrategyOpportunity(
  opp: {
    label: string;
    market: string;
    outcome: string;
    modelProb: number;
    marketOdd: number;
    expectedValue: number;
    edgePp: number;
    suggestedStakeValue?: number;
  },
  ctx: Omit<
    ComboProposalContext,
    | "title"
    | "combinedOdd"
    | "combinedProb"
    | "combinedEv"
    | "suggestedStake"
    | "modelSource"
    | "qualified"
    | "disqualifyReason"
    | "legs"
  >,
): ComboProposalContext {
  const qualification = qualifyStrategyOpportunity(opp);
  const leg: ComboProposalLeg = {
    market: opp.market,
    outcome: opp.outcome,
    label: opp.label,
    modelProb: opp.modelProb,
    marketOdd: opp.marketOdd,
    expectedValue: opp.expectedValue,
    edgePp: opp.edgePp,
  };
  return {
    ...ctx,
    title: opp.label,
    combinedOdd: opp.marketOdd,
    combinedProb: opp.modelProb,
    combinedEv: opp.expectedValue,
    suggestedStake: opp.suggestedStakeValue ?? Math.max(10, Math.round(opp.expectedValue * 100)),
    modelSource: "inplay_market_scan",
    qualified: qualification.qualified,
    disqualifyReason: qualification.reason,
    legs: [leg],
  };
}

export function buildProposalFromInplayLeg(
  leg: InplayTicketLeg,
  ctx: Omit<
    ComboProposalContext,
    | "title"
    | "combinedOdd"
    | "combinedProb"
    | "combinedEv"
    | "suggestedStake"
    | "modelSource"
    | "qualified"
    | "disqualifyReason"
    | "legs"
  >,
  title?: string,
): ComboProposalContext {
  return buildProposalFromInplayCombo(
    {
      id: `${leg.market}-${leg.outcome}`,
      title: title ?? leg.label,
      legs: [leg],
      combinedOdd: leg.marketOdd,
      combinedProb: leg.modelProb,
      combinedEv: leg.expectedValue,
      suggestedStakePct: leg.suggestedStakePct ?? 1,
      suggestedStakeValue: leg.suggestedStakeValue ?? 10,
      notes: [],
    },
    ctx,
  );
}

export function buildProposalFromKxlTicket(
  ticket: {
    title?: string | null;
    mainBets: Array<Parameters<typeof legFromKxlPattern>[0]>;
    comboOdd?: number | null;
    comboEv?: number | null;
    suggestedStakeValue: number;
    bookCoverage?: { mainAvailable: number; mainTotal: number } | null;
  },
  ctx: Omit<
    ComboProposalContext,
    | "title"
    | "combinedOdd"
    | "combinedProb"
    | "combinedEv"
    | "suggestedStake"
    | "modelSource"
    | "qualified"
    | "disqualifyReason"
    | "legs"
  >,
): ComboProposalContext {
  const qualification = qualifyKxlCombo(ticket);
  const combinedOdd =
    ticket.comboOdd ??
    ticket.mainBets.reduce((acc, leg) => acc * (leg.marketOdd ?? 1), 1);
  const combinedProb = ticket.mainBets.reduce((acc, leg) => acc * leg.hitRate, 1);
  const combinedEv =
    ticket.comboEv ?? (combinedOdd > 1 ? combinedProb * combinedOdd - 1 : 0);
  return {
    ...ctx,
    title: ticket.title ?? `${ctx.homeTeam} × ${ctx.awayTeam}`,
    combinedOdd,
    combinedProb,
    combinedEv,
    suggestedStake: ticket.suggestedStakeValue,
    modelSource: "kxl_patterns",
    qualified: qualification.qualified,
    disqualifyReason: qualification.reason,
    legs: ticket.mainBets.map(legFromKxlPattern),
  };
}

export function buildProposalApiBody(proposal: ComboProposalContext): ComboProposalApiBody {
  if (!proposal.qualified) {
    throw new Error(proposal.disqualifyReason ?? "Proposta não qualificada (modelo × mercado).");
  }
  const stake = Math.max(1, Math.round(proposal.suggestedStake));
  const odds = Math.max(1.51, proposal.combinedOdd);
  return {
    id: `proposal-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    superbet_event_id: proposal.superbetEventId ?? null,
    event_name: `${proposal.homeTeam} × ${proposal.awayTeam}`,
    home_team: proposal.homeTeam,
    away_team: proposal.awayTeam,
    picks: proposal.legs.map((leg) => ({
      market: leg.market,
      outcome: leg.outcome,
      target_value: leg.targetValue ?? leg.label,
      model_prob: Number(leg.modelProb.toFixed(4)),
      market_odd: Number(leg.marketOdd.toFixed(3)),
      expected_value: Number(leg.expectedValue.toFixed(4)),
      edge_pp: Number(leg.edgePp.toFixed(2)),
    })),
    stake,
    odds_placed: Number(odds.toFixed(2)),
    potential_return: Number((stake * odds).toFixed(2)),
    source: "bolao_proposal",
    minute: proposal.minute ?? null,
    model_source: proposal.modelSource,
    combined_ev: Number(proposal.combinedEv.toFixed(4)),
    combined_prob: Number(proposal.combinedProb.toFixed(4)),
  };
}
