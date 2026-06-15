import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import type { HandicapChartPoint } from "@/presentation/utils/predictionChartData";
import type { GoalEvent } from "@/presentation/hooks/useLivePredictionHistory";
import { defaultDataZoom, goalMarkLineData } from "@/presentation/utils/liveChartUtils";

const COLORS = {
  up: "#00ff88",
  down: "#f87171",
  away: "#38bdf8",
  modelHome: "#fbbf24",
  modelAway: "#a78bfa",
  implied: "#64748b",
  edgePos: "rgba(0, 255, 136, 0.25)",
  edgeNeg: "rgba(248, 113, 113, 0.25)",
  grid: "#1e293b",
  text: "#94a3b8",
};

function buildOptions(
  points: HandicapChartPoint[],
  homeTeam: string,
  awayTeam: string,
  title: string,
  goalEvents: GoalEvent[],
): EChartsOption {
  const labels = points.map((p) => p.label);
  const candleData = points.map((p) => p.homeOhlc ?? [null, null, null, null]);
  const awayOdds = points.map((p) => p.awayOdd);
  const homeModel = points.map((p) => p.homeModelPct);
  const homeImplied = points.map((p) => p.homeImpliedPct);
  const homeEdge = points.map((p) => p.homeEdgePp);
  const markLine =
    goalEvents.length > 0
      ? { symbol: ["none", "none"] as [string, string], data: goalMarkLineData(goalEvents) }
      : undefined;

  return {
    backgroundColor: "transparent",
    animationDuration: 600,
    title: {
      text: title,
      left: 0,
      top: 0,
      textStyle: { color: "#e2e8f0", fontSize: 12, fontWeight: 600 },
    },
    legend: {
      top: 22,
      textStyle: { color: COLORS.text, fontSize: 10 },
      itemWidth: 14,
      itemHeight: 8,
    },
    axisPointer: {
      link: [{ xAxisIndex: [0, 1] }],
      label: { backgroundColor: "#334155" },
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      backgroundColor: "rgba(15, 23, 42, 0.95)",
      borderColor: "#334155",
      textStyle: { color: "#e2e8f0", fontSize: 11 },
      formatter(params) {
        if (!Array.isArray(params) || params.length === 0) return "";
        const idx = params[0]?.dataIndex ?? 0;
        const p = points[idx];
        if (!p) return "";
        const lines = [`<strong>${p.label}</strong>`];
        if (p.homeOdd != null) lines.push(`Odd ${homeTeam}: <b>${p.homeOdd.toFixed(2)}</b>`);
        if (p.awayOdd != null) lines.push(`Odd ${awayTeam}: <b>${p.awayOdd.toFixed(2)}</b>`);
        if (p.homeModelPct != null) lines.push(`P(modelo) ${homeTeam}: <b>${p.homeModelPct.toFixed(1)}%</b>`);
        if (p.homeImpliedPct != null) lines.push(`Implícita casa: <b>${p.homeImpliedPct.toFixed(1)}%</b>`);
        if (p.homeEdgePp != null) {
          const sign = p.homeEdgePp >= 0 ? "+" : "";
          lines.push(`Edge casa: <b>${sign}${p.homeEdgePp.toFixed(1)} pp</b>`);
        }
        return lines.join("<br/>");
      },
    },
    grid: [
      { left: 52, right: 52, top: 72, height: "38%" },
      { left: 52, right: 52, top: "58%", height: "28%" },
    ],
    xAxis: [
      {
        type: "category",
        data: labels,
        gridIndex: 0,
        axisLine: { lineStyle: { color: COLORS.grid } },
        axisLabel: { color: COLORS.text, fontSize: 10 },
        axisTick: { show: false },
      },
      {
        type: "category",
        data: labels,
        gridIndex: 1,
        axisLine: { lineStyle: { color: COLORS.grid } },
        axisLabel: { color: COLORS.text, fontSize: 10 },
        axisTick: { show: false },
      },
    ],
    yAxis: [
      {
        scale: true,
        gridIndex: 0,
        name: "Odd",
        nameTextStyle: { color: COLORS.text, fontSize: 10 },
        axisLine: { show: false },
        splitLine: { lineStyle: { color: COLORS.grid, type: "dashed" } },
        axisLabel: { color: COLORS.text, fontSize: 10 },
      },
      {
        gridIndex: 1,
        name: "Prob %",
        nameTextStyle: { color: COLORS.text, fontSize: 10 },
        min: 0,
        max: 100,
        axisLine: { show: false },
        splitLine: { lineStyle: { color: COLORS.grid, type: "dashed" } },
        axisLabel: { color: COLORS.text, fontSize: 10, formatter: "{value}%" },
      },
    ],
    dataZoom: defaultDataZoom(points.length),
    series: [
      {
        name: `Odd ${homeTeam}`,
        type: "candlestick",
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: candleData,
        markLine,
        itemStyle: {
          color: COLORS.up,
          color0: COLORS.down,
          borderColor: COLORS.up,
          borderColor0: COLORS.down,
        },
      },
      {
        name: `Odd ${awayTeam}`,
        type: "line",
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: awayOdds,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: COLORS.away, type: "dashed" },
        itemStyle: { color: COLORS.away },
      },
      {
        name: `P(modelo) ${homeTeam}`,
        type: "line",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: homeModel,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: COLORS.modelHome },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(251, 191, 36, 0.35)" },
              { offset: 1, color: "rgba(251, 191, 36, 0.02)" },
            ],
          },
        },
      },
      {
        name: `Implícita ${homeTeam}`,
        type: "line",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: homeImplied,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1.5, color: COLORS.implied, type: "dotted" },
      },
      {
        name: "Edge casa (pp)",
        type: "bar",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: homeEdge,
        barWidth: "55%",
        itemStyle: {
          color: (params) => {
            const v = Number(params.value);
            return v >= 0 ? COLORS.edgePos : COLORS.edgeNeg;
          },
        },
      },
    ],
  };
}

interface HandicapMetricsChartProps {
  points: HandicapChartPoint[];
  homeTeam: string;
  awayTeam: string;
  title: string;
  goalEvents?: GoalEvent[];
  height?: number;
}

/** Gráfico dual: candlestick de odds + painel de probabilidade/edge (ECharts). */
export function HandicapMetricsChart({
  points,
  homeTeam,
  awayTeam,
  title,
  goalEvents = [],
  height = 360,
}: HandicapMetricsChartProps) {
  const option = useMemo(
    () => buildOptions(points, homeTeam, awayTeam, title, goalEvents),
    [points, homeTeam, awayTeam, title, goalEvents],
  );

  if (points.length < 2) {
    return (
      <p className="py-10 text-center text-xs text-slate-500">
        Aguardando mais ticks ao vivo para candlestick e métricas…
      </p>
    );
  }

  return (
    <ReactECharts
      option={option}
      style={{ height, width: "100%" }}
      opts={{ renderer: "canvas" }}
      notMerge
      lazyUpdate
    />
  );
}
