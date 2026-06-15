import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import type { WcPrediction } from "@/domain/entities";
import { springSnappy } from "@/presentation/theme/motion";
import { ConfidenceBadge, ConfidenceBar } from "./ConfidenceBadge";
import { ProbabilityBar } from "../charts/ProbabilityCharts";
import {
  formatPercent,
  outcomeColors,
  predictedWinner,
} from "@/presentation/theme";
import { IconChevronRight, IconWallet } from "@/presentation/components/ui/Icons";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";
import { buildMatchTicketsPath } from "@/presentation/utils/matchSuperbetEvent";

interface MatchCardProps {
  prediction: WcPrediction;
  index?: number;
  compact?: boolean;
  group?: string | null;
  selected?: boolean;
  onSelect?: () => void;
}

function TeamAvatar({ name }: { name: string }) {
  return <TeamFlag team={name} size={40} rounded="md" />;
}

function UncertaintyBadge({ level }: { level: "alta" | "media" | "baixa" }) {
  const styles = {
    alta: { bg: "bg-amber-500/15", text: "text-amber-300", label: "Incerteza alta" },
    media: { bg: "bg-sky-500/15", text: "text-sky-300", label: "Incerteza média" },
    baixa: { bg: "bg-neon-green/10", text: "text-neon-green", label: "Incerteza baixa" },
  } as const;
  const s = styles[level];
  return (
    <span className={`rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${s.bg} ${s.text}`}>
      {s.label}
    </span>
  );
}

function ResultBadge({
  actualScore,
  predictionHit,
}: {
  actualScore: string;
  predictionHit: boolean | null;
}) {
  const hit = predictionHit === true;
  const miss = predictionHit === false;
  return (
    <div className="flex items-center gap-2">
      <span className="rounded-md bg-white/8 px-2 py-0.5 text-[10px] font-bold text-slate-300">
        Real: {actualScore.replace("x", "×")}
      </span>
      {hit && <span className="text-[10px] font-bold text-neon-green">✓ acertou</span>}
      {miss && <span className="text-[10px] font-bold text-red-400">✗ errou</span>}
    </div>
  );
}

