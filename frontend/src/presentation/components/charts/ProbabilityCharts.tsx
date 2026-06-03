import Chart from "react-apexcharts";
import type { ApexOptions } from "apexcharts";
import type { OutcomeLabel } from "@/domain/entities";
import { formatPercent, outcomeColors, outcomeLabels } from "@/presentation/theme";

interface ProbabilityDonutProps {
  probHome: number;
  probDraw: number;
  probAway: number;
  prediction: OutcomeLabel;
  height?: number;
}

export function ProbabilityDonut({
  probHome,
  probDraw,
  probAway,
  prediction,
  height = 220,
}: ProbabilityDonutProps) {
  const series = [probHome, probDraw, probAway];
  const colors = [outcomeColors["1"], outcomeColors.X, outcomeColors["2"]];

  const options: ApexOptions = {
    chart: { type: "donut", background: "transparent", fontFamily: "inherit" },
    labels: ["1 (Casa)", "X (Empate)", "2 (Fora)"],
    colors,
    legend: {
      position: "bottom",
      labels: { colors: "#94a3b8" },
    },
    dataLabels: {
      enabled: true,
      formatter: (val: number) => `${val.toFixed(1)}%`,
      style: { fontSize: "11px", fontWeight: 600 },
      dropShadow: { enabled: false },
    },
    plotOptions: {
      pie: {
        donut: {
          size: "65%",
          labels: {
            show: true,
            name: { color: "#94a3b8", fontSize: "12px" },
            value: {
              color: outcomeColors[prediction],
              fontSize: "22px",
              fontWeight: 700,
              formatter: (val) => `${val}%`,
            },
            total: {
              show: true,
              label: "Palpite",
              color: "#64748b",
              formatter: () => prediction,
            },
          },
        },
      },
    },
    stroke: { width: 2, colors: ["#0a0f1a"] },
    tooltip: {
      theme: "dark",
      y: { formatter: (val) => formatPercent(val / 100, 1) },
    },
  };

  return (
    <Chart
      options={options}
      series={series.map((v) => v * 100)}
      type="donut"
      height={height}
    />
  );
}

interface ModelBreakdownChartProps {
  dixonColes: Record<OutcomeLabel, number>;
  logistic: Record<OutcomeLabel, number>;
  height?: number;
}

export function ModelBreakdownChart({
  dixonColes,
  logistic,
  height = 200,
}: ModelBreakdownChartProps) {
  const options: ApexOptions = {
    chart: {
      type: "bar",
      background: "transparent",
      toolbar: { show: false },
      fontFamily: "inherit",
    },
    plotOptions: {
      bar: { horizontal: false, columnWidth: "55%", borderRadius: 6 },
    },
    dataLabels: { enabled: false },
    xaxis: {
      categories: ["1", "X", "2"],
      labels: { style: { colors: "#94a3b8" } },
    },
    yaxis: {
      max: 1,
      labels: {
        formatter: (v) => formatPercent(v),
        style: { colors: "#64748b" },
      },
    },
    colors: ["#00ff88", "#00d4ff"],
    legend: {
      labels: { colors: "#94a3b8" },
      position: "top",
    },
    grid: { borderColor: "#1e293b", strokeDashArray: 4 },
    tooltip: {
      theme: "dark",
      y: { formatter: (v) => formatPercent(v) },
    },
  };

  const series = [
    { name: "Dixon-Coles", data: [dixonColes["1"], dixonColes.X, dixonColes["2"]] },
    { name: "Logística", data: [logistic["1"], logistic.X, logistic["2"]] },
  ];

  return (
    <div>
      <p className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-500">
        Breakdown Dixon-Coles vs Logística
      </p>
      <Chart options={options} series={series} type="bar" height={height} />
    </div>
  );
}

interface ProbabilityBarProps {
  probHome: number;
  probDraw: number;
  probAway: number;
}

export function ProbabilityBar({ probHome, probDraw, probAway }: ProbabilityBarProps) {
  const items = [
    { label: "1", value: probHome, color: outcomeColors["1"] },
    { label: "X", value: probDraw, color: outcomeColors.X },
    { label: "2", value: probAway, color: outcomeColors["2"] },
  ];

  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-3">
          <span
            className="w-6 text-center text-sm font-bold"
            style={{ color: item.color }}
          >
            {item.label}
          </span>
          <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-white/5">
            <div
              className="absolute inset-y-0 left-0 rounded-full transition-all duration-700"
              style={{
                width: `${item.value * 100}%`,
                backgroundColor: item.color,
                opacity: 0.85,
              }}
            />
          </div>
          <span className="w-12 text-right text-xs text-slate-400">
            {formatPercent(item.value)}
          </span>
        </div>
      ))}
    </div>
  );
}

export { outcomeLabels };
