import type { ComboProposalContext } from "@/application/dtos/comboProposal";
import type { InplayTicketCombo } from "@/domain/entities";

const MIN_MARKET_ODD = 1.01;
const MIN_COMBINED_EV = 0.0001;

export interface ComboProposalQualification {
  qualified: boolean;
  reason: string | null;
}

function legHasModelAndMarket(
  modelProb: number | null | undefined,
  marketOdd: number | null | undefined,
  expectedValue: number | null | undefined,
): boolean {
  if (marketOdd == null || marketOdd < MIN_MARKET_ODD) return false;
  if (modelProb == null || modelProb <= 0) return false;
  if (expectedValue != null && expectedValue <= 0) return false;
  return true;
}

/** In-play: pernas do market_scan com EV+ e odd Superbet. */
export function qualifyInplayCombo(combo: InplayTicketCombo): ComboProposalQualification {
  if (combo.legs.length < 1) {
    return { qualified: false, reason: "Combo sem pernas." };
  }
  if (combo.combinedEv <= MIN_COMBINED_EV) {
    return {
      qualified: false,
      reason: "EV combinado não positivo — modelo sem edge vs mercado.",
    };
  }
  for (const leg of combo.legs) {
    if (!legHasModelAndMarket(leg.modelProb, leg.marketOdd, leg.expectedValue)) {
      return {
        qualified: false,
        reason: `"${leg.label}": falta odd Superbet ou EV do modelo.`,
      };
    }
  }
  return { qualified: true, reason: null };
}

/** KXL: padrões históricos cruzados com odd Superbet e EV combo+. */
export function qualifyKxlCombo(ticket: {
  mainBets: Array<{
    label: string;
    hitRate: number;
    availableOnBook?: boolean;
    marketOdd?: number | null;
    expectedValue?: number | null;
  }>;
  comboOdd?: number | null;
  comboEv?: number | null;
  bookCoverage?: { mainAvailable: number; mainTotal: number } | null;
}): ComboProposalQualification {
  if (ticket.mainBets.length < 2) {
    return { qualified: false, reason: "Combo KXL incompleto." };
  }
  const coverage = ticket.bookCoverage;
  if (coverage && coverage.mainAvailable < coverage.mainTotal) {
    return {
      qualified: false,
      reason: `${coverage.mainAvailable}/${coverage.mainTotal} pernas na Superbet — aguarde captura de mercado.`,
    };
  }
  for (const leg of ticket.mainBets) {
    if (leg.availableOnBook === false) {
      return { qualified: false, reason: `"${leg.label}" não encontrado na Superbet.` };
    }
    if (!legHasModelAndMarket(leg.hitRate, leg.marketOdd, leg.expectedValue)) {
      return {
        qualified: false,
        reason: `"${leg.label}": falta cruzamento padrão KXL × odd de mercado.`,
      };
    }
  }
  if (ticket.comboOdd == null || ticket.comboOdd < MIN_MARKET_ODD) {
    return { qualified: false, reason: "Odd combinada da Superbet indisponível." };
  }
  if (ticket.comboEv == null || ticket.comboEv <= MIN_COMBINED_EV) {
    return {
      qualified: false,
      reason: "EV combo (padrão KXL × odd) não positivo.",
    };
  }
  return { qualified: true, reason: null };
}

/** Oportunidade única do strategy (hero / radar). */
export function qualifyStrategyOpportunity(opp: {
  modelProb: number;
  marketOdd: number;
  expectedValue: number;
}): ComboProposalQualification {
  if (opp.marketOdd < MIN_MARKET_ODD) {
    return { qualified: false, reason: "Odd de mercado indisponível na Superbet." };
  }
  if (opp.modelProb <= 0) {
    return { qualified: false, reason: "Probabilidade do modelo indisponível." };
  }
  if (opp.expectedValue <= MIN_COMBINED_EV) {
    return {
      qualified: false,
      reason: "EV não positivo — sem edge modelo × mercado.",
    };
  }
  return { qualified: true, reason: null };
}

export function qualifyComboProposal(proposal: ComboProposalContext): ComboProposalContext {
  if (proposal.legs.length < 2) {
    return { ...proposal, qualified: false, disqualifyReason: "Múltipla exige 2+ pernas." };
  }
  if (proposal.combinedEv <= MIN_COMBINED_EV) {
    return {
      ...proposal,
      qualified: false,
      disqualifyReason: "EV combinado não positivo — modelo sem edge vs mercado.",
    };
  }
  for (const leg of proposal.legs) {
    if (!legHasModelAndMarket(leg.modelProb, leg.marketOdd, leg.expectedValue)) {
      return {
        ...proposal,
        qualified: false,
        disqualifyReason: `"${leg.label}": falta odd Superbet ou EV do modelo.`,
      };
    }
  }
  return { ...proposal, qualified: true, disqualifyReason: null };
}

export function formatProposalBasis(proposal: ComboProposalContext): string {
  const evPct = (proposal.combinedEv * 100).toFixed(1);
  const probPct = (proposal.combinedProb * 100).toFixed(1);
  if (proposal.modelSource === "kxl_patterns") {
    return `KXL ${probPct}% × Superbet @${proposal.combinedOdd.toFixed(2)} · EV ${evPct}%`;
  }
  return `Modelo in-play ${probPct}% × mercado @${proposal.combinedOdd.toFixed(2)} · EV ${evPct}%`;
}
