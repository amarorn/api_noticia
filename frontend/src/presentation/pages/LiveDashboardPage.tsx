import { useMemo, useState, useCallback } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import Chart from "react-apexcharts";
import type { ApexOptions } from "apexcharts";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { IconArrowLeft, IconChevronRight } from "@/presentation/components/ui/Icons";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";

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
import { LiveMatchProbCard } from "@/presentation/components/predictions/LiveMatchProbCard";
import { LiveStatsProjectionPanel } from "@/presentation/components/predictions/LiveStatsProjectionPanel";

import { useLiveAdviceQueries } from "@/presentation/hooks/useLiveAdviceQueries";
import { useLivePossessionHistory } from "@/presentation/hooks/useLivePossessionHistory";
import { useLiveRecalibration } from "@/presentation/hooks/useLiveRecalibration";
import { resolveLiveAdvicePhase } from "@/presentation/utils/liveAdvicePhase";
import { useTicket, type TicketLeg } from "@/presentation/hooks/useTicket";
import { TicketSimulator, FloatingTicketBadge } from "@/presentation/components/ticket/TicketSimulator";
import { useOddsDropMonitor, type OddsDropAlert } from "@/presentation/hooks/useOddsDropMonitor";
import { LiveOddsDropAlert } from "@/presentation/components/predictions/LiveOddsDropAlert";
import { LiveOpenBetsPanel } from "@/presentation/components/predictions/LiveOpenBetsPanel";
import type { SuperbetLiveAdvice } from "@/domain/entities";

// ─── Types ───────────────────────────────────────────────────────────────────

type Tab = "resumo" | "mercados" | "qualidade" | "bilhete";

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

// ─── Sub-components ───────────────────────────────────────────────────────────

function MatchProgressBar({ minute, isLive }: { minute: number; isLive: boolean }) {
  const fullTime = 90;
  const pct = Math.min(100, (minute / fullTime) * 100);
  const extraTime = minute > 90;

  return (
    <div className="relative h-1 w-full overflow-hidden rounded-full bg-white/10">
      <div
        className="absolute inset-y-0 left-0 rounded-full transition-all duration-1000"
        style={{
          width: `${pct}%`,
          background: extraTime
            ? "linear-gradient(90deg, #f59e0b, #ef4444)"
            : "linear-gradient(90deg, #00ff88, #38bdf8)",
        }}
      />
      {isLive && !extraTime && (
        <div
          className="absolute top-1/2 h-3 w-3 -translate-y-1/2 -translate-x-1/2 animate-pulse rounded-full bg-white shadow-[0_0_6px_2px_rgba(255,255,255,0.4)]"
          style={{ left: `${pct}%` }}
        />
      )}
    </div>
  );
}

function KpiCard({
  label,
  value,
  sub,
  delta,
  deltaPositive,
  accentColor,
  badge,
}: {
  label: string;
  value: string;
  sub?: string;
  delta?: string;
  deltaPositive?: boolean;
  accentColor: string;
  badge?: { text: string; color: string };
}) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/8 bg-white/[0.03] p-3 backdrop-blur-sm">
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px opacity-80"
        style={{ background: accentColor }}
      />
      <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{label}</p>
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
      {delta && (
        <p
          className={`mt-1 text-[11px] font-semibold ${deltaPositive ? "text-emerald-400" : "text-red-400"}`}
        >
          {deltaPositive ? "↑" : "↓"} {delta}
        </p>
      )}
      {sub && !delta && (
        <p className="mt-1 truncate text-[11px] text-slate-500">{sub}</p>
      )}
    </div>
  );
}