export function MatchCard({
  prediction,
  index = 0,
  compact = false,
  group,
  selected = false,
  onSelect,
}: MatchCardProps) {
  const winner = predictedWinner(
    prediction.prediction,
    prediction.homeTeam,
    prediction.awayTeam,
  );
  const winnerColor = outcomeColors[prediction.prediction];
  const homeColor = outcomeColors["1"];
  const awayColor = outcomeColors["2"];
  const showDrawNote =
    prediction.pickReason === "empate_equilibrio" &&
    prediction.maxProbOutcome &&
    prediction.maxProbOutcome !== "X";

  return (
    <motion.article
      initial={{ opacity: 0, y: 20, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: index * 0.05, ...springSnappy }}
      whileHover={{ y: -6, transition: { duration: 0.2 } }}
      className={`glass-card-hover group relative flex flex-col overflow-hidden ${
        selected ? "ring-2 ring-violet-400/60 ring-offset-2 ring-offset-[#0a0f1a]" : ""
      }`}
      onClick={onSelect}
      role={onSelect ? "button" : undefined}
      tabIndex={onSelect ? 0 : undefined}
      onKeyDown={
        onSelect
          ? (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelect();
              }
            }
          : undefined
      }
    >
      {/* Textura de fundo */}
      <img
        src="/images/card-texture.png"
        alt=""
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 h-full w-full object-cover opacity-[0.18]"
        draggable={false}
      />

      {/* Header: resultado previsto */}
      <div
        className="relative flex items-center justify-between rounded-t-2xl px-4 py-3 transition-colors duration-300"
        style={{ backgroundColor: `${winnerColor}10`, borderBottom: `1px solid ${winnerColor}20` }}
      >
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Palpite</span>
          {group && (
            <span className="rounded-md bg-neon-green/10 px-1.5 py-0.5 text-[10px] font-black text-neon-green">
              {group}
            </span>
          )}
          {prediction.uncertainty && (
            <UncertaintyBadge level={prediction.uncertainty} />
          )}
          <span className="text-sm font-bold" style={{ color: winnerColor }}>{winner}</span>
        </div>
        <ConfidenceBadge
          confidence={prediction.confidence}
          prediction={prediction.prediction}
          label="Prob. palpite"
        />
      </div>

      {prediction.actualScore && (
        <div className="relative border-b border-white/5 px-4 py-2">
          <ResultBadge
            actualScore={prediction.actualScore}
            predictionHit={prediction.predictionHit ?? null}
          />
        </div>
      )}

      {showDrawNote && (
        <p className="relative px-4 pt-2 text-[11px] leading-snug text-slate-400">
          Empate escolhido por equilíbrio (P({prediction.maxProbOutcome})=
          {formatPercent(prediction.maxProb ?? 0)} vs P(X)={formatPercent(prediction.confidence)}).
        </p>
      )}

      {/* Times */}
      <div className="relative flex items-center justify-between gap-2 px-4 py-4">
        <div className="flex min-w-0 flex-1 items-center gap-2.5">
          <TeamAvatar name={prediction.homeTeam} />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-white">{prediction.homeTeam}</p>
            <p className="text-[11px] text-slate-500">Mandante</p>
          </div>
        </div>

        <div className="flex shrink-0 flex-col items-center gap-1.5">
          <span className="text-[11px] font-black text-slate-500">VS</span>
          {/* Mini probability sparkline */}
          <div className="flex h-1 w-10 overflow-hidden rounded-full">
            <div style={{ width: `${prediction.probHome * 100}%`, backgroundColor: homeColor }} />
            <div style={{ width: `${prediction.probDraw * 100}%`, backgroundColor: outcomeColors.X }} />
            <div style={{ width: `${prediction.probAway * 100}%`, backgroundColor: awayColor }} />
          </div>
          {prediction.prediction !== "X" && (
            <div
              className="h-0.5 w-6 rounded-full"
              style={{
                background: `linear-gradient(90deg, ${homeColor}80, ${awayColor}80)`,
              }}
            />
          )}
        </div>

        <div className="flex min-w-0 flex-1 items-center justify-end gap-2.5">
          <div className="min-w-0 text-right">
            <p className="truncate text-sm font-semibold text-white">{prediction.awayTeam}</p>
            <p className="text-[11px] text-slate-500">Visitante</p>
          </div>
          <TeamAvatar name={prediction.awayTeam} />
        </div>
      </div>

      {/* Stats + barra */}
      {!compact && (
        <div className="relative space-y-3 px-4 pb-4">
          <ProbabilityBar
            probHome={prediction.probHome}
            probDraw={prediction.probDraw}
            probAway={prediction.probAway}
          />

          <div className="grid grid-cols-2 gap-2">
            <div className="stat-pill">
              <p className="text-[11px] text-slate-500">Placar provável</p>
              <p className="mt-0.5 text-sm font-bold text-neon-green">{prediction.poissonScore}</p>
            </div>
            <div className="stat-pill">
              <p className="text-[11px] text-slate-500">Gols esperados</p>
              <p className="mt-0.5 text-sm font-bold text-neon-blue">{prediction.expectedGoals}</p>
            </div>
          </div>

          <ConfidenceBar confidence={prediction.confidence} label="Probabilidade do palpite" />

          <p className="line-clamp-1 text-xs text-slate-500">{prediction.h2hSummary}</p>
        </div>
      )}

      <div className="relative mx-4 mb-4 flex flex-col gap-2">
        <Link
          to={buildMatchTicketsPath(prediction.homeTeam, prediction.awayTeam)}
          onClick={(event) => event.stopPropagation()}
          className="flex items-center justify-center gap-1.5 rounded-xl border border-violet-400/35 bg-violet-500/15 py-2.5 text-sm font-semibold text-violet-100 transition-all hover:border-violet-300/50 hover:bg-violet-500/25"
        >
          <IconWallet className="h-4 w-4" />
          Bilhetes R$ 5 → R$ 500+
          <IconChevronRight className="h-3.5 w-3.5" />
        </Link>
        <Link
          to={`/match/${encodeURIComponent(prediction.homeTeam)}/${encodeURIComponent(prediction.awayTeam)}`}
          state={{ prediction }}
          onClick={(event) => event.stopPropagation()}
          className="flex items-center justify-center gap-1.5 rounded-xl border border-white/8 bg-white/4 py-2.5 text-sm font-medium text-slate-400 transition-all group-hover:border-neon-green/25 group-hover:bg-neon-green/4 group-hover:text-neon-green"
        >
          Ver análise completa
          <IconChevronRight className="h-3.5 w-3.5" />
        </Link>
        <Link
          to={`/match/${encodeURIComponent(prediction.homeTeam)}/${encodeURIComponent(prediction.awayTeam)}?sofascore=1`}
          onClick={(event) => event.stopPropagation()}
          className="flex items-center justify-center gap-1.5 rounded-xl border border-white/8 bg-white/4 py-2 text-xs font-medium text-slate-500 transition-all hover:border-neon-blue/25 hover:bg-neon-blue/4 hover:text-neon-blue"
        >
          Palpite com escalação Sofascore
          <IconChevronRight className="h-3 w-3" />
        </Link>
      </div>
    </motion.article>
  );
}

interface BrasileiraoCardProps {
  homeTeam: string;
  awayTeam: string;
  prediction: string;
  confidence: number;
  reason: string;
  newsCount: number;
  index?: number;
}

export function BrasileiraoCard({
  homeTeam,
  awayTeam,
  prediction,
  confidence,
  reason,
  newsCount,
  index = 0,
}: BrasileiraoCardProps) {
  const predColor =
    prediction === "1"
      ? outcomeColors["1"]
      : prediction === "2"
        ? outcomeColors["2"]
        : outcomeColors["X"];

  return (
    <motion.article
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className="glass-card-hover flex flex-col gap-3 p-4"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate font-bold text-white">
            {homeTeam} <span className="font-normal text-slate-500">x</span> {awayTeam}
          </h3>
          <p className="mt-0.5 text-[11px] text-slate-500">{newsCount} notícias analisadas</p>
        </div>
        <div
          className="flex h-11 w-11 shrink-0 flex-col items-center justify-center rounded-xl text-xs"
          style={{ backgroundColor: `${predColor}18`, border: `1px solid ${predColor}30` }}
        >
          <span className="text-lg font-black" style={{ color: predColor }}>{prediction}</span>
          <span className="text-[10px] font-semibold text-slate-500">{formatPercent(confidence)}</span>
        </div>
      </div>
      <p className="line-clamp-2 text-xs leading-relaxed text-slate-400">{reason}</p>
    </motion.article>
  );
}
