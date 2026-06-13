import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQueries, useQuery } from "@tanstack/react-query";
import {
  getSuperbetEventUseCase,
  getSuperbetLiveAdviceUseCase,
  getUserOpenBetsUseCase,
} from "@/application/container";
import { useDataPulse } from "@/infrastructure/api/dataPulseStore";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";
import { IconArrowLeft, IconChevronRight } from "@/presentation/components/ui/Icons";
import { BetStrategyPanel } from "@/presentation/components/predictions/BetStrategyPanel";
import { ComboTicketPanel } from "@/presentation/components/predictions/ComboTicketPanel";
import { LiveActionNowPanel } from "@/presentation/components/predictions/LiveActionNowPanel";
import { LiveMarketCards } from "@/presentation/components/predictions/LiveMarketCards";
import { LiveModelPanel } from "@/presentation/components/predictions/LiveModelPanel";
import {
  LiveOpenBetMonitor,
  createRegisteredBetId,
  type RegisteredBetEntry,
} from "@/presentation/components/predictions/LiveOpenBetMonitor";
import { LivePlainGuide } from "@/presentation/components/predictions/LivePlainGuide";
import { LiveScoreHeatmap } from "@/presentation/components/predictions/LiveScoreHeatmap";
import LiveHedgeAlert from "@/presentation/components/predictions/LiveHedgeAlert";
import LiveAgainstModelAlert from "@/presentation/components/predictions/LiveAgainstModelAlert";
import { draftAgainstModelAlert, normalizeH2hOutcome } from "@/presentation/utils/againstModelBet";

const POLL_MS = 15_000;
const SCORE_POLL_MS = 10_000;
const MAX_OPEN_BETS = 2;

type BetDraft = {
  market: string;
  outcome: string;
  stake: number;
  oddsPlaced: number;
  offeredCashout: number | null;
};

const DEFAULT_BET_DRAFT: BetDraft = {
  market: "h2h",
  outcome: "X",
  stake: 10,
  oddsPlaced: 2,
  offeredCashout: null,
};

