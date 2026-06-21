import { useMemo, useState, useCallback } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { IconArrowLeft, IconChevronRight } from "@/presentation/components/ui/Icons";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";

// Painéis de análise e mercado
import { LiveModelVsMarketHero } from "@/presentation/components/predictions/LiveModelVsMarketHero";
import { LiveEvRealPanel } from "@/presentation/components/predictions/LiveEvRealPanel";
import { LiveStatsCompactBar } from "@/presentation/components/predictions/LiveStatsCompactBar";
import { LiveCornersPanel } from "@/presentation/components/predictions/LiveCornersPanel";
import { LiveTimelinePanel } from "@/presentation/components/predictions/LiveTimelinePanel";
import { LiveFormH2hPanel } from "@/presentation/components/predictions/LiveFormH2hPanel";
import { LivePlayerStatsPanel } from "@/presentation/components/predictions/LivePlayerStatsPanel";
import { LiveSocialRadarPanel } from "@/presentation/components/predictions/LiveSocialRadarPanel";
import { LiveActionNowPanel } from "@/presentation/components/predictions/LiveActionNowPanel";
import { LiveBestCombosPanel } from "@/presentation/components/predictions/LiveBestCombosPanel";
import { LiveHalfTicketsPanel } from "@/presentation/components/predictions/LiveHalfTicketsPanel";
import { LiveRemaining2hMarketsPanel } from "@/presentation/components/predictions/LiveRemaining2hMarketsPanel";
import { LiveLongshotCombosPanel } from "@/presentation/components/predictions/LiveLongshotCombosPanel";
import { LiveMarketCards } from "@/presentation/components/predictions/LiveMarketCards";
import { LiveScoreHeatmap } from "@/presentation/components/predictions/LiveScoreHeatmap";
import { LiveP0GuardBanner } from "@/presentation/components/predictions/LiveP0GuardBanner";
import LiveAgainstModelAlert from "@/presentation/components/predictions/LiveAgainstModelAlert";
import LiveHedgeAlert from "@/presentation/components/predictions/LiveHedgeAlert";
import { LiveRecalibrationBanner } from "@/presentation/components/predictions/LiveRecalibrationBanner";
import { LiveTopReturnPanel } from "@/presentation/components/predictions/LiveTopReturnPanel";
import { LiveOptimizedTicketsPanel } from "@/presentation/components/predictions/LiveOptimizedTicketsPanel";
import { BetStrategyPanel } from "@/presentation/components/predictions/BetStrategyPanel";
import { LiveBetBuilderGuardPanel } from "@/presentation/components/predictions/LiveBetBuilderGuardPanel";
import { LiveContextUpload } from "@/presentation/components/predictions/LiveContextUpload";

// Componentes do dashboard visual
import { LiveDashboardHero } from "@/presentation/components/live-dashboard/LiveDashboardHero";
import { LiveDirectionKpis } from "@/presentation/components/live-dashboard/LiveDirectionKpis";
import { LivePossessionPanel } from "@/presentation/components/live-dashboard/LivePossessionPanel";
import { LiveMatchStatsPanel } from "@/presentation/components/live-dashboard/LiveMatchStatsPanel";
import { LiveEvLeaderboard } from "@/presentation/components/live-dashboard/LiveEvLeaderboard";
import { LiveTrendSignals } from "@/presentation/components/live-dashboard/LiveTrendSignals";
import { LivePredictionEvolutionChart } from "@/presentation/components/live-dashboard/LivePredictionEvolutionChart";

import { useLiveAdviceQueries } from "@/presentation/hooks/useLiveAdviceQueries";
import { useLivePossessionHistory } from "@/presentation/hooks/useLivePossessionHistory";
import { useLiveRecalibration } from "@/presentation/hooks/useLiveRecalibration";
import { resolveLiveAdvicePhase } from "@/presentation/utils/liveAdvicePhase";
import { useTicket, type TicketLeg } from "@/presentation/hooks/useTicket";
import { TicketSimulator, AddBtn, FloatingTicketBadge } from "@/presentation/components/ticket/TicketSimulator";
import { useOddsDropMonitor, type OddsDropAlert } from "@/presentation/hooks/useOddsDropMonitor";
import { LiveOddsDropAlert } from "@/presentation/components/predictions/LiveOddsDropAlert";
import { LiveOpenBetsPanel } from "@/presentation/components/predictions/LiveOpenBetsPanel";

