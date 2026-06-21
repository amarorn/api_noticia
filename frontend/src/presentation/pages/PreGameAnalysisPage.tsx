import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/infrastructure/api/client";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { HeroPageHeader } from "@/presentation/components/layout/PageHeader";
import { Skeleton } from "@/presentation/components/ui/Skeleton";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { teamColor } from "@/data/teamColors";

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

interface TodayResponse {
  date: string;
  end_date: string;
  total: number;
  matches: TodayMatch[];
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
  arbitro: { nome: string; perfil: string };
  analise_mercados: { resultado: string; over_under: string; btts: string; handicap?: string };
  picks_recomendados: ResearchPick[];
  placar_provavel: string;
  nota_final: string;
}

interface ResearchResponse {
  home_team: string;
  away_team: string;
  model_data: Record<string, unknown>;
  web_research: { text: string; citations: string[] };
  synthesis: ResearchSynthesis | null;
  provider?: string;
  errors: Record<string, string>;
  from_cache: boolean;
  cached_at?: number;
}

interface AnalysisResponse {
  home_team: string;
  away_team: string;
  phase: string;
  group: string | null;
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
      <div className="flex text-xs text-neutral-400 justify-between mb-1">
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
        <span className="text-neutral-400">{dPct}%</span>
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

// ── Deep Research Panel ───────────────────────────────────────────────────────

function DeepResearchPanel({ home, away, phase }: { home: string; away: string; phase: string }) {
  const [triggered, setTriggered] = useState(false);
  const [forceRefresh, setForceRefresh] = useState(false);

  const { data, isFetching, error, refetch } = useQuery<ResearchResponse>({
    queryKey: ["pregame-research", home, away, phase, forceRefresh],
    queryFn: () =>
      apiFetch(
        `/worldcup/pregame/research?home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}&phase=${phase}${forceRefresh ? "&force_refresh=true" : ""}`,
      ),
    enabled: triggered,
    staleTime: Infinity,
    retry: 1,
  });

  const confColor = (c?: string) =>
    c === "Alta"
      ? "text-emerald-400 bg-emerald-900/30 border-emerald-700/40"
      : c === "Média"
      ? "text-blue-400 bg-blue-900/30 border-blue-700/40"
      : "text-neutral-400 bg-neutral-800/40 border-neutral-600/30";

  if (!triggered) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-4 text-center">
        <div className="text-4xl">🔬</div>
        <div className="text-base font-semibold text-neutral-200">Deep Research com IA</div>
        <div className="text-sm text-neutral-400 max-w-xs">
          Pesquisa em tempo real via <span className="text-blue-400 font-semibold">Google Search</span> +
          síntese com <span className="text-purple-400 font-semibold">Gemini</span>.
          <br />Pode levar até 30s.
        </div>
        <button
          onClick={() => { setTriggered(true); setForceRefresh(false); }}
          className="mt-2 px-6 py-2.5 rounded-xl bg-emerald-700 hover:bg-emerald-600 text-white font-semibold text-sm transition-colors"
        >
          Iniciar pesquisa
        </button>
      </div>
    );
  }

  if (isFetching) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3">
        <div className="animate-spin text-3xl">🔬</div>
        <div className="text-sm text-neutral-400 text-center">
          Pesquisando no Google e sintetizando com IA...
          <br /><span className="text-xs text-neutral-600">Gemini + Google Search Grounding</span>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return <ErrorState message="Falha na pesquisa. Verifique as API keys (PERPLEXITY_API_KEY, MOONSHOT_API_KEY)." />;
  }

  const s = data.synthesis;
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
            <span className="text-xs text-neutral-500 bg-neutral-800 px-2 py-0.5 rounded-full">{cacheInfo}</span>
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
          onClick={() => { setForceRefresh(true); void refetch(); }}
          className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors"
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
            <p className="text-sm text-neutral-200 leading-relaxed">{s.resumo_executivo}</p>
            <div className="mt-2 text-xs text-neutral-400">
              Favorito: <span className="text-white font-semibold">{s.favorito}</span>
              {" · "}Placar provável: <span className="text-emerald-300 font-mono font-bold">{s.placar_provavel}</span>
            </div>
          </div>

          {/* Picks recomendados */}
          {s.picks_recomendados?.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-2">
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
                          <div className="text-xs text-neutral-400 mt-0.5">{p.racional}</div>
                        </div>
                        <span className={`ml-auto text-xs font-semibold flex-shrink-0 ${
                          p.nivel_confianca === "Alta" ? "text-emerald-400" :
                          p.nivel_confianca === "Média" ? "text-blue-400" : "text-neutral-400"
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
              <div key={team} className="rounded-lg bg-neutral-800/40 p-3">
                <div className="text-xs font-bold text-neutral-300 mb-1">{team}</div>
                <div className={`text-xs mb-1 ${esc.status === "Completo" ? "text-emerald-400" : "text-amber-400"}`}>
                  {esc.status}
                </div>
                {esc.lesoes_suspensoes?.length > 0 && (
                  <ul className="text-xs text-red-400 space-y-0.5">
                    {esc.lesoes_suspensoes.map((l, i) => <li key={i}>• {l}</li>)}
                  </ul>
                )}
                {esc.destaque && (
                  <div className="text-xs text-neutral-400 mt-1">⭐ {esc.destaque}</div>
                )}
              </div>
            ))}
          </div>

          {/* Árbitro */}
          {s.arbitro?.nome !== "Não divulgado" && (
            <div className="rounded-lg bg-neutral-800/40 p-3">
              <div className="text-xs font-bold text-neutral-400 mb-1">⚖️ Árbitro</div>
              <div className="text-sm text-white">{s.arbitro.nome}</div>
              <div className="text-xs text-neutral-400 mt-0.5">{s.arbitro.perfil}</div>
            </div>
          )}

          {/* Fatores + riscos */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-neutral-800/40 p-3">
              <div className="text-xs font-bold text-emerald-400 mb-2">✅ Principais Fatores</div>
              <ul className="space-y-1">
                {s.principais_fatores?.map((f, i) => (
                  <li key={i} className="text-xs text-neutral-300">• {f}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-lg bg-neutral-800/40 p-3">
              <div className="text-xs font-bold text-amber-400 mb-2">⚠️ Alertas de Risco</div>
              <ul className="space-y-1">
                {s.alertas_risco?.map((r, i) => (
                  <li key={i} className="text-xs text-neutral-300">• {r}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* Análise mercados */}
          <div className="rounded-lg bg-neutral-800/40 p-3 space-y-2">
            <div className="text-xs font-bold text-neutral-400 mb-1">📊 Análise de Mercados</div>
            {[
              ["1X2", s.analise_mercados?.resultado],
              ["Over/Under", s.analise_mercados?.over_under],
              ["BTTS", s.analise_mercados?.btts],
              ["Handicap", s.analise_mercados?.handicap],
            ].filter(([, v]) => v).map(([k, v]) => (
              <div key={k as string}>
                <span className="text-xs font-semibold text-neutral-500">{k}: </span>
                <span className="text-xs text-neutral-300">{v}</span>
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
          {data.web_research.citations.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-neutral-600 mb-1">Fontes consultadas</div>
              <div className="space-y-0.5">
                {data.web_research.citations.slice(0, 5).map((c, i) => (
                  <div key={i} className="text-xs text-neutral-600 truncate">{i + 1}. {c}</div>
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
            <div className="text-xs text-neutral-400 leading-relaxed">
              A síntese com IA externa (Gemini/Moonshot) está temporariamente indisponível.
              <br />
              <span className="text-emerald-400 font-semibold">
                Usando análise local com dados do modelo + contexto pré-jogo.
              </span>
              <br />
              Picks, probabilidades e placares estão disponíveis nas abas ao lado.
            </div>
            <button
              onClick={() => { setForceRefresh(true); void refetch(); }}
              className="mt-3 px-4 py-1.5 rounded-lg bg-neutral-700 hover:bg-neutral-600 text-xs text-neutral-300 transition-colors"
            >
              ↻ Tentar novamente com IA
            </button>
          </div>
          {data.web_research?.text && (
            <div className="rounded-lg bg-neutral-800/40 p-4">
              <div className="text-xs font-bold text-neutral-400 mb-2">Pesquisa Web coletada</div>
              <p className="text-xs text-neutral-300 leading-relaxed whitespace-pre-wrap">
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
      {/* Match header */}
      <div className="p-4 border-b border-neutral-800">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div className="flex-1 text-center">
            <div className="text-2xl font-bold" style={{ color: homeColor }}>{home}</div>
            <div className="text-xs text-neutral-400 mt-1">Casa</div>
          </div>
          <div className="text-center px-4">
            <div className="text-3xl font-black text-neutral-300">VS</div>
            {data.group && (
              <div className="text-xs text-emerald-400 font-semibold mt-1">Grupo {data.group}</div>
            )}
          </div>
          <div className="flex-1 text-center">
            <div className="text-2xl font-bold" style={{ color: awayColor }}>{away}</div>
            <div className="text-xs text-neutral-400 mt-1">Visitante</div>
          </div>
        </div>

        <ProbBar
          home={data.prob_home}
          draw={data.prob_draw}
          away={data.prob_away}
          homeTeam={home}
          awayTeam={away}
        />

        <div className="mt-3 flex items-center gap-3 text-sm">
          <span className="px-3 py-1 rounded-full bg-emerald-900/40 border border-emerald-600/40 text-emerald-300 font-semibold">
            {data.prediction}
          </span>
          <span className="text-neutral-400">
            conf. <span className="text-white font-mono">{(data.confidence * 100).toFixed(1)}%</span>
          </span>
          <span className="text-neutral-500">|</span>
          <span className="text-neutral-400">
            xG <span className="text-white font-mono">{data.expected_goals}</span>
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-neutral-800 overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors ${
              tab === t.key
                ? "text-emerald-400 border-b-2 border-emerald-500"
                : "text-neutral-400 hover:text-neutral-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="p-4 space-y-4">

        {/* ── BILHETE ── */}
        {tab === "bilhete" && (
          <div className="space-y-4">
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
                    <div className="text-xs text-neutral-400">Odd Justa</div>
                    <div className="text-xl font-black text-emerald-300 font-mono">
                      {data.ticket.combo.fair_odd?.toFixed(2) ?? "—"}
                    </div>
                  </div>
                  <div className="bg-black/30 rounded-lg p-2 text-center">
                    <div className="text-xs text-neutral-400">Prob. Modelo</div>
                    <div className="text-xl font-black text-blue-300 font-mono">
                      {(data.ticket.combo.model_prob * 100).toFixed(0)}%
                    </div>
                  </div>
                  <div className="bg-black/30 rounded-lg p-2 text-center">
                    <div className="text-xs text-neutral-400">Kelly 25%</div>
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
                    : "bg-neutral-700/60 text-neutral-300"
                }`}>
                  Confiança: {data.ticket.combo.confidence}
                </div>
              </div>
            )}

            {/* Singles recomendadas */}
            <div>
              <div className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-2">
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
                      : "text-neutral-400 bg-neutral-800/40 border-neutral-600/30";
                  return (
                    <div
                      key={pick.market}
                      className={`flex items-center gap-3 rounded-lg border p-3 ${confColor}`}
                    >
                      <span className="text-xl w-7 text-center">{medal}</span>
                      <div className="flex-1 min-w-0">
                        <div className="font-semibold text-sm text-white truncate">{pick.label}</div>
                        <div className="text-xs text-neutral-500 font-mono">{pick.market}</div>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <div className="text-base font-black font-mono text-white">
                          {pick.fair_odd?.toFixed(2) ?? "—"}
                        </div>
                        <div className="text-xs text-neutral-400">
                          {(pick.model_prob * 100).toFixed(0)}% · {pick.kelly_units.toFixed(1)}u
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Placar mais provável */}
            <div className="rounded-lg bg-neutral-800/40 p-3">
              <div className="text-xs text-neutral-400 mb-2">Placar Mais Provável</div>
              <div className="flex gap-3 flex-wrap">
                {data.top_scorelines.slice(0, 4).map((s, i) => {
                  const [hg, ag] = s.score.split("x").map(Number);
                  const outColor = hg > ag ? "text-blue-400" : hg === ag ? "text-neutral-400" : "text-orange-400";
                  return (
                    <div key={s.score} className="flex items-center gap-1.5 bg-black/30 rounded-lg px-3 py-2">
                      <span className="text-xs text-neutral-500">{i + 1}º</span>
                      <span className={`font-mono font-bold ${outColor}`}>{s.score}</span>
                      <span className="text-xs text-emerald-400 font-mono">{(s.prob * 100).toFixed(0)}%</span>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="text-xs text-neutral-600 italic">{data.ticket.note}</div>
          </div>
        )}

        {tab === "resumo" && (
          <div className="space-y-4">
            <div className="rounded-lg border border-blue-700/40 bg-blue-900/20 p-3">
              <div className="text-xs font-semibold text-blue-400 mb-1">Contexto</div>
              <p className="text-sm text-neutral-200">{data.h2h_summary}</p>
            </div>
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: "Placar provável", value: data.poisson_score },
                { label: "xG Esperado", value: data.expected_goals },
                { label: "Fase", value: data.phase === "group" ? "Grupos" : "Mata-mata" },
              ].map((item) => (
                <div key={item.label} className="rounded-lg bg-neutral-800/60 p-3 text-center">
                  <div className="text-xs text-neutral-400 mb-1">{item.label}</div>
                  <div className="text-base font-bold text-white">{item.value}</div>
                </div>
              ))}
            </div>
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: home, value: `${(data.prob_home * 100).toFixed(1)}%`, color: "text-blue-400" },
                { label: "Empate", value: `${(data.prob_draw * 100).toFixed(1)}%`, color: "text-neutral-300" },
                { label: away, value: `${(data.prob_away * 100).toFixed(1)}%`, color: "text-orange-400" },
              ].map((item) => (
                <div key={item.label} className="rounded-lg bg-neutral-800/60 p-3 text-center">
                  <div className="text-xs text-neutral-400 mb-1">{item.label}</div>
                  <div className={`text-lg font-black font-mono ${item.color}`}>{item.value}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === "placar" && (
          <div className="space-y-2">
            <div className="text-sm text-neutral-400 mb-3">
              Top placares mais prováveis (distribuição Poisson)
            </div>
            {data.top_scorelines.map((s, i) => {
              const [hg, ag] = s.score.split("x").map(Number);
              const outcome = hg > ag ? "home" : hg === ag ? "draw" : "away";
              const outColor = outcome === "home" ? "text-blue-400" : outcome === "draw" ? "text-neutral-400" : "text-orange-400";
              return (
                <div key={s.score} className="flex items-center gap-3 p-2 rounded-lg bg-neutral-800/50">
                  <span className="text-xs text-neutral-500 w-4 text-right">{i + 1}</span>
                  <span className={`font-mono font-bold text-base w-12 text-center ${outColor}`}>{s.score}</span>
                  <div className="flex-1 h-2 rounded-full bg-neutral-700 overflow-hidden">
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
            <div className="text-xs text-neutral-500 mb-2">Todos os mercados — ordenados por probabilidade</div>
            {[...data.picks].sort((a, b) => b.model_prob - a.model_prob).map((p) => (
              <div key={p.market} className="flex items-center gap-3 p-2.5 rounded-lg bg-neutral-800/50 border border-neutral-700/30">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-neutral-200 truncate">{p.label}</div>
                  <div className="text-xs text-neutral-600 font-mono">{p.market}</div>
                </div>
                <div className="flex gap-4 items-center text-right">
                  <div>
                    <div className="text-xs text-neutral-500">Prob.</div>
                    <div className="text-sm font-bold text-emerald-400 font-mono">
                      {(p.model_prob * 100).toFixed(0)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-neutral-500">Odd Justa</div>
                    <div className="text-sm font-bold text-white font-mono">
                      {p.fair_odd?.toFixed(2) ?? "—"}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-neutral-500">Kelly</div>
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
          <DeepResearchPanel home={home} away={away} phase={phase} />
        )}

        {tab === "h2h" && (
          <div className="space-y-3">
            <div className="text-sm text-neutral-400">Histórico de confrontos</div>
            <div className="rounded-lg bg-neutral-800/50 p-4">
              <p className="text-sm text-neutral-200 leading-relaxed">{data.h2h_summary}</p>
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
                    <div className="text-sm text-neutral-200">
                      Árbitro: <span className="text-white font-semibold">{String(data.match_context.referee_name)}</span>
                    </div>
                  )}
                  {data.match_context.referee_card_lambda != null && (
                    <div className="text-sm text-neutral-300">
                      Média cartões: <span className="font-mono text-amber-400">{Number(data.match_context.referee_card_lambda).toFixed(2)}/jogo</span>
                    </div>
                  )}
                  {data.match_context.home_pregame_xg != null && (
                    <div className="text-sm text-neutral-300">
                      xG pré-jogo: <span className="font-mono text-blue-400">{Number(data.match_context.home_pregame_xg).toFixed(2)}</span>
                      {" "}x{" "}
                      <span className="font-mono text-orange-400">{Number(data.match_context.away_pregame_xg ?? 0).toFixed(2)}</span>
                    </div>
                  )}
                  {data.match_context.h2h_avg_goals != null && (
                    <div className="text-sm text-neutral-300">
                      H2H média gols: <span className="font-mono text-white">{Number(data.match_context.h2h_avg_goals).toFixed(2)}</span>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="rounded-lg bg-neutral-800/50 p-4 text-sm text-neutral-400 text-center">
                Nenhum arquivo de contexto carregado.<br />
                <span className="text-xs">Faça upload via tela Ao Vivo para enriquecer a análise.</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export function PreGameAnalysisPage() {
  const [selected, setSelected] = useState<TodayMatch | null>(null);

  const { data, isLoading, error } = useQuery<TodayResponse>({
    queryKey: ["pregame-today"],
    queryFn: () => apiFetch("/worldcup/pregame/today"),
    staleTime: 5 * 60 * 1000,
  });

  return (
    <PageTransition>
      <div className="flex flex-col h-full min-h-screen">
        <HeroPageHeader
          title="Análise Pré-Jogo"
          subtitle="Jogos de hoje · Copa 2026"
        />

        <div className="flex flex-1 overflow-hidden gap-0 divide-x divide-neutral-800">
          {/* Sidebar — games list */}
          <div className="w-72 flex-shrink-0 overflow-auto p-3 space-y-1">
            {isLoading && (
              <div className="space-y-2 pt-2">
                {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-20 w-full rounded-lg" />)}
              </div>
            )}

            {error && <ErrorState message="Não foi possível carregar os jogos." />}

            {data && data.matches.length === 0 && (
              <div className="text-sm text-neutral-400 text-center py-8">
                Nenhum jogo disponível.
              </div>
            )}

            {data && (() => {
              // Agrupar por data
              const byDate = new Map<string, TodayMatch[]>();
              for (const m of data.matches) {
                const d = m.kickoff_date;
                if (!byDate.has(d)) byDate.set(d, []);
                byDate.get(d)!.push(m);
              }
              const today = data.date;

              return Array.from(byDate.entries()).map(([date, matches]) => (
                <div key={date} className="mb-1">
                  <div className="text-xs font-semibold text-neutral-500 uppercase tracking-wider px-1 py-2 sticky top-0 bg-neutral-950/80 backdrop-blur-sm z-10">
                    {date === today ? "Hoje" : new Date(date + "T12:00:00Z").toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit" })}
                    <span className="ml-2 text-neutral-600 font-normal normal-case">
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
                              ? "border-emerald-600/60 bg-emerald-900/20"
                              : match.played
                              ? "border-neutral-800/40 bg-neutral-900/20 hover:bg-neutral-800/30"
                              : "border-neutral-700/40 bg-neutral-800/30 hover:bg-neutral-800/60"
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1.5">
                            <span className={`text-xs ${match.played ? "text-neutral-600" : "text-neutral-500"}`}>
                              {formatKickoff(match.kickoff_utc)}
                            </span>
                            <div className="flex items-center gap-1.5">
                              {match.group && (
                                <span className="text-xs text-emerald-600 font-semibold">G{match.group}</span>
                              )}
                              {match.played && (
                                <span className="text-xs text-neutral-600 bg-neutral-800 px-1.5 py-0.5 rounded-full">
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
                              <div className="text-xs text-neutral-600">vs</div>
                              <div className="text-sm font-semibold truncate" style={{ color: awayColor }}>
                                {match.away_team}
                              </div>
                            </div>
                          </div>
                          {!match.played && (
                            <div className="mt-2 flex gap-2 text-xs font-mono">
                              <span className="text-blue-400">{(match.prob_home * 100).toFixed(0)}%</span>
                              <span className="text-neutral-500">{(match.prob_draw * 100).toFixed(0)}%</span>
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
              <div className="flex items-center justify-center h-full text-neutral-500 text-sm">
                Selecione um jogo para ver a análise detalhada
              </div>
            )}
          </div>
        </div>
      </div>
    </PageTransition>
  );
}
