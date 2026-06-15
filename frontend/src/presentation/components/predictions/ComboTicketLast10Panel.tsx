import type { WcComboTicket } from "@/domain/entities";

type Last10Analysis = NonNullable<WcComboTicket["last10Analysis"]>;
type Last10Leg = Last10Analysis["legs"][number];
type Last10Match = Last10Leg["teams"][number]["matches"][number];

function hitBadge(hit: boolean | null) {
  if (hit === true) {
    return (
      <span className="rounded-md bg-neon-green/15 px-2 py-0.5 text-[10px] font-semibold text-neon-green">
        ✓
      </span>
    );
  }
  if (hit === false) {
    return (
      <span className="rounded-md bg-red-500/15 px-2 py-0.5 text-[10px] font-semibold text-red-300">
        ✗
      </span>
    );
  }
  return (
    <span className="rounded-md bg-white/5 px-2 py-0.5 text-[10px] text-slate-500">—</span>
  );
}

function TeamMatchesTable({
  teamBlock,
}: {
  teamBlock: Last10Leg["teams"][number];
}) {
  return (
    <div className="mt-3">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <span className="font-semibold text-white">{teamBlock.team}</span>
        <span className="rounded-md bg-white/5 px-2 py-0.5 text-slate-400">
          Sofascore: {teamBlock.hits}/{teamBlock.total}
          {teamBlock.hitRate != null ? ` (${(teamBlock.hitRate * 100).toFixed(0)}%)` : ""}
        </span>
        {teamBlock.kxlPattern && (
          <span className="rounded-md bg-neon-blue/10 px-2 py-0.5 text-neon-blue">
            KXL: {teamBlock.kxlPattern.hits}/{teamBlock.kxlPattern.total}
          </span>
        )}
      </div>
      <div className="overflow-x-auto rounded-lg border border-white/10">
        <table className="min-w-full text-left text-[11px]">
          <thead className="bg-white/[0.03] text-slate-500">
            <tr>
              <th className="px-3 py-2 font-medium">Data</th>
              <th className="px-3 py-2 font-medium">Jogo</th>
              <th className="px-3 py-2 font-medium">1T / métrica</th>
              <th className="px-3 py-2 font-medium">Acerto</th>
            </tr>
          </thead>
          <tbody>
            {teamBlock.matches.map((m: Last10Match) => (
              <tr key={m.eventId} className="border-t border-white/5 text-slate-300">
                <td className="whitespace-nowrap px-3 py-2">{m.matchDate ?? "—"}</td>
                <td className="px-3 py-2">
                  {m.homeTeam} × {m.awayTeam}
                </td>
                <td className="px-3 py-2 text-slate-400">{m.detail}</td>
                <td className="px-3 py-2">{hitBadge(m.hit)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

interface ComboTicketLast10PanelProps {
  analysis?: WcComboTicket["last10Analysis"];
}

export function ComboTicketLast10Panel({ analysis }: ComboTicketLast10PanelProps) {
  if (!analysis?.legs?.length) return null;

  return (
    <section className="mt-6 rounded-2xl border border-white/10 bg-white/[0.02] p-5">
      <h3 className="text-sm font-semibold text-white">
        Fundamentação — últimos {analysis.windowSize} jogos
      </h3>
      <p className="mt-1 text-xs text-slate-400">{analysis.sourceNote}</p>
      {analysis.incidentsFetched > 0 && (
        <p className="mt-1 text-[11px] text-neon-blue/90">
          Incidentes 1T carregados em {analysis.incidentsFetched} partida(s) via Sofascore.
        </p>
      )}

      <div className="mt-4 space-y-6">
        {analysis.legs.map((leg) => (
          <div
            key={`${leg.rank}-${leg.stat}-${leg.period}`}
            className="rounded-xl border border-white/10 bg-black/20 p-4"
          >
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Aposta {leg.rank}
            </p>
            <p className="mt-1 text-sm font-medium text-white">{leg.label}</p>
            <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
              <span className="rounded-md bg-neon-blue/10 px-2 py-0.5 text-neon-blue">
                KXL cruzamento: {leg.kxlCrossing.hits}/{leg.kxlCrossing.total}
                {leg.kxlCrossing.hitRate != null
                  ? ` (${(leg.kxlCrossing.hitRate * 100).toFixed(0)}%)`
                  : ""}
              </span>
              <span className="rounded-md bg-white/5 px-2 py-0.5 text-slate-400">
                Sofascore (min das duas):{" "}
                {leg.sofascoreCrossing.evaluated != null && leg.sofascoreCrossing.evaluated > 0
                  ? `${leg.sofascoreCrossing.hits}/${leg.sofascoreCrossing.total}${
                      leg.sofascoreCrossing.hitRate != null
                        ? ` (${(leg.sofascoreCrossing.hitRate * 100).toFixed(0)}%)`
                        : ""
                    }`
                  : "1T pendente (incidentes)"}
              </span>
            </div>
            {leg.teams.map((teamBlock) => (
              <TeamMatchesTable key={teamBlock.team} teamBlock={teamBlock} />
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}
