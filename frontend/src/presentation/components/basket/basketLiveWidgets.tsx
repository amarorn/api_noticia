import Chart from "react-apexcharts";
import type { ApexOptions } from "apexcharts";
import type {
  BasketAporteAdvice,
  BasketInPlaySummary,
  BasketQuarterScore,
  BasketSuperbetLiveAdvice,
} from "@/domain/entities";

export const BASKET_LIVE_POLL_MS = 5_000;
export const DEFAULT_BASKET_MATCH_MINUTES = 48;

export type BasketLiveTab = "resumo" | "mercados" | "qualidade";

export function formatPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(0)}%`;
}

export function formatPoints(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export function formatCapturedAt(iso: string | null): string {
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

export function buildBasketKpis(data: BasketSuperbetLiveAdvice) {
  const s = data.inplaySummary;
  const positiveEv = data.aportes.filter((a) => a.expectedValue > 0).length;
  const leaderProb = Math.max(s.probHomeWin ?? 0, s.probAwayWin ?? 0);
  const leader =
    (s.probHomeWin ?? 0) >= (s.probAwayWin ?? 0) ? data.homeTeam : data.awayTeam;
  const totalDelta =
    s.marketTotalLine != null && s.expectedTotal != null
      ? s.expectedTotal - s.marketTotalLine
      : null;

  return {
    leader,
    leaderProb,
    totalDelta,
    totalLine: s.marketTotalLine,
    expectedTotal: s.expectedTotal,
    spreadLine: s.marketSpreadLine,
    remaining: s.remainingMinutes,
    ppmAvg:
      s.ppmHome != null && s.ppmAway != null ? (s.ppmHome + s.ppmAway) / 2 : null,
    ppmHome: s.ppmHome,
    ppmAway: s.ppmAway,
    positiveEv,
    totalAportes: data.aportes.length,
    confidence: data.confidence,
  };
}

export function BasketKpiCard({
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

export function QuarterPaceChart({
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
    plotOptions: { bar: { borderRadius: 6, columnWidth: "55%" } },
    dataLabels: { enabled: false },
    xaxis: {
      categories,
      labels: { style: { colors: "#64748b", fontSize: "10px" } },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: { labels: { style: { colors: "#64748b", fontSize: "10px" } } },
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

export function ProjectionPanel({
  summary,
  homeTeam,
  awayTeam,
}: {
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
          <p
            className={`mt-2 text-xs font-semibold ${delta > 0 ? "text-neon-green" : delta < 0 ? "text-red-400" : "text-slate-400"}`}
          >
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

export function ActionBadge({ action }: { action: string }) {
  const styles: Record<string, string> = {
    bet: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    strong_bet: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
    apostar: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    monitorar: "bg-amber-500/15 text-amber-300 border-amber-500/25",
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

export function OpportunityCard({ aporte, rank }: { aporte: BasketAporteAdvice; rank: number }) {
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

export function MarketRow({ aporte }: { aporte: BasketAporteAdvice }) {
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
      <td
        className={`px-2 py-2.5 text-right font-mono text-sm font-bold ${aporte.expectedValue > 0 ? "text-neon-green" : "text-red-400"}`}
      >
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

export function QuarterScoreTable({
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
              <td key={p.num} className="px-2 py-2 text-center font-mono text-slate-300">
                {p.home}
              </td>
            ))}
            <td className="px-2 py-2 text-center font-mono font-semibold text-neon-green">{homeTotal}</td>
          </tr>
          <tr className="border-t border-white/5">
            <td className="py-2 pr-3 font-medium text-white">{awayTeam}</td>
            {periods.map((p) => (
              <td key={p.num} className="px-2 py-2 text-center font-mono text-slate-300">
                {p.away}
              </td>
            ))}
            <td className="px-2 py-2 text-center font-mono font-semibold text-sky-400">{awayTotal}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
