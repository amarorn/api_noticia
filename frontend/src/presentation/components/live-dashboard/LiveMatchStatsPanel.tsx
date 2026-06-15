import Chart from "react-apexcharts";
import type { ApexOptions } from "apexcharts";
import type { SuperbetLiveAdvice } from "@/domain/entities";

interface LiveMatchStatsPanelProps {
  data: SuperbetLiveAdvice;
}

export function LiveMatchStatsPanel({ data }: LiveMatchStatsPanelProps) {
  const stats = data.liveStats;
  const s = data.inplaySummary;

  const barOptions: ApexOptions = {
    chart: {
      type: "bar",
      background: "transparent",
      toolbar: { show: false },
      fontFamily: "inherit",
    },
    plotOptions: {
      bar: { horizontal: true, barHeight: "55%", borderRadius: 6 },
    },
    dataLabels: {
      enabled: true,
      formatter: (val) => (typeof val === "number" ? val.toFixed(2) : String(val)),
      style: { fontSize: "11px", colors: ["#fff"] },
    },
    xaxis: {
      categories: ["xG", "Chutes no alvo", "Escanteios", "Amarelos"],
      labels: { style: { colors: "#94a3b8" } },
    },
    yaxis: { labels: { show: false } },
    colors: ["#00ff88", "#38bdf8"],
    legend: {
      position: "top",
      labels: { colors: "#94a3b8" },
      fontSize: "11px",
    },
    grid: { borderColor: "#1e293b", strokeDashArray: 4 },
    tooltip: { theme: "dark" },
  };

  const homeXg = stats?.homeXg ?? 0;
  const awayXg = stats?.awayXg ?? 0;
  const homeShots = stats?.homeShotsOnTarget ?? 0;
  const awayShots = stats?.awayShotsOnTarget ?? 0;
  const homeCorners = stats?.homeCorners ?? 0;
  const awayCorners = stats?.awayCorners ?? 0;
  const homeYellow = stats?.homeYellowCards ?? 0;
  const awayYellow = stats?.awayYellowCards ?? 0;

  const hasPhysicalStats =
    stats?.homeXg != null ||
    stats?.homeShotsOnTarget != null ||
    homeCorners > 0 ||
    awayCorners > 0;

  const modelSeries = [
    {
      name: "Modelo",
      data: [
        (s.over25 ?? 0) * 100,
        (s.btts ?? 0) * 100,
        ((s.probNextGoalHome ?? 0) + (s.probNextGoalAway ?? 0)) * 100,
      ],
    },
  ];

  const modelOptions: ApexOptions = {
    chart: { type: "radar", background: "transparent", toolbar: { show: false }, fontFamily: "inherit" },
    xaxis: {
      categories: ["Over 2.5", "BTTS", "Próximo gol"],
      labels: { style: { colors: "#94a3b8", fontSize: "10px" } },
    },
    yaxis: { show: false, max: 100 },
    colors: ["#a855f7"],
    fill: { opacity: 0.25 },
    stroke: { width: 2 },
    markers: { size: 4 },
    tooltip: { theme: "dark", y: { formatter: (v) => `${v.toFixed(0)}%` } },
  };

  return (
    <section className="flex h-full flex-col gap-4 rounded-2xl border border-white/8 bg-white/[0.02] p-4 backdrop-blur-sm">
      <div>
        <h2 className="text-sm font-semibold text-white">Performance & mercados</h2>
        <p className="text-[11px] text-slate-500">xG/chutes ao vivo + leitura do modelo</p>
      </div>

      {hasPhysicalStats ? (
        <Chart
          options={barOptions}
          series={[
            { name: data.homeTeam, data: [homeXg, homeShots, homeCorners, homeYellow] },
            { name: data.awayTeam, data: [awayXg, awayShots, awayCorners, awayYellow] },
          ]}
          type="bar"
          height={200}
        />
      ) : (
        <div className="rounded-xl border border-dashed border-white/10 bg-black/20 px-4 py-6 text-center text-xs text-slate-500">
          Stats físicas (xG, chutes) no refresh completo · escanteios/cartões via Superbet
        </div>
      )}

      <div className="border-t border-white/8 pt-3">
        <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-slate-500">
          Radar de mercados (modelo)
        </p>
        <Chart options={modelOptions} series={modelSeries} type="radar" height={220} />
      </div>
    </section>
  );
}
