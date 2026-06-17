import { useMemo, useState } from "react";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import { SendComboProposalButton } from "@/presentation/components/predictions/SendComboProposalButton";
import { buildProposalFromStrategyOpportunity } from "@/presentation/utils/comboProposalPayload";
import {
  buildTopReturnRows,
  MIN_ODD_PRESETS,
} from "@/presentation/utils/topReturnOpportunities";

interface LiveTopReturnPanelProps {
  data: SuperbetLiveAdvice;
}

export function LiveTopReturnPanel({ data }: LiveTopReturnPanelProps) {
  const [minOdd, setMinOdd] = useState(1);
  const [evOnly, setEvOnly] = useState(true);

  const rows = useMemo(
    () =>
      buildTopReturnRows(data.strategy?.marketScan, {
        minOdd,
        evOnly,
        maxRows: 8,
      }),
    [data.strategy?.marketScan, minOdd, evOnly],
  );

  if (!data.isLive || data.isFinished) return null;

  const scanCount = data.strategy?.marketScan?.length ?? 0;

  return (
    <section className="rounded-2xl border border-sky-500/25 bg-gradient-to-br from-sky-500/[0.08] to-transparent p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Top retorno esperado</h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Mercados ordenados por lucro esperado (stake sugerido × EV) · odd Superbet ao vivo
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <span>Odd mín.</span>
            <select
              value={minOdd}
              onChange={(e) => setMinOdd(Number(e.target.value))}
              className="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-xs text-white"
            >
              {MIN_ODD_PRESETS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex cursor-pointer items-center gap-1.5 text-[11px] text-slate-400">
            <input
              type="checkbox"
              checked={evOnly}
              onChange={(e) => setEvOnly(e.target.checked)}
              className="rounded border-white/20"
            />
            Só EV+
          </label>
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="text-sm text-slate-500">
          {scanCount === 0
            ? "Aguardando scan de mercados (poll Superbet)…"
            : `Nenhum mercado com EV+ acima de odd ${minOdd.toFixed(2)}. Tente reduzir o filtro ou aguarde o próximo refresh.`}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead>
              <tr className="border-b border-white/8 text-left text-slate-500">
                <th className="pb-2 pr-2">#</th>
                <th className="pb-2 pr-3">Mercado</th>
                <th className="pb-2 pr-3">Odd</th>
                <th className="pb-2 pr-3">EV</th>
                <th className="pb-2 pr-3">Retorno esp.</th>
                <th className="pb-2 pr-3">Se ganhar</th>
                <th className="pb-2 pr-3">Stake</th>
                <th className="pb-2">Ação</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const stake =
                  row.suggestedStakeValue > 0 ? row.suggestedStakeValue : 25;
                const proposal = buildProposalFromStrategyOpportunity(
                  { ...row, suggestedStakeValue: stake },
                  {
                    homeTeam: data.homeTeam,
                    awayTeam: data.awayTeam,
                    superbetEventId: data.superbetEventId,
                    minute: data.minute,
                  },
                );
                return (
                  <tr
                    key={`${row.market}:${row.outcome}`}
                    className="border-b border-white/5 hover:bg-white/[0.02]"
                  >
                    <td className="py-2.5 pr-2 font-mono text-slate-500">{row.rank}</td>
                    <td className="max-w-[200px] py-2.5 pr-3">
                      <span className="block truncate font-medium text-white" title={row.label}>
                        {row.label}
                      </span>
                      <span className="text-[10px] text-slate-600">
                        {row.modelProb * 100 >= 1
                          ? `${(row.modelProb * 100).toFixed(0)}% modelo · +${row.edgePp.toFixed(1)} pp`
                          : `+${row.edgePp.toFixed(1)} pp`}
                      </span>
                    </td>
                    <td className="py-2.5 pr-3 font-mono text-sky-300">
                      @{row.marketOdd.toFixed(2)}
                    </td>
                    <td className="py-2.5 pr-3 font-mono text-neon-green">
                      +{(row.expectedValue * 100).toFixed(1)}%
                    </td>
                    <td className="py-2.5 pr-3 font-mono font-semibold text-neon-green">
                      R$ {row.expectedProfit.toFixed(2)}
                    </td>
                    <td className="py-2.5 pr-3 text-slate-300">
                      <span className="font-mono text-white">+R$ {row.winProfit.toFixed(0)}</span>
                      <span className="ml-1 text-[10px] text-slate-600">
                        (→ R$ {row.potentialReturn.toFixed(0)})
                      </span>
                    </td>
                    <td className="py-2.5 pr-3 text-slate-400">
                      R$ {stake.toFixed(0)}
                    </td>
                    <td className="py-2.5">
                      <SendComboProposalButton proposal={proposal} compact />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <p className="mt-3 text-[10px] leading-relaxed text-slate-600">
        Retorno esperado = stake × EV (média de longo prazo). &quot;Se ganhar&quot; é o lucro bruto
        na odd atual — não confundir odd alta com valor; EV+ filtra mercados onde o modelo vê edge.
      </p>
    </section>
  );
}
