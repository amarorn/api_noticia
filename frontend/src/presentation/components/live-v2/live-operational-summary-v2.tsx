import type {
  MarketOperationalRow,
  OddsHistoryPoint,
} from "@/presentation/components/live-operational/useMarketOperationalRows";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import type { DataQualityReport } from "@/presentation/components/live-operational/dataQuality";
import type { OperationalDecision } from "@/presentation/components/live-operational/liveOperationalUtils";
import { formatOdd } from "@/presentation/components/live-operational/liveOperationalUtils";
import {
  IconActivity,
  IconBell,
  IconClock,
  IconDatabase,
  IconShieldCheck,
  IconTrendingUp,
} from "@/presentation/components/ui/Icons";
import { LiveDecisionCardV2 } from "./live-decision-card-v2";
import { LiveMarketMiniChartV2 } from "./live-market-mini-chart-v2";
import { LiveMarketsOverviewV2 } from "./live-markets-overview-v2";
import { usePreviousOnChange } from "./usePreviousOnChange";

function deltaMeta(
  diff: number | null,
  options: {
    goodWhen: "up" | "down";
    suffix: string;
    formatValue?: (n: number) => string;
  },
) {
  if (diff == null) return { text: "sem histórico", tone: "text-slate-500" };
  if (diff === 0) return { text: "— estável", tone: "text-slate-500" };
  const up = diff > 0;
  const isGood = options.goodWhen === "up" ? up : !up;
  const arrow = up ? "↑" : "↓";
  const tone = isGood ? "text-emerald-300" : "text-red-300";
  const shown = options.formatValue ? options.formatValue(diff) : `${Math.abs(diff)}`;
  return { text: `${arrow} ${shown}${options.suffix}`, tone };
}

function KpiCard({
  icon,
  label,
  value,
  badge,
  delta,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  badge?: React.ReactNode;
  delta: { text: string; tone: string };
}) {
  return (
    <div className="panel-v2 p-3">
      <div className="flex items-center gap-2">
        <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg border border-white/8 bg-white/[0.04] text-neon-green">
          {icon}
        </span>
        <p className="truncate text-[9px] font-black uppercase tracking-[0.12em] text-slate-500">{label}</p>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <p className="font-mono text-2xl font-black text-white">{value}</p>
        {badge}
      </div>
      <p className={`mt-1 truncate text-[10px] font-semibold ${delta.tone}`}>{delta.text}</p>
    </div>
  );
}

function LiveKpiGridV2({
  data,
  rows,
  quality,
  isAdvicePending,
}: {
  data: SuperbetLiveAdvice;
  rows: MarketOperationalRow[];
  quality: DataQualityReport;
  isAdvicePending: boolean;
}) {
  const activeCount = rows.filter((r) => r.status === "ativo").length;
  const confidencePct = Math.round(quality.avgConfidence * 100);

  const snapshot = {
    evPct: quality.positiveEvPct,
    activeCount,
    confidencePct,
    avgUpdateSec: quality.avgUpdateSec ?? 0,
    alertsCount: quality.alerts.length,
    qualityScore: quality.score,
  };
  const prev = usePreviousOnChange(snapshot, data.capturedAt, isAdvicePending);

  const evDelta = deltaMeta(prev ? snapshot.evPct - prev.evPct : null, { goodWhen: "up", suffix: "pp" });
  const activeDelta = deltaMeta(prev ? snapshot.activeCount - prev.activeCount : null, {
    goodWhen: "up",
    suffix: "",
    formatValue: (n) => `${Math.abs(n)} ${Math.abs(n) === 1 ? (n > 0 ? "novo" : "a menos") : n > 0 ? "novos" : "a menos"}`,
  });
  const confidenceDelta = deltaMeta(prev ? snapshot.confidencePct - prev.confidencePct : null, { goodWhen: "up", suffix: "pp" });
  const intervalDelta = deltaMeta(prev ? snapshot.avgUpdateSec - prev.avgUpdateSec : null, { goodWhen: "down", suffix: "s" });
  const alertsDelta = deltaMeta(prev ? snapshot.alertsCount - prev.alertsCount : null, {
    goodWhen: "down",
    suffix: "",
    formatValue: (n) => `${Math.abs(n)} ${Math.abs(n) === 1 ? "novo" : "novos"}`,
  });
  const qualityDelta = deltaMeta(prev ? snapshot.qualityScore - prev.qualityScore : null, { goodWhen: "up", suffix: "" });

  const statusClass =
    quality.status === "Excelente" || quality.status === "Boa"
      ? "text-emerald-300 border-emerald-400/30 bg-emerald-400/10"
      : quality.status === "Atenção"
      ? "text-amber-300 border-amber-400/30 bg-amber-400/10"
      : "text-orange-300 border-orange-400/30 bg-orange-400/10";

  return (
    <div className="grid grid-cols-2 gap-3">
      <KpiCard icon={<IconTrendingUp className="h-4 w-4" />} label="EV Positivo" value={`${quality.positiveEvPct}%`} delta={evDelta} />
      <KpiCard icon={<IconActivity className="h-4 w-4" />} label="Mercados Ativos" value={String(activeCount)} delta={activeDelta} />
      <KpiCard icon={<IconShieldCheck className="h-4 w-4" />} label="Confiança Média" value={`${confidencePct}%`} delta={confidenceDelta} />
      <KpiCard
        icon={<IconClock className="h-4 w-4" />}
        label="Intervalo Médio"
        value={quality.avgUpdateSec != null ? `${quality.avgUpdateSec}s` : "N/D"}
        delta={intervalDelta}
      />
      <KpiCard icon={<IconBell className="h-4 w-4" />} label="Alertas Ativos" value={String(quality.alerts.length)} delta={alertsDelta} />
      <KpiCard
        icon={<IconDatabase className="h-4 w-4" />}
        label="Qualidade dos Dados"
        value={String(quality.score)}
        badge={<span className={`pill-v2 border px-2 py-0.5 text-[9px] ${statusClass}`}>{quality.status}</span>}
        delta={qualityDelta}
      />
    </div>
  );
}

