import type { WcPrediction, WcScheduleMatch } from "@/domain/entities";

export interface BracketPhaseColumn {
  phase: string;
  label: string;
  matches: BracketMatchNode[];
}

export interface BracketMatchNode {
  id: string;
  homeTeam: string;
  awayTeam: string;
  homeScore: number | null;
  awayScore: number | null;
  played: boolean;
  winner: string | null;
  loser: string | null;
  kickoff: string | null;
  placeholder: boolean;
  sourceMatchIds: string[];
  prediction: "1" | "X" | "2" | null;
  confidence: number | null;
  probHome: number | null;
  probDraw: number | null;
  probAway: number | null;
  projectedWinner: string | null;
  analysisContext: string | null;
}

const PHASE_ORDER: { phase: string; label: string; slots: number }[] = [
  { phase: "round_of_32", label: "32 avos", slots: 16 },
  { phase: "round_16", label: "Oitavas", slots: 8 },
  { phase: "quarterfinal", label: "Quartas", slots: 4 },
  { phase: "semifinal", label: "Semis", slots: 2 },
  { phase: "final", label: "Final", slots: 1 },
];

const KNOCKOUT_PHASES = new Set(PHASE_ORDER.map((p) => p.phase));
const TBD = "A definir";

function parseActualScore(score: string): { home: number; away: number } | null {
  const m = score.trim().match(/^(\d+)\s*[xX×]\s*(\d+)$/);
  if (!m) return null;
  return { home: Number(m[1]), away: Number(m[2]) };
}

function resolveMatchResult(
  match: WcScheduleMatch,
  predictionLookup: Map<string, WcPrediction>,
): Pick<BracketMatchNode, "homeScore" | "awayScore" | "played" | "winner" | "loser"> {
  let homeScore = match.homeScore ?? null;
  let awayScore = match.awayScore ?? null;

  // Placar oficial do calendário tem prioridade; palpites da fase de grupos não
  // devem vazar para o mata-mata (mesmo confronto mandante×visitante).
  const isKnockout = KNOCKOUT_PHASES.has(match.phase);
  if (!isKnockout && (homeScore == null || awayScore == null)) {
    const key = `${match.homeTeam}::${match.awayTeam}`;
    const rev = `${match.awayTeam}::${match.homeTeam}`;
    const pred = predictionLookup.get(key) ?? predictionLookup.get(rev);
    if (pred?.actualScore) {
      const parsed = parseActualScore(pred.actualScore);
      if (parsed) {
        if (predictionLookup.has(key)) {
          homeScore = parsed.home;
          awayScore = parsed.away;
        } else {
          homeScore = parsed.away;
          awayScore = parsed.home;
        }
      }
    }
  }

  const played = homeScore != null && awayScore != null;
  if (!played) {
    return { homeScore, awayScore, played: false, winner: null, loser: null };
  }

  const hs = homeScore as number;
  const as = awayScore as number;

  if (hs > as) {
    return {
      homeScore: hs,
      awayScore: as,
      played: true,
      winner: match.homeTeam,
      loser: match.awayTeam,
    };
  }
  if (as > hs) {
    return {
      homeScore: hs,
      awayScore: as,
      played: true,
      winner: match.awayTeam,
      loser: match.homeTeam,
    };
  }
  return { homeScore: hs, awayScore: as, played: true, winner: null, loser: null };
}

function sortByKickoff(a: WcScheduleMatch, b: WcScheduleMatch): number {
  const ka = a.kickoff ?? "";
  const kb = b.kickoff ?? "";
  return ka.localeCompare(kb);
}

function buildPlaceholderNode(
  id: string,
  homeTeam: string,
  awayTeam: string,
  sourceMatchIds: string[],
): BracketMatchNode {
  return {
    id,
    homeTeam,
    awayTeam,
    homeScore: null,
    awayScore: null,
    played: false,
    winner: null,
    loser: null,
    kickoff: null,
    placeholder: true,
    sourceMatchIds,
    prediction: null,
    confidence: null,
    probHome: null,
    probDraw: null,
    probAway: null,
    projectedWinner: null,
    analysisContext: null,
  };
}

function projectionForMatch(
  match: WcScheduleMatch,
  predictionLookup: Map<string, WcPrediction>,
): Pick<
  BracketMatchNode,
  | "prediction"
  | "confidence"
  | "probHome"
  | "probDraw"
  | "probAway"
  | "projectedWinner"
  | "analysisContext"
