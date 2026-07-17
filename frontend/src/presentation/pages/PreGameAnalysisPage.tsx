import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/infrastructure/api/client";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { HeroPageHeader } from "@/presentation/components/layout/PageHeader";
import { LiveDashboardTabs } from "@/presentation/components/live-dashboard/LiveDashboardTabs";
import { LiveCopilotPanel } from "@/presentation/components/live-dashboard/LiveCopilotPanel";
import { Skeleton } from "@/presentation/components/ui/Skeleton";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { teamColor } from "@/data/teamColors";
import {
  usePregameResearchQuery,
  usePregameSummaryQuery,
  type PregameResearchResponse,
  type PregameSummaryResponse,
} from "@/presentation/hooks/usePregameLlmQueries";
import {
  usePregameCopilotAgentSession,
  usePregameCopilotQuery,
} from "@/presentation/hooks/usePregameCopilotSession";

// ── Types ────────────────────────────────────────────────────────────────────

interface TodayMatch {
  id: string;
  home_team: string;
  away_team: string;
  kickoff_utc: string;
  kickoff_local: string;
  kickoff_date: string;
  venue: string | null;
  city: string | null;
  group: string | null;
  phase: string;
  played: boolean;
  status?: string;
  home_score?: number | null;
  away_score?: number | null;
  prob_home: number;
  prob_draw: number;
  prob_away: number;
  prediction: string;
  confidence: number;
  poisson_score: string;
  expected_goals: string;
}

interface NextMatchHint {
  id?: string | null;
  home_team: string;
  away_team: string;
  phase?: string | null;
  kickoff?: string | null;
  kickoff_br?: string | null;
  eta_label?: string | null;
  venue?: string | null;
  city?: string | null;
}

interface TodayResponse {
  date: string;
  end_date: string;
  total: number;
  matches: TodayMatch[];
  next_match?: NextMatchHint | null;
}

interface Scoreline {
  score: string;
  prob: number;
}

interface Pick {
  market: string;
  label: string;
  model_prob: number;
  fair_odd: number | null;
  kelly_units: number;
  confidence: string;
}

interface ComboTicket {
  label: string;
  markets: string[];
  model_prob: number;
  fair_odd: number | null;
  kelly_units: number;
  confidence: string;
}

interface Ticket {
  singles: Pick[];
  combo: ComboTicket | null;
  note: string;
}

interface ResearchPick {
  rank: number;
  aposta: string;
  racional: string;
  nivel_confianca: "Alta" | "Média" | "Baixa";
}

interface ResearchSynthesis {
  resumo_executivo: string;
  favorito: string;
  confianca_geral: "Alta" | "Média" | "Baixa";
  principais_fatores: string[];
  alertas_risco: string[];
  escalacao_home: { status: string; lesoes_suspensoes: string[]; destaque: string };
  escalacao_away: { status: string; lesoes_suspensoes: string[]; destaque: string };
  arbitro: { nome: string; perfil: string; card_lambda?: number; penalty_rate?: number };
  analise_mercados: { resultado: string; over_under: string; btts: string; handicap?: string };
  picks_recomendados: ResearchPick[];
  placar_provavel: string;
  nota_final: string;
}

interface AnalysisResponse {
  home_team: string;
  away_team: string;
  phase: string;
  group: string | null;
  kickoff_utc?: string | null;
  kickoff_date?: string | null;
  kickoff_local?: string | null;
  venue?: string | null;
  city?: string | null;
  prediction: string;
  confidence: number;
  prob_home: number;
  prob_draw: number;
  prob_away: number;
  poisson_score: string;
  expected_goals: string;
  h2h_summary: string;
  top_scorelines: Scoreline[];
  picks: Pick[];
  ticket: Ticket;
  match_context: Record<string, unknown> | null;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatKickoff(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "America/Sao_Paulo",
    }) + " (Brasília)";
  } catch {
    return iso;
  }
}

function ProbBar({ home, draw, away, homeTeam, awayTeam }: {
  home: number; draw: number; away: number; homeTeam: string; awayTeam: string;
}) {
  const hPct = Math.round(home * 100);
  const dPct = Math.round(draw * 100);
  const aPct = Math.round(away * 100);
  return (
    <div className="space-y-1">
      <div className="flex text-xs text-slate-400 justify-between mb-1">
        <span>{homeTeam}</span>
        <span>Empate</span>
        <span>{awayTeam}</span>
      </div>
      <div className="flex h-6 rounded-full overflow-hidden text-xs font-semibold">
        <div className="flex items-center justify-center bg-blue-600 text-white transition-all" style={{ width: `${hPct}%` }}>
          {hPct > 10 ? `${hPct}%` : ""}
        </div>
        <div className="flex items-center justify-center bg-neutral-500 text-white transition-all" style={{ width: `${dPct}%` }}>
          {dPct > 10 ? `${dPct}%` : ""}
        </div>
        <div className="flex items-center justify-center bg-orange-500 text-white transition-all" style={{ width: `${aPct}%` }}>
          {aPct > 10 ? `${aPct}%` : ""}
        </div>
      </div>
      <div className="flex text-xs justify-between font-mono">
        <span className="text-blue-400">{hPct}%</span>
        <span className="text-slate-400">{dPct}%</span>
        <span className="text-orange-400">{aPct}%</span>
      </div>
    </div>
  );
}

