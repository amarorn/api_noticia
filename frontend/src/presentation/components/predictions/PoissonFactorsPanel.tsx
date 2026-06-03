import { motion } from "framer-motion";
import type { GoalModelFactors } from "@/domain/entities";

interface PoissonFactorsPanelProps {
  factors: GoalModelFactors;
  homeTeam: string;
  awayTeam: string;
}

function FactorCell({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2">
      <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-0.5 font-mono text-sm font-semibold ${accent ?? "text-slate-200"}`}>
        {value}
      </p>
    </div>
  );
}

export function PoissonFactorsPanel({ factors, homeTeam, awayTeam }: PoissonFactorsPanelProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card rounded-xl p-5"
    >
      <div className="mb-4 flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-slate-200">Fatores Poisson / Dixon-Coles</h3>
          <p className="text-xs text-slate-500">
            λ (lambda) = gols esperados por time antes da correção ρ
          </p>
        </div>
        <span className="rounded-full border border-neon-green/30 bg-neon-green/10 px-2 py-0.5 font-mono text-xs text-neon-green">
          ρ = {factors.rho.toFixed(3)}
        </span>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 rounded-lg border border-neon-blue/20 bg-neon-blue/5 p-3 sm:grid-cols-4">
        <FactorCell
          label={`λ ${homeTeam}`}
          value={factors.lambdaHome.toFixed(2)}
          accent="text-neon-green"
        />
        <FactorCell
          label={`λ ${awayTeam}`}
          value={factors.lambdaAway.toFixed(2)}
          accent="text-neon-blue"
        />
        <FactorCell label="Média liga" value={factors.leagueAvg.toFixed(2)} />
        <FactorCell label="Mando (+gols)" value={factors.homeAdvantage.toFixed(2)} />
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <FactorCell label={`Ataque ${homeTeam}`} value={factors.homeAttack.toFixed(2)} />
        <FactorCell label={`Ataque ${awayTeam}`} value={factors.awayAttack.toFixed(2)} />
        <FactorCell label={`Defesa ${homeTeam}`} value={factors.homeDefense.toFixed(2)} />
        <FactorCell label={`Defesa ${awayTeam}`} value={factors.awayDefense.toFixed(2)} />
        <FactorCell label="Fator Elo casa" value={factors.eloFactorHome.toFixed(2)} />
        <FactorCell label="Fator Elo fora" value={factors.eloFactorAway.toFixed(2)} />
      </div>

      <p className="mt-3 text-[11px] leading-relaxed text-slate-500">
        λ<sub>casa</sub> = média × ataque<sub>casa</sub> × defesa<sub>fora</sub> + mando, ajustado
        pelo Elo. Dixon-Coles aplica ρ nos placares baixos (0×0, 1×0, 0×1, 1×1).
      </p>
    </motion.div>
  );
}
