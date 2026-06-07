import { motion } from "framer-motion";
import type { MonteCarloBreakdown } from "@/domain/entities";
import { formatPercent } from "@/presentation/theme";

interface MonteCarloPanelProps {
  simulation: MonteCarloBreakdown;
}

function MarketCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2">
      <p className="text-[11px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-0.5 font-mono text-sm font-semibold text-slate-200">{value}</p>
    </div>
  );
}

export function MonteCarloPanel({ simulation }: MonteCarloPanelProps) {
  const topScores = Object.entries(simulation.topScores).slice(0, 6);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card rounded-xl p-5"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-slate-200">Simulação Monte Carlo</h3>
          <p className="text-xs text-slate-500">
            {simulation.nSimulations.toLocaleString("pt-BR")} jogos simulados · Poisson + ρ Dixon-Coles
          </p>
        </div>
        <span className="rounded-full border border-neon-purple/30 bg-neon-purple/10 px-2 py-0.5 font-mono text-xs text-neon-purple">
          ρ = {simulation.rhoUsed.toFixed(3)}
        </span>
      </div>

      <div className="mb-4 grid grid-cols-3 gap-2">
        <MarketCell label="Casa" value={formatPercent(simulation.probHome)} />
        <MarketCell label="Empate" value={formatPercent(simulation.probDraw)} />
        <MarketCell label="Fora" value={formatPercent(simulation.probAway)} />
      </div>

      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <MarketCell
          label="Gols esp."
          value={`${simulation.expectedGoalsHome.toFixed(2)} x ${simulation.expectedGoalsAway.toFixed(2)}`}
        />
        <MarketCell label="Over 2.5" value={formatPercent(simulation.over25)} />
        <MarketCell label="Under 2.5" value={formatPercent(simulation.under25)} />
        <MarketCell label="Ambos marcam" value={formatPercent(simulation.bothTeamsScore)} />
      </div>

      {topScores.length > 0 && (
        <div>
          <p className="mb-2 text-[11px] uppercase tracking-wider text-slate-500">Placares mais prováveis</p>
          <div className="flex flex-wrap gap-2">
            {topScores.map(([score, prob]) => (
              <span
                key={score}
                className="rounded-lg border border-neon-green/20 bg-neon-green/5 px-2.5 py-1 font-mono text-xs text-neon-green"
              >
                {score} · {formatPercent(prob)}
              </span>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}
