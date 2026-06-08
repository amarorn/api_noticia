import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQueries, useQuery } from "@tanstack/react-query";
import { getSuperbetLiveAdviceUseCase } from "@/application/container";
import { useDataPulse } from "@/infrastructure/api/dataPulseStore";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";
import { IconArrowLeft, IconChevronRight } from "@/presentation/components/ui/Icons";
import { BetStrategyPanel } from "@/presentation/components/predictions/BetStrategyPanel";
import { LiveActionNowPanel } from "@/presentation/components/predictions/LiveActionNowPanel";
import { LiveMarketsGuidePanel } from "@/presentation/components/predictions/LiveMarketsGuidePanel";
import {
  LiveOpenBetMonitor,
  createRegisteredBetId,
  type RegisteredBetEntry,
} from "@/presentation/components/predictions/LiveOpenBetMonitor";
import { LivePlainGuide } from "@/presentation/components/predictions/LivePlainGuide";
import { LiveStrategyDashboard } from "@/presentation/components/predictions/LiveStrategyDashboard";
import { formatPercent } from "@/presentation/theme";

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

function teamLabel(name: string, maxLen = 18): string {
  const trimmed = name.trim();
  if (trimmed.length <= maxLen) return trimmed;
  return `${trimmed.slice(0, maxLen - 1)}…`;
}

