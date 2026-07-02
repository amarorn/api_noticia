import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import Chart from "react-apexcharts";
import type { ApexOptions } from "apexcharts";
import { getBasketSuperbetLiveAdviceUseCase } from "@/application/container";
import type {
  BasketAporteAdvice,
  BasketInPlaySummary,
  BasketQuarterScore,
  BasketSuperbetLiveAdvice,
} from "@/domain/entities";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { useLiveDashboardChrome } from "@/presentation/components/layout/liveDashboardChromeContext";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import {
  BasketLiveContentSkeleton,
  MatchScoreboardSkeleton,
} from "@/presentation/components/ui/Skeleton";
import { LiveMatchProgressBar } from "@/presentation/components/live-dashboard/LiveMatchProgressBar";
import { LiveDashboardTabs } from "@/presentation/components/live-dashboard/LiveDashboardTabs";
import { LiveCopilotPanel } from "@/presentation/components/live-dashboard/LiveCopilotPanel";
import { useLiveCopilotQuery } from "@/presentation/hooks/useLiveCopilotQuery";
import { useLiveCopilotActionAlerts } from "@/presentation/hooks/useLiveCopilotActionAlerts";
import { useLiveCopilotAgentSession } from "@/presentation/hooks/useLiveCopilotAgentSession";
import { useCopilotAlertsPreference } from "@/presentation/hooks/useCopilotAlertsPreference";
import {
  ModelSimulationMeta,
  PpmPacePanel,
  SpreadLinesTable,
  TotalLinesTable,
} from "@/presentation/components/live-dashboard/BasketModelPanels";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";

const LIVE_POLL_MS = 5_000;
const DEFAULT_BASKET_MATCH_MINUTES = 48;

type BasketTab = "resumo" | "mercados" | "qualidade";

function formatPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(0)}%`;
}

function formatPoints(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
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
    return "—";
  }
}

function BasketKpiCard({
  label,
  value,
  sub,
  accentColor,
  icon,
}: {
  label: string;
  value: string;
  sub?: string;
  accentColor: string;
  icon: "ml" | "total" | "spread" | "pace" | "ev" | "conf";
}) {
  const icons = {
    ml: "M12 3v18M5 12h14",
    total: "M4 18h16M8 14l4-8 4 8",
    spread: "M4 12h16M14 8l4 4-4 4",
    pace: "M3 12h4l3 8 4-16 3 8h4",
    ev: "M3 17l6-6 4 4 8-8",
    conf: "M12 3l8 3v6c0 5-3.5 7.5-8 9-4.5-1.5-8-4-8-9V6z",
  };
  return (
    <div className="live-kpi-card">
      <div
        className="live-kpi-icon"
        style={{
          color: accentColor,
          boxShadow: `0 0 18px ${accentColor}33, inset 0 0 12px ${accentColor}12`,
          border: `1px solid ${accentColor}22`,
        }}
      >
        <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
          <path d={icons[icon]} strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <p className="mt-2 text-[10px] font-bold uppercase tracking-widest text-slate-500">{label}</p>
      <p className="mt-1.5 font-mono text-2xl font-bold leading-none text-white">{value}</p>
      {sub ? <p className="mt-1 truncate text-[11px] text-slate-500">{sub}</p> : null}
    </div>
  );
}

function QuarterPaceChart({
  periods,
  homeTeam,
  awayTeam,
}: {
  periods: BasketQuarterScore[];
  homeTeam: string;
  awayTeam: string;
}) {
  if (periods.length === 0) {
    return (
      <div className="flex h-44 items-center justify-center rounded-xl border border-dashed border-white/10 text-xs text-slate-600">
        Placar por quarto ainda não disponível…
      </div>
    );
  }

  const categories = periods.map((p) => `Q${p.num}`);
  const options: ApexOptions = {
    chart: { type: "bar", background: "transparent", toolbar: { show: false }, fontFamily: "inherit" },
    colors: ["#00ff88", "#38bdf8"],
    plotOptions: {
      bar: { borderRadius: 6, columnWidth: "55%" },
    },
    dataLabels: { enabled: false },
    xaxis: {
      categories,
      labels: { style: { colors: "#64748b", fontSize: "10px" } },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      labels: { style: { colors: "#64748b", fontSize: "10px" } },
    },
    grid: { borderColor: "rgba(30,41,59,0.6)", strokeDashArray: 3 },
    legend: {
      show: true,
      position: "top",
      horizontalAlign: "right",
      labels: { colors: "#94a3b8" },
      fontSize: "10px",
    },
    tooltip: { theme: "dark" },
  };

  const series = [
    { name: homeTeam, data: periods.map((p) => p.home) },
    { name: awayTeam, data: periods.map((p) => p.away) },
  ];

  return <Chart options={options} series={series} type="bar" height={220} />;
}

function ProjectionPanel({ summary, homeTeam, awayTeam }: {
  summary: BasketInPlaySummary;
  homeTeam: string;
  awayTeam: string;
}) {
  const totalLine = summary.marketTotalLine;
  const projected = summary.expectedTotal;
  const delta =
    totalLine != null && projected != null ? projected - totalLine : null;
  const spreadLine = summary.marketSpreadLine;

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <div className="rounded-xl border border-white/8 bg-black/20 p-3">
        <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Total de pontos</p>
        <div className="mt-2 flex items-end justify-between gap-2">
          <div>
            <p className="font-mono text-2xl font-bold text-white">{formatPoints(projected, 0)}</p>
            <p className="text-[11px] text-slate-500">proj. final</p>
          </div>
          {totalLine != null && (
            <div className="text-right">
              <p className="font-mono text-lg font-semibold text-sky-400">{formatPoints(totalLine, 1)}</p>
              <p className="text-[11px] text-slate-500">linha mercado</p>
            </div>
          )}
        </div>
        {delta != null && (
          <p className={`mt-2 text-xs font-semibold ${delta > 0 ? "text-neon-green" : delta < 0 ? "text-red-400" : "text-slate-400"}`}>
            {delta > 0 ? "+" : ""}
            {delta.toFixed(1)} pts vs linha
          </p>
        )}
      </div>
      <div className="rounded-xl border border-white/8 bg-black/20 p-3">
        <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Spread (handicap)</p>
        <div className="mt-2 flex items-end justify-between gap-2">
          <div>
            <p className="font-mono text-2xl font-bold text-white">
              {spreadLine != null ? `${spreadLine > 0 ? "+" : ""}${formatPoints(spreadLine, 1)}` : "—"}
            </p>
            <p className="text-[11px] text-slate-500">linha {homeTeam}</p>
          </div>
          <div className="text-right">
            <p className="font-mono text-lg font-semibold text-sky-400">
              {formatPoints(summary.expectedFinalHome, 0)}–{formatPoints(summary.expectedFinalAway, 0)}
            </p>
            <p className="text-[11px] text-slate-500">proj. final</p>
          </div>
        </div>
        <p className="mt-2 text-[11px] text-slate-500">
          {awayTeam} moneyline {formatPct(summary.probAwayWin)}
        </p>
      </div>
    </div>
  );
}

function ActionBadge({ action }: { action: string }) {
  const styles: Record<string, string> = {
    bet: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    strong_bet: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
    watch: "bg-amber-500/15 text-amber-300 border-amber-500/25",
    avoid: "bg-slate-500/10 text-slate-400 border-white/10",
  };
  const cls = styles[action] ?? styles.watch;
  return (
    <span className={`inline-flex rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${cls}`}>
      {action}
    </span>
  );
}

function OpportunityCard({ aporte, rank }: { aporte: BasketAporteAdvice; rank: number }) {
  const isTop = rank === 1;
  const confPct = Math.round(aporte.modelProb * 100);
  const circumference = 2 * Math.PI * 16;
  const dashOffset = circumference * (1 - aporte.modelProb);

  return (
    <div
      className={`relative flex min-w-[220px] flex-col gap-3 overflow-hidden rounded-2xl border p-4 ${
        isTop
          ? "live-opp-card-top border-neon-green/35 bg-gradient-to-b from-neon-green/12 via-neon-green/[0.04] to-transparent"
          : "live-glass-panel border-white/8"
      }`}
    >
      {isTop && (
        <div className="pointer-events-none absolute left-0 top-0 z-10 h-14 w-14 overflow-hidden">
          <div className="absolute -left-7 top-2.5 w-24 rotate-[-45deg] bg-gradient-to-r from-amber-400 via-yellow-300 to-amber-500 py-0.5 text-center text-[8px] font-black uppercase tracking-wider text-black shadow-lg">
            TOP
          </div>
        </div>
      )}
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-bold uppercase tracking-wide text-neon-blue">{aporte.market}</span>
        <span className="text-[11px] font-bold text-slate-500">#{rank}</span>
      </div>
      <div>
        <p className="text-sm font-bold text-white">{aporte.label}</p>
        <p className="mt-0.5 text-[11px] text-slate-500">Odd {aporte.marketOdd.toFixed(2)}</p>
      </div>
      <div className="flex items-end justify-between gap-2">
        <div className="space-y-2">
          <div>
            <p className="text-[9px] font-bold uppercase tracking-widest text-slate-600">EV</p>
            <p className={`font-mono text-lg font-bold ${aporte.expectedValue > 0 ? "text-neon-green" : "text-red-400"}`}>
              {aporte.expectedValue > 0 ? "+" : ""}
              {(aporte.expectedValue * 100).toFixed(1)}%
            </p>
          </div>
          <div>
            <p className="text-[9px] font-bold uppercase tracking-widest text-slate-600">Edge</p>
            <p className="font-mono text-xs text-slate-300">
              {aporte.edgePp > 0 ? "+" : ""}
              {aporte.edgePp.toFixed(1)} pp
            </p>
          </div>
        </div>
        <div className="relative flex flex-col items-center">
          <svg width="44" height="44" className="-rotate-90" style={{ filter: "drop-shadow(0 0 6px rgba(0,255,136,0.5))" }}>
            <circle cx="22" cy="22" r="16" strokeWidth="3" className="fill-none stroke-white/10" />
            <circle
              cx="22"
              cy="22"
              r="16"
              strokeWidth="3"
              className="fill-none stroke-neon-green"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
              strokeLinecap="round"
            />
          </svg>
          <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white">
            {confPct}%
          </span>
          <span className="mt-0.5 text-[9px] text-slate-600">Kelly {(aporte.kellyQuarter * 100).toFixed(1)}%</span>
        </div>
      </div>
      {aporte.suggestedStakeValue != null && aporte.action === "apostar" && (
        <p className="text-[11px] font-semibold text-neon-green">
          Stake sugerido: R$ {aporte.suggestedStakeValue.toFixed(2)}
        </p>
      )}
      <ActionBadge action={aporte.action} />
    </div>
  );
}

function MarketRow({ aporte }: { aporte: BasketAporteAdvice }) {
  return (
    <tr className="border-t border-white/[0.04] hover:bg-white/[0.02]">
      <td className="py-2.5 pl-4 pr-2 text-xs font-semibold text-white">{aporte.market}</td>
      <td className="px-2 py-2.5">
        <span className="rounded-lg border border-white/10 bg-white/5 px-2 py-0.5 text-xs text-slate-200">
          {aporte.label}
        </span>
      </td>
      <td className="px-2 py-2.5 text-right font-mono text-sm text-white">{aporte.marketOdd.toFixed(2)}</td>
      <td className="px-2 py-2.5 text-right font-mono text-xs text-slate-400">{formatPct(aporte.modelProb)}</td>
      <td className="px-2 py-2.5 text-right font-mono text-xs text-slate-400">
        {aporte.edgePp > 0 ? "+" : ""}
        {aporte.edgePp.toFixed(1)} pp
      </td>
      <td className={`px-2 py-2.5 text-right font-mono text-sm font-bold ${aporte.expectedValue > 0 ? "text-neon-green" : "text-red-400"}`}>
        {aporte.expectedValue > 0 ? "+" : ""}
        {(aporte.expectedValue * 100).toFixed(1)}%
      </td>
      <td className="px-2 py-2.5 text-right font-mono text-xs text-slate-300">
        {(aporte.kellyQuarter * 100).toFixed(1)}%
      </td>
      <td className="px-2 py-2.5 text-right font-mono text-xs text-neon-green">
        {aporte.suggestedStakeValue != null ? `R$ ${aporte.suggestedStakeValue.toFixed(2)}` : "—"}
      </td>
      <td className="py-2.5 pl-2 pr-4">
        <ActionBadge action={aporte.action} />
      </td>
    </tr>
  );
}

function QuarterScoreTable({
  periods,
  homeTeam,
  awayTeam,
  currentQuarter,
}: {
  periods: BasketQuarterScore[];
  homeTeam: string;
  awayTeam: string;
  currentQuarter: number | null;
}) {
  if (periods.length === 0) {
    return <p className="text-sm text-slate-500">Placar por quarto indisponível.</p>;
  }
  const homeTotal = periods.reduce((s, p) => s + p.home, 0);
  const awayTotal = periods.reduce((s, p) => s + p.away, 0);
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="text-left text-[10px] uppercase tracking-widest text-slate-500">
            <th className="py-2 pr-3">Time</th>
            {periods.map((p) => (
              <th key={p.num} className="px-2 py-2 text-center">
                Q{p.num}
                {p.num === currentQuarter ? " •" : ""}
              </th>
            ))}
            <th className="px-2 py-2 text-center">Total</th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-t border-white/5">
            <td className="py-2 pr-3 font-medium text-white">{homeTeam}</td>
            {periods.map((p) => (
              <td key={p.num} className="px-2 py-2 text-center font-mono text-slate-300">{p.home}</td>
            ))}
            <td className="px-2 py-2 text-center font-mono font-semibold text-neon-green">{homeTotal}</td>
          </tr>
          <tr className="border-t border-white/5">
            <td className="py-2 pr-3 font-medium text-white">{awayTeam}</td>
            {periods.map((p) => (
              <td key={p.num} className="px-2 py-2 text-center font-mono text-slate-300">{p.away}</td>
            ))}
            <td className="px-2 py-2 text-center font-mono font-semibold text-sky-400">{awayTotal}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function buildKpis(data: BasketSuperbetLiveAdvice) {
  const s = data.inplaySummary;
  const positiveEv = data.aportes.filter((a) => a.expectedValue > 0).length;
  const leaderProb = Math.max(s.probHomeWin ?? 0, s.probAwayWin ?? 0);
  const leader =
    (s.probHomeWin ?? 0) >= (s.probAwayWin ?? 0) ? data.homeTeam : data.awayTeam;
  const totalDelta =
    s.marketTotalLine != null && s.expectedTotal != null
      ? s.expectedTotal - s.marketTotalLine
      : null;
  const ppmAvg =
    s.ppmHome != null && s.ppmAway != null ? (s.ppmHome + s.ppmAway) / 2 : null;

  return {
    leader,
    leaderProb,
    totalDelta,
    totalLine: s.marketTotalLine,
    expectedTotal: s.expectedTotal,
    spreadLine: s.marketSpreadLine,
    remaining: s.remainingMinutes,
    ppmAvg,
    ppmHome: s.ppmHome,
    ppmAway: s.ppmAway,
    positiveEv,
    totalAportes: data.aportes.length,
    confidence: data.confidence,
  };
}

export function BasketLiveInPlayPage() {
  const params = useParams<{ eventId: string }>();
  const eventId = Number(params.eventId);
  const enabled = Number.isFinite(eventId) && eventId > 0;
  const [activeTab, setActiveTab] = useState<BasketTab>("resumo");
  const [nextCountdown, setNextCountdown] = useState(Math.round(LIVE_POLL_MS / 1000));
  const { setChrome } = useLiveDashboardChrome();

  const adviceQuery = useQuery({
    queryKey: ["basket-superbet-live-advice", eventId],
    queryFn: () => getBasketSuperbetLiveAdviceUseCase.execute({ eventId, fast: true }),
    enabled,
    staleTime: 8_000,
    refetchInterval: (q) => {
      const d = q.state.data;
      if (!d?.isLive || d?.isFinished) return false;
      return LIVE_POLL_MS;
    },
  });

  const data = adviceQuery.data;
  const isLoading = adviceQuery.isLoading && !data;
  const kpis = useMemo(() => (data ? buildKpis(data) : null), [data]);
  const matchMinutes = data?.inplaySummary.matchMinutes ?? DEFAULT_BASKET_MATCH_MINUTES;
  const headerIsLiveEarly = Boolean(data?.isLive && !data?.isFinished);
  const { alertsActive: copilotAlertsActive } = useCopilotAlertsPreference();

  const copilotQuery = useLiveCopilotQuery({
    eventId,
    sport: "basketball",
    bankroll: 1000,
    enabled: enabled && headerIsLiveEarly,
  });

  useLiveCopilotActionAlerts(copilotQuery.data, {
    eventId,
    homeTeam: data?.homeTeam,
    awayTeam: data?.awayTeam,
    enabled: enabled && headerIsLiveEarly && copilotAlertsActive,
  });

  const { displayCopilot, agentChat } = useLiveCopilotAgentSession({
    eventId,
    sport: "basketball",
    bankroll: 1000,
    enabled: enabled && headerIsLiveEarly,
    baseCopilot: copilotQuery.data,
    onSwitchTab: (tab) => {
      if (tab === "resumo" || tab === "mercados" || tab === "qualidade") {
        setActiveTab(tab);
      }
    },
  });

  useEffect(() => {
    if (adviceQuery.isFetching) return;
    setNextCountdown(Math.round(LIVE_POLL_MS / 1000));
  }, [adviceQuery.isFetching]);

  useEffect(() => {
    const id = window.setInterval(() => setNextCountdown((c) => Math.max(0, c - 1)), 1000);
    return () => window.clearInterval(id);
  }, []);

  const nextUpdateLabel = `00:${String(nextCountdown).padStart(2, "0")}`;
  const lastUpdateLabel = formatCapturedAt(data?.capturedAt ?? null);
  const headerIsLive = Boolean(data?.isLive && !data?.isFinished);
  const scoreParts = (data?.currentScore ?? "0x0").split(/x/i).map((s) => s.trim());

  useEffect(() => {
    setChrome({
      isLive: headerIsLive,
      lastUpdate: lastUpdateLabel,
      nextUpdate: nextUpdateLabel,
      isFetching: adviceQuery.isFetching,
      onRefresh: () => adviceQuery.refetch(),
    });
    return () => setChrome(null);
  }, [
    headerIsLive,
    lastUpdateLabel,
    nextUpdateLabel,
    adviceQuery.isFetching,
    adviceQuery.refetch,
    setChrome,
  ]);

  const TABS: { id: BasketTab; label: string; count?: number }[] = [
    { id: "resumo", label: "Resumo Operacional" },
    { id: "mercados", label: "Mercados", count: kpis?.positiveEv || undefined },
    { id: "qualidade", label: "Qualidade dos Dados" },
  ];

  return (
    <PageTransition live className="space-y-0 pb-24">
      <div className="sticky top-0 z-30 -mx-2 sm:-mx-4">
        {data ? (
          <div className="live-scoreboard mx-2 mt-2 sm:mx-4">
            <div className="relative flex items-center justify-between gap-4 px-5 py-4">
              <div className="flex min-w-0 flex-1 items-center gap-3">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-full border border-white/12 bg-white/[0.06] shadow-[0_0_16px_rgba(0,245,160,0.12)]">
                  <TeamFlag team={data.homeTeam} size={44} />
                </div>
                <span className="truncate text-base font-bold text-white sm:text-lg">{data.homeTeam}</span>
              </div>
              <div className="flex shrink-0 flex-col items-center px-2">
                <div className="flex items-center gap-3 font-mono text-4xl font-extrabold leading-none text-white">
                  <span>{scoreParts[0] ?? "0"}</span>
                  <span className="text-2xl text-slate-500">×</span>
                  <span>{scoreParts[1] ?? "0"}</span>
                </div>
                <span className="mt-1.5 text-xs font-semibold text-amber-300">
                  {data.minute}&apos;
                  {data.periodLabel ? ` · ${data.periodLabel}` : ""}
                  {headerIsLive ? " · Ao vivo" : ""}
                </span>
              </div>
              <div className="flex min-w-0 flex-1 items-center justify-end gap-3">
                <span className="truncate text-right text-base font-bold text-white sm:text-lg">{data.awayTeam}</span>
                <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-full border border-white/12 bg-white/[0.06] shadow-[0_0_16px_rgba(0,224,255,0.12)]">
                  <TeamFlag team={data.awayTeam} size={44} />
                </div>
              </div>
            </div>
            {headerIsLive && (
              <div className="px-5 pb-5 pt-1">
                <LiveMatchProgressBar minute={data.minute} isLive matchMinutes={matchMinutes} />
              </div>
            )}
          </div>
        ) : (
          <MatchScoreboardSkeleton />
        )}

        <LiveDashboardTabs
          tabs={TABS.map((tab) => ({ id: tab.id, label: tab.label, count: tab.count }))}
          activeId={activeTab}
          onChange={(id) => setActiveTab(id as BasketTab)}
        />
      </div>

      <div className="space-y-4 p-4 pt-3">
        {isLoading ? (
          <BasketLiveContentSkeleton />
        ) : adviceQuery.isError || !data ? (
          <ErrorState
            message={
              adviceQuery.error instanceof Error
                ? adviceQuery.error.message
                : "Falha ao carregar dados do jogo de basquete"
            }
            onRetry={() => adviceQuery.refetch()}
          />
        ) : (
          <>
            {data.superbetStale && (
              <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-xs text-amber-200">
                Dados Superbet em cache — última captura pode estar desatualizada.
              </div>
            )}

            {activeTab === "resumo" && kpis && (
              <div className="space-y-4">
                <LiveCopilotPanel
                  copilot={displayCopilot}
                  isLoading={copilotQuery.isLoading}
                  isFetching={copilotQuery.isFetching}
                  agentChat={agentChat}
                />

                <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
                  <div className="live-glass-panel-glow glow-border rounded-2xl p-4">
                    <div className="mb-4 flex flex-wrap items-center gap-2">
                      <h2 className="text-xs font-black uppercase tracking-widest text-white">
                        Ritmo por quarto
                      </h2>
                      <span className="rounded-full border border-neon-green/20 bg-neon-green/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-widest text-neon-green">
                        Ao Vivo
                      </span>
                      <span className="ml-auto flex items-center gap-3 font-mono text-sm">
                        <span className="text-neon-green neon-text">{formatPct(data.inplaySummary.probHomeWin)}</span>
                        <span className="text-slate-600">·</span>
                        <span className="text-sky-400">{formatPct(data.inplaySummary.probAwayWin)}</span>
                      </span>
                    </div>
                    <QuarterPaceChart
                      periods={data.basketPeriods}
                      homeTeam={data.homeTeam}
                      awayTeam={data.awayTeam}
                    />
                    <div className="mt-4">
                      <ProjectionPanel summary={data.inplaySummary} homeTeam={data.homeTeam} awayTeam={data.awayTeam} />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 xl:grid-cols-2">
                    <BasketKpiCard
                      label="Moneyline líder"
                      value={formatPct(kpis.leaderProb)}
                      sub={kpis.leader}
                      accentColor="#00f5a0"
                      icon="ml"
                    />
                    <BasketKpiCard
                      label="Total vs linha"
                      value={
                        kpis.totalDelta != null
                          ? `${kpis.totalDelta > 0 ? "+" : ""}${kpis.totalDelta.toFixed(1)}`
                          : "—"
                      }
                      sub={
                        kpis.expectedTotal != null && kpis.totalLine != null
                          ? `proj. ${formatPoints(kpis.expectedTotal, 0)} · linha ${formatPoints(kpis.totalLine, 1)}`
                          : undefined
                      }
                      accentColor="#00e0ff"
                      icon="total"
                    />
                    <BasketKpiCard
                      label="Spread linha"
                      value={
                        kpis.spreadLine != null
                          ? `${kpis.spreadLine > 0 ? "+" : ""}${formatPoints(kpis.spreadLine, 1)}`
                          : "—"
                      }
                      sub={`Handicap ${data.homeTeam}`}
                      accentColor="#00e0ff"
                      icon="spread"
                    />
                    <BasketKpiCard
                      label="Ritmo (PPM)"
                      value={kpis.ppmAvg != null ? formatPoints(kpis.ppmAvg, 2) : "—"}
                      sub={
                        kpis.ppmHome != null && kpis.ppmAway != null
                          ? `${formatPoints(kpis.ppmHome, 2)} / ${formatPoints(kpis.ppmAway, 2)}`
                          : `${kpis.remaining ?? "—"} min restantes`
                      }
                      accentColor="#ffd166"
                      icon="pace"
                    />
                    <BasketKpiCard
                      label="Aportes EV+"
                      value={`${kpis.positiveEv}/${kpis.totalAportes}`}
                      sub="moneyline · spread · total"
                      accentColor="#00f5a0"
                      icon="ev"
                    />
                    <BasketKpiCard
                      label="Confiança"
                      value={
                        kpis.confidence
                          ? `${Math.round(kpis.confidence.score * 100)}%`
                          : "—"
                      }
                      sub={kpis.confidence?.label ?? "modelo basquete"}
                      accentColor="#fbbf24"
                      icon="conf"
                    />
                  </div>
                </div>

                <PpmPacePanel data={data} homeTeam={data.homeTeam} awayTeam={data.awayTeam} />

                <ModelSimulationMeta summary={data.inplaySummary} />

                {data.aportes.length > 0 && (
                  <div className="live-glass-panel rounded-2xl p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <h2 className="text-xs font-black uppercase tracking-widest text-white">
                        Oportunidades em destaque
                      </h2>
                      <span className="rounded-full bg-neon-green/15 px-2 py-0.5 text-[10px] font-bold text-neon-green">
                        {data.aportes.length}
                      </span>
                    </div>
                    <div className="flex gap-3 overflow-x-auto pb-2">
                      {data.aportes.slice(0, 6).map((a, i) => (
                        <OpportunityCard key={`${a.market}-${a.outcome}-${i}`} aporte={a} rank={i + 1} />
                      ))}
                    </div>
                  </div>
                )}

                <div className="live-glass-panel overflow-hidden rounded-2xl">
                  <div className="border-b border-white/[0.04] px-4 py-3">
                    <h2 className="text-xs font-black uppercase tracking-widest text-white">
                      Mercados avaliados
                    </h2>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[860px] text-left">
                      <thead>
                        <tr className="border-b border-white/[0.04]">
                          {["Mercado", "Seleção", "Odd", "Modelo", "Edge", "EV", "Kelly", "Stake", "Ação"].map((h) => (
                            <th
                              key={h}
                              className={`py-2 text-[9px] font-black uppercase tracking-widest text-slate-600 ${
                                h === "Mercado" ? "pl-4" : h === "Ação" ? "pr-4" : "px-2"
                              } ${["Odd", "Modelo", "Edge", "EV", "Kelly", "Stake"].includes(h) ? "text-right" : ""}`}
                            >
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {data.aportes.length > 0 ? (
                          data.aportes.map((a, i) => (
                            <MarketRow key={`${a.market}-${a.outcome}-${i}`} aporte={a} />
                          ))
                        ) : (
                          <tr>
                            <td colSpan={9} className="px-4 py-8 text-center text-sm text-slate-600">
                              Nenhum mercado com edge no momento.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "mercados" && (
              <div className="space-y-4">
                <div className="live-glass-panel rounded-2xl p-4">
                  <h2 className="mb-4 text-xs font-black uppercase tracking-widest text-white">Moneyline</h2>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-xl border border-white/8 bg-black/20 p-4 text-center">
                      <p className="text-[11px] uppercase text-slate-500">{data.homeTeam}</p>
                      <p className="mt-1 font-mono text-2xl font-bold text-neon-green">
                        {data.h2hOdds["1"]?.toFixed(2) ?? "—"}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">modelo {formatPct(data.inplaySummary.probHomeWin)}</p>
                    </div>
                    <div className="rounded-xl border border-white/8 bg-black/20 p-4 text-center">
                      <p className="text-[11px] uppercase text-slate-500">{data.awayTeam}</p>
                      <p className="mt-1 font-mono text-2xl font-bold text-sky-400">
                        {data.h2hOdds["2"]?.toFixed(2) ?? "—"}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">modelo {formatPct(data.inplaySummary.probAwayWin)}</p>
                    </div>
                  </div>
                </div>

                <div className="live-glass-panel overflow-hidden rounded-2xl p-4">
                  <h2 className="mb-4 text-xs font-black uppercase tracking-widest text-white">
                    Spread — modelo vs mercado
                  </h2>
                  <SpreadLinesTable data={data} />
                </div>

                <div className="live-glass-panel overflow-hidden rounded-2xl p-4">
                  <h2 className="mb-4 text-xs font-black uppercase tracking-widest text-white">
                    Total de pontos — modelo vs mercado
                  </h2>
                  <TotalLinesTable data={data} />
                </div>

                {data.inplaySummary.nextQuarterNumber != null && (
                  <div className="live-glass-panel rounded-2xl p-4">
                    <h2 className="mb-4 text-xs font-black uppercase tracking-widest text-white">
                      Projeção Q{data.inplaySummary.nextQuarterNumber}
                    </h2>
                    <div className="grid grid-cols-2 gap-3 text-center">
                      <div>
                        <p className="text-[11px] text-slate-500">{data.homeTeam}</p>
                        <p className="font-mono text-2xl font-bold text-neon-green">
                          {formatPoints(data.inplaySummary.nextQuarterProjectionHome)}
                        </p>
                      </div>
                      <div>
                        <p className="text-[11px] text-slate-500">{data.awayTeam}</p>
                        <p className="font-mono text-2xl font-bold text-sky-400">
                          {formatPoints(data.inplaySummary.nextQuarterProjectionAway)}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                <div className="live-glass-panel rounded-2xl p-4">
                  <h2 className="mb-3 text-xs font-black uppercase tracking-widest text-white">Todos os aportes</h2>
                  {data.aportes.length === 0 ? (
                    <p className="text-sm text-slate-500">Nenhuma oportunidade no momento.</p>
                  ) : (
                    data.aportes.map((a, i) => (
                      <div
                        key={`${a.market}-${i}`}
                        className="flex items-center justify-between border-b border-white/5 py-3 last:border-0"
                      >
                        <div>
                          <p className="text-sm font-medium text-white">{a.label}</p>
                          <p className="text-[11px] text-slate-500">{a.market}</p>
                        </div>
                        <div className="flex flex-col items-end gap-1">
                          <span className="font-mono text-xs text-emerald-300">
                            EV {(a.expectedValue * 100).toFixed(1)}% · edge {a.edgePp.toFixed(1)} pp
                          </span>
                          {a.suggestedStakeValue != null && (
                            <span className="font-mono text-[11px] text-neon-green">
                              R$ {a.suggestedStakeValue.toFixed(2)} · Kelly {(a.kellyQuarter * 100).toFixed(1)}%
                            </span>
                          )}
                          <ActionBadge action={a.action} />
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {activeTab === "qualidade" && (
              <div className="space-y-4">
                <ModelSimulationMeta summary={data.inplaySummary} />

                <div className="live-glass-panel rounded-2xl p-4">
                  <h2 className="mb-4 text-xs font-black uppercase tracking-widest text-white">Qualidade dos dados</h2>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <div>
                      <p className="text-[10px] uppercase text-slate-500">Confiança</p>
                      <p className="font-mono text-xl font-bold text-white">
                        {data.confidence ? `${Math.round(data.confidence.score * 100)}%` : "—"}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase text-slate-500">Edge máx.</p>
                      <p className="font-mono text-xl font-bold text-white">
                        {data.confidence ? `${data.confidence.maxEdgePp.toFixed(1)} pp` : "—"}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase text-slate-500">Poll</p>
                      <p className="font-mono text-xl font-bold text-white">{LIVE_POLL_MS / 1000}s</p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase text-slate-500">Fonte</p>
                      <p className="text-sm font-semibold text-white">
                        {data.superbetStale ? "Cache" : "Superbet"}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="live-glass-panel rounded-2xl p-4">
                  <h2 className="mb-4 text-xs font-black uppercase tracking-widest text-white">Placar por quarto</h2>
                  <QuarterScoreTable
                    periods={data.basketPeriods}
                    homeTeam={data.homeTeam}
                    awayTeam={data.awayTeam}
                    currentQuarter={
                      data.basketPeriods.length > 0
                        ? data.basketPeriods[data.basketPeriods.length - 1].num
                        : null
                    }
                  />
                </div>
              </div>
            )}

            <div className="live-glass-panel flex items-center justify-center gap-3 px-4 py-3 text-[11px] text-slate-500">
              <svg viewBox="0 0 40 12" className={`live-status-pulse h-3 w-10 text-neon-green ${adviceQuery.isFetching ? "animate-pulse" : ""}`} aria-hidden>
                <polyline
                  points="0,6 4,6 6,2 8,10 10,6 14,6 16,3 18,9 20,6 24,6 26,1 28,11 30,6 40,6"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
              </svg>
              Atualizando odds de basquete e recalculando spread/total…
            </div>
          </>
        )}
      </div>
    </PageTransition>
  );
}
