import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQueries, useQuery } from "@tanstack/react-query";
import {
  getSuperbetLiveAdviceUseCase,
  getUserOpenBetsUseCase,
  refreshOpenBetsCashoutsUseCase,
} from "@/application/container";
import { useDataPulse } from "@/infrastructure/api/dataPulseStore";
import { SuperbetPulseBadge } from "@/presentation/components/layout/SuperbetPulseBadge";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { LiveMatchSkeleton } from "@/presentation/components/ui/Skeleton";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";
import { IconArrowLeft, IconBell, IconChevronRight } from "@/presentation/components/ui/Icons";
import { useToast } from "@/presentation/components/ui/toast/ToastContext";
import { CashoutAlertSetup } from "@/presentation/components/predictions/CashoutAlertSetup";
import { BetStrategyPanel } from "@/presentation/components/predictions/BetStrategyPanel";
import { ComboTicketPanel } from "@/presentation/components/predictions/ComboTicketPanel";
import { LiveBestCombosPanel } from "@/presentation/components/predictions/LiveBestCombosPanel";
import { LiveHalfTicketsPanel } from "@/presentation/components/predictions/LiveHalfTicketsPanel";
import { LiveRemaining2hMarketsPanel } from "@/presentation/components/predictions/LiveRemaining2hMarketsPanel";
import { LiveLongshotCombosPanel } from "@/presentation/components/predictions/LiveLongshotCombosPanel";
import { LiveTopReturnPanel } from "@/presentation/components/predictions/LiveTopReturnPanel";
import { LiveOptimizedTicketsPanel } from "@/presentation/components/predictions/LiveOptimizedTicketsPanel";
import { LiveActionNowPanel } from "@/presentation/components/predictions/LiveActionNowPanel";
import { LiveModelVsMarketHero } from "@/presentation/components/predictions/LiveModelVsMarketHero";
import { LiveEvRealPanel } from "@/presentation/components/predictions/LiveEvRealPanel";
import { LiveCornersPanel } from "@/presentation/components/predictions/LiveCornersPanel";
import { LiveStatsCompactBar } from "@/presentation/components/predictions/LiveStatsCompactBar";
import { LiveTimelinePanel } from "@/presentation/components/predictions/LiveTimelinePanel";
import { LiveFormH2hPanel } from "@/presentation/components/predictions/LiveFormH2hPanel";
import { LivePlayerStatsPanel } from "@/presentation/components/predictions/LivePlayerStatsPanel";
import { LiveSocialRadarPanel } from "@/presentation/components/predictions/LiveSocialRadarPanel";
import { LiveMarketCards } from "@/presentation/components/predictions/LiveMarketCards";
import { LiveModelPanel } from "@/presentation/components/predictions/LiveModelPanel";
import { LiveMatchProbCard } from "@/presentation/components/predictions/LiveMatchProbCard";
import { LiveStatsProjectionPanel } from "@/presentation/components/predictions/LiveStatsProjectionPanel";
import LiveRefereePanel from "@/presentation/components/predictions/LiveRefereePanel";
import {
  LiveOpenBetMonitor,
  createRegisteredBetId,
  type RegisteredBetEntry,
} from "@/presentation/components/predictions/LiveOpenBetMonitor";
import { LivePlainGuide } from "@/presentation/components/predictions/LivePlainGuide";
import { LiveScoreHeatmap } from "@/presentation/components/predictions/LiveScoreHeatmap";
import { LivePredictionEvolutionChart } from "@/presentation/components/live-dashboard/LivePredictionEvolutionChart";
import LiveHedgeAlert from "@/presentation/components/predictions/LiveHedgeAlert";
import LiveAgainstModelAlert from "@/presentation/components/predictions/LiveAgainstModelAlert";
import { LiveP0GuardBanner } from "@/presentation/components/predictions/LiveP0GuardBanner";
import { LiveBetBuilderGuardPanel } from "@/presentation/components/predictions/LiveBetBuilderGuardPanel";
import { LiveRecalibrationBanner } from "@/presentation/components/predictions/LiveRecalibrationBanner";
import { useLiveAdviceQueries } from "@/presentation/hooks/useLiveAdviceQueries";
import { useLiveRecalibration } from "@/presentation/hooks/useLiveRecalibration";
import { useCashoutTargetAlerts } from "@/presentation/hooks/useCashoutTargetAlerts";
import { LiveContextUpload } from "@/presentation/components/predictions/LiveContextUpload";
import {
  ensureNotificationPermission,
  notificationPermission,
} from "@/presentation/utils/browserNotifications";
import {
  getCashoutAlertConfig,
  setCashoutAlertConfig,
} from "@/presentation/utils/cashoutAlertStorage";
import { draftAgainstModelAlert, normalizeH2hOutcome } from "@/presentation/utils/againstModelBet";
import { resolveLiveAdvicePhase } from "@/presentation/utils/liveAdvicePhase";