function h2hOutcomeLabel(
  key: "1" | "X" | "2",
  homeTeam: string,
  awayTeam: string,
): string {
  if (key === "1") return teamLabel(homeTeam);
  if (key === "2") return teamLabel(awayTeam);
  return "Empate";
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
    <PageTransition className="space-y-5">
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
          <section className="rounded-2xl border border-amber-500/20 bg-gradient-to-br from-amber-500/8 to-transparent p-5">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex min-w-0 flex-1 items-center gap-3">
                <TeamFlag team={data.homeTeam} size={36} />
                <div className="min-w-0 text-center">
                  <p className="truncate font-semibold text-white">{data.homeTeam}</p>
                </div>
                <div className="px-2 text-center">
                  <p className="font-mono text-2xl font-bold text-white">
                    {data.currentScore?.replace("x", " × ") ?? "0 × 0"}
                  </p>
                  <p className="mt-1 text-xs font-semibold text-amber-300">
                    {data.minute}&apos;{data.periodLabel ? ` · ${data.periodLabel}` : ""}
                  </p>
                </div>
                <div className="min-w-0 text-center">
                  <p className="truncate font-semibold text-white">{data.awayTeam}</p>
                </div>
                <TeamFlag team={data.awayTeam} size={36} />
              </div>
              <div className="text-right text-xs text-slate-400">
                <p>Odds mercado: {formatOddsLine(data.h2hOdds)}</p>
                <p>{data.rawMarketCount} mercados</p>
                <p className="mt-1">
                  Captura {formatCapturedAt(data.capturedAt)}
                  {data.isLive ? ` · refresh ${POLL_MS / 1000}s` : ""}
                </p>
              </div>
            </div>
            {data.isFinished && (
              <p className="mt-3 text-sm text-slate-400">Jogo encerrado — polling pausado.</p>
            )}
          </section>

          <LiveActionNowPanel data={data} trackBet={betAnalysisActive} />

          <LivePlainGuide data={data} trackBet={betAnalysisActive} />

          <LiveStrategyDashboard data={data} />

          <LiveMarketsGuidePanel data={data} />

          <section className="rounded-2xl border border-white/8 bg-white/[0.02] p-5">
            <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-white">Sua aposta (cash-out)</h2>
                <p className="text-xs text-slate-500">
                  Cadastre até {MAX_OPEN_BETS} bilhetes (ex.: Empate + Jordânia). Monitore cash-out
                  a cada {POLL_MS / 1000}s.
                </p>
              </div>
              <div className="flex flex-wrap items-end gap-3">
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
                    Digitar não recarrega a página — clique Aplicar para recalcular aportes
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
            </div>

            {trackBet && registeredBets.length > 0 && (
              <div className="mb-4 space-y-6">
                {registeredBets.map((bet, index) =>
                  formMode === bet.id ? null : (
                    <LiveOpenBetMonitor
                      key={bet.id}
                      data={data}
                      bet={bet}
                      cashout={betAdviceQueries[index]?.data?.cashout ?? null}
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
                          prev.map((b) => (b.id === bet.id ? { ...b, autoMonitor: on } : b)),
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
                Marque a opção acima ou clique em adicionar para cadastrar até {MAX_OPEN_BETS}{" "}
                bilhetes do mesmo jogo.
              </p>
            )}
          </section>

          <section className="rounded-2xl border border-violet-500/15 bg-violet-500/[0.04] p-5">
            <h2 className="mb-1 text-sm font-semibold text-white">Posição da casa</h2>
            <p className="mb-4 text-xs text-slate-500">
              Onde a Superbet precifica vs nosso modelo — edge negativo favorece a casa
            </p>

            {data.h2hOverround != null && (
              <p className="mb-3 text-xs text-slate-400">
                Margem 1X2 (overround):{" "}
                <span className="font-mono font-semibold text-violet-300">
                  {(data.h2hOverround * 100).toFixed(1)}%
                </span>
              </p>
            )}

            <div className="mb-4 grid gap-2 sm:grid-cols-3">
              {(["1", "X", "2"] as const).map((key) => {
                const implied = data.h2hImplied[key];
                const odd = data.h2hOdds[key];
                const bench = data.marketBenchmark?.h2h?.[key];
                if (implied == null && odd == null) return null;
                const edgePp = bench ? bench.edge * 100 : null;
                const edgeColor =
                  edgePp == null
                    ? "text-slate-400"
                    : edgePp > 2
                      ? "text-neon-green"
                      : edgePp < -2
                        ? "text-red-400"
                        : "text-slate-300";
                const label = h2hOutcomeLabel(key, data.homeTeam, data.awayTeam);
                const fullLabel =
                  key === "1" ? data.homeTeam : key === "2" ? data.awayTeam : "Empate";
                return (
                  <div
                    key={key}
                    className="rounded-xl border border-white/8 bg-white/[0.03] px-3 py-3"
                  >
                    <p
                      className="truncate text-[10px] uppercase tracking-wider text-slate-500"
                      title={fullLabel}
                    >
                      {label}
                    </p>
                    {odd != null && (
                      <p className="font-mono text-sm text-white">
                        {odd.toFixed(2)}
                        {implied != null && (
                          <span className="ml-2 text-xs text-slate-400">
                            ({formatPercent(implied)})
                          </span>
                        )}
                      </p>
                    )}
                    {bench && (
                      <p className={`mt-1 text-xs ${edgeColor}`}>
                        Modelo {formatPercent(bench.model)} · edge{" "}
                        {edgePp != null ? `${edgePp > 0 ? "+" : ""}${edgePp.toFixed(1)} pp` : "—"}
                      </p>
                    )}
                    {edgePp != null && edgePp < -2 && (
                      <p className="mt-1 text-[10px] text-red-400/80">
                        {fullLabel} — mercado otimista
                      </p>
                    )}
                    {edgePp != null && edgePp > 2 && (
                      <p className="mt-1 text-[10px] text-neon-green/80">Valor p/ apostador</p>
                    )}
                  </div>
                );
              })}
            </div>

            {data.marketBenchmark?.totals &&
              Object.keys(data.marketBenchmark.totals).length > 0 && (
                <div className="mb-4">
                  <p className="mb-2 text-[11px] uppercase tracking-wider text-slate-500">
                    Totais de gols
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(data.marketBenchmark.totals).map(([line, row]) => {
                      const edgePp = row.edgeOver * 100;
                      return (
                        <span
                          key={line}
                          className="rounded-lg border border-white/8 bg-white/[0.03] px-2.5 py-1.5 text-xs text-slate-300"
                        >
                          Over {line}: casa {formatPercent(row.marketOver)} · modelo{" "}
                          {formatPercent(row.modelOver)} ·{" "}
                          <span className={edgePp > 0 ? "text-neon-green" : "text-red-400"}>
                            {edgePp > 0 ? "+" : ""}
                            {edgePp.toFixed(1)} pp
                          </span>
                        </span>
                      );
                    })}
                  </div>
                </div>
              )}

            {Object.keys(data.generosityProbs).length > 0 && (
              <div className="rounded-lg border border-violet-500/20 bg-violet-500/5 px-3 py-2 text-xs text-slate-400">
                Generosity Superbet:{" "}
                {data.generosityProbs.home != null && (
                  <span>
                    {data.homeTeam} {formatPercent(data.generosityProbs.home)}
                  </span>
                )}
                {data.generosityProbs.away != null && (
                  <span className="ml-2">
                    {data.awayTeam} {formatPercent(data.generosityProbs.away)}
                  </span>
                )}
                <span className="ml-2 text-slate-500">(metadado interno da odd)</span>
              </div>
            )}
          </section>

          <section className="rounded-2xl border border-white/8 bg-white/[0.02] p-5">
            <h2 className="mb-1 text-sm font-semibold text-white">Modelo in-play</h2>
            <p className="mb-4 text-xs text-slate-500">
              Probabilidades condicionadas ao placar e minuto atual
            </p>
            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <Stat
                label={teamLabel(data.homeTeam)}
                title={data.homeTeam}
                value={formatPercent(data.inplaySummary.probFinalHome)}
              />
              <Stat label="Empate" value={formatPercent(data.inplaySummary.probFinalDraw)} />
              <Stat
                label={teamLabel(data.awayTeam)}
                title={data.awayTeam}
                value={formatPercent(data.inplaySummary.probFinalAway)}
              />
              {data.inplaySummary.over25 != null && (
                <Stat label="Over 2.5" value={formatPercent(data.inplaySummary.over25)} />
              )}
              {data.inplaySummary.btts != null && (
                <Stat label="BTTS" value={formatPercent(data.inplaySummary.btts)} />
              )}
              {data.inplaySummary.probNextGoalHome != null && (
                <Stat
                  label={`Gol ${teamLabel(data.homeTeam, 12)}`}
                  title={`Próximo gol ${data.homeTeam}`}
                  value={formatPercent(data.inplaySummary.probNextGoalHome)}
                />
              )}
              {data.inplaySummary.probNextGoalAway != null && (
                <Stat
                  label={`Gol ${teamLabel(data.awayTeam, 12)}`}
                  title={`Próximo gol ${data.awayTeam}`}
                  value={formatPercent(data.inplaySummary.probNextGoalAway)}
                />
              )}
            </div>
          </section>

          <BetStrategyPanel strategy={data.strategy} />

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

function Stat({ label, value, title }: { label: string; value: string; title?: string }) {
  return (
    <div className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2">
      <p
        className="truncate text-[10px] uppercase tracking-wider text-slate-500"
        title={title ?? label}
      >
        {label}
      </p>
      <p className="font-mono text-sm font-semibold text-white">{value}</p>
    </div>
  );
}
