import Chart from "react-apexcharts";
import type { ApexOptions } from "apexcharts";
import type { SuperbetLiveAdvice, Viable2hMarketRow } from "@/domain/entities";
import {
  SendComboProposalButton,
} from "@/presentation/components/predictions/SendComboProposalButton";
import { buildProposalFromInplayLeg } from "@/presentation/utils/comboProposalPayload";

interface LiveRemaining2hMarketsPanelProps {
  data: SuperbetLiveAdvice;
}

function formatPct(v: number): string {
  if (v >= 0.01) return `${(v * 100).toFixed(1)}%`;
  return `${(v * 100).toFixed(2)}%`;
}

const CATEGORY_COLORS: Record<string, string> = {
  "1x2": "#38bdf8",
  correct_score: "#f472b6",
  handicap: "#fbbf24",
  exact_goals: "#a78bfa",
  totals: "#00ff88",
  other: "#94a3b8",
};

function MarketRow({ row, data }: { row: Viable2hMarketRow; data: SuperbetLiveAdvice }) {
  const proposal = buildProposalFromInplayLeg(
    {
      market: row.market,
      outcome: row.outcome,
      label: row.label,
      modelProb: row.modelProb,
      marketOdd: row.marketOdd,
      expectedValue: row.expectedValue,
      edgePp: row.edgePp,
    },
    {
      homeTeam: data.homeTeam,
      awayTeam: data.awayTeam,
      superbetEventId: data.superbetEventId,
      minute: data.minute,
    },
  );

  return (
    <li className="rounded-lg border border-white/8 bg-black/25 px-3 py-2.5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <span
            className="mb-1 inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
            style={{
              backgroundColor: `${CATEGORY_COLORS[row.category] ?? "#64748b"}22`,
              color: CATEGORY_COLORS[row.category] ?? "#94a3b8",
            }}
          >
            {row.categoryLabel}
          </span>
          <p className="text-sm text-slate-100">{row.label}</p>
        </div>
        <span className="font-mono text-sm text-neon-green">@{row.marketOdd.toFixed(2)}</span>
      </div>
      <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-slate-500">
        <span className="text-sky-300">Prob. {formatPct(row.modelProb)}</span>
        <span>EV {(row.expectedValue * 100).toFixed(1)}%</span>
        <span>Edge {row.edgePp.toFixed(1)} pp</span>
        {row.meetsThreshold && (
          <span className="text-emerald-400">✓ edge OK</span>
        )}
      </div>
      <SendComboProposalButton proposal={proposal} compact className="mt-2" />
    </li>
  );
}

export function LiveRemaining2hMarketsPanel({ data }: LiveRemaining2hMarketsPanelProps) {
  const panel = data.viable2hMarkets;
  if (!panel) return null;

  const chart = panel.chart;
  const hasChart = chart.categories.length > 0;

  const chartOptions: ApexOptions = {
    chart: {
      type: "bar",
      background: "transparent",
      toolbar: { show: false },
      fontFamily: "inherit",
    },
    plotOptions: {
      bar: { horizontal: true, barHeight: "62%", borderRadius: 6, dataLabels: { position: "center" } },
    },
    dataLabels: {
      enabled: true,
      formatter: (val) => `${val}%`,
      style: { fontSize: "10px", colors: ["#0f172a"] },
    },
    xaxis: {
      categories: chart.categories,
      max: 100,
      labels: { style: { colors: "#94a3b8", fontSize: "11px" } },
    },
    yaxis: { labels: { style: { colors: "#cbd5e1", fontSize: "11px" } } },
    colors: ["#00ff88"],
    grid: { borderColor: "#1e293b", strokeDashArray: 4 },
    tooltip: {
      theme: "dark",
      y: { formatter: (v) => `${v}% prob. modelo` },
    },
  };

  return (
    <section className="rounded-2xl border border-sky-500/25 bg-gradient-to-br from-sky-500/[0.08] to-indigo-900/[0.06] p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wider text-sky-300/90">
            Tempo restante · 2º tempo
          </p>
          <h2 className="text-lg font-bold text-white">
            Mercados ainda viáveis no 2T
          </h2>
          <p className="mt-1 text-xs text-slate-400">
            Probabilidade do modelo condicionada ao placar e aos{" "}
            <span className="font-mono text-sky-200">{panel.minutesRemaining}&apos;</span>{" "}
            restantes ({formatPct(panel.remainingFraction)} do jogo).
          </p>
        </div>
        <div className="rounded-xl border border-sky-400/20 bg-black/30 px-3 py-2 text-right">
          <p className="text-[10px] uppercase text-slate-500">Minuto</p>
          <p className="font-mono text-xl font-bold text-white">{data.minute}&apos;</p>
          <p className="text-[10px] text-slate-500">até {panel.block2hMinute}&apos;</p>
        </div>
      </div>

      {panel.closed && (
        <p className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-400">
          {panel.closedReason ?? "Mercados do 2º tempo indisponíveis neste momento."}
        </p>
      )}

      {!panel.closed && hasChart && (
        <div className="mb-4 rounded-xl border border-white/8 bg-black/20 p-3">
          <p className="mb-2 text-xs font-semibold text-slate-300">
            Melhor opção por tipo — prob. do modelo (%)
          </p>
          <Chart
            type="bar"
            height={Math.max(160, chart.categories.length * 44)}
            options={chartOptions}
            series={[{ name: "Prob. modelo", data: chart.probabilitiesPct }]}
          />
        </div>
      )}

      {!panel.closed && panel.markets.length > 0 && (
        <ul className="space-y-2">
          {panel.markets.map((row) => (
            <MarketRow
              key={`${row.market}:${row.outcome}`}
              row={row}
              data={data}
            />
          ))}
        </ul>
      )}

      {!panel.closed && panel.markets.length === 0 && (
        <p className="text-sm text-slate-500">
          Nenhum mercado 2T acima de {(panel.minModelProb * 100).toFixed(0)}% de probabilidade
          neste refresh — aguarde o próximo poll ou abra os cards de mercado.
        </p>
      )}
    </section>
  );
}

export default LiveRemaining2hMarketsPanel;
