import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQueries, useQuery } from "@tanstack/react-query";
import {
  getBaseballSuperbetLiveAdviceUseCase,
  getUserOpenBetsUseCase,
  refreshOpenBetsCashoutsUseCase,
} from "@/application/container";
import type {
  BaseballMarketBenchmark,
  BaseballSuperbetLiveAdvice,
} from "@/domain/entities";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { useLiveDashboardChrome } from "@/presentation/components/layout/liveDashboardChromeContext";
import { LiveCopilotPanel } from "@/presentation/components/live-dashboard/LiveCopilotPanel";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";
import { useNotifications } from "@/presentation/components/ui/notifications";
import { useBaseballLiveAdviceQueries } from "@/presentation/hooks/useBaseballLiveAdviceQueries";
import { useCashoutRiskAlerts } from "@/presentation/hooks/useCashoutRiskAlerts";
import { useCashoutTargetAlerts } from "@/presentation/hooks/useCashoutTargetAlerts";
import { useCopilotAlertsPreference } from "@/presentation/hooks/useCopilotAlertsPreference";
import { getCashoutAlertConfig } from "@/presentation/utils/cashoutAlertStorage";
import { useLiveCopilotActionAlerts } from "@/presentation/hooks/useLiveCopilotActionAlerts";
import { useLiveCopilotAgentSession } from "@/presentation/hooks/useLiveCopilotAgentSession";
import { useLiveCopilotQuery } from "@/presentation/hooks/useLiveCopilotQuery";
import {
  BaseballLiveOpenBetMonitor,
  normalizeBaseballAdviceMarket,
} from "@/presentation/components/predictions/BaseballLiveOpenBetMonitor";
import { BaseballDataQualityBanner } from "@/presentation/components/predictions/BaseballDataQualityBanner";
import { BaseballMarketScanPanel } from "@/presentation/components/predictions/BaseballMarketScanPanel";
import {
  createRegisteredBetId,
  type RegisteredBetEntry,
} from "@/presentation/components/predictions/LiveOpenBetMonitor";

const LIVE_POLL_MS = 8_000;
const CASHOUT_REFRESH_MS = 45_000;

type BetDraft = {
  market: string;
  outcome: string;
  stake: number;
  oddsPlaced: number;
};

const DEFAULT_BET_DRAFT: BetDraft = {
  market: "moneyline",
  outcome: "1",
  stake: 50,
  oddsPlaced: 2.0,
};

const BASEBALL_MARKET_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "moneyline", label: "Vencedor (ML)" },
  { value: "spread", label: "Run line" },
  { value: "total_runs", label: "Total de corridas" },
  { value: "team_total_runs", label: "Total por time" },
  { value: "f5_total", label: "Total F5" },
];

const PERIOD_MARKETS = new Set([
  "f5_total",
  "f5_moneyline",
  "f5_spread",
  "inning_total",
  "inning_moneyline",
  "highest_inning",
  "run_n",
  "team_total_runs",
]);

function formatPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(0)}%`;
}

function formatNum(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

function formatCapturedAt(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date(iso));
  } catch {
    return "—";
  }
}

const POSTURE_LABELS: Record<string, string> = {
  atacar: "Atacar",
  neutro: "Neutro",
  defensivo: "Defensivo",
};

const POSTURE_STYLES: Record<string, string> = {
  atacar: "border-emerald-500/40 bg-emerald-500/15 text-emerald-300",
  neutro: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  defensivo: "border-red-500/40 bg-red-500/15 text-red-300",
};

function EdgeBadge({ edge }: { edge: number }) {
  const pp = edge * 100;
  const tone =
    Math.abs(pp) < 1
      ? "text-slate-400"
      : pp > 0
        ? "text-emerald-300"
        : "text-rose-300";
  return (
    <span className={`font-mono text-xs font-semibold ${tone}`}>
      {pp > 0 ? "+" : ""}
      {pp.toFixed(1)} pp
    </span>
  );
}

function MarketEdgeCards({
  data,
  benchmark,
}: {
  data: BaseballSuperbetLiveAdvice;
  benchmark: BaseballMarketBenchmark | null;
}) {
  const mlHome = data.h2hOdds["1"];
  const mlAway = data.h2hOdds["2"];
  const modelHome = data.inplaySummary.probHomeWin;
  const modelAway = data.inplaySummary.probAwayWin;
  const mlEdgeHome = benchmark?.moneyline?.["1"]?.edge;
  const mlEdgeAway = benchmark?.moneyline?.["2"]?.edge;

  const totalLine = data.inplaySummary.marketTotalLine;
  const totalKey =
    totalLine != null
      ? Object.keys(data.totalRunsOdds).find(
          (k) => Math.abs(Number(k) - totalLine) < 1e-6,
        ) ?? String(totalLine)
      : Object.keys(data.totalRunsOdds)[0];
  const totalOverOdd = totalKey ? data.totalRunsOdds[totalKey]?.over : undefined;
  const totalBench = totalKey ? benchmark?.totals?.[totalKey] : undefined;

  const spreadKey = Object.keys(data.spreadOdds)[0];
  const spreadHomeOdd = spreadKey ? data.spreadOdds[spreadKey]?.home : undefined;
  const spreadBench = spreadKey ? benchmark?.spread?.[spreadKey] : undefined;
  const spreadLine = data.inplaySummary.marketSpreadLine;

  return (
    <section className="grid gap-3 sm:grid-cols-3">
      <div className="rounded-xl border border-white/8 bg-black/25 p-4">
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Vencedor (ML)
        </div>
        <div className="space-y-2 text-sm">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate text-slate-300">{data.homeTeam}</span>
            <div className="flex items-center gap-2">
              <span className="font-mono text-white">
                {mlHome != null ? mlHome.toFixed(2) : "—"}
              </span>
              <span className="text-slate-500">{formatPct(modelHome)}</span>
              {mlEdgeHome != null ? <EdgeBadge edge={mlEdgeHome} /> : null}
            </div>
          </div>
          <div className="flex items-center justify-between gap-2">
            <span className="truncate text-slate-300">{data.awayTeam}</span>
            <div className="flex items-center gap-2">
              <span className="font-mono text-white">
                {mlAway != null ? mlAway.toFixed(2) : "—"}
              </span>
              <span className="text-slate-500">{formatPct(modelAway)}</span>
              {mlEdgeAway != null ? <EdgeBadge edge={mlEdgeAway} /> : null}
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-white/8 bg-black/25 p-4">
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Run line
          {spreadLine != null ? ` · ${spreadLine > 0 ? "+" : ""}${formatNum(spreadLine)}` : ""}
        </div>
        {spreadHomeOdd != null ? (
          <div className="space-y-1 text-sm">
            <div className="flex justify-between gap-2">
              <span className="text-slate-400">Odd casa</span>
              <span className="font-mono text-white">{spreadHomeOdd.toFixed(2)}</span>
            </div>
            {spreadBench ? (
              <>
                <div className="flex justify-between gap-2">
                  <span className="text-slate-400">Modelo cobre</span>
                  <span className="text-slate-200">{formatPct(spreadBench.modelHomeCover)}</span>
                </div>
                <div className="flex justify-between gap-2">
                  <span className="text-slate-400">Edge</span>
                  <EdgeBadge edge={spreadBench.edgeHome} />
                </div>
              </>
            ) : (
              <p className="text-[11px] text-slate-500">Sem edge vs mercado ainda.</p>
            )}
          </div>
        ) : (
          <p className="text-sm text-slate-500">Linha ausente no feed.</p>
        )}
      </div>

      <div className="rounded-xl border border-white/8 bg-black/25 p-4">
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Total de corridas
          {totalLine != null ? ` · ${formatNum(totalLine)}` : ""}
        </div>
        {totalOverOdd != null ? (
          <div className="space-y-1 text-sm">
            <div className="flex justify-between gap-2">
              <span className="text-slate-400">Odd over</span>
              <span className="font-mono text-white">{totalOverOdd.toFixed(2)}</span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-slate-400">Proj. final</span>
              <span className="text-slate-200">{formatNum(data.inplaySummary.expectedTotal)}</span>
            </div>
            {totalBench ? (
              <div className="flex justify-between gap-2">
                <span className="text-slate-400">Edge over</span>
                <EdgeBadge edge={totalBench.edgeOver} />
              </div>
            ) : null}
          </div>
        ) : (
          <p className="text-sm text-slate-500">
            Total do jogo ausente — modelo usa prior inferido.
          </p>
        )}
      </div>
    </section>
  );
}

export function BaseballLiveInPlayPage() {
  const { eventId: eventIdParam } = useParams();
  const eventId = Number(eventIdParam);
  const { setChrome } = useLiveDashboardChrome();
  const [trackBet, setTrackBet] = useState(false);
  const [registeredBets, setRegisteredBets] = useState<RegisteredBetEntry[]>([]);
  const [formMode, setFormMode] = useState<"add" | string | null>(null);
  const [betDraft, setBetDraft] = useState<BetDraft>(DEFAULT_BET_DRAFT);
  const [betSectionOpen, setBetSectionOpen] = useState(false);
  const [alertConfigVersion] = useState(0);
  const { addNotification } = useNotifications();

  const openBetsQuery = useQuery({
    queryKey: ["user-open-bets"],
    queryFn: () => getUserOpenBetsUseCase.execute(),
  });

  const liveQueries = useBaseballLiveAdviceQueries(eventId, 1000);
  const data = liveQueries.data;
  const summary = data?.inplaySummary;
  const displayScore = liveQueries.liveHeader?.currentScore ?? data?.currentScore ?? "0x0";
  const displayInning = liveQueries.liveHeader?.inning ?? data?.inning ?? 0;
  const displayPeriod =
    liveQueries.liveHeader?.periodLabel ?? data?.periodLabel ?? `${displayInning}I`;

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
        market: b.picks[0]?.market ?? "moneyline",
        outcome: b.picks[0]?.outcome ?? "1",
        stake: b.stake,
        oddsPlaced: b.oddsPlaced,
        potentialReturn: b.potentialReturn,
        ticketCode: b.ticketCode,
        cashoutValue: b.cashoutValue,
        autoMonitor: true,
        offeredCashout: b.cashoutValue,
        picks: b.picks.map((p) => ({
          market: p.market,
          outcome: p.outcome,
          label: `${p.market} ${p.outcome}`,
          targetValue: p.targetValue,
        })),
      }));
  }, [openBetsQuery.data, eventId, data?.homeTeam, data?.awayTeam]);

  const displayBets = apiBets.length > 0 ? apiBets : registeredBets;

  useEffect(() => {
    if (apiBets.length > 0) setTrackBet(true);
  }, [apiBets.length]);

  useEffect(() => {
    if (!trackBet || !Number.isFinite(eventId) || eventId <= 0 || data?.isFinished) return;
    let cancelled = false;
    const syncCashouts = async () => {
      try {
        await refreshOpenBetsCashoutsUseCase.execute(eventId);
        if (!cancelled) await openBetsQuery.refetch();
      } catch {
        /* offline */
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
    onAlert: ({ title, body, kind }) => {
      addNotification({
        title,
        body,
        type: kind === "reach" ? "success" : "info",
        source: "cashout",
      });
    },
  });

  useCashoutRiskAlerts({
    bets: displayBets.map((b) => ({
      id: b.id,
      stake: b.stake,
      oddsPlaced: b.oddsPlaced,
      potentialReturn: b.potentialReturn ?? b.stake * b.oddsPlaced,
      cashoutValue: b.offeredCashout ?? b.cashoutValue,
      ticketCode: b.ticketCode,
      picks:
        b.picks?.map((p) => ({
          market: p.market,
          outcome: p.outcome,
          label: p.label,
        })) ?? [{ market: b.market, outcome: b.outcome }],
    })),
    currentScore: data?.currentScore ?? null,
    minute: (data?.inning ?? data?.minute ?? 0) * 10,
    periodLabel: data?.periodLabel,
    enabled: trackBet && Boolean(data?.homeTeam) && !data?.isFinished,
    eventLabel:
      data?.homeTeam && data?.awayTeam ? `${data.homeTeam} x ${data.awayTeam}` : undefined,
  });

  const activeAlertCount = useMemo(
    () => displayBets.filter((b) => getCashoutAlertConfig(b.id).enabled).length,
    [displayBets, alertConfigVersion],
  );

  const betAdviceQueries = useQueries({
    queries: displayBets.map((bet) => ({
      queryKey: [
        "baseball-live-bet",
        eventId,
        bet.id,
        bet.market,
        bet.outcome,
        bet.stake,
        bet.oddsPlaced,
      ],
      queryFn: () =>
        getBaseballSuperbetLiveAdviceUseCase.execute({
          eventId,
          bankroll: 1000,
          fast: false,
          market: normalizeBaseballAdviceMarket(bet.market),
          outcome: bet.outcome,
          stake: bet.stake,
          oddsPlaced: bet.oddsPlaced,
        }),
      enabled:
        Number.isFinite(eventId) &&
        eventId > 0 &&
        trackBet &&
        bet.autoMonitor &&
        !data?.isFinished,
      staleTime: 10_000,
      refetchInterval: (query: { state: { data?: { isFinished?: boolean } } }) =>
        query.state.data?.isFinished ? false : LIVE_POLL_MS,
    })),
  });

  useEffect(() => {
    setChrome({
      isLive: Boolean(data?.isLive),
      lastUpdate: formatCapturedAt(liveQueries.liveHeader?.capturedAt ?? data?.capturedAt),
      nextUpdate: `${Math.round(liveQueries.pollMs.fast / 1000)}s`,
      isFetching: liveQueries.isFetching,
      onRefresh: () => {
        void liveQueries.refetch();
      },
    });
    return () => setChrome(null);
  }, [
    data?.isLive,
    data?.capturedAt,
    liveQueries.liveHeader?.capturedAt,
    liveQueries.isFetching,
    liveQueries.refetch,
    liveQueries.pollMs.fast,
    setChrome,
  ]);

  const topAportes = useMemo(() => data?.aportes ?? [], [data?.aportes]);
  const betAportes = useMemo(
    () => topAportes.filter((a) => a.action === "apostar"),
    [topAportes],
  );
  const periodAportes = useMemo(
    () => topAportes.filter((a) => PERIOD_MARKETS.has(a.market)),
    [topAportes],
  );

  const headerIsLive = Boolean(data?.isLive && !data?.isFinished);
  const { alertsActive: copilotAlertsActive } = useCopilotAlertsPreference();
  const copilotQuery = useLiveCopilotQuery({
    eventId,
    sport: "baseball",
    bankroll: 1000,
    enabled: headerIsLive,
  });
  useLiveCopilotActionAlerts(copilotQuery.data, {
    eventId,
    homeTeam: data?.homeTeam,
    awayTeam: data?.awayTeam,
    enabled: headerIsLive && copilotAlertsActive,
  });
  const { displayCopilot, agentChat } = useLiveCopilotAgentSession({
    eventId,
    sport: "baseball",
    bankroll: 1000,
    enabled: headerIsLive,
    baseCopilot: copilotQuery.data,
  });

  if (!Number.isFinite(eventId) || eventId <= 0) {
    return (
      <PageTransition>
        <ErrorState message="Evento inválido." />
      </PageTransition>
    );
  }

  return (
    <PageTransition>
      <div className="mx-auto max-w-5xl space-y-6 px-4 py-6">
        <div className="flex items-center justify-between gap-3">
          <Link to="/ao-vivo" className="text-sm text-slate-400 hover:text-white">
            ← Ao vivo
          </Link>
          {data?.superbetStale ? (
            <span className="rounded-full bg-amber-500/15 px-2.5 py-1 text-[11px] text-amber-300">
              Snapshot stale
            </span>
          ) : null}
          {data?.scoreStale?.scoreStale ? (
            <span
              className="rounded-full bg-rose-500/15 px-2.5 py-1 text-[11px] text-rose-300"
              title={data.scoreStale.warnings.join(" ")}
            >
              Placar defasado
            </span>
          ) : null}
          {liveQueries.reactiveBoosted ? (
            <span className="rounded-full bg-sky-500/15 px-2.5 py-1 text-[11px] text-sky-300">
              poll acelerado
            </span>
          ) : null}
        </div>

        {liveQueries.isLoading ? (
          <DashboardSkeleton />
        ) : liveQueries.isError || !data ? (
          <ErrorState
            message={
              liveQueries.error instanceof Error
                ? liveQueries.error.message
                : "Falha ao carregar advice de beisebol"
            }
            onRetry={() => liveQueries.refetch()}
          />
        ) : (
          <>
            <section className="rounded-2xl border border-white/10 bg-black/30 p-5">
              <div className="mb-2 flex flex-wrap items-center gap-2 text-xs uppercase tracking-wider text-emerald-400/80">
                <span>
                  Beisebol · {displayPeriod}
                  {data.isLive ? " · ao vivo" : ""}
                  {liveQueries.adviceSource === "fast" && data.isLive ? " · modelo rápido" : ""}
                </span>
                {summary?.scoreAdapted ? (
                  <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2 py-0.5 text-[10px] font-semibold normal-case text-cyan-200">
                    λ box score
                  </span>
                ) : null}
              </div>
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex min-w-0 items-center gap-3">
                  <TeamFlag team={data.homeTeam} size={36} />
                  <div>
                    <div className="font-semibold text-white">{data.homeTeam}</div>
                    <div className="text-xs text-slate-500">mandante</div>
                  </div>
                </div>
                <div className="font-mono text-3xl font-black text-white">{displayScore}</div>
                <div className="flex min-w-0 items-center gap-3">
                  <div className="text-right">
                    <div className="font-semibold text-white">{data.awayTeam}</div>
                    <div className="text-xs text-slate-500">visitante</div>
                  </div>
                  <TeamFlag team={data.awayTeam} size={36} />
                </div>
              </div>
            </section>

            <BaseballDataQualityBanner
              data={data}
              adviceSource={liveQueries.adviceSource}
              scoreIsFresh={liveQueries.liveHeader?.scoreIsFresh}
              capturedAt={liveQueries.liveHeader?.capturedAt ?? data.capturedAt}
            />

            <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-xl border border-white/8 bg-black/25 p-4">
                <div className="text-[11px] text-slate-500">P(casa)</div>
                <div className="text-2xl font-bold text-blue-300">
                  {formatPct(summary?.probHomeWin)}
                </div>
                <div className="text-[11px] text-slate-500">
                  proj. {formatNum(summary?.expectedFinalHome)}
                </div>
              </div>
              <div className="rounded-xl border border-white/8 bg-black/25 p-4">
                <div className="text-[11px] text-slate-500">P(fora)</div>
                <div className="text-2xl font-bold text-orange-300">
                  {formatPct(summary?.probAwayWin)}
                </div>
                <div className="text-[11px] text-slate-500">
                  proj. {formatNum(summary?.expectedFinalAway)}
                </div>
              </div>
              <div className="rounded-xl border border-white/8 bg-black/25 p-4">
                <div className="text-[11px] text-slate-500">Total esperado</div>
                <div className="text-2xl font-bold text-white">
                  {formatNum(summary?.expectedTotal)}
                </div>
                <div className="text-[11px] text-slate-500">
                  restante {formatNum(summary?.remainingInnings)} ent.
                  {summary?.marketTotalLine != null
                    ? ` · linha ${formatNum(summary.marketTotalLine)}`
                    : ""}
                </div>
              </div>
              <div className="rounded-xl border border-white/8 bg-black/25 p-4">
                <div className="text-[11px] text-slate-500">Ritmo (R/ent)</div>
                <div className="text-sm text-slate-200">
                  {formatNum(summary?.rpiHome, 2)} × {formatNum(summary?.rpiAway, 2)}
                </div>
                <div className="text-[11px] text-slate-500">
                  conf. {data.confidence?.label ?? "—"} · sim {summary?.nSimulations ?? "—"}
                  {summary?.scoreAdapted && summary.rpiHomePrior != null ? (
                    <span className="ml-1 text-cyan-400/80">
                      · prior {formatNum(summary.rpiHomePrior, 2)}/{formatNum(summary.rpiAwayPrior, 2)}
                    </span>
                  ) : null}
                </div>
              </div>
            </section>

            {data.trendReport?.dominant_trend ? (
              <section className="rounded-xl border border-violet-500/20 bg-violet-500/5 px-4 py-3 text-xs text-slate-300">
                <div className="mb-1 font-semibold uppercase tracking-wider text-violet-300/90">
                  Tendência do jogo
                </div>
                <p>{String(data.trendReport.dominant_trend)}</p>
                {data.trendReport.position_advice &&
                typeof data.trendReport.position_advice === "object" &&
                (data.trendReport.position_advice as { reasoning?: string }).reasoning ? (
                  <p className="mt-1 text-slate-400">
                    {(data.trendReport.position_advice as { reasoning: string }).reasoning}
                  </p>
                ) : null}
              </section>
            ) : null}

            <MarketEdgeCards data={data} benchmark={data.marketBenchmark} />

            <BaseballMarketScanPanel data={data} />

            {headerIsLive ? (
              <LiveCopilotPanel
                copilot={displayCopilot}
                isLoading={copilotQuery.isLoading}
                isFetching={copilotQuery.isFetching}
                agentChat={agentChat}
              />
            ) : null}

            {periodAportes.length > 0 ? (
              <section className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4">
                <div className="mb-3 flex items-center justify-between gap-2">
                  <div className="text-sm font-semibold text-white">
                    F5 · por entrada · totais por time
                  </div>
                  <span className="rounded-full bg-cyan-500/15 px-2 py-0.5 text-[10px] font-bold text-cyan-200">
                    {periodAportes.length}
                  </span>
                </div>
                <ul className="space-y-2">
                  {periodAportes.slice(0, 6).map((a) => (
                    <li
                      key={`period-${a.market}-${a.outcome}-${a.label}`}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white/10 bg-black/20 px-3 py-2"
                    >
                      <div>
                        <div className="text-sm font-medium text-white">{a.label}</div>
                        <div className="text-[11px] text-slate-500">
                          {a.marketDisplay || a.market} · odd {a.marketOdd.toFixed(2)} · modelo{" "}
                          {formatPct(a.modelProb)}
                        </div>
                      </div>
                      <div className="text-right font-mono text-sm text-cyan-200">
                        EV {(a.expectedValue * 100).toFixed(1)}%
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            {data.gamePhase || data.strategy ? (
              <section className="rounded-xl border border-white/8 bg-black/25 p-4">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <div className="text-sm font-semibold text-white">Plano operacional</div>
                  {data.strategy?.posture ? (
                    <span
                      className={`rounded-lg border px-2.5 py-1 text-[11px] font-bold uppercase ${
                        POSTURE_STYLES[data.strategy.posture] ?? POSTURE_STYLES.neutro
                      }`}
                    >
                      {POSTURE_LABELS[data.strategy.posture] ?? data.strategy.posture}
                    </span>
                  ) : null}
                </div>
                {data.gamePhase ? (
                  <p className="mb-3 text-xs text-slate-400">
                    Fase: {data.gamePhase.label}
                    {data.gamePhase.extrasPossible ? " · extras possíveis" : ""}
                    {data.gamePhase.runGap > 0
                      ? ` · diferença ${data.gamePhase.runGap} run${data.gamePhase.runGap > 1 ? "s" : ""}`
                      : ""}
                  </p>
                ) : null}
                {data.strategy?.waitReason ? (
                  <p className="mb-3 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-200">
                    {data.strategy.waitReason}
                  </p>
                ) : null}
                {data.betGuardrails?.blockNewBets ? (
                  <p className="mb-3 rounded-lg border border-red-500/25 bg-red-500/10 px-3 py-2 text-xs text-red-200">
                    Novas apostas bloqueadas: {data.betGuardrails.blockReason ?? "cenário defensivo"}
                  </p>
                ) : null}
                {(data.strategy?.shields ?? []).length > 0 ? (
                  <ul className="mb-3 space-y-2">
                    {data.strategy!.shields.slice(0, 4).map((shield, idx) => (
                      <li
                        key={`${shield.title}-${idx}`}
                        className="rounded-lg border border-white/10 bg-black/20 px-3 py-2"
                      >
                        <div className="text-xs font-medium text-white">{shield.title}</div>
                        <div className="text-[11px] text-slate-500">{shield.reason}</div>
                      </li>
                    ))}
                  </ul>
                ) : null}
                {(data.strategy?.rules ?? []).length > 0 ? (
                  <ul className="list-inside list-disc text-[11px] text-slate-500">
                    {data.strategy!.rules.slice(0, 4).map((rule) => (
                      <li key={rule}>{rule}</li>
                    ))}
                  </ul>
                ) : null}
              </section>
            ) : null}

            {trackBet || displayBets.length > 0 ? (
              <section className="rounded-xl border border-emerald-500/20 bg-emerald-500/5">
                <button
                  type="button"
                  onClick={() => setBetSectionOpen((o) => !o)}
                  className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
                >
                  <div>
                    <div className="text-sm font-semibold text-white">Minhas apostas abertas</div>
                    <div className="text-[11px] text-slate-500">
                      Cash-out com tendência de mercado (ticks)
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {activeAlertCount > 0 ? (
                      <span className="rounded-full border border-amber-400/30 bg-amber-500/10 px-2 py-0.5 text-[11px] font-semibold text-amber-200">
                        {activeAlertCount} alerta{activeAlertCount > 1 ? "s" : ""}
                      </span>
                    ) : null}
                    {displayBets.length > 0 ? (
                      <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[11px] font-semibold text-emerald-300">
                        {displayBets.length} ativo{displayBets.length > 1 ? "s" : ""}
                      </span>
                    ) : null}
                    <span
                      className={`text-slate-500 transition-transform ${betSectionOpen ? "rotate-180" : ""}`}
                      aria-hidden
                    >
                      ▾
                    </span>
                  </div>
                </button>

                {betSectionOpen ? (
                  <div className="space-y-4 border-t border-white/8 px-4 pb-4 pt-3">
                    <label className="flex items-center gap-2 text-xs text-slate-400">
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
                      Tenho aposta aberta — monitorar cash-out
                    </label>

                    {trackBet && displayBets.length > 0 ? (
                      <div className="space-y-4">
                        {displayBets.map((bet, index) => (
                          <BaseballLiveOpenBetMonitor
                            key={bet.id}
                            data={data}
                            bet={bet}
                            cashout={
                              (betAdviceQueries[index]?.data as BaseballSuperbetLiveAdvice | undefined)
                                ?.cashout ?? null
                            }
                            betIndex={index + 1}
                            totalBets={displayBets.length}
                            isFetching={betAdviceQueries[index]?.isFetching ?? false}
                            pollSeconds={Math.round(LIVE_POLL_MS / 1000)}
                            onAutoMonitorChange={(on) => {
                              if (apiBets.some((b) => b.id === bet.id)) return;
                              setRegisteredBets((prev) =>
                                prev.map((b) => (b.id === bet.id ? { ...b, autoMonitor: on } : b)),
                              );
                            }}
                          />
                        ))}
                      </div>
                    ) : null}

                    {trackBet && formMode != null ? (
                      <div className="rounded-xl border border-white/10 bg-black/25 p-4">
                        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
                          {formMode === "add" ? "Cadastrar aposta manual" : "Editar aposta"}
                        </p>
                        <div className="grid gap-3 sm:grid-cols-2">
                          <label className="text-xs text-slate-400">
                            Mercado
                            <select
                              value={betDraft.market}
                              onChange={(e) =>
                                setBetDraft((d) => ({ ...d, market: e.target.value }))
                              }
                              className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-white"
                            >
                              {BASEBALL_MARKET_OPTIONS.map((o) => (
                                <option key={o.value} value={o.value}>
                                  {o.label}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className="text-xs text-slate-400">
                            Outcome
                            <input
                              value={betDraft.outcome}
                              onChange={(e) =>
                                setBetDraft((d) => ({ ...d, outcome: e.target.value }))
                              }
                              placeholder="1, 2, over_8_5, under_8_5…"
                              className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 font-mono text-sm text-white"
                            />
                          </label>
                          <label className="text-xs text-slate-400">
                            Stake (R$)
                            <input
                              type="number"
                              min={1}
                              value={betDraft.stake}
                              onChange={(e) =>
                                setBetDraft((d) => ({ ...d, stake: Number(e.target.value) }))
                              }
                              className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 font-mono text-sm text-white"
                            />
                          </label>
                          <label className="text-xs text-slate-400">
                            Odd de entrada
                            <input
                              type="number"
                              min={1.01}
                              step={0.01}
                              value={betDraft.oddsPlaced}
                              onChange={(e) =>
                                setBetDraft((d) => ({ ...d, oddsPlaced: Number(e.target.value) }))
                              }
                              className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 font-mono text-sm text-white"
                            />
                          </label>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              if (formMode === "add") {
                                setRegisteredBets((prev) => [
                                  ...prev,
                                  {
                                    id: createRegisteredBetId(),
                                    market: betDraft.market,
                                    outcome: betDraft.outcome,
                                    stake: betDraft.stake,
                                    oddsPlaced: betDraft.oddsPlaced,
                                    autoMonitor: true,
                                  },
                                ]);
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
                                        }
                                      : b,
                                  ),
                                );
                              }
                              setFormMode(null);
                              setBetDraft(DEFAULT_BET_DRAFT);
                            }}
                            className="rounded-lg border border-emerald-500/30 bg-emerald-500/15 px-3 py-1.5 text-xs font-semibold text-emerald-200"
                          >
                            {formMode === "add" ? "Cadastrar e monitorar" : "Salvar"}
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setFormMode(null);
                              setBetDraft(DEFAULT_BET_DRAFT);
                            }}
                            className="rounded-lg border border-white/15 px-3 py-1.5 text-xs text-slate-400"
                          >
                            Cancelar
                          </button>
                        </div>
                      </div>
                    ) : trackBet && displayBets.length === 0 ? (
                      <button
                        type="button"
                        onClick={() => {
                          setBetDraft(DEFAULT_BET_DRAFT);
                          setFormMode("add");
                        }}
                        className="text-xs text-emerald-300 hover:text-emerald-200"
                      >
                        + Cadastrar aposta manualmente
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </section>
            ) : (
              <section className="rounded-xl border border-white/8 bg-black/20 p-4">
                <label className="flex items-center gap-2 text-sm text-slate-300">
                  <input
                    type="checkbox"
                    checked={trackBet}
                    onChange={(e) => {
                      const on = e.target.checked;
                      setTrackBet(on);
                      setBetSectionOpen(on);
                      if (on && displayBets.length === 0) {
                        setFormMode("add");
                        setBetDraft(DEFAULT_BET_DRAFT);
                      }
                    }}
                    className="rounded border-white/20"
                  />
                  Tenho aposta aberta — monitorar cash-out
                </label>
              </section>
            )}

            {data.cashout && displayBets.length === 0 && !trackBet ? (
              <section className="rounded-xl border border-violet-500/25 bg-violet-500/5 p-4">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div className="text-sm font-semibold text-white">Cash-out</div>
                  <span className="rounded-full bg-violet-500/20 px-2 py-0.5 text-[10px] font-bold uppercase text-violet-200">
                    {data.cashout.action.replace("_", " ")}
                  </span>
                </div>
                <p className="text-xs text-slate-300">{data.cashout.reason}</p>
                <div className="mt-2 grid gap-2 text-[11px] text-slate-500 sm:grid-cols-3">
                  <div>
                    P(modelo) {formatPct(data.cashout.currentModelProb)} · EV residual{" "}
                    {(data.cashout.remainingEv * 100).toFixed(1)}%
                  </div>
                  <div>Fair ~ R$ {data.cashout.estimatedFairCashout.toFixed(2)}</div>
                  <div>Retorno pot. R$ {data.cashout.potentialReturn.toFixed(2)}</div>
                </div>
              </section>
            ) : null}

            {data.baseballInnings.length > 0 ? (
              <section className="overflow-x-auto rounded-xl border border-white/8 bg-black/20 p-3">
                <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Por entrada
                </div>
                <table className="min-w-full text-center text-sm">
                  <thead>
                    <tr className="text-slate-500">
                      <th className="px-2 py-1 text-left">Time</th>
                      {data.baseballInnings.map((inn) => (
                        <th key={inn.num} className="px-2 py-1">
                          {inn.num}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className="px-2 py-1 text-left text-slate-300">{data.homeTeam}</td>
                      {data.baseballInnings.map((inn) => (
                        <td key={`h-${inn.num}`} className="px-2 py-1 font-mono text-white">
                          {inn.home}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-2 py-1 text-left text-slate-300">{data.awayTeam}</td>
                      {data.baseballInnings.map((inn) => (
                        <td key={`a-${inn.num}`} className="px-2 py-1 font-mono text-white">
                          {inn.away}
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </section>
            ) : null}

            <section className="rounded-xl border border-white/8 bg-black/25 p-4">
              <div className="mb-3 flex items-center justify-between gap-2">
                <div className="text-sm font-semibold text-white">Aportes sugeridos</div>
                {topAportes.length > 0 ? (
                  <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-bold text-emerald-300">
                    {betAportes.length} apostar · {topAportes.length} total
                  </span>
                ) : null}
              </div>
              {topAportes.length === 0 ? (
                <p className="text-sm text-slate-500">
                  Nenhum edge acima do mínimo no momento (Vencedor, Handicap, Total, F5, por
                  entrada, maior pontuação ou corrida N).
                </p>
              ) : (
                <ul className="space-y-2">
                  {topAportes.slice(0, 8).map((a) => (
                    <li
                      key={`${a.market}-${a.outcome}-${a.label}`}
                      className={`flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 ${
                        a.action === "apostar"
                          ? "border-emerald-500/20 bg-emerald-500/5"
                          : "border-amber-500/20 bg-amber-500/5"
                      }`}
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <div className="text-sm font-medium text-white">{a.label}</div>
                          <span
                            className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                              a.action === "apostar"
                                ? "bg-emerald-500/20 text-emerald-300"
                                : "bg-amber-500/20 text-amber-300"
                            }`}
                          >
                            {a.action}
                          </span>
                          {a.lineTier === "alternative" ? (
                            <span className="rounded bg-sky-500/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-sky-300">
                              linha alt.
                            </span>
                          ) : null}
                          {a.lineTier === "extreme" ? (
                            <span className="rounded bg-rose-500/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-rose-300">
                              linha extrema
                            </span>
                          ) : null}
                        </div>
                        <div className="text-[11px] text-slate-500">
                          {a.marketDisplay || a.market} · odd {a.marketOdd.toFixed(2)} · modelo{" "}
                          {formatPct(a.modelProb)} · edge {a.edgePp.toFixed(1)} pp
                        </div>
                      </div>
                      <div className="text-right text-sm">
                        <div
                          className={`font-mono ${
                            a.action === "apostar" ? "text-emerald-300" : "text-amber-300"
                          }`}
                        >
                          EV {(a.expectedValue * 100).toFixed(1)}%
                        </div>
                        {a.suggestedStakeValue != null ? (
                          <div className="text-[11px] text-slate-400">
                            R$ {a.suggestedStakeValue.toFixed(2)}
                          </div>
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </div>
    </PageTransition>
  );
}