function OpportunityCard({
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

  return (
    <div
      className={`relative flex min-w-[200px] flex-col gap-3 rounded-2xl border p-4 transition-all ${
        isTop
          ? "border-neon-green/30 bg-gradient-to-b from-neon-green/8 to-transparent"
          : "border-white/8 bg-white/[0.02]"
      }`}
    >
      {/* Badge */}
      <div className="flex items-center gap-1.5">
        {isTop && (
          <span className="rounded bg-neon-green/20 px-1.5 py-0.5 text-[9px] font-black uppercase tracking-widest text-neon-green">
            TOP
          </span>
        )}
        {isHot && <span className="text-sm">🔥</span>}
        <span className="ml-auto text-[11px] font-bold text-neon-blue">
          #{rank}
        </span>
      </div>

      {/* Market info */}
      <div>
        <p className="text-sm font-bold leading-tight text-white">
          {formatOutcomeLabel(outcome, homeTeam, awayTeam)}
        </p>
        <p className="mt-0.5 text-[11px] text-slate-500">{formatMarketLabel(market)}</p>
      </div>

      {/* Metrics */}
      <div className="flex items-end justify-between gap-2">
        <div className="space-y-1">
          <div>
            <p className="text-[9px] font-bold uppercase tracking-widest text-slate-600">EV</p>
            <p
              className={`font-mono text-base font-bold ${ev > 0.1 ? "text-neon-green" : ev > 0 ? "text-sky-400" : "text-red-400"}`}
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

        {/* Circular confidence */}
        <div className="relative flex flex-col items-center">
          <svg width="44" height="44" className="-rotate-90">
            <circle cx="22" cy="22" r="16" strokeWidth="3" className="fill-none stroke-white/10" />
            <circle
              cx="22"
              cy="22"
              r="16"
              strokeWidth="3"
              className="fill-none"
              stroke={confPct >= 60 ? "#00ff88" : confPct >= 40 ? "#fbbf24" : "#64748b"}
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

      {onAdd && (
        <button
          type="button"
          onClick={onAdd}
          className="w-full rounded-xl border border-neon-green/30 bg-neon-green/10 py-1.5 text-xs font-semibold text-neon-green transition hover:bg-neon-green/20"
        >
          + Bilhete
        </button>
      )}
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

  const chartOptions: ApexOptions = {
    chart: {
      type: "area",
      background: "transparent",
      toolbar: { show: false },
      fontFamily: "inherit",
      animations: { enabled: true, speed: 800 },
    },
    colors: ["#00ff88", "#38bdf8"],
    stroke: { curve: "smooth", width: [2, 2] },
    fill: {
      type: "gradient",
      gradient: {
        shadeIntensity: 1,
        opacityFrom: 0.3,
        opacityTo: 0.02,
        stops: [0, 100],
      },
    },
    dataLabels: { enabled: false },
    xaxis: {
      categories: history.map((h) => `${h.minute}'`),
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
    },
    grid: {
      borderColor: "#1e293b",
      strokeDashArray: 4,
      padding: { left: 0, right: 0 },
    },
    legend: { show: false },
    tooltip: {
      theme: "dark",
      y: { formatter: (val) => `${val.toFixed(0)}%` },
    },
    annotations: {
      xaxis: [
        {
          x: `${currentMinute}'`,
          borderColor: "#ffffff30",
          strokeDashArray: 4,
          label: {
            text: `${currentMinute}'`,
            style: { color: "#fff", background: "#1e293b", fontSize: "10px", padding: { top: 2, bottom: 2, left: 6, right: 6 } },
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
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div>
            <p className="font-mono text-2xl font-bold text-neon-green">
              {displayHome.toFixed(0)}%
            </p>
            <p className="text-xs font-semibold text-slate-400">{homeTeam}</p>
          </div>
          <div className="h-8 w-px bg-white/10" />
          <div>
            <p className="font-mono text-2xl font-bold text-sky-400">
              {displayAway.toFixed(0)}%
            </p>
            <p className="text-xs font-semibold text-slate-400">{awayTeam}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-slate-500">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-4 rounded-full bg-neon-green/60" />
            {homeTeam}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-4 rounded-full bg-sky-400/60" />
            {awayTeam}
          </span>
        </div>
      </div>

      {hasData ? (
        <Chart options={chartOptions} series={series} type="area" height={180} />
      ) : (
        <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-white/10 text-xs text-slate-600">
          Acumulando amostras de posse ao longo dos polls…
        </div>
      )}
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
  const direction = ev > 0.1 ? "↗ Valor" : ev > 0 ? "→ Estável" : "↘ Encurtando";
  const directionColor = ev > 0.1 ? "#00ff88" : ev > 0 ? "#94a3b8" : "#ef4444";
  const confPct = Math.min(100, Math.max(0, Math.round(50 + ev * 200)));

  return (
    <tr className="group border-t border-white/[0.04] transition-colors hover:bg-white/[0.02]">
      {/* Mercado */}
      <td className="py-2.5 pl-4 pr-2">
        <div className="flex items-center gap-2">
          <button
            onClick={onToggleFav}
            className={`text-sm transition ${isFavorite ? "text-amber-400" : "text-white/20 hover:text-white/40"}`}
          >
            ★
          </button>
          <div>
            <p className="text-xs font-semibold text-white">{formatMarketLabel(market)}</p>
            <p className="text-[10px] text-slate-600">{label.slice(0, 32)}</p>
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

      {/* Pressão implícita */}
      <td className="px-2 py-2.5 text-right">
        <span className="text-xs text-slate-400">{impliedPct.toFixed(0)}% mercado</span>
      </td>

      {/* Direção */}
      <td className="px-2 py-2.5">
        <span className="text-xs font-semibold" style={{ color: directionColor }}>
          {direction}
        </span>
      </td>

      {/* Última mudança */}
      <td className="px-2 py-2.5">
        <span className="text-[11px] text-slate-600">{formatCapturedAt(capturedAt)}</span>
      </td>

      {/* Confiança */}
      <td className="py-2.5 pl-2 pr-4">
        <div className="flex items-center gap-1.5">
          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${confPct}%`,
                backgroundColor: confPct >= 60 ? "#00ff88" : confPct >= 40 ? "#fbbf24" : "#64748b",
              }}
            />
          </div>
          <span className="w-8 text-right text-[10px] text-slate-500">{confPct}%</span>
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
  const advicePhase = resolveLiveAdvicePhase(searchParams);
  const eventId = Number.parseInt(eventIdParam ?? "", 10);
  const [activeTab, setActiveTab] = useState<Tab>("resumo");
  const [riskAlerts, setRiskAlerts] = useState<OddsDropAlert[]>([]);
  const [favoriteMarkets, setFavoriteMarkets] = useState<Set<string>>(new Set());
  const [showOnlyFavs, setShowOnlyFavs] = useState(false);
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

  const possessionHistory = useLivePossessionHistory(data);
  const recalibrationEvent = useLiveRecalibration(data, isFetching);
  useOddsDropMonitor(data, handleRiskAlerts);

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
    const positiveCount = scan.filter((r) => r.expectedValue > 0).length;
    const conf = data.confidence?.score ?? 0;
    const quality = computeQualityScore(data);
    const alertCount = data.strategy?.opportunityCount ?? 0;
    const pollSec = Math.round(pollMs.fast / 1000);

    return { bestEv, positiveCount, conf, quality, alertCount, pollSec };
  }, [data, pollMs.fast]);

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

  const TABS: { id: Tab; label: string; count?: number }[] = [
    { id: "resumo", label: "Resumo Operacional" },
    { id: "mercados", label: "Mercados", count: opportunityCount > 0 ? (strongCount || opportunityCount) : undefined },
    { id: "qualidade", label: "Qualidade dos Dados" },
    { id: "bilhete", label: "Meu Bilhete", count: ticket.legs.length > 0 ? ticket.legs.length : riskAlerts.length > 0 ? riskAlerts.length : undefined },
  ];

  return (
    <PageTransition className="space-y-0 pb-24">

      {/* ══ MATCH HERO ══ */}
      <div className="sticky top-0 z-30 bg-[#0a0e1a]/95 p-3 backdrop-blur-xl">
        <div className="overflow-hidden rounded-2xl border border-white/8 bg-white/[0.02]">
          {/* Nav bar */}
          <div className="flex items-center justify-between gap-3 px-4 py-3">
            <Link
              to="/ao-vivo"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 transition-colors hover:text-white"
            >
              <IconArrowLeft className="h-4 w-4" />
              <span className="hidden sm:inline">Ao vivo</span>
            </Link>

            {/* Score compact */}
            {data && (
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <TeamFlag team={data.homeTeam} size={28} />
                  <span className="text-sm font-medium text-slate-300 hidden sm:inline">
                    {data.homeTeam}
                  </span>
                </div>
                <div className="flex flex-col items-center px-2">
                  <span className="font-mono text-2xl font-bold leading-none text-white">
                    {(liveHeader?.currentScore ?? data.currentScore)?.replace("x", " × ") ?? "0 × 0"}
                  </span>
                  <span className="mt-1 text-[10px] text-amber-300 font-semibold">
                    {liveHeader?.minute ?? data.minute}&apos;
                    {(liveHeader?.periodLabel ?? data.periodLabel) ? ` · ${liveHeader?.periodLabel ?? data.periodLabel}` : ""}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-slate-300 hidden sm:inline">
                    {data.awayTeam}
                  </span>
                  <TeamFlag team={data.awayTeam} size={28} />
                </div>
              </div>
            )}

            <div className="flex items-center gap-2">
              {data?.isLive && !data?.isFinished && (
                <span className="inline-flex items-center gap-1 rounded-full border border-red-500/30 bg-red-500/10 px-2 py-1 text-[10px] font-bold text-red-300">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red-500" />
                  AO VIVO
                </span>
              )}
              <button
                onClick={refetch}
                disabled={isFetching}
                className="rounded-lg border border-white/10 bg-white/5 p-1.5 text-slate-400 transition hover:border-white/20 hover:text-white disabled:opacity-50"
                title="Atualizar"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`}
                >
                  <path fillRule="evenodd" d="M15.312 11.424a5.5 5.5 0 0 1-9.201 2.466l-.312-.311h2.433a.75.75 0 0 0 0-1.5H3.989a.75.75 0 0 0-.75.75v4.242a.75.75 0 0 0 1.5 0v-2.43l.31.31a7 7 0 0 0 11.712-3.138.75.75 0 0 0-1.46-.33Zm-7.66-8.848A5.5 5.5 0 0 1 18.5 10a.75.75 0 0 0 1.5 0 7 7 0 0 0-11.712-5.138l-.31.31V2.75a.75.75 0 0 0-1.5 0v4.243c0 .414.336.75.75.75h4.243a.75.75 0 0 0 0-1.5h-2.43l.31-.31Z" clipRule="evenodd" />
                </svg>
              </button>
              <div className="hidden flex-col items-end text-[10px] text-slate-600 sm:flex">
                <span>Última atualização {formatCapturedAt(liveHeader?.capturedAt ?? data?.capturedAt ?? null)}</span>
                <span>Próxima atualização {Math.round(pollMs.fast / 1000)}s</span>
              </div>
            </div>
          </div>

          {/* Progress bar */}
          {data?.isLive && !data?.isFinished && (
            <div className="px-4 pb-3">
              <MatchProgressBar minute={liveHeader?.minute ?? data.minute} isLive={data.isLive} />
            </div>
          )}

          {/* Tabs */}
          <div className="flex gap-1 border-t border-white/[0.04] p-2">
            {TABS.map((tab) => {
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`relative flex flex-1 items-center justify-center gap-1.5 rounded-xl px-2 py-2 text-[11px] font-semibold transition-colors ${
                    isActive
                      ? "bg-neon-green/15 text-neon-green"
                      : "text-slate-500 hover:bg-white/[0.03] hover:text-slate-300"
                  }`}
                >
                  {tab.label}
                  {tab.count != null && tab.count > 0 && (
                    <span className={`flex h-4 min-w-[16px] items-center justify-center rounded-full px-1 text-[9px] font-black ${
                      tab.id === "bilhete" && riskAlerts.length > 0
                        ? "bg-red-500 text-white animate-pulse"
                        : "bg-neon-green text-black"
                    }`}>
                      {tab.count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* ══ CONTENT ══ */}
      <div className="space-y-4 p-4">
        {isLoading ? (
          <DashboardSkeleton />
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

                    {/* Pressão implícita + KPIs */}
                    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_320px]">

                      {/* Gráfico pressão */}
                      <div className="rounded-2xl border border-white/8 bg-white/[0.02] p-4">
                        <div className="mb-3 flex items-center gap-2">
                          <h2 className="text-sm font-bold text-white">Pressão Implícita</h2>
                          <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[9px] font-bold uppercase tracking-widest text-slate-500">
                            Ao Vivo
                          </span>
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
                          history={possessionHistory}
                          currentMinute={liveHeader?.minute ?? data.minute}
                        />
                      </div>

                      {/* KPIs 3×2 */}
                      {kpis && (
                        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-2">
                          <KpiCard
                            label="EV Positivo"
                            value={kpis.bestEv ? `${(kpis.bestEv.expectedValue * 100).toFixed(0)}%` : "—"}
                            delta={kpis.bestEv ? `${kpis.positiveCount} mercados` : undefined}
                            deltaPositive
                            accentColor="#00ff88"
                          />
                          <KpiCard
                            label="Mercados Ativos"
                            value={String(data.rawMarketCount)}
                            sub={`${kpis.positiveCount} com EV positivo`}
                            accentColor="#38bdf8"
                          />
                          <KpiCard
                            label="Confiança Média"
                            value={`${Math.round(kpis.conf * 100)}%`}
                            sub={data.confidence?.label ?? "—"}
                            accentColor="#a855f7"
                          />
                          <KpiCard
                            label="Intervalo Médio"
                            value={`${kpis.pollSec}s`}
                            sub={pollMs.tier === "urgent" ? "poll urgente" : pollMs.tier === "accelerated" ? "acelerado" : "normal"}
                            accentColor="#fbbf24"
                          />
                          <KpiCard
                            label="Alertas Ativos"
                            value={String(kpis.alertCount)}
                            sub={`${data.strategy?.strongOpportunityCount ?? 0} fortes`}
                            accentColor={kpis.alertCount > 0 ? "#00ff88" : "#475569"}
                          />
                          <KpiCard
                            label="Qualidade dos Dados"
                            value={String(kpis.quality.score)}
                            badge={{ text: kpis.quality.label, color: kpis.quality.color }}
                            accentColor={kpis.quality.color}
                          />
                        </div>
                      )}
                    </div>

                    {/* Oportunidades em Destaque */}
                    {topOpportunities.length > 0 && (
                      <div className="rounded-2xl border border-white/8 bg-white/[0.02] p-4">
                        <div className="mb-3 flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <h2 className="text-sm font-bold text-white">Oportunidades em Destaque</h2>
                            <span className="rounded-full bg-neon-green/15 px-2 py-0.5 text-[10px] font-bold text-neon-green">
                              {topOpportunities.length}
                            </span>
                          </div>
                          <button
                            onClick={() => setActiveTab("bilhete")}
                            className="flex items-center gap-1 text-[11px] font-semibold text-neon-blue transition hover:text-white"
                          >
                            Ver bilhete
                            <IconChevronRight className="h-3 w-3" />
                          </button>
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
                    <div className="rounded-2xl border border-white/8 bg-white/[0.02] overflow-hidden">
                      <div className="flex items-center justify-between gap-2 border-b border-white/[0.04] px-4 py-3">
                        <div className="flex items-center gap-2">
                          <h2 className="text-sm font-bold text-white">Visão Geral de Mercados</h2>
                          <span className="text-[11px] text-slate-600">{marketRows.length} mercados</span>
                        </div>
                        <div className="flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 p-0.5">
                          <button
                            onClick={() => setShowOnlyFavs(false)}
                            className={`rounded-md px-2.5 py-1 text-[10px] font-semibold transition ${
                              !showOnlyFavs
                                ? "bg-neon-green/15 text-neon-green"
                                : "text-slate-500 hover:text-slate-300"
                            }`}
                          >
                            Todos os mercados
                          </button>
                          <button
                            onClick={() => setShowOnlyFavs(true)}
                            className={`flex items-center gap-1 rounded-md px-2.5 py-1 text-[10px] font-semibold transition ${
                              showOnlyFavs
                                ? "bg-amber-500/15 text-amber-300"
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

                    {/* Stats adicionais */}
                    <LiveMatchProbCard data={data} />
                    <LiveStatsProjectionPanel data={data} />
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
            ) : bootstrap ? (
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
          count={ticket.legs.length}
          onClick={() => setActiveTab("bilhete")}
        />
      )}
    </PageTransition>
  );
}
