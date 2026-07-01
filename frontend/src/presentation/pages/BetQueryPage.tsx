import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/infrastructure/api/client";
import { PageHeader } from "@/presentation/components/layout/PageHeader";
import { PageTransition } from "@/presentation/components/layout/PageTransition";

// ─── Tipos ──────────────────────────────────────────────────────────────────

interface PickData {
  market: string;
  outcome: string;
  target_value?: string | null;
  model_prob?: number | null;
  market_odd?: number | null;
  expected_value?: number | null;
  edge_pp?: number | null;
}

interface ScoreBreakdown {
  ev_score: number;
  odd_score: number;
  market_score: number;
  timing_score: number;
  combo_penalty: number;
  total_score: number;
}

interface ScoredBet {
  bet_id: string;
  event_name: string;
  home_team: string;
  away_team: string;
  picks: PickData[];
  stake: number;
  odds_placed: number;
  potential_return: number;
  cashout_value: number | null;
  ticket_code: string | null;
  minute: number | null;
  status: string;
  captured_at: string;
  superbet_event_id: number | null;
  source: string;
  score: ScoreBreakdown;
  recommendation: string;
  reasoning: string;
  potential_actions: string[];
}

interface QuerySummary {
  n_high_potential: number;
  n_medium_potential: number;
  n_low_potential: number;
  n_poor_potential: number;
  total_open_bets: number;
  total_scored: number;
  total_potential_return: number;
  total_staked: number;
  avg_score: number;
  has_history: boolean;
  best_odd_range: string;
  best_market: string;
  overall_roi: number;
}

interface UserPatterns {
  odd_range_stats: Record<string, { n_bets: number; wins: number; win_rate: number; roi: number; avg_stake: number }>;
  market_stats: Record<string, { n_bets: number; wins: number; win_rate: number; roi: number }>;
  combo_stats: Record<string, { n_bets: number; wins: number; win_rate: number; roi: number }>;
  overall_roi: number;
  best_odd_range: string;
  best_market: string;
  has_history: boolean;
  total_settled: number;
}

interface QueryResult {
  total_open_bets: number;
  summary: QuerySummary;
  user_patterns: UserPatterns;
  scored_bets: ScoredBet[];
}

interface QueryResponse {
  error: string | null;
  result: QueryResult | null;
  message: string;
}

// ─── Formatadores ───────────────────────────────────────────────────────────

function formatBRL(value: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    minimumFractionDigits: 2,
  }).format(value);
}

function scoreColor(score: number): string {
  if (score >= 75) return "text-emerald-400";
  if (score >= 55) return "text-emerald-300";
  if (score >= 35) return "text-yellow-400";
  if (score >= 20) return "text-orange-400";
  return "text-red-400";
}

function scoreBg(score: number): string {
  if (score >= 75) return "bg-emerald-500/10 border-emerald-500/30";
  if (score >= 55) return "bg-emerald-500/5 border-emerald-500/20";
  if (score >= 35) return "bg-yellow-500/10 border-yellow-500/30";
  if (score >= 20) return "bg-orange-500/10 border-orange-500/30";
  return "bg-red-500/10 border-red-500/30";
}

function recBadge(rec: string): string {
  switch (rec) {
    case "HOLD":
      return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
    case "MONITOR":
      return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
    case "CASHOUT":
      return "bg-orange-500/20 text-orange-400 border-orange-500/30";
    case "AVOID":
      return "bg-red-500/20 text-red-400 border-red-500/30";
    default:
      return "bg-slate-500/20 text-slate-400 border-slate-500/30";
  }
}

function recEmoji(rec: string): string {
  switch (rec) {
    case "HOLD": return "✓";
    case "MONITOR": return "👁";
    case "CASHOUT": return "⚠";
    case "AVOID": return "✗";
    default: return "?";
  }
}

// ─── Componentes ────────────────────────────────────────────────────────────

function ScoreBar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 text-slate-400 text-right">{label}</span>
      <div className="flex-1 h-2 bg-white/10 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-8 text-right font-mono text-slate-300">{value.toFixed(0)}</span>
    </div>
  );
}

