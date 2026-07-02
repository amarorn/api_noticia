import Chart from "react-apexcharts";
import type { ApexOptions } from "apexcharts";
import type { BasketInPlaySummary, BasketSuperbetLiveAdvice } from "@/domain/entities";

function formatPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function formatPoints(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

function parseScore(score: string | null): [number, number] {
  if (!score) return [0, 0];
  const parts = score.split(/x/i).map((s) => Number.parseInt(s.trim(), 10));
  return [parts[0] || 0, parts[1] || 0];
}

export function decodeSpreadLineKey(key: string): number | null {
  try {
    return Number.parseFloat(key.replace("p", "").replace("m", "-").replace("_", "."));
  } catch {
    return null;
  }
}

function formatSpreadLine(line: number, team: string): string {
  const sign = line > 0 ? "+" : "";
  return `${team} ${sign}${line}`;
}

function buildPpmChartOptions(
  categories: string[],
  yMax: number,
  currentIndex: number,
): ApexOptions {
  return {
    chart: {
      type: "area",
      background: "transparent",
      toolbar: { show: false },
      fontFamily: "inherit",
      animations: { enabled: true, speed: 700 },
      dropShadow: {
        enabled: true,
        top: 0,
        left: 0,
        blur: 8,
        opacity: 0.35,
        color: "#00ff88",
      },
    },
    colors: ["#00ff88", "#38bdf8"],
    stroke: { curve: "smooth", width: [3, 3] },
    fill: {
      type: "gradient",
      gradient: {
        shadeIntensity: 1,
        opacityFrom: 0.35,
        opacityTo: 0.02,
        stops: [0, 85, 100],
      },
    },
    markers: {
      size: 5,
      strokeWidth: 2,
      strokeColors: "#0a1020",
      hover: { size: 7 },
    },
    dataLabels: { enabled: false },
    xaxis: {
      categories,
      labels: { style: { colors: "#64748b", fontSize: "10px", fontWeight: 600 } },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      min: 0,
      max: yMax,
      tickAmount: 4,
      labels: {
        formatter: (v) => v.toFixed(1),
        style: { colors: "#64748b", fontSize: "10px" },
      },
    },
    grid: {
      borderColor: "rgba(30, 41, 59, 0.6)",
      strokeDashArray: 3,
      padding: { left: 4, right: 8, top: 4 },
    },
    legend: {
      show: true,
      position: "top",
      horizontalAlign: "right",
      labels: { colors: "#94a3b8" },
      fontSize: "10px",
      markers: { size: 4, offsetX: -2 },
    },
    tooltip: {
      theme: "dark",
      y: { formatter: (val) => (val != null ? `${val.toFixed(2)} PPM` : "—") },
    },
    annotations: {
      xaxis: [
        {
          x: categories[currentIndex] ?? categories[1],
          borderColor: "rgba(255, 209, 102, 0.55)",
          strokeDashArray: 4,
          label: {
            text: "Ao vivo",
            borderColor: "#ffd166",
            borderWidth: 0,
            position: "top",
            offsetY: -4,
            style: {
              color: "#050811",
              background: "#ffd166",
              fontSize: "9px",
              fontWeight: 700,
              padding: { top: 2, bottom: 2, left: 6, right: 6 },
            },
          },
        },
      ],
    },
  };
}

function PpmTeamAreaChart({
  team,
  color,
  prior,
  observed,
  projection,
}: {
  team: string;
  color: string;
  prior: number | null;
  observed: number | null;
  projection: number | null;
}) {
  const categories = ["Prior mercado", "Observado", "Projeção"];
  const values = [
    prior ?? null,
    observed ?? null,
    projection ?? null,
  ];
  const numeric = values.filter((v): v is number => v != null);
  const yMax = Math.max(...numeric, 1) * 1.15;

  const options: ApexOptions = {
    ...buildPpmChartOptions(categories, yMax, 1),
    colors: [color],
    chart: {
      ...buildPpmChartOptions(categories, yMax, 1).chart,
      dropShadow: {
        enabled: true,
        top: 0,
        left: 0,
        blur: 8,
        opacity: 0.35,
        color,
      },
    },
    legend: { show: false },
    stroke: { curve: "smooth", width: 3 },
  };

  return (
    <div className="rounded-xl border border-white/8 bg-black/20 p-3">
      <div className="mb-3 flex items-end justify-between gap-2">
        <p className="text-[11px] font-bold" style={{ color }}>
          {team}
        </p>
        <div className="text-right">
          <p className="font-mono text-xl font-bold leading-none text-white">
            {projection != null ? formatPoints(projection, 2) : "—"}
          </p>
          <p className="text-[9px] uppercase tracking-wide text-slate-500">proj. PPM</p>
        </div>
      </div>
      <Chart
        options={options}
        series={[{ name: team, data: values }]}
        type="area"
        height={160}
      />
      <div className="mt-2 grid grid-cols-3 gap-1 text-center text-[9px]">
        <div>
          <p className="text-slate-600">Prior</p>
          <p className="font-mono font-semibold text-slate-400">
            {prior != null ? formatPoints(prior, 2) : "—"}
          </p>
        </div>
        <div>
          <p className="text-amber-400/80">Observado</p>
          <p className="font-mono font-semibold text-amber-300">
            {observed != null ? formatPoints(observed, 2) : "—"}
          </p>
        </div>
        <div>
          <p style={{ color }}>Modelo</p>
          <p className="font-mono font-semibold text-white">
            {projection != null ? formatPoints(projection, 2) : "—"}
          </p>
        </div>
      </div>
    </div>
  );
}

export function PpmPacePanel({
  data,
  homeTeam,
  awayTeam,
}: {
  data: BasketSuperbetLiveAdvice;
  homeTeam: string;
  awayTeam: string;
}) {
  const s = data.inplaySummary;
  const [homeScore, awayScore] = parseScore(data.currentScore);
  const observedHome = data.minute > 0 ? homeScore / data.minute : null;
  const observedAway = data.minute > 0 ? awayScore / data.minute : null;

  return (
    <div className="live-glass-panel rounded-2xl p-4">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xs font-black uppercase tracking-widest text-white">
            Ritmo de pontos (PPM)
          </h2>
          <p className="mt-1 text-[11px] text-slate-500">
            Prior mercado → observado → projeção do modelo ·{" "}
            {s.remainingMinutes?.toFixed(0) ?? "—"} min restantes
          </p>
        </div>
        <div className="flex items-center gap-4 font-mono text-sm">
          <span className="text-neon-green neon-text">
            {s.ppmHome != null ? formatPoints(s.ppmHome, 2) : "—"} {homeTeam}
          </span>
          <span className="text-slate-600">·</span>
          <span className="text-sky-400">
            {s.ppmAway != null ? formatPoints(s.ppmAway, 2) : "—"} {awayTeam}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <PpmTeamAreaChart
          team={homeTeam}
          color="#00ff88"
          prior={s.ppmHomePrior}
          observed={observedHome}
          projection={s.ppmHome}
        />
        <PpmTeamAreaChart
          team={awayTeam}
          color="#38bdf8"
          prior={s.ppmAwayPrior}
          observed={observedAway}
          projection={s.ppmAway}
        />
      </div>
    </div>
  );
}

function probDeltaColor(deltaPp: number): string {
  if (deltaPp >= 3) return "text-neon-green";
  if (deltaPp <= -3) return "text-red-400";
  return "text-slate-300";
}

export function SpreadLinesTable({ data }: { data: BasketSuperbetLiveAdvice }) {
  const lines = Object.keys(data.spreadOdds);
  if (lines.length === 0) {
    return <p className="text-sm text-slate-500">Nenhuma linha de spread disponível na Superbet.</p>;
  }

  const sorted = [...lines].sort((a, b) => {
    const la = decodeSpreadLineKey(a) ?? 0;
    const lb = decodeSpreadLineKey(b) ?? 0;
    return la - lb;
  });

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead>
          <tr className="border-b border-white/[0.04] text-[9px] font-black uppercase tracking-widest text-slate-600">
            <th className="py-2 pl-4">Linha</th>
            <th className="px-2 py-2">Lado</th>
            <th className="px-2 py-2 text-right">Odd</th>
            <th className="px-2 py-2 text-right">Implícita</th>
            <th className="px-2 py-2 text-right">Modelo</th>
            <th className="py-2 pr-4 text-right">Δ vs mercado</th>
          </tr>
        </thead>
        <tbody>
          {sorted.flatMap((lineKey) => {
            const lineVal = decodeSpreadLineKey(lineKey);
            if (lineVal == null) return [];
            const sides = data.spreadOdds[lineKey] ?? {};
            return (["home", "away"] as const).map((side) => {
              const odd = sides[side];
              if (odd == null) return null;
              const probKey = `${side}_${lineKey}`;
              const modelProb = data.inplaySummary.spreadProbs[probKey];
              const implied = data.spreadImplied[lineKey]?.[side];
              const deltaPp =
                modelProb != null && implied != null ? (modelProb - implied) * 100 : null;
              const team = side === "home" ? data.homeTeam : data.awayTeam;
              const displayLine = side === "home" ? lineVal : -lineVal;
              return (
                <tr key={probKey} className="border-t border-white/[0.04] hover:bg-white/[0.02]">
                  <td className="py-2.5 pl-4 font-mono text-xs text-white">
                    {formatSpreadLine(displayLine, team)}
                  </td>
                  <td className="px-2 py-2.5 text-xs capitalize text-slate-400">{side}</td>
                  <td className="px-2 py-2.5 text-right font-mono text-sm text-white">{odd.toFixed(2)}</td>
                  <td className="px-2 py-2.5 text-right font-mono text-xs text-slate-400">
                    {implied != null ? formatPct(implied) : "—"}
                  </td>
                  <td className="px-2 py-2.5 text-right font-mono text-sm font-semibold text-white">
                    {modelProb != null ? formatPct(modelProb) : "—"}
                  </td>
                  <td
                    className={`py-2.5 pr-4 text-right font-mono text-xs font-semibold ${
                      deltaPp != null ? probDeltaColor(deltaPp) : "text-slate-500"
                    }`}
                  >
                    {deltaPp != null ? `${deltaPp > 0 ? "+" : ""}${deltaPp.toFixed(1)} pp` : "—"}
                  </td>
                </tr>
              );
            }).filter(Boolean);
          })}
        </tbody>
      </table>
    </div>
  );
}