function buildLine(seed: number, invert = false) {
  return Array.from({ length: 26 }, (_, i) => {
    const x = 12 + i * 10.6;
    const wave = Math.sin(i / 2.1 + seed) * 11 + Math.cos(i / 4 + seed) * 7;
    const y = invert ? 118 - wave - seed * 10 : 118 + wave - seed * 12;
    return `${x},${Math.max(28, Math.min(172, y))}`;
  }).join(" ");
}

const CHART_X_START = 12;
const CHART_X_END = 277;
const AXIS_TICKS = [15, 30, 45, 60, 75, 90] as const;

function tickX(minute: number) {
  return CHART_X_START + ((CHART_X_END - CHART_X_START) * minute) / 90;
}

function LivePressureOverviewV2({ data }: { data: SuperbetLiveAdvice }) {
  const homeProb = data.inplaySummary.probFinalHome || 0;
  const awayProb = data.inplaySummary.probFinalAway || 0;
  const total = Math.max(homeProb + awayProb, 0.01);
  const homePressure = Math.round((homeProb / total) * 100);
  const awayPressure = 100 - homePressure;
  const nowX = tickX(Math.max(0, Math.min(90, data.minute)));

  return (
    <section className="panel-v2 p-4 sm:p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-xs font-black uppercase tracking-[0.12em] text-slate-400">Pressão Implícita (Ao Vivo)</h2>
        <span className="chip-v2">{data.minute}'</span>
      </div>

      <div className="grid gap-4 lg:grid-cols-[150px_minmax(0,1fr)]">
        <div className="space-y-5">
          <div>
            <p className="font-mono text-3xl font-black text-neon-green">{homePressure}%</p>
            <p className="truncate text-xs font-bold uppercase tracking-wide text-slate-400">{data.homeTeam}</p>
          </div>
          <div>
            <p className="font-mono text-3xl font-black text-blue-400">{awayPressure}%</p>
            <p className="truncate text-xs font-bold uppercase tracking-wide text-slate-400">{data.awayTeam}</p>
          </div>
        </div>

        <div className="pressure-chart-v2 overflow-hidden">
          <svg viewBox="0 0 292 206" className="h-full w-full" role="img" aria-label="Pressão ao vivo">
            <defs>
              <linearGradient id="home-pressure-area" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgba(0,245,160,0.35)" />
                <stop offset="100%" stopColor="rgba(0,245,160,0)" />
              </linearGradient>
              <linearGradient id="away-pressure-area" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgba(59,130,246,0.28)" />
                <stop offset="100%" stopColor="rgba(59,130,246,0)" />
              </linearGradient>
            </defs>
            <polygon points={`12,188 ${buildLine(homeProb + 0.4)} 277,188`} fill="url(#home-pressure-area)" />
            <polygon points={`12,188 ${buildLine(awayProb + 1.2, true)} 277,188`} fill="url(#away-pressure-area)" />
            <polyline points={buildLine(homeProb + 0.4)} fill="none" stroke="#00f5a0" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            <polyline points={buildLine(awayProb + 1.2, true)} fill="none" stroke="#3b82f6" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
            <line x1={nowX} y1="18" x2={nowX} y2="188" stroke="rgba(250,204,21,0.7)" strokeDasharray="4 5" />
            <rect x={nowX - 12} y="10" width="29" height="16" rx="8" fill="rgba(0,245,160,0.16)" stroke="rgba(0,245,160,0.45)" />
            <text x={nowX + 2.5} y="21" textAnchor="middle" fill="#d1fae5" fontSize="9" fontWeight="700">{data.minute}'</text>
            {AXIS_TICKS.map((minute) => (
              <text key={minute} x={tickX(minute)} y="200" textAnchor="middle" fill="rgba(148,163,184,0.55)" fontSize="8" fontWeight="600">
                {minute === 90 ? "90'+" : `${minute}'`}
              </text>
            ))}
          </svg>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-5">
        <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-400">
          <span className="h-2 w-2 rounded-full" style={{ background: "#00f5a0" }} />
          {data.homeTeam}
        </span>
        <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-400">
          <span className="h-2 w-2 rounded-full" style={{ background: "#3b82f6" }} />
          {data.awayTeam}
        </span>
      </div>
    </section>
  );
}

