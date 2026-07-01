import type { SuperbetLiveAdvice } from "@/domain/entities";
import {
  buildExtraMarketRows,
  buildH2hMarketRows,
  evDisplayTone,
  type ModelMarketRow,
} from "@/presentation/utils/liveModelMarketRows";

function MarketTable({
  rows,
  threshold,
  bestEv,
  showShortLabel,
}: {
  rows: ModelMarketRow[];
  threshold: number;
  bestEv: number | null;
  showShortLabel?: boolean;
}) {
  if (!rows.length) return null;

  return (
    <tbody>
      {rows.map((row) => {
        const modelPct = (row.modelProb * 100).toFixed(0);
        const evPct = row.expectedValue * 100;
        const tone = evDisplayTone(row.expectedValue, threshold);
        const isBest =
          bestEv != null &&
          row.expectedValue === bestEv &&
          row.expectedValue >= threshold;

        return (
          <tr
            key={row.id}
            className={`border-b border-white/5 transition-colors last:border-0 ${
              isBest ? "bg-neon-green/[0.08]" : row.meetsThreshold ? "bg-neon-green/[0.04]" : ""
            }`}
          >
            <td className="max-w-[180px] truncate px-4 py-2.5 font-medium text-slate-200">
              {showShortLabel && row.shortLabel && (
                <span className="mr-1.5 font-mono text-slate-500">{row.shortLabel}</span>
              )}
              {row.label}
            </td>
            <td className="px-3 py-2.5 text-right font-mono font-semibold text-violet-300">
              {modelPct}%
            </td>
            <td className="px-3 py-2.5 text-right font-mono text-slate-300">
              {row.marketOdd.toFixed(2)}
            </td>
            <td className="px-4 py-2.5 text-right">
              <span
                className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 font-mono text-[11px] font-bold ${tone.bg} ${tone.text}`}
              >
                {isBest && (
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-neon-green" />
                )}
                <span aria-hidden="true">{tone.icon}</span>
                {evPct >= 0 ? "+" : ""}
                {evPct.toFixed(1)}%
              </span>
            </td>
          </tr>
        );
      })}
    </tbody>
  );
}

interface LiveModelVsMarketHeroProps {
  data: SuperbetLiveAdvice;
}

/** Modelo × odd da casa × EV — 1X2 + mercados do scan. */
export function LiveModelVsMarketHero({ data }: LiveModelVsMarketHeroProps) {
  const threshold = data.strategy?.minEdgeThreshold ?? 0.04;
  const h2hRows = buildH2hMarketRows(data, threshold);
  const extraRows = buildExtraMarketRows(data, threshold, 6);
  const allRows = [...h2hRows, ...extraRows];

  if (!allRows.length) return null;

  const bestEv = allRows.reduce<number | null>((best, r) => {
    return best == null || r.expectedValue > best ? r.expectedValue : best;
  }, null);

  return (
    <section
      className="glass-card overflow-hidden p-0"
      aria-label="Odds ao vivo versus modelo"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/8 px-4 py-2.5">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Odds ao vivo · Superbet
          </h2>
          <p className="text-[10px] text-slate-600">
            EV = (prob × odd) − 1 · atualiza a cada refresh do modelo
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded-full border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-[10px] font-semibold text-red-300">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red-400" />
            LIVE
          </span>
          {data.h2hOverround != null && (
            <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-0.5 font-mono text-[10px] text-slate-400">
              Margem 1X2 {(data.h2hOverround * 100).toFixed(1)}%
            </span>
          )}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[360px] text-left text-xs">
          <thead>
            <tr className="border-b border-white/6 text-[10px] uppercase tracking-wider text-slate-600">
              <th className="px-4 py-2 font-semibold">Mercado</th>
              <th className="px-3 py-2 text-right font-semibold">Modelo</th>
              <th className="px-3 py-2 text-right font-semibold">Odd casa</th>
              <th className="px-4 py-2 text-right font-semibold">EV real</th>
            </tr>
          </thead>
          {h2hRows.length > 0 && (
            <>
              <tbody>
                <tr className="bg-white/[0.02] text-[10px] uppercase tracking-wider text-slate-500">
                  <td colSpan={4} className="px-4 py-1.5 font-semibold">
                    Resultado final
                  </td>
                </tr>
              </tbody>
              <MarketTable
                rows={h2hRows}
                threshold={threshold}
                bestEv={bestEv}
                showShortLabel
              />
            </>
          )}
          {extraRows.length > 0 && (
            <>
              <tbody>
                <tr className="bg-white/[0.02] text-[10px] uppercase tracking-wider text-slate-500">
                  <td colSpan={4} className="px-4 py-1.5 font-semibold">
                    Outros mercados
                  </td>
                </tr>
              </tbody>
              <MarketTable rows={extraRows} threshold={threshold} bestEv={bestEv} />
            </>
          )}
        </table>
      </div>
    </section>
  );
}
