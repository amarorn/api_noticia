import type { SuperbetLiveAdvice } from "@/domain/entities";

export type HandicapCoverStatus =
  | "on_track"
  | "needs_win"
  | "needs_comeback"
  | "settled_won"
  | "settled_lost";

export interface ParsedHandicapMarket {
  period: "ft" | "1h" | "2h";
  kind: "hcap" | "ah";
  side: "home" | "away";
  lineKey: string;
  line: number;
}

export interface SuggestedHandicapPick extends ParsedHandicapMarket {
  market: string;
  label: string;
}

const MARKET_RE = /^(ft|1h|2h)_(hcap|ah)_(home|away)_(.+)$/;

function lineFromKey(lineKey: string): number | null {
  if (lineKey === "0") return 0;
  const m = lineKey.match(/^([mp])([\d_]+)$/);
  if (!m) return null;
  const n = Number.parseFloat(m[2].replace("_", "."));
  if (!Number.isFinite(n)) return null;
  return m[1] === "m" ? -n : n;
}

export function parseHandicapMarketId(market: string): ParsedHandicapMarket | null {
  const match = market.match(MARKET_RE);
  if (!match) return null;
  const line = lineFromKey(match[4]);
  if (line == null) return null;
  return {
    period: match[1] as ParsedHandicapMarket["period"],
    kind: match[2] as ParsedHandicapMarket["kind"],
    side: match[3] as "home" | "away",
    lineKey: match[4],
    line,
  };
}

function periodGoals(
  period: ParsedHandicapMarket["period"],
  side: "home" | "away",
  homeScore: number,
  awayScore: number,
  minute: number,
  htHome?: number,
  htAway?: number,
): { sideG: number; oppG: number; closed: boolean } {
  if (period === "ft") {
    return {
      sideG: side === "home" ? homeScore : awayScore,
      oppG: side === "home" ? awayScore : homeScore,
      closed: minute >= 90,
    };
  }
  if (period === "1h") {
    if (minute <= 45) {
      return {
        sideG: side === "home" ? homeScore : awayScore,
        oppG: side === "home" ? awayScore : homeScore,
        closed: false,
      };
    }
    const htH = htHome ?? homeScore;
    const htA = htAway ?? awayScore;
    return {
      sideG: side === "home" ? htH : htA,
      oppG: side === "home" ? htA : htH,
      closed: true,
    };
  }
  const htH = htHome ?? 0;
  const htA = htAway ?? 0;
  const shH = Math.max(0, homeScore - htH);
  const shA = Math.max(0, awayScore - htA);
  return {
    sideG: side === "home" ? shH : shA,
    oppG: side === "home" ? shA : shH,
    closed: minute >= 90,
  };
}

function europeanCovers(sideG: number, oppG: number, line: number, side: "home" | "away"): boolean {
  const margin = sideG - oppG;
  return side === "home" ? margin + line > 0 : margin - line > 0;
}

function asianCovers(sideG: number, oppG: number, line: number, side: "home" | "away"): boolean {
  const margin = sideG - oppG;
  const adj = side === "home" ? margin + line : margin - line;
  if (Math.abs(line - Math.round(line)) < 1e-9 && Math.abs(adj) < 1e-9) return false;
  return adj > 0;
}

function minimumHint(
  side: "home" | "away",
  line: number,
  homeScore: number,
  awayScore: number,
  homeTeam: string,
  awayTeam: string,
): string {
  const team = side === "home" ? homeTeam : awayTeam;
  const h = homeScore;
  const a = awayScore;
  if (line <= -0.5) {
    if (side === "home") {
      const need = a - h + 1;
      return need <= 0 ? `${team} já cobre com vitória` : `${team} precisa vencer (ex.: ${a}×${h + need})`;
    }
    const need = h - a + 1;
    return need <= 0 ? `${team} já cobre com vitória` : `${team} precisa vencer (ex.: ${h}×${a + need})`;
  }
  if (line >= 0.5) {
    return `${team} cobre com empate ou vitória (não perder por ${Math.floor(line) + 1}+)`;
  }
  return `${team} precisa vencer (empate anula handicap 0)`;
}