function betToDraft(bet: RegisteredBetEntry): BetDraft {
  return {
    market: bet.market,
    outcome: bet.outcome,
    stake: bet.stake,
    oddsPlaced: bet.oddsPlaced,
    offeredCashout: bet.offeredCashout ?? null,
  };
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

function formatOddsLine(odds: Record<string, number>): string {
  const parts: string[] = [];
  if (odds["1"]) parts.push(`1 ${odds["1"].toFixed(2)}`);
  if (odds["X"]) parts.push(`X ${odds["X"].toFixed(2)}`);
  if (odds["2"]) parts.push(`2 ${odds["2"].toFixed(2)}`);
  return parts.join(" · ") || "—";
}

export function LiveInPlayPage() {
  const { eventId: eventIdParam } = useParams();
  const eventId = Number.parseInt(eventIdParam ?? "", 10);
  const pulse = useDataPulse();

  const [bankrollDraft, setBankrollDraft] = useState(1000);
  const [appliedBankroll, setAppliedBankroll] = useState(1000);
  const bankrollDirty = bankrollDraft !== appliedBankroll;
  const [registeredBets, setRegisteredBets] = useState<RegisteredBetEntry[]>([]);
  const [trackBet, setTrackBet] = useState(false);
  const [betDraft, setBetDraft] = useState<BetDraft>(DEFAULT_BET_DRAFT);
  const [formMode, setFormMode] = useState<"add" | string | null>(null);
  const [betSectionOpen, setBetSectionOpen] = useState(false);

  const openBetsQuery = useQuery({
    queryKey: ["user-open-bets"],
    queryFn: () => getUserOpenBetsUseCase.execute(),
  });

  const adviceQuery = useQuery({
    queryKey: ["superbet-live-advice", eventId, appliedBankroll],
    queryFn: () =>
      getSuperbetLiveAdviceUseCase.execute({
        eventId,
        phase: "friendly",
        bankroll: appliedBankroll,
      }),
    enabled: Number.isFinite(eventId) && eventId > 0,
    staleTime: 10_000,
    refetchInterval: (query) =>
      query.state.data?.isFinished ? false : POLL_MS,
  });

  const scoreTickQuery = useQuery({
    queryKey: ["superbet-event-score", eventId],
    queryFn: () => getSuperbetEventUseCase.execute({ eventId, saveBronze: false }),
    enabled: Number.isFinite(eventId) && eventId > 0,
    staleTime: 5_000,
    refetchInterval: (query) =>
      query.state.data?.isLive === false ? false : SCORE_POLL_MS,
  });

  const data = adviceQuery.data;
  const scoreTick = scoreTickQuery.data;
  const isLoading = adviceQuery.isLoading && !data;

  const liveHeader = useMemo(() => {
    if (!data) return null;
    const adviceCapturedMs = data.capturedAt ? Date.parse(data.capturedAt) : 0;
    const tickCapturedMs = scoreTick?.capturedAt ? Date.parse(scoreTick.capturedAt) : 0;
    const useTick =
      scoreTick != null &&
      Number.isFinite(tickCapturedMs) &&
      tickCapturedMs >= adviceCapturedMs;
    return {
      currentScore: useTick ? scoreTick.currentScore : data.currentScore,
      minute: useTick ? scoreTick.minute : data.minute,
      periodLabel: useTick ? scoreTick.periodLabel : data.periodLabel,
      h2hOdds: useTick ? scoreTick.h2hOdds : data.h2hOdds,
      rawMarketCount: useTick ? scoreTick.rawMarketCount : data.rawMarketCount,
      capturedAt: useTick ? scoreTick.capturedAt : data.capturedAt,
      scoreIsFresh: useTick,
    };
  }, [data, scoreTick]);

  useEffect(() => {
    if (!scoreTick?.currentScore || !data?.currentScore) return;
    if (scoreTick.currentScore === data.currentScore) return;
    if (adviceQuery.isFetching || data.isFinished) return;
    void adviceQuery.refetch();
  }, [
    scoreTick?.currentScore,
    data?.currentScore,
    data?.isFinished,
    adviceQuery.isFetching,
    adviceQuery.refetch,
  ]);

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

  const showBetForm = trackBet && formMode != null;
  const canAddBet = trackBet && displayBets.length < MAX_OPEN_BETS && formMode === null;
  const betAnalysisActive =
    trackBet && displayBets.some((b) => b.autoMonitor && formMode !== b.id);

  const betAdviceQueries = useQueries({
    queries: displayBets.map((bet) => ({
      queryKey: [
        "superbet-live-bet",
        eventId,
        appliedBankroll,
        bet.id,
        bet.market,
        bet.outcome,
        bet.stake,
        bet.oddsPlaced,
      ],
      queryFn: () =>
        getSuperbetLiveAdviceUseCase.execute({
          eventId,
          phase: "friendly",
          bankroll: appliedBankroll,
          market: bet.market,
          outcome: bet.outcome,
          stake: bet.stake,
          oddsPlaced: bet.oddsPlaced,
        }),
      enabled:
        Number.isFinite(eventId) &&
        eventId > 0 &&
        trackBet &&
        bet.autoMonitor &&
        formMode !== bet.id,
      staleTime: 10_000,
      refetchInterval: (query: { state: { data?: { isFinished?: boolean } } }) =>
        query.state.data?.isFinished ? false : POLL_MS,
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
    const params = new URLSearchParams({
      source: "friendly",
      phase: "friendly",
      superbet: String(eventId),
      liveHome: String(data.currentScore?.split("x")[0] ?? "0"),
      liveAway: String(data.currentScore?.split("x")[1] ?? "0"),
      minute: String(data.minute),
    });
    return `/match/${encodeURIComponent(data.homeTeam)}/${encodeURIComponent(data.awayTeam)}?${params}`;
  }, [data, eventId]);

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
    <PageTransition className="space-y-4">
      {/* ── Cabeçalho de navegação ── */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to="/ao-vivo"
          className="inline-flex items-center gap-2 text-sm text-slate-400 transition-colors hover:text-white"
        >
          <IconArrowLeft className="h-4 w-4" />
          Voltar ao vivo
        </Link>
        <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
          {pulse?.wcModelsReady === false && (
            <span className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-amber-300">
              Modelo WC indisponível
            </span>
          )}
          <span>
            Superbet #{eventId}
            {data?.betradarId ? ` · Betradar ${data.betradarId}` : ""}
          </span>
        </div>
      </div>

      {isLoading ? (
        <DashboardSkeleton />
      ) : adviceQuery.isError ? (
        <ErrorState
          message={
            adviceQuery.error instanceof Error
              ? adviceQuery.error.message
              : "Falha ao capturar jogo na Superbet"
          }
          onRetry={() => adviceQuery.refetch()}
        />
      ) : data ? (
        <>
          {/* ── 1. MATCH HEADER ── */}
          <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex min-w-0 flex-1 items-center gap-3">
                <TeamFlag team={data.homeTeam} size={36} />
                <div className="min-w-0 text-left">
                  <p className="truncate text-sm font-semibold text-white">{data.homeTeam}</p>
                </div>
                <div className="px-2 text-center">
                  <p className="font-mono text-2xl font-bold text-white">
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
                <TeamFlag team={data.awayTeam} size={36} />
              </div>
              <div className="text-right text-[11px] text-slate-500">
                <p>
                  Odds:{" "}
                  <span className="text-slate-300">
                    {formatOddsLine(liveHeader?.h2hOdds ?? data.h2hOdds)}
                  </span>
                </p>
                <p>{liveHeader?.rawMarketCount ?? data.rawMarketCount} mercados</p>
                <p className="mt-0.5 flex items-center justify-end gap-2">
                  <span>
                    Captura {formatCapturedAt(liveHeader?.capturedAt ?? data.capturedAt)}
                    {data.isLive
                      ? liveHeader?.scoreIsFresh
                        ? ` · placar ${SCORE_POLL_MS / 1000}s · modelo ${POLL_MS / 1000}s`
                        : ` · refresh ${POLL_MS / 1000}s`
                      : ""}
                  </span>
                  <button
                    onClick={() => {
                      void scoreTickQuery.refetch();
                      void adviceQuery.refetch();
                    }}
                    disabled={adviceQuery.isFetching || scoreTickQuery.isFetching}
                    title="Atualizar agora"
                    className="rounded p-0.5 text-slate-500 transition hover:text-slate-300 disabled:opacity-40"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      className={`h-3.5 w-3.5 ${adviceQuery.isFetching ? "animate-spin" : ""}`}
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
              <p className="mt-3 text-sm text-slate-400">Jogo encerrado — polling pausado.</p>
            )}

            {/* ── Barras de probabilidade 1X2 ── */}
            {(data.inplaySummary.probFinalHome > 0 || data.inplaySummary.probFinalAway > 0) && (
              <div className="mt-3">
                <div className="flex overflow-hidden rounded-xl" style={{ height: "28px" }}>
                  {[
                    {
                      key: "1",
                      label: data.homeTeam,
                      prob: data.inplaySummary.probFinalHome,
                      bg: "rgba(0,255,136,0.18)",
                      text: "#00ff88",
                    },
                    {
                      key: "X",
                      label: "Empate",
                      prob: data.inplaySummary.probFinalDraw,
                      bg: "rgba(251,191,36,0.18)",
                      text: "#fbbf24",
                    },
                    {
                      key: "2",
                      label: data.awayTeam,
                      prob: data.inplaySummary.probFinalAway,
                      bg: "rgba(56,189,248,0.18)",
                      text: "#38bdf8",
                    },
                  ].map(({ key, label, prob, bg, text }) => {
                    const pct = prob * 100;
                    if (pct < 1) return null;
                    return (
                      <div
                        key={key}
                        style={{ width: `${pct.toFixed(1)}%`, backgroundColor: bg, minWidth: "36px" }}
                        className="relative flex items-center justify-center transition-all duration-500"
                        title={`${label}: ${pct.toFixed(0)}%`}
                      >
                        <span
                          className="font-mono text-[10px] font-bold"
                          style={{ color: text }}
                        >
                          {pct.toFixed(0)}%
                        </span>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-1 flex justify-between px-0.5 text-[9px] text-slate-600">
                  <span className="max-w-[35%] truncate text-left">{data.homeTeam}</span>
                  <span>Empate</span>
                  <span className="max-w-[35%] truncate text-right">{data.awayTeam}</span>
                </div>
              </div>
            )}
          </section>

          {/* ── 2. HERO CTA ── */}
          <LiveActionNowPanel data={data} trackBet={betAnalysisActive} />

          {/* ── 2a. ALERTA — aposta contra palpite do modelo ── */}
          <LiveAgainstModelAlert alerts={againstModelAlerts} />

          {/* ── 2b. ALERTA DE HEDGE (apostas do usuário) ── */}
          <LiveHedgeAlert report={data?.hedgeReport ?? null} />

          {/* ── 3. COLUNA DUPLA: Mercados | Modelo + Casa ── */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_340px]">
            <section className="rounded-2xl border border-white/8 bg-white/[0.02] p-4">
              <LiveMarketCards data={data} />
            </section>
            <LiveModelPanel data={data} />
          </div>

          {/* ── 3b. HEATMAP DE PLACARES ── */}
          <LiveScoreHeatmap data={data} />

          {/* ── 4. GUIA RÁPIDO (colapsável) ── */}
          <LivePlainGuide data={data} trackBet={betAnalysisActive} />

          {/* ── 5. BILHETE COMBO KXL ── */}
          <ComboTicketPanel homeTeam={data.homeTeam} awayTeam={data.awayTeam} strategy={data.strategy} />

          {/* ── 6. ESTRATÉGIA ── */}
          <BetStrategyPanel strategy={data.strategy} />

          {/* ── 7. MINHA APOSTA / CASHOUT (colapsável) ── */}
          <section className="rounded-2xl border border-white/8 bg-white/[0.02]">
            <button
              type="button"
              onClick={() => setBetSectionOpen((v) => !v)}
              className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left"
              aria-expanded={betSectionOpen}
            >
              <div>
                <h2 className="text-sm font-semibold text-white">
                  Minha aposta — monitorar cash-out
                </h2>
                <p className="mt-0.5 text-xs text-slate-500">
                  {displayBets.length > 0
                    ? `${displayBets.length} bilhete${displayBets.length > 1 ? "s" : ""} cadastrado${displayBets.length > 1 ? "s" : ""} · atualiza a cada ${POLL_MS / 1000}s`
                    : `Cadastre até ${MAX_OPEN_BETS} bilhetes e monitore o ponto ideal de cash-out`}
                </p>
              </div>
              <div className="flex items-center gap-2">
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

                {trackBet && displayBets.length > 0 && (
                  <div className="mb-4 space-y-6">
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
                          pollSeconds={POLL_MS / 1000}
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
                    <label className="mb-3 flex max-w-xs flex-col gap-1 text-xs text-slate-400">
                      Cash-out oferecido na Superbet (R$) — opcional
                      <input
                        type="number"
                        min={0}
                        step={0.01}
                        placeholder="ex.: 4,31"
                        value={betDraft.offeredCashout ?? ""}
                        onChange={(e) => {
                          const raw = e.target.value;
                          setBetDraft((d) => ({
                            ...d,
                            offeredCashout: raw === "" ? null : Number(raw),
                          }));
                        }}
                        className="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 font-mono text-sm text-white"
                      />
                    </label>
                    <div className="mb-4 flex flex-wrap items-center gap-3">
                      <button
                        type="button"
                        onClick={() => {
                          if (formMode === "add") {
                            setRegisteredBets((prev) =>
                              [
                                ...prev,
                                {
                                  ...betDraft,
                                  id: createRegisteredBetId(),
                                  autoMonitor: true,
                                },
                              ].slice(0, MAX_OPEN_BETS),
                            );
                          } else if (typeof formMode === "string") {
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
                          setFormMode(null);
                        }}
                        className="rounded-lg border border-neon-green/40 bg-neon-green/15 px-4 py-2 text-sm font-semibold text-neon-green transition-colors hover:bg-neon-green/25"
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
      ) : null}

      {adviceQuery.isFetching && data && (
        <p className="text-center text-[11px] text-slate-500" aria-live="polite">
          Atualizando snapshot Superbet…
        </p>
      )}
    </PageTransition>
  );
}