> {
  const key = `${match.homeTeam}::${match.awayTeam}`;
  const detailed = predictionLookup.get(key);
  const prediction = detailed?.prediction ?? match.prediction ?? null;
  const probHome = detailed?.probHome ?? match.probHome ?? null;
  const probDraw = detailed?.probDraw ?? match.probDraw ?? null;
  const probAway = detailed?.probAway ?? match.probAway ?? null;
  const confidence = detailed?.confidence ?? match.confidence ?? null;

  let projectedWinner: string | null = null;
  if (prediction === "1") projectedWinner = match.homeTeam;
  if (prediction === "2") projectedWinner = match.awayTeam;
  if (prediction === "X") {
    // No mata-mata o empate em 90 minutos não classifica ninguém. Para a chave,
    // usa-se a maior chance de vitória entre as duas seleções e o card mantém P(X).
    projectedWinner = (probHome ?? 0) >= (probAway ?? 0) ? match.homeTeam : match.awayTeam;
  }

  return {
    prediction,
    confidence,
    probHome,
    probDraw,
    probAway,
    projectedWinner,
    analysisContext: detailed?.context ?? null,
  };
}

/** Só o vencedor de um jogo encerrado avança; jogo pendente → slot vazio. */
export function advanceFromMatch(
  node: BracketMatchNode | undefined,
  eliminated: ReadonlySet<string>,
): string {
  if (!node?.played || !node.winner) return TBD;
  if (eliminated.has(node.winner)) return TBD;
  return node.winner;
}

/** Avança resultado oficial quando existe; caso contrário, usa projeção identificada. */
export function projectFromMatch(
  node: BracketMatchNode | undefined,
  eliminated: ReadonlySet<string>,
): string {
  const team = node?.winner ?? node?.projectedWinner;
  if (!team || eliminated.has(team)) return TBD;
  return team;
}

function collectEliminated(nodes: BracketMatchNode[], eliminated: Set<string>): void {
  for (const node of nodes) {
    if (node.loser) eliminated.add(node.loser);
  }
}

/** Remove seleções já eliminadas de fases posteriores (ex.: Japão após perder nos 32 avos). */
export function scrubEliminatedTeams(
  nodes: BracketMatchNode[],
  eliminated: ReadonlySet<string>,
): void {
  for (const node of nodes) {
    let homeChanged = false;
    let awayChanged = false;

    if (node.homeTeam !== TBD && eliminated.has(node.homeTeam)) {
      node.homeTeam = TBD;
      homeChanged = true;
    }
    if (node.awayTeam !== TBD && eliminated.has(node.awayTeam)) {
      node.awayTeam = TBD;
      awayChanged = true;
    }

    if (homeChanged || awayChanged) {
      node.homeScore = null;
      node.awayScore = null;
      node.played = false;
      node.winner = null;
      node.loser = null;
      if (!node.placeholder) {
        node.placeholder = true;
      }
    }
  }
}

/** Monta colunas do mata-mata com vencedores/eliminados e slots projetados. */
export function buildKnockoutBracket(
  scheduleMatches: WcScheduleMatch[],
  predictions: WcPrediction[] = [],
): BracketPhaseColumn[] {
  const predictionLookup = new Map<string, WcPrediction>();
  for (const p of predictions) {
    predictionLookup.set(`${p.homeTeam}::${p.awayTeam}`, p);
  }

  const knockoutRaw = scheduleMatches.filter((m) => KNOCKOUT_PHASES.has(m.phase));
  if (knockoutRaw.length === 0) {
    return [];
  }

  const eliminated = new Set<string>();
  const byPhase = new Map<string, BracketMatchNode[]>();

  for (const phaseDef of PHASE_ORDER) {
    const scheduled = knockoutRaw.filter((m) => m.phase === phaseDef.phase).sort(sortByKickoff);
    const nodes: BracketMatchNode[] = scheduled.map((m) => {
      const result = resolveMatchResult(m, predictionLookup);
      const projection = projectionForMatch(m, predictionLookup);
      return {
        id: m.matchId,
        homeTeam: m.homeTeam,
        awayTeam: m.awayTeam,
        homeScore: result.homeScore,
        awayScore: result.awayScore,
        played: result.played,
        winner: result.winner,
        loser: result.loser,
        kickoff: m.kickoff,
        placeholder: false,
        sourceMatchIds: [],
        ...projection,
        projectedWinner: result.winner ?? projection.projectedWinner,
      };
    });

    scrubEliminatedTeams(nodes, eliminated);

    const prev = byPhase.get(PHASE_ORDER[PHASE_ORDER.indexOf(phaseDef) - 1]?.phase ?? "") ?? [];
    const expected = phaseDef.slots;

    if (prev.length > 0) {
      for (let i = nodes.length; i < expected; i++) {
        const left = prev[i * 2];
        const right = prev[i * 2 + 1];
        const homeLabel = projectFromMatch(left, eliminated);
        const awayLabel = projectFromMatch(right, eliminated);
        const sources = [left?.id, right?.id].filter(Boolean) as string[];
        const placeholder = buildPlaceholderNode(
            `placeholder-${phaseDef.phase}-${i}`,
            homeLabel,
            awayLabel,
            sources,
          );
        placeholder.projectedWinner = null;
        nodes.push(placeholder);
      }
    }

    while (nodes.length < expected) {
      const i = nodes.length;
      nodes.push(
        buildPlaceholderNode(`placeholder-${phaseDef.phase}-${i}`, TBD, TBD, []),
      );
    }

    const phaseNodes = nodes.slice(0, expected);
    scrubEliminatedTeams(phaseNodes, eliminated);
    collectEliminated(phaseNodes, eliminated);
    byPhase.set(phaseDef.phase, phaseNodes);
  }

  return PHASE_ORDER.map((p) => ({
    phase: p.phase,
    label: p.label,
    matches: byPhase.get(p.phase) ?? [],
  })).filter((col) => col.matches.length > 0);
}

