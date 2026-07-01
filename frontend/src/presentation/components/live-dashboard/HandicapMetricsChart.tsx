import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import {
  type HandicapChartPoint,
  handicapChartLegendSuffix,
} from "@/presentation/utils/predictionChartData";
import {
  coverStatusColor,
  coverStatusLabel,
  coverTrajectoryValue,
  type SuggestedHandicapPick,
} from "@/presentation/utils/handicapCover";
import { formatHandicapLineKey } from "@/presentation/utils/handicapLine";
import type { GoalEvent } from "@/presentation/hooks/useLivePredictionHistory";
import { defaultDataZoom, goalMarkLineData } from "@/presentation/utils/liveChartUtils";

const COLORS = {
  up: "#00ff88",
  down: "#f87171",
  away: "#38bdf8",
  modelHome: "#fbbf24",
  modelAway: "#a78bfa",
  awayWin: "#f472b6",
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
  suggestedPick?: SuggestedHandicapPick | null,
  showSuggestedTrack?: boolean,
): EChartsOption {
  const last = points[points.length - 1];
  const legend = handicapChartLegendSuffix(homeTeam, awayTeam, last);
  const labels = points.map((p) => p.label);
  const candleData = points.map((p) => p.homeOhlc ?? [null, null, null, null]);
  const awayOdds = points.map((p) => p.awayOdd);
  const homeModel = points.map((p) => p.homeModelPct);
  const awayModel = points.map((p) => p.awayModelPct);
  const awayWinModel = points.map((p) => p.awayWinModelPct);
  const homeImplied = points.map((p) => p.homeImpliedPct);
  const awayImplied = points.map((p) => p.awayImpliedPct);
  const markLine =
    goalEvents.length > 0
      ? { symbol: ["none", "none"] as [string, string], data: goalMarkLineData(goalEvents) }
      : undefined;

  const series: EChartsOption["series"] = [
    {
      name: `Odd ${legend.homeLine}`,
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
      name: `Odd ${legend.awayLine}`,
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
      name: `P(modelo) ${legend.homeLine}`,
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
            { offset: 0, color: "rgba(251, 191, 36, 0.25)" },
            { offset: 1, color: "rgba(251, 191, 36, 0.02)" },
          ],
        },
      },
    },
    {
      name: `P(modelo) ${legend.awayLine}`,
      type: "line",
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: awayModel,
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 2, color: COLORS.modelAway },
    },
    {
      name: `Implícita ${legend.homeLine}`,
      type: "line",
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: homeImplied,
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 1.5, color: COLORS.implied, type: "dotted" },
    },
    {
      name: `Implícita ${legend.awayLine}`,
      type: "line",
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: awayImplied,
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 1, color: "#475569", type: "dotted" },
    },
  ];

  if (legend.awayWinLine) {
    series.push({
      name: `P(modelo) ${legend.awayWinLine}`,
      type: "line",
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: awayWinModel,
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 1.5, color: COLORS.awayWin, type: [4, 4] },
    });
  }

  if (showSuggestedTrack && suggestedPick) {
    series.push({
      name: `Palpite · P(modelo)`,
      type: "line",
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: points.map((p) => p.suggestedModelPct),
      smooth: true,
      showSymbol: true,
      symbolSize: 6,
      lineStyle: { width: 2.5, color: "#00ff88", type: "solid" },
      itemStyle: { color: "#00ff88", borderColor: "#064e3b", borderWidth: 1 },
      z: 10,
    });
    series.push({
      name: "Caminho do palpite",
      type: "bar",
      xAxisIndex: 2,
      yAxisIndex: 2,
      data: points.map((p) =>
        p.suggestedCoverStatus != null ? coverTrajectoryValue(p.suggestedCoverStatus) : null,
      ),
      barWidth: "70%",
      itemStyle: {
        color: (params) => {
          const idx = params.dataIndex ?? 0;
          const st = points[idx]?.suggestedCoverStatus;
          return st ? coverStatusColor(st) : "#334155";
        },
        opacity: 0.85,
      },
    });
  }

  const gridRows = showSuggestedTrack
    ? [
        { left: 52, right: 52, top: 72, height: "32%" },
        { left: 52, right: 52, top: "48%", height: "26%" },
        { left: 52, right: 52, top: "78%", height: "12%" },
      ]
    : [
        { left: 52, right: 52, top: 72, height: "38%" },
        { left: 52, right: 52, top: "58%", height: "28%" },
      ];

  const xAxes: EChartsOption["xAxis"] = gridRows.map((_, i) => ({
    type: "category",
    data: labels,
    gridIndex: i,
    axisLine: { lineStyle: { color: COLORS.grid } },
    axisLabel: { color: COLORS.text, fontSize: 10, show: i === gridRows.length - 1 },
    axisTick: { show: false },
  }));

  const yAxes: EChartsOption["yAxis"] = [
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
  ];

  if (showSuggestedTrack) {
    yAxes.push({
      gridIndex: 2,
      name: "Palpite",
      nameTextStyle: { color: COLORS.text, fontSize: 9 },
      min: 0,
      max: 100,
      show: false,
      axisLine: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
    });
  }

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
      link: [{ xAxisIndex: showSuggestedTrack ? [0, 1, 2] : [0, 1] }],
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
        const lg = handicapChartLegendSuffix(homeTeam, awayTeam, p);
        const lines = [`<strong>${p.label}</strong>`];
        if (p.currentScore) lines.push(`Placar: <b>${p.currentScore.replace("x", "×")}</b>`);
        if (p.homeOdd != null) {
          lines.push(`Odd ${lg.homeLine}: <b>${p.homeOdd.toFixed(2)}</b>`);
        }
        if (p.awayOdd != null) {
          lines.push(`Odd ${lg.awayLine}: <b>${p.awayOdd.toFixed(2)}</b>`);
        }
        if (p.homeModelPct != null) {
          lines.push(`P(modelo) ${lg.homeLine}: <b>${p.homeModelPct.toFixed(1)}%</b>`);
        }
        if (p.awayModelPct != null) {
          lines.push(`P(modelo) ${lg.awayLine}: <b>${p.awayModelPct.toFixed(1)}%</b>`);
        }
        if (p.awayWinModelPct != null && lg.awayWinLine) {
          lines.push(
            `P(modelo) ${lg.awayWinLine}: <b>${p.awayWinModelPct.toFixed(1)}%</b> (não é o botão +0.5)`,
          );
        }
        if (p.suggestedCoverStatus && p.suggestedCoverHint) {
          lines.push(
            `Palpite: <b>${coverStatusLabel(p.suggestedCoverStatus)}</b> — ${p.suggestedCoverHint}`,
          );
        }
        if (p.suggestedModelPct != null) {
          lines.push(`P(modelo) palpite: <b>${p.suggestedModelPct.toFixed(1)}%</b>`);
        }
        return lines.join("<br/>");
      },
    },
    grid: gridRows,
    xAxis: xAxes,
    yAxis: yAxes,
    dataZoom: defaultDataZoom(points.length),
    series,
  };
}

