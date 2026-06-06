import type { KxlFeptMeta } from "@/domain/entities";

interface SofascoreFeptPanelProps {
  fept: KxlFeptMeta | null | undefined;
}

export function SofascoreFeptPanel({ fept }: SofascoreFeptPanelProps) {
  if (!fept) return null;

  return (
    <div className="glass-card space-y-3 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="section-label">Escalação Sofascore (FEPT)</p>
        {fept.autoMerged ? (
          <span className="rounded-md bg-neon-green/10 px-2 py-0.5 text-[10px] font-bold text-neon-green">
            Auto
          </span>
        ) : (
          <span className="rounded-md bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold text-amber-400">
            Manual
          </span>
        )}
      </div>

      <div className="grid gap-2 text-sm sm:grid-cols-2">
        <InfoRow label="Evento" value={`#${fept.eventId}`} />
        <InfoRow
          label="Notas"
          value={`${fept.ratingsFound} preenchidas · ${fept.ratingsMissing} ausentes`}
        />
        <InfoRow label="Esquema mandante" value={fept.esquemaMandante ?? "—"} />
        <InfoRow label="Esquema visitante" value={fept.esquemaVisitante ?? "—"} />
        {(fept.absencesHome != null || fept.absencesAway != null) && (
          <InfoRow
            label="Desfalques (FEDE)"
            value={`${fept.absencesHome ?? 0} mandante · ${fept.absencesAway ?? 0} visitante`}
          />
        )}
        {fept.referee && (
          <InfoRow
            label="Árbitro (FEJU)"
            value={`${fept.referee} · ${fept.refereeProfile ?? "equilibrado"}${
              fept.refereeCardsPerGame != null
                ? ` · ${fept.refereeCardsPerGame.toFixed(1)} cartões/jogo`
                : ""
            }`}
          />
        )}
      </div>

      {fept.note && <p className="text-xs text-amber-400/90">{fept.note}</p>}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2">
      <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-0.5 font-medium text-white">{value}</p>
    </div>
  );
}
