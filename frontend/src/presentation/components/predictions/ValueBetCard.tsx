import type { ValueMatch } from "@/domain/entities";
import { motion } from "framer-motion";
import { formatPercent, outcomeColors } from "@/presentation/theme";

interface ValueBetCardProps {
  match: ValueMatch;
  index?: number;
}

export function ValueBetCard({ match, index = 0 }: ValueBetCardProps) {
  const best = match.best;
  const hasEdge = best && best.expectedValue > 0;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: index * 0.05 }}
      className={`glass-card p-5 ${hasEdge ? "border-neon-green/30 shadow-neon" : ""}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wider text-slate-500">Value Bet</p>
          <h3 className="font-bold text-white">
            {match.homeTeam} x {match.awayTeam}
          </h3>
        </div>
        {hasEdge && best && (
          <div className="rounded-xl bg-neon-green/10 px-3 py-2 text-right">
            <p className="text-xs text-neon-green">EV+</p>
            <p className="text-lg font-bold text-neon-green">
              +{formatPercent(best.expectedValue)}
            </p>
          </div>
        )}
      </div>

      <div className="mt-4 space-y-2">
        {match.outcomes.map((o) => (
          <div
            key={o.outcome}
            className="flex items-center justify-between rounded-lg bg-white/5 px-3 py-2 text-sm"
          >
            <span
              className="font-bold"
              style={{ color: outcomeColors[o.outcome] }}
            >
              {o.outcome}
            </span>
            <span className="text-slate-400">Odd {o.odd.toFixed(2)}</span>
            <span className={o.expectedValue > 0 ? "text-neon-green" : "text-slate-500"}>
              EV {o.expectedValue > 0 ? "+" : ""}
              {formatPercent(o.expectedValue)}
            </span>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

interface ValueBetsSectionProps {
  edges: ValueMatch[];
  matchedGames: number;
  totalGames: number;
  loading?: boolean;
  error?: string | null;
}

export function ValueBetsSection({
  edges,
  matchedGames,
  totalGames,
  loading,
  error,
}: ValueBetsSectionProps) {
  if (loading) {
    return (
      <section className="space-y-4">
        <h2 className="text-xl font-bold gradient-text">Value Bets (EV)</h2>
        <p className="text-sm text-slate-400">Carregando odds ao vivo...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="glass-card border-amber-500/20 p-6">
        <h2 className="text-lg font-bold text-amber-400">Value Bets indisponível</h2>
        <p className="mt-2 text-sm text-slate-400">{error}</p>
        <p className="mt-1 text-xs text-slate-500">
          Configure ODDS_API_KEY no backend para habilitar análise de EV.
        </p>
      </section>
    );
  }

  const positiveEdges = edges.filter((e) => e.best && e.best.expectedValue > 0);

  return (
    <section className="space-y-3">
      {/* Cabeçalho compacto */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="h-5 w-5 rounded-md bg-neon-yellow/10 border border-neon-yellow/20 flex items-center justify-center">
            <span className="text-[10px] font-bold text-neon-yellow">$</span>
          </span>
          <div>
            <h2 className="text-sm font-bold text-white">Value Bets</h2>
            <p className="font-mono text-[10px] text-slate-500">
              {matchedGames}/{totalGames} jogos · {positiveEdges.length} edge positivo
            </p>
          </div>
        </div>
        {positiveEdges.length > 0 && (
          <span className="badge-premium border-neon-yellow/20 text-neon-yellow">
            +{positiveEdges.length} EV
          </span>
        )}
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {edges.map((match, i) => (
          <ValueBetCard key={`${match.homeTeam}-${match.awayTeam}`} match={match} index={i} />
        ))}
      </div>
    </section>
  );
}
