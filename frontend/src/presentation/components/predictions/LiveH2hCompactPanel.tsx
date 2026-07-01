import type { SuperbetLiveAdvice } from "@/domain/entities";

interface LiveH2hCompactPanelProps {
  data: SuperbetLiveAdvice;
}

/** H2H ScoreAlarm — vitórias/empates entre os times. */
export function LiveH2hCompactPanel({ data }: LiveH2hCompactPanelProps) {
  const h2h = data.scorealarm?.h2h;
  if (!h2h) return null;

  const total = h2h.homeWins + h2h.draws + h2h.awayWins;
  if (total <= 0) return null;

  const homePct = (h2h.homeWins / total) * 100;
  const drawPct = (h2h.draws / total) * 100;
  const awayPct = (h2h.awayWins / total) * 100;

  return (
    <section className="glass-card p-3" aria-label="Confronto direto">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          H2H histórico
        </h2>
        {h2h.sinceYear != null && (
          <span className="text-[10px] text-slate-600">desde {h2h.sinceYear}</span>
        )}
      </div>

      <div className="mb-2 flex h-2.5 overflow-hidden rounded-full bg-white/5">
        <div className="bg-neon-green/70" style={{ width: `${homePct}%` }} />
        <div className="bg-amber-400/70" style={{ width: `${drawPct}%` }} />
        <div className="bg-sky-400/70" style={{ width: `${awayPct}%` }} />
      </div>

      <div className="grid grid-cols-3 gap-2 text-center text-[11px]">
        <div>
          <p className="truncate text-slate-500">{data.homeTeam}</p>
          <p className="font-mono text-lg font-bold text-neon-green">{h2h.homeWins}</p>
        </div>
        <div>
          <p className="text-slate-500">Empates</p>
          <p className="font-mono text-lg font-bold text-amber-300">{h2h.draws}</p>
        </div>
        <div>
          <p className="truncate text-slate-500">{data.awayTeam}</p>
          <p className="font-mono text-lg font-bold text-sky-300">{h2h.awayWins}</p>
        </div>
      </div>
    </section>
  );
}
