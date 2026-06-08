import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQueries, useQuery } from "@tanstack/react-query";
import { getSuperbetLiveAdviceUseCase } from "@/application/container";
import { useDataPulse } from "@/infrastructure/api/dataPulseStore";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";
import { IconArrowLeft, IconChevronRight } from "@/presentation/components/ui/Icons";
import { BetStrategyPanel } from "@/presentation/components/predictions/BetStrategyPanel";
import { LiveActionNowPanel } from "@/presentation/components/predictions/LiveActionNowPanel";
import { LiveMarketCards } from "@/presentation/components/predictions/LiveMarketCards";
import { LiveModelPanel } from "@/presentation/components/predictions/LiveModelPanel";
import {
  LiveOpenBetMonitor,
  createRegisteredBetId,
  type RegisteredBetEntry,
} from "@/presentation/components/predictions/LiveOpenBetMonitor";
import { LivePlainGuide } from "@/presentation/components/predictions/LivePlainGuide";

const POLL_MS = 25_000;
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

  const showBetForm = trackBet && formMode != null;
  const canAddBet = trackBet && registeredBets.length < MAX_OPEN_BETS && formMode === null;
  const betAnalysisActive =
    trackBet && registeredBets.some((b) => b.autoMonitor && formMode !== b.id);

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

  const betAdviceQueries = useQueries({
    queries: registeredBets.map((bet) => ({
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

  const data = adviceQuery.data;
  const isLoading = adviceQuery.isLoading && !data;

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
                    {data.currentScore?.replace("x", " × ") ?? "0 × 0"}
                  </p>
                  <p className="mt-0.5 flex items-center justify-center gap-1.5 text-xs font-semibold">
                    {data.isLive && !data.isFinished && (
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red-400" />
                    )}
                    <span className="text-amber-300">
                      {data.minute}&apos;
                      {data.periodLabel ? ` · ${data.periodLabel}` : ""}
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
                  <span className="text-slate-300">{formatOddsLine(data.h2hOdds)}</span>
                </p>
                <p>{data.rawMarketCount} mercados</p>
                <p className="mt-0.5">
                  Captura {formatCapturedAt(data.capturedAt)}
                  {data.isLive ? ` · refresh ${POLL_MS / 1000}s` : ""}
                </p>
              </div>
            </div>
            {data.isFinished && (
              <p className="mt-3 text-sm text-slate-400">Jogo encerrado — polling pausado.</p>
            )}
          </section>

          {/* ── 2. HERO CTA ── */}
          <LiveActionNowPanel data={data} trackBet={betAnalysisActive} />

          {/* ── 3. COLUNA DUPLA: Mercados | Modelo + Casa ── */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_340px]">
            <section className="rounded-2xl border border-white/8 bg-white/[0.02] p-4">
              <LiveMarketCards data={data} />
            </section>
            <LiveModelPanel data={data} />
          </div>

          {/* ── 4. GUIA RÁPIDO (colapsável) ── */}
          <LivePlainGuide data={data} trackBet={betAnalysisActive} />

          {/* ── 5. ESTRATÉGIA ── */}
          <BetStrategyPanel strategy={data.strategy} />

          {/* ── 6. MINHA APOSTA / CASHOUT (colapsável) ── */}
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
                  {registeredBets.length > 0
                    ? `${registeredBets.length} bilhete${registeredBets.length > 1 ? "s" : ""} cadastrado${registeredBets.length > 1 ? "s" : ""} · atualiza a cada ${POLL_MS / 1000}s`
                    : `Cadastre até ${MAX_OPEN_BETS} bilhetes e monitore o ponto ideal de cash-out`}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {registeredBets.length > 0 && (
                  <span className="rounded-full bg-neon-green/15 px-2 py-0.5 text-[11px] font-semibold text-neon-green">
                    {registeredBets.length} ativo{registeredBets.length > 1 ? "s" : ""}
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
                        } else if (registeredBets.length === 0) {
                          setBetDraft(DEFAULT_BET_DRAFT);
                          setFormMode("add");
                        }
                      }}
                      className="rounded border-white/20"
                    />
                    Tenho aposta aberta
                  </label>
                </div>

                {trackBet && registeredBets.length > 0 && (
                  <div className="mb-4 space-y-6">
                    {registeredBets.map((bet, index) =>
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
                          totalBets={registeredBets.length}
                          isFetching={betAdviceQueries[index]?.isFetching ?? false}
                          pollSeconds={POLL_MS / 1000}
                          onEdit={() => {
                            setBetDraft(betToDraft(bet));
                            setFormMode(bet.id);
                          }}
                          onRemove={() => {
                            setRegisteredBets((prev) => {
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
                    + Adicionar outra aposta ({registeredBets.length}/{MAX_OPEN_BETS})
                  </button>
                )}

                {showBetForm && (
                  <>
                    <p className="mb-3 text-xs text-slate-500">
                      {formMode === "add"
                        ? `Nova aposta (${registeredBets.length + 1} de ${MAX_OPEN_BETS})`
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
                      {registeredBets.length > 0 && (
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

                {trackBet && registeredBets.length === 0 && formMode === null && (
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