export function bracketStats(columns: BracketPhaseColumn[]) {
  const all = columns.flatMap((c) => c.matches);
  const played = all.filter((m) => m.played && !m.placeholder).length;
  const scheduled = all.filter((m) => !m.placeholder).length;
  const eliminated = new Set(all.filter((m) => m.loser).map((m) => m.loser as string));
  return { played, scheduled, eliminated: eliminated.size };
}

export interface BracketTreeHalf {
  r32: BracketMatchNode[];
  r16: BracketMatchNode[];
  quarter: BracketMatchNode[];
  semi: BracketMatchNode[];
}

export interface BracketTree {
  left: BracketTreeHalf;
  right: BracketTreeHalf;
  final: BracketMatchNode | null;
  labels: { r32: string; r16: string; quarter: string; semi: string; final: string };
}

function padMatches(list: BracketMatchNode[], count: number, phase: string): BracketMatchNode[] {
  const out = [...list];
  while (out.length < count) {
    out.push(
      buildPlaceholderNode(`placeholder-${phase}-pad-${out.length}`, TBD, TBD, []),
    );
  }
  return out.slice(0, count);
}

/** Árvore simétrica esquerda/direita convergindo à final (estilo chave clássica). */
export function buildBracketTree(columns: BracketPhaseColumn[]): BracketTree | null {
  if (columns.length === 0) return null;

  const get = (phase: string) => columns.find((c) => c.phase === phase)?.matches ?? [];
  const label = (phase: string) => columns.find((c) => c.phase === phase)?.label ?? phase;

  const r32 = padMatches(get("round_of_32"), 16, "round_of_32");
  const r16 = padMatches(get("round_16"), 8, "round_16");
  const quarter = padMatches(get("quarterfinal"), 4, "quarterfinal");
  const semi = padMatches(get("semifinal"), 2, "semifinal");
  const finalList = padMatches(get("final"), 1, "final");

  return {
    left: {
      r32: r32.slice(0, 8),
      r16: r16.slice(0, 4),
      quarter: quarter.slice(0, 2),
      semi: semi.slice(0, 1),
    },
    right: {
      r32: [...r32.slice(8, 16)].reverse(),
      r16: [...r16.slice(4, 8)].reverse(),
      quarter: [...quarter.slice(2, 4)].reverse(),
      semi: semi.slice(1, 2),
    },
    final: finalList[0] ?? null,
    labels: {
      r32: label("round_of_32"),
      r16: label("round_16"),
      quarter: label("quarterfinal"),
      semi: label("semifinal"),
      final: label("final"),
    },
  };
}

/** Mapa global de eliminados por fase (para estilo visual em fases futuras). */
export function buildEliminatedByPhase(columns: BracketPhaseColumn[]): Map<string, Set<string>> {
  const cumulative = new Set<string>();
  const out = new Map<string, Set<string>>();

  for (const col of columns) {
    out.set(col.phase, new Set(cumulative));
    for (const match of col.matches) {
      if (match.loser) cumulative.add(match.loser);
    }
  }
  return out;
}
