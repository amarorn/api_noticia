import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/infrastructure/api/client";
import { PageHeader } from "@/presentation/components/layout/PageHeader";
import { PageTransition } from "@/presentation/components/layout/PageTransition";

// ─── Tipos ──────────────────────────────────────────────────────────────────

interface MarketPerf {
  market: string;
  total_bets: number;
  wins: number;
  losses: number;
  cashouts: number;
  total_stake: number;
  total_return: number;
  roi_pct: number;
  avg_odd: number;
  win_rate_pct: number;
}

interface OddRangePerf {
  range: string;
  total_bets: number;
  wins: number;
  losses: number;
  total_stake: number;
  total_return: number;
  roi_pct: number;
  win_rate_pct: number;
}

interface LossPattern {
  type: string;
  description: string;
  severity: string;
  evidence: string;
  suggestion: string;
}

interface PerformanceData {
  summary: {
    total_bets: number;
    total_stake: number;
    total_return: number;
    net_profit: number;
    roi_pct: number;
    win_rate_pct: number;
    avg_odd: number;
    best_market: string;
    worst_market: string;
  };
  by_market: MarketPerf[];
  by_odd_range: OddRangePerf[];
  loss_patterns: LossPattern[];
  suggestions: string[];
}

// ─── Formatadores ───────────────────────────────────────────────────────────

function formatBRL(value: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    minimumFractionDigits: 2,
  }).format(value);
}

function roiColor(roi: number): string {
  if (roi > 10) return "text-emerald-400";
  if (roi > 0) return "text-emerald-300";
  if (roi > -10) return "text-yellow-400";
  return "text-red-400";
}

function severityBadge(severity: string) {
  const colors: Record<string, string> = {
    high: "bg-red-500/20 text-red-400 border-red-500/30",
    medium: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    low: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  };
  return colors[severity] || colors.low;
}

// ─── Componentes ────────────────────────────────────────────────────────────

