import { useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSuperbetEventUseCase, getSuperbetLiveAdviceUseCase } from "@/application/container";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import type { LiveAdviceScoreTick } from "@/presentation/hooks/useLiveAdviceQueries";

const STALE_MS = 8_000;
/** Superbet direto (sem cache server-side): manter 1min30s para balancear
 *  freshnesss com rate-limit. O cronômetro na UI reflete esse intervalo. */
const ODDS_POLL_MS = 90_000;
const SCORE_POLL_MS = 90_000;

function fallbackAdviceFromScore(
  score: LiveAdviceScoreTick | null | undefined,
  eventId: number,
): SuperbetLiveAdvice | undefined {
  if (!score) return undefined;
  return {
    homeTeam: score.homeTeam,
    awayTeam: score.awayTeam,
    minute: score.minute ?? 0,
    currentScore: score.currentScore,
    periodLabel: score.periodLabel,
    status: score.status,
    isFinished: !score.isLive,
    isLive: score.isLive,
    superbetStale: true,
    scoreStale: {
      scoreStale: false,
      warnings: ["Advice ainda nao carregado; exibindo snapshot leve do evento."],
    },
    superbetEventId: eventId,
    betradarId: null,
    capturedAt: score.capturedAt,
    rawMarketCount: score.rawMarketCount,
    h2hOdds: score.h2hOdds ?? {},
    h2hImplied: {},
    h2hOverround: null,
    generosityProbs: {},
    confidence: null,
    marketBenchmark: null,
    strategy: {
      posture: "neutro",
      maxNewExposurePct: 0,
      maxNewExposureValue: 0,
      opportunityCount: 0,
      strongOpportunityCount: 0,
      minEdgeThreshold: 0.04,
      waitReason: "Aguardando cálculo do modelo in-play.",
      watchList: [],
      marketScan: [],
      opportunities: [],
      shields: [
        {
          action: "aguardar",
          priority: "media",
          title: "Modelo carregando",
          reason: "Snapshot do jogo disponível; odds/EV ainda estão carregando.",
        },
      ],
      rules: [],
      cashout: null,
      patternAccuracy: null,
      comboTicket: null,
    },
    cashout: null,
    aportes: [],
    bttsOdds: {},
    nextGoalOdds: {},
    analysisCoverage: null,
    inplaySummary: {
      probFinalHome: 0,
      probFinalDraw: 0,
      probFinalAway: 0,
    },
    hedgeReport: null,
    againstModelAlerts: [],
    betGuardrails: null,
    liveStats: null,
    scorealarm: null,
    trendReport: null,
    halfTickets: null,
    viable2hMarkets: null,
    superMultipla: null,
    matchContext: null,
    optimizedTickets: undefined,
  } as unknown as SuperbetLiveAdvice;
}

/**
 * Hook leve para a tela /aovivo-v2.
 * Usa somente snapshot do evento + advice fast=true. Evita o full advice, que carrega
 * contexto pesado como scorealarm completo, hedge, trend e análises auxiliares.
 */
export function useLiveOperationalData(
  eventId: number,
  bankroll = 1000,
  kickoff?: string | null,
  phase = "group",
) {
  const enabled = Number.isFinite(eventId) && eventId > 0;
  const kickoffKey = kickoff ?? "";
  const phaseKey = phase || "group";

  const scoreTickQuery = useQuery({
    queryKey: ["operational-superbet-event-score", eventId],
    queryFn: () => getSuperbetEventUseCase.execute({ eventId, saveBronze: false }),
    enabled,
    retry: false,
    staleTime: STALE_MS,
    refetchInterval: (q) => {
      const d = q.state.data as LiveAdviceScoreTick | undefined;
      if (!d?.isLive) return false;
      return SCORE_POLL_MS;
    },
  });

  const adviceQuery = useQuery({
    queryKey: ["operational-superbet-live-advice", eventId, bankroll, kickoffKey, phaseKey],
    queryFn: () =>
      getSuperbetLiveAdviceUseCase.execute({
        eventId,
        bankroll,
        phase: phaseKey,
        fast: true,
        ...(kickoff ? { kickoff } : {}),
      }),
    enabled: enabled && Boolean(scoreTickQuery.data),
    retry: false,
    staleTime: STALE_MS,
    refetchInterval: (q) => {
      const d = q.state.data as SuperbetLiveAdvice | undefined;
      if (!d?.isLive || d?.isFinished) return false;
      return ODDS_POLL_MS;
    },
  });

  const refetch = useCallback(() => {
    void scoreTickQuery.refetch();
    void adviceQuery.refetch();
  }, [adviceQuery, scoreTickQuery]);

  const fallbackData = fallbackAdviceFromScore(scoreTickQuery.data ?? null, eventId);
  const data = adviceQuery.data ?? fallbackData;

  return {
    data,
    scoreTick: scoreTickQuery.data ?? null,
    isLoading: !scoreTickQuery.data && !adviceQuery.data && (scoreTickQuery.isLoading || adviceQuery.isLoading),
    isAdvicePending: !adviceQuery.data && adviceQuery.isLoading,
    isError: !data && adviceQuery.isError && scoreTickQuery.isError,
    error: adviceQuery.error ?? scoreTickQuery.error,
    isFetching: adviceQuery.isFetching || scoreTickQuery.isFetching,
    refetch,
    pollMs: {
      fast: ODDS_POLL_MS,
      score: SCORE_POLL_MS,
      full: ODDS_POLL_MS,
      /** Exposto para o countdown da topbar — 1min30s = 90s. */
      seconds: ODDS_POLL_MS / 1000,
      tier: "leve",
    },
  };
}
