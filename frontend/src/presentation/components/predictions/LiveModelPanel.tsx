import type { SuperbetLiveAdvice } from "@/domain/entities";
import { formatPercent } from "@/presentation/theme";

interface ProbBarProps {
  label: string;
  prob: number;
  color?: "green" | "amber" | "slate" | "blue";
  title?: string;
}

function ProbBar({ label, prob, color = "slate", title }: ProbBarProps) {
  const barColors: Record<string, string> = {
    green: "bg-neon-green/70",
    amber: "bg-amber-400/70",
    blue: "bg-sky-400/70",
    slate: "bg-slate-400/50",
  };
  const textColors: Record<string, string> = {
    green: "text-neon-green",
    amber: "text-amber-300",
    blue: "text-sky-300",
    slate: "text-slate-300",
  };
  const widthPct = Math.max(0, Math.min(100, prob * 100));

  return (
    <div className="flex items-center gap-2">
      <p
        className="w-28 shrink-0 truncate text-[11px] text-slate-400"
        title={title ?? label}
      >
        {label}
      </p>
      <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-white/8">
        <div
          className={`absolute inset-y-0 left-0 rounded-full transition-all duration-500 ${barColors[color]}`}
          style={{ width: `${widthPct}%` }}
        />
      </div>
      <span className={`w-10 text-right font-mono text-[11px] font-semibold ${textColors[color]}`}>
        {formatPercent(prob)}
      </span>
    </div>
  );
}

function h2hColor(key: "1" | "X" | "2", probs: { home: number; draw: number; away: number }): "green" | "amber" | "slate" {
  const max = Math.max(probs.home, probs.draw, probs.away);
  if (key === "1" && probs.home === max) return "green";
  if (key === "2" && probs.away === max) return "green";
  if (key === "X" && probs.draw === max) return "amber";
  return "slate";
}

interface EdgeMiniCardProps {
  label: string;
  labelFull?: string;
  odd: number | undefined;
  implied: number | undefined;
  model: number | undefined;
  edge: number | undefined;
}

function EdgeMiniCard({ label, odd, implied, model, edge }: EdgeMiniCardProps) {
  const edgePp = edge != null ? edge * 100 : null;
  const edgeColor =
    edgePp == null
      ? "text-slate-400"
      : edgePp > 2
        ? "text-neon-green"
        : edgePp < -2
          ? "text-red-400"
          : "text-slate-300";

  return (
    <div className="rounded-xl border border-white/8 bg-white/[0.03] px-3 py-2.5">
      <p className="truncate text-[10px] uppercase tracking-wider text-slate-500" title={label}>
        {label}
      </p>
      {odd != null ? (
        <>
          <p className="font-mono text-sm font-semibold text-white">
            {odd.toFixed(2)}
            {implied != null && (
              <span className="ml-1.5 text-xs text-slate-500">
                ({formatPercent(implied)})
              </span>
            )}
          </p>
          {model != null && edgePp != null && (
            <p className={`mt-1 text-[11px] ${edgeColor}`}>
              Modelo {formatPercent(model)} · edge {edgePp > 0 ? "+" : ""}
              {edgePp.toFixed(1)} pp
            </p>
          )}
          {edgePp != null && edgePp > 2 && (
            <p className="mt-0.5 text-[10px] text-neon-green/70">Valor p/ apostador</p>
          )}
          {edgePp != null && edgePp < -2 && (
            <p className="mt-0.5 text-[10px] text-red-400/70">Casa otimista</p>
          )}
        </>
      ) : (
        <p className="text-xs text-slate-600">—</p>
      )}
    </div>
  );
}

interface LiveModelPanelProps {
  data: SuperbetLiveAdvice;
}

