import type { ScorealarmH2h, ScorealarmTeamForm, SuperbetLiveAdvice } from "@/domain/entities";
import { outcomeColors } from "@/presentation/theme";

interface LiveFormH2hPanelProps {
  data: SuperbetLiveAdvice;
}

/** Forma pré-jogo (últimos 5), médias de gols, treinador e H2H ScoreAlarm. */
export function LiveFormH2hPanel({ data }: LiveFormH2hPanelProps) {
  const prematch = data.scorealarm?.prematch;
  const h2h = data.scorealarm?.h2h;
  if (!prematch && !h2h) return null;

  return (
    <section className="glass-card p-4" aria-label="Forma pré-jogo e confronto direto">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Forma pré-jogo
          </h2>
          <p className="text-[10px] text-slate-600">Últimos 5 · ScoreAlarm</p>
        </div>
        {data.scorealarm?.stale && (
          <span className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-300">
            cache
          </span>
        )}
      </div>

      {prematch && (
        <div className="grid gap-3 sm:grid-cols-2">
          <TeamFormCard
            team={data.homeTeam}
            form={prematch.home}
            side="home"
          />
          <TeamFormCard
            team={data.awayTeam}
            form={prematch.away}
            side="away"
          />
        </div>
      )}

      {h2h && <H2hSummaryBar data={data} h2h={h2h} />}

      {prematch && prematch.h2hMatches.length > 0 && (
        <div className="mt-3 rounded-xl border border-white/8 bg-white/[0.02] px-3 py-2">
          <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
            Confrontos diretos recentes
          </p>
          <ul className="mt-2 space-y-1">
            {prematch.h2hMatches.map((m, i) => (
              <li
                key={`${m.homeTeam}-${m.awayTeam}-${i}`}
                className="flex items-center justify-between text-[11px] text-slate-300"
              >
                <span className="truncate">
                  {m.homeTeam} <span className="text-slate-600">x</span> {m.awayTeam}
                </span>
                <span className="font-mono font-semibold text-white">{m.score}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function TeamFormCard({
  team,
  form,
  side,
}: {
  team: string;
  form: ScorealarmTeamForm;
  side: "home" | "away";
}) {
  const accent = side === "home" ? outcomeColors["1"] : outcomeColors["2"];
  const chips = form.form ? form.form.split("-").filter(Boolean) : [];

  return (
    <div
      className="rounded-xl border p-3"
      style={{ borderColor: `${accent}25`, backgroundColor: `${accent}06` }}
    >
      <p className="truncate text-sm font-semibold text-white">{team}</p>
      {form.coach && (
        <p className="mt-0.5 truncate text-[10px] text-slate-500">Téc. {form.coach}</p>
      )}
      <div className="mt-2 flex flex-wrap gap-1">
        {chips.length > 0 ? (
          chips.map((r, i) => <FormChip key={`${r}-${i}`} result={r} />)
        ) : (
          <span className="text-[10px] text-slate-600">Sem jogos recentes</span>
        )}
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2 text-[10px]">
        <div>
          <p className="text-slate-600">Gols/jogo</p>
          <p className="font-mono font-semibold text-white">{form.goalsAvg.toFixed(1)}</p>
        </div>
        <div>
          <p className="text-slate-600">Sofridos/jogo</p>
          <p className="font-mono font-semibold text-amber-300">{form.concededAvg.toFixed(1)}</p>
        </div>
      </div>
      {form.lastMatches.length > 0 && (
        <ul className="mt-2 space-y-0.5 border-t border-white/5 pt-2">
          {form.lastMatches.slice(0, 3).map((m, i) => (
            <li key={`${m.opponent}-${i}`} className="flex justify-between text-[10px] text-slate-500">
              <span className="truncate">vs {m.opponent}</span>
              <span className="font-mono text-slate-400">{m.score}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function H2hSummaryBar({
  data,
  h2h,
}: {
  data: SuperbetLiveAdvice;
  h2h: ScorealarmH2h;
}) {
  const total = h2h.homeWins + h2h.draws + h2h.awayWins;
  if (total <= 0) return null;

  const homePct = (h2h.homeWins / total) * 100;
  const drawPct = (h2h.draws / total) * 100;
  const awayPct = (h2h.awayWins / total) * 100;

  return (
    <div className="mt-3 rounded-xl border border-white/8 bg-white/[0.02] px-3 py-2">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
          H2H histórico
        </p>
        {h2h.sinceYear != null && (
          <span className="text-[10px] text-slate-600">desde {h2h.sinceYear}</span>
        )}
      </div>
      <div className="mb-2 flex h-2 overflow-hidden rounded-full bg-white/5">
        <div className="bg-neon-green/70" style={{ width: `${homePct}%` }} />
        <div className="bg-amber-400/70" style={{ width: `${drawPct}%` }} />
        <div className="bg-sky-400/70" style={{ width: `${awayPct}%` }} />
      </div>
      <div className="grid grid-cols-3 gap-2 text-center text-[10px]">
        <div>
          <p className="truncate text-slate-500">{data.homeTeam}</p>
          <p className="font-mono text-base font-bold text-neon-green">{h2h.homeWins}</p>
        </div>
        <div>
          <p className="text-slate-500">Empates</p>
          <p className="font-mono text-base font-bold text-amber-300">{h2h.draws}</p>
        </div>
        <div>
          <p className="truncate text-slate-500">{data.awayTeam}</p>
          <p className="font-mono text-base font-bold text-sky-300">{h2h.awayWins}</p>
        </div>
      </div>
    </div>
  );
}

function FormChip({ result }: { result: string }) {
  const map: Record<string, string> = {
    V: "bg-neon-green/20 text-neon-green",
    E: "bg-amber-400/20 text-amber-300",
    D: "bg-red-400/20 text-red-300",
  };
  const label = { V: "V", E: "E", D: "D" }[result] ?? result;
  return (
    <span
      className={`inline-flex h-6 w-6 items-center justify-center rounded-md text-[10px] font-bold ${map[result] ?? "bg-white/10 text-slate-400"}`}
    >
      {label}
    </span>
  );
}
