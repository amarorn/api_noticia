import type { OperationalDecision } from "@/presentation/components/live-operational/liveOperationalUtils";
import { formatMoney, formatOdd, formatPercent } from "@/presentation/components/live-operational/liveOperationalUtils";
import { RadialGaugeV2, StatusPillV2, type ToneV2 } from "./live-ui-v2";

const STATUS_STYLE: Record<OperationalDecision["status"], { panel: string; tone: ToneV2; short: string }> = {
  entrar: { panel: "border-emerald-400/30 bg-emerald-400/[0.08]", tone: "green", short: "ENTRAR" },
  aguardar: { panel: "border-amber-400/30 bg-amber-400/[0.08]", tone: "amber", short: "AGUARDAR" },
  evitar: { panel: "border-red-400/30 bg-red-400/[0.08]", tone: "red", short: "EVITAR" },
  suspenso: { panel: "border-slate-400/30 bg-slate-400/[0.06]", tone: "slate", short: "REVISAR" },
  desatualizado: { panel: "border-cyan-400/30 bg-cyan-400/[0.06]", tone: "cyan", short: "REVISAR" },
};

function orNd(value: string) {
  return value === "-" ? "N/D" : value;
}

export function LiveDecisionCardV2({ decision, bankroll }: { decision: OperationalDecision; bankroll: number }) {
  const style = STATUS_STYLE[decision.status];
  const pick = decision.pick;
  const unit = bankroll * 0.01;
  const stakeUnits = pick ? pick.suggestedStakeValue / Math.max(unit, 1) : 0;
  const confidencePct = pick?.confidenceScore != null ? Math.round(pick.confidenceScore * 100) : 0;

  return (
    <section className={`panel-v2 ${style.panel} p-5 sm:p-6`}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <StatusPillV2 label={style.short} tone={style.tone} />
            <span className="text-xs font-semibold text-slate-400">{decision.title}</span>
          </div>
          <h1 className="mt-3 text-xl font-black text-white sm:text-2xl">{pick?.label ?? "Sem mercado recomendado agora"}</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-300">{decision.reason}</p>
        </div>

        <div className="flex shrink-0 items-center gap-3 self-start rounded-2xl border border-white/8 bg-black/25 px-4 py-3">
          <RadialGaugeV2 pct={confidencePct} label={`${confidencePct}%`} tone={style.tone} />
          <div>
            <p className="text-[11px] uppercase tracking-wide text-slate-500">Confiança</p>
            <p className="text-xs font-semibold text-slate-300">{pick?.confidenceLabel ?? "sem sinal"}</p>
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Metric label="Odd atual" value={orNd(formatOdd(pick?.marketOdd))} />
        <Metric label="Odd justa / mínima" value={orNd(formatOdd(decision.fairOdd))} />
        <Metric label="EV" value={orNd(formatPercent(pick?.expectedValue ?? null))} accent="text-neon-green" />
        <Metric
          label="Stake sugerida"
          value={pick ? `${stakeUnits.toFixed(2)}u` : "N/D"}
          sub={pick ? formatMoney(pick.suggestedStakeValue) : undefined}
        />
        <Metric
          label="Dados"
          value={decision.isFresh ? "Frescos" : "Revisar"}
          sub={decision.dataAgeSec != null ? `${decision.dataAgeSec}s atrás` : "sem captura"}
        />
      </div>
    </section>
  );
}

function Metric({ label, value, sub, accent = "text-white" }: { label: string; value: string; sub?: string; accent?: string }) {
  return (
    <div className="rounded-xl border border-white/8 bg-black/20 px-3 py-2.5 backdrop-blur-sm">
      <p className="text-[11px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 font-mono text-lg font-black ${accent}`}>{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-400">{sub}</p>}
    </div>
  );
}
