import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api/client";

export interface HedgeSuggestion {
  market: string;
  outcome: string;
  odd_current: number;
  stake_suggested: number;
  guaranteed_return: number;
  net_if_original_wins: number;
  net_if_hedge_wins: number;
}

export interface BetAdvice {
  bet_id: string;
  event_name: string;
  market: string;
  outcome: string;
  stake: number;
  odds_placed: number;
  potential_return: number;
  prob_current: number;
  ev_remaining: number;
  action: "cashout" | "hedge" | "hold" | "shift";
  urgency: "critical" | "high" | "medium" | "low";
  reasoning: string;
  hedge?: HedgeSuggestion;
  cashout_value?: number;
}

export interface HedgeReport {
  advices: BetAdvice[];
  total_at_risk: number;
  total_potential: number;
  overall_action: string;
  summary: string;
}

/**
 * Hook que extrai o hedge_report da resposta do advice endpoint.
 * Não faz chamada própria — recebe os dados do advice já carregado.
 */
export function useHedgeReport(
  adviceData: { hedge_report?: HedgeReport | null } | undefined
): HedgeReport | null {
  if (!adviceData?.hedge_report) return null;
  return adviceData.hedge_report;
}

/**
 * Hook para buscar apostas abertas do usuário direto da API.
 * Útil para listagem geral fora do contexto de evento.
 */
export function useUserOpenBets() {
  return useQuery({
    queryKey: ["user-open-bets"],
    queryFn: () => apiFetch<{ bets: any[] }>("/user/open-bets"),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}
