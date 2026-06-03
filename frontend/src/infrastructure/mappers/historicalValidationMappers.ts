import type {
  HistoricalValidationMatch,
  HistoricalValidationResult,
  OutcomeLabel,
  WcEdition,
  WcHistoricalMatch,
} from "@/domain/entities";
import { mapModelBreakdown, type ApiModelBreakdown } from "./index";

function mapOutcome(value: string): OutcomeLabel {
  if (value === "1" || value === "X" || value === "2") return value;
  return "X";
}

interface ApiWcEdition {
  season: number;
  label: string;
  match_count: number;
}

interface ApiWcHistoricalMatch {
  match_id: string;
  season: number;
  home_team: string;
  away_team: string;
  match_date: string;
  phase: string;
  phase_label: string;
  group_name: string | null;
  home_score: number;
  away_score: number;
  result: string;
  result_label: string;
  score: string;
}

interface ApiValidateMatch {
  match_id: string;
  season: number;
  home_team: string;
  away_team: string;
  match_date: string;
  phase: string;
  phase_label: string;
  group_name: string | null;
  home_score: number;
  away_score: number;
  actual_result: string;
  actual_result_label: string;
  actual_score: string;
}

interface ApiValidateResponse {
  match: ApiValidateMatch;
  prediction: string;
  confidence: number;
  prob_home: number;
  prob_draw: number;
  prob_away: number;
  poisson_score: string;
  expected_goals: string;
  correct: boolean;
  context: string;
  h2h_summary: string;
  model_breakdown: ApiModelBreakdown;
  cutoff_date: string;
  cutoff_note: string;
}

export function mapWcEdition(raw: ApiWcEdition): WcEdition {
  return {
    season: raw.season,
    label: raw.label,
    matchCount: raw.match_count,
  };
}

export function mapWcHistoricalMatch(raw: ApiWcHistoricalMatch): WcHistoricalMatch {
  return {
    matchId: raw.match_id,
    season: raw.season,
    homeTeam: raw.home_team,
    awayTeam: raw.away_team,
    matchDate: raw.match_date,
    phase: raw.phase,
    phaseLabel: raw.phase_label,
    groupName: raw.group_name,
    homeScore: raw.home_score,
    awayScore: raw.away_score,
    result: mapOutcome(raw.result),
    resultLabel: raw.result_label,
    score: raw.score,
  };
}

function mapValidationMatch(raw: ApiValidateMatch): HistoricalValidationMatch {
  return {
    matchId: raw.match_id,
    season: raw.season,
    homeTeam: raw.home_team,
    awayTeam: raw.away_team,
    matchDate: raw.match_date,
    phase: raw.phase,
    phaseLabel: raw.phase_label,
    groupName: raw.group_name,
    homeScore: raw.home_score,
    awayScore: raw.away_score,
    actualResult: mapOutcome(raw.actual_result),
    actualResultLabel: raw.actual_result_label,
    actualScore: raw.actual_score,
  };
}

export function mapHistoricalValidation(
  raw: ApiValidateResponse,
): HistoricalValidationResult {
  return {
    match: mapValidationMatch(raw.match),
    prediction: mapOutcome(raw.prediction),
    confidence: raw.confidence,
    probHome: raw.prob_home,
    probDraw: raw.prob_draw,
    probAway: raw.prob_away,
    poissonScore: raw.poisson_score,
    expectedGoals: raw.expected_goals,
    correct: raw.correct,
    context: raw.context,
    h2hSummary: raw.h2h_summary,
    modelBreakdown: mapModelBreakdown(raw.model_breakdown),
    cutoffDate: raw.cutoff_date,
    cutoffNote: raw.cutoff_note,
  };
}
