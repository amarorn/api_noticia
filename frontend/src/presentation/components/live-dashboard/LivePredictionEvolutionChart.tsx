import { useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import type { GoalEvent } from "@/presentation/hooks/useLivePredictionHistory";
import { useLivePredictionHistory } from "@/presentation/hooks/useLivePredictionHistory";
import { HandicapMetricsChart } from "@/presentation/components/live-dashboard/HandicapMetricsChart";
import {
  buildHandicapChartPoints,
  buildH2hChartPoints,
  buildTotalsChartPoints,
} from "@/presentation/utils/predictionChartData";
import {
  formatHandicapLineKey,
  pickPrimaryHandicapLine,
} from "@/presentation/utils/handicapLine";
import { defaultDataZoom, goalMarkLineData } from "@/presentation/utils/liveChartUtils";
import { outcomeColors } from "@/presentation/theme";

type TabId = "h2h" | "totals" | "handicap" | "asian";

const TABS: { id: TabId; label: string }[] = [
  { id: "h2h", label: "1X2" },
  { id: "totals", label: "Over 2.5" },
  { id: "handicap", label: "Handicap EU" },
  { id: "asian", label: "Handicap Asiático" },
];

const COLORS = { grid: "#1e293b", text: "#94a3b8", up: "#00ff88", down: "#f87171" };

function buildH2hOptions(
  points: ReturnType<typeof buildH2hChartPoints>,
  goalEvents: GoalEvent[],
): EChartsOption {
  const labels = points.map((p) => p.label);
  const markLine =
    goalEvents.length > 0
      ? { symbol: ["none", "none"] as [string, string], data: goalMarkLineData(goalEvents) }
      : undefined;

  return {
    backgroundColor: "transparent",
    animationDuration: 600,
    legend: { top: 8, textStyle: { color: COLORS.text, fontSize: 10 } },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      backgroundColor: "rgba(15, 23, 42, 0.95)",
      borderColor: "#334155",
      textStyle: { color: "#e2e8f0", fontSize: 11 },
    },
    axisPointer: { link: [{ xAxisIndex: [0, 1] }] },
    grid: [
      { left: 48, right: 48, top: 48, height: "36%" },
      { left: 48, right: 48, top: "54%", height: "32%" },
    ],
    xAxis: [
      {
        type: "category",
        data: labels,
        gridIndex: 0,
        axisLabel: { color: COLORS.text, fontSize: 10 },
        axisTick: { show: false },
      },
      {
        type: "category",
        data: labels,
        gridIndex: 1,
        axisLabel: { color: COLORS.text, fontSize: 10 },
        axisTick: { show: false },
      },
    ],
    yAxis: [
      {
        scale: true,
        gridIndex: 0,
        name: "Odd 1",
        nameTextStyle: { color: COLORS.text, fontSize: 10 },
        splitLine: { lineStyle: { color: COLORS.grid, type: "dashed" } },
        axisLabel: { color: COLORS.text, fontSize: 10 },
      },
      {
        gridIndex: 1,
        min: 0,
        max: 100,
        name: "Prob %",
        nameTextStyle: { color: COLORS.text, fontSize: 10 },
        splitLine: { lineStyle: { color: COLORS.grid, type: "dashed" } },
        axisLabel: { color: COLORS.text, fontSize: 10, formatter: "{value}%" },
      },
    ],
    dataZoom: defaultDataZoom(points.length),
    series: [
      {
        name: "Odd 1 (candle)",
        type: "candlestick",
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: points.map((p) => p.odd1Ohlc ?? [null, null, null, null]),
        markLine,
        itemStyle: {
          color: COLORS.up,
          color0: COLORS.down,
          borderColor: COLORS.up,
          borderColor0: COLORS.down,
        },
      },
      {
        name: "Odd X",
        type: "line",
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: points.map((p) => p.oddX),
        smooth: true,
        showSymbol: false,
        lineStyle: { color: outcomeColors.X, width: 1.5, type: "dashed" },
      },
      {
        name: "Odd 2",
        type: "line",
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: points.map((p) => p.odd2),
        smooth: true,
        showSymbol: false,
        lineStyle: { color: outcomeColors["2"], width: 1.5, type: "dashed" },
      },
      {
        name: "P(modelo) 1",
        type: "line",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: points.map((p) => p.model1),
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: outcomeColors["1"] },
      },
      {
        name: "P(modelo) X",
        type: "line",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: points.map((p) => p.modelX),
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: outcomeColors.X },
      },
      {
        name: "P(modelo) 2",
        type: "line",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: points.map((p) => p.model2),
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: outcomeColors["2"] },
      },
      {
        name: "Implícita 1",
        type: "line",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: points.map((p) => p.implied1),
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1, color: "#64748b", type: "dotted" },
      },
    ],
  };
}