// ── Tab system ───────────────────────────────────────────────────────────────

type Tab = "bilhete" | "resumo" | "placar" | "picks" | "research" | "h2h" | "contexto";

const TABS: { key: Tab; label: string }[] = [
  { key: "bilhete", label: "🎯 Bilhete" },
  { key: "resumo", label: "📋 Resumo" },
  { key: "placar", label: "⚽ Placares" },
  { key: "picks", label: "💰 Picks" },
  { key: "research", label: "🔬 Deep Research" },
  { key: "h2h", label: "📊 H2H" },
  { key: "contexto", label: "🔍 Contexto" },
];

function confBadgeClass(c?: string) {
  return c === "Alta"
    ? "text-emerald-400 bg-emerald-900/30 border-emerald-700/40"
    : c === "Média"
      ? "text-blue-400 bg-blue-900/30 border-blue-700/40"
      : "text-slate-400 bg-white/5 border-white/8";
}

function PregameSummaryCard({
  summary,
  isLoading,
  researchLoading,
}: {
  summary: PregameSummaryResponse | undefined;
  isLoading: boolean;
  researchLoading: boolean;
}) {
  if (isLoading) {
    return <Skeleton className="h-24 w-full rounded-xl" />;
  }
  if (!summary?.narrative) return null;

  return (
    <div className="rounded-xl border border-purple-500/30 bg-gradient-to-br from-purple-900/20 to-blue-900/10 p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="text-xs font-bold uppercase tracking-wider text-purple-300">
          Resumo IA
        </span>
        <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${confBadgeClass(summary.confianca)}`}>
          {summary.confianca}
        </span>
        {summary.from_cache && (
          <span className="text-xs text-slate-500">+ research em cache</span>
        )}
        {researchLoading && (
          <span className="text-xs text-slate-500 animate-pulse">Atualizando pesquisa…</span>
        )}
      </div>
      <p className="text-sm leading-relaxed text-slate-200">{summary.narrative}</p>
      {summary.modelo_vs_noticias && (
        <p className="mt-2 text-xs text-amber-300">{summary.modelo_vs_noticias}</p>
      )}
      {summary.alertas.length > 0 && (
        <ul className="mt-2 space-y-1">
          {summary.alertas.map((a, i) => (
            <li key={i} className="text-xs text-amber-200/90">⚠ {a}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Deep Research Panel ───────────────────────────────────────────────────────

function DeepResearchPanel({
  research,
  isFetching,
  error,
  onRefresh,
}: {
  home: string;
  away: string;
  phase: string;
  research: PregameResearchResponse | undefined;
  isFetching: boolean;
  error: Error | null;
  onRefresh: () => void;
}) {
  if (isFetching && !research) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3">
        <div className="animate-spin text-3xl">🔬</div>
        <div className="text-sm text-slate-400 text-center">
          Pesquisando e sintetizando com IA…
          <br /><span className="text-xs text-slate-600">Gemini + Perplexity</span>
        </div>
      </div>
    );
  }

  if (error && !research) {
    const msg = error instanceof Error ? error.message : "Falha na pesquisa com IA.";
    return (
      <div className="flex flex-col items-center justify-center py-10 gap-4 text-center px-4">
        <div className="text-3xl">⚠️</div>
        <div className="text-sm text-red-400 font-semibold">Falha na pesquisa</div>
        <div className="text-xs text-slate-500 max-w-sm">{msg}</div>
        <button
          onClick={onRefresh}
          className="mt-2 px-5 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-white text-sm font-semibold transition-colors"
        >
          Tentar novamente
        </button>
      </div>
    );
  }

  const data = research;
  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3">
        <div className="animate-spin text-3xl">🔬</div>
        <div className="text-sm text-slate-400">Aguardando Deep Research…</div>
      </div>
    );
  }

  const confColor = confBadgeClass;
  const s = data.synthesis as ResearchSynthesis | null;
  const isLocalSynthesis = data.provider?.startsWith("local:");
  const cacheInfo = data.from_cache && data.cached_at
    ? `Cache de ${Math.round((Date.now() / 1000 - data.cached_at) / 60)}min atrás`
    : "Resultado ao vivo";

  return (
    <div className="space-y-4">
      {/* Header info */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {data.from_cache && (
            <span className="text-xs text-slate-500 bg-white/5 px-2 py-0.5 rounded-full">{cacheInfo}</span>
          )}
          {isLocalSynthesis && (
            <span className="text-xs text-emerald-400 bg-emerald-900/20 border border-emerald-700/30 px-2 py-0.5 rounded-full">
              🏠 Análise Local
            </span>
          )}
          {Object.keys(data.errors).length > 0 && (
            <span className="text-xs text-amber-400 bg-amber-900/20 border border-amber-700/30 px-2 py-0.5 rounded-full">
              ⚠️ Parcial
            </span>
          )}
        </div>
        <button
          onClick={onRefresh}
          className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
        >
          ↻ Atualizar
        </button>
      </div>

      {/* Errors */}
      {Object.entries(data.errors).map(([k, v]) => (
        <div key={k} className="rounded-lg bg-red-900/20 border border-red-700/30 p-2 text-xs text-red-300">
          <strong>{k}:</strong> {v}
        </div>
      ))}

      {s ? (
        <>
          {/* Resumo executivo */}
          <div className={`rounded-xl border p-4 ${isLocalSynthesis ? 'border-blue-700/30 bg-blue-900/10' : 'border-emerald-700/30 bg-emerald-900/10'}`}>
            <div className="flex items-center justify-between mb-2">
              <div className={`text-xs font-bold uppercase tracking-wider ${isLocalSynthesis ? 'text-blue-400' : 'text-emerald-400'}`}>
                {isLocalSynthesis ? 'Síntese Local (Modelo + Contexto)' : 'Síntese IA'}
              </div>
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${confColor(s.confianca_geral)}`}>
                Confiança {s.confianca_geral}
              </span>
            </div>
            <p className="text-sm text-slate-200 leading-relaxed">{s.resumo_executivo}</p>
            <div className="mt-2 text-xs text-slate-400">
              Favorito: <span className="text-white font-semibold">{s.favorito}</span>
              {" · "}Placar provável: <span className="text-emerald-300 font-mono font-bold">{s.placar_provavel}</span>
            </div>
          </div>

          {/* Picks recomendados */}
          {s.picks_recomendados?.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Picks Recomendados pela IA
              </div>
              <div className="space-y-2">
                {s.picks_recomendados.map((p, i) => {
                  const medal = i === 0 ? "🥇" : i === 1 ? "🥈" : i === 2 ? "🥉" : `${i + 1}.`;
                  return (
                    <div key={i} className={`rounded-lg border p-3 ${confColor(p.nivel_confianca)}`}>
                      <div className="flex items-start gap-2">
                        <span className="text-lg w-7 flex-shrink-0 text-center">{medal}</span>
                        <div>
                          <div className="font-semibold text-sm text-white">{p.aposta}</div>
                          <div className="text-xs text-slate-400 mt-0.5">{p.racional}</div>
                        </div>
                        <span className={`ml-auto text-xs font-semibold flex-shrink-0 ${
                          p.nivel_confianca === "Alta" ? "text-emerald-400" :
                          p.nivel_confianca === "Média" ? "text-blue-400" : "text-slate-400"
                        }`}>{p.nivel_confianca}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Grid escalações + árbitro */}
          <div className="grid grid-cols-2 gap-3">
            {[
              { team: data.home_team, esc: s.escalacao_home },
              { team: data.away_team, esc: s.escalacao_away },
            ].map(({ team, esc }) => (
              <div key={team} className="rounded-lg bg-white/5 p-3">
                <div className="text-xs font-bold text-slate-300 mb-1">{team}</div>
                {esc?.status ? (
                  <div className={`text-xs mb-1 ${esc.status === "Completo" ? "text-emerald-400" : "text-amber-400"}`}>
                    {esc.status}
                  </div>
                ) : (
                  <div className="text-xs mb-1 text-slate-500">Escalação não disponível</div>
                )}
                {esc?.lesoes_suspensoes?.length > 0 && (
                  <ul className="text-xs text-red-400 space-y-0.5">
                    {esc.lesoes_suspensoes.map((l, i) => <li key={i}>• {l}</li>)}
                  </ul>
                )}
                {esc?.destaque && (
                  <div className="text-xs text-slate-400 mt-1">⭐ {esc.destaque}</div>
                )}
              </div>
            ))}
          </div>

          {/* Árbitro + Projeção de Cartões */}
          {s.arbitro?.nome && s.arbitro.nome !== "Não divulgado" && (
            <div className="rounded-lg bg-white/5 p-3 space-y-2">
              <div className="text-xs font-bold text-slate-400 mb-1">⚖️ Árbitro</div>
              <div className="text-sm text-white">{s.arbitro.nome}</div>
              {s.arbitro.perfil && (
                <div className="text-xs text-slate-400">{s.arbitro.perfil}</div>
              )}
              {/* Dados numéricos para projeção de cartões */}
              {(data.pregame_context?.referee_card_lambda != null || s.arbitro?.card_lambda != null) && (() => {
                const lambda = data.pregame_context?.referee_card_lambda ?? s.arbitro?.card_lambda;
                const penRate = data.pregame_context?.referee_penalty_rate ?? s.arbitro?.penalty_rate;
                return (
                  <div className="mt-2 pt-2 border-t border-white/10 grid grid-cols-2 gap-2">
                    {lambda != null && (
                      <div className="bg-amber-900/20 rounded-lg p-2 text-center border border-amber-700/30">
                        <div className="text-xs text-amber-400 font-semibold">Cartões/Jogo</div>
                        <div className="text-lg font-black text-amber-300 font-mono">{Number(lambda).toFixed(1)}</div>
                        <div className="text-xs text-slate-500">λ amarelos</div>
                      </div>
                    )}
                    {penRate != null && (
                      <div className="bg-red-900/20 rounded-lg p-2 text-center border border-red-700/30">
                        <div className="text-xs text-red-400 font-semibold">Pênaltis</div>
                        <div className="text-lg font-black text-red-300 font-mono">{(Number(penRate) * 100).toFixed(0)}%</div>
                        <div className="text-xs text-slate-500">% jogos com pen.</div>
                      </div>
                    )}
                  </div>
                );
              })()}
              {data.pregame_context && (
                <div className="text-xs text-emerald-500/70 flex items-center gap-1 mt-1">
                  <span>✓</span>
                  <span>Dados salvos — modelo ao vivo usará esses priors</span>
                </div>
              )}
            </div>
          )}

          {/* Fatores + riscos */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-white/5 p-3">
              <div className="text-xs font-bold text-emerald-400 mb-2">✅ Principais Fatores</div>
              <ul className="space-y-1">
                {s.principais_fatores?.map((f, i) => (
                  <li key={i} className="text-xs text-slate-300">• {f}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-lg bg-white/5 p-3">
              <div className="text-xs font-bold text-amber-400 mb-2">⚠️ Alertas de Risco</div>
              <ul className="space-y-1">
                {s.alertas_risco?.map((r, i) => (
                  <li key={i} className="text-xs text-slate-300">• {r}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* Análise mercados */}
          <div className="rounded-lg bg-white/5 p-3 space-y-2">
            <div className="text-xs font-bold text-slate-400 mb-1">📊 Análise de Mercados</div>
            {[
              ["1X2", s.analise_mercados?.resultado],
              ["Over/Under", s.analise_mercados?.over_under],
              ["BTTS", s.analise_mercados?.btts],
              ["Handicap", s.analise_mercados?.handicap],
            ].filter(([, v]) => v).map(([k, v]) => (
              <div key={k as string}>
                <span className="text-xs font-semibold text-slate-500">{k}: </span>
                <span className="text-xs text-slate-300">{v}</span>
              </div>
            ))}
          </div>

          {/* Nota final */}
          {s.nota_final && (
            <div className="rounded-lg border border-blue-700/20 bg-blue-900/10 p-3 text-xs text-blue-300 italic">
              💡 {s.nota_final}
            </div>
          )}

          {/* Fontes */}
          {data.web_research?.citations?.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-slate-600 mb-1">Fontes consultadas</div>
              <div className="space-y-0.5">
                {data.web_research.citations.slice(0, 5).map((c: string, i: number) => (
                  <div key={i} className="text-xs text-slate-600 truncate">{i + 1}. {c}</div>
                ))}
              </div>
            </div>
          )}
        </>
      ) : (
        /* Sem síntese — quota esgotada ou erro de API */
        <div className="space-y-4">
          <div className="rounded-xl border border-amber-700/30 bg-amber-900/10 p-4 text-center">
            <div className="text-2xl mb-2">🤖</div>
            <div className="text-sm font-semibold text-amber-300 mb-1">Análise Local Ativa</div>
            <div className="text-xs text-slate-400 leading-relaxed">
              A síntese com IA externa (Gemini/Moonshot) está temporariamente indisponível.
              <br />
              <span className="text-emerald-400 font-semibold">
                Usando análise local com dados do modelo + contexto pré-jogo.
              </span>
              <br />
              Picks, probabilidades e placares estão disponíveis nas abas ao lado.
            </div>
            <button
              onClick={onRefresh}
              className="mt-3 px-4 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-xs text-slate-300 transition-colors"
            >
              ↻ Tentar novamente com IA
            </button>
          </div>
          {data.web_research?.text && (
            <div className="rounded-lg bg-white/5 p-4">
              <div className="text-xs font-bold text-slate-400 mb-2">Pesquisa Web coletada</div>
              <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap">
                {data.web_research.text}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Analysis Panel ────────────────────────────────────────────────────────────

function AnalysisPanel({ home, away, phase }: { home: string; away: string; phase: string }) {
  const [tab, setTab] = useState<Tab>("bilhete");

  const { data, isLoading, error } = useQuery<AnalysisResponse>({
    queryKey: ["pregame-analysis", home, away, phase],
    queryFn: () =>
      apiFetch(`/worldcup/pregame/analysis?home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}&phase=${phase}`),
    staleTime: 5 * 60 * 1000,
  });

  const analysisReady = Boolean(data && !isLoading);
  const researchQuery = usePregameResearchQuery({ home, away, phase, enabled: analysisReady });
  const summaryQuery = usePregameSummaryQuery({ home, away, phase, enabled: analysisReady });
  const copilotQuery = usePregameCopilotQuery({ home, away, phase, enabled: analysisReady });

  const handleSwitchTab = (t: string) => {
    const allowed: Tab[] = ["bilhete", "resumo", "placar", "picks", "research", "h2h", "contexto"];
    if (allowed.includes(t as Tab)) setTab(t as Tab);
  };

  const { displayCopilot, agentChat } = usePregameCopilotAgentSession({
    home,
    away,
    phase,
    enabled: analysisReady,
    baseCopilot: copilotQuery.data,
    onSwitchTab: handleSwitchTab,
  });

  const refreshResearch = () => {
    void apiFetch<PregameResearchResponse>(
      `/worldcup/pregame/research?home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}&phase=${phase}&force_refresh=true`,
      { timeoutMs: 120_000 },
    ).then(() => {
      void researchQuery.refetch();
      void summaryQuery.refetch();
    });
  };

  useEffect(() => {
    if (researchQuery.data?.synthesis && !researchQuery.isFetching) {
      void summaryQuery.refetch();
    }
  }, [researchQuery.data?.synthesis, researchQuery.isFetching, summaryQuery]);

  if (isLoading) {
    return (
      <div className="space-y-3 p-4">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }
  if (error || !data) {
    return <ErrorState message="Falha ao carregar análise." />;
  }

  const homeColor = teamColor(home);
  const awayColor = teamColor(away);

  return (
    <div className="flex-1 overflow-auto">
      <div className="live-scoreboard mx-2 mt-2 border-b-0 sm:mx-4">
        <div className="relative px-5 py-4">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div className="flex-1 text-center">
              <div className="text-2xl font-bold" style={{ color: homeColor }}>{home}</div>
              <div className="mt-1 text-xs text-slate-400">Casa</div>
            </div>
            <div className="px-4 text-center">
              <div className="font-mono text-3xl font-black text-white">VS</div>
              {data.group && (
                <div className="mt-1 text-xs font-semibold text-neon-green">Grupo {data.group}</div>
              )}
            </div>
            <div className="flex-1 text-center">
              <div className="text-2xl font-bold" style={{ color: awayColor }}>{away}</div>
              <div className="mt-1 text-xs text-slate-400">Visitante</div>
            </div>
          </div>

          <ProbBar
            home={data.prob_home}
            draw={data.prob_draw}
            away={data.prob_away}
            homeTeam={home}
            awayTeam={away}
          />

          <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
            {data.kickoff_date && (
              <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-xs text-slate-300">
                {data.kickoff_date === new Date().toLocaleDateString("en-CA", { timeZone: "America/Sao_Paulo" })
                  ? "Hoje"
                  : new Date(`${data.kickoff_date}T12:00:00`).toLocaleDateString("pt-BR")}{" "}
                ·{" "}
                {data.kickoff_utc
                  ? formatKickoff(data.kickoff_utc)
                  : data.kickoff_local ?? ""}
              </span>
            )}
            <span className="rounded-full border border-neon-green/30 bg-neon-green/10 px-3 py-1 font-semibold text-neon-green">
              {data.prediction}
            </span>
            <span className="text-slate-400">
              conf. <span className="font-mono text-white">{(data.confidence * 100).toFixed(1)}%</span>
            </span>
            <span className="text-slate-500">|</span>
            <span className="text-slate-400">
              xG <span className="font-mono text-white">{data.expected_goals}</span>
            </span>
          </div>
        </div>
      </div>

      <LiveDashboardTabs
        tabs={TABS.map((t) => ({ id: t.key, label: t.label }))}
        activeId={tab}
        onChange={(id) => setTab(id as Tab)}
      />

      <div className="space-y-4 p-4 pt-3">

        {/* ── BILHETE ── */}
        {tab === "bilhete" && (
          <div className="space-y-4">
            <PregameSummaryCard
              summary={summaryQuery.data}
              isLoading={summaryQuery.isLoading}
              researchLoading={researchQuery.isFetching}
            />

            {/* Combo recomendado */}
            {data.ticket.combo && (
              <div className="rounded-xl border border-emerald-500/50 bg-gradient-to-br from-emerald-900/30 to-emerald-800/10 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-lg">🏆</span>
                  <div>
                    <div className="text-xs font-bold text-emerald-400 uppercase tracking-wider">Aposta Principal (Combinada)</div>
                    <div className="text-base font-bold text-white mt-0.5">{data.ticket.combo.label}</div>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 mb-3">
                  <div className="bg-black/30 rounded-lg p-2 text-center">
                    <div className="text-xs text-slate-400">Odd Justa</div>
                    <div className="text-xl font-black text-emerald-300 font-mono">
                      {data.ticket.combo.fair_odd?.toFixed(2) ?? "—"}
                    </div>
                  </div>
                  <div className="bg-black/30 rounded-lg p-2 text-center">
                    <div className="text-xs text-slate-400">Prob. Modelo</div>
                    <div className="text-xl font-black text-blue-300 font-mono">
                      {(data.ticket.combo.model_prob * 100).toFixed(0)}%
                    </div>
                  </div>
                  <div className="bg-black/30 rounded-lg p-2 text-center">
                    <div className="text-xs text-slate-400">Kelly 25%</div>
                    <div className="text-xl font-black text-amber-300 font-mono">
                      {data.ticket.combo.kelly_units.toFixed(1)}u
                    </div>
                  </div>
                </div>
                <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${
                  data.ticket.combo.confidence === "Alta"
                    ? "bg-emerald-800/60 text-emerald-300"
                    : data.ticket.combo.confidence === "Média"
                    ? "bg-blue-800/60 text-blue-300"
                    : "bg-white/10 text-slate-300"
                }`}>
                  Confiança: {data.ticket.combo.confidence}
                </div>
              </div>
            )}

            {/* Singles recomendadas */}
            <div>
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Apostas Individuais Recomendadas
              </div>
              <div className="space-y-2">
                {data.ticket.singles.map((pick, i) => {
                  const medal = i === 0 ? "🥇" : i === 1 ? "🥈" : "🥉";
                  const confColor =
                    pick.confidence === "Alta"
                      ? "text-emerald-400 bg-emerald-900/30 border-emerald-700/40"
                      : pick.confidence === "Média"
                      ? "text-blue-400 bg-blue-900/30 border-blue-700/40"
                      : "text-slate-400 bg-white/5 border-white/8";
                  return (
                    <div
                      key={pick.market}
                      className={`flex items-center gap-3 rounded-lg border p-3 ${confColor}`}
                    >
                      <span className="text-xl w-7 text-center">{medal}</span>
                      <div className="flex-1 min-w-0">
                        <div className="font-semibold text-sm text-white truncate">{pick.label}</div>
                        <div className="text-xs text-slate-500 font-mono">{pick.market}</div>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <div className="text-base font-black font-mono text-white">
                          {pick.fair_odd?.toFixed(2) ?? "—"}
                        </div>
                        <div className="text-xs text-slate-400">
                          {(pick.model_prob * 100).toFixed(0)}% · {pick.kelly_units.toFixed(1)}u
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Placar mais provável */}
            <div className="rounded-lg bg-white/5 p-3">
              <div className="text-xs text-slate-400 mb-2">Placar Mais Provável</div>
              <div className="flex gap-3 flex-wrap">
                {data.top_scorelines.slice(0, 4).map((s, i) => {
                  const [hg, ag] = s.score.split("x").map(Number);
                  const outColor = hg > ag ? "text-blue-400" : hg === ag ? "text-slate-400" : "text-orange-400";
                  return (
                    <div key={s.score} className="flex items-center gap-1.5 bg-black/30 rounded-lg px-3 py-2">
                      <span className="text-xs text-slate-500">{i + 1}º</span>
                      <span className={`font-mono font-bold ${outColor}`}>{s.score}</span>
                      <span className="text-xs text-emerald-400 font-mono">{(s.prob * 100).toFixed(0)}%</span>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="text-xs text-slate-600 italic">{data.ticket.note}</div>
          </div>
        )}

        {tab === "resumo" && (
          <div className="space-y-4">
            <div className="rounded-lg border border-blue-700/40 bg-blue-900/20 p-3">
              <div className="text-xs font-semibold text-blue-400 mb-1">Contexto</div>
              <p className="text-sm text-slate-200">{data.h2h_summary}</p>
            </div>
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: "Placar provável", value: data.poisson_score },
                { label: "xG Esperado", value: data.expected_goals },
                { label: "Fase", value: data.phase === "group" ? "Grupos" : "Mata-mata" },
              ].map((item) => (
                <div key={item.label} className="rounded-lg bg-white/5/60 p-3 text-center">
                  <div className="text-xs text-slate-400 mb-1">{item.label}</div>
                  <div className="text-base font-bold text-white">{item.value}</div>
                </div>
              ))}
            </div>
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: home, value: `${(data.prob_home * 100).toFixed(1)}%`, color: "text-blue-400" },
                { label: "Empate", value: `${(data.prob_draw * 100).toFixed(1)}%`, color: "text-slate-300" },
                { label: away, value: `${(data.prob_away * 100).toFixed(1)}%`, color: "text-orange-400" },
              ].map((item) => (
                <div key={item.label} className="rounded-lg bg-white/5/60 p-3 text-center">
                  <div className="text-xs text-slate-400 mb-1">{item.label}</div>
                  <div className={`text-lg font-black font-mono ${item.color}`}>{item.value}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === "placar" && (
          <div className="space-y-2">
            <div className="text-sm text-slate-400 mb-3">
              Top placares mais prováveis (distribuição Poisson)
            </div>
            {data.top_scorelines.map((s, i) => {
              const [hg, ag] = s.score.split("x").map(Number);
              const outcome = hg > ag ? "home" : hg === ag ? "draw" : "away";
              const outColor = outcome === "home" ? "text-blue-400" : outcome === "draw" ? "text-slate-400" : "text-orange-400";
              return (
                <div key={s.score} className="flex items-center gap-3 p-2 rounded-lg bg-white/5">
                  <span className="text-xs text-slate-500 w-4 text-right">{i + 1}</span>
                  <span className={`font-mono font-bold text-base w-12 text-center ${outColor}`}>{s.score}</span>
                  <div className="flex-1 h-2 rounded-full bg-white/10 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-emerald-500/70"
                      style={{ width: `${Math.min(100, s.prob * 100 * 5)}%` }}
                    />
                  </div>
                  <span className="text-xs font-mono text-emerald-400 w-12 text-right">
                    {(s.prob * 100).toFixed(1)}%
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {tab === "picks" && (
          <div className="space-y-2">
            <div className="text-xs text-slate-500 mb-2">Todos os mercados — ordenados por probabilidade</div>
            {[...data.picks].sort((a, b) => b.model_prob - a.model_prob).map((p) => (
              <div key={p.market} className="flex items-center gap-3 p-2.5 rounded-lg bg-white/5 border border-white/8">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-slate-200 truncate">{p.label}</div>
                  <div className="text-xs text-slate-600 font-mono">{p.market}</div>
                </div>
                <div className="flex gap-4 items-center text-right">
                  <div>
                    <div className="text-xs text-slate-500">Prob.</div>
                    <div className="text-sm font-bold text-emerald-400 font-mono">
                      {(p.model_prob * 100).toFixed(0)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">Odd Justa</div>
                    <div className="text-sm font-bold text-white font-mono">
                      {p.fair_odd?.toFixed(2) ?? "—"}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">Kelly</div>
                    <div className="text-sm font-bold text-amber-400 font-mono">
                      {p.kelly_units.toFixed(1)}u
                    </div>
                  </div>
                </div>
              </div>
            ))}
            <div className="rounded-lg border border-amber-700/30 bg-amber-900/10 p-2.5 text-xs text-amber-300 mt-1">
              Kelly 25%: stake = (prob × odd − 1) / (odd − 1) × 0.25 × bankroll
            </div>
          </div>
        )}

        {tab === "research" && (
          <DeepResearchPanel
            home={home}
            away={away}
            phase={phase}
            research={researchQuery.data}
            isFetching={researchQuery.isFetching}
            error={researchQuery.error as Error | null}
            onRefresh={refreshResearch}
          />
        )}

        {tab === "h2h" && (
          <div className="space-y-3">
            <div className="text-sm text-slate-400">Histórico de confrontos</div>
            <div className="rounded-lg bg-white/5 p-4">
              <p className="text-sm text-slate-200 leading-relaxed">{data.h2h_summary}</p>
            </div>
          </div>
        )}

        {tab === "contexto" && (
          <div className="space-y-3">
            {data.match_context ? (
              <>
                <div className="rounded-lg border border-emerald-700/30 bg-emerald-900/10 p-3">
                  <div className="text-xs font-semibold text-emerald-400 mb-2">Contexto carregado</div>
                  {!!data.match_context.referee_name && (
                    <div className="text-sm text-slate-200">
                      Árbitro: <span className="text-white font-semibold">{String(data.match_context.referee_name)}</span>
                    </div>
                  )}
                  {data.match_context.referee_card_lambda != null && (
                    <div className="text-sm text-slate-300">
                      Média cartões: <span className="font-mono text-amber-400">{Number(data.match_context.referee_card_lambda).toFixed(2)}/jogo</span>
                    </div>
                  )}
                  {data.match_context.home_pregame_xg != null && (
                    <div className="text-sm text-slate-300">
                      xG pré-jogo: <span className="font-mono text-blue-400">{Number(data.match_context.home_pregame_xg).toFixed(2)}</span>
                      {" "}x{" "}
                      <span className="font-mono text-orange-400">{Number(data.match_context.away_pregame_xg ?? 0).toFixed(2)}</span>
                    </div>
                  )}
                  {data.match_context.h2h_avg_goals != null && (
                    <div className="text-sm text-slate-300">
                      H2H média gols: <span className="font-mono text-white">{Number(data.match_context.h2h_avg_goals).toFixed(2)}</span>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="rounded-lg bg-white/5 p-4 text-sm text-slate-400 text-center">
                Nenhum arquivo de contexto carregado.<br />
                <span className="text-xs">Faça upload via tela Ao Vivo para enriquecer a análise.</span>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="border-t border-white/8 p-4 mx-2 sm:mx-4 mb-4">
        <LiveCopilotPanel
          copilot={displayCopilot}
          isLoading={copilotQuery.isLoading}
          isFetching={copilotQuery.isFetching}
          agentChat={agentChat}
        />
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export function PreGameAnalysisPage() {
  const [selected, setSelected] = useState<TodayMatch | null>(null);

  const { data, isLoading, error } = useQuery<TodayResponse>({
    queryKey: ["pregame-today", "v2", "today_only", "America/Sao_Paulo"],
    queryFn: () =>
      apiFetch("/worldcup/pregame/today?today_only=true&tz=America/Sao_Paulo"),
    staleTime: 60_000,
    refetchOnMount: "always",
  });

  const todayMatches = useMemo(() => data?.matches ?? [], [data]);

  useEffect(() => {
    if (!data) return;
    if (selected && !todayMatches.some((m) => m.id === selected.id)) {
      setSelected(null);
    }
  }, [data, selected, todayMatches]);

  useEffect(() => {
    if (todayMatches.length === 1 && !selected) {
      setSelected(todayMatches[0]);
    }
  }, [todayMatches, selected]);

  return (
    <PageTransition>
      <div className="flex flex-col h-full min-h-screen">
        <HeroPageHeader
          title="Análise Pré-Jogo"
          subtitle="Jogos de hoje · horário de Brasília"
        />

        <div className="flex flex-1 overflow-hidden gap-0 divide-x divide-white/8">
          {/* Sidebar — games list */}
          <div className="w-72 flex-shrink-0 overflow-auto p-3 space-y-1">
            {isLoading && (
              <div className="space-y-2 pt-2">
                {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-20 w-full rounded-lg" />)}
              </div>
            )}

            {error && <ErrorState message="Não foi possível carregar os jogos." />}

            {data && todayMatches.length === 0 && (
              <div className="text-sm text-slate-400 text-center py-8 px-2 space-y-3">
                <p>
                  Nenhum jogo da Copa hoje (
                  {new Date(data.date + "T12:00:00").toLocaleDateString("pt-BR")}).
                </p>
                {data.next_match ? (
                  <div className="rounded-xl border border-white/10 bg-black/30 p-3 text-left space-y-1">
                    <div className="text-[10px] uppercase tracking-wider text-emerald-500/90 font-semibold">
                      Próximo
                    </div>
                    <div className="text-sm font-semibold text-white">
                      {data.next_match.home_team}{" "}
                      <span className="text-slate-500 font-normal">×</span>{" "}
                      {data.next_match.away_team}
                    </div>
                    <div className="text-xs text-slate-400">
                      {data.next_match.kickoff_br ?? "data a definir"}
                      {data.next_match.eta_label ? ` · ${data.next_match.eta_label}` : ""}
                    </div>
                    {data.next_match.phase && (
                      <div className="text-[10px] text-slate-500 capitalize">
                        {String(data.next_match.phase).replaceAll("_", " ")}
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-slate-500">
                    Sem próximo confronto no calendário — rode{" "}
                    <code className="text-slate-300">sync-wc-knockout-schedule</code> quando a FIFA
                    publicar a próxima fase.
                  </p>
                )}
              </div>
            )}

            {data && todayMatches.length > 0 && (() => {
              const byDate = new Map<string, TodayMatch[]>();
              for (const m of todayMatches) {
                const d = m.kickoff_date;
                if (!byDate.has(d)) byDate.set(d, []);
                byDate.get(d)!.push(m);
              }
              const today = data.date;
              const tomorrow = (() => {
                const d = new Date(today + "T12:00:00");
                d.setDate(d.getDate() + 1);
                return d.toISOString().slice(0, 10);
              })();
              const yesterday = (() => {
                const d = new Date(today + "T12:00:00");
                d.setDate(d.getDate() - 1);
                return d.toISOString().slice(0, 10);
              })();

              return Array.from(byDate.entries()).map(([date, matches]) => (
                <div key={date} className="mb-1">
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider px-1 py-2 sticky top-0 bg-black/60 backdrop-blur-sm z-10">
                    {date === today
                      ? "Hoje"
                      : date === tomorrow
                        ? "Madrugada"
                      : date === yesterday
                        ? "Ontem"
                        : new Date(date + "T12:00:00Z").toLocaleDateString("pt-BR", {
                            weekday: "short",
                            day: "2-digit",
                            month: "2-digit",
                          })}
                    <span className="ml-2 text-slate-600 font-normal normal-case">
                      {matches.filter(m => !m.played).length} a jogar
                    </span>
                  </div>
                  <div className="space-y-1.5">
                    {matches.map((match) => {
                      const isSelected = selected?.id === match.id;
                      const homeColor = match.played ? "#6b7280" : teamColor(match.home_team);
                      const awayColor = match.played ? "#6b7280" : teamColor(match.away_team);
                      return (
                        <button
                          key={match.id}
                          onClick={() => setSelected(match)}
                          className={`w-full text-left rounded-xl border p-3 transition-all ${
                            isSelected
                              ? "border-neon-green/40 bg-neon-green/10"
                              : match.played
                              ? "border-white/8 bg-black/15 hover:bg-white/5"
                              : "live-glass-panel border-white/10 hover:border-neon-green/20"
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1.5">
                            <span className={`text-xs ${match.played ? "text-slate-600" : "text-slate-500"}`}>
                              {formatKickoff(match.kickoff_utc)}
                            </span>
                            <div className="flex items-center gap-1.5">
                              {match.group && (
                                <span className="text-xs text-emerald-600 font-semibold">G{match.group}</span>
                              )}
                              {match.played && (
                                <span className="text-xs text-slate-600 bg-white/5 px-1.5 py-0.5 rounded-full">
                                  {match.home_score ?? 0}–{match.away_score ?? 0}
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <div className="text-sm font-semibold truncate" style={{ color: homeColor }}>
                                {match.home_team}
                              </div>
                              <div className="text-xs text-slate-600">vs</div>
                              <div className="text-sm font-semibold truncate" style={{ color: awayColor }}>
                                {match.away_team}
                              </div>
                            </div>
                          </div>
                          {!match.played && (
                            <div className="mt-2 flex gap-2 text-xs font-mono">
                              <span className="text-blue-400">{(match.prob_home * 100).toFixed(0)}%</span>
                              <span className="text-slate-500">{(match.prob_draw * 100).toFixed(0)}%</span>
                              <span className="text-orange-400">{(match.prob_away * 100).toFixed(0)}%</span>
                              <span className="ml-auto text-emerald-500 truncate text-xs">{match.prediction}</span>
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ));
            })()}
          </div>

          {/* Main content */}
          <div className="flex-1 overflow-auto">
            {selected ? (
              <AnalysisPanel
                key={selected.id}
                home={selected.home_team}
                away={selected.away_team}
                phase={selected.phase}
              />
            ) : (
              <div className="flex items-center justify-center h-full text-slate-500 text-sm">
                Selecione um jogo para ver a análise detalhada
              </div>
            )}
          </div>
        </div>
      </div>
    </PageTransition>
  );
}
