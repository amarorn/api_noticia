import type { SuperbetLiveAdvice } from "@/domain/entities";

interface LiveSocialRadarPanelProps {
  data: SuperbetLiveAdvice;
}

/**
 * Top picks sociais da casa (social-front) ou radar do modelo como fallback.
 */
export function LiveSocialRadarPanel({ data }: LiveSocialRadarPanelProps) {
  const social = data.scorealarm?.social;
  const modelPicks = (data.strategy?.opportunities ?? [])
    .filter((o) => o.tier !== "abaixo_limiar")
    .slice(0, 4);

  if (social?.available && social.picks.length > 0) {
    return (
      <section className="glass-card p-4" aria-label="Apostas populares na casa">
        <div className="mb-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            O que a torcida aposta
          </h2>
          <p className="text-[10px] text-slate-600">Top picks in-play · Superbet Social</p>
        </div>
        <ul className="space-y-2">
          {social.picks.map((pick, idx) => (
            <li
              key={`${pick.label}-${idx}`}
              className="flex items-center justify-between gap-2 rounded-xl border border-white/8 bg-white/[0.02] px-3 py-2 text-xs"
            >
              <span className="min-w-0 truncate text-slate-200">{pick.label}</span>
              <div className="flex shrink-0 items-center gap-2 font-mono text-[11px]">
                {pick.sharePct != null && (
                  <span className="text-amber-300">{pick.sharePct.toFixed(0)}%</span>
                )}
                {pick.odd != null && <span className="text-neon-green">{pick.odd.toFixed(2)}</span>}
              </div>
            </li>
          ))}
        </ul>
      </section>
    );
  }

  if (modelPicks.length === 0) return null;

  return (
    <section className="glass-card p-4" aria-label="Radar de mercados">
      <div className="mb-3">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Radar de mercados
        </h2>
        <p className="text-[10px] text-slate-600">
          Social indisponível
          {social?.reason ? ` — ${social.reason}` : ""}
          . Exibindo leituras do modelo.
        </p>
      </div>
      <ul className="space-y-2">
        {modelPicks.map((pick) => (
          <li
            key={`${pick.market}-${pick.outcome}`}
            className="flex items-center justify-between gap-2 rounded-xl border border-white/8 bg-white/[0.02] px-3 py-2 text-xs"
          >
            <span className="min-w-0 truncate text-slate-200">{pick.label}</span>
            <span className="shrink-0 font-mono text-neon-green">
              EV {(pick.expectedValue * 100).toFixed(0)}%
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