export function assessHandicapCover(
  pick: ParsedHandicapMarket,
  ctx: {
    homeScore: number;
    awayScore: number;
    minute: number;
    homeTeam: string;
    awayTeam: string;
    htHome?: number;
    htAway?: number;
  },
): { status: HandicapCoverStatus; hint: string; covers: boolean } {
  const { homeScore, awayScore, minute, homeTeam, awayTeam, htHome, htAway } = ctx;
  const { sideG, oppG, closed } = periodGoals(
    pick.period,
    pick.side,
    homeScore,
    awayScore,
    minute,
    htHome,
    htAway,
  );
  const covers =
    pick.kind === "ah"
      ? asianCovers(sideG, oppG, pick.line, pick.side)
      : europeanCovers(sideG, oppG, pick.line, pick.side);
  const hint = minimumHint(pick.side, pick.line, homeScore, awayScore, homeTeam, awayTeam);

  if (closed) {
    return {
      status: covers ? "settled_won" : "settled_lost",
      hint,
      covers,
    };
  }
  if (covers) {
    return { status: "on_track", hint, covers };
  }

  const deficit = oppG - sideG;
  const needsWin = pick.line <= -0.5 || (pick.line === 0 && pick.kind === "hcap");
  if (needsWin && deficit >= 3) {
    return { status: "needs_comeback", hint, covers: false };
  }
  if (needsWin && deficit > 0) {
    return { status: "needs_win", hint, covers: false };
  }
  return { status: "needs_win", hint, covers: false };
}

export function coverStatusLabel(status: HandicapCoverStatus): string {
  switch (status) {
    case "on_track":
      return "No caminho";
    case "needs_win":
      return "Precisa reação";
    case "needs_comeback":
      return "Virada difícil";
    case "settled_won":
      return "Coberto";
    case "settled_lost":
      return "Perdido";
    default:
      return status;
  }
}

export function coverStatusColor(status: HandicapCoverStatus): string {
  switch (status) {
    case "on_track":
    case "settled_won":
      return "#00ff88";
    case "needs_win":
      return "#fbbf24";
    case "needs_comeback":
    case "settled_lost":
      return "#f87171";
    default:
      return "#64748b";
  }
}

/** Trajetória 0–100 para barra de “caminho do palpite”. */
export function coverTrajectoryValue(status: HandicapCoverStatus): number {
  switch (status) {
    case "settled_won":
    case "on_track":
      return 100;
    case "needs_win":
      return 55;
    case "needs_comeback":
      return 25;
    case "settled_lost":
      return 0;
    default:
      return 40;
  }
}

export function pickSuggestedHandicap(data: SuperbetLiveAdvice): SuggestedHandicapPick | null {
  type Row = { market: string; label: string; edgePp: number };
  const rows: Row[] = [];

  for (const a of data.aportes ?? []) {
    if (a.market.includes("_hcap_") || a.market.includes("_ah_")) {
      rows.push({ market: a.market, label: a.label, edgePp: a.edgePp ?? 0 });
    }
  }
  for (const o of data.strategy?.opportunities ?? []) {
    if (o.market.includes("_hcap_") || o.market.includes("_ah_")) {
      rows.push({ market: o.market, label: o.label, edgePp: o.edgePp ?? 0 });
    }
  }

  rows.sort((a, b) => b.edgePp - a.edgePp);
  for (const row of rows) {
    const parsed = parseHandicapMarketId(row.market);
    if (parsed) {
      return { ...parsed, market: row.market, label: row.label };
    }
  }
  return null;
}

/** Linha do gráfico (chave Superbet) para o palpite indicado. */
export function chartLineKeyForPick(pick: ParsedHandicapMarket): string {
  if (pick.side === "home" && pick.lineKey.startsWith("m")) return pick.lineKey;
  if (pick.side === "away" && pick.lineKey.startsWith("p")) return pick.lineKey;
  if (pick.side === "home" && pick.lineKey.startsWith("p")) return pick.lineKey;
  if (pick.side === "away" && pick.lineKey.startsWith("m")) return pick.lineKey;
  return pick.lineKey;
}

export function pickMatchesChartLine(pick: ParsedHandicapMarket, chartLineKey: string): boolean {
  return chartLineKeyForPick(pick) === chartLineKey;
}