function SummaryCards({ data }: { data: PerformanceData["summary"] }) {
  const cards = [
    { label: "Total Apostas", value: String(data.total_bets) },
    { label: "Investido", value: formatBRL(data.total_stake) },
    { label: "Retorno", value: formatBRL(data.total_return) },
    {
      label: "Lucro Liquido",
      value: formatBRL(data.net_profit),
      color: data.net_profit >= 0 ? "text-emerald-400" : "text-red-400",
    },
    {
      label: "ROI",
      value: `${data.roi_pct.toFixed(1)}%`,
      color: roiColor(data.roi_pct),
    },
    {
      label: "Win Rate",
      value: `${data.win_rate_pct.toFixed(0)}%`,
      color: data.win_rate_pct >= 40 ? "text-emerald-400" : "text-yellow-400",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {cards.map((c) => (
        <div
          key={c.label}
          className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50"
        >
          <div className="text-xs text-slate-400 mb-1">{c.label}</div>
          <div className={`text-lg font-bold ${c.color || "text-white"}`}>
            {c.value}
          </div>
        </div>
      ))}
    </div>
  );
}

function MarketTable({ markets }: { markets: MarketPerf[] }) {
  if (!markets.length) return null;
  return (
    <div className="bg-slate-800/50 rounded-lg border border-slate-700/50 overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-700/50">
        <h3 className="text-sm font-semibold text-white">Performance por Mercado</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-400 border-b border-slate-700/50">
              <th className="text-left px-4 py-2">Mercado</th>
              <th className="text-center px-2 py-2">Apostas</th>
              <th className="text-center px-2 py-2">W/L/C</th>
              <th className="text-right px-2 py-2">Stake</th>
              <th className="text-right px-2 py-2">Retorno</th>
              <th className="text-right px-2 py-2">ROI</th>
              <th className="text-right px-4 py-2">Win%</th>
            </tr>
          </thead>
          <tbody>
            {markets.map((m) => (
              <tr
                key={m.market}
                className="border-b border-slate-700/30 hover:bg-slate-700/30"
              >
                <td className="px-4 py-2 font-medium text-white capitalize">
                  {m.market}
                </td>
                <td className="text-center px-2 py-2 text-slate-300">
                  {m.total_bets}
                </td>
                <td className="text-center px-2 py-2 text-slate-300">
                  <span className="text-emerald-400">{m.wins}</span>/
                  <span className="text-red-400">{m.losses}</span>/
                  <span className="text-yellow-400">{m.cashouts}</span>
                </td>
                <td className="text-right px-2 py-2 text-slate-300">
                  {formatBRL(m.total_stake)}
                </td>
                <td className="text-right px-2 py-2 text-slate-300">
                  {formatBRL(m.total_return)}
                </td>
                <td className={`text-right px-2 py-2 font-bold ${roiColor(m.roi_pct)}`}>
                  {m.roi_pct > 0 ? "+" : ""}
                  {m.roi_pct.toFixed(1)}%
                </td>
                <td className="text-right px-4 py-2 text-slate-300">
                  {m.win_rate_pct.toFixed(0)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function OddRangeTable({ ranges }: { ranges: OddRangePerf[] }) {
  if (!ranges.length) return null;
  return (
    <div className="bg-slate-800/50 rounded-lg border border-slate-700/50 overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-700/50">
        <h3 className="text-sm font-semibold text-white">Performance por Faixa de Odd</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-400 border-b border-slate-700/50">
              <th className="text-left px-4 py-2">Faixa</th>
              <th className="text-center px-2 py-2">Apostas</th>
              <th className="text-center px-2 py-2">Wins</th>
              <th className="text-right px-2 py-2">Stake</th>
              <th className="text-right px-2 py-2">Retorno</th>
              <th className="text-right px-2 py-2">ROI</th>
              <th className="text-right px-4 py-2">Win%</th>
            </tr>
          </thead>
          <tbody>
            {ranges.map((r) => (
              <tr
                key={r.range}
                className="border-b border-slate-700/30 hover:bg-slate-700/30"
              >
                <td className="px-4 py-2 font-medium text-white">{r.range}</td>
                <td className="text-center px-2 py-2 text-slate-300">
                  {r.total_bets}
                </td>
                <td className="text-center px-2 py-2 text-emerald-400">
                  {r.wins}
                </td>
                <td className="text-right px-2 py-2 text-slate-300">
                  {formatBRL(r.total_stake)}
                </td>
                <td className="text-right px-2 py-2 text-slate-300">
                  {formatBRL(r.total_return)}
                </td>
                <td className={`text-right px-2 py-2 font-bold ${roiColor(r.roi_pct)}`}>
                  {r.roi_pct > 0 ? "+" : ""}
                  {r.roi_pct.toFixed(1)}%
                </td>
                <td className="text-right px-4 py-2 text-slate-300">
                  {r.win_rate_pct.toFixed(0)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LossPatterns({ patterns }: { patterns: LossPattern[] }) {
  if (!patterns.length) return null;
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-white">Padroes de Perda Detectados</h3>
      {patterns.map((p, i) => (
        <div
          key={i}
          className={`rounded-lg border p-4 ${severityBadge(p.severity)}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-bold uppercase">{p.severity}</span>
            <span className="text-sm font-medium">{p.description}</span>
          </div>
          <p className="text-xs opacity-80 mb-2">{p.evidence}</p>
          <p className="text-xs font-medium opacity-90">
            Sugestao: {p.suggestion}
          </p>
        </div>
      ))}
    </div>
  );
}

function Suggestions({ items }: { items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="bg-slate-800/50 rounded-lg border border-slate-700/50 p-4">
      <h3 className="text-sm font-semibold text-white mb-3">Sugestoes de Melhoria</h3>
      <ul className="space-y-2">
        {items.map((s, i) => (
          <li key={i} className="text-xs text-slate-300 flex items-start gap-2">
            <span className="text-emerald-400 mt-0.5">&#9654;</span>
            <span>{s}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ─── Pagina Principal ───────────────────────────────────────────────────────

export function BetPerformancePage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["bet-performance"],
    queryFn: () =>
      apiFetch<{ report: PerformanceData | null; message?: string }>(
        "/user/bet-performance",
      ),
  });

  return (
    <PageTransition>
      <div className="space-y-6">
        <PageHeader
          title="Performance de Apostas"
          subtitle="Analise de ROI, padroes de perda e sugestoes de melhoria"
        />

        {isLoading && (
          <div className="text-center py-12 text-slate-400">Carregando...</div>
        )}

        {error && (
          <div className="text-center py-12 text-red-400">
            Erro ao carregar: {(error as Error).message}
          </div>
        )}

        {data && !data.report && (
          <div className="text-center py-12">
            <p className="text-slate-400 mb-2">
              Nenhuma aposta finalizada encontrada.
            </p>
            <p className="text-xs text-slate-500">
              Use a extensao Superbet para capturar apostas da aba
              &quot;Finalizados&quot;.
            </p>
          </div>
        )}

        {data?.report && (
          <>
            <SummaryCards data={data.report.summary} />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <MarketTable markets={data.report.by_market} />
              <OddRangeTable ranges={data.report.by_odd_range} />
            </div>

            <LossPatterns patterns={data.report.loss_patterns} />
            <Suggestions items={data.report.suggestions} />
          </>
        )}
      </div>
    </PageTransition>
  );
}