export function LiveModelPanel({ data }: LiveModelPanelProps) {
  const s = data.inplaySummary;
  const probs = { home: s.probFinalHome, draw: s.probFinalDraw, away: s.probFinalAway };

  function teamLabel(name: string, maxLen = 14): string {
    const t = name.trim();
    return t.length <= maxLen ? t : `${t.slice(0, maxLen - 1)}…`;
  }

  return (
    <div className="space-y-5">
      {/* Probabilidades de resultado final */}
      <div className="rounded-2xl border border-white/8 bg-white/[0.02] p-4">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
          Modelo in-play
        </h3>
        <div className="space-y-2.5">
          <ProbBar
            label={teamLabel(data.homeTeam)}
            title={data.homeTeam}
            prob={s.probFinalHome}
            color={h2hColor("1", probs)}
          />
          <ProbBar
            label="Empate"
            prob={s.probFinalDraw}
            color={h2hColor("X", probs)}
          />
          <ProbBar
            label={teamLabel(data.awayTeam)}
            title={data.awayTeam}
            prob={s.probFinalAway}
            color={h2hColor("2", probs)}
          />
        </div>

        {(s.over25 != null || s.btts != null) && (
          <>
            <div className="my-3 h-px bg-white/8" />
            <div className="space-y-2">
              {s.over25 != null && (
                <ProbBar label="Over 2.5 gols" prob={s.over25} color="blue" />
              )}
              {s.btts != null && (
                <ProbBar label="Ambos marcam" prob={s.btts} color="blue" />
              )}
              {s.probNextGoalHome != null && (
                <ProbBar
                  label={`Próx. gol ${teamLabel(data.homeTeam, 9)}`}
                  title={`Próximo gol ${data.homeTeam}`}
                  prob={s.probNextGoalHome}
                  color="slate"
                />
              )}
              {s.probNextGoalAway != null && (
                <ProbBar
                  label={`Próx. gol ${teamLabel(data.awayTeam, 9)}`}
                  title={`Próximo gol ${data.awayTeam}`}
                  prob={s.probNextGoalAway}
                  color="slate"
                />
              )}
              {s.probNoMoreGoals != null && (
                <ProbBar label="Sem mais gols" prob={s.probNoMoreGoals} color="slate" />
              )}
            </div>
          </>
        )}
      </div>

      {/* Posição da casa — edge 1X2 */}
      <div className="rounded-2xl border border-violet-500/15 bg-violet-500/[0.03] p-4">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Posição da casa
          </h3>
          {data.h2hOverround != null && (
            <span className="rounded-md bg-violet-500/15 px-2 py-0.5 font-mono text-[11px] text-violet-300">
              Margem {(data.h2hOverround * 100).toFixed(1)}%
            </span>
          )}
        </div>

        <div className="grid grid-cols-3 gap-2">
          {(["1", "X", "2"] as const).map((key) => {
            const odd = data.h2hOdds[key];
            const implied = data.h2hImplied[key];
            const bench = data.marketBenchmark?.h2h?.[key];
            const label =
              key === "1"
                ? teamLabel(data.homeTeam)
                : key === "2"
                  ? teamLabel(data.awayTeam)
                  : "Empate";
            const fullLabel =
              key === "1" ? data.homeTeam : key === "2" ? data.awayTeam : "Empate";
            return (
              <EdgeMiniCard
                key={key}
                label={label}
                labelFull={fullLabel}
                odd={odd}
                implied={implied}
                model={bench?.model}
                edge={bench?.edge}
              />
            );
          })}
        </div>

        {/* Totais de gols */}
        {data.marketBenchmark?.totals &&
          Object.keys(data.marketBenchmark.totals).length > 0 && (
            <div className="mt-3">
              <p className="mb-1.5 text-[10px] uppercase tracking-wider text-slate-600">
                Totais de gols
              </p>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(data.marketBenchmark.totals).map(([line, row]) => {
                  const edgePp = row.edgeOver * 100;
                  return (
                    <span
                      key={line}
                      className="rounded-md border border-white/8 bg-white/[0.03] px-2 py-1 text-[10px] text-slate-400"
                    >
                      Over {line}{" "}
                      <span className={edgePp > 0 ? "text-neon-green" : "text-red-400"}>
                        {edgePp > 0 ? "+" : ""}
                        {edgePp.toFixed(1)} pp
                      </span>
                    </span>
                  );
                })}
              </div>
            </div>
          )}

        {/* Generosity */}
        {Object.keys(data.generosityProbs).length > 0 && (
          <p className="mt-3 text-[10px] text-slate-600">
            Generosity:{" "}
            {data.generosityProbs.home != null && (
              <span>
                {teamLabel(data.homeTeam, 10)} {formatPercent(data.generosityProbs.home)}
              </span>
            )}
            {data.generosityProbs.away != null && (
              <span className="ml-1.5">
                {teamLabel(data.awayTeam, 10)} {formatPercent(data.generosityProbs.away)}
              </span>
            )}
          </p>
        )}
      </div>
    </div>
  );
}
