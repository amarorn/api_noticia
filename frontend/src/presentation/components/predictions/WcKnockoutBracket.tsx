import { useMemo } from "react";
import type { WcPrediction, WcScheduleMatch } from "@/domain/entities";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";
import { getTeamIso } from "@/presentation/utils/teamFlags";
import {
  bracketStats,
  buildBracketTree,
  buildEliminatedByPhase,
  buildKnockoutBracket,
  type BracketMatchNode,
  type BracketTreeHalf,
} from "@/presentation/utils/wcKnockoutBracket";

interface WcKnockoutBracketProps {
  matches: WcScheduleMatch[];
  predictions?: WcPrediction[];
  resultsSyncedAt?: string | null;
}

const ROWS = 8;
const ROW_H = 54;
const GRID_H = ROWS * ROW_H;
const COL_W = 108;
const WIRE_W = 22;

function teamStatus(
  match: BracketMatchNode,
  team: string,
  eliminatedBeforePhase: Set<string>,
): "winner" | "loser" | "pending" | "tbd" | "eliminated" {
  if (team === "A definir") return "tbd";
  if (eliminatedBeforePhase.has(team) && !match.played) return "eliminated";
  if (!match.played) return match.placeholder ? "tbd" : "pending";
  if (match.winner === team) return "winner";
  if (match.loser === team) return "loser";
  return "pending";
}

function teamScore(match: BracketMatchNode, team: string): number | null {
  if (team === match.homeTeam) return match.homeScore;
  if (team === match.awayTeam) return match.awayScore;
  return null;
}

function teamLabel(team: string): string {
  if (team === "A definir") return "—";
  const iso = getTeamIso(team);
  if (iso) return iso.toUpperCase();
  const parts = team.trim().split(/\s+/);
  return parts[parts.length - 1].slice(0, 3).toUpperCase();
}

function centerY(tier: number, index: number): number {
  const span = 2 ** tier;
  return (index * span + span / 2) * ROW_H;
}

/** Borda interna entre dois cards adjacentes (ex.: par nos 32 avos). */
function pairEdgeY(tier: number, pairIndex: number, edge: "top" | "bottom"): number {
  const span = 2 ** tier;
  const row = pairIndex * 2 + (edge === "bottom" ? 1 : 0);
  return (row * span + span / 2) * ROW_H;
}

function BracketTeamRow({
  match,
  team,
  eliminatedBeforePhase,
}: {
  match: BracketMatchNode;
  team: string;
  eliminatedBeforePhase: Set<string>;
}) {
  const status = teamStatus(match, team, eliminatedBeforePhase);
  const score = teamScore(match, team);
  const isTbd = team === "A definir";

  return (
    <div className={`wc-bracket-row ${status}`} title={isTbd ? "Aguardando classificados" : team}>
      {!isTbd ? (
        <TeamFlag team={team} size={20} rounded="md" />
      ) : (
        <span className="wc-bracket-row-tbd" aria-hidden />
      )}
      <span className="wc-bracket-row-label">{teamLabel(team)}</span>
      {score != null && <span className="wc-bracket-row-score">{score}</span>}
      {status === "winner" && match.played && (
        <span className="wc-bracket-row-badge" aria-label="Classificado">
          ✓
        </span>
      )}
    </div>
  );
}

function BracketMatchCard({
  match,
  eliminatedBeforePhase,
}: {
  match: BracketMatchNode;
  eliminatedBeforePhase: Set<string>;
}) {
  return (
    <div
      className={`wc-bracket-card ${match.played && match.winner ? "is-resolved" : ""} ${
        match.placeholder ? "is-placeholder" : ""
      }`}
    >
      <BracketTeamRow match={match} team={match.homeTeam} eliminatedBeforePhase={eliminatedBeforePhase} />
      <div className="wc-bracket-card-divider" aria-hidden />
      <BracketTeamRow match={match} team={match.awayTeam} eliminatedBeforePhase={eliminatedBeforePhase} />
    </div>
  );
}