interface HandicapMetricsChartProps {
  points: HandicapChartPoint[];
  homeTeam: string;
  awayTeam: string;
  title: string;
  helpText?: string;
  goalEvents?: GoalEvent[];
  height?: number;
  suggestedPick?: SuggestedHandicapPick | null;
  showSuggestedTrack?: boolean;
}

/** Gráfico dual: odds + P(modelo) por lado, com trilha do palpite indicado. */
export function HandicapMetricsChart({
  points,
  homeTeam,
  awayTeam,
  title,
  helpText,
  goalEvents = [],
  height = 360,
  suggestedPick = null,
  showSuggestedTrack = false,
}: HandicapMetricsChartProps) {
  const option = useMemo(
    () =>
      buildOptions(
        points,
        homeTeam,
        awayTeam,
        title,
        goalEvents,
        suggestedPick,
        showSuggestedTrack,
      ),
    [points, homeTeam, awayTeam, title, goalEvents, suggestedPick, showSuggestedTrack],
  );

  const last = points[points.length - 1];
  const lineBadge =
    last != null
      ? `${formatHandicapLineKey(last.homeLineKey)} / ${formatHandicapLineKey(last.awayLineKey)}`
      : null;

  if (points.length < 2) {
    return (
      <p className="py-10 text-center text-xs text-slate-500">
        Aguardando mais ticks ao vivo para candlestick e métricas…
      </p>
    );
  }

  const lastStatus = last?.suggestedCoverStatus;
  const lastHint = last?.suggestedCoverHint;

  return (
    <div className="space-y-2">
      {showSuggestedTrack && suggestedPick && lastStatus && (
        <div
          className="rounded-lg border px-3 py-2 text-[11px]"
          style={{
            borderColor: `${coverStatusColor(lastStatus)}40`,
            backgroundColor: `${coverStatusColor(lastStatus)}10`,
          }}
        >
          <p className="font-semibold text-white">
            Palpite indicado: {suggestedPick.label}
            <span className="ml-2 font-normal" style={{ color: coverStatusColor(lastStatus) }}>
              · {coverStatusLabel(lastStatus)}
            </span>
          </p>
          {lastHint && <p className="mt-1 text-slate-400">{lastHint}</p>}
          {last.suggestedModelPct != null && (
            <p className="mt-1 text-[10px] text-neon-green">
              P(modelo) agora: {last.suggestedModelPct.toFixed(1)}%
              {last.suggestedModelPct >= 50 ? " — favorável" : " — ainda longe"}
            </p>
          )}
        </div>
      )}
      {helpText && (
        <p className="rounded-lg border border-sky-500/20 bg-sky-500/5 px-3 py-2 text-[11px] leading-relaxed text-sky-100/90">
          {helpText}
        </p>
      )}
      {lineBadge && (
        <p className="text-[10px] text-slate-500">
          Linhas no gráfico: mandante {formatHandicapLineKey(last.homeLineKey)} · visitante{" "}
          {formatHandicapLineKey(last.awayLineKey)}
          {last.currentScore ? ` · placar ${last.currentScore.replace("x", "×")}` : ""}
        </p>
      )}
      <ReactECharts
        option={option}
        style={{ height: showSuggestedTrack ? height + 48 : height, width: "100%" }}
        opts={{ renderer: "canvas" }}
        notMerge
        lazyUpdate
      />
    </div>
  );
}
