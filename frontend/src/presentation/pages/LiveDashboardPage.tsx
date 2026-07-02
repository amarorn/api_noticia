import { useMemo, useState, useCallback, useEffect, useRef } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import Chart from "react-apexcharts";
import type { ApexOptions } from "apexcharts";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { LiveDashboardContentSkeleton, MatchScoreboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { useLiveDashboardChrome } from "@/presentation/components/layout/liveDashboardChromeContext";
import { IconChevronRight } from "@/presentation/components/ui/Icons";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";
import { LiveMatchProgressBar } from "@/presentation/components/live-dashboard/LiveMatchProgressBar";
import { LiveDashboardTabs } from "@/presentation/components/live-dashboard/LiveDashboardTabs";
import { LiveCopilotPanel } from "@/presentation/components/live-dashboard/LiveCopilotPanel";

// Painéis de análise e mercado
import { LiveModelVsMarketHero } from "@/presentation/components/predictions/LiveModelVsMarketHero";
import { LiveEvRealPanel } from "@/presentation/components/predictions/LiveEvRealPanel";
import { LiveStatsCompactBar } from "@/presentation/components/predictions/LiveStatsCompactBar";
import { LiveCornersPanel } from "@/presentation/components/predictions/LiveCornersPanel";
import { LiveTimelinePanel } from "@/presentation/components/predictions/LiveTimelinePanel";
import { LiveFormH2hPanel } from "@/presentation/components/predictions/LiveFormH2hPanel";
import { LivePlayerStatsPanel } from "@/presentation/components/predictions/LivePlayerStatsPanel";
import { LiveSocialRadarPanel } from "@/presentation/components/predictions/LiveSocialRadarPanel";
import { LiveActionNowPanel } from "@/presentation/components/predictions/LiveActionNowPanel";
import { LiveBestCombosPanel } from "@/presentation/components/predictions/LiveBestCombosPanel";
import { LiveHalfTicketsPanel } from "@/presentation/components/predictions/LiveHalfTicketsPanel";
import { LiveRemaining2hMarketsPanel } from "@/presentation/components/predictions/LiveRemaining2hMarketsPanel";
import { LiveLongshotCombosPanel } from "@/presentation/components/predictions/LiveLongshotCombosPanel";
import { LiveMarketCards } from "@/presentation/components/predictions/LiveMarketCards";
import { LiveScoreHeatmap } from "@/presentation/components/predictions/LiveScoreHeatmap";
import { LiveP0GuardBanner } from "@/presentation/components/predictions/LiveP0GuardBanner";
import LiveAgainstModelAlert from "@/presentation/components/predictions/LiveAgainstModelAlert";
import LiveHedgeAlert from "@/presentation/components/predictions/LiveHedgeAlert";
import { LiveRecalibrationBanner } from "@/presentation/components/predictions/LiveRecalibrationBanner";
import { LiveTopReturnPanel } from "@/presentation/components/predictions/LiveTopReturnPanel";
import { LiveOptimizedTicketsPanel } from "@/presentation/components/predictions/LiveOptimizedTicketsPanel";
import { BetStrategyPanel } from "@/presentation/components/predictions/BetStrategyPanel";
import { LiveBetBuilderGuardPanel } from "@/presentation/components/predictions/LiveBetBuilderGuardPanel";
import { LiveContextUpload } from "@/presentation/components/predictions/LiveContextUpload";

// Componentes do dashboard visual
import { LiveMatchStatsPanel } from "@/presentation/components/live-dashboard/LiveMatchStatsPanel";
import { LiveEvLeaderboard } from "@/presentation/components/live-dashboard/LiveEvLeaderboard";
import { LiveTrendSignals } from "@/presentation/components/live-dashboard/LiveTrendSignals";
import { LivePredictionEvolutionChart } from "@/presentation/components/live-dashboard/LivePredictionEvolutionChart";

import { useLiveAdviceQueries } from "@/presentation/hooks/useLiveAdviceQueries";
import { useLiveCopilotQuery } from "@/presentation/hooks/useLiveCopilotQuery";
import { useLiveCopilotActionAlerts } from "@/presentation/hooks/useLiveCopilotActionAlerts";
import { useLiveCopilotAgentSession } from "@/presentation/hooks/useLiveCopilotAgentSession";
import { useCopilotAlertsPreference } from "@/presentation/hooks/useCopilotAlertsPreference";
import { useLivePossessionHistory } from "@/presentation/hooks/useLivePossessionHistory";
import { useLiveRecalibration } from "@/presentation/hooks/useLiveRecalibration";
import { useLivePredictionHistory } from "@/presentation/hooks/useLivePredictionHistory";
import { resolveLiveAdvicePhase } from "@/presentation/utils/liveAdvicePhase";
import { useTicket, type TicketLeg } from "@/presentation/hooks/useTicket";
import { TicketSimulator, FloatingTicketBadge } from "@/presentation/components/ticket/TicketSimulator";
import { useOddsDropMonitor, type OddsDropAlert } from "@/presentation/hooks/useOddsDropMonitor";
import { LiveOddsDropAlert } from "@/presentation/components/predictions/LiveOddsDropAlert";
import { LiveOpenBetsPanel } from "@/presentation/components/predictions/LiveOpenBetsPanel";
import type { SuperbetLiveAdvice } from "@/domain/entities";

// ─── Types ───────────────────────────────────────────────────────────────────

type LiveDashboardTab = "resumo" | "mercados" | "qualidade" | "bilhete";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatMarketLabel(market: string): string {
  const map: Record<string, string> = {
    h2h: "Resultado Final",
    over_2_5: "Total de Gols",
    over_1_5: "Total de Gols",
    over_3_5: "Total de Gols",
    btts: "Ambos Marcam",
    next_goal: "Próximo Gol",
    asian_handicap: "Handicap Asiático",
    corners: "Escanteios",
    yellow_cards: "Cartões Amarelos",
    first_half: "1º Tempo",
    second_half: "2º Tempo",
  };
  return map[market] ?? market.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatOutcomeLabel(outcome: string, homeTeam: string, awayTeam: string): string {
  if (outcome === "1") return homeTeam;
  if (outcome === "2") return awayTeam;
  if (outcome === "X") return "Empate";
  if (outcome === "yes") return "Sim";
  if (outcome === "no") return "Não";
  if (outcome === "home") return `Gol ${homeTeam}`;
  if (outcome === "away") return `Gol ${awayTeam}`;
  return outcome;
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

function formatRelativeCapturedAt(iso: string | null): { time: string; ago: string | null } {
  if (!iso) return { time: "—", ago: null };
  try {
    const diff = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
    const time = formatCapturedAt(iso);
    return { time, ago: diff < 120 ? `há ${diff}s` : null };
  } catch {
    return { time: "—", ago: null };
  }
}

function impliedPressureLabel(pct: number): string {
  if (pct >= 60) return "alta";
  if (pct >= 40) return "média";
  return "baixa";
}

function computeQualityScore(data: SuperbetLiveAdvice): { score: number; label: string; color: string } {
  let score = 0;
  if (data.confidence) score += Math.round(data.confidence.score * 40);
  if (data.liveStats?.sofascoreAvailable) score += 25;
  if (data.liveStats?.scorealarmAvailable && !data.liveStats?.scorealarmStale) score += 20;
  if (data.liveStats?.homePossessionPct != null) score += 10;
  if (data.rawMarketCount > 50) score += 5;

  const label = score >= 80 ? "Excelente" : score >= 60 ? "Boa" : score >= 40 ? "Regular" : "Fraca";
  const color = score >= 80 ? "#00ff88" : score >= 60 ? "#38bdf8" : score >= 40 ? "#fbbf24" : "#ef4444";
  return { score: Math.min(100, score), label, color };
}

function MiniIcon({ name }: { name: "trend" | "activity" | "shield" | "clock" | "bell" | "db" }) {
  const p = {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    className: "h-3.5 w-3.5",
  };
  switch (name) {
    case "trend":
      return (<svg {...p}><path d="M3 17l6-6 4 4 8-8" /><path d="M14 7h7v7" /></svg>);
    case "activity":
      return (<svg {...p}><path d="M3 12h4l3 8 4-16 3 8h4" /></svg>);
    case "shield":
      return (<svg {...p}><path d="M12 3l8 3v6c0 5-3.5 7.5-8 9-4.5-1.5-8-4-8-9V6z" /></svg>);
    case "clock":
      return (<svg {...p}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>);
    case "bell":
      return (<svg {...p}><path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 0 1-3.4 0" /></svg>);
    case "db":
      return (<svg {...p}><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5" /><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></svg>);
  }
}

type KpiDelta = { text: string; trend: "up" | "down" | "flat" };

function KpiCard({
  label,
  value,
  sub,
  delta,
  accentColor,
  badge,
  icon,
  highlight = false,
}: {
  label: string;
  value: string;
  sub?: string;
  delta?: KpiDelta;
  accentColor: string;
  badge?: { text: string; color: string };
  icon?: "trend" | "activity" | "shield" | "clock" | "bell" | "db";
  highlight?: boolean;
}) {
  const arrow = delta?.trend === "up" ? "↑" : delta?.trend === "down" ? "↓" : "—";
  const deltaColor =
    delta?.trend === "up"
      ? "text-emerald-400"
      : delta?.trend === "down"
        ? "text-red-400"
        : "text-slate-500";
  return (
    <div className={`live-kpi-card ${highlight ? "border-white/20" : ""}`}>
      <div
        className="live-kpi-icon"
        style={{
          color: accentColor,
          boxShadow: `0 0 18px ${accentColor}33, inset 0 0 12px ${accentColor}12`,
          border: `1px solid ${accentColor}22`,
        }}
      >
        {icon ? <MiniIcon name={icon} /> : null}
      </div>
      <p className="mt-2 text-[10px] font-bold uppercase tracking-widest text-slate-500">{label}</p>
      <div className="mt-1.5 flex items-end gap-2">
        <span className="font-mono text-2xl font-bold leading-none text-white">{value}</span>
        {badge && (
          <span
            className="mb-0.5 rounded px-1.5 py-0.5 text-[10px] font-semibold"
            style={{ backgroundColor: `${badge.color}22`, color: badge.color }}
          >
            {badge.text}
          </span>
        )}
      </div>
      {delta ? (
        <p className={`mt-1 flex items-center gap-1 text-[11px] font-semibold ${deltaColor}`}>
          <span aria-hidden>{arrow}</span>
          {delta.text}
        </p>
      ) : sub ? (
        <p className="mt-1 truncate text-[11px] text-slate-500">{sub}</p>
      ) : null}
    </div>
  );
}

function OpportunityCard({
  label,
  market,
  outcome,
  ev,
  odd,
  confidence,
  rank,
  homeTeam,
  awayTeam,
  onAdd,
}: {
  label?: string;
  market: string;
  outcome: string;
  ev: number;
  odd: number;
  confidence: number;
  rank: number;
  homeTeam: string;
  awayTeam: string;
  onAdd?: () => void;
}) {
  const isTop = rank === 1;
  const isHot = ev > 0.3;
  const confPct = Math.round(confidence * 100);
  const circumference = 2 * Math.PI * 16;
  const dashOffset = circumference * (1 - confidence);
  const title = label?.trim() || formatOutcomeLabel(outcome, homeTeam, awayTeam);

  const confColor = confPct >= 60 ? "#00ff88" : confPct >= 40 ? "#fbbf24" : "#64748b";

  return (
    <div
      role={onAdd ? "button" : undefined}
      tabIndex={onAdd ? 0 : undefined}
      onClick={onAdd}
      onKeyDown={onAdd ? (e) => e.key === "Enter" && onAdd() : undefined}
      className={`relative flex min-w-[220px] flex-col gap-3 overflow-hidden rounded-2xl border p-4 transition-all ${
        isTop
          ? "live-opp-card-top border-neon-green/35 bg-gradient-to-b from-neon-green/12 via-neon-green/[0.04] to-transparent"
          : "live-glass-panel border-white/8 hover:border-white/15"
      } ${onAdd ? "cursor-pointer" : ""}`}
    >
      {isTop && (
        <div className="pointer-events-none absolute left-0 top-0 z-10 h-14 w-14 overflow-hidden">
          <div className="absolute -left-7 top-2.5 w-24 rotate-[-45deg] bg-gradient-to-r from-amber-400 via-yellow-300 to-amber-500 py-0.5 text-center text-[8px] font-black uppercase tracking-wider text-black shadow-lg">
            TOP
          </div>
        </div>
      )}

      <div className="flex items-center gap-1.5">
        {isHot && <span className="text-sm" aria-hidden>🔥</span>}
        <span className="ml-auto text-[11px] font-bold text-neon-blue">#{rank}</span>
      </div>

      <div>
        <p className="text-sm font-bold leading-tight text-white">{title}</p>
        <p className="mt-0.5 text-[11px] text-slate-500">{formatMarketLabel(market)}</p>
      </div>

      <div className="flex items-end justify-between gap-2">
        <div className="space-y-1">
          <div>
            <p className="text-[9px] font-bold uppercase tracking-widest text-slate-600">EV</p>
            <p
              className={`font-mono text-lg font-bold ${ev > 0.1 ? "text-neon-green neon-text" : ev > 0 ? "text-sky-400" : "text-red-400"}`}
            >
              {ev > 0 ? "+" : ""}
              {(ev * 100).toFixed(1)}%
            </p>
          </div>
          <div>
            <p className="text-[9px] font-bold uppercase tracking-widest text-slate-600">Odd</p>
            <p className="font-mono text-sm font-semibold text-white">{odd.toFixed(2)}</p>
          </div>
        </div>

        <div className="relative flex flex-col items-center">
          <svg
            width="48"
            height="48"
            className="-rotate-90"
            style={{ filter: `drop-shadow(0 0 6px ${confColor}88)` }}
          >
            <circle cx="24" cy="24" r="17" strokeWidth="3" className="fill-none stroke-white/10" />
            <circle
              cx="24"
              cy="24"
              r="17"
              strokeWidth="3"
              className="fill-none"
              stroke={confColor}
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
              strokeLinecap="round"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-[11px] font-bold text-white">{confPct}%</span>
          </div>
          <span className="mt-0.5 text-[9px] font-semibold uppercase tracking-wide text-slate-600">
            Conf.
          </span>
        </div>
      </div>
    </div>
  );
}

function PressureChart({
  homeTeam,
  awayTeam,
  history,
  currentMinute,
}: {
  homeTeam: string;
  awayTeam: string;
  history: { minute: number; home: number; away: number }[];
  currentMinute: number;
}) {
  const hasData = history.length >= 2;

  const displayHome = history.length > 0 ? history[history.length - 1].home : 50;
  const displayAway = history.length > 0 ? history[history.length - 1].away : 50;
  const labels = history.map((point) => `${point.minute}'`);
  const currentMinuteLabel = `${currentMinute}'`;

  const chartOptions: ApexOptions = {
    chart: {
      type: "area",
      background: "transparent",
      toolbar: { show: false },
      fontFamily: "inherit",
      animations: { enabled: true, speed: 800 },
      zoom: { enabled: false },
      dropShadow: { enabled: false },
    },
    colors: ["#00ff88", "#38bdf8"],
    stroke: { curve: "smooth", width: [2.5, 2.5] },
    fill: {
      type: "gradient",
      gradient: {
        shadeIntensity: 1,
        opacityFrom: 0.22,
        opacityTo: 0.01,
        stops: [0, 85, 100],
      },
    },
    dataLabels: { enabled: false },
    markers: {
      size: 0,
      hover: { size: 4 },
      discrete: history.length
        ? [
            {
              seriesIndex: 0,
              dataPointIndex: history.length - 1,
              fillColor: "#00ff88",
              strokeColor: "#052e1f",
              size: 5,
            },
            {
              seriesIndex: 1,
              dataPointIndex: history.length - 1,
              fillColor: "#38bdf8",
              strokeColor: "#082f49",
              size: 5,
            },
          ]
        : [],
    },
    xaxis: {
      categories: labels,
      labels: { style: { colors: "#475569", fontSize: "10px" }, rotate: 0 },
      axisBorder: { show: false },
      axisTicks: { show: false },
      tickAmount: Math.min(8, history.length),
    },
    yaxis: {
      min: 0,
      max: 100,
      labels: {
        formatter: (v) => `${v.toFixed(0)}%`,
        style: { colors: "#475569", fontSize: "10px" },
      },
      tickAmount: 4,
    },
    grid: {
      borderColor: "rgba(30, 41, 59, 0.6)",
      strokeDashArray: 3,
      xaxis: { lines: { show: false } },
      padding: { left: 0, right: 8, top: 8, bottom: -6 },
    },
    legend: { show: false },
    tooltip: {
      theme: "dark",
      shared: true,
      intersect: false,
      y: { formatter: (val) => `${val.toFixed(1)}%` },
    },
    annotations: {
      yaxis: [
        {
          y: 50,
          borderColor: "rgba(148, 163, 184, 0.28)",
          strokeDashArray: 4,
        },
      ],
      xaxis: [
        {
          x: labels.includes(currentMinuteLabel) ? currentMinuteLabel : labels[labels.length - 1],
          borderColor: "rgba(255, 209, 102, 0.55)",
          strokeDashArray: 4,
          label: {
            text: `${currentMinute}'`,
            borderColor: "#ffd166",
            borderWidth: 0,
            position: "top",
            offsetY: -6,
            style: {
              color: "#050811",
              background: "#ffd166",
              fontSize: "10px",
              fontWeight: 700,
              padding: { top: 3, bottom: 3, left: 8, right: 8 },
            },
          },
        },
      ],
    },
  };

  const series = [
    { name: homeTeam, data: history.map((h) => h.home) },
    { name: awayTeam, data: history.map((h) => h.away) },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex items-end gap-6">
          <div>
            <p className="font-mono text-3xl font-bold leading-none text-neon-green neon-text">
              {displayHome.toFixed(0)}%
            </p>
            <p className="mt-1 text-[10px] font-bold uppercase tracking-widest text-slate-400">
              {homeTeam}
            </p>
          </div>
          <div>
            <p className="font-mono text-3xl font-bold leading-none text-sky-400">
              {displayAway.toFixed(0)}%
            </p>
            <p className="mt-1 text-[10px] font-bold uppercase tracking-widest text-slate-400">
              {awayTeam}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-5 rounded-full bg-neon-green/70 shadow-[0_0_8px_rgba(0,255,136,0.4)]" />
            {homeTeam}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-5 rounded-full bg-sky-400/70 shadow-[0_0_8px_rgba(56,189,248,0.35)]" />
            {awayTeam}
          </span>
        </div>
      </div>

      {hasData ? (
        <div className="rounded-2xl border border-white/6 bg-[radial-gradient(circle_at_top,rgba(20,184,166,0.08),transparent_55%),linear-gradient(180deg,rgba(15,23,42,0.32),rgba(15,23,42,0.12))] p-2">
          <Chart options={chartOptions} series={series} type="area" height={220} />
        </div>
      ) : (
        <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-white/10 text-xs text-slate-600">
          Acumulando amostras de posse ao longo dos polls…
        </div>
      )}
    </div>
  );
}

function MarketTypeIcon({ market }: { market: string }) {
  const p = {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.75,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    className: "h-3.5 w-3.5 shrink-0 text-slate-500",
  };
  if (market.includes("over") || market.includes("total")) {
    return (
      <svg {...p}>
        <path d="M4 18h16" />
        <path d="M8 14l4-8 4 8" />
      </svg>
    );
  }
  if (market === "btts") {
    return (
      <svg {...p}>
        <circle cx="9" cy="12" r="3" />
        <circle cx="15" cy="12" r="3" />
      </svg>
    );
  }
  if (market.includes("handicap")) {
    return (
      <svg {...p}>
        <path d="M4 12h16" />
        <path d="M14 8l4 4-4 4" />
      </svg>
    );
  }
  return (
    <svg {...p}>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v4l2 2" />
    </svg>
  );
}

function ConfidenceBar({ pct }: { pct: number }) {
  const color = pct >= 60 ? "#00ff88" : pct >= 40 ? "#fbbf24" : "#64748b";
  const segments = 5;
  const filled = Math.round((pct / 100) * segments);
  return (
    <div className="flex items-center gap-0.5">
      {Array.from({ length: segments }).map((_, i) => (
        <div
          key={i}
          className="h-2 w-1.5 rounded-sm transition-colors"
          style={{
            backgroundColor: i < filled ? color : "rgba(255,255,255,0.08)",
            boxShadow: i < filled ? `0 0 6px ${color}55` : undefined,
          }}
        />
      ))}
    </div>
  );
}

function MarketRow({
  label,
  market,
  outcome,
  marketOdd,
  modelProb,
  ev,
  capturedAt,
  homeTeam,
  awayTeam,
  isFavorite,
  onToggleFav,
}: {
  label: string;
  market: string;
  outcome: string;
  marketOdd: number;
  modelProb: number;
  ev: number;
  capturedAt: string | null;
  homeTeam: string;
  awayTeam: string;
  isFavorite: boolean;
  onToggleFav: () => void;
}) {
  const fairOdd = modelProb > 0 ? 1 / modelProb : 0;
  const impliedPct = marketOdd > 0 ? (1 / marketOdd) * 100 : 0;
  const isPositive = ev > 0;
  const direction =
    ev > 0.05 ? "Esticando" : ev <= -0.02 ? "Encurtando" : "Estável";
  const directionIcon = ev > 0.05 ? "↗" : ev <= -0.02 ? "↘" : "→";
  const directionColor = ev > 0.05 ? "#00ff88" : ev <= -0.02 ? "#ef4444" : "#94a3b8";
  const confPct = Math.min(100, Math.max(0, Math.round(50 + ev * 200)));
  const captured = formatRelativeCapturedAt(capturedAt);

  const confColor = confPct >= 60 ? "#00ff88" : confPct >= 40 ? "#fbbf24" : "#64748b";

  return (
    <tr className="group border-t border-white/[0.04] transition-colors hover:bg-white/[0.03]">
      <td className="py-2.5 pl-4 pr-2">
        <div className="flex items-start gap-2">
          <MarketTypeIcon market={market} />
          <div>
            <p className="text-xs font-semibold text-white">{formatMarketLabel(market)}</p>
            <p className="text-[10px] text-slate-600">{label.slice(0, 36)}</p>
          </div>
        </div>
      </td>

      {/* Seleção */}
      <td className="px-2 py-2.5">
        <span className="rounded-lg border border-white/10 bg-white/5 px-2 py-0.5 text-xs font-semibold text-slate-200">
          {formatOutcomeLabel(outcome, homeTeam, awayTeam)}
        </span>
      </td>

      {/* Odd atual */}
      <td className="px-2 py-2.5 text-right">
        <span className="font-mono text-sm font-semibold text-white">{marketOdd.toFixed(2)}</span>
      </td>

      {/* Odd justa */}
      <td className="px-2 py-2.5 text-right">
        <span className="font-mono text-xs text-slate-400">
          {fairOdd > 0 ? fairOdd.toFixed(2) : "—"}
        </span>
      </td>

      {/* EV */}
      <td className="px-2 py-2.5 text-right">
        <span
          className={`font-mono text-sm font-bold ${isPositive ? "text-neon-green" : "text-red-400"}`}
        >
          {ev > 0 ? "+" : ""}
          {(ev * 100).toFixed(1)}%
        </span>
      </td>

      <td className="px-2 py-2.5 text-right">
        <span className="text-xs text-slate-300">
          {impliedPct.toFixed(0)}%{" "}
          <span className="text-slate-500">{impliedPressureLabel(impliedPct)}</span>
        </span>
      </td>

      <td className="px-2 py-2.5">
        <span className="inline-flex items-center gap-1 text-xs font-semibold" style={{ color: directionColor }}>
          <span aria-hidden>{directionIcon}</span>
          {direction}
        </span>
      </td>

      <td className="px-2 py-2.5">
        <div className="flex flex-col">
          <span className="text-[11px] text-slate-400">{captured.time}</span>
          {captured.ago && <span className="text-[10px] text-slate-600">{captured.ago}</span>}
        </div>
      </td>

      <td className="py-2.5 pl-2 pr-4">
        <div className="flex items-center gap-2">
          <ConfidenceBar pct={confPct} />
          <span className="w-8 text-right text-[10px] font-semibold" style={{ color: confColor }}>
            {confPct}%
          </span>
          <button
            type="button"
            onClick={onToggleFav}
            className={`text-sm transition ${
              isFavorite
                ? "text-amber-400 drop-shadow-[0_0_6px_rgba(251,191,36,0.6)]"
                : "text-white/20 hover:text-amber-300/60"
            }`}
            aria-label={isFavorite ? "Remover favorito" : "Marcar favorito"}
          >
            ★
          </button>
        </div>
      </td>
    </tr>
  );
}

function SeverityBadge({ level }: { level: "Alto" | "Médio" | "Baixo" }) {
  const map = {
    Alto: "border-red-500/30 bg-red-500/10 text-red-300",
    Médio: "border-amber-500/30 bg-amber-500/10 text-amber-300",
    Baixo: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  } as const;
  return (
    <span className={`shrink-0 rounded-md border px-2 py-0.5 text-[10px] font-bold ${map[level]}`}>
      {level}
    </span>
  );
}

function RingKpi({
  label, value, sub, subColor, pct, color, dashed = false,
}: {
  label: string; value: string; sub: string; subColor: string;
  pct: number; color: string; dashed?: boolean;
}) {
  const size = 78, r = 30, sw = 5;
  const circ = 2 * Math.PI * r;
  const off = circ * (1 - Math.min(1, Math.max(0, pct / 100)));
  return (
    <div className="flex flex-col items-center justify-between gap-2 rounded-2xl border border-white/8 bg-white/[0.02] p-3 text-center transition-colors hover:border-white/15">
      <p className="text-[9px] font-bold uppercase tracking-widest text-slate-500">{label}</p>
      <div className="relative">
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={r} strokeWidth={sw} className="fill-none stroke-white/10" />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            strokeWidth={sw}
            className="fill-none"
            stroke={color}
            strokeLinecap="round"
            strokeDasharray={dashed ? "3 6" : circ}
            strokeDashoffset={dashed ? 0 : off}
            style={{ transition: "stroke-dashoffset 700ms ease" }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="font-mono text-lg font-bold text-white">{value}</span>
        </div>
      </div>
      <p className="text-[10px] font-semibold" style={{ color: subColor }}>{sub}</p>
    </div>
  );
}

function QualityShield({ score, label, color }: { score: number; label: string; color: string }) {
  return (
    <div className="relative flex-shrink-0" style={{ width: 116, height: 132 }}>
      <svg viewBox="0 0 116 132" width="116" height="132" style={{ filter: `drop-shadow(0 0 14px ${color}66)` }}>
        <defs>
          <linearGradient id="qualityShieldFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.20" />
            <stop offset="100%" stopColor={color} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <path
          d="M58 4 L108 22 V64 C108 96 86 118 58 128 C30 118 8 96 8 64 V22 Z"
          fill="url(#qualityShieldFill)"
          stroke={color}
          strokeWidth="2"
        />
        <path
          d="M58 16 L98 30 V64 C98 89 80 107 58 116 C36 107 18 89 18 64 V30 Z"
          fill="none"
          stroke={color}
          strokeWidth="1"
          strokeOpacity="0.35"
          strokeDasharray="3 4"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center pb-2">
        <span className="font-mono text-4xl font-bold leading-none text-white">{score}</span>
        <span className="mt-1 text-xs font-bold uppercase tracking-wider" style={{ color }}>{label}</span>
      </div>
    </div>
  );
}

function FreshnessTimeline({ pollSec }: { pollSec: number }) {
  const nodes = [
    { k: "15m", l: "Muito bom", c: "#00f5a0" },
    { k: "10m", l: "Bom", c: "#00f5a0" },
    { k: "5m", l: "Atenção", c: "#ffd166" },
    { k: "2m", l: "Ruim", c: "#ff9f43" },
    { k: "Agora", l: "Crítico", c: "#ff4d6d" },
  ];
  const thresholds = [20, 25, 30, 40];
  let active = thresholds.findIndex((t) => pollSec <= t);
  if (active === -1) active = 4;
  const activeColor = nodes[active].c;
  const fillPct = (active / (nodes.length - 1)) * 100;
  const ideal = pollSec <= 20;

  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.02] p-4">
      <div className="mb-6 flex items-center justify-between gap-2">
        <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400">Frescor dos dados</h3>
        <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-semibold text-slate-300">
          Atual: {pollSec}s
        </span>
      </div>

      {/* Trilha */}
      <div className="relative mx-1 h-1 rounded-full bg-white/10">
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ width: `${fillPct}%`, background: "linear-gradient(90deg,#00f5a0,#ffd166)", transition: "width 700ms ease" }}
        />
        {nodes.map((n, i) => {
          const left = (i / (nodes.length - 1)) * 100;
          const isActive = i === active;
          const reached = i <= active;
          return (
            <div
              key={n.k}
              className={`absolute rounded-full ${isActive ? "animate-pulse" : ""}`}
              style={{
                left: `${left}%`,
                top: "50%",
                transform: "translate(-50%,-50%)",
                width: isActive ? 14 : 9,
                height: isActive ? 14 : 9,
                background: reached ? n.c : "#334155",
                boxShadow: isActive ? `0 0 8px 2px ${n.c}88` : "none",
                border: isActive ? "2px solid rgba(255,255,255,0.75)" : "none",
              }}
            />
          );
        })}
      </div>

      {/* Rótulos */}
      <div className="mt-4 flex justify-between">
        {nodes.map((n) => (
          <div key={n.k} className="text-center">
            <p className="text-[10px] font-bold text-slate-300">{n.k}</p>
            <p className="text-[9px] text-slate-500">{n.l}</p>
          </div>
        ))}
      </div>

      <div className="mt-5 flex items-start gap-3 rounded-xl border border-white/[0.06] bg-black/20 px-3 py-2.5">
        <span className="mt-1 h-2 w-2 shrink-0 rounded-full" style={{ background: activeColor }} />
        <p className="text-[11px] leading-relaxed text-slate-400">
          {ideal
            ? `Intervalo de atualização ${pollSec}s está dentro do ideal (≤ 20s).`
            : `Intervalo de atualização ${pollSec}s está acima do ideal (≤ 20s). Maior latência pode impactar a precisão dos sinais.`}
        </p>
      </div>
    </div>
  );
}

function QualityDataTab({
  data, pollSec, isFetching, lastUpdate, eventId, phaseLabel,
}: {
  data: SuperbetLiveAdvice;
  pollSec: number;
  isFetching: boolean;
  lastUpdate: string;
  eventId: number;
  phaseLabel: string;
}) {
  const quality = computeQualityScore(data);
  const conf = data.confidence;
  const confPct = Math.round((conf?.score ?? 0) * 100);

  const scan = data.strategy?.marketScan ?? [];
  const total = scan.length;
  const positive = scan.filter((r) => r.expectedValue > 0).length;
  const evPositivePct = total ? Math.round((positive / total) * 100) : 0;
  const withModel = scan.filter((r) => (r.modelProb ?? 0) > 0).length;
  const completePct = total ? Math.round((withModel / total) * 100) : 0;

  // Distribuição do estado dos mercados
  const esticando = scan.filter((r) => r.expectedValue > 0.05).length;
  const estavel = scan.filter((r) => r.expectedValue > -0.02 && r.expectedValue <= 0.05).length;
  const encurtando = scan.filter((r) => r.expectedValue <= -0.02).length;
  const suspensos = Math.max(0, data.rawMarketCount - total);
  const distTotal = esticando + estavel + encurtando + suspensos || 1;
  const dist = [
    { key: "Esticando", n: esticando, c: "#00f5a0" },
    { key: "Estável", n: estavel, c: "#ffd166" },
    { key: "Encurtando", n: encurtando, c: "#ff4d6d" },
    { key: "Suspensos", n: suspensos, c: "#64748b" },
  ];

  // Mercados suspeitos
  const suspectCount = encurtando + suspensos;
  const suspectPct = data.rawMarketCount ? Math.round((suspectCount / data.rawMarketCount) * 100) : 0;
  const alta = scan.filter((r) => r.expectedValue < -0.1).length + suspensos;
  const media = scan.filter((r) => r.expectedValue <= -0.04 && r.expectedValue >= -0.1).length;
  const baixa = scan.filter((r) => r.expectedValue < 0 && r.expectedValue > -0.04).length;
  const sTotal = alta + media + baixa || 1;
  const altaPct = Math.round((alta / sTotal) * 100);
  const mediaPct = Math.round((media / sTotal) * 100);
  const baixaPct = Math.max(0, 100 - altaPct - mediaPct);

  // Alertas derivados
  const alerts: { text: string; level: "Alto" | "Médio" | "Baixo"; icon: string }[] = [];
  if (pollSec > 20) alerts.push({ text: "Dados potencialmente desatualizados.", level: "Alto", icon: "⚠️" });
  if (pollSec > 30) alerts.push({ text: "Frequência de atualização abaixo do ideal.", level: "Alto", icon: "〰️" });
  if (total > 0 && encurtando > total * 0.25) alerts.push({ text: "Muitos mercados em estado de evitar/revisar.", level: "Médio", icon: "🛑" });
  if (conf && confPct < 60) alerts.push({ text: "Baixa confiança média dos sinais.", level: "Médio", icon: "📉" });
  (data.liveStats?.warnings ?? []).forEach((w) => alerts.push({ text: w, level: "Médio", icon: "🛑" }));
  const alertCount = alerts.length;

  const confColor = confPct >= 60 ? "#00f5a0" : confPct >= 40 ? "#ffd166" : "#ff4d6d";
  const evColor = evPositivePct >= 40 ? "#00f5a0" : evPositivePct >= 20 ? "#ffd166" : "#ff9f43";
  const completeColor = completePct >= 90 ? "#00f5a0" : completePct >= 60 ? "#ffd166" : "#ff9f43";

  return (
    <div className="space-y-4">
      {/* Hero */}
      <div className="text-center">
        <h1 className="font-display text-3xl font-bold tracking-tight text-white">
          Data <span className="text-neon-green">Quality</span>
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Monitor the reliability and freshness of signals in real time.
        </p>
        <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-neon-green/20 bg-neon-green/5 px-3 py-1 text-[11px] font-semibold text-neon-green">
          {phaseLabel} · Superbet #{eventId}
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-7">
        {/* Shield */}
        <div className="col-span-2 flex items-center gap-4 rounded-2xl border border-white/8 bg-white/[0.02] p-4 sm:col-span-3 xl:col-span-2">
          <QualityShield score={quality.score} label={quality.label} color={quality.color} />
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Qualidade dos dados</p>
            <p className="mt-2 text-xs leading-relaxed text-slate-400">
              {quality.score >= 80
                ? "Dados completos e estáveis — alta precisão dos sinais."
                : quality.score >= 60
                  ? "Boa cobertura de dados — confiança razoável."
                  : quality.score >= 40
                    ? "Qualidade abaixo do ideal. Atenção com sinais instáveis e mercados suspensos."
                    : "Dados escassos e instáveis — evite apostas grandes."}
            </p>
          </div>
        </div>

        <RingKpi label="Confiança média" value={`${confPct}%`} sub={confPct >= 60 ? "Boa confiança" : "Baixa confiança"} subColor={confColor} pct={confPct} color={confColor} />
        <RingKpi label="Intervalo médio" value={`${pollSec}s`} sub="Atualização" subColor="#94a3b8" pct={100} color="#00e0ff" dashed />
        <RingKpi label="Mercados completos" value={`${completePct}%`} sub={completePct >= 90 ? "Saudável" : "Parcial"} subColor={completeColor} pct={completePct} color={completeColor} />
        <RingKpi label="EV positivo" value={`${evPositivePct}%`} sub={evPositivePct >= 40 ? "Saudável" : "Abaixo do ideal"} subColor={evColor} pct={evPositivePct} color={evColor} />

        {/* Alertas ativos */}
        <div className="flex flex-col items-center justify-center gap-1 rounded-2xl border border-amber-500/30 bg-amber-500/5 p-3 text-center">
          <p className="text-[9px] font-bold uppercase tracking-widest text-amber-300/80">Alertas ativos</p>
          <svg viewBox="0 0 24 24" className="h-6 w-6 text-neon-orange" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M13.7 21a2 2 0 0 1-3.4 0" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="font-mono text-2xl font-bold text-white">{alertCount}</span>
          <span className="text-[10px] text-slate-500">itens ativos</span>
        </div>
      </div>

      {/* Alertas ativos + Frescor dos dados */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,420px)_1fr]">
        <div className="rounded-2xl border border-white/8 bg-white/[0.02] p-4">
          <div className="mb-3 flex items-center gap-2">
            <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400">Alertas ativos</h3>
            <span className="flex h-5 min-w-[20px] items-center justify-center rounded-full bg-amber-500/20 px-1.5 text-[10px] font-bold text-amber-300">{alertCount}</span>
          </div>
          {alertCount > 0 ? (
            <div className="space-y-2">
              {alerts.map((a, i) => (
                <div key={i} className="flex items-center gap-3 rounded-xl border border-white/[0.05] bg-black/20 px-3 py-2.5">
                  <span className="text-base" aria-hidden>{a.icon}</span>
                  <p className="flex-1 text-xs text-slate-300">{a.text}</p>
                  <SeverityBadge level={a.level} />
                </div>
              ))}
            </div>
          ) : (
            <p className="rounded-xl border border-white/[0.05] bg-black/20 px-3 py-6 text-center text-xs text-slate-600">
              Nenhum alerta ativo.
            </p>
          )}
          <button
            type="button"
            className="mt-3 flex items-center gap-1 text-[11px] font-semibold text-neon-blue transition hover:text-white"
          >
            Ver todos os alertas
            <IconChevronRight className="h-3 w-3" />
          </button>
        </div>

        <FreshnessTimeline pollSec={pollSec} />
      </div>

      {/* Mercados suspeitos + Distribuição */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-white/8 bg-white/[0.02] p-4">
          <h3 className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-400">Mercados suspeitos</h3>
          <div className="flex items-end gap-4">
            <div>
              <p className="font-mono text-4xl font-bold text-neon-red">{suspectPct}%</p>
              <p className="mt-1 max-w-[130px] text-[11px] text-slate-500">dos mercados apresentam sinais de risco</p>
            </div>
            <div className="flex-1">
              <div className="flex h-2 overflow-hidden rounded-full bg-white/5">
                <div style={{ width: `${altaPct}%`, background: "#ff4d6d" }} />
                <div style={{ width: `${mediaPct}%`, background: "#ffd166" }} />
                <div style={{ width: `${baixaPct}%`, background: "#00f5a0" }} />
              </div>
              <div className="mt-2 flex justify-between text-center text-[10px]">
                <div><p className="font-bold text-neon-red">{altaPct}%</p><p className="text-slate-500">Alta suspeita</p></div>
                <div><p className="font-bold text-neon-yellow">{mediaPct}%</p><p className="text-slate-500">Média suspeita</p></div>
                <div><p className="font-bold text-neon-green">{baixaPct}%</p><p className="text-slate-500">Baixa suspeita</p></div>
              </div>
            </div>
          </div>
          <button
            type="button"
            className="mt-4 flex items-center gap-1 text-[11px] font-semibold text-neon-blue transition hover:text-white"
          >
            Ver mercados
            <IconChevronRight className="h-3 w-3" />
          </button>
        </div>

        <div className="rounded-2xl border border-white/8 bg-white/[0.02] p-4">
          <h3 className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-400">Distribuição do estado dos mercados</h3>
          <div className="flex h-2.5 overflow-hidden rounded-full bg-white/5">
            {dist.map((d) => (
              <div key={d.key} style={{ width: `${(d.n / distTotal) * 100}%`, background: d.c }} title={d.key} />
            ))}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-4">
            {dist.map((d) => (
              <div key={d.key} className="flex flex-col gap-0.5">
                <span className="flex items-center gap-1.5 text-[11px] text-slate-300">
                  <span className="h-2 w-2 rounded-full" style={{ background: d.c }} />
                  {d.key}
                </span>
                <span className="pl-3.5 text-[11px] font-semibold text-slate-400">
                  {Math.round((d.n / distTotal) * 100)}% <span className="text-slate-600">({d.n})</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Status bar */}
      <div className="flex items-center justify-center gap-2 rounded-2xl border border-white/[0.06] bg-black/20 px-4 py-2.5 text-[11px] text-slate-500">
        <svg viewBox="0 0 20 20" fill="currentColor" className={`h-3.5 w-3.5 text-neon-green ${isFetching ? "animate-spin" : ""}`}>
          <path fillRule="evenodd" d="M15.312 11.424a5.5 5.5 0 0 1-9.201 2.466l-.312-.311h2.433a.75.75 0 0 0 0-1.5H3.989a.75.75 0 0 0-.75.75v4.242a.75.75 0 0 0 1.5 0v-2.43l.31.31a7 7 0 0 0 11.712-3.138.75.75 0 0 0-1.46-.33Zm-7.66-8.848A5.5 5.5 0 0 1 18.5 10a.75.75 0 0 0 1.5 0 7 7 0 0 0-11.712-5.138l-.31.31V2.75a.75.75 0 0 0-1.5 0v4.243c0 .414.336.75.75.75h4.243a.75.75 0 0 0 0-1.5h-2.43l.31-.31Z" clipRule="evenodd" />
        </svg>
        Atualizando odds e recalculando sinais… Última atualização: {lastUpdate}
      </div>
    </div>
  );
}

function CollapsibleSection({
  title,
  defaultOpen = true,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.02]">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left"
      >
        <span className="text-sm font-semibold text-white">{title}</span>
        <IconChevronRight
          className={`h-4 w-4 shrink-0 text-slate-500 transition-transform duration-200 ${open ? "rotate-90" : ""}`}
        />
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

// ─── Bootstrap hero (carregando) ─────────────────────────────────────────────

function LiveBootstrapHero({
  homeTeam, awayTeam, score, minute, periodLabel,
}: {
  homeTeam: string; awayTeam: string; score: string;
  minute: number; periodLabel: string | null;
}) {
  return (
    <section className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-slate-900/80 via-slate-900/40 to-slate-950/90 p-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <TeamFlag team={homeTeam} size={44} />
          <p className="truncate text-sm font-medium text-slate-300">{homeTeam}</p>
        </div>
        <div className="flex shrink-0 flex-col items-center px-2">
          <p className="font-mono text-4xl font-bold tracking-tight text-white">
            {score.replace("x", " × ")}
          </p>
          <div className="mt-1 flex items-center gap-2 rounded-full border border-white/10 bg-black/30 px-3 py-1 text-xs font-semibold text-amber-200">
            {minute}&apos;{periodLabel ? ` · ${periodLabel}` : ""}
          </div>
        </div>
        <div className="flex min-w-0 flex-1 items-center justify-end gap-3">
          <p className="truncate text-sm font-medium text-slate-300">{awayTeam}</p>
          <TeamFlag team={awayTeam} size={44} />
        </div>
      </div>
      <p className="mt-4 text-center text-xs text-slate-500" aria-live="polite">
        Carregando modelo in-play…
      </p>
    </section>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export function LiveDashboardPage() {
  const { eventId: eventIdParam } = useParams();
  const [searchParams] = useSearchParams();
  const { setChrome } = useLiveDashboardChrome();
  const advicePhase = resolveLiveAdvicePhase(searchParams);
  const eventId = Number.parseInt(eventIdParam ?? "", 10);
  const [activeTab, setActiveTab] = useState<LiveDashboardTab>("resumo");
  const [riskAlerts, setRiskAlerts] = useState<OddsDropAlert[]>([]);
  const [favoriteMarkets, setFavoriteMarkets] = useState<Set<string>>(new Set());
  const [showOnlyFavs, setShowOnlyFavs] = useState(false);
  const [nextCountdown, setNextCountdown] = useState(0);
  const ticket = useTicket();

  const handleRiskAlerts = useCallback((newAlerts: OddsDropAlert[]) => {
    setRiskAlerts((prev) => {
      const existingIds = new Set(prev.map((a) => a.id));
      const fresh = newAlerts.filter((a) => !existingIds.has(a.id));
      if (fresh.length === 0) return prev;
      return [...prev, ...fresh].slice(-8);
    });
  }, []);

  const {
    data, scoreTick, liveHeader,
    isLoading, isAdvicePending, isError, error,
    isFetching, refetch, timelineReactive, pollMs,
  } = useLiveAdviceQueries(eventId, 1000, null, advicePhase);

  const copilotEnabled = Boolean(data?.isLive && !data?.isFinished && eventId > 0);
  const { alertsActive: copilotAlertsActive } = useCopilotAlertsPreference();
  const copilotQuery = useLiveCopilotQuery({
    eventId,
    sport: "football",
    phase: advicePhase,
    bankroll: 1000,
    enabled: copilotEnabled,
  });

  useLiveCopilotActionAlerts(copilotQuery.data, {
    eventId,
    homeTeam: data?.homeTeam,
    awayTeam: data?.awayTeam,
    enabled: copilotEnabled && copilotAlertsActive,
  });

  const addCopilotLegsToTicket = useCallback(
    (legs: import("@/domain/entities").LiveCopilotUiLeg[]) => {
      if (!data) return;
      legs.forEach((perna) => {
        ticket.add({
          id: `${eventId}_${perna.market}_${perna.outcome}`,
          home: data.homeTeam,
          away: data.awayTeam,
          group: null,
          kickoff: "",
          label: perna.label,
          market: perna.market,
          fairOdd:
            perna.modelProb != null && perna.modelProb > 0
              ? +(1 / perna.modelProb).toFixed(2)
              : perna.marketOdd ?? 0,
          modelProb: perna.modelProb ?? 0,
          confidence:
            (perna.expectedValue ?? 0) >= 0.1
              ? "Alta"
              : (perna.expectedValue ?? 0) >= 0.05
                ? "Média"
                : "Baixa",
          type: "live",
          liveMinute: data.minute,
          liveScore: data.currentScore ?? undefined,
        });
      });
    },
    [data, eventId, ticket],
  );

  const { displayCopilot, agentChat } = useLiveCopilotAgentSession({
    eventId,
    sport: "football",
    phase: advicePhase,
    bankroll: 1000,
    enabled: copilotEnabled,
    baseCopilot: copilotQuery.data,
    onAddTicketLegs: (legs) => {
      addCopilotLegsToTicket(legs);
      setActiveTab("bilhete");
    },
    onSwitchTab: (tab) => setActiveTab(tab),
  });

  const possessionHistory = useLivePossessionHistory(data);
  const { history: predictionHistory } = useLivePredictionHistory(data);
  const pressureHistory = useMemo(() => {
    const marketHistory = predictionHistory
      .map((tick) => {
        const rawHome =
          tick.h2hImplied["1"] != null
            ? tick.h2hImplied["1"] * 100
            : tick.h2hOdds["1"] != null
              ? 100 / tick.h2hOdds["1"]
              : null;
        const rawAway =
          tick.h2hImplied["2"] != null
            ? tick.h2hImplied["2"] * 100
            : tick.h2hOdds["2"] != null
              ? 100 / tick.h2hOdds["2"]
              : null;
        if (rawHome == null || rawAway == null) return null;
        const total = rawHome + rawAway;
        if (total <= 0) return null;
        return {
          minute: tick.minute,
          home: (rawHome / total) * 100,
          away: (rawAway / total) * 100,
          capturedAt: tick.capturedAt,
        };
      })
      .filter((sample): sample is { minute: number; home: number; away: number; capturedAt: string | null } => sample != null);

    return marketHistory.length >= 2 ? marketHistory.slice(-36) : possessionHistory;
  }, [predictionHistory, possessionHistory]);
  const recalibrationEvent = useLiveRecalibration(data, isFetching);
  useOddsDropMonitor(data, handleRiskAlerts);

  useEffect(() => {
    if (isFetching) return;
    setNextCountdown(Math.round(pollMs.fast / 1000));
  }, [isFetching, pollMs.fast]);

  useEffect(() => {
    const id = window.setInterval(() => {
      setNextCountdown((current) => Math.max(0, current - 1));
    }, 1000);
    return () => window.clearInterval(id);
  }, []);

  const liveSuggestions = useMemo<TicketLeg[]>(() => {
    if (!data?.aportes) return [];
    return data.aportes
      .filter((a) => a.action === "apostar" || a.action === "aporte")
      .map((a) => ({
        id: `${eventId}_${a.market}_${a.outcome}`,
        home: data.homeTeam,
        away: data.awayTeam,
        group: null,
        kickoff: "",
        label: a.label,
        market: a.market,
        fairOdd: a.modelProb > 0 ? +(1 / a.modelProb).toFixed(2) : a.marketOdd,
        modelProb: a.modelProb,
        confidence:
          a.expectedValue >= 0.1 ? "Alta" : a.expectedValue >= 0.05 ? "Média" : "Baixa",
        type: "live" as const,
        liveMinute: data.minute,
        liveScore: data.currentScore ?? undefined,
      }));
  }, [data, eventId]);

  // ── KPI derivations ──
  const kpis = useMemo(() => {
    if (!data) return null;
    const scan = [...(data.strategy?.marketScan ?? [])];
    const bestEv = scan.sort((a, b) => b.expectedValue - a.expectedValue)[0];
    const total = scan.length;
    const positiveCount = scan.filter((r) => r.expectedValue > 0).length;
    const evPositivePct = total ? Math.round((positiveCount / total) * 100) : 0;
    const activeMarkets = data.rawMarketCount;
    const conf = data.confidence?.score ?? 0;
    const quality = computeQualityScore(data);
    const alertCount = data.strategy?.opportunityCount ?? 0;
    const pollSec = Math.round(pollMs.fast / 1000);

    return { bestEv, total, positiveCount, evPositivePct, activeMarkets, conf, quality, alertCount, pollSec };
  }, [data, pollMs.fast]);

  // Delta vs. leitura anterior (recalcula quando qualquer métrica muda)
  const kpiSig = kpis
    ? `${kpis.evPositivePct}|${kpis.activeMarkets}|${Math.round(kpis.conf * 100)}|${kpis.pollSec}|${kpis.alertCount}|${kpis.quality.score}`
    : "";
  const [kpiDeltas, setKpiDeltas] = useState<{
    ev: number; markets: number; conf: number; poll: number; alerts: number; quality: number;
  } | null>(null);
  const prevKpiRef = useRef<typeof kpis>(null);
  useEffect(() => {
    if (!kpis) return;
    const prev = prevKpiRef.current;
    if (prev) {
      setKpiDeltas({
        ev: kpis.evPositivePct - prev.evPositivePct,
        markets: kpis.activeMarkets - prev.activeMarkets,
        conf: Math.round(kpis.conf * 100) - Math.round(prev.conf * 100),
        poll: kpis.pollSec - prev.pollSec,
        alerts: kpis.alertCount - prev.alertCount,
        quality: kpis.quality.score - prev.quality.score,
      });
    }
    prevKpiRef.current = kpis;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kpiSig]);

  // ── Market table data ──
  const marketRows = useMemo(() => {
    if (!data) return [];
    return [...(data.strategy?.marketScan ?? [])]
      .sort((a, b) => b.expectedValue - a.expectedValue)
      .slice(0, 20);
  }, [data]);

  const displayedMarketRows = showOnlyFavs
    ? marketRows.filter((r) => favoriteMarkets.has(`${r.market}:${r.outcome}`))
    : marketRows;

  // ── Opportunities ──
  const topOpportunities = useMemo(() => {
    if (!data) return [];
    return [...(data.strategy?.opportunities ?? [])]
      .filter((o) => o.tier !== "abaixo_limiar" || o.expectedValue > 0)
      .slice(0, 6);
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

  const bootstrap = scoreTick ?? (data
    ? { homeTeam: data.homeTeam, awayTeam: data.awayTeam,
        currentScore: data.currentScore, minute: data.minute, periodLabel: data.periodLabel }
    : null);

  const opportunityCount = data?.strategy?.opportunityCount ?? 0;
  const strongCount = data?.strategy?.strongOpportunityCount ?? 0;

  // Deltas formatados dos KPIs (vs. leitura anterior)
  const trendOf = (d: number): "up" | "down" | "flat" => (d > 0 ? "up" : d < 0 ? "down" : "flat");
  const dd = kpiDeltas;
  const dEv: KpiDelta | undefined = dd ? { trend: trendOf(dd.ev), text: dd.ev === 0 ? "estável" : `${Math.abs(dd.ev)}pp vs anterior` } : undefined;
  const dMarkets: KpiDelta | undefined = dd ? { trend: trendOf(dd.markets), text: dd.markets === 0 ? "estável" : `${Math.abs(dd.markets)} ${dd.markets > 0 ? "novos" : "a menos"}` } : undefined;
  const dConf: KpiDelta | undefined = dd ? { trend: trendOf(dd.conf), text: dd.conf === 0 ? "estável" : `${dd.conf > 0 ? "+" : "-"}${Math.abs(dd.conf)}pp` } : undefined;
  const dPoll: KpiDelta | undefined = dd ? { trend: dd.poll === 0 ? "flat" : dd.poll > 0 ? "down" : "up", text: dd.poll === 0 ? "estável" : `${dd.poll > 0 ? "+" : "-"}${Math.abs(dd.poll)}s` } : undefined;
  const dAlerts: KpiDelta | undefined = dd ? { trend: trendOf(dd.alerts), text: dd.alerts === 0 ? "estável" : `${Math.abs(dd.alerts)} ${dd.alerts > 0 ? (Math.abs(dd.alerts) > 1 ? "novos" : "novo") : "a menos"}` } : undefined;
  const dQuality: KpiDelta | undefined = dd ? { trend: trendOf(dd.quality), text: dd.quality === 0 ? "estável" : `${dd.quality > 0 ? "+" : "-"}${Math.abs(dd.quality)} vs anterior` } : undefined;

  // Header: labels de atualização
  const nextSec = Math.round(pollMs.fast / 1000);
  const nextUpdateLabel = `${String(Math.floor((nextCountdown || nextSec) / 60)).padStart(2, "0")}:${String((nextCountdown || nextSec) % 60).padStart(2, "0")}`;
  const lastUpdateLabel = formatCapturedAt(liveHeader?.capturedAt ?? data?.capturedAt ?? null);
  const headerMinute = liveHeader?.minute ?? data?.minute ?? bootstrap?.minute ?? 0;
  const headerPeriod = liveHeader?.periodLabel ?? data?.periodLabel ?? bootstrap?.periodLabel ?? null;
  const scoreParts = ((liveHeader?.currentScore ?? data?.currentScore ?? bootstrap?.currentScore ?? "0x0").split(/x/i).map((s) => s.trim()));

  const matchHome = data?.homeTeam ?? bootstrap?.homeTeam ?? "—";
  const matchAway = data?.awayTeam ?? bootstrap?.awayTeam ?? "—";
  const hasScoreboardData = Boolean(data || bootstrap);

  const TABS: { id: LiveDashboardTab; label: string; count?: number }[] = [
    { id: "resumo", label: "Resumo Operacional" },
    { id: "mercados", label: "Mercados", count: opportunityCount > 0 ? (strongCount || opportunityCount) : undefined },
    { id: "qualidade", label: "Qualidade dos Dados" },
  ];
  const bilheteCount =
    ticket.legs.length > 0 ? ticket.legs.length : riskAlerts.length > 0 ? riskAlerts.length : 0;
  const headerIsLive =
    (data?.isLive && !data?.isFinished) ||
    (Boolean(bootstrap) && headerMinute > 0 && !data?.isFinished);

  useEffect(() => {
    setChrome({
      isLive: headerIsLive,
      lastUpdate: lastUpdateLabel,
      nextUpdate: nextUpdateLabel,
      isFetching,
      onRefresh: refetch,
    });
    return () => setChrome(null);
  }, [
    headerIsLive,
    lastUpdateLabel,
    nextUpdateLabel,
    isFetching,
    refetch,
    setChrome,
  ]);

  return (
    <PageTransition live className="space-y-0 pb-24">

      {/* Placar + abas (top bar unificada no AppLayout) */}
      <div className="sticky top-0 z-30 -mx-2 sm:-mx-4">
        {hasScoreboardData ? (
          <div className="live-scoreboard mx-2 mt-2 sm:mx-4">
            <div className="relative flex items-center justify-between gap-4 px-5 py-4">
              <div className="flex min-w-0 flex-1 items-center gap-3">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-full border border-white/12 bg-white/[0.06] shadow-[0_0_16px_rgba(0,245,160,0.12)]">
                  {matchHome !== "—" ? <TeamFlag team={matchHome} size={44} /> : null}
                </div>
                <span className="truncate text-base font-bold text-white sm:text-lg">{matchHome}</span>
              </div>

              <div className="flex shrink-0 flex-col items-center px-2">
                <div className="flex items-center gap-3 font-mono text-4xl font-extrabold leading-none text-white drop-shadow-[0_0_20px_rgba(255,255,255,0.08)]">
                  <span>{scoreParts[0] ?? "0"}</span>
                  <span className="text-2xl text-slate-500">×</span>
                  <span>{scoreParts[1] ?? "0"}</span>
                </div>
                <span className="mt-1.5 text-xs font-semibold text-amber-300">
                  {headerMinute}&apos;{headerPeriod ? ` · ${headerPeriod}` : ""}
                  {(data?.isLive && !data?.isFinished) || (bootstrap && headerMinute > 0 && !data?.isFinished)
                    ? " · Ao vivo"
                    : ""}
                </span>
              </div>

              <div className="flex min-w-0 flex-1 items-center justify-end gap-3">
                <span className="truncate text-right text-base font-bold text-white sm:text-lg">{matchAway}</span>
                <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-full border border-white/12 bg-white/[0.06] shadow-[0_0_16px_rgba(0,224,255,0.12)]">
                  {matchAway !== "—" ? <TeamFlag team={matchAway} size={44} /> : null}
                </div>
              </div>
            </div>

            {(data?.isLive && !data?.isFinished) || (bootstrap && headerMinute > 0) ? (
              <div className="px-5 pb-5 pt-1">
                <LiveMatchProgressBar minute={headerMinute} isLive={data?.isLive ?? Boolean(bootstrap)} />
              </div>
            ) : null}
          </div>
        ) : (
          <MatchScoreboardSkeleton />
        )}

        <LiveDashboardTabs
          tabs={TABS.map((tab) => ({ id: tab.id, label: tab.label, count: tab.count }))}
          activeId={activeTab}
          onChange={(id) => setActiveTab(id as LiveDashboardTab)}
        />
      </div>

      {/* ══ CONTENT ══ */}
      <div className="space-y-4 p-4 pt-3">
        {isLoading || (bootstrap && !data && activeTab === "resumo") ? (
          <LiveDashboardContentSkeleton />
        ) : isError ? (
          <ErrorState
            message={error instanceof Error ? error.message : "Falha ao capturar jogo na Superbet"}
            onRetry={refetch}
          />
        ) : (
          <>
            {data ? (
              <>
                {/* Alertas globais */}
                <LiveRecalibrationBanner event={recalibrationEvent} />
                <LiveP0GuardBanner guardrails={data.betGuardrails} />
                <LiveAgainstModelAlert alerts={data.againstModelAlerts ?? []} />
                <LiveHedgeAlert report={data.hedgeReport ?? null} />

                {/* ══ ABA: RESUMO OPERACIONAL ══ */}
                {activeTab === "resumo" && (
                  <div className="space-y-4">
                    <LiveCopilotPanel
                      copilot={displayCopilot}
                      isLoading={copilotQuery.isLoading}
                      isFetching={copilotQuery.isFetching}
                      agentChat={agentChat}
                      onAddBilheteToTicket={() => {
                        const bilhete = displayCopilot?.bilhete;
                        if (!bilhete?.pernas.length || !data) return;
                        addCopilotLegsToTicket(
                          bilhete.pernas.map((perna) => ({
                            market: perna.market,
                            outcome: perna.outcome,
                            label: perna.label,
                            modelProb: perna.modelProb,
                            marketOdd: perna.marketOdd,
                            expectedValue: perna.expectedValue,
                            edgePp: perna.edgePp,
                          })),
                        );
                        setActiveTab("bilhete");
                      }}
                    />

                    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_340px]">
                      <div className="live-glass-panel-glow glow-border rounded-2xl p-4">
                        <div className="mb-4 flex items-center gap-2">
                          <h2 className="text-xs font-black uppercase tracking-widest text-white">
                            Pressão Implícita
                          </h2>
                          <span className="rounded-full border border-neon-green/20 bg-neon-green/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-widest text-neon-green">
                            Ao Vivo
                          </span>
                          <button
                            type="button"
                            className="ml-1 text-slate-600 hover:text-slate-400"
                            aria-label="Info pressão implícita"
                          >
                            <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
                              <circle cx="12" cy="12" r="9" />
                              <path d="M12 10v6M12 7h.01" strokeLinecap="round" />
                            </svg>
                          </button>
                          {data.isLive && (
                            <span className="ml-auto flex items-center gap-1 text-[10px] text-slate-600">
                              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-neon-green" />
                              {Math.round(pollMs.fast / 1000)}s
                            </span>
                          )}
                        </div>
                        <PressureChart
                          homeTeam={data.homeTeam}
                          awayTeam={data.awayTeam}
                          history={pressureHistory}
                          currentMinute={liveHeader?.minute ?? data.minute}
                        />
                      </div>

                      {kpis && (
                        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-2">
                          <KpiCard
                            label="EV Positivo"
                            value={`${kpis.evPositivePct}%`}
                            icon="trend"
                            delta={dEv}
                            sub={`${kpis.positiveCount}/${kpis.total} mercados`}
                            accentColor="#00f5a0"
                          />
                          <KpiCard
                            label="Mercados Ativos"
                            value={String(kpis.activeMarkets)}
                            icon="activity"
                            delta={dMarkets}
                            sub={`${kpis.positiveCount} com EV positivo`}
                            accentColor="#00e0ff"
                          />
                          <KpiCard
                            label="Confiança Média"
                            value={`${Math.round(kpis.conf * 100)}%`}
                            icon="shield"
                            delta={dConf}
                            sub={data.confidence?.label ?? "—"}
                            accentColor="#c084fc"
                          />
                          <KpiCard
                            label="Intervalo Médio"
                            value={`${kpis.pollSec}s`}
                            icon="clock"
                            delta={dPoll}
                            sub={pollMs.tier === "urgent" ? "poll urgente" : pollMs.tier === "accelerated" ? "acelerado" : "estável"}
                            accentColor="#ffd166"
                          />
                          <KpiCard
                            label="Alertas Ativos"
                            value={String(kpis.alertCount)}
                            icon="bell"
                            delta={dAlerts}
                            sub={`${data.strategy?.strongOpportunityCount ?? 0} fortes`}
                            accentColor={kpis.alertCount > 0 ? "#00f5a0" : "#475569"}
                          />
                          <KpiCard
                            label="Qualidade dos Dados"
                            value={String(kpis.quality.score)}
                            icon="db"
                            badge={{ text: kpis.quality.label, color: kpis.quality.color }}
                            delta={dQuality}
                            accentColor={kpis.quality.color}
                            highlight
                          />
                        </div>
                      )}
                    </div>

                    {/* Oportunidades em Destaque */}
                    {topOpportunities.length > 0 && (
                      <div className="live-glass-panel rounded-2xl p-4">
                        <div className="mb-3 flex items-center justify-between gap-2">
                          <h2 className="text-xs font-black uppercase tracking-widest text-white">
                            Oportunidades em Destaque
                          </h2>
                          <span className="rounded-full bg-neon-green/15 px-2 py-0.5 text-[10px] font-bold text-neon-green">
                            {topOpportunities.length}
                          </span>
                        </div>
                        <div className="flex gap-3 overflow-x-auto pb-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                          {topOpportunities.map((opp) => (
                            <OpportunityCard
                              key={`${opp.market}-${opp.outcome}`}
                              label={opp.label}
                              market={opp.market}
                              outcome={opp.outcome}
                              ev={opp.expectedValue}
                              odd={opp.marketOdd}
                              confidence={opp.modelProb}
                              rank={opp.rank}
                              homeTeam={data.homeTeam}
                              awayTeam={data.awayTeam}
                              onAdd={() => {
                                const leg: TicketLeg = {
                                  id: `${eventId}_${opp.market}_${opp.outcome}`,
                                  home: data.homeTeam,
                                  away: data.awayTeam,
                                  group: null,
                                  kickoff: "",
                                  label: opp.label,
                                  market: opp.market,
                                  fairOdd: opp.modelProb > 0 ? +(1 / opp.modelProb).toFixed(2) : opp.marketOdd,
                                  modelProb: opp.modelProb,
                                  confidence: opp.expectedValue >= 0.1 ? "Alta" : "Média",
                                  type: "live",
                                  liveMinute: data.minute,
                                  liveScore: data.currentScore ?? undefined,
                                };
                                ticket.add(leg);
                                setActiveTab("bilhete");
                              }}
                            />
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Visão Geral de Mercados */}
                    <div className="live-glass-panel overflow-hidden rounded-2xl">
                      <div className="flex items-center justify-between gap-2 border-b border-white/[0.04] px-4 py-3">
                        <div className="flex items-center gap-2">
                          <h2 className="text-xs font-black uppercase tracking-widest text-white">
                            Visão Geral de Mercados
                          </h2>
                          <span className="text-[11px] text-slate-600">{marketRows.length} mercados</span>
                        </div>
                        <div className="flex items-center gap-1 rounded-lg border border-white/10 bg-black/20 p-0.5">
                          <button
                            onClick={() => setShowOnlyFavs(false)}
                            className={
                              !showOnlyFavs
                                ? "live-filter-pill-active"
                                : "rounded-md px-2.5 py-1 text-[10px] font-semibold text-slate-500 transition hover:text-slate-300"
                            }
                          >
                            Todos os mercados
                          </button>
                          <button
                            onClick={() => setShowOnlyFavs(true)}
                            className={`flex items-center gap-1 rounded-md px-2.5 py-1 text-[10px] font-semibold transition ${
                              showOnlyFavs
                                ? "live-filter-pill-active border-amber-500/35 bg-amber-500/12 text-amber-300"
                                : "text-slate-500 hover:text-slate-300"
                            }`}
                          >
                            <span aria-hidden>★</span>
                            Apenas favoritos
                          </button>
                        </div>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full min-w-[700px] text-left">
                          <thead>
                            <tr className="border-b border-white/[0.04]">
                              {["Mercado", "Seleção", "Odd Atual", "Odd Justa", "EV", "Pressão Implícita", "Direção", "Última Mudança", "Confiança"].map((h) => (
                                <th
                                  key={h}
                                  className={`py-2 text-[9px] font-black uppercase tracking-widest text-slate-600 ${h === "Mercado" ? "pl-4 pr-2" : h === "Confiança" ? "pl-2 pr-4" : "px-2"} ${["Odd Atual", "Odd Justa", "EV", "Pressão Implícita"].includes(h) ? "text-right" : ""}`}
                                >
                                  {h}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {displayedMarketRows.length > 0 ? (
                              displayedMarketRows.map((row) => {
                                const key = `${row.market}:${row.outcome}`;
                                return (
                                  <MarketRow
                                    key={key}
                                    label={row.label}
                                    market={row.market}
                                    outcome={row.outcome}
                                    marketOdd={row.marketOdd}
                                    modelProb={row.modelProb ?? row.impliedProb}
                                    ev={row.expectedValue}
                                    capturedAt={data.capturedAt}
                                    homeTeam={data.homeTeam}
                                    awayTeam={data.awayTeam}
                                    isFavorite={favoriteMarkets.has(key)}
                                    onToggleFav={() =>
                                      setFavoriteMarkets((prev) => {
                                        const next = new Set(prev);
                                        next.has(key) ? next.delete(key) : next.add(key);
                                        return next;
                                      })
                                    }
                                  />
                                );
                              })
                            ) : (
                              <tr>
                                <td colSpan={9} className="px-4 py-8 text-center text-sm text-slate-600">
                                  {showOnlyFavs ? "Nenhum favorito marcado." : "Nenhum mercado disponível."}
                                </td>
                              </tr>
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    <div className="live-glass-panel flex items-center justify-center gap-3 px-4 py-3 text-[11px] text-slate-500">
                      <svg viewBox="0 0 40 12" className={`live-status-pulse h-3 w-10 text-neon-green ${isFetching ? "animate-pulse" : ""}`} aria-hidden>
                        <polyline
                          points="0,6 4,6 6,2 8,10 10,6 14,6 16,3 18,9 20,6 24,6 26,1 28,11 30,6 40,6"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                      Atualizando odds e recalculando sinais…
                    </div>
                  </div>
                )}

                {/* ══ ABA: MERCADOS ══ */}
                {activeTab === "mercados" && (
                  <div className="space-y-4">
                    <LiveModelVsMarketHero data={data} />
                    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                      <LiveEvRealPanel data={data} />
                      <LiveEvLeaderboard data={data} />
                    </div>
                    <LiveCornersPanel data={data} />
                    <CollapsibleSection title="Todos os mercados com EV">
                      <LiveMarketCards data={data} />
                    </CollapsibleSection>
                    <CollapsibleSection title="Stats ao vivo" defaultOpen={true}>
                      <LiveStatsCompactBar data={data} eventId={eventId} />
                    </CollapsibleSection>
                    <LiveActionNowPanel data={data} trackBet={false} />
                    <LiveOptimizedTicketsPanel data={data} />
                    <LiveTopReturnPanel data={data} />
                    <LiveHalfTicketsPanel data={data} />
                    <LiveBestCombosPanel data={data} />
                    <CollapsibleSection title="Mercados 2T viáveis">
                      <LiveRemaining2hMarketsPanel data={data} />
                    </CollapsibleSection>
                    <CollapsibleSection title="Longshots (alto retorno)" defaultOpen={false}>
                      <LiveLongshotCombosPanel data={data} />
                    </CollapsibleSection>
                    <CollapsibleSection title="Estratégia completa" defaultOpen={false}>
                      <BetStrategyPanel strategy={data.strategy} />
                    </CollapsibleSection>
                    <CollapsibleSection title="Bet Builder — validação" defaultOpen={false}>
                      <LiveBetBuilderGuardPanel guardrails={data.betGuardrails} />
                    </CollapsibleSection>
                    <LiveContextUpload
                      eventId={eventId}
                      homeTeam={data.homeTeam}
                      awayTeam={data.awayTeam}
                      activeContext={data.matchContext ?? null}
                      onContextChanged={refetch}
                    />
                  </div>
                )}

                {/* ══ ABA: QUALIDADE DOS DADOS ══ */}
                {activeTab === "qualidade" && (
                  <div className="space-y-4">
                    <QualityDataTab
                      data={data}
                      pollSec={Math.round(pollMs.fast / 1000)}
                      isFetching={isFetching}
                      lastUpdate={formatCapturedAt(liveHeader?.capturedAt ?? data.capturedAt ?? null)}
                      eventId={eventId}
                      phaseLabel="V2 operacional"
                    />
                    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                      <LiveTimelinePanel
                        data={data}
                        highlightGoalMinute={timelineReactive.latestGoalMinute}
                        reactiveBoosted={timelineReactive.boosted}
                      />
                      <LiveFormH2hPanel data={data} />
                    </div>
                    <CollapsibleSection title="Evolução das probabilidades">
                      <LivePredictionEvolutionChart data={data} />
                    </CollapsibleSection>
                    <CollapsibleSection title="Sinais de tendência">
                      <LiveTrendSignals data={data} />
                    </CollapsibleSection>
                    <CollapsibleSection title="Heatmap de placares" defaultOpen={false}>
                      <LiveScoreHeatmap data={data} />
                    </CollapsibleSection>
                    <CollapsibleSection title="Match Stats" defaultOpen={false}>
                      <LiveMatchStatsPanel data={data} />
                    </CollapsibleSection>
                    <CollapsibleSection title="Jogadores & Radar social" defaultOpen={false}>
                      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                        <LivePlayerStatsPanel data={data} />
                        <LiveSocialRadarPanel data={data} />
                      </div>
                    </CollapsibleSection>
                  </div>
                )}

                {/* ══ ABA: MEU BILHETE ══ */}
                {activeTab === "bilhete" && (
                  <div className="space-y-4">
                    {riskAlerts.length > 0 && (
                      <LiveOddsDropAlert
                        alerts={riskAlerts}
                        onDismiss={(id) => setRiskAlerts((prev) => prev.filter((a) => a.id !== id))}
                      />
                    )}
                    <LiveOpenBetsPanel
                      eventId={eventId}
                      homeTeam={data?.homeTeam}
                      awayTeam={data?.awayTeam}
                    />
                    {data && <LiveOptimizedTicketsPanel data={data} />}
                    <TicketSimulator ticket={ticket} suggestions={liveSuggestions} />
                  </div>
                )}
              </>
            ) : bootstrap && activeTab !== "resumo" ? (
              <LiveBootstrapHero
                homeTeam={bootstrap.homeTeam}
                awayTeam={bootstrap.awayTeam}
                score={bootstrap.currentScore ?? "0x0"}
                minute={bootstrap.minute ?? 0}
                periodLabel={bootstrap.periodLabel ?? null}
              />
            ) : null}

            {isAdvicePending && (
              <p className="text-center text-[11px] text-slate-500" aria-live="polite">
                Calculando probabilidades e mercados…
              </p>
            )}
          </>
        )}
      </div>

      {activeTab !== "bilhete" && (
        <FloatingTicketBadge
          count={bilheteCount}
          onClick={() => setActiveTab("bilhete")}
        />
      )}
    </PageTransition>
  );
}
