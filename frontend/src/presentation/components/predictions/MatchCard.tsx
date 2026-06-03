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
import { IconChevronRight } from "@/presentation/components/ui/Icons";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";

interface MatchCardProps {
  prediction: WcPrediction;
  index?: number;
  compact?: boolean;
  group?: string | null;
}

function TeamAvatar({ name }: { name: string }) {
  return <TeamFlag team={name} size={40} rounded="md" />;
}

export function MatchCard({ prediction, index = 0, compact = false, group }: MatchCardProps) {
  const winner = predictedWinner(
    prediction.prediction,
    prediction.homeTeam,
    prediction.awayTeam,
  );
  const winnerColor = outcomeColors[prediction.prediction];
  const homeColor = outcomeColors["1"];
  const awayColor = outcomeColors["2"];

  return (
    <motion.article
      initial={{ opacity: 0, y: 20, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: index * 0.05, ...springSnappy }}
      whileHover={{ y: -6, transition: { duration: 0.2 } }}
      className="glass-card-hover group relative flex flex-col overflow-hidden"
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
          <span className="text-[9px] font-bold uppercase tracking-widest text-slate-500">Palpite</span>
          {group && (
            <span className="rounded-md bg-neon-green/10 px-1.5 py-0.5 text-[9px] font-black text-neon-green">
              {group}
            </span>
          )}
          <span className="text-sm font-bold" style={{ color: winnerColor }}>{winner}</span>
        </div>
        <ConfidenceBadge
          confidence={prediction.confidence}
          prediction={prediction.prediction}
        />
      </div>

      {/* Times */}
      <div className="relative flex items-center justify-between gap-2 px-4 py-4">
        <div className="flex min-w-0 flex-1 items-center gap-2.5">
          <TeamAvatar name={prediction.homeTeam} />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-white">{prediction.homeTeam}</p>
            <p className="text-[10px] text-slate-500">Mandante</p>
          </div>
        </div>

        <div className="flex shrink-0 flex-col items-center gap-0.5">
          <span className="text-[10px] font-black text-slate-600">VS</span>
          {prediction.prediction !== "X" && (
            <div
              className="h-1 w-6 rounded-full"
              style={{
                background: `linear-gradient(90deg, ${homeColor}80, ${awayColor}80)`,
              }}
            />
          )}
        </div>

        <div className="flex min-w-0 flex-1 items-center justify-end gap-2.5">
          <div className="min-w-0 text-right">
            <p className="truncate text-sm font-semibold text-white">{prediction.awayTeam}</p>
            <p className="text-[10px] text-slate-500">Visitante</p>
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
              <p className="text-[10px] text-slate-500">Placar provável</p>
              <p className="mt-0.5 text-sm font-bold text-neon-green">{prediction.poissonScore}</p>
            </div>
            <div className="stat-pill">
              <p className="text-[10px] text-slate-500">Gols esperados</p>
              <p className="mt-0.5 text-sm font-bold text-neon-blue">{prediction.expectedGoals}</p>
            </div>
          </div>

          <ConfidenceBar confidence={prediction.confidence} />

          <p className="line-clamp-1 text-[11px] text-slate-600">{prediction.h2hSummary}</p>
        </div>
      )}

      <Link
        to={`/match/${encodeURIComponent(prediction.homeTeam)}/${encodeURIComponent(prediction.awayTeam)}`}
        state={{ prediction }}
        className="relative mx-4 mb-4 flex items-center justify-center gap-1.5 rounded-xl border border-white/8 bg-white/4 py-2.5 text-sm font-medium text-slate-400 transition-all group-hover:border-neon-green/25 group-hover:bg-neon-green/4 group-hover:text-neon-green"
      >
        Ver análise completa
        <IconChevronRight className="h-3.5 w-3.5" />
      </Link>
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
            {homeTeam} <span className="font-normal text-slate-600">x</span> {awayTeam}
          </h3>
          <p className="mt-0.5 text-[10px] text-slate-500">{newsCount} notícias analisadas</p>
        </div>
        <div
          className="flex h-11 w-11 shrink-0 flex-col items-center justify-center rounded-xl text-xs"
          style={{ backgroundColor: `${predColor}18`, border: `1px solid ${predColor}30` }}
        >
          <span className="text-lg font-black" style={{ color: predColor }}>{prediction}</span>
          <span className="text-[8px] font-semibold text-slate-500">{formatPercent(confidence)}</span>
        </div>
      </div>
      <p className="line-clamp-2 text-xs leading-relaxed text-slate-400">{reason}</p>
    </motion.article>
  );
}
