/** Utilitários compartilhados para gráficos ao vivo (ECharts). */

export interface ParsedScore {
  home: number;
  away: number;
  label: string;
}

export interface GoalEvent {
  index: number;
  minute: number;
  label: string;
  scoreLabel: string;
  side: "home" | "away" | "both";
}

export function parseScore(raw: string | null | undefined): ParsedScore | null {
  if (!raw) return null;
  const parts = raw.toLowerCase().split("x");
  if (parts.length !== 2) return null;
  const home = Number.parseInt(parts[0]?.trim() ?? "", 10);
  const away = Number.parseInt(parts[1]?.trim() ?? "", 10);
  if (!Number.isFinite(home) || !Number.isFinite(away)) return null;
  return { home, away, label: `${home}×${away}` };
}

export function impliedPctFromOdd(odd: number | null | undefined): number | null {
  if (odd == null || odd <= 1) return null;
  return 100 / odd;
}

export function buildOhlc(
  prev: number | null,
  current: number | null,
): [number, number, number, number] | null {
  if (current == null) return null;
  const open = prev ?? current;
  const close = current;
  return [open, close, Math.min(open, close), Math.max(open, close)];
}

/** Detecta gols comparando placar entre ticks consecutivos. */
export function detectGoalEvents(
  ticks: Array<{ minute: number; label: string; homeScore: number; awayScore: number }>,
): GoalEvent[] {
  const goals: GoalEvent[] = [];
  for (let i = 0; i < ticks.length; i += 1) {
    if (i === 0) continue;
    const prev = ticks[i - 1];
    const cur = ticks[i];
    const dh = cur.homeScore - prev.homeScore;
    const da = cur.awayScore - prev.awayScore;
    if (dh <= 0 && da <= 0) continue;
    let side: GoalEvent["side"] = "both";
    if (dh > 0 && da === 0) side = "home";
    else if (da > 0 && dh === 0) side = "away";
    goals.push({
      index: i,
      minute: cur.minute,
      label: cur.label,
      scoreLabel: `⚽ ${cur.homeScore}×${cur.awayScore}`,
      side,
    });
  }
  return goals;
}

export function goalMarkLineData(goals: GoalEvent[]) {
  return goals.map((g) => ({
    xAxis: g.label,
    label: {
      formatter: g.scoreLabel,
      color: "#fde68a",
      fontSize: 10,
      fontWeight: 600,
    },
    lineStyle: { color: "rgba(251, 191, 36, 0.55)", type: "dashed" as const, width: 1.5 },
  }));
}

export function defaultDataZoom(pointCount: number, xAxisIndexes: number[] = [0, 1]) {
  return [
    {
      type: "inside" as const,
      xAxisIndex: xAxisIndexes,
      start: pointCount > 12 ? 100 - (12 / pointCount) * 100 : 0,
      end: 100,
    },
    {
      type: "slider" as const,
      xAxisIndex: xAxisIndexes,
      bottom: 4,
      height: 18,
      borderColor: "#1e293b",
      fillerColor: "rgba(0, 255, 136, 0.12)",
      handleStyle: { color: "#00ff88" },
      textStyle: { color: "#94a3b8", fontSize: 9 },
    },
  ];
}
