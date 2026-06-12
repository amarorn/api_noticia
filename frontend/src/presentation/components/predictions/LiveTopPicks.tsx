import { motion } from "framer-motion";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import { formatPercent } from "@/presentation/theme";
import {
  buildBetReason,
  probComparisonLabel,
  rankLabel,
  TIER_CONFIG,
  TIMING_CONFIG,
  type BetTier,
} from "@/presentation/components/predictions/liveBetInsights";

type Opportunity = NonNullable<SuperbetLiveAdvice["strategy"]>["opportunities"][number];

interface LiveTopPicksProps {
  data: SuperbetLiveAdvice;
}

function PickCard({
  opp,
  data,
  isPrimary,
}: {
  opp: Opportunity;
  data: SuperbetLiveAdvice;
  isPrimary: boolean;
}) {
  const tier = (opp.tier as BetTier) || "leve";
  const tierCfg = TIER_CONFIG[tier] ?? TIER_CONFIG.leve;
  const timingCfg = TIMING_CONFIG[opp.timing ?? "monitorar"] ?? TIMING_CONFIG.monitorar;
  const implied = opp.impliedProb ?? 1 / opp.marketOdd;

  const reason = buildBetReason({
    label: opp.label,
    market: opp.market,
    outcome: opp.outcome,
    modelProb: opp.modelProb,
    impliedProb: implied,
    edgePp: opp.edgePp,
    tier,
    rank: opp.rank,
    minute: data.minute,
    currentScore: data.currentScore ?? undefined,
    timing: opp.timing,
    timingReason: opp.timingReason,
    fundamentacao: opp.fundamentacao,
    confidenceLabel: data.confidence?.label,
    confidenceScore: data.confidence?.score,
  });

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`relative overflow-hidden rounded-2xl p-4 ${tierCfg.cardClass}`}
    >
      {isPrimary && (
        <div
          className="pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full bg-neon-green/10 blur-2xl"
          aria-hidden
        />
      )}

      <div className="relative flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`rounded-lg border px-2 py-0.5 font-mono text-[11px] font-bold uppercase tracking-wide ${
              isPrimary
                ? "border-neon-green/50 bg-neon-green/20 text-neon-green"
                : "border-white/15 bg-white/5 text-slate-400"
            }`}
          >
            {rankLabel(opp.rank)}
          </span>
          <span
            className={`rounded-lg border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${tierCfg.badgeClass}`}
          >
            {tierCfg.label}
          </span>
          <span
            className={`rounded-lg border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${timingCfg.badgeClass}`}
          >
            {timingCfg.icon} {timingCfg.label}
          </span>
        </div>
      </div>

      <h3 className="relative mt-3 text-base font-semibold leading-snug text-white">{opp.label}</h3>

      <p className="relative mt-2 font-mono text-sm text-slate-300">
        {probComparisonLabel(opp.modelProb, implied)}
      </p>

      <div className="relative mt-2 flex flex-wrap gap-2 text-xs">
        <span className="rounded-md bg-white/5 px-2 py-1 text-neon-green">
          Edge +{opp.edgePp.toFixed(1)} pp
        </span>
        {data.confidence && (
          <span className="rounded-md bg-white/5 px-2 py-1 text-slate-400">
            Confiança {data.confidence.label} · {formatPercent(data.confidence.score)}
          </span>
        )}
      </div>

      <div
        className={`relative mt-3 rounded-xl border px-3 py-2.5 ${
          isPrimary
            ? "border-neon-green/25 bg-neon-green/[0.07]"
            : "border-white/10 bg-white/[0.04]"
        }`}
      >
        <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
          Fundamentação do modelo
        </p>
        <p className="mt-1 text-xs leading-relaxed text-slate-300">{reason}</p>
      </div>

      {opp.suggestedStakeValue > 0 && opp.timing === "agora" && (
        <p className="relative mt-3 text-[11px] text-slate-500">
          Exposição sugerida (Kelly): R$ {opp.suggestedStakeValue.toFixed(0)} ({opp.suggestedStakePct}%)
        </p>
      )}
    </motion.article>
  );
}

export function LiveTopPicks({ data }: LiveTopPicksProps) {
  const opportunities = data.strategy?.opportunities ?? [];
  const picks = opportunities.filter((o) => o.tier !== "abaixo_limiar").slice(0, 3);

  if (picks.length === 0) {
    if (data.confidence && data.confidence.score < 0.25) {
      return (
        <section className="mb-6 rounded-2xl border border-amber-500/30 bg-amber-500/[0.06] p-4">
          <p className="text-sm font-semibold text-amber-200">Sem recomendação fundamentada</p>
          <p className="mt-1 text-xs leading-relaxed text-slate-400">{data.confidence.reason}</p>
        </section>
      );
    }
    return null;
  }

  return (
    <section className="mb-6" aria-label="Melhores leituras do modelo">
      <div className="mb-3 flex items-center gap-2">
        <span className="flex h-2 w-2 rounded-full bg-neon-green shadow-[0_0_8px_rgba(0,255,136,0.8)]" />
        <h2 className="text-sm font-semibold text-white">Melhor leitura do modelo</h2>
        <span className="text-[11px] text-slate-500">ranqueado por probabilidade real vs mercado</span>
      </div>

      <div
        className={`grid gap-3 ${
          picks.length === 1
            ? "grid-cols-1"
            : picks.length === 2
              ? "grid-cols-1 sm:grid-cols-2"
              : "grid-cols-1 lg:grid-cols-3"
        }`}
      >
        {picks.map((opp, idx) => (
          <PickCard
            key={`${opp.market}-${opp.outcome}`}
            opp={opp}
            data={data}
            isPrimary={idx === 0}
          />
        ))}
      </div>
    </section>
  );
}