function ScoreBreakdown({ score }: { score: ScoreBreakdown }) {
  return (
    <div className="space-y-1 mt-2">
      <ScoreBar label="EV" value={score.ev_score} max={25} color="bg-blue-400" />
      <ScoreBar label="Odd" value={score.odd_score} max={25} color="bg-purple-400" />
      <ScoreBar label="Mercado" value={score.market_score} max={20} color="bg-cyan-400" />
      <ScoreBar label="Timing" value={score.timing_score} max={15} color="bg-amber-400" />
      <ScoreBar label="Combo" value={-score.combo_penalty} max={-15} color="bg-red-400" />
    </div>
  );
}

function SummaryCards({ summary }: { summary: QuerySummary }) {
  const cards = [
    {
      label: "Bilhetes Abertos",
      value: String(summary.total_open_bets),
      hint: `${summary.total_scored} analisados`,
    },
    {
      label: "Alto Potencial",
      value: String(summary.n_high_potential),
      color: "text-emerald-400",
      hint: "Score ≥ 75",
    },
    {
      label: "Potencial Médio",
      value: String(summary.n_medium_potential),
      color: "text-emerald-300",
      hint: "Score 55-74",
    },
    {
      label: "Incerto",
      value: String(summary.n_low_potential),
      color: "text-yellow-400",
      hint: "Score 35-54",
    },
    {
      label: "Baixo Potencial",
      value: String(summary.n_poor_potential),
      color: "text-red-400",
      hint: "Score < 35",
    },
    {
      label: "Retorno Potencial",
      value: formatBRL(summary.total_potential_return),
      hint: `Stake ${formatBRL(summary.total_staked)}`,
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
          {c.hint && <div className="text-[10px] text-slate-500 mt-1">{c.hint}</div>}
        </div>
      ))}
    </div>
  );
}

