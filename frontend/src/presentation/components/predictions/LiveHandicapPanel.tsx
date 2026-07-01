import type { HandicapAnalysis, HandicapLine } from "@/domain/entities";

interface LiveHandicapPanelProps {
  analysis: HandicapAnalysis | null | undefined;
  homeTeam: string;
  awayTeam: string;
  isLoading?: boolean;
}

function formatLine(line: number): string {
  if (line === 0) return "0";
  return line > 0 ? `+${line}` : `${line}`;
}

function sideLabel(side: string, homeTeam: string, awayTeam: string): string {
  if (side === "home") return homeTeam;
  return awayTeam;
}

function LineCard({
  row,
  homeTeam,
  awayTeam,
}: {
  row: HandicapLine;
  homeTeam: string;
  awayTeam: string;
}) {
  const evPositive = row.ev != null && row.ev > 0.05;
  const evWatch = row.ev != null && row.ev > 0 && row.ev <= 0.05;
  const modelPct = (row.modelProb * 100).toFixed(0);
  const impliedPct =
    row.superbetOdd != null && row.superbetOdd > 1
      ? ((1 / row.superbetOdd) * 100).toFixed(0)
      : null;

  return (
    <div
      className={`rounded-xl border px-3 py-3 ${
        evPositive
          ? "border-neon-green/40 bg-neon-green/[0.06]"
          : "border-white/10 bg-white/[0.03]"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-semibold text-white">
            {sideLabel(row.side, homeTeam, awayTeam)} {formatLine(row.line)}
          </p>
          {row.superbetOdd != null ? (
            <p className="mt-0.5 font-mono text-sm text-neon-blue">@{row.superbetOdd.toFixed(2)}</p>
          ) : (
            <p className="mt-0.5 text-[11px] text-slate-500">Sem odd Superbet</p>
          )}
        </div>
        {evPositive && (
          <span className="rounded-md border border-neon-green/40 bg-neon-green/10 px-2 py-0.5 text-[10px] font-bold uppercase text-neon-green">
            EV+
          </span>
        )}
        {evWatch && (
          <span className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold uppercase text-amber-200">
            watch
          </span>
        )}
      </div>
      <div className="mt-2 space-y-1">
        <div className="flex justify-between text-[11px] text-slate-400">
          <span>Modelo {modelPct}%</span>
          {impliedPct != null && <span>Mercado {impliedPct}%</span>}
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
          <div
            className="h-full rounded-full bg-neon-blue/80"
            style={{ width: `${Math.min(100, Number(modelPct))}%` }}
          />
        </div>
      </div>
      {row.ev != null && (
        <p
          className={`mt-2 text-[11px] font-medium ${
            row.ev > 0 ? "text-neon-green" : "text-slate-500"
          }`}
        >
          EV {(row.ev * 100).toFixed(1)}%
          {row.kellyStake > 0 ? ` · Stake ~R$ ${row.kellyStake.toFixed(0)}` : ""}
        </p>
      )}
    </div>
  );
}

export function LiveHandicapPanel({
  analysis,
  homeTeam,
  awayTeam,
  isLoading,
}: LiveHandicapPanelProps) {
  if (isLoading) {
    return (
      <p className="text-xs text-slate-500" aria-live="polite">
        Carregando handicap asiático…
      </p>
    );
  }
  if (!analysis?.lines?.length) {
    return (
      <p className="text-xs text-slate-500">
        Handicap indisponível — informe evento Superbet ao vivo para cruzar odds.
      </p>
    );
  }

  const pairs = new Map<string, { home?: HandicapLine; away?: HandicapLine }>();
  for (const row of analysis.lines) {
    const key = Math.abs(row.line).toString();
    const bucket = pairs.get(key) ?? {};
    if (row.side === "home") bucket.home = row;
    else bucket.away = row;
    pairs.set(key, bucket);
  }

  return (
    <div className="space-y-3">
      {analysis.bestBet && analysis.bestBet.ev != null && analysis.bestBet.ev > 0.05 && (
        <p className="rounded-lg border border-neon-green/30 bg-neon-green/10 px-3 py-2 text-xs text-neon-green">
          Melhor edge: {sideLabel(analysis.bestBet.side, homeTeam, awayTeam)}{" "}
          {formatLine(analysis.bestBet.line)} · EV {(analysis.bestBet.ev * 100).toFixed(1)}%
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from(pairs.entries()).map(([key, pair]) => (
          <div key={key} className="grid gap-2 sm:col-span-2 lg:col-span-2">
            <div className="grid grid-cols-2 gap-2">
              {pair.home && (
                <LineCard row={pair.home} homeTeam={homeTeam} awayTeam={awayTeam} />
              )}
              {pair.away && (
                <LineCard row={pair.away} homeTeam={homeTeam} awayTeam={awayTeam} />
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