const FAST_POLL_MS = 10_000;
const SCORE_POLL_MS = 5_000;
const MAX_OPEN_BETS = 2;

const CASHOUT_REFRESH_MS = 30_000;

type BetDraft = {
  market: string;
  outcome: string;
  stake: number;
  oddsPlaced: number;
  offeredCashout: number | null;
  cashoutAlertEnabled: boolean;
  cashoutAlertTarget: number | null;
  cashoutNotifyApproach: boolean;
  cashoutNotifyReach: boolean;
};

const DEFAULT_BET_DRAFT: BetDraft = {
  market: "h2h",
  outcome: "X",
  stake: 10,
  oddsPlaced: 2,
  offeredCashout: null,
  cashoutAlertEnabled: false,
  cashoutAlertTarget: null,
  cashoutNotifyApproach: true,
  cashoutNotifyReach: true,
};

function betToDraft(bet: RegisteredBetEntry): BetDraft {
  const alert = getCashoutAlertConfig(bet.id);
  return {
    market: bet.market,
    outcome: bet.outcome,
    stake: bet.stake,
    oddsPlaced: bet.oddsPlaced,
    offeredCashout: bet.offeredCashout ?? null,
    cashoutAlertEnabled: alert.enabled,
    cashoutAlertTarget: alert.target,
    cashoutNotifyApproach: alert.notifyApproach,
    cashoutNotifyReach: alert.notifyReach,
  };
}

function persistBetAlertConfig(
  betId: string,
  draft: BetDraft,
  bump?: () => void,
): void {
  setCashoutAlertConfig(betId, {
    enabled: draft.cashoutAlertEnabled,
    target: draft.cashoutAlertTarget,
    notifyApproach: draft.cashoutNotifyApproach,
    notifyReach: draft.cashoutNotifyReach,
  });
  bump?.();
}