function BracketWires({
  side,
  rounds,
  id,
}: {
  side: "left" | "right";
  rounds: Array<{ tier: number; count: number }>;
  id: string;
}) {
  const cols = rounds.length;
  const width = cols * COL_W + (cols - 1) * WIRE_W;
  const paths: string[] = [];
  const nodes: Array<{ cx: number; cy: number }> = [];

  const colLeft = (index: number) => index * (COL_W + WIRE_W);
  const colRight = (index: number) => colLeft(index) + COL_W;

  const wirePairs: Array<{ fromTier: number; toTier: number; fromCol: number; toCol: number; count: number }> =
    [];

  if (side === "left") {
    for (let c = 0; c < cols - 1; c++) {
      wirePairs.push({
        fromTier: rounds[c].tier,
        toTier: rounds[c + 1].tier,
        fromCol: c,
        toCol: c + 1,
        count: rounds[c + 1].count,
      });
    }
  } else {
    for (let c = 0; c < cols - 1; c++) {
      const fromCol = cols - 1 - c;
      const toCol = cols - 2 - c;
      wirePairs.push({
        fromTier: rounds[fromCol].tier,
        toTier: rounds[toCol].tier,
        fromCol,
        toCol,
        count: rounds[toCol].count,
      });
    }
  }

  for (const pair of wirePairs) {
    const xFrom = side === "left" ? colRight(pair.fromCol) : colLeft(pair.fromCol);
    const xTo = side === "left" ? colLeft(pair.toCol) : colRight(pair.toCol);
    const xFork = (xFrom + xTo) / 2;

    for (let i = 0; i < pair.count; i++) {
      const yTop = pair.fromTier === 0
        ? pairEdgeY(0, i, "top")
        : centerY(pair.fromTier, i * 2);
      const yBottom = pair.fromTier === 0
        ? pairEdgeY(0, i, "bottom")
        : centerY(pair.fromTier, i * 2 + 1);
      const yMid = centerY(pair.toTier, i);
      paths.push(`M ${xFrom} ${yTop} H ${xFork} V ${yMid} H ${xTo}`);
      paths.push(`M ${xFrom} ${yBottom} H ${xFork} V ${yMid}`);
      nodes.push({ cx: xFork, cy: yMid });
    }
  }

  const glowId = `wire-glow-${id}`;
  const gradId = `wire-grad-${id}`;

  return (
    <svg
      className="wc-bracket-wires"
      width={width}
      height={GRID_H}
      viewBox={`0 0 ${width} ${GRID_H}`}
      aria-hidden
    >
      <defs>
        <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#00f5a0" stopOpacity="0.35" />
          <stop offset="45%" stopColor="#00f5a0" stopOpacity="1" />
          <stop offset="100%" stopColor="#00e0ff" stopOpacity="0.85" />
        </linearGradient>
        <filter id={glowId} x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="2.5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      {paths.map((d, i) => (
        <path key={`base-${i}`} d={d} className="wc-bracket-wire-base" />
      ))}
      {paths.map((d, i) => (
        <path
          key={`neon-${i}`}
          d={d}
          className="wc-bracket-wire-neon"
          stroke={`url(#${gradId})`}
          filter={`url(#${glowId})`}
        />
      ))}
      {nodes.map((n, i) => (
        <circle key={`node-${i}`} cx={n.cx} cy={n.cy} r="2.5" className="wc-bracket-wire-node" />
      ))}
    </svg>
  );
}

function BracketSemiWire({ side }: { side: "left" | "right" }) {
  const yMid = centerY(3, 0);
  const gradId = `wire-grad-semi-${side}`;
  const glowId = `wire-glow-semi-${side}`;
  const d = side === "left" ? `M 0 ${yMid} H 20` : `M 20 ${yMid} H 0`;

  return (
    <svg
      className={`wc-bracket-semi-wire wc-bracket-semi-wire-${side}`}
      width={20}
      height={GRID_H}
      viewBox={`0 0 20 ${GRID_H}`}
      aria-hidden
    >
      <defs>
        <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#00f5a0" stopOpacity="0.5" />
          <stop offset="100%" stopColor="#fde047" stopOpacity="0.95" />
        </linearGradient>
        <filter id={glowId} x="-60%" y="-20%" width="220%" height="140%">
          <feGaussianBlur stdDeviation="2.5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <path d={d} className="wc-bracket-wire-base" />
      <path
        d={d}
        className="wc-bracket-wire-neon wc-bracket-wire-final"
        stroke={`url(#${gradId})`}
        filter={`url(#${glowId})`}
      />
      <circle
        cx={side === "left" ? 20 : 0}
        cy={yMid}
        r="3"
        className="wc-bracket-wire-node wc-bracket-wire-node-final"
      />
    </svg>
  );
}

function BracketColumn({
  label,
  tier,
  matches,
  phase,
  eliminatedByPhase,
  showLabel = true,
}: {
  label: string;
  tier: number;
  matches: BracketMatchNode[];
  phase: string;
  eliminatedByPhase: Map<string, Set<string>>;
  showLabel?: boolean;
}) {
  const span = 2 ** tier;
  const eliminatedBeforePhase = eliminatedByPhase.get(phase) ?? new Set();

  return (
    <div className="wc-bracket-column">
      {showLabel && <span className="wc-bracket-column-label">{label}</span>}
      <div className="wc-bracket-column-grid">
        {matches.map((match, i) => (
          <div
            key={match.id}
            className="wc-bracket-cell"
            style={{ gridRow: `${i * span + 1} / span ${span}` }}
          >
            <BracketMatchCard match={match} eliminatedBeforePhase={eliminatedBeforePhase} />
          </div>
        ))}
      </div>
    </div>
  );
}

