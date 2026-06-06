import { motion } from "framer-motion";
import type { WcCornersPrediction } from "@/domain/entities";
import { formatPercent } from "@/presentation/theme";

interface CornersPredictionPanelProps {
  prediction: WcCornersPrediction;
}

const LINE_KEYS = ["over_8.5", "over_9.5", "over_10.5", "over_11.5"] as const;

function dataSourceLabel(source: string): string {
  if (source === "sofascore_corners") return "Histórico Sofascore";
  if (source === "sofascore_corners+goal_proxy") return "Sofascore + proxy de gols";
  if (source === "goal_proxy_default") return "Proxy de gols (sem histórico de cantos)";
  return source;
}

function FactorCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2">
      <p className="text-[11px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-0.5 font-mono text-sm font-semibold text-slate-200">{value}</p>
    </div>
  );
}

export function CornersPredictionPanel({ prediction }: CornersPredictionPanelProps) {
  const { factors, trainingSummary } = prediction;
  const lines = LINE_KEYS.filter((key) => key in prediction.lineProbs);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card space-y-5 rounded-xl p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-200">Escanteios (Poisson)</h3>
          <p className="text-xs text-slate-500">
            λ casa/fora → total esperado e linhas over/under
          </p>
        </div>
        <span className="rounded-full border border-amber-500/25 bg-amber-500/10 px-2.5 py-1 text-[11px] text-amber-300">
          {dataSourceLabel(prediction.dataSource)}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4">
          <p className="text-[11px] uppercase tracking-wider text-slate-500">Esperado</p>
          <p className="mt-1 text-xl font-bold text-amber-300">{prediction.expectedCorners}</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
          <p className="text-[11px] uppercase tracking-wider text-slate-500">Total</p>
          <p className="mt-1 text-xl font-bold text-white">
            {prediction.expectedTotalCorners.toFixed(1)}
          </p>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
          <p className="text-[11px] uppercase tracking-wider text-slate-500">Placar provável</p>
          <p className="mt-1 text-xl font-bold text-neon-green">{prediction.mostLikelyCorners}</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
          <p className="text-[11px] uppercase tracking-wider text-slate-500">Base treino</p>
          <p className="mt-1 text-xl font-bold text-slate-200">{trainingSummary.matches}</p>
          <p className="text-[10px] text-slate-500">jogos no lake</p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 rounded-lg border border-white/5 bg-white/[0.02] p-3 text-center text-xs">
        <div>
          <p className="text-slate-500">Mais cantos — casa</p>
          <p className="mt-1 font-semibold text-neon-green">
            {formatPercent(prediction.probHomeMoreCorners)}
          </p>
        </div>
        <div>
          <p className="text-slate-500">Empate em cantos</p>
          <p className="mt-1 font-semibold text-neon-blue">
            {formatPercent(prediction.probDrawCorners)}
          </p>
        </div>
        <div>
          <p className="text-slate-500">Mais cantos — fora</p>
          <p className="mt-1 font-semibold text-neon-purple">
            {formatPercent(prediction.probAwayMoreCorners)}
          </p>
        </div>
      </div>

      {lines.length > 0 && (
        <div>
          <p className="mb-2 text-[11px] uppercase tracking-wider text-slate-500">
            Linhas de total
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {lines.map((key) => {
              const over = prediction.lineProbs[key] ?? 0;
              const line = key.replace("over_", "");
              const underKey = `under_${line}`;
              const under = prediction.lineProbs[underKey] ?? 1 - over;
              return (
                <div
                  key={key}
                  className="flex items-center justify-between rounded-lg border border-white/5 px-3 py-2 text-sm"
                >
                  <span className="font-mono text-slate-400">Total {line}</span>
                  <span>
                    <span className="text-neon-green">Over {formatPercent(over)}</span>
                    <span className="mx-2 text-slate-600">·</span>
                    <span className="text-slate-400">Under {formatPercent(under)}</span>
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <FactorCell
          label={`λ ${prediction.homeTeam}`}
          value={factors.lambdaHome.toFixed(2)}
        />
        <FactorCell
          label={`λ ${prediction.awayTeam}`}
          value={factors.lambdaAway.toFixed(2)}
        />
        <FactorCell label="Média liga" value={factors.leagueAvg.toFixed(2)} />
        <FactorCell label="Mando (+cantos)" value={factors.homeAdvantage.toFixed(2)} />
        <FactorCell label={`Ataque ${prediction.homeTeam}`} value={factors.homeAttack.toFixed(2)} />
        <FactorCell label={`Ataque ${prediction.awayTeam}`} value={factors.awayAttack.toFixed(2)} />
        <FactorCell label={`Defesa ${prediction.homeTeam}`} value={factors.homeDefense.toFixed(2)} />
        <FactorCell label={`Defesa ${prediction.awayTeam}`} value={factors.awayDefense.toFixed(2)} />
      </div>

      {trainingSummary.matches === 0 && (
        <p className="text-xs text-amber-400/90">
          Sem jogos com cantos no lake. Rode{" "}
          <code className="rounded bg-white/5 px-1">ingest-sofascore --stats-only</code> em
          partidas disputadas para calibrar o modelo.
        </p>
      )}
      {factors.blendWithGoalProxy > 0 && (
        <p className="text-xs text-slate-500">
          Blend com proxy de gols: {formatPercent(factors.blendWithGoalProxy)} (pouco histórico
          Sofascore para estes times).
        </p>
      )}
    </motion.div>
  );
}