function buildTotalsOptions(
  points: ReturnType<typeof buildTotalsChartPoints>,
  goalEvents: GoalEvent[],
): EChartsOption {
  const labels = points.map((p) => p.label);
  const markLine =
    goalEvents.length > 0
      ? { symbol: ["none", "none"] as [string, string], data: goalMarkLineData(goalEvents) }
      : undefined;

  return {
    backgroundColor: "transparent",
    legend: { top: 8, textStyle: { color: COLORS.text, fontSize: 10 } },
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(15, 23, 42, 0.95)",
      borderColor: "#334155",
      textStyle: { color: "#e2e8f0", fontSize: 11 },
    },
    axisPointer: { link: [{ xAxisIndex: [0, 1] }] },
    grid: [
      { left: 48, right: 48, top: 48, height: "36%" },
      { left: 48, right: 48, top: "54%", height: "32%" },
    ],
    xAxis: [
      { type: "category", data: labels, gridIndex: 0, axisLabel: { color: COLORS.text, fontSize: 10 } },
      { type: "category", data: labels, gridIndex: 1, axisLabel: { color: COLORS.text, fontSize: 10 } },
    ],
    yAxis: [
      {
        scale: true,
        gridIndex: 0,
        name: "Odd Over",
        splitLine: { lineStyle: { color: COLORS.grid, type: "dashed" } },
        axisLabel: { color: COLORS.text, fontSize: 10 },
      },
      {
        gridIndex: 1,
        min: 0,
        max: 100,
        name: "Prob %",
        splitLine: { lineStyle: { color: COLORS.grid, type: "dashed" } },
        axisLabel: { color: COLORS.text, fontSize: 10, formatter: "{value}%" },
      },
    ],
    dataZoom: defaultDataZoom(points.length),
    series: [
      {
        name: "Odd Over 2.5",
        type: "candlestick",
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: points.map((p) => p.overOhlc ?? [null, null, null, null]),
        markLine,
        itemStyle: {
          color: "#38bdf8",
          color0: COLORS.down,
          borderColor: "#38bdf8",
          borderColor0: COLORS.down,
        },
      },
      {
        name: "P(modelo) Over",
        type: "line",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: points.map((p) => p.modelOverPct),
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: "#38bdf8" },
        areaStyle: { color: "rgba(56, 189, 248, 0.15)" },
      },
      {
        name: "Implícita Over",
        type: "line",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: points.map((p) => p.impliedOverPct),
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1.5, color: "#64748b", type: "dotted" },
      },
      {
        name: "Edge Over (pp)",
        type: "bar",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: points.map((p) => p.edgeOverPp),
        barWidth: "50%",
        itemStyle: {
          color: (params) =>
            Number(params.value) >= 0 ? "rgba(0,255,136,0.25)" : "rgba(248,113,113,0.25)",
        },
      },
    ],
  };
}

