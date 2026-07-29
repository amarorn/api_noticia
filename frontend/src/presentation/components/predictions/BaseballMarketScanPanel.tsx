import type { BaseballSuperbetLiveAdvice } from "@/domain/entities";
import {
  formatBaseballScanCategory,
  formatBaseballScanLine,
  sortBaseballMarketScan,
} from "@/presentation/utils/baseballOperationalUtils";

interface BaseballMarketScanPanelProps {
  data: BaseballSuperbetLiveAdvice;
}

function scanCategoryDead(category: string, deadMarkets: string[]): boolean {
  const map: Record<string, string[]> = {
    moneyline: ["moneyline", "h2h"],
    totals: ["total_runs", "f5_total", "team_total_runs"],
    spread: ["run_line", "spread", "f5_spread"],
  };
  const keys = map[category] ?? [category];
  return deadMarkets.some((m) => keys.some((k) => m === k || m.startsWith(`${k}_`)));
}

function formatProb(value: number | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

export function BaseballMarketScanPanel({ data }: BaseballMarketScanPanelProps) {
  const rows = sortBaseballMarketScan(data);
  const deadMarkets = data.betGuardrails?.deadMarkets ?? [];

  if (rows.length === 0) {
    return (
      <section className="rounded-xl border border-white/8 bg-black/25 p-4">
        <h2 className="text-sm font-semibold text-white">Scan de mercados</h2>
        <p className="mt-2 text-xs text-slate-500">
          Benchmark modelo × Superbet indisponível no momento (feed sem ML/total/spread).
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-white/8 bg-black/25 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-white">Scan de mercados</h2>
          <p className="text-[11px] text-slate-500">
            Modelo vs implied Superbet · ordenado por |edge|
          </p>
        </div>
        <span className="rounded-full bg-white/5 px-2.5 py-1 text-[10px] font-bold text-slate-300">
          {rows.length} linhas
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-left text-xs">
          <thead>
            <tr className="border-b border-white/10 text-[10px] uppercase tracking-wider text-slate-500">
              <th className="pb-2 pr-3 font-medium">Mercado</th>
              <th className="pb-2 pr-3 font-medium">Linha</th>
              <th className="pb-2 pr-3 font-medium">Mercado</th>
              <th className="pb-2 pr-3 font-medium">Modelo</th>
              <th className="pb-2 font-medium text-right">Edge</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const edge = row.edgePp;
              const edgeTone =
                Math.abs(edge) < 1
                  ? "text-slate-400"
                  : edge > 0
                    ? "text-emerald-300"
                    : "text-rose-300";
              const isDead = scanCategoryDead(row.category, [...deadMarkets]);
              return (
                <tr
                  key={`${row.category}-${row.line}`}
                  className="border-b border-white/[0.04] last:border-0"
                >
                  <td className="py-2.5 pr-3 font-medium text-white">
                    {formatBaseballScanCategory(row.category)}
                    {isDead ? (
                      <span className="ml-1.5 rounded bg-red-500/15 px-1 py-0.5 text-[9px] uppercase text-red-300">
                        morto
                      </span>
                    ) : null}
                  </td>
                  <td className="py-2.5 pr-3 text-slate-300">
                    {formatBaseballScanLine(row.category, row.line)}
                  </td>
                  <td className="py-2.5 pr-3 font-mono text-slate-400">
                    {formatProb(row.market)}
                  </td>
                  <td className="py-2.5 pr-3 font-mono text-slate-200">
                    {formatProb(row.model)}
                  </td>
                  <td className={`py-2.5 text-right font-mono font-semibold ${edgeTone}`}>
                    {edge > 0 ? "+" : ""}
                    {edge.toFixed(1)} pp
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {(data.strategy?.watchList?.length ?? 0) > 0 ? (
        <p className="mt-3 text-[11px] text-slate-500">
          Watch list: {data.strategy!.watchList.length} oportunidade(s) com edge ≥ 3 pp nos aportes.
        </p>
      ) : null}
    </section>
  );
}
