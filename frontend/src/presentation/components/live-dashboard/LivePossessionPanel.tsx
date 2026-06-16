import Chart from "react-apexcharts";
import type { ApexOptions } from "apexcharts";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import type { PossessionSample } from "@/presentation/hooks/useLivePossessionHistory";
import { LiveMatchTracker } from "@/presentation/components/live-dashboard/SportradarLmtWidget";

interface LivePossessionPanelProps {
  data: SuperbetLiveAdvice;
  history: PossessionSample[];
}

export function LivePossessionPanel({ data, history }: LivePossessionPanelProps) {
  const homePct = data.liveStats?.homePossessionPct ?? 50;
  const awayPct =
    data.liveStats?.awayPossessionPct ??
    Math.max(0, 100 - homePct);
  const possessionSource = data.liveStats?.possessionSource;
  const isProxy = possessionSource === "corners_proxy" || possessionSource === "momentum_proxy";
  const isNeutral = possessionSource === "neutral" || possessionSource == null;

  const donutOptions: ApexOptions = {
    chart: { type: "donut", background: "transparent", fontFamily: "inherit" },
    labels: [data.homeTeam, data.awayTeam],
    colors: ["#00ff88", "#38bdf8"],
    legend: { show: false },
    dataLabels: { enabled: false },
    plotOptions: {
      pie: {
        donut: {
          size: "72%",
          labels: {
            show: true,
            name: { color: "#94a3b8", fontSize: "11px" },
            value: {
              color: "#fff",
              fontSize: "20px",
              fontWeight: 700,
              formatter: (val) => `${Number(val).toFixed(0)}%`,
            },
            total: {
              show: true,
              label: "Posse",
              color: "#64748b",
              formatter: () =>
                homePct != null ? `${homePct.toFixed(0)} / ${awayPct?.toFixed(0) ?? "—"}` : "—",
            },
          },
        },
      },
    },
    stroke: { width: 3, colors: ["#0a0f1a"] },
    tooltip: { theme: "dark" },
  };

  const lineOptions: ApexOptions = {
    chart: {
      type: "area",
      background: "transparent",
      toolbar: { show: false },
      fontFamily: "inherit",
      sparkline: { enabled: false },
      animations: { enabled: true, speed: 600 },
    },
    colors: ["#00ff88", "#38bdf8"],
    stroke: { curve: "smooth", width: 2 },
    fill: {
      type: "gradient",
      gradient: { opacityFrom: 0.35, opacityTo: 0.05 },
    },
    dataLabels: { enabled: false },
    xaxis: {
      categories: history.map((h) => `${h.minute}'`),
      labels: { style: { colors: "#64748b", fontSize: "10px" } },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      min: 0,
      max: 100,
      labels: {
        formatter: (v) => `${v.toFixed(0)}%`,
        style: { colors: "#64748b", fontSize: "10px" },
      },
    },
    grid: { borderColor: "#1e293b", strokeDashArray: 4 },
    legend: {
      labels: { colors: "#94a3b8" },
      position: "top",
      fontSize: "11px",
    },
    tooltip: { theme: "dark", x: { show: true } },
  };

  const lineSeries = [
    { name: data.homeTeam, data: history.map((h) => h.home) },
    { name: data.awayTeam, data: history.map((h) => h.away) },
  ];

  const hasDonutData = data.liveStats?.homePossessionPct != null;

  return (
    <section className="flex h-full flex-col rounded-2xl border border-white/8 bg-white/[0.02] p-4 backdrop-blur-sm">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-white">Campo ao vivo</h2>
          <p className="text-[11px] text-slate-500">
            Tracker estilo broadcast · posição estimada por posse e momentum
          </p>
        </div>
        {!isNeutral && (
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
              isProxy
                ? "bg-amber-500/15 text-amber-300"
                : "bg-neon-green/10 text-neon-green"
            }`}
          >
            {isProxy ? "ESTIMATIVA" : "LIVE"}
          </span>
        )}
      </div>

      <LiveMatchTracker data={data} className="mb-4" />

      {!hasDonutData ? (
        <div className="rounded-xl border border-dashed border-white/10 bg-black/20 px-4 py-4 text-center text-xs text-slate-500">
          Gráficos circulares após primeiro tick com posse confirmada
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Chart
              options={donutOptions}
              series={[homePct, awayPct ?? 0]}
              type="donut"
              height={220}
            />
            <div className="flex flex-col justify-center gap-3">
              {[ 
                { team: data.homeTeam, pct: homePct, color: "#00ff88" },
                { team: data.awayTeam, pct: awayPct ?? 0, color: "#38bdf8" },
              ].map(({ team, pct, color }) => (
                <div key={team}>
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="truncate text-slate-300">{team}</span>
                    <span className="font-mono font-semibold text-white">{pct.toFixed(0)}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-white/5">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{ width: `${pct}%`, backgroundColor: color }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {history.length >= 2 && (
            <div className="mt-4 border-t border-white/8 pt-4">
              <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-slate-500">
                Evolução em tempo real
              </p>
              <Chart options={lineOptions} series={lineSeries} type="area" height={180} />
            </div>
          )}

          {data.liveStats?.warnings?.[0] && (
            <p className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/8 px-3 py-2 text-[11px] text-amber-200/90">
              {data.liveStats.warnings[0]}
            </p>
          )}
        </>
      )}
    </section>
  );
}
