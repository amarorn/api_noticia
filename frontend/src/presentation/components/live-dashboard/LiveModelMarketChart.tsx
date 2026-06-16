import Chart from "react-apexcharts";
import type { ApexOptions } from "apexcharts";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import { formatPercent, outcomeColors } from "@/presentation/theme";

interface LiveModelMarketChartProps {
  data: SuperbetLiveAdvice;
}

export function LiveModelMarketChart({ data }: LiveModelMarketChartProps) {
  const model = [
    data.inplaySummary.probFinalHome,
    data.inplaySummary.probFinalDraw,
    data.inplaySummary.probFinalAway,
  ];
  const market = [
    data.h2hImplied["1"] ?? 0,
    data.h2hImplied["X"] ?? 0,
    data.h2hImplied["2"] ?? 0,
  ];

  const options: ApexOptions = {
    chart: {
      type: "bar",
      background: "transparent",
      toolbar: { show: false },
      fontFamily: "inherit",
    },
    plotOptions: {
      bar: { columnWidth: "50%", borderRadius: 6 },
    },
    dataLabels: {
      enabled: true,
      formatter: (val) => `${Number(val).toFixed(0)}%`,
      style: { fontSize: "10px", colors: ["#fff"] },
    },
    xaxis: {
      categories: ["1 Casa", "X Empate", "2 Fora"],
      labels: { style: { colors: "#94a3b8" } },
    },
    yaxis: {
      max: 100,
      labels: { formatter: (v) => `${v}%`, style: { colors: "#64748b" } },
    },
    colors: ["#00ff88", "#64748b"],
    legend: { labels: { colors: "#94a3b8" }, position: "top" },
    grid: { borderColor: "#1e293b", strokeDashArray: 4 },
    tooltip: { theme: "dark" },
  };

  const series = [
    { name: "Modelo in-play", data: model.map((v) => v * 100) },
    { name: "Mercado (implícita)", data: market.map((v) => v * 100) },
  ];

  const edges = (["1", "X", "2"] as const).map((k) => ({
    key: k,
    edge: data.marketBenchmark?.h2h?.[k]?.edge ?? 0,
    color: outcomeColors[k],
  }));
  const bestEdge = edges.reduce((a, b) => (Math.abs(b.edge) > Math.abs(a.edge) ? b : a));

  return (
    <section className="rounded-2xl border border-white/8 bg-white/[0.02] p-4 backdrop-blur-sm">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-white">Modelo vs casa (1X2)</h2>
          <p className="text-[11px] text-slate-500">Onde há divergência de probabilidade</p>
        </div>
        {bestEdge.edge !== 0 && (
          <span
            className="rounded-lg px-2 py-1 text-[10px] font-semibold"
            style={{
              color: bestEdge.color,
              backgroundColor: `${bestEdge.color}18`,
              border: `1px solid ${bestEdge.color}40`,
            }}
          >
            Edge {bestEdge.key}: {(bestEdge.edge * 100).toFixed(1)} pp
          </span>
        )}
      </div>
      <Chart options={options} series={series} type="bar" height={260} />
      <div className="mt-3 grid grid-cols-3 gap-2 text-center text-[10px]">
        {edges.map(({ key, edge, color }) => {
          const idx = ["1", "X", "2"].indexOf(key);
          return (
            <div key={key} className="rounded-lg border border-white/8 bg-black/20 py-2">
              <span className="font-bold" style={{ color }}>
                {key}
              </span>
              <p className="mt-0.5 font-mono text-white">{(edge * 100).toFixed(1)} pp</p>
              <p className="text-slate-500">{formatPercent(model[idx])} mod</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