function TabChart({
  tab,
  history,
  goalEvents,
  data,
  handicapLine,
  asianLine,
}: {
  tab: TabId;
  history: ReturnType<typeof useLivePredictionHistory>["history"];
  goalEvents: GoalEvent[];
  data: SuperbetLiveAdvice;
  handicapLine: string;
  asianLine: string;
}) {
  const h2hPoints = useMemo(() => buildH2hChartPoints(history), [history]);
  const totalsPoints = useMemo(() => buildTotalsChartPoints(history), [history]);
  const h2hOption = useMemo(() => buildH2hOptions(h2hPoints, goalEvents), [h2hPoints, goalEvents]);
  const totalsOption = useMemo(
    () => buildTotalsOptions(totalsPoints, goalEvents),
    [totalsPoints, goalEvents],
  );

  if (history.length < 2) {
    return (
      <p className="py-16 text-center text-xs text-slate-500">
        Aguardando mais ticks ao vivo… (gols marcados no eixo quando o placar mudar)
      </p>
    );
  }

  if (tab === "h2h") {
    return (
      <ReactECharts
        option={h2hOption}
        style={{ height: 380, width: "100%" }}
        opts={{ renderer: "canvas" }}
        notMerge
        lazyUpdate
      />
    );
  }

  if (tab === "totals") {
    if (totalsPoints.every((p) => p.overOdd == null && p.modelOverPct == null)) {
      return (
        <p className="py-16 text-center text-xs text-slate-500">
          Mercado Over 2.5 indisponível neste evento.
        </p>
      );
    }
    return (
      <ReactECharts
        option={totalsOption}
        style={{ height: 380, width: "100%" }}
        opts={{ renderer: "canvas" }}
        notMerge
        lazyUpdate
      />
    );
  }

  const kind = tab === "handicap" ? "handicap" : "asian";
  const lineKey = tab === "handicap" ? handicapLine : asianLine;
  const points = buildHandicapChartPoints(history, kind, lineKey);
  return (
    <HandicapMetricsChart
      points={points}
      homeTeam={data.homeTeam}
      awayTeam={data.awayTeam}
      title={tab === "handicap" ? "Handicap europeu" : "Handicap asiático"}
      goalEvents={goalEvents}
    />
  );
}

interface LivePredictionEvolutionChartProps {
  data: SuperbetLiveAdvice;
}

/** Painel unificado ECharts: 1X2, Over 2.5, Handicap EU e Asiático com marcas de gol. */
export function LivePredictionEvolutionChart({ data }: LivePredictionEvolutionChartProps) {
  const { history, goalEvents } = useLivePredictionHistory(data);
  const ft = data.halfMarkets?.ft;
  const handicapLines = Object.keys(ft?.handicap ?? {});
  const asianLines = Object.keys(ft?.asian_handicap ?? {});

  const [tab, setTab] = useState<TabId>("h2h");
  const [handicapLine, setHandicapLine] = useState(() => pickPrimaryHandicapLine(handicapLines) ?? "0");
  const [asianLine, setAsianLine] = useState(() => pickPrimaryHandicapLine(asianLines) ?? "0");

  const activeHandicap =
    handicapLines.includes(handicapLine) ? handicapLine : pickPrimaryHandicapLine(handicapLines) ?? handicapLine;
  const activeAsian =
    asianLines.includes(asianLine) ? asianLine : pickPrimaryHandicapLine(asianLines) ?? asianLine;

  const lineOptions = tab === "handicap" ? handicapLines : tab === "asian" ? asianLines : [];

  return (
    <section className="rounded-2xl border border-white/8 bg-white/[0.02] p-4 backdrop-blur-sm">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Evolução de mercados</h2>
          <p className="text-[11px] text-slate-500">
            Candlestick + modelo + edge · gols marcados no eixo · zoom no slider
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {goalEvents.length > 0 && (
            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-200">
              {goalEvents.length} gol{goalEvents.length > 1 ? "s" : ""} no gráfico
            </span>
          )}
          <span className="rounded-full border border-white/10 bg-black/30 px-2 py-0.5 text-[10px] text-slate-400">
            {history.length} ticks
          </span>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap gap-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`rounded-lg border px-3 py-1.5 text-[11px] font-medium transition ${
              tab === t.id
                ? "border-neon-green/40 bg-neon-green/10 text-neon-green"
                : "border-white/10 text-slate-500 hover:border-white/20 hover:text-slate-300"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {lineOptions.length > 1 && (tab === "handicap" || tab === "asian") && (
        <div className="mb-3 flex flex-wrap gap-1">
          {lineOptions.map((lk) => (
            <button
              key={lk}
              type="button"
              onClick={() => (tab === "handicap" ? setHandicapLine(lk) : setAsianLine(lk))}
              className={`rounded-lg border px-2 py-1 font-mono text-[10px] transition ${
                (tab === "handicap" ? activeHandicap : activeAsian) === lk
                  ? "border-sky-400/40 bg-sky-400/10 text-sky-300"
                  : "border-white/10 text-slate-500"
              }`}
            >
              {formatHandicapLineKey(lk)}
            </button>
          ))}
        </div>
      )}

      <TabChart
        tab={tab}
        history={history}
        goalEvents={goalEvents}
        data={data}
        handicapLine={activeHandicap}
        asianLine={activeAsian}
      />
    </section>
  );
}
