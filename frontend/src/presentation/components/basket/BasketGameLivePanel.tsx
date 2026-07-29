import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getBasketSuperbetLiveAdviceUseCase } from "@/application/container";
import type { BasketSuperbetLiveAdvice } from "@/domain/entities";
import { LiveMatchProgressBar } from "@/presentation/components/live-dashboard/LiveMatchProgressBar";
import { LiveDashboardTabs } from "@/presentation/components/live-dashboard/LiveDashboardTabs";
import { LiveCopilotPanel } from "@/presentation/components/live-dashboard/LiveCopilotPanel";
import { useLiveCopilotQuery } from "@/presentation/hooks/useLiveCopilotQuery";
import { useLiveCopilotActionAlerts } from "@/presentation/hooks/useLiveCopilotActionAlerts";
import { useLiveCopilotAgentSession } from "@/presentation/hooks/useLiveCopilotAgentSession";
import { useCopilotAlertsPreference } from "@/presentation/hooks/useCopilotAlertsPreference";
import {
  ModelSimulationMeta,
  PpmPacePanel,
  SpreadLinesTable,
  TotalLinesTable,
} from "@/presentation/components/live-dashboard/BasketModelPanels";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import {
  BasketLiveContentSkeleton,
  MatchScoreboardSkeleton,
} from "@/presentation/components/ui/Skeleton";
import {
  BASKET_LIVE_POLL_MS,
  BasketKpiCard,
  buildBasketKpis,
  DEFAULT_BASKET_MATCH_MINUTES,
  formatCapturedAt,
  formatPct,
  formatPoints,
  MarketRow,
  OpportunityCard,
  ProjectionPanel,
  QuarterPaceChart,
  QuarterScoreTable,
  type BasketLiveTab,
} from "@/presentation/components/basket/basketLiveWidgets";

export interface BasketGameLivePanelProps {
  eventId: number;
  showCopilot?: boolean;
  collapsible?: boolean;
  defaultExpanded?: boolean;
  stickyHeader?: boolean;
  anchorId?: string;
  onAdviceLoaded?: (data: BasketSuperbetLiveAdvice) => void;
  onQueryMetaChange?: (meta: {
    isFetching: boolean;
    refetch: () => void;
    capturedAt: string | null;
    isLive: boolean;
  }) => void;
}