function formatEvDisplay(ev: number): string {
  const pct = (ev * 100).toFixed(1);
  return ev > 0 ? `+${pct}%` : `${pct}%`;
}

function marketSubtitle(row: MarketOperationalRow): string {
  if (row.type === "Resultado") return "Resultado Final";
  if (row.market === "btts" || row.label.toLowerCase().includes("ambos")) return "Ambos Marcam";
  if (row.period !== "Jogo") return `${row.period} · ${row.type}`;
  return row.type;
}

function confidenceTone(score: number): { color: string } {
  const pct = Math.round(score * 100);
  if (pct >= 60) return { color: "#00ff88" };
  if (pct >= 40) return { color: "#fbbf24" };
  return { color: "#64748b" };
}

function OpportunityCardV2({ row, rank }: { row: MarketOperationalRow; rank: number }) {
  const displayRank = rank + 1;
  const isTop = rank === 0;
  const isHot = row.expectedValue > 0.3;
  const confidencePct = Math.round(row.confidenceScore * 100);
  const { color: confColor } = confidenceTone(row.confidenceScore);
  const circumference = 2 * Math.PI * 16;
  const dashOffset = circumference * (1 - row.confidenceScore);
  const showStake = row.action === "apostar" && row.suggestedStakeValue > 0;

  return (
    <article
      className={`signal-card-v2 relative flex h-full min-h-[176px] min-w-[210px] flex-col gap-2.5 overflow-hidden p-3.5 sm:min-w-[220px] sm:p-4 ${
        isTop ? "signal-card-v2--top live-opp-card-top" : ""
      }`}
    >
      {isTop && (
        <div className="pointer-events-none absolute left-0 top-0 z-10 h-12 w-12 overflow-hidden">
          <div className="absolute -left-7 top-2 w-24 rotate-[-45deg] bg-gradient-to-r from-amber-400 via-yellow-300 to-amber-500 py-0.5 text-center text-[8px] font-black uppercase tracking-wider text-black shadow-lg">
            TOP
          </div>
        </div>
      )}

      <div
        className={`relative z-20 flex min-h-[20px] items-center ${
          isTop ? "justify-end gap-1 pt-1" : "gap-1.5"
        }`}
      >
        {!isTop &&
          (isHot ? (
            <span className="text-sm leading-none" aria-hidden>
              🔥
            </span>
          ) : (
            <span className="h-3.5 w-3.5 shrink-0" />
          ))}
        {isTop && isHot && (
          <span className="text-sm leading-none" aria-hidden>
            🔥
          </span>
        )}
        <span className={`font-mono text-[11px] font-bold text-neon-blue ${isTop ? "" : "ml-auto"}`}>
          #{displayRank}
        </span>
      </div>

      <div className="min-h-[52px] min-w-0 flex-1 pr-1">
        <p className="line-clamp-2 text-sm font-bold leading-tight text-white" title={row.label}>
          {row.label}
        </p>
        <p className="mt-0.5 truncate text-[11px] text-slate-500">{marketSubtitle(row)}</p>
        {showStake ? (
          <span className="mt-1.5 inline-flex rounded-md border border-emerald-400/20 bg-emerald-400/10 px-1.5 py-0.5 text-[9px] font-bold text-emerald-300">
            Stake R$ {row.suggestedStakeValue.toFixed(2)}
          </span>
        ) : null}
      </div>

      <div className="mt-auto flex items-end justify-between gap-2">
        <div className="space-y-1">
          <div>
            <p className="text-[9px] font-bold uppercase tracking-widest text-slate-600">EV</p>
            <p
              className={`font-mono text-lg font-bold leading-none sm:text-xl ${
                row.expectedValue > 0.1
                  ? "text-neon-green neon-text"
                  : row.expectedValue > 0
                    ? "text-sky-400"
                    : "text-slate-400"
              }`}
            >
              {formatEvDisplay(row.expectedValue)}
            </p>
          </div>
          <div>
            <p className="text-[9px] font-bold uppercase tracking-widest text-slate-600">Odd</p>
            <p className="font-mono text-sm font-semibold text-white">{formatOdd(row.marketOdd)}</p>
          </div>
        </div>

        <div className="flex shrink-0 flex-col items-center">
          <div className="relative h-12 w-12">
            <svg
              width="48"
              height="48"
              viewBox="0 0 48 48"
              className="absolute inset-0 -rotate-90"
              style={{ filter: `drop-shadow(0 0 6px ${confColor}88)` }}
              aria-hidden
            >
              <circle cx="24" cy="24" r="16" strokeWidth="3" className="fill-none stroke-white/10" />
              <circle
                cx="24"
                cy="24"
                r="16"
                strokeWidth="3"
                className="fill-none"
                stroke={confColor}
                strokeDasharray={circumference}
                strokeDashoffset={dashOffset}
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute inset-0 grid place-items-center">
              <span className="font-mono text-[10px] font-bold tabular-nums leading-none text-white">
                {confidencePct}%
              </span>
            </div>
          </div>
          <span className="mt-0.5 text-[9px] font-semibold uppercase tracking-wide text-slate-600">Conf.</span>
        </div>
      </div>
    </article>
  );
}

