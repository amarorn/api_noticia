import type { LivePredictionTick } from "@/presentation/hooks/useLivePredictionHistory";
import { buildOhlc, impliedPctFromOdd } from "@/presentation/utils/liveChartUtils";
import {
  formatHandicapLineKey,
  handicapOddForSide,
  bookModelProbKey,
  pairedHandicapKeys,
} from "@/presentation/utils/handicapLine";
import {
  assessHandicapCover,
  type HandicapCoverStatus,
  type SuggestedHandicapPick,
  pickMatchesChartLine,
  coverTrajectoryValue,
} from "@/presentation/utils/handicapCover";

export type MarketKind = "handicap" | "asian";

export interface H2hChartPoint {
  minute: number;
  label: string;
  odd1: number | null;
  oddX: number | null;
  odd2: number | null;
  odd1Ohlc: [number, number, number, number] | null;
  model1: number;
  modelX: number;
  model2: number;
  implied1: number | null;
  impliedX: number | null;
  implied2: number | null;
  edge1: number | null;
  edgeX: number | null;
  edge2: number | null;
}

export interface TotalsChartPoint {
  minute: number;
  label: string;
  overOdd: number | null;
  overOhlc: [number, number, number, number] | null;
  modelOverPct: number | null;
  impliedOverPct: number | null;
  edgeOverPp: number | null;
}

export interface HandicapChartPoint {
  minute: number;
  label: string;
  currentScore: string | null;
  homeLineKey: string;
  awayLineKey: string;
  homeOdd: number | null;
  awayOdd: number | null;
  homeImpliedPct: number | null;
  awayImpliedPct: number | null;
  homeModelPct: number | null;
  /** P(modelo) do botão Superbet do visitante (+0.5 quando casa é −0.5). */
  awayModelPct: number | null;
  /** P(modelo) vitória pura visitante (= AH −0.5), condicionada ao placar. */
  awayWinModelPct: number | null;
  homeEdgePp: number | null;
  awayEdgePp: number | null;
  homeOhlc: [number, number, number, number] | null;
  /** Palpite indicado (quando linha do gráfico = palpite). */
  suggestedCoverStatus?: HandicapCoverStatus | null;
  suggestedCoverHint?: string | null;
  suggestedModelPct?: number | null;
  suggestedTrajectory?: number | null;
}

export function buildH2hChartPoints(history: LivePredictionTick[]): H2hChartPoint[] {
  let prevOdd1: number | null = null;
  return history.map((t) => {
    const odd1 = t.h2hOdds["1"] ?? null;
    const oddX = t.h2hOdds["X"] ?? null;
    const odd2 = t.h2hOdds["2"] ?? null;
    const implied1 = impliedPctFromOdd(odd1) ?? (t.h2hImplied["1"] != null ? t.h2hImplied["1"] * 100 : null);
    const impliedX = impliedPctFromOdd(oddX) ?? (t.h2hImplied["X"] != null ? t.h2hImplied["X"] * 100 : null);
    const implied2 = impliedPctFromOdd(odd2) ?? (t.h2hImplied["2"] != null ? t.h2hImplied["2"] * 100 : null);
    const point: H2hChartPoint = {
      minute: t.minute,
      label: t.label,
      odd1,
      oddX,
      odd2,
      odd1Ohlc: buildOhlc(prevOdd1, odd1),
      model1: t.modelHomePct,
      modelX: t.modelDrawPct,
      model2: t.modelAwayPct,
      implied1,
      impliedX,
      implied2,
      edge1: implied1 != null ? t.modelHomePct - implied1 : null,
      edgeX: impliedX != null ? t.modelDrawPct - impliedX : null,
      edge2: implied2 != null ? t.modelAwayPct - implied2 : null,
    };
    if (odd1 != null) prevOdd1 = odd1;
    return point;
  });
}

export function buildTotalsChartPoints(history: LivePredictionTick[]): TotalsChartPoint[] {
  let prevOdd: number | null = null;
  return history.map((t) => {
    const implied = t.over25ImpliedPct ?? impliedPctFromOdd(t.over25Odd);
    const point: TotalsChartPoint = {
      minute: t.minute,
      label: t.label,
      overOdd: t.over25Odd,
      overOhlc: buildOhlc(prevOdd, t.over25Odd),
      modelOverPct: t.over25ModelPct,
      impliedOverPct: implied,
      edgeOverPp:
        t.over25ModelPct != null && implied != null ? t.over25ModelPct - implied : null,
    };
    if (t.over25Odd != null) prevOdd = t.over25Odd;
    return point;
  });
}