export function BasketGameLivePanel({
  eventId,
  showCopilot = false,
  collapsible = false,
  defaultExpanded = true,
  stickyHeader = true,
  anchorId,
  onAdviceLoaded,
  onQueryMetaChange,
}: BasketGameLivePanelProps) {
  const enabled = Number.isFinite(eventId) && eventId > 0;
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [activeTab, setActiveTab] = useState<BasketLiveTab>("resumo");

  const adviceQuery = useQuery({
    queryKey: ["basket-superbet-live-advice", eventId],
    queryFn: () => getBasketSuperbetLiveAdviceUseCase.execute({ eventId, fast: true }),
    enabled,
    staleTime: 8_000,
    refetchInterval: (q) => {
      const d = q.state.data;
      if (!d?.isLive || d?.isFinished) return false;
      return BASKET_LIVE_POLL_MS;
    },
  });

  const data = adviceQuery.data;
  const kpis = useMemo(() => (data ? buildBasketKpis(data) : null), [data]);
  const matchMinutes = data?.inplaySummary.matchMinutes ?? DEFAULT_BASKET_MATCH_MINUTES;
  const headerIsLiveEarly = Boolean(data?.isLive && !data?.isFinished);
  const { alertsActive: copilotAlertsActive } = useCopilotAlertsPreference();

  const copilotQuery = useLiveCopilotQuery({
    eventId,
    sport: "basketball",
    bankroll: 1000,
    enabled: enabled && showCopilot && headerIsLiveEarly,
  });

  useLiveCopilotActionAlerts(copilotQuery.data, {
    eventId,
    homeTeam: data?.homeTeam,
    awayTeam: data?.awayTeam,
    enabled: enabled && showCopilot && headerIsLiveEarly && copilotAlertsActive,
  });

  const { displayCopilot, agentChat } = useLiveCopilotAgentSession({
    eventId,
    sport: "basketball",
    bankroll: 1000,
    enabled: enabled && showCopilot && headerIsLiveEarly,
    baseCopilot: copilotQuery.data,
    onSwitchTab: (tab) => {
      if (tab === "resumo" || tab === "mercados" || tab === "qualidade") {
        setActiveTab(tab);
        setExpanded(true);
      }
    },
  });

  useEffect(() => {
    if (data && onAdviceLoaded) onAdviceLoaded(data);
  }, [data, onAdviceLoaded]);

  useEffect(() => {
    if (!onQueryMetaChange) return;
    onQueryMetaChange({
      isFetching: adviceQuery.isFetching,
      refetch: () => void adviceQuery.refetch(),
      capturedAt: data?.capturedAt ?? null,
      isLive: Boolean(data?.isLive && !data?.isFinished),
    });
  }, [
    adviceQuery.isFetching,
    adviceQuery.refetch,
    data?.capturedAt,
    data?.isLive,
    data?.isFinished,
    onQueryMetaChange,
  ]);

  const headerIsLive = Boolean(data?.isLive && !data?.isFinished);
  const scoreParts = (data?.currentScore ?? "0x0").split(/x/i).map((s) => s.trim());

  const TABS: { id: BasketLiveTab; label: string; count?: number }[] = [
    { id: "resumo", label: "Resumo Operacional" },
    { id: "mercados", label: "Mercados", count: kpis?.positiveEv || undefined },
    { id: "qualidade", label: "Qualidade dos Dados" },
  ];

  const scoreboard = data ? (
    <div className="live-scoreboard">
      <div className="relative flex items-center justify-between gap-4 px-5 py-4">
        {collapsible ? (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="absolute left-3 top-3 rounded-md border border-white/10 px-2 py-1 text-[10px] text-slate-400 hover:text-white"
          >
            {expanded ? "Recolher" : "Expandir"}
          </button>
        ) : null}
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-full border border-white/12 bg-white/[0.06]">
            <TeamFlag team={data.homeTeam} size={44} />
          </div>
          <span className="truncate text-base font-bold text-white sm:text-lg">{data.homeTeam}</span>
        </div>
        <div className="flex shrink-0 flex-col items-center px-2">
          <div className="flex items-center gap-3 font-mono text-4xl font-extrabold leading-none text-white">
            <span>{scoreParts[0] ?? "0"}</span>
            <span className="text-2xl text-slate-500">×</span>
            <span>{scoreParts[1] ?? "0"}</span>
          </div>
          <span className="mt-1.5 text-xs font-semibold text-amber-300">
            {data.minute}&apos;
            {data.periodLabel ? ` · ${data.periodLabel}` : ""}
            {headerIsLive ? " · Ao vivo" : ""}
          </span>
        </div>
        <div className="flex min-w-0 flex-1 items-center justify-end gap-3">
          <span className="truncate text-right text-base font-bold text-white sm:text-lg">{data.awayTeam}</span>
          <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-full border border-white/12 bg-white/[0.06]">
            <TeamFlag team={data.awayTeam} size={44} />
          </div>
        </div>
      </div>
      {headerIsLive && (
        <div className="px-5 pb-5 pt-1">
          <LiveMatchProgressBar minute={data.minute} isLive matchMinutes={matchMinutes} />
        </div>
      )}
      {collapsible ? (
        <div className="flex items-center justify-between border-t border-white/5 px-5 py-2 text-[11px] text-slate-500">
          <span>ID {eventId} · atualizado {formatCapturedAt(data.capturedAt)}</span>
          <Link
            to={`/ao-vivo/basquete/${eventId}`}
            className="text-amber-300 hover:underline"
          >
            Painel dedicado
          </Link>
        </div>
      ) : null}
    </div>
  ) : adviceQuery.isLoading ? (
    <MatchScoreboardSkeleton />
  ) : null;

  const tabContent = data && kpis && expanded ? (
    <div className="space-y-4 p-4 pt-3">
      {data.superbetStale && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-xs text-amber-200">
          Dados Superbet em cache — última captura pode estar desatualizada.
        </div>
      )}

      {activeTab === "resumo" && (
        <div className="space-y-4">
          {showCopilot ? (
            <LiveCopilotPanel
              copilot={displayCopilot}
              isLoading={copilotQuery.isLoading}
              isFetching={copilotQuery.isFetching}
              agentChat={agentChat}
            />
          ) : null}

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
            <div className="live-glass-panel-glow glow-border rounded-2xl p-4">
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <h2 className="text-xs font-black uppercase tracking-widest text-white">Ritmo por quarto</h2>
                <span className="rounded-full border border-neon-green/20 bg-neon-green/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-widest text-neon-green">
                  Ao Vivo
                </span>
                <span className="ml-auto flex items-center gap-3 font-mono text-sm">
                  <span className="text-neon-green neon-text">{formatPct(data.inplaySummary.probHomeWin)}</span>
                  <span className="text-slate-600">·</span>
                  <span className="text-sky-400">{formatPct(data.inplaySummary.probAwayWin)}</span>
                </span>
              </div>
              <QuarterPaceChart periods={data.basketPeriods} homeTeam={data.homeTeam} awayTeam={data.awayTeam} />
              <div className="mt-4">
                <ProjectionPanel summary={data.inplaySummary} homeTeam={data.homeTeam} awayTeam={data.awayTeam} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 xl:grid-cols-2">
              <BasketKpiCard label="Moneyline líder" value={formatPct(kpis.leaderProb)} sub={kpis.leader} accentColor="#00f5a0" icon="ml" />
              <BasketKpiCard
                label="Total vs linha"
                value={kpis.totalDelta != null ? `${kpis.totalDelta > 0 ? "+" : ""}${kpis.totalDelta.toFixed(1)}` : "—"}
                sub={
                  kpis.expectedTotal != null && kpis.totalLine != null
                    ? `proj. ${formatPoints(kpis.expectedTotal, 0)} · linha ${formatPoints(kpis.totalLine, 1)}`
                    : undefined
                }
                accentColor="#00e0ff"
                icon="total"
              />
              <BasketKpiCard
                label="Spread linha"
                value={kpis.spreadLine != null ? `${kpis.spreadLine > 0 ? "+" : ""}${formatPoints(kpis.spreadLine, 1)}` : "—"}
                sub={`Handicap ${data.homeTeam}`}
                accentColor="#00e0ff"
                icon="spread"
              />
              <BasketKpiCard
                label="Ritmo (PPM)"
                value={kpis.ppmAvg != null ? formatPoints(kpis.ppmAvg, 2) : "—"}
                sub={
                  kpis.ppmHome != null && kpis.ppmAway != null
                    ? `${formatPoints(kpis.ppmHome, 2)} / ${formatPoints(kpis.ppmAway, 2)}`
                    : `${kpis.remaining ?? "—"} min restantes`
                }
                accentColor="#ffd166"
                icon="pace"
              />
              <BasketKpiCard label="Aportes EV+" value={`${kpis.positiveEv}/${kpis.totalAportes}`} sub="moneyline · spread · total" accentColor="#00f5a0" icon="ev" />
              <BasketKpiCard
                label="Confiança"
                value={kpis.confidence ? `${Math.round(kpis.confidence.score * 100)}%` : "—"}
                sub={kpis.confidence?.label ?? "modelo basquete"}
                accentColor="#fbbf24"
                icon="conf"
              />
            </div>
          </div>

          <PpmPacePanel data={data} homeTeam={data.homeTeam} awayTeam={data.awayTeam} />
          <ModelSimulationMeta summary={data.inplaySummary} />

          {data.aportes.length > 0 && (
            <div className="live-glass-panel rounded-2xl p-4">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-xs font-black uppercase tracking-widest text-white">Oportunidades em destaque</h2>
                <span className="rounded-full bg-neon-green/15 px-2 py-0.5 text-[10px] font-bold text-neon-green">
                  {data.aportes.length}
                </span>
              </div>
              <div className="flex gap-3 overflow-x-auto pb-2">
                {data.aportes.slice(0, 6).map((a, i) => (
                  <OpportunityCard key={`${a.market}-${a.outcome}-${i}`} aporte={a} rank={i + 1} />
                ))}
              </div>
            </div>
          )}

          <div className="live-glass-panel overflow-hidden rounded-2xl">
            <div className="border-b border-white/[0.04] px-4 py-3">
              <h2 className="text-xs font-black uppercase tracking-widest text-white">Mercados avaliados</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] text-left">
                <thead>
                  <tr className="border-b border-white/[0.04]">
                    {["Mercado", "Seleção", "Odd", "Modelo", "Edge", "EV", "Kelly", "Stake", "Ação"].map((h) => (
                      <th
                        key={h}
                        className={`py-2 text-[9px] font-black uppercase tracking-widest text-slate-600 ${
                          h === "Mercado" ? "pl-4" : h === "Ação" ? "pr-4" : "px-2"
                        } ${["Odd", "Modelo", "Edge", "EV", "Kelly", "Stake"].includes(h) ? "text-right" : ""}`}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.aportes.length > 0 ? (
                    data.aportes.map((a, i) => (
                      <MarketRow key={`${a.market}-${a.outcome}-${i}`} aporte={a} />
                    ))
                  ) : (
                    <tr>
                      <td colSpan={9} className="px-4 py-8 text-center text-sm text-slate-600">
                        Nenhum mercado com edge no momento.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {activeTab === "mercados" && (
        <div className="space-y-4">
          <div className="live-glass-panel rounded-2xl p-4">
            <h2 className="mb-4 text-xs font-black uppercase tracking-widest text-white">Moneyline</h2>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl border border-white/8 bg-black/20 p-4 text-center">
                <p className="text-[11px] uppercase text-slate-500">{data.homeTeam}</p>
                <p className="mt-1 font-mono text-2xl font-bold text-neon-green">{data.h2hOdds["1"]?.toFixed(2) ?? "—"}</p>
                <p className="mt-1 text-xs text-slate-500">modelo {formatPct(data.inplaySummary.probHomeWin)}</p>
              </div>
              <div className="rounded-xl border border-white/8 bg-black/20 p-4 text-center">
                <p className="text-[11px] uppercase text-slate-500">{data.awayTeam}</p>
                <p className="mt-1 font-mono text-2xl font-bold text-sky-400">{data.h2hOdds["2"]?.toFixed(2) ?? "—"}</p>
                <p className="mt-1 text-xs text-slate-500">modelo {formatPct(data.inplaySummary.probAwayWin)}</p>
              </div>
            </div>
          </div>
          <div className="live-glass-panel overflow-hidden rounded-2xl p-4">
            <h2 className="mb-4 text-xs font-black uppercase tracking-widest text-white">Spread — modelo vs mercado</h2>
            <SpreadLinesTable data={data} />
          </div>
          <div className="live-glass-panel overflow-hidden rounded-2xl p-4">
            <h2 className="mb-4 text-xs font-black uppercase tracking-widest text-white">Total de pontos — modelo vs mercado</h2>
            <TotalLinesTable data={data} />
          </div>
        </div>
      )}

      {activeTab === "qualidade" && (
        <div className="space-y-4">
          <ModelSimulationMeta summary={data.inplaySummary} />
          <div className="live-glass-panel rounded-2xl p-4">
            <h2 className="mb-4 text-xs font-black uppercase tracking-widest text-white">Placar por quarto</h2>
            <QuarterScoreTable
              periods={data.basketPeriods}
              homeTeam={data.homeTeam}
              awayTeam={data.awayTeam}
              currentQuarter={
                data.basketPeriods.length > 0
                  ? data.basketPeriods[data.basketPeriods.length - 1].num
                  : null
              }
            />
          </div>
        </div>
      )}
    </div>
  ) : adviceQuery.isLoading && expanded ? (
    <BasketLiveContentSkeleton />
  ) : adviceQuery.isError && expanded ? (
    <ErrorState
      message={
        adviceQuery.error instanceof Error
          ? adviceQuery.error.message
          : "Falha ao carregar dados do jogo de basquete"
      }
      onRetry={() => adviceQuery.refetch()}
    />
  ) : null;

  return (
    <section id={anchorId} className="mb-6 overflow-hidden rounded-2xl border border-white/8 bg-black/10">
      <div className={stickyHeader && !collapsible ? "sticky top-0 z-20" : undefined}>
        {scoreboard}
        {data && expanded ? (
          <LiveDashboardTabs
            tabs={TABS.map((tab) => ({ id: tab.id, label: tab.label, count: tab.count }))}
            activeId={activeTab}
            onChange={(id) => setActiveTab(id as BasketLiveTab)}
          />
        ) : null}
      </div>
      {tabContent}
    </section>
  );
}
