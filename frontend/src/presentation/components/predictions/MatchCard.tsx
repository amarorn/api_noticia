import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import type { WcPrediction } from "@/domain/entities";
import { ConfidenceBadge, ConfidenceBar } from "./ConfidenceBadge";
import { ProbabilityBar } from "../charts/ProbabilityCharts";
import {
  formatPercent,
  outcomeColors,
  predictedWinner,
} from "@/presentation/theme";

interface MatchCardProps {
  prediction: WcPrediction;
  index?: number;
  compact?: boolean;
}

export function MatchCard({ prediction, index = 0, compact = false }: MatchCardProps) {
  const winner = predictedWinner(
    prediction.prediction,
    prediction.homeTeam,
    prediction.awayTeam,
  );
  const winnerColor = outcomeColors[prediction.prediction];

  return (
    <motion.article
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.4 }}
      whileHover={{ y: -4 }}
      className="glass-card-hover group flex flex-col p-5"
    >
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wider text-slate-500">Confronto</p>
          <h3 className="mt-1 text-lg font-bold text-white">
            {prediction.homeTeam}{" "}
            <span className="text-slate-500 font-normal">x</span> {prediction.awayTeam}
          </h3>
        </div>
        <ConfidenceBadge
          confidence={prediction.confidence}
          prediction={prediction.prediction}
        />
      </div>

      <div
        className="mb-4 rounded-xl border px-4 py-3"
        style={{
          borderColor: `${winnerColor}40`,
          backgroundColor: `${winnerColor}12`,
        }}
      >
        <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
          Vence o jogo (palpite)
        </p>
        <p className="mt-1 text-xl font-bold" style={{ color: winnerColor }}>
          {winner}
        </p>
        {prediction.prediction !== "X" && (
          <p className="mt-0.5 text-xs text-slate-400">
            {prediction.prediction === "1" ? "Mandante" : "Visitante"} ·{" "}
            {formatPercent(
              prediction.prediction === "1"
                ? prediction.probHome
                : prediction.probAway,
            )}{" "}
            de chance
          </p>
        )}
        {prediction.prediction === "X" && (
          <p className="mt-0.5 text-xs text-slate-400">
            {formatPercent(prediction.probDraw)} de chance de empate
          </p>
        )}
      </div>

      {!compact && (
        <>
          <ProbabilityBar
            probHome={prediction.probHome}
            probDraw={prediction.probDraw}
            probAway={prediction.probAway}
          />

          <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-xl bg-white/5 p-3">
              <p className="text-xs text-slate-500">Placar provável</p>
              <p className="font-semibold text-neon-green">{prediction.poissonScore}</p>
            </div>
            <div className="rounded-xl bg-white/5 p-3">
              <p className="text-xs text-slate-500">Gols esperados</p>
              <p className="font-semibold text-neon-blue">{prediction.expectedGoals}</p>
            </div>
          </div>

          <ConfidenceBar confidence={prediction.confidence} />

          <p className="mt-3 line-clamp-2 text-xs text-slate-500">{prediction.h2hSummary}</p>
        </>
      )}

      <Link
        to={`/match/${encodeURIComponent(prediction.homeTeam)}/${encodeURIComponent(prediction.awayTeam)}`}
        state={{ prediction }}
        className="btn-ghost mt-4 w-full text-center group-hover:border-neon-green/30"
      >
        Ver análise completa
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
  return (
    <motion.article
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className="glass-card p-5"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-white">
            {homeTeam} <span className="text-slate-500">x</span> {awayTeam}
          </h3>
          <p className="mt-1 text-xs text-slate-500">{newsCount} notícias analisadas</p>
        </div>
        <div className="text-right">
          <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-neon-green/10 text-lg font-bold text-neon-green">
            {prediction}
          </span>
          <p className="mt-1 text-xs text-slate-400">{formatPercent(confidence)}</p>
        </div>
      </div>
      <p className="mt-3 text-sm text-slate-400 line-clamp-2">{reason}</p>
    </motion.article>
  );
}