function formatCapturedAt(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function betMarketKey(bet: Pick<RegisteredBetEntry, "market" | "outcome">): string {
  const outcome =
    bet.market === "h2h" ? normalizeH2hOutcome(bet.outcome) : bet.outcome.toLowerCase();
  return `${bet.market}:${outcome}`;
}

function hasDuplicateMarket(
  bets: RegisteredBetEntry[],
  draft: BetDraft,
  excludeId?: string,
): boolean {
  const key = betMarketKey(draft);
  return bets.some((b) => b.id !== excludeId && betMarketKey(b) === key);
}

function formatOddsLine(odds: Record<string, number>): string {
  const parts: string[] = [];
  if (odds["1"]) parts.push(`1 ${odds["1"].toFixed(2)}`);
  if (odds["X"]) parts.push(`X ${odds["X"].toFixed(2)}`);
  if (odds["2"]) parts.push(`2 ${odds["2"].toFixed(2)}`);
  return parts.join(" · ") || "—";
}

export function LiveInPlayPage() {
  const { eventId: eventIdParam } = useParams();
  const [searchParams] = useSearchParams();
  const kickoffFromUrl = searchParams.get("kickoff");
  const advicePhase = resolveLiveAdvicePhase(searchParams);
  const eventId = Number.parseInt(eventIdParam ?? "", 10);
  const pulse = useDataPulse();
  const { addToast } = useToast();

  const [bankrollDraft, setBankrollDraft] = useState(1000);
  const [appliedBankroll, setAppliedBankroll] = useState(1000);
  const bankrollDirty = bankrollDraft !== appliedBankroll;
  const [registeredBets, setRegisteredBets] = useState<RegisteredBetEntry[]>([]);
  const [trackBet, setTrackBet] = useState(false);
  const [betDraft, setBetDraft] = useState<BetDraft>(DEFAULT_BET_DRAFT);
  const [formMode, setFormMode] = useState<"add" | string | null>(null);
  const [betSectionOpen, setBetSectionOpen] = useState(false);
  const [notifyPermission, setNotifyPermission] = useState(notificationPermission());
  const [alertConfigVersion, setAlertConfigVersion] = useState(0);

  const openBetsQuery = useQuery({
    queryKey: ["user-open-bets"],
    queryFn: () => getUserOpenBetsUseCase.execute(),
  });

  const {
    data,
    scoreTick,
    liveHeader,
    adviceSource,
    isLoading,
    isAdvicePending,
    isError: adviceIsError,
    error: adviceError,
    isFetching: adviceFetching,
    refetch: refetchAdvice,
    pollMs,
    timelineReactive,
  } = useLiveAdviceQueries(eventId, appliedBankroll, kickoffFromUrl, advicePhase);

  const recalibrationEvent = useLiveRecalibration(data, adviceFetching);

  const apiBets: RegisteredBetEntry[] = useMemo(() => {
    if (!openBetsQuery.data?.bets) return [];
    return openBetsQuery.data.bets
      .filter(
        (b) =>
          b.superbetEventId === eventId ||
          (b.homeTeam === data?.homeTeam && b.awayTeam === data?.awayTeam),
      )
      .map((b) => ({
        id: b.id,
        market: b.picks[0]?.market ?? "h2h",
        outcome: b.picks[0]?.outcome ?? "X",
        stake: b.stake,
        oddsPlaced: b.oddsPlaced,
        potentialReturn: b.potentialReturn,
        ticketCode: b.ticketCode,
        cashoutValue: b.cashoutValue,
        autoMonitor: true,
        offeredCashout: b.cashoutValue,
      }));
  }, [openBetsQuery.data, eventId, data?.homeTeam, data?.awayTeam]);

  const displayBets = apiBets.length > 0 ? apiBets : registeredBets;

  useEffect(() => {
    if (!trackBet || !Number.isFinite(eventId) || eventId <= 0 || data?.isFinished) return;
    let cancelled = false;
    const syncCashouts = async () => {
      try {
        await refreshOpenBetsCashoutsUseCase.execute(eventId);
        if (!cancelled) await openBetsQuery.refetch();
      } catch {
        /* API ou Superbet offline */
      }
    };
    void syncCashouts();
    const timer = window.setInterval(syncCashouts, CASHOUT_REFRESH_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [trackBet, eventId, data?.isFinished, openBetsQuery.refetch]);

  useCashoutTargetAlerts({
    bets: displayBets,
    homeTeam: data?.homeTeam ?? "",
    awayTeam: data?.awayTeam ?? "",
    enabled: trackBet && Boolean(data?.homeTeam) && !data?.isFinished,
    configVersion: alertConfigVersion,
    onAlert: ({ body, kind }) => {
      addToast(body, kind === "reach" ? "success" : "info");
    },
  });

  const activeAlertCount = useMemo(
    () => displayBets.filter((b) => getCashoutAlertConfig(b.id).enabled).length,
    [displayBets, alertConfigVersion],
  );

  const blockNewBets = Boolean(data?.betGuardrails?.blockNewBets);
  const showBetForm = trackBet && formMode != null && !blockNewBets;
  const canAddBet =
    trackBet &&
    !blockNewBets &&
    displayBets.length < MAX_OPEN_BETS &&
    formMode === null;
  const betAnalysisActive =
    trackBet && displayBets.some((b) => b.autoMonitor && formMode !== b.id);

  const betAdviceQueries = useQueries({
    queries: displayBets.map((bet) => ({
      queryKey: [
        "superbet-live-bet",
        eventId,
        appliedBankroll,
        advicePhase,
        bet.id,
        bet.market,
        bet.outcome,
        bet.stake,
        bet.oddsPlaced,
      ],
      queryFn: () =>
        getSuperbetLiveAdviceUseCase.execute({
          eventId,
          phase: advicePhase,
          bankroll: appliedBankroll,
          market: bet.market,
          outcome: bet.outcome,
          stake: bet.stake,
          oddsPlaced: bet.oddsPlaced,
          fast: true,
        }),
      enabled:
        Number.isFinite(eventId) &&
        eventId > 0 &&
        trackBet &&
        bet.autoMonitor &&
        formMode !== bet.id,
      staleTime: 10_000,
      refetchInterval: (query: { state: { data?: { isFinished?: boolean } } }) =>
        query.state.data?.isFinished ? false : FAST_POLL_MS,
    })),
  });

  const draftAgainstAlert = useMemo(() => {
    if (!data || !showBetForm || betDraft.market !== "h2h") return null;
    const normalized = normalizeH2hOutcome(betDraft.outcome);
    const apiAlert = data.againstModelAlerts?.find((a) => a.betOutcome === normalized);
    if (apiAlert) return apiAlert;
    const pregame = data.againstModelAlerts?.[0]
      ? {
          palpite: data.againstModelAlerts[0].pregamePalpite,
          prob: data.againstModelAlerts[0].pregameProb,
        }
      : null;
    return draftAgainstModelAlert(betDraft, data, pregame);
  }, [data, showBetForm, betDraft]);

  const againstModelAlerts = useMemo(() => {
    const fromApi = data?.againstModelAlerts ?? [];
    if (draftAgainstAlert && !fromApi.some((a) => a.message === draftAgainstAlert.message)) {
      return [draftAgainstAlert, ...fromApi];
    }
    return fromApi;
  }, [data?.againstModelAlerts, draftAgainstAlert]);

  const matchLink = useMemo(() => {
    if (!data) return null;
    const isFriendly = advicePhase === "friendly";
    const params = new URLSearchParams({
      ...(isFriendly ? { source: "friendly" } : {}),
      phase: advicePhase,
      superbet: String(eventId),
      liveHome: String(data.currentScore?.split("x")[0] ?? "0"),
      liveAway: String(data.currentScore?.split("x")[1] ?? "0"),
      minute: String(data.minute),
    });
    return `/match/${encodeURIComponent(data.homeTeam)}/${encodeURIComponent(data.awayTeam)}?${params}`;
  }, [advicePhase, data, eventId]);

  const defensiveLiveContext = useMemo(() => {
    if (!data) return null;
    return {
      minute: data.minute,
      periodLabel: data.periodLabel,
      liveStats: data.liveStats,
      halftimeReport: data.halftimeReport ?? null,
      shields: data.strategy?.shields ?? [],
    };
  }, [data]);

  if (!Number.isFinite(eventId) || eventId <= 0) {
    return (
      <PageTransition>
        <ErrorState message="ID do evento inválido." />
        <Link to="/ao-vivo" className="mt-4 inline-flex text-sm text-neon-green hover:underline">
          Voltar à lista ao vivo
        </Link>
      </PageTransition>
    );
  }

  return (
    <PageTransition>
      {/* ── Cabeçalho de navegação ── */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to="/ao-vivo"
          className="inline-flex items-center gap-2 text-sm text-slate-400 transition-colors hover:text-white"
        >
          <IconArrowLeft className="h-4 w-4" />
          Voltar ao vivo
        </Link>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to={`/ao-vivo/${eventId}/painel`}
            className="inline-flex items-center gap-1.5 rounded-lg border border-neon-blue/30 bg-neon-blue/10 px-3 py-1.5 text-xs font-medium text-neon-blue transition hover:border-neon-blue/50"
          >
            Painel completo
          </Link>
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
          {pulse?.wcModelsReady === false && (
            <span className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-amber-300">
              Modelo WC indisponível
            </span>
          )}
          <SuperbetPulseBadge
            eventId={eventId}
            compact
            adaptivePollMs={pollMs.fast}
            adaptivePollTier={pollMs.tier}
          />
          <span>
            Superbet #{eventId}
            {data?.betradarId ? ` · Betradar ${data.betradarId}` : ""}
          </span>
          </div>
        </div>
      </div>

      {isLoading ? (
        <LiveMatchSkeleton />
      ) : adviceIsError && !scoreTick ? (
        <ErrorState
          message={
            adviceError instanceof Error
              ? adviceError.message
              : "Falha ao capturar jogo na Superbet"
          }
          onRetry={refetchAdvice}
        />
      ) : data ? (
        <>
          {/* ── 1. MATCH HEADER ── */}
          <section className="glass-card p-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex min-w-0 flex-1 items-center gap-2">
                <TeamFlag team={data.homeTeam} size={32} />
                <div className="min-w-0 text-left">
                  <p className="truncate text-sm font-semibold text-white">{data.homeTeam}</p>
                </div>
                <div className="px-2 text-center">
                  <p className="font-mono text-xl font-bold text-white">
                    {liveHeader?.currentScore?.replace("x", " × ") ??
                      data.currentScore?.replace("x", " × ") ??
                      "0 × 0"}
                  </p>
                  <p className="mt-0.5 flex items-center justify-center gap-1.5 text-xs font-semibold">
                    {data.isLive && !data.isFinished && (
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red-400" />
                    )}
                    <span className="text-amber-300">
                      {(liveHeader?.minute ?? data.minute)}&apos;
                      {(liveHeader?.periodLabel ?? data.periodLabel)
                        ? ` · ${liveHeader?.periodLabel ?? data.periodLabel}`
                        : ""}
                    </span>
                  </p>
                </div>
                <div className="min-w-0 text-right">
                  <p className="truncate text-sm font-semibold text-white">{data.awayTeam}</p>
                </div>
                <TeamFlag team={data.awayTeam} size={32} />
              </div>
              <div className="text-right text-[11px] text-slate-500">
                <p>
                  Odds:{" "}
                  <span className="text-slate-300">
                    {formatOddsLine(liveHeader?.h2hOdds ?? data.h2hOdds)}
                  </span>
                </p>
                <p>{liveHeader?.rawMarketCount ?? data.rawMarketCount} mercados</p>
                <p className="mt-0.5 flex flex-wrap items-center justify-end gap-2">
                  <span>
                    {formatCapturedAt(liveHeader?.capturedAt ?? data.capturedAt)}
                    {data.isLive
                      ? liveHeader?.scoreIsFresh
                        ? ` · ${SCORE_POLL_MS / 1000}s`
                        : ` · ${FAST_POLL_MS / 1000}s`
                      : ""}
                  </span>
                  {data.isLive && !data.isFinished && (
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                        adviceSource === "full"
                          ? "bg-sky-500/15 text-sky-300"
                          : "bg-amber-500/10 text-amber-300"
                      }`}
                      title={
                        adviceSource === "full"
                          ? "Última captura com Sofascore e lake completo"
                          : "Modo rápido — refresh completo a cada 60s"
                      }
                    >
                      {adviceSource === "full" ? "completo" : "rápido"}
                    </span>
                  )}
                  <button
                    onClick={() => refetchAdvice()}
                    disabled={adviceFetching}
                    title="Atualizar agora"
                    className="rounded p-0.5 text-slate-500 transition hover:text-slate-300 disabled:opacity-40"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      className={`h-3.5 w-3.5 ${adviceFetching ? "animate-spin" : ""}`}
                    >
                      <path
                        fillRule="evenodd"
                        d="M15.312 11.424a5.5 5.5 0 0 1-9.201 2.466l-.312-.311h2.433a.75.75 0 0 0 0-1.5H3.989a.75.75 0 0 0-.75.75v4.242a.75.75 0 0 0 1.5 0v-2.43l.31.31a7 7 0 0 0 11.712-3.138.75.75 0 0 0-1.46-.33Zm-7.66-8.848A5.5 5.5 0 0 1 18.5 10a.75.75 0 0 0 1.5 0 7 7 0 0 0-11.712-5.138l-.31.31V2.75a.75.75 0 0 0-1.5 0v4.243c0 .414.336.75.75.75h4.243a.75.75 0 0 0 0-1.5h-2.43l.31-.31Z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </button>
                </p>
              </div>
            </div>
            {data.isFinished && (
              <p className="mt-2 text-sm text-slate-400">Jogo encerrado — polling pausado.</p>
            )}

          </section>

          {/* ── 1b-top. CARD PROB 1X2 ── */}
          {(data.inplaySummary.probFinalHome > 0 || data.inplaySummary.probFinalAway > 0) && (
            <LiveMatchProbCard data={data} />
          )}

          {/* ── 1b-mid. PROJEÇÕES ESCANTEIOS / CARTÕES / GOLS / FALTAS ── */}
          <LiveStatsProjectionPanel data={data} />

          {/* ── 1c. ANÁLISE PRÉ-JOGO (upload .txt) ── */}
          <LiveContextUpload
            eventId={eventId}
            activeContext={data.matchContext ?? null}
            onContextChanged={refetchAdvice}
          />

          {/* ── 1b. ODDS + EV + STATS AO VIVO ── */}
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
            <LiveModelVsMarketHero data={data} />
            <div className="flex flex-col gap-3">
              <LiveStatsCompactBar data={data} eventId={eventId} />
              <LiveEvRealPanel data={data} />
            </div>
          </div>
          <LiveCornersPanel data={data} />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <LiveTimelinePanel
              data={data}
              highlightGoalMinute={timelineReactive.latestGoalMinute}
              reactiveBoosted={timelineReactive.boosted}
            />
            <LiveFormH2hPanel data={data} />
          </div>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <LivePlayerStatsPanel data={data} />
            <LiveSocialRadarPanel data={data} />
          </div>

          <LiveRecalibrationBanner event={recalibrationEvent} />

          {/* ── 2. HERO CTA ── */}
          <LiveActionNowPanel data={data} trackBet={betAnalysisActive} />

          <LiveOptimizedTicketsPanel data={data} />

          {/* ── 2a-top. RETORNO ESPERADO (EV × stake, filtro odd) ── */}
          <LiveTopReturnPanel data={data} />

          {/* ── 2a. BILHETES 1T / 2T (modelo × mercado) ── */}
          <LiveHalfTicketsPanel data={data} />

          {/* ── 2a0. MELHOR COMBO (seguro / equilibrado / longshot) ── */}
          <LiveBestCombosPanel data={data} />

          {/* ── 2a1. MERCADOS 2T VIÁVEIS (tempo restante) ── */}
          <LiveRemaining2hMarketsPanel data={data} />

          {/* ── 2a2. LONGSHOT R$5 → R$400+ ── */}
          <LiveLongshotCombosPanel data={data} />

          {/* ── 2b. REGRAS P0 ── */}
          <LiveP0GuardBanner guardrails={data.betGuardrails} />

          {/* ── 2b1. CRIAR APOSTA / over 1T ── */}
          <LiveBetBuilderGuardPanel guardrails={data.betGuardrails} />

          {/* ── 2b. ALERTA — aposta contra palpite do modelo ── */}
          <LiveAgainstModelAlert alerts={againstModelAlerts} />

          {/* ── 2b. ALERTA DE HEDGE (apostas do usuário) ── */}
          <LiveHedgeAlert report={data?.hedgeReport ?? null} />

          {/* ── 3. COLUNA DUPLA: Mercados | Modelo + Casa ── */}
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_320px]">
            <section className="glass-card p-3 space-y-3">
              <LiveMarketCards data={data} />
              <LiveRefereePanel
                refereeMarkets={data?.inplaySummary?.refereeMarkets}
                refereeProfile={data?.inplaySummary?.refereeProfile}
                currentMinute={data?.minute ?? 0}
                homeYellows={data?.liveStats?.homeYellowCards ?? 0}
                awayYellows={data?.liveStats?.awayYellowCards ?? 0}
                homeReds={data?.liveStats?.homeRedCards ?? 0}
                awayReds={data?.liveStats?.awayRedCards ?? 0}
                compact
              />
            </section>
            <LiveModelPanel data={data} recalibrationEvent={recalibrationEvent} />
          </div>

          {/* ── 3b. HEATMAP DE PLACARES ── */}
          <LivePredictionEvolutionChart data={data} />

          <LiveScoreHeatmap data={data} />

          {/* ── 4. GUIA RÁPIDO (colapsável) ── */}
          <LivePlainGuide data={data} trackBet={betAnalysisActive} />

          {/* ── 5. BILHETE COMBO KXL ── */}
          <ComboTicketPanel
            homeTeam={data.homeTeam}
            awayTeam={data.awayTeam}
            strategy={data.strategy}
            superbetEventId={data.superbetEventId}
            minute={data.minute}
            defensiveMode
            liveContext={defensiveLiveContext}
          />

          {/* ── 6. ESTRATÉGIA ── */}
          <BetStrategyPanel strategy={data.strategy} />

          {/* ── 7. MINHA APOSTA / CASHOUT (colapsável) ── */}
          <section className="overflow-hidden rounded-2xl border border-white/8 bg-gradient-to-b from-white/[0.03] to-transparent">
            <button
              type="button"
              onClick={() => setBetSectionOpen((v) => !v)}
              className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left transition-colors hover:bg-white/[0.02]"
              aria-expanded={betSectionOpen}
            >
              <div className="flex items-start gap-3">
                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-neon-blue/10 text-neon-blue">
                  <IconBell className="h-4 w-4" />
                </span>
                <div>
                  <h2 className="text-sm font-semibold text-white">Minha aposta & cash-out</h2>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {displayBets.length > 0
                      ? `${displayBets.length} bilhete${displayBets.length > 1 ? "s" : ""} · modelo a cada ${FAST_POLL_MS / 1000}s`
                      : "Cadastre seu bilhete, defina meta de saída e receba alertas"}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {activeAlertCount > 0 && (
                  <span className="inline-flex items-center gap-1 rounded-full border border-amber-400/30 bg-amber-500/10 px-2 py-0.5 text-[11px] font-semibold text-amber-200">
                    <IconBell className="h-3 w-3" />
                    {activeAlertCount} alerta{activeAlertCount > 1 ? "s" : ""}
                  </span>
                )}
                {displayBets.length > 0 && (
                  <span className="rounded-full bg-neon-green/15 px-2 py-0.5 text-[11px] font-semibold text-neon-green">
                    {displayBets.length} ativo{displayBets.length > 1 ? "s" : ""}
                  </span>
                )}
                <span
                  className={`shrink-0 text-slate-500 transition-transform duration-200 ${betSectionOpen ? "rotate-180" : ""}`}
                  aria-hidden="true"
                >
                  ▾
                </span>
              </div>
            </button>

            {betSectionOpen && (
              <div className="border-t border-white/8 px-5 pb-5 pt-4">
                <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
                  <div className="flex flex-col gap-1 text-xs text-slate-400">
                    <span>Minha banca (R$)</span>
                    <div className="flex flex-wrap items-center gap-2">
                      <input
                        type="number"
                        min={100}
                        value={bankrollDraft}
                        onChange={(e) => setBankrollDraft(Number(e.target.value))}
                        className="w-28 rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 font-mono text-sm text-white"
                      />
                      <button
                        type="button"
                        disabled={!bankrollDirty}
                        onClick={() => setAppliedBankroll(bankrollDraft)}
                        className="rounded-lg border border-white/15 px-2.5 py-1.5 text-xs text-slate-300 transition-colors hover:border-neon-green/30 hover:text-white disabled:cursor-default disabled:opacity-40"
                      >
                        Aplicar banca
                      </button>
                    </div>
                    <span className="text-[10px] text-slate-600">
                      Digitar não recarrega — clique Aplicar para recalcular aportes
                    </span>
                  </div>
                  <label className="flex items-center gap-2 pb-2 text-xs text-slate-400">
                    <input
                      type="checkbox"
                      checked={trackBet}
                      onChange={(e) => {
                        const on = e.target.checked;
                        setTrackBet(on);
                        if (!on) {
                          setRegisteredBets([]);
                          setFormMode(null);
                        } else if (displayBets.length === 0) {
                          setBetDraft(DEFAULT_BET_DRAFT);
                          setFormMode("add");
                        }
                      }}
                      className="rounded border-white/20"
                    />
                    Tenho aposta aberta
                  </label>
                </div>

                {trackBet && blockNewBets && (
                  <p className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">
                    Cadastro de novas apostas desativado após{" "}
                    {data.betGuardrails?.blockMinute ?? 45}&apos;. Use o monitor de cash-out
                    nos bilhetes já abertos.
                  </p>
                )}

                {trackBet && displayBets.length > 0 && (
                  <div className="mb-4 space-y-3">
                    {displayBets.map((bet, index) =>
                      formMode === bet.id ? null : (
                        <LiveOpenBetMonitor
                          key={bet.id}
                          data={data}
                          bet={bet}
                          cashout={
                            (betAdviceQueries[index]?.data as SuperbetLiveAdvice | undefined)
                              ?.cashout ?? null
                          }
                          betIndex={index + 1}
                          totalBets={displayBets.length}
                          isFetching={betAdviceQueries[index]?.isFetching ?? false}
                          pollSeconds={FAST_POLL_MS / 1000}
                          onEdit={() => {
                            setBetDraft(betToDraft(bet));
                            setFormMode(bet.id);
                          }}
                          onRemove={() => {
                            setRegisteredBets((prev) => {
                              if (apiBets.some((b) => b.id === bet.id)) return prev; // read-only API bets
                              const next = prev.filter((b) => b.id !== bet.id);
                              if (next.length === 0) {
                                setTrackBet(false);
                                setFormMode(null);
                              } else if (formMode === bet.id) {
                                setFormMode(null);
                              }
                              return next;
                            });
                          }}
                          onAutoMonitorChange={(on) => {
                            setRegisteredBets((prev) =>
                              prev.map((b) =>
                                b.id === bet.id ? { ...b, autoMonitor: on } : b,
                              ),
                            );
                          }}
                        />
                      ),
                    )}
                  </div>
                )}

                {canAddBet && (
                  <button
                    type="button"
                    onClick={() => {
                      setBetDraft(DEFAULT_BET_DRAFT);
                      setFormMode("add");
                    }}
                    className="mb-4 rounded-lg border border-white/15 px-4 py-2 text-sm text-slate-300 transition-colors hover:border-neon-green/30 hover:text-white"
                  >
                    + Adicionar outra aposta ({displayBets.length}/{MAX_OPEN_BETS})
                  </button>
                )}

                {showBetForm && (
                  <>
                    <p className="mb-3 text-xs text-slate-500">
                      {formMode === "add"
                        ? `Nova aposta (${displayBets.length + 1} de ${MAX_OPEN_BETS})`
                        : "Editar aposta"}
                    </p>
                    <div className="mb-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                      <label className="flex flex-col gap-1 text-xs text-slate-400">
                        Mercado
                        <select
                          value={betDraft.market}
                          onChange={(e) =>
                            setBetDraft((d) => ({ ...d, market: e.target.value }))
                          }
                          className="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-white"
                        >
                          <option value="h2h">1X2</option>
                          <option value="over_2_5">Over 2.5</option>
                          <option value="btts">Ambos marcam</option>
                          <option value="next_goal">Próximo gol</option>
                        </select>
                      </label>
                      <label className="flex flex-col gap-1 text-xs text-slate-400">
                        Palpite
                        <select
                          value={betDraft.outcome}
                          onChange={(e) =>
                            setBetDraft((d) => ({ ...d, outcome: e.target.value }))
                          }
                          className="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-white"
                        >
                          <option value="1">{data.homeTeam}</option>
                          <option value="X">Empate</option>
                          <option value="2">{data.awayTeam}</option>
                          <option value="yes">Sim</option>
                          <option value="home">Gol {data.homeTeam}</option>
                          <option value="away">Gol {data.awayTeam}</option>
                        </select>
                      </label>
                      <label className="flex flex-col gap-1 text-xs text-slate-400">
                        Stake (R$)
                        <input
                          type="number"
                          min={1}
                          value={betDraft.stake}
                          onChange={(e) =>
                            setBetDraft((d) => ({ ...d, stake: Number(e.target.value) }))
                          }
                          className="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 font-mono text-sm text-white"
                        />
                      </label>
                      <label className="flex flex-col gap-1 text-xs text-slate-400">
                        Odd entrada
                        <input
                          type="number"
                          min={1.01}
                          step={0.01}
                          value={betDraft.oddsPlaced}
                          onChange={(e) =>
                            setBetDraft((d) => ({ ...d, oddsPlaced: Number(e.target.value) }))
                          }
                          className="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 font-mono text-sm text-white"
                        />
                      </label>
                    </div>
                    <CashoutAlertSetup
                      draft={betDraft}
                      notifyPermission={notifyPermission}
                      refreshSeconds={CASHOUT_REFRESH_MS / 1000}
                      onDraftChange={(patch) => setBetDraft((d) => ({ ...d, ...patch }))}
                      onRequestNotificationPermission={async () => {
                        const ok = await ensureNotificationPermission();
                        setNotifyPermission(ok ? "granted" : notificationPermission());
                      }}
                    />
                    <div className="mb-4 mt-4 flex flex-wrap items-center gap-3">
                      {hasDuplicateMarket(
                        displayBets,
                        betDraft,
                        typeof formMode === "string" && formMode !== "add" ? formMode : undefined,
                      ) && (
                        <p className="w-full rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                          Já existe bilhete neste mercado/palpite. Regra P0: máximo 1 por
                          mercado.
                        </p>
                      )}
                      <button
                        type="button"
                        disabled={hasDuplicateMarket(
                          displayBets,
                          betDraft,
                          typeof formMode === "string" && formMode !== "add"
                            ? formMode
                            : undefined,
                        )}
                        onClick={() => {
                          if (formMode === "add") {
                            const newId = createRegisteredBetId();
                            persistBetAlertConfig(newId, betDraft, () =>
                              setAlertConfigVersion((v) => v + 1),
                            );
                            setRegisteredBets((prev) =>
                              [
                                ...prev,
                                {
                                  ...betDraft,
                                  id: newId,
                                  autoMonitor: true,
                                },
                              ].slice(0, MAX_OPEN_BETS),
                            );
                          } else if (typeof formMode === "string") {
                            persistBetAlertConfig(formMode, betDraft, () =>
                              setAlertConfigVersion((v) => v + 1),
                            );
                            if (!apiBets.some((b) => b.id === formMode)) {
                              setRegisteredBets((prev) =>
                                prev.map((b) =>
                                  b.id === formMode
                                    ? {
                                        ...b,
                                        market: betDraft.market,
                                        outcome: betDraft.outcome,
                                        stake: betDraft.stake,
                                        oddsPlaced: betDraft.oddsPlaced,
                                        offeredCashout: betDraft.offeredCashout,
                                      }
                                    : b,
                                ),
                              );
                            }
                          }
                          setFormMode(null);
                        }}
                        className="rounded-lg border border-neon-green/40 bg-neon-green/15 px-4 py-2 text-sm font-semibold text-neon-green transition-colors hover:bg-neon-green/25 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        {formMode === "add" ? "Cadastrar e monitorar" : "Salvar alterações"}
                      </button>
                      {(displayBets.length > 0 || apiBets.length === 0) && (
                        <button
                          type="button"
                          onClick={() => setFormMode(null)}
                          className="rounded-lg border border-white/15 px-4 py-2 text-sm text-slate-400 hover:text-white"
                        >
                          Cancelar
                        </button>
                      )}
                      <span className="text-xs text-slate-500">
                        A página não recarrega ao digitar nos campos
                      </span>
                    </div>
                  </>
                )}

                {trackBet && displayBets.length === 0 && formMode === null && (
                  <p className="text-sm text-slate-500">
                    Marque a opção acima ou clique em adicionar para cadastrar até{" "}
                    {MAX_OPEN_BETS} bilhetes do mesmo jogo.
                  </p>
                )}
              </div>
            )}
          </section>

          {matchLink && (
            <div className="flex justify-end">
              <Link
                to={matchLink}
                className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-neon-green"
              >
                Ver análise completa do jogo
                <IconChevronRight className="h-3 w-3" />
              </Link>
            </div>
          )}
        </>
      ) : scoreTick ? (
        <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex min-w-0 flex-1 items-center gap-3">
              <TeamFlag team={scoreTick.homeTeam} size={36} />
              <p className="truncate text-sm font-semibold text-white">{scoreTick.homeTeam}</p>
            </div>
            <div className="px-2 text-center">
              <p className="font-mono text-2xl font-bold text-white">
                {scoreTick.currentScore?.replace("x", " × ") ?? "0 × 0"}
              </p>
              <p className="mt-0.5 text-xs font-semibold text-amber-300">
                {scoreTick.minute}&apos;
                {scoreTick.periodLabel ? ` · ${scoreTick.periodLabel}` : ""}
              </p>
            </div>
            <div className="flex min-w-0 flex-1 items-center justify-end gap-3">
              <p className="truncate text-sm font-semibold text-white">{scoreTick.awayTeam}</p>
              <TeamFlag team={scoreTick.awayTeam} size={36} />
            </div>
          </div>
          <p className="mt-4 text-center text-xs text-slate-500" aria-live="polite">
            Carregando modelo in-play…
          </p>
        </section>
      ) : null}

      {isAdvicePending && (
        <p className="text-center text-[11px] text-slate-500" aria-live="polite">
          Calculando probabilidades e mercados…
        </p>
      )}

      {adviceFetching && data && (
        <p className="text-center text-[11px] text-slate-500" aria-live="polite">
          Atualizando palpite…
        </p>
      )}
    </PageTransition>
  );
}