function BracketHalfBoard({
  half,
  side,
  labels,
  eliminatedByPhase,
}: {
  half: BracketTreeHalf;
  side: "left" | "right";
  labels: { r32: string; r16: string; quarter: string; semi: string };
  eliminatedByPhase: Map<string, Set<string>>;
}) {
  const rounds = [
    { key: "r32", phase: "round_of_32", label: labels.r32, matches: half.r32, tier: 0 },
    { key: "r16", phase: "round_16", label: labels.r16, matches: half.r16, tier: 1 },
    { key: "quarter", phase: "quarterfinal", label: labels.quarter, matches: half.quarter, tier: 2 },
    { key: "semi", phase: "semifinal", label: labels.semi, matches: half.semi, tier: 3 },
  ];

  const ordered = side === "left" ? rounds : [...rounds].reverse();
  const wireRounds = ordered.map((r) => ({ tier: r.tier, count: r.matches.length }));
  const stageWidth = ordered.length * COL_W + (ordered.length - 1) * WIRE_W;

  return (
    <div className={`wc-bracket-half-board wc-bracket-half-${side}`}>
      <div className="wc-bracket-half-labels" style={{ width: stageWidth }}>
        {ordered.map((round) => (
          <span key={round.key} className="wc-bracket-column-label">
            {round.label}
          </span>
        ))}
      </div>
      <div className="wc-bracket-half-row">
        {side === "right" && <BracketSemiWire side="right" />}
        <div className="wc-bracket-grid-stage" style={{ width: stageWidth, height: GRID_H }}>
          <BracketWires side={side} rounds={wireRounds} id={side} />
          <div className="wc-bracket-columns">
            {ordered.map((round) => (
              <BracketColumn
                key={round.key}
                label={round.label}
                tier={round.tier}
                matches={round.matches}
                phase={round.phase}
                eliminatedByPhase={eliminatedByPhase}
                showLabel={false}
              />
            ))}
          </div>
        </div>
        {side === "left" && <BracketSemiWire side="left" />}
      </div>
    </div>
  );
}

function BracketFinal({
  match,
  eliminatedBeforePhase,
}: {
  match: BracketMatchNode;
  eliminatedBeforePhase: Set<string>;
}) {
  return (
    <div className="wc-bracket-center">
      <span className="wc-bracket-center-head-label">Final</span>
      <div className="wc-bracket-center-stage" style={{ height: GRID_H }}>
        <div className="wc-bracket-final-inner">
          <div className="wc-bracket-trophy-wrap" aria-hidden>
            <span className="wc-bracket-trophy">🏆</span>
            <span className="wc-bracket-trophy-glow" />
          </div>
          <p className="wc-bracket-center-label">Final</p>
          <div className="wc-bracket-final-card">
            <BracketMatchCard match={match} eliminatedBeforePhase={eliminatedBeforePhase} />
            {match.played && match.winner && (
              <p className="wc-bracket-champion">
                Campeão: <strong>{match.winner}</strong>
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function WcKnockoutBracket({ matches, predictions = [], resultsSyncedAt }: WcKnockoutBracketProps) {
  const columns = useMemo(
    () => buildKnockoutBracket(matches, predictions),
    [matches, predictions],
  );
  const tree = useMemo(() => buildBracketTree(columns), [columns]);
  const stats = useMemo(() => bracketStats(columns), [columns]);
  const eliminatedByPhase = useMemo(() => buildEliminatedByPhase(columns), [columns]);

  if (!tree) {
    return (
      <div className="app-empty-state">
        Nenhum jogo do mata-mata no calendário ainda. Rode{" "}
        <code className="text-neon-green/80">sync-wc-knockout-schedule</code> quando a FIFA publicar os
        confrontos.
      </div>
    );
  }

  return (
    <section className="wc-bracket-shell">
      <header className="wc-bracket-hero">
        <h2 className="wc-bracket-hero-title">Chaveamento</h2>
        <span className="wc-bracket-hero-badge">Copa do Mundo 2026</span>
        <div className="wc-bracket-stats">
          <span>{stats.scheduled} jogos</span>
          <span>{stats.played} encerrados</span>
          <span>{stats.eliminated} eliminados</span>
          {resultsSyncedAt && (
            <span className="wc-bracket-sync">
              sync{" "}
              {new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(
                new Date(resultsSyncedAt),
              )}
            </span>
          )}
        </div>
      </header>

      <div className="wc-bracket-scroll">
        <div className="wc-bracket-pitch">
          <div className="wc-bracket-pitch-grass" aria-hidden />
          <div className="wc-bracket-pitch-markings" aria-hidden>
            <span className="wc-bracket-pitch-line wc-bracket-pitch-line-center" />
            <span className="wc-bracket-pitch-circle" />
          </div>
          <div className="wc-bracket-board">
            <BracketHalfBoard
              half={tree.left}
              side="left"
              labels={tree.labels}
              eliminatedByPhase={eliminatedByPhase}
            />
            {tree.final && (
              <BracketFinal
                match={tree.final}
                eliminatedBeforePhase={eliminatedByPhase.get("final") ?? new Set()}
              />
            )}
            <BracketHalfBoard
              half={tree.right}
              side="right"
              labels={tree.labels}
              eliminatedByPhase={eliminatedByPhase}
            />
          </div>
        </div>
      </div>

      <p className="wc-bracket-legend">
        Eliminados saem da chave · verde = avança · tracejado = aguardando classificados
      </p>
    </section>
  );
}