// ─── Tab types ───────────────────────────────────────────────────────────────

type Tab = "apostar" | "mercados" | "analise" | "bilhete";

const TABS: { id: Tab; label: string; emoji: string; hint: string }[] = [
  { id: "apostar",   label: "Apostar Agora", emoji: "🎯", hint: "Bilhetes e oportunidades" },
  { id: "mercados",  label: "Mercados & EV",  emoji: "📊", hint: "Odds, EV e leaderboard"  },
  { id: "analise",   label: "Análise",        emoji: "📈", hint: "Stats, timeline e tendência" },
  { id: "bilhete",   label: "Meu Bilhete",    emoji: "🎟️", hint: "Simulador de bilhete"    },
];

// ─── CollapsibleSection ──────────────────────────────────────────────────────

function CollapsibleSection({
  title,
  defaultOpen = true,
  badge,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  badge?: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.02]">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-white">{title}</span>
          {badge && (
            <span className="rounded-full bg-neon-green/15 px-2 py-0.5 text-[10px] font-bold text-neon-green">
              {badge}
            </span>
          )}
        </div>
        <IconChevronRight
          className={`h-4 w-4 shrink-0 text-slate-500 transition-transform duration-200 ${open ? "rotate-90" : ""}`}
        />
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

// ─── Bootstrap hero (carregando) ─────────────────────────────────────────────

function LiveBootstrapHero({
  homeTeam, awayTeam, score, minute, periodLabel,
}: {
  homeTeam: string; awayTeam: string; score: string;
  minute: number; periodLabel: string | null;
}) {
  return (
    <section className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-slate-900/80 via-slate-900/40 to-slate-950/90 p-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <TeamFlag team={homeTeam} size={44} />
          <p className="truncate text-sm font-medium text-slate-300">{homeTeam}</p>
        </div>
        <div className="flex shrink-0 flex-col items-center px-2">
          <p className="font-mono text-4xl font-bold tracking-tight text-white">
            {score.replace("x", " × ")}
          </p>
          <div className="mt-1 flex items-center gap-2 rounded-full border border-white/10 bg-black/30 px-3 py-1 text-xs font-semibold text-amber-200">
            {minute}&apos;{periodLabel ? ` · ${periodLabel}` : ""}
          </div>
        </div>
        <div className="flex min-w-0 flex-1 items-center justify-end gap-3">
          <p className="truncate text-sm font-medium text-slate-300">{awayTeam}</p>
          <TeamFlag team={awayTeam} size={44} />
        </div>
      </div>
      <p className="mt-4 text-center text-xs text-slate-500" aria-live="polite">
        Carregando modelo in-play…
      </p>
    </section>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export function LiveDashboardPage() {
  const { eventId: eventIdParam } = useParams();
  const [searchParams] = useSearchParams();
  const advicePhase = resolveLiveAdvicePhase(searchParams);
  const eventId = Number.parseInt(eventIdParam ?? "", 10);
  const [activeTab, setActiveTab] = useState<Tab>("apostar");
  const [riskAlerts, setRiskAlerts] = useState<OddsDropAlert[]>([]);
  const ticket = useTicket();

  const handleRiskAlerts = useCallback((newAlerts: OddsDropAlert[]) => {
    setRiskAlerts((prev) => {
      const existingIds = new Set(prev.map((a) => a.id));
      const fresh = newAlerts.filter((a) => !existingIds.has(a.id));
      if (fresh.length === 0) return prev;
      // Mantém últimos 8 alertas
      return [...prev, ...fresh].slice(-8);
    });
  }, []);

  const {
    data, scoreTick, liveHeader, adviceSource,
    isLoading, isAdvicePending, isError, error,
    isFetching, refetch, timelineReactive,
  } = useLiveAdviceQueries(eventId, 1000, null, advicePhase);

  const possessionHistory = useLivePossessionHistory(data);
  const recalibrationEvent = useLiveRecalibration(data, isFetching);
  useOddsDropMonitor(data, handleRiskAlerts);

  const liveSuggestions = useMemo<TicketLeg[]>(() => {
    if (!data?.aportes) return [];
    return data.aportes
      .filter((a) => a.action === "apostar" || a.action === "aporte")
      .map((a) => ({
        id: `${eventId}_${a.market}_${a.outcome}`,
        home: data.homeTeam,
        away: data.awayTeam,
        group: null,
        kickoff: "",
        label: a.label,
        market: a.market,
        fairOdd: a.modelProb > 0 ? +(1 / a.modelProb).toFixed(2) : a.marketOdd,
        modelProb: a.modelProb,
        confidence:
          a.expectedValue >= 0.1 ? "Alta" : a.expectedValue >= 0.05 ? "Média" : "Baixa",
        type: "live" as const,
        liveMinute: data.minute,
        liveScore: data.currentScore ?? undefined,
      }));
  }, [data, eventId]);

  if (!Number.isFinite(eventId) || eventId <= 0) {
    return (
      <PageTransition>
        <ErrorState message="ID do evento inválido." />
        <Link to="/ao-vivo" className="mt-4 inline-flex text-sm text-neon-green hover:underline">
          Voltar à lista ao vivo
        </Link>
      </PageTransition>
    );
  }

  const bootstrap = scoreTick ?? (data
    ? { homeTeam: data.homeTeam, awayTeam: data.awayTeam,
        currentScore: data.currentScore, minute: data.minute, periodLabel: data.periodLabel }
    : null);

  const opportunityCount = data?.strategy?.opportunityCount ?? 0;
  const strongCount = data?.strategy?.strongOpportunityCount ?? 0;

  return (
    <PageTransition className="space-y-4">

      {/* ── Navegação superior ── */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/8 bg-white/[0.02] px-4 py-3">
        <Link
          to="/ao-vivo"
          className="inline-flex items-center gap-2 text-sm font-medium text-slate-400 transition-colors hover:text-white"
        >
          <IconArrowLeft className="h-4 w-4" />
          Todos os jogos ao vivo
        </Link>
        <div className="flex items-center gap-2">
          {data?.isLive && !data?.isFinished && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-red-500/30 bg-red-500/10 px-3 py-1 text-[11px] font-semibold text-red-300">
              <span className="h-2 w-2 animate-pulse rounded-full bg-red-500" />
              AO VIVO
            </span>
          )}
          <span className="rounded-full border border-white/8 bg-slate-900/60 px-3 py-1 text-[11px] font-medium text-slate-400">
            Superbet #{eventId}
          </span>
        </div>
      </div>

      {/* ── Conteúdo principal ── */}
      {isLoading ? (
        <DashboardSkeleton />
      ) : isError ? (
        <ErrorState
          message={error instanceof Error ? error.message : "Falha ao capturar jogo na Superbet"}
          onRetry={refetch}
        />
      ) : (
        <>
          {data ? (
            <>
              {/* ══ TOPO FIXO: Hero + KPIs + Alertas ══ */}
              <LiveDashboardHero
                data={data}
                liveHeader={liveHeader}
                adviceSource={adviceSource ?? "fast"}
                onRefresh={refetch}
                isFetching={isFetching}
              />

              <LiveRecalibrationBanner event={recalibrationEvent} />
              <LiveP0GuardBanner guardrails={data.betGuardrails} />
              <LiveAgainstModelAlert alerts={data.againstModelAlerts ?? []} />
              <LiveHedgeAlert report={data.hedgeReport ?? null} />

              <LiveDirectionKpis data={data} />

              {/* ══ ABAS ══ */}
              <div className="sticky top-0 z-20 -mx-1 rounded-2xl border border-white/8 bg-slate-950/90 px-1 py-2 backdrop-blur-md">
                <div className="flex gap-1">
                  {TABS.map((tab) => {
                    const isActive = activeTab === tab.id;
                    const showBadge = tab.id === "apostar" && opportunityCount > 0;
                    return (
                      <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        title={tab.hint}
                        className={`relative flex flex-1 flex-col items-center gap-0.5 rounded-xl px-2 py-2 text-center transition-all duration-200 ${
                          isActive
                            ? "bg-neon-blue/15 text-white shadow-sm"
                            : "text-slate-500 hover:bg-white/5 hover:text-slate-300"
                        }`}
                      >
                        <span className="text-base leading-none">{tab.emoji}</span>
                        <span className="text-[11px] font-semibold leading-tight">{tab.label}</span>
                        {isActive && (
                          <span className="absolute bottom-0 left-1/2 h-0.5 w-8 -translate-x-1/2 rounded-full bg-neon-blue" />
                        )}
                        {showBadge && (
                          <span className="absolute right-2 top-2 flex h-4 w-4 items-center justify-center rounded-full bg-neon-green text-[9px] font-bold text-black">
                            {strongCount > 0 ? strongCount : opportunityCount}
                          </span>
                        )}
                        {tab.id === "bilhete" && riskAlerts.length > 0 && (
                          <span className="absolute right-2 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[9px] font-bold text-white animate-pulse">
                            !
                          </span>
                        )}
                        {tab.id === "bilhete" && ticket.legs.length > 0 && riskAlerts.length === 0 && (
                          <span className="absolute right-2 top-2 flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500 text-[9px] font-bold text-black">
                            {ticket.legs.length}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* ══ ABA: APOSTAR AGORA ══ */}
              {activeTab === "apostar" && (
                <div className="space-y-4">

                  {/* Picks do jogo com AddBtn */}
                  {liveSuggestions.length > 0 && (
                    <div className="rounded-2xl border border-white/8 bg-white/[0.02] overflow-hidden">
                      <div className="flex items-center justify-between px-4 py-3 border-b border-white/6">
                        <div className="flex items-center gap-2">
                          <span className="text-sm">⚡</span>
                          <span className="text-sm font-bold text-white">Picks deste jogo</span>
                          <span className="text-[10px] text-slate-500 bg-slate-800/60 px-2 py-0.5 rounded-full">
                            {data?.homeTeam} × {data?.awayTeam}
                            {data?.currentScore && (
                              <span className="ml-1 font-mono text-white">{data.currentScore}</span>
                            )}
                            {data?.minute != null && (
                              <span className="ml-1 text-amber-400">{data.minute}&apos;</span>
                            )}
                          </span>
                        </div>
                        <button
                          onClick={() => setActiveTab("bilhete")}
                          className="text-[10px] text-neon-blue hover:text-white transition-colors font-semibold"
                        >
                          Ver bilhete →
                        </button>
                      </div>
                      <div className="divide-y divide-white/5">
                        {liveSuggestions.map((leg) => (
                          <div key={leg.id} className="flex items-center gap-3 px-4 py-3">
                            <AddBtn leg={leg} ticket={ticket} />
                            <div className="flex-1 min-w-0">
                              <div className="text-xs text-slate-500 truncate mb-0.5">{leg.market}</div>
                              <div className="text-sm font-semibold text-white truncate">{leg.label}</div>
                            </div>
                            <div className="text-right shrink-0">
                              <div className="text-base font-black font-mono text-emerald-300">{leg.fairOdd.toFixed(2)}</div>
                              <div className="text-[10px] text-slate-500">
                                EV {((leg.fairOdd * leg.modelProb - 1) * 100).toFixed(1)}%
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Upload de análise pré-jogo */}
                  <LiveContextUpload
                    eventId={eventId}
                    activeContext={data.matchContext ?? null}
                    onContextChanged={refetch}
                  />

                  {/* CTA principal */}
                  <LiveActionNowPanel data={data} trackBet={false} />

                  {/* Bilhetes otimizados */}
                  <LiveOptimizedTicketsPanel data={data} />

                  {/* Melhor retorno esperado */}
                  <LiveTopReturnPanel data={data} />

                  {/* Bilhetes 1T / 2T */}
                  <LiveHalfTicketsPanel data={data} />

                  {/* Melhores combos */}
                  <LiveBestCombosPanel data={data} />

                  {/* Mercados 2T viáveis */}
                  <CollapsibleSection title="Mercados 2T viáveis" defaultOpen={true}>
                    <LiveRemaining2hMarketsPanel data={data} />
                  </CollapsibleSection>

                  {/* Longshots */}
                  <CollapsibleSection title="Longshots (alto retorno)" defaultOpen={false}>
                    <LiveLongshotCombosPanel data={data} />
                  </CollapsibleSection>

                  {/* Estratégia de aposta */}
                  <CollapsibleSection title="Estratégia completa" defaultOpen={false}>
                    <BetStrategyPanel strategy={data.strategy} />
                  </CollapsibleSection>

                  {/* Bet Builder Guard */}
                  <CollapsibleSection title="Bet Builder — validação" defaultOpen={false}>
                    <LiveBetBuilderGuardPanel guardrails={data.betGuardrails} />
                  </CollapsibleSection>
                </div>
              )}

              {/* ══ ABA: MERCADOS & EV ══ */}
              {activeTab === "mercados" && (
                <div className="space-y-4">
                  {/* Modelo vs mercado — painel principal */}
                  <LiveModelVsMarketHero data={data} />

                  {/* EV real + leaderboard lado a lado */}
                  <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                    <LiveEvRealPanel data={data} />
                    <LiveEvLeaderboard data={data} />
                  </div>

                  {/* Escanteios */}
                  <LiveCornersPanel data={data} />

                  {/* Cards de mercado com EV */}
                  <CollapsibleSection title="Todos os mercados com EV">
                    <LiveMarketCards data={data} />
                  </CollapsibleSection>

                  {/* Stats ao vivo */}
                  <CollapsibleSection title="Stats ao vivo" defaultOpen={true}>
                    <LiveStatsCompactBar data={data} eventId={eventId} />
                  </CollapsibleSection>
                </div>
              )}

              {/* ══ ABA: ANÁLISE ══ */}
              {activeTab === "analise" && (
                <div className="space-y-4">
                  {/* Posse + stats gerais */}
                  <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                    <LivePossessionPanel data={data} history={possessionHistory} />
                    <LiveMatchStatsPanel data={data} />
                  </div>

                  {/* Timeline + Forma/H2H */}
                  <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                    <LiveTimelinePanel
                      data={data}
                      highlightGoalMinute={timelineReactive.latestGoalMinute}
                      reactiveBoosted={timelineReactive.boosted}
                    />
                    <LiveFormH2hPanel data={data} />
                  </div>

                  {/* Evolução das probabilidades */}
                  <CollapsibleSection title="Evolução das probabilidades">
                    <LivePredictionEvolutionChart data={data} />
                  </CollapsibleSection>

                  {/* Sinais de tendência */}
                  <CollapsibleSection title="Sinais de tendência" defaultOpen={true}>
                    <LiveTrendSignals data={data} />
                  </CollapsibleSection>

                  {/* Heatmap de placares */}
                  <CollapsibleSection title="Heatmap de placares" defaultOpen={false}>
                    <LiveScoreHeatmap data={data} />
                  </CollapsibleSection>

                  {/* Stats por jogador + social */}
                  <CollapsibleSection title="Jogadores & Radar social" defaultOpen={false}>
                    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                      <LivePlayerStatsPanel data={data} />
                      <LiveSocialRadarPanel data={data} />
                    </div>
                  </CollapsibleSection>
                </div>
              )}

              {/* ══ ABA: MEU BILHETE ══ */}
              {activeTab === "bilhete" && (
                <div className="space-y-4">
                  {/* 1. Monitor de risco ao vivo */}
                  {riskAlerts.length > 0 && (
                    <LiveOddsDropAlert
                      alerts={riskAlerts}
                      onDismiss={(id) =>
                        setRiskAlerts((prev) => prev.filter((a) => a.id !== id))
                      }
                    />
                  )}

                  {/* 2. Apostas abertas na Superbet (capturadas pela extensão) */}
                  <LiveOpenBetsPanel
                    eventId={eventId}
                    homeTeam={data?.homeTeam}
                    awayTeam={data?.awayTeam}
                  />

                  {/* 3. Bilhetes otimizados pelo modelo */}
                  {data && <LiveOptimizedTicketsPanel data={data} />}

                  {/* 4. Bilhete manual (simulador) */}
                  <TicketSimulator ticket={ticket} suggestions={liveSuggestions} />
                </div>
              )}
            </>
          ) : bootstrap ? (
            <LiveBootstrapHero
              homeTeam={bootstrap.homeTeam}
              awayTeam={bootstrap.awayTeam}
              score={bootstrap.currentScore ?? "0x0"}
              minute={bootstrap.minute ?? 0}
              periodLabel={bootstrap.periodLabel ?? null}
            />
          ) : null}

          {isAdvicePending && (
            <p className="text-center text-[11px] text-slate-500" aria-live="polite">
              Calculando probabilidades e mercados…
            </p>
          )}
        </>
      )}

      {isFetching && data && (
        <p className="text-center text-[11px] text-slate-500" aria-live="polite">
          Atualizando painel…
        </p>
      )}

      {activeTab !== "bilhete" && (
        <FloatingTicketBadge
          count={ticket.legs.length}
          onClick={() => setActiveTab("bilhete")}
        />
      )}
    </PageTransition>
  );
}
