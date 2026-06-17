import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/infrastructure/api/client";
import { PageHeader } from "@/presentation/components/layout/PageHeader";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { EmptyState, ErrorState } from "@/presentation/components/ui/EmptyState";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { FilterBar, FilterChip } from "@/presentation/components/ui/FilterBar";

interface SettledBet {
  id?: string;
  home_team?: string;
  away_team?: string;
  market?: string;
  outcome?: string;
  stake?: number;
  odd?: number;
  result?: string;
  profit?: number;
  settled_at?: string;
  predicted_outcome?: string;
}

interface OpenBet {
  id: string;
  home_team: string;
  away_team: string;
  market: string;
  outcome: string;
  stake: number;
  odd?: number;
  status?: string;
}

type StatusFilter = "all" | "won" | "lost" | "pending" | "cashout";

function formatBRL(value: number): string {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value);
}

function normalizeStatus(result?: string, status?: string): StatusFilter | "won" | "lost" | "cashout" {
  const raw = (result || status || "").toLowerCase();
  if (raw.includes("win") || raw === "ganhou" || raw === "won") return "won";
  if (raw.includes("cash")) return "cashout";
  if (raw.includes("loss") || raw === "perdeu" || raw === "lost") return "lost";
  return "pending";
}

export function HistoricoPage() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [marketFilter, setMarketFilter] = useState<string>("all");
  const [teamQuery, setTeamQuery] = useState("");

  const performanceQuery = useQuery({
    queryKey: ["bet-performance"],
    queryFn: () =>
      apiFetch<{ report: Record<string, unknown> | null; message?: string }>(
        "/user/bet-performance",
      ),
  });

  const settledQuery = useQuery({
    queryKey: ["user-settled-bets"],
    queryFn: () => apiFetch<{ bets: SettledBet[]; count: number }>("/user/settled-bets"),
  });

  const openQuery = useQuery({
    queryKey: ["user-open-bets-historico"],
    queryFn: () => apiFetch<{ bets: OpenBet[] }>("/user/open-bets"),
  });

  const summary = performanceQuery.data?.report?.summary as
    | {
        total_bets: number;
        total_stake: number;
        net_profit: number;
        roi_pct: number;
        win_rate_pct: number;
      }
    | undefined;

  const rows = useMemo(() => {
    const settled = (settledQuery.data?.bets ?? []).map((bet) => ({
      ...bet,
      status: normalizeStatus(bet.result),
      kind: "settled" as const,
    }));
    const open = (openQuery.data?.bets ?? []).map((bet) => ({
      ...bet,
      status: "pending" as const,
      kind: "open" as const,
      result: "pendente",
      profit: undefined,
      settled_at: undefined,
    }));
    return [...open, ...settled];
  }, [settledQuery.data?.bets, openQuery.data?.bets]);

  const markets = useMemo(() => {
    const set = new Set<string>();
    rows.forEach((row) => {
      const m = (row.market || "unknown").toLowerCase();
      if (m !== "unknown") set.add(m);
    });
    return ["all", ...Array.from(set).sort()];
  }, [rows]);

  const filtered = useMemo(() => {
    const q = teamQuery.trim().toLowerCase();
    return rows.filter((row) => {
      if (statusFilter !== "all" && row.status !== statusFilter) return false;
      if (marketFilter !== "all" && (row.market || "").toLowerCase() !== marketFilter) return false;
      if (!q) return true;
      const home = (row.home_team || "").toLowerCase();
      const away = (row.away_team || "").toLowerCase();
      return home.includes(q) || away.includes(q);
    });
  }, [rows, statusFilter, marketFilter, teamQuery]);

  const isLoading = settledQuery.isLoading || openQuery.isLoading;
  const isError = settledQuery.isError || openQuery.isError;

  return (
    <PageTransition className="space-y-5">
      <PageHeader
        title="Histórico de palpites"
        subtitle="Apostas abertas e finalizadas — previsto vs. resultado real"
      >
        <Link
          to="/validate"
          className="rounded-lg border border-slate-600/50 px-3 py-1.5 text-xs text-slate-300 hover:border-neon-green/40 hover:text-neon-green"
        >
          Backtest WC
        </Link>
      </PageHeader>

      {summary && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          {[
            { label: "Apostas", value: String(summary.total_bets) },
            { label: "Investido", value: formatBRL(summary.total_stake) },
            {
              label: "Lucro líquido",
              value: formatBRL(summary.net_profit),
              color: summary.net_profit >= 0 ? "text-emerald-400" : "text-red-400",
            },
            { label: "ROI", value: `${summary.roi_pct.toFixed(1)}%` },
            { label: "Hit rate", value: `${summary.win_rate_pct.toFixed(0)}%` },
          ].map((card) => (
            <div key={card.label} className="glass-card p-3">
              <p className="text-[11px] text-slate-500">{card.label}</p>
              <p className={`font-mono text-lg font-bold ${card.color || "text-white"}`}>
                {card.value}
              </p>
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        <input
          type="search"
          placeholder="Filtrar seleção..."
          value={teamQuery}
          onChange={(e) => setTeamQuery(e.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-900/60 px-3 py-2 text-sm text-white"
        />
      </div>

      <FilterBar label="Status">
        {(["all", "pending", "won", "lost", "cashout"] as StatusFilter[]).map((status) => (
          <FilterChip
            key={status}
            active={statusFilter === status}
            onClick={() => setStatusFilter(status)}
            label={
              status === "all"
                ? "Todos"
                : status === "pending"
                  ? "Pendente"
                  : status === "won"
                    ? "Ganhou"
                    : status === "lost"
                      ? "Perdeu"
                      : "Cash-out"
            }
          />
        ))}
      </FilterBar>

      <FilterBar label="Mercado">
        {markets.map((market) => (
          <FilterChip
            key={market}
            active={marketFilter === market}
            onClick={() => setMarketFilter(market)}
            label={market === "all" ? "Todos" : market}
          />
        ))}
      </FilterBar>

      {isLoading ? (
        <DashboardSkeleton />
      ) : isError ? (
        <ErrorState
          message="Não foi possível carregar o histórico de apostas."
          onRetry={() => {
            void settledQuery.refetch();
            void openQuery.refetch();
          }}
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="Nenhum palpite registrado"
          description="Cadastre apostas na tela Ao Vivo ou importe finalizados via extensão Superbet."
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-700/50">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-700/50 text-slate-400">
              <tr>
                <th className="px-3 py-2">Jogo</th>
                <th className="px-3 py-2">Mercado</th>
                <th className="px-3 py-2">Palpite</th>
                <th className="px-3 py-2">Odd</th>
                <th className="px-3 py-2">Stake</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">P&L</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, idx) => (
                <tr key={`${row.id ?? idx}-${row.kind}`} className="border-b border-slate-800/60">
                  <td className="px-3 py-2 text-white">
                    {row.home_team} × {row.away_team}
                  </td>
                  <td className="px-3 py-2 font-mono text-slate-300">{row.market || "—"}</td>
                  <td className="px-3 py-2">
                    {row.outcome ||
                      ("predicted_outcome" in row ? row.predicted_outcome : undefined) ||
                      "—"}
                  </td>
                  <td className="px-3 py-2 font-mono">{row.odd?.toFixed(2) ?? "—"}</td>
                  <td className="px-3 py-2 font-mono">{formatBRL(row.stake ?? 0)}</td>
                  <td className="px-3 py-2 capitalize">{String(row.status)}</td>
                  <td className="px-3 py-2 font-mono">
                    {row.profit != null ? formatBRL(row.profit) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!performanceQuery.data?.report && !performanceQuery.isLoading && (
        <p className="text-xs text-slate-500">
          Métricas agregadas aparecem após importar apostas finalizadas (
          <Link to="/performance" className="text-neon-green hover:underline">
            Performance
          </Link>
          ).
        </p>
      )}
    </PageTransition>
  );
}
