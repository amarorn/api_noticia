import { useMemo, useState } from "react";
import type { MarketOperationalRow } from "@/presentation/components/live-operational/useMarketOperationalRows";
import { formatOdd, formatPercent } from "@/presentation/components/live-operational/liveOperationalUtils";
import { IconInfo, IconStar } from "@/presentation/components/ui/Icons";
import { ChipV2, MiniBarV2, SectionTitleV2, type ToneV2 } from "./live-ui-v2";

const DIRECTION_TONE: Record<MarketOperationalRow["direction"], { label: string; tone: ToneV2 }> = {
  encurtando: { label: "Encurtando ↓", tone: "green" },
  esticando: { label: "Esticando ↑", tone: "amber" },
  estavel: { label: "Estável →", tone: "slate" },
  novo: { label: "Novo ★", tone: "cyan" },
};

function fmtTime(iso: string | null) {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function LiveMarketsOverviewV2({ rows }: { rows: MarketOperationalRow[] }) {
  const [favorites, setFavorites] = useState<ReadonlySet<string>>(new Set());
  const [onlyFavorites, setOnlyFavorites] = useState(false);

  const toggleFavorite = (key: string) => {
    setFavorites((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const visible = useMemo(() => {
    const sorted = [...rows].sort((a, b) => b.expectedValue - a.expectedValue);
    const base = onlyFavorites ? sorted.filter((r) => favorites.has(r.key)) : sorted;
    return base.slice(0, 8);
  }, [favorites, onlyFavorites, rows]);

  return (
    <section className="panel-v2 w-full max-w-full p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SectionTitleV2 title="Visão Geral de Mercados" icon={<IconInfo className="h-3.5 w-3.5" />} />
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-white/8 bg-black/20 p-0.5">
            <button
              type="button"
              onClick={() => setOnlyFavorites(false)}
              className={`rounded-md px-3 py-1.5 text-[11px] font-bold transition-colors ${
                !onlyFavorites ? "bg-neon-green text-slate-950" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Todos os mercados
            </button>
            <button
              type="button"
              onClick={() => setOnlyFavorites(true)}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[11px] font-bold transition-colors ${
                onlyFavorites ? "bg-neon-green text-slate-950" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <IconStar className="h-3 w-3" filled={onlyFavorites} />
              Apenas favoritos
            </button>
          </div>
        </div>
      </div>

      <div className="markets-table-wrapper-v2 scroll-v2 mt-4">
        <table className="markets-table-v2 text-left">
          <thead>
            <tr>
              <th>Mercado</th>
              <th>Seleção</th>
              <th>Odd atual</th>
              <th>Odd justa</th>
              <th>EV</th>
              <th>Pressão implícita</th>
              <th>Direção</th>
              <th>Última mudança</th>
              <th>Confiança</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.05]">
            {visible.map((row) => (
              <tr key={row.key} className="bg-transparent transition-colors hover:bg-white/[0.04]">
                <td className="max-w-[220px]">
                  <p className="truncate font-semibold text-white" title={row.label}>{row.label}</p>
                  <p className="text-slate-500">{row.type}</p>
                </td>
                <td className="text-slate-300">{row.outcome}</td>
                <td className="font-mono text-white">{formatOdd(row.marketOdd)}</td>
                <td className="font-mono text-slate-300">{formatOdd(row.fairOdd)}</td>
                <td className={`font-mono font-bold ${row.expectedValue > 0 ? "text-neon-green" : "text-slate-300"}`}>{formatPercent(row.expectedValue)}</td>
                <td>
                  <div className="flex items-center gap-2">
                    <div className="w-14 shrink-0">
                      <MiniBarV2 pct={row.pressureEstimate} tone="cyan" />
                    </div>
                    <span className="font-mono text-[11px] text-slate-300">
                      {row.pressureEstimate}% · {row.pressureLabel}
                    </span>
                  </div>
                </td>
                <td>
                  <ChipV2 label={DIRECTION_TONE[row.direction].label} tone={DIRECTION_TONE[row.direction].tone} />
                </td>
                <td>
                  <p className="font-mono text-slate-200">{fmtTime(row.lastChangedAt)}</p>
                  <p className="text-slate-500">há {row.lastChangedAgeSec ?? "-"}s</p>
                </td>
                <td>
                  <div className="flex items-center gap-2">
                    <div className="w-12 shrink-0">
                      <MiniBarV2 pct={Math.round(row.confidenceScore * 100)} tone="green" />
                    </div>
                    <span className="font-mono text-[11px] text-slate-300">{formatPercent(row.confidenceScore, 0)}</span>
                  </div>
                </td>
                <td>
                  <button
                    type="button"
                    onClick={() => toggleFavorite(row.key)}
                    aria-label={favorites.has(row.key) ? "Remover dos favoritos" : "Adicionar aos favoritos"}
                    className={`grid h-6 w-6 place-items-center rounded transition-colors ${
                      favorites.has(row.key) ? "text-amber-300" : "text-slate-600 hover:text-slate-300"
                    }`}
                  >
                    <IconStar className="h-3.5 w-3.5" filled={favorites.has(row.key)} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {visible.length === 0 && (
        <div className="empty-v2 mt-3">
          <p className="text-sm font-semibold text-slate-200">
            {onlyFavorites ? "Nenhum mercado favoritado ainda" : "Nenhum mercado disponível"}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {onlyFavorites
              ? "Clique na estrela de um mercado para favoritá-lo."
              : "Aguarde a próxima captura de odds."}
          </p>
        </div>
      )}
    </section>
  );
}
