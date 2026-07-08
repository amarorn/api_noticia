import { Fragment, useMemo, useState } from "react";
import type { MarketOperationalRow } from "@/presentation/components/live-operational/useMarketOperationalRows";
import { formatOdd, formatPercent } from "@/presentation/components/live-operational/liveOperationalUtils";
import { ChipV2, MiniBarV2, StatusPillV2, type ToneV2 } from "./live-ui-v2";

type SortKey = "ev" | "confidence" | "pressure" | "recent" | "changed";
type StatusFilter = "todos" | "ativos" | "suspensos";

const PERIODS = ["Todos", "1T", "2T", "Jogo"] as const;
const TYPES = ["Todos", "Gols", "Escanteios", "Cartões", "Handicap", "Resultado", "Outros"] as const;

const STATUS_TONE: Record<MarketOperationalRow["status"], { label: string; tone: ToneV2 }> = {
  ativo: { label: "Ativo", tone: "green" },
  aguardar: { label: "Aguardar", tone: "cyan" },
  evitar: { label: "Evitar", tone: "red" },
};

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

export function LiveMarketsTableV2({ rows }: { rows: MarketOperationalRow[] }) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("ev");
  const [positiveOnly, setPositiveOnly] = useState(false);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("todos");
  const [period, setPeriod] = useState<(typeof PERIODS)[number]>("Todos");
  const [type, setType] = useState<(typeof TYPES)[number]>("Todos");
  const [expanded, setExpanded] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows
      .filter((row) => !q || `${row.label} ${row.market} ${row.outcome}`.toLowerCase().includes(q))
      .filter((row) => !positiveOnly || row.expectedValue > 0)
      .filter((row) => statusFilter === "todos" || (statusFilter === "ativos" ? row.status === "ativo" : row.status === "evitar"))
      .filter((row) => period === "Todos" || row.period === period)
      .filter((row) => type === "Todos" || row.type === type)
      .sort((a, b) => {
        if (sort === "confidence") return b.confidenceScore - a.confidenceScore;
        if (sort === "pressure") return b.pressureEstimate - a.pressureEstimate;
        if (sort === "recent") return (a.lastChangedAgeSec ?? 9999) - (b.lastChangedAgeSec ?? 9999);
        if (sort === "changed") return Date.parse(b.lastChangedAt ?? "") - Date.parse(a.lastChangedAt ?? "");
        return b.expectedValue - a.expectedValue;
      });
  }, [period, positiveOnly, query, rows, sort, statusFilter, type]);

  return (
    <section className="panel-v2 w-full max-w-full p-4 sm:p-5">
      <div className="min-w-0">
        <h2 className="text-xs font-black uppercase tracking-[0.12em] text-slate-400">Mercados</h2>
        <p className="text-xs text-slate-500" title="Estimada por movimento de odds, probabilidade implicita e distancia da odd justa.">
          Pressão implícita estimada por odds, probabilidade implícita e odd justa.
        </p>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-6">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar mercado"
          className="field-v2 sm:col-span-2"
        />
        <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)} className="field-v2">
          <option value="ev">Maior EV</option>
          <option value="confidence">Maior confiança</option>
          <option value="pressure">Maior pressão</option>
          <option value="recent">Mais recente</option>
          <option value="changed">Última alteração</option>
        </select>
        <select value={period} onChange={(e) => setPeriod(e.target.value as (typeof PERIODS)[number])} className="field-v2">
          {PERIODS.map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
        <select value={type} onChange={(e) => setType(e.target.value as (typeof TYPES)[number])} className="field-v2">
          {TYPES.map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
        <div className="flex gap-2">
          <Toggle label="EV+" active={positiveOnly} onClick={() => setPositiveOnly((v) => !v)} />
          <Toggle label="Ativos" active={statusFilter === "ativos"} onClick={() => setStatusFilter((v) => (v === "ativos" ? "todos" : "ativos"))} />
          <Toggle
            label="Suspensos"
            active={statusFilter === "suspensos"}
            onClick={() => setStatusFilter((v) => (v === "suspensos" ? "todos" : "suspensos"))}
          />
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
              <th>Pressão estimada</th>
              <th>Direção</th>
              <th>Última mudança</th>
              <th>Confiança</th>
              <th>Status</th>
              <th>Ação</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.05]">
            {filtered.map((row) => (
              <Fragment key={row.key}>
                <tr
                  onClick={() => setExpanded((cur) => (cur === row.key ? null : row.key))}
                  className="cursor-pointer bg-transparent transition-colors hover:bg-white/[0.04]"
                >
                  <td className="max-w-[240px]">
                    <p className="truncate font-semibold text-white" title={row.label}>{row.label}</p>
                    <p className="text-slate-500">{row.type} · {row.period}</p>
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
                      <span className="font-mono text-[11px] text-slate-300">{row.pressureEstimate}%</span>
                    </div>
                  </td>
                  <td>
                    <ChipV2 label={DIRECTION_TONE[row.direction].label} tone={DIRECTION_TONE[row.direction].tone} />
                  </td>
                  <td>
                    <p className="font-mono text-slate-200">{fmtTime(row.lastChangedAt)}</p>
                    <p className="text-slate-500">há {row.lastChangedAgeSec ?? "-"}s</p>
                  </td>
                  <td className="font-mono text-slate-200">{formatPercent(row.confidenceScore, 0)}</td>
                  <td>
                    <StatusPillV2 label={STATUS_TONE[row.status].label} tone={STATUS_TONE[row.status].tone} />
                  </td>
                  <td className="text-slate-400">{row.action}</td>
                </tr>
                {expanded === row.key && (
                  <tr className="bg-black/20">
                    <td colSpan={11} className="px-3 py-3 text-xs text-slate-400">
                      Prob. modelo {formatPercent(row.modelProb)} · Prob. implícita {formatPercent(row.impliedProb)} · Edge{" "}
                      {row.edgePp.toFixed(1)} pp · Stake sugerida R$ {row.suggestedStakeValue.toFixed(2)}
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {filtered.length === 0 && (
        <div className="empty-v2 mt-3">
          <p className="text-sm font-semibold text-slate-200">Nenhum mercado encontrado</p>
          <p className="mt-1 text-xs text-slate-500">Ajuste os filtros ou aguarde a proxima captura de odds.</p>
        </div>
      )}
    </section>
  );
}

function Toggle({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex-1 rounded-lg border px-2 py-2 text-[11px] font-bold transition-colors sm:flex-none sm:px-3 ${
        active ? "border-emerald-400/35 bg-emerald-400/10 text-emerald-300" : "border-white/8 bg-black/20 text-slate-400 hover:text-slate-200"
      }`}
    >
      {label}
    </button>
  );
}