export function TotalLinesTable({ data }: { data: BasketSuperbetLiveAdvice }) {
  const lines = Object.keys(data.totalPointsOdds);
  if (lines.length === 0) {
    return <p className="text-sm text-slate-500">Nenhuma linha de total disponível na Superbet.</p>;
  }

  const sorted = [...lines].sort((a, b) => Number.parseFloat(a) - Number.parseFloat(b));

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead>
          <tr className="border-b border-white/[0.04] text-[9px] font-black uppercase tracking-widest text-slate-600">
            <th className="py-2 pl-4">Linha</th>
            <th className="px-2 py-2">Seleção</th>
            <th className="px-2 py-2 text-right">Odd</th>
            <th className="px-2 py-2 text-right">Implícita</th>
            <th className="px-2 py-2 text-right">Modelo</th>
            <th className="py-2 pr-4 text-right">Δ vs mercado</th>
          </tr>
        </thead>
        <tbody>
          {sorted.flatMap((line) => {
            const lineVal = Number.parseFloat(line.replace(",", "."));
            const lineKey = `${lineVal}`.replace(".", "_");
            const sides = data.totalPointsOdds[line] ?? {};
            return (["over", "under"] as const).map((outcome) => {
              const odd = sides[outcome];
              if (odd == null) return null;
              const probKey = `${outcome}_${lineKey}`;
              const modelProb = data.inplaySummary.totalProbs[probKey];
              const implied = data.totalPointsImplied[line]?.[outcome];
              const deltaPp =
                modelProb != null && implied != null ? (modelProb - implied) * 100 : null;
              return (
                <tr key={probKey} className="border-t border-white/[0.04] hover:bg-white/[0.02]">
                  <td className="py-2.5 pl-4 font-mono text-xs text-white">{lineVal}</td>
                  <td className="px-2 py-2.5 text-xs uppercase text-slate-300">
                    {outcome === "over" ? "Over" : "Under"}
                  </td>
                  <td className="px-2 py-2.5 text-right font-mono text-sm text-white">{odd.toFixed(2)}</td>
                  <td className="px-2 py-2.5 text-right font-mono text-xs text-slate-400">
                    {implied != null ? formatPct(implied) : "—"}
                  </td>
                  <td className="px-2 py-2.5 text-right font-mono text-sm font-semibold text-white">
                    {modelProb != null ? formatPct(modelProb) : "—"}
                  </td>
                  <td
                    className={`py-2.5 pr-4 text-right font-mono text-xs font-semibold ${
                      deltaPp != null ? probDeltaColor(deltaPp) : "text-slate-500"
                    }`}
                  >
                    {deltaPp != null ? `${deltaPp > 0 ? "+" : ""}${deltaPp.toFixed(1)} pp` : "—"}
                  </td>
                </tr>
              );
            }).filter(Boolean);
          })}
        </tbody>
      </table>
    </div>
  );
}

export function ModelSimulationMeta({ summary }: { summary: BasketInPlaySummary }) {
  return (
    <div className="flex flex-wrap gap-3 text-[11px] text-slate-500">
      {summary.matchMinutes != null && (
        <span>
          Duração regulamentar: <strong className="text-slate-300">{summary.matchMinutes} min</strong>
        </span>
      )}
      {summary.nSimulations != null && (
        <span>
          Simulações MC: <strong className="text-slate-300">{summary.nSimulations.toLocaleString("pt-BR")}</strong>
        </span>
      )}
      {summary.expectedTotal != null && summary.marketTotalLine != null && (
        <span>
          Viés total:{" "}
          <strong
            className={
              summary.expectedTotal > summary.marketTotalLine ? "text-neon-green" : "text-red-400"
            }
          >
            {summary.expectedTotal > summary.marketTotalLine ? "Over" : "Under"}
          </strong>{" "}
          ({formatPoints(summary.expectedTotal - summary.marketTotalLine, 1)} pts)
        </span>
      )}
    </div>
  );
}
