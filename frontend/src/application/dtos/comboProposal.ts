/** Payload enviado à estação (POST /user/open-bets, source=bolao_proposal). */
export interface ComboProposalApiBody {
  id: string;
  superbet_event_id: number | null;
  event_name: string;
  home_team: string;
  away_team: string;
  picks: Array<{
    market: string;
    outcome: string;
    target_value?: string | null;
    model_prob?: number;
    market_odd?: number;
    expected_value?: number;
    edge_pp?: number;
  }>;
  stake: number;
  odds_placed: number;
  potential_return: number;
  source: "bolao_proposal";
  minute: number | null;
  model_source: "inplay_market_scan" | "kxl_patterns";
  combined_ev: number;
  combined_prob: number;
}

export interface ComboProposalLeg {
  market: string;
  outcome: string;
  label: string;
  targetValue?: string | null;
  modelProb: number;
  marketOdd: number;
  expectedValue: number;
  edgePp: number;
}

export interface ComboProposalContext {
  homeTeam: string;
  awayTeam: string;
  superbetEventId?: number | null;
  minute?: number | null;
  title: string;
  combinedOdd: number;
  combinedProb: number;
  combinedEv: number;
  suggestedStake: number;
  modelSource: "inplay_market_scan" | "kxl_patterns";
  qualified: boolean;
  disqualifyReason: string | null;
  legs: ComboProposalLeg[];
}

export interface RegisterComboProposalResult {
  id: string;
  message: string;
  status: string;
}