function TopOpportunitiesV2({ rows }: { rows: MarketOperationalRow[] }) {
  const top = rows.slice(0, 6);

  return (
    <section className="panel-v2 p-4 sm:p-5">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-xs font-black uppercase tracking-widest text-white">Oportunidades em Destaque</h2>
        <span className="flex h-5 min-w-[20px] items-center justify-center rounded-full bg-neon-green/15 px-2 text-[10px] font-bold text-neon-green">
          {top.length}
        </span>
      </div>

      {top.length === 0 ? (
        <div className="empty-v2">
          <p className="text-sm font-semibold text-slate-200">Sem sinal operacional no momento</p>
          <p className="mt-1 text-xs text-slate-500">Aguardando mercado com odd, probabilidade do modelo e EV calculado.</p>
        </div>
      ) : (
        <div className="opportunities-rail-v2 -mx-1 px-1 pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {top.map((row, i) => (
            <OpportunityCardV2 key={row.key} row={row} rank={i} />
          ))}
        </div>
      )}
    </section>
  );
}

export function LiveOperationalSummaryV2({
  decision,
  bankroll,
  rows,
  history,
  data,
  quality,
  isAdvicePending,
}: {
  decision: OperationalDecision;
  bankroll: number;
  rows: MarketOperationalRow[];
  history: Record<string, OddsHistoryPoint[]>;
  data: SuperbetLiveAdvice;
  quality: DataQualityReport;
  isAdvicePending: boolean;
}) {
  const bestKey = decision.pick ? `${decision.pick.market}:${decision.pick.outcome}` : rows[0]?.key;

  return (
    <div className="space-y-4">
      <LiveDecisionCardV2 decision={decision} bankroll={bankroll} />

      <section className="grid gap-3 xl:grid-cols-[minmax(0,1.25fr)_minmax(330px,0.75fr)]">
        <LivePressureOverviewV2 data={data} />
        <LiveKpiGridV2 data={data} rows={rows} quality={quality} isAdvicePending={isAdvicePending} />
      </section>

      <TopOpportunitiesV2 rows={rows} />

      <LiveMarketMiniChartV2
        label={decision.pick?.label ?? rows[0]?.label ?? "Mercado recomendado"}
        points={bestKey ? history[bestKey] ?? [] : []}
      />

      <LiveMarketsOverviewV2 rows={rows} />
    </div>
  );
}
