import type { DefensiveComboView } from "@/presentation/utils/defensiveComboTicket";

const STATUS_STYLES: Record<string, string> = {
  won: "border-neon-green/40 bg-neon-green/10 text-neon-green",
  ok: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
  at_risk: "border-amber-500/40 bg-amber-500/10 text-amber-200",
  lost: "border-red-500/40 bg-red-500/10 text-red-200",
  pending: "border-white/15 bg-white/[0.03] text-slate-400",
};

interface DefensiveComboBannerProps {
  view: DefensiveComboView;
  homeTeam: string;
  awayTeam: string;
}

export function DefensiveComboBanner({ view, homeTeam, awayTeam }: DefensiveComboBannerProps) {
  const firstRisk = view.legRisks[0];

  return (
    <div className="mb-4 space-y-3 rounded-xl border border-neon-green/25 bg-neon-green/[0.04] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-neon-green">
            Modo bilhete defensivo
          </p>
          <p className="mt-1 text-sm text-slate-300">
            {homeTeam} × {awayTeam} · só EV+ na Superbet · stake reduzida
          </p>
        </div>
        <span
          className={`rounded-lg border px-3 py-1 text-[11px] font-bold uppercase tracking-wide ${
            view.qualified
              ? "border-neon-green/40 bg-neon-green/10 text-neon-green"
              : "border-amber-500/35 bg-amber-500/10 text-amber-200"
          }`}
        >
          {view.qualified ? "Pronto para montar" : "Aguardando EV+"}
        </span>
      </div>

      {!view.qualified && view.disqualifyReason && (
        <p className="rounded-lg border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-xs text-amber-100/90">
          {view.disqualifyReason}
        </p>
      )}

      {view.qualified && (
        <div className="grid gap-2 sm:grid-cols-3">
          <MiniMetric
            label="Odd combo def."
            value={view.comboOdd != null ? view.comboOdd.toFixed(2) : "—"}
            sub={
              view.comboEv != null ? `EV ${(view.comboEv * 100).toFixed(1)}%` : "pernas cruzadas"
            }
          />
          <MiniMetric
            label="Stake def."
            value={`${view.suggestedStakePct.toFixed(1)}%`}
            sub={`R$ ${view.suggestedStakeValue}`}
          />
          <MiniMetric
            label="Acerto est."
            value={`${(view.combinedHitRate * 100).toFixed(0)}%`}
            sub={`${view.defensiveLegs.length} pernas EV+`}
          />
        </div>
      )}

      {view.legRisks.length > 0 && (
        <div className="space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Monitor das pernas
          </p>
          {view.legRisks.map((risk) => (
            <div
              key={`${risk.legIndex}-${risk.label}`}
              className={`rounded-lg border px-3 py-2 text-xs ${STATUS_STYLES[risk.status] ?? STATUS_STYLES.pending}`}
            >
              <span className="font-semibold">
                Perna {risk.legIndex + 1}
                {risk.legIndex === 0 ? " (principal)" : ""}:{" "}
              </span>
              {risk.message}
            </div>
          ))}
        </div>
      )}

      {view.hedgePlan && (
        <div
          className={`rounded-lg border px-3 py-3 text-xs ${
            firstRisk?.status === "lost"
              ? "border-red-500/35 bg-red-950/30 text-red-100"
              : "border-amber-500/35 bg-amber-950/20 text-amber-100"
          }`}
        >
          <p className="font-semibold">{view.hedgePlan.title}</p>
          <p className="mt-1 leading-relaxed opacity-90">{view.hedgePlan.reason}</p>
          {view.hedgePlan.reserveLeg && (
            <p className="mt-2 rounded-md border border-white/10 bg-black/20 px-2 py-1.5">
              Reserva: <strong>{view.hedgePlan.reserveLeg.label}</strong>
              {view.hedgePlan.reserveLeg.marketOdd != null
                ? ` @ ${view.hedgePlan.reserveLeg.marketOdd.toFixed(2)}`
                : ""}
              {view.hedgePlan.reserveLeg.expectedValue != null
                ? ` · EV ${(view.hedgePlan.reserveLeg.expectedValue * 100).toFixed(1)}%`
                : ""}
            </p>
          )}
          {view.hedgePlan.shield && (
            <p className="mt-2 rounded-md border border-white/10 bg-black/20 px-2 py-1.5">
              {view.hedgePlan.shield.title}
              {view.hedgePlan.shield.odd != null
                ? ` @ ${view.hedgePlan.shield.odd.toFixed(2)}`
                : ""}
              {" — "}
              {view.hedgePlan.shield.reason}
            </p>
          )}
        </div>
      )}

      <ul className="space-y-1 text-[11px] text-slate-500">
        {view.rules.map((rule) => (
          <li key={rule} className="flex gap-2">
            <span className="text-neon-green" aria-hidden="true">
              •
            </span>
            <span>{rule}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function MiniMetric({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-lg border border-white/8 bg-black/20 px-3 py-2">
      <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="font-mono text-base font-semibold text-white">{value}</p>
      <p className="text-[10px] text-slate-500">{sub}</p>
    </div>
  );
}