export function buildHandicapChartPoints(
  history: LivePredictionTick[],
  kind: MarketKind,
  lineKey: string,
  options?: {
    homeTeam?: string;
    awayTeam?: string;
    suggestedPick?: SuggestedHandicapPick | null;
    htHome?: number;
    htAway?: number;
  },
): HandicapChartPoint[] {
  const oddsKey = kind === "handicap" ? "handicap" : "asianHandicap";
  const modelKey = kind === "handicap" ? "modelHandicap" : "modelAsian";
  const { homeLineKey, awayLineKey } = pairedHandicapKeys(lineKey);
  let prevHomeOdd: number | null = null;
  const homeTeam = options?.homeTeam ?? "Casa";
  const awayTeam = options?.awayTeam ?? "Fora";
  const suggested = options?.suggestedPick;
  const showSuggested =
    suggested != null &&
    suggested.kind === (kind === "handicap" ? "hcap" : "ah") &&
    pickMatchesChartLine(suggested, lineKey);

  return history.map((sample) => {
    const book = sample[oddsKey];
    const homeOdd = handicapOddForSide(book, "home", homeLineKey);
    const awayOdd = handicapOddForSide(book, "away", awayLineKey);
    const homeModel = sample[modelKey]?.[bookModelProbKey("home", homeLineKey)] ?? null;
    const awayModel = sample[modelKey]?.[bookModelProbKey("away", awayLineKey)] ?? null;
    const awayWinModel =
      awayLineKey !== homeLineKey
        ? sample[modelKey]?.[bookModelProbKey("away", homeLineKey)] ?? null
        : awayModel;
    const homeImpliedPct = impliedPctFromOdd(homeOdd);
    const awayImpliedPct = impliedPctFromOdd(awayOdd);
    const homeModelPct = homeModel != null ? homeModel * 100 : null;
    const awayModelPct = awayModel != null ? awayModel * 100 : null;
    const awayWinModelPct = awayWinModel != null ? awayWinModel * 100 : null;

    let suggestedCoverStatus: HandicapCoverStatus | null = null;
    let suggestedCoverHint: string | null = null;
    let suggestedModelPct: number | null = null;
    let suggestedTrajectory: number | null = null;

    if (showSuggested && suggested) {
      const cover = assessHandicapCover(suggested, {
        homeScore: sample.homeScore,
        awayScore: sample.awayScore,
        minute: sample.minute,
        homeTeam,
        awayTeam,
        htHome: options?.htHome,
        htAway: options?.htAway,
      });
      suggestedCoverStatus = cover.status;
      suggestedCoverHint = cover.hint;
      const probKey = bookModelProbKey(suggested.side, suggested.lineKey);
      const raw = sample[modelKey]?.[probKey];
      suggestedModelPct = raw != null ? raw * 100 : null;
      suggestedTrajectory = coverTrajectoryValue(cover.status);
    }

    const point: HandicapChartPoint = {
      minute: sample.minute,
      label: sample.label,
      currentScore: sample.currentScore,
      homeLineKey,
      awayLineKey,
      homeOdd,
      awayOdd,
      homeImpliedPct,
      awayImpliedPct,
      homeModelPct,
      awayModelPct,
      awayWinModelPct,
      homeEdgePp:
        homeModelPct != null && homeImpliedPct != null ? homeModelPct - homeImpliedPct : null,
      awayEdgePp:
        awayModelPct != null && awayImpliedPct != null ? awayModelPct - awayImpliedPct : null,
      homeOhlc: buildOhlc(prevHomeOdd, homeOdd),
      suggestedCoverStatus,
      suggestedCoverHint,
      suggestedModelPct,
      suggestedTrajectory,
    };
    if (homeOdd != null) prevHomeOdd = homeOdd;
    return point;
  });
}

export function handicapChartLegendSuffix(
  homeTeam: string,
  awayTeam: string,
  point: HandicapChartPoint | undefined,
): { homeLine: string; awayLine: string; awayWinLine: string | null } {
  if (!point) {
    return { homeLine: "", awayLine: "", awayWinLine: null };
  }
  const homeLine = `${homeTeam} ${formatHandicapLineKey(point.homeLineKey)}`;
  const awayLine = `${awayTeam} ${formatHandicapLineKey(point.awayLineKey)}`;
  const awayWinLine =
    point.homeLineKey !== point.awayLineKey
      ? `${awayTeam} ${formatHandicapLineKey(point.homeLineKey)} (vitória)`
      : null;
  return { homeLine, awayLine, awayWinLine };
}
