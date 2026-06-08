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
          {strategy.shields.map((shield, idx) => (
            <div
              key={`${shield.action}-${idx}`}
              className={`rounded-xl border px-3 py-2.5 ${SHIELD_STYLES[shield.priority] ?? SHIELD_STYLES.baixa}`}
            >
              <p className="text-sm font-medium text-white">{shield.title}</p>
              <p className="mt-1 text-xs text-slate-400">{shield.reason}</p>
            </div>
          ))}
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

function Metric({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2">
      <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="font-mono text-sm font-semibold text-white">{value}</p>
      <p className="text-[10px] text-slate-500">{sub}</p>
    </div>
  );
}
