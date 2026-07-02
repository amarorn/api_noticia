import type { SuperbetLiveAdvice } from "@/domain/entities";

const POSTURE_STYLES: Record<string, string> = {
  atacar: "border-neon-green/40 bg-neon-green/15 text-neon-green",
  neutro: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  defensivo: "border-red-500/40 bg-red-500/15 text-red-300",
};

const POSTURE_LABELS: Record<string, string> = {
  atacar: "Atacar com limite",
  neutro: "Neutro — seletivo",
  defensivo: "Defensivo — proteger",
};

const TIER_STYLES: Record<string, string> = {
  forte: "text-neon-green",
  moderada: "text-neon-blue",
  leve: "text-slate-300",
};

const SHIELD_STYLES: Record<string, string> = {
  alta: "border-red-500/35 bg-red-500/10",
  media: "border-amber-500/30 bg-amber-500/10",
  baixa: "border-white/15 bg-white/5",
};

interface BetStrategyPanelProps {
  strategy: SuperbetLiveAdvice["strategy"];
}

export function BetStrategyPanel({ strategy }: BetStrategyPanelProps) {
  if (!strategy) return null;

  return (
    <section className="rounded-2xl border border-neon-green/20 bg-neon-green/[0.04] p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Estratégia de blindagem</h2>
          <p className="text-xs text-slate-500">
            Oportunidades ranqueadas + regras para limitar exposição
          </p>
        </div>
        <span
          className={`rounded-lg border px-3 py-1.5 text-xs font-bold uppercase tracking-wide ${
            POSTURE_STYLES[strategy.posture] ?? POSTURE_STYLES.neutro
          }`}
        >
          {POSTURE_LABELS[strategy.posture] ?? strategy.posture}
        </span>
      </div>

      <div className="mb-4 grid gap-2 sm:grid-cols-3">
        <Metric
          label="Exposição máx."
          value={`${strategy.maxNewExposurePct.toFixed(1)}%`}
          sub={`R$ ${strategy.maxNewExposureValue.toFixed(0)}`}
        />
        <Metric
          label="Oportunidades"
          value={String(strategy.opportunityCount)}
          sub={`${strategy.strongOpportunityCount} fortes/moderadas`}
        />
        <Metric label="Blindagens" value={String(strategy.shields.length)} sub="alertas ativos" />
      </div>

      {strategy.shields.length > 0 && (
        <div className="mb-4 space-y-2">
          <p className="text-[11px] uppercase tracking-wider text-slate-500">Proteções</p>
          {strategy.shields.map((shield, idx) => {
            const isHandicapTrap =
              shield.priority === "alta" &&
              shield.action === "evitar" &&
              shield.title.toLowerCase().includes("handicap");
            return (
            <div
              key={`${shield.action}-${idx}`}
              className={`rounded-xl border px-3 py-2.5 ${
                isHandicapTrap
                  ? "border-red-500/45 bg-red-500/12"
                  : SHIELD_STYLES[shield.priority] ?? SHIELD_STYLES.baixa
              }`}
            >
              <p className={`text-sm font-medium ${isHandicapTrap ? "text-red-100" : "text-white"}`}>
                {shield.title}
              </p>
              <p className="mt-1 text-xs text-slate-400">{shield.reason}</p>
            </div>
            );
          })}
        </div>
      )}

      {strategy.opportunities.length > 0 ? (
        <div className="mb-4 overflow-x-auto">
          <p className="mb-2 text-[11px] uppercase tracking-wider text-slate-500">
            Oportunidades ranqueadas
          </p>
          <table className="min-w-full text-xs">
            <thead>
              <tr className="border-b border-white/8 text-left text-slate-500">
                <th className="pb-2 pr-3">#</th>
                <th className="pb-2 pr-3">Mercado</th>
                <th className="pb-2 pr-3">EV</th>
                <th className="pb-2 pr-3">Stake</th>
                <th className="pb-2">Tier</th>
              </tr>
            </thead>
            <tbody>
              {strategy.opportunities.map((op) => (
                <tr key={`${op.market}-${op.outcome}`} className="border-b border-white/5">
                  <td className="py-2 pr-3 font-mono text-slate-400">{op.rank}</td>
                  <td className="py-2 pr-3">
                    <span className="text-white">{op.label}</span>
                    <span className="ml-1 text-slate-500">@{op.marketOdd.toFixed(2)}</span>
                  </td>
                  <td className="py-2 pr-3 font-mono text-neon-green">
                    +{(op.expectedValue * 100).toFixed(1)}%
                  </td>
                  <td className="py-2 pr-3 text-slate-300">
                    R$ {op.suggestedStakeValue.toFixed(0)} ({op.suggestedStakePct}%)
                  </td>
                  <td className={`py-2 font-semibold uppercase ${TIER_STYLES[op.tier] ?? ""}`}>
                    {op.tier}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mb-4 text-sm text-slate-500">
          Nenhuma oportunidade com edge suficiente — aguardar protege a banca.
        </p>
      )}

      <HedgePairStrategiesSection hedgePairs={strategy.hedgePairStrategies} />

      <div className="rounded-xl border border-white/8 bg-white/[0.02] px-3 py-3">
        <p className="mb-2 text-[11px] uppercase tracking-wider text-slate-500">
          Regras do plano
        </p>
        <ul className="space-y-1.5">
          {strategy.rules.map((rule) => (
            <li key={rule} className="flex gap-2 text-xs text-slate-300">
              <span className="text-neon-green" aria-hidden>
                •
              </span>
              {rule}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function HedgePairStrategiesSection({
  hedgePairs,
}: {
  hedgePairs: NonNullable<SuperbetLiveAdvice["strategy"]>["hedgePairStrategies"];
}) {
  if (!hedgePairs?.available || hedgePairs.strategies.length === 0) return null;

  return (
    <div className="mb-4 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-[11px] uppercase tracking-wider text-slate-500">
          Estratégias pareadas (blindagem)
        </p>
        {hedgePairs.enabled && (
          <span className="rounded-full border border-violet-400/25 bg-violet-400/10 px-2 py-0.5 text-[9px] font-bold uppercase text-violet-200">
            GPT
          </span>
        )}
      </div>
      {hedgePairs.error && (
        <p className="text-[10px] text-slate-500">{hedgePairs.error}</p>
      )}
      <div className="grid gap-3 lg:grid-cols-2">
        {hedgePairs.strategies.map((pair) => (
          <div
            key={pair.id}
            className="rounded-xl border border-cyan-400/15 bg-cyan-400/[0.04] p-3"
          >
            <div className="mb-2 flex items-start justify-between gap-2">
              <h3 className="text-sm font-semibold text-white">{pair.titulo}</h3>
              <span className="shrink-0 rounded-md border border-neon-green/20 bg-neon-green/10 px-2 py-0.5 text-[10px] font-bold text-neon-green">
                {(pair.coverage.probAtLeastOne * 100).toFixed(0)}% cobertura
              </span>
            </div>
            {pair.resumo && (
              <p className="mb-3 text-xs leading-relaxed text-slate-300">{pair.resumo}</p>
            )}
            <div className="space-y-2">
              {[pair.legA, pair.legB].map((leg, idx) => (
                <div
                  key={`${pair.id}-${leg.market}-${idx}`}
                  className="rounded-lg border border-white/[0.06] bg-black/25 px-3 py-2"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-xs font-semibold text-white">
                        Perna {idx + 1}: {leg.label}
                      </p>
                      <p className="mt-0.5 text-[10px] text-slate-500">
                        Prob modelo {(leg.modelProb * 100).toFixed(0)}%
                        {leg.expectedValue !== 0 && (
                          <>
                            {" "}
                            · EV {(leg.expectedValue * 100).toFixed(1)}%
                          </>
                        )}
                      </p>
                    </div>
                    <span className="shrink-0 font-mono text-xs font-bold text-slate-200">
                      @{leg.marketOdd.toFixed(2)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 space-y-1 text-[10px] text-slate-400">
              {pair.cenarioChave && (
                <p>
                  <span className="text-cyan-300">Chave:</span> {pair.cenarioChave}
                </p>
              )}
              {pair.scenarioA && <p>{pair.scenarioA}</p>}
              {pair.scenarioB && <p>{pair.scenarioB}</p>}
              {pair.scenarioBoth && (
                <p className="text-neon-green/80">{pair.scenarioBoth}</p>
              )}
            </div>
            <div className="mt-3 flex flex-wrap gap-3 text-[10px] text-slate-500">
              <span>Split: {pair.stakeSplit}</span>
              {pair.stakeHintPct > 0 && (
                <span>
                  Stake total sugerida: {pair.stakeHintPct.toFixed(1)}% (R${" "}
                  {pair.stakeHintValue.toFixed(0)})
                </span>
              )}
              {pair.coverage.probBothLose > 0 && (
                <span className="text-amber-300/90">
                  Risco dupla perda: {(pair.coverage.probBothLose * 100).toFixed(0)}%
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
      <p className="text-[10px] leading-relaxed text-slate-600">
        Pares complementares — se uma perna falhar, a outra tende a compensar. Odds e probabilidades
        vêm do motor in-play; narrativa enriquecida por GPT quando ativo.
      </p>
    </div>
  );
}

function Metric({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2">
      <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="font-mono text-sm font-semibold text-white">{value}</p>
      <p className="text-[10px] text-slate-500">{sub}</p>
    </div>
  );
}