function UserPatternsPanel({ patterns }: { patterns: UserPatterns }) {
  if (!patterns.has_history) {
    return (
      <div className="bg-slate-800/50 rounded-lg border border-slate-700/50 p-4">
        <h3 className="text-sm font-semibold text-white mb-2">Seu Histórico</h3>
        <p className="text-xs text-slate-400">
          Nenhuma aposta liquidada encontrada. A análise usa defaults conservadores.
          Suba apostas finalizadas para scores mais precisos.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-slate-800/50 rounded-lg border border-slate-700/50 p-4 space-y-4">
      <h3 className="text-sm font-semibold text-white">Seu Perfil (Baseado em {patterns.total_settled} apostas)</h3>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="rounded-xl bg-white/5 px-3 py-2">
          <div className="text-[10px] uppercase text-slate-500">ROI Geral</div>
          <div className={`text-lg font-bold ${patterns.overall_roi >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {patterns.overall_roi >= 0 ? "+" : ""}{patterns.overall_roi.toFixed(1)}%
          </div>
        </div>
        <div className="rounded-xl bg-white/5 px-3 py-2">
          <div className="text-[10px] uppercase text-slate-500">Melhor Faixa Odd</div>
          <div className="text-lg font-bold text-emerald-400">{patterns.best_odd_range || "—"}</div>
        </div>
        <div className="rounded-xl bg-white/5 px-3 py-2">
          <div className="text-[10px] uppercase text-slate-500">Melhor Mercado</div>
          <div className="text-lg font-bold text-emerald-400 capitalize">{patterns.best_market || "—"}</div>
        </div>
        <div className="rounded-xl bg-white/5 px-3 py-2">
          <div className="text-[10px] uppercase text-slate-500">Apostas Analisadas</div>
          <div className="text-lg font-bold text-slate-200">{patterns.total_settled}</div>
        </div>
      </div>

      {/* Odd Range Stats */}
      {Object.keys(patterns.odd_range_stats).length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-slate-400 mb-2">Performance por Faixa de Odd</h4>
          <div className="space-y-1">
            {Object.entries(patterns.odd_range_stats)
              .sort((a, b) => b[1].roi - a[1].roi)
              .map(([range, stats]) => (
                <div key={range} className="flex items-center justify-between text-xs py-1 border-b border-white/5">
                  <span className="text-slate-300">{range}</span>
                  <span className="text-slate-500">{stats.n_bets} apostas · {stats.wins} wins</span>
                  <span className={`font-mono font-bold ${stats.roi >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {stats.roi >= 0 ? "+" : ""}{stats.roi.toFixed(1)}%
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Market Stats */}
      {Object.keys(patterns.market_stats).length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-slate-400 mb-2">Performance por Mercado</h4>
          <div className="space-y-1">
            {Object.entries(patterns.market_stats)
              .sort((a, b) => b[1].roi - a[1].roi)
              .map(([market, stats]) => (
                <div key={market} className="flex items-center justify-between text-xs py-1 border-b border-white/5">
                  <span className="capitalize text-slate-300">{market}</span>
                  <span className="text-slate-500">{stats.n_bets} apostas · {stats.wins} wins</span>
                  <span className={`font-mono font-bold ${stats.roi >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {stats.roi >= 0 ? "+" : ""}{stats.roi.toFixed(1)}%
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

function BetCard({ bet }: { bet: ScoredBet }) {
  const [expanded, setExpanded] = useState(false);

  const pickSummary = bet.picks
    .map((p) => {
      const m = p.market === "h2h" ? "1X2" : p.market;
      return `${m}: ${p.outcome}`;
    })
    .join(" · ");

  return (
    <div className={`rounded-xl border p-4 transition-colors ${scoreBg(bet.score.total_score)}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-lg font-bold ${scoreColor(bet.score.total_score)}`}>
              {bet.score.total_score.toFixed(0)}
            </span>
            <span className={`px-2 py-0.5 rounded text-xs font-bold border ${recBadge(bet.recommendation)}`}>
              {recEmoji(bet.recommendation)} {bet.recommendation}
            </span>
            {bet.ticket_code && (
              <span className="text-[10px] text-slate-500 font-mono">{bet.ticket_code}</span>
            )}
          </div>
          <h4 className="text-sm font-semibold text-white mt-1 truncate">
            {bet.home_team} × {bet.away_team}
          </h4>
          <p className="text-xs text-slate-400 mt-0.5">{pickSummary}</p>
        </div>
        <div className="text-right shrink-0">
          <div className="text-sm font-bold text-white">{bet.odds_placed.toFixed(2)}</div>
          <div className="text-xs text-slate-400">odd</div>
          <div className="text-xs text-emerald-400 mt-1">{formatBRL(bet.potential_return)}</div>
        </div>
      </div>

      <p className="text-xs text-slate-300 mt-2 leading-relaxed">{bet.reasoning}</p>

      <button
        onClick={() => setExpanded(!expanded)}
        className="mt-2 text-xs text-slate-500 hover:text-slate-300 transition-colors"
      >
        {expanded ? "▲ Ocultar detalhes" : "▼ Ver detalhes do score"}
      </button>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-white/10">
          <ScoreBreakdown score={bet.score} />

          <div className="mt-3 space-y-1">
            <div className="text-xs text-slate-400 font-semibold">Ações sugeridas:</div>
            {bet.potential_actions.map((action, i) => (
              <div key={i} className="text-xs text-slate-300 flex items-start gap-2">
                <span className="text-emerald-400 mt-0.5">▸</span>
                <span>{action}</span>
              </div>
            ))}
          </div>

          <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
            <div className="bg-white/5 rounded px-2 py-1">
              <span className="text-slate-500">Stake:</span>{" "}
              <span className="text-slate-300 font-mono">{formatBRL(bet.stake)}</span>
            </div>
            <div className="bg-white/5 rounded px-2 py-1">
              <span className="text-slate-500">Retorno:</span>{" "}
              <span className="text-emerald-400 font-mono">{formatBRL(bet.potential_return)}</span>
            </div>
            {bet.cashout_value !== null && bet.cashout_value > 0 && (
              <div className="bg-white/5 rounded px-2 py-1">
                <span className="text-slate-500">Cash-out:</span>{" "}
                <span className="text-yellow-400 font-mono">{formatBRL(bet.cashout_value)}</span>
              </div>
            )}
            {bet.minute !== null && (
              <div className="bg-white/5 rounded px-2 py-1">
                <span className="text-slate-500">Minuto:</span>{" "}
                <span className="text-slate-300 font-mono">{bet.minute}&apos;</span>
              </div>
            )}
            <div className="bg-white/5 rounded px-2 py-1">
              <span className="text-slate-500">Pernas:</span>{" "}
              <span className="text-slate-300 font-mono">{bet.picks.length}</span>
            </div>
            <div className="bg-white/5 rounded px-2 py-1">
              <span className="text-slate-500">Fonte:</span>{" "}
              <span className="text-slate-300">{bet.source}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Página Principal ───────────────────────────────────────────────────────

export function BetQueryPage() {
  const [minScore, setMinScore] = useState(0);
  const [filterRec, setFilterRec] = useState<string>("ALL");

  const { data, isLoading, error } = useQuery<QueryResponse>({
    queryKey: ["bet-query", minScore],
    queryFn: () =>
      apiFetch<QueryResponse>(`/user/bets/query?min_score=${minScore}&max_results=100`),
  });

  const filteredBets = data?.result?.scored_bets.filter((b) => {
    if (filterRec === "ALL") return true;
    return b.recommendation === filterRec;
  }) ?? [];

  const recCounts = {
    ALL: data?.result?.scored_bets.length ?? 0,
    HOLD: data?.result?.scored_bets.filter((b) => b.recommendation === "HOLD").length ?? 0,
    MONITOR: data?.result?.scored_bets.filter((b) => b.recommendation === "MONITOR").length ?? 0,
    CASHOUT: data?.result?.scored_bets.filter((b) => b.recommendation === "CASHOUT").length ?? 0,
    AVOID: data?.result?.scored_bets.filter((b) => b.recommendation === "AVOID").length ?? 0,
  };

  return (
    <PageTransition>
      <div className="space-y-3">
        <PageHeader
          title="Query Inteligente de Bilhetes"
          subtitle="Análise de potencial de retorno baseada no seu histórico"
        />

        {isLoading && (
          <div className="text-center py-12 text-slate-400">Analisando bilhetes...</div>
        )}

        {error && (
          <div className="text-center py-12 text-red-400">
            Erro ao carregar: {(error as Error).message}
          </div>
        )}

        {data && !data.result && (
          <div className="text-center py-12">
            <p className="text-slate-400 mb-2">Nenhum bilhete aberto encontrado.</p>
            <p className="text-xs text-slate-500">
              Cadastre apostas abertas via extensão ou manualmente para ver a análise.
            </p>
          </div>
        )}

        {data?.result && (
          <>
            {/* Summary */}
            <SummaryCards summary={data.result.summary} />

            {/* User Patterns */}
            <UserPatternsPanel patterns={data.result.user_patterns} />

            {/* Filters */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-slate-400">Filtrar:</span>
              {(["ALL", "HOLD", "MONITOR", "CASHOUT", "AVOID"] as const).map((rec) => (
                <button
                  key={rec}
                  onClick={() => setFilterRec(rec)}
                  className={`px-3 py-1 rounded-lg text-xs font-medium border transition-colors ${
                    filterRec === rec
                      ? "bg-white/10 border-white/30 text-white"
                      : "bg-white/5 border-white/10 text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {rec === "ALL" ? "Todos" : rec} ({recCounts[rec]})
                </button>
              ))}
              <div className="ml-auto flex items-center gap-2">
                <span className="text-xs text-slate-400">Score mín:</span>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={minScore}
                  onChange={(e) => setMinScore(Number(e.target.value))}
                  className="w-24 accent-emerald-400"
                />
                <span className="text-xs text-slate-300 w-8">{minScore}</span>
              </div>
            </div>

            {/* Bet Cards */}
            <div className="space-y-3">
              {filteredBets.length === 0 && (
                <div className="text-center py-8 text-slate-500 text-sm">
                  Nenhum bilhete corresponde aos filtros selecionados.
                </div>
              )}
              {filteredBets.map((bet) => (
                <BetCard key={bet.bet_id} bet={bet} />
              ))}
            </div>
          </>
        )}
      </div>
    </PageTransition>
  );
}
