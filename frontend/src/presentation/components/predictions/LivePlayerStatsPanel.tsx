import type { SuperbetLiveAdvice } from "@/domain/entities";

interface LivePlayerStatsPanelProps {
  data: SuperbetLiveAdvice;
}

/** Jogadores em destaque ao vivo (ScoreAlarm player stats SSE). */
export function LivePlayerStatsPanel({ data }: LivePlayerStatsPanelProps) {
  const players = data.scorealarm?.players ?? [];
  if (players.length === 0) return null;

  return (
    <section className="glass-card p-4" aria-label="Jogadores em destaque">
      <div className="mb-3">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Jogadores em destaque
        </h2>
        <p className="text-[10px] text-slate-600">Stats individuais · ScoreAlarm</p>
      </div>

      <ul className="space-y-2">
        {players.map((player, idx) => (
          <li
            key={`${player.name}-${player.jersey}-${idx}`}
            className="flex items-start justify-between gap-3 rounded-xl border border-white/8 bg-white/[0.02] px-3 py-2"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-white">
                {player.jersey ? `#${player.jersey} ` : ""}
                {player.name}
              </p>
              <p className="truncate text-[10px] text-slate-500">
                {player.team}
                {player.positionLabel ? ` · ${player.positionLabel}` : ""}
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap justify-end gap-1">
              {player.highlights.map((h) => (
                <span
                  key={h}
                  className="rounded-md border border-neon-green/20 bg-neon-green/10 px-1.5 py-0.5 text-[10px] font-medium text-neon-green"
                >
                  {h}
                </span>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
