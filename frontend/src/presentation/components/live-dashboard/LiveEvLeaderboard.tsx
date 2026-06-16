import Chart from "react-apexcharts";
import type { ApexOptions } from "apexcharts";
import type { SuperbetLiveAdvice } from "@/domain/entities";

interface LiveEvLeaderboardProps {
  data: SuperbetLiveAdvice;
}

export function LiveEvLeaderboard({ data }: LiveEvLeaderboardProps) {
  const rows = [...(data.strategy?.marketScan ?? [])]
    .sort((a, b) => b.expectedValue - a.expectedValue)
    .slice(0, 8);

  if (rows.length === 0) {
    return (
      <section className="rounded-2xl border border-white/8 bg-white/[0.02] p-4">
        <h2 className="text-sm font-semibold text-white">Ranking de EV</h2>
        <p className="mt-4 text-sm text-slate-500">Nenhum mercado com EV positivo mapeado.</p>
      </section>
    );
  }

  const categories = rows.map((r) => r.label.slice(0, 28));
  const values = rows.map((r) => r.expectedValue * 100);
  const colors = values.map((v) => (v >= 5 ? "#00ff88" : v >= 0 ? "#38bdf8" : "#ef4444"));

  const options: ApexOptions = {
    chart: {
      type: "bar",
      background: "transparent",
      toolbar: { show: false },
      fontFamily: "inherit",
    },
    plotOptions: {
      bar: {
        horizontal: true,
        borderRadius: 4,
        distributed: true,
        dataLabels: { position: "center" },
      },
    },
    colors,
    dataLabels: {
      enabled: true,
      formatter: (val) => `${Number(val) >= 0 ? "+" : ""}${Number(val).toFixed(1)}%`,
      style: { fontSize: "10px", colors: ["#0a0f1a"] },
    },
    xaxis: {
      categories,
      labels: { style: { colors: "#94a3b8", fontSize: "10px" } },
    },
    yaxis: {
      labels: {
        maxWidth: 140,
        style: { colors: "#cbd5e1", fontSize: "11px" },
      },
    },
    grid: { borderColor: "#1e293b", strokeDashArray: 4 },
    legend: { show: false },
    tooltip: {
      theme: "dark",
      y: {
        formatter: (_, opts) => {
          const row = rows[opts.dataPointIndex];
          return `EV ${(row.expectedValue * 100).toFixed(1)}% · odd ${row.marketOdd.toFixed(2)}`;
        },
      },
    },
  };

  return (
    <section className="rounded-2xl border border-white/8 bg-white/[0.02] p-4 backdrop-blur-sm">
      <h2 className="text-sm font-semibold text-white">Ranking de EV</h2>
      <p className="mb-3 text-[11px] text-slate-500">Mercados ordenados por valor esperado</p>
      <Chart options={options} series={[{ name: "EV", data: values }]} type="bar" height={Math.max(220, rows.length * 36)} />
    </section>
  );
}
