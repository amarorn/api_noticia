import { Link, useParams } from "react-router-dom";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { IconArrowLeft } from "@/presentation/components/ui/Icons";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";
import { LiveActionNowPanel } from "@/presentation/components/predictions/LiveActionNowPanel";
import { LiveHalfTicketsPanel } from "@/presentation/components/predictions/LiveHalfTicketsPanel";
import { LiveRemaining2hMarketsPanel } from "@/presentation/components/predictions/LiveRemaining2hMarketsPanel";
import { LiveLongshotCombosPanel } from "@/presentation/components/predictions/LiveLongshotCombosPanel";
import { LiveMarketCards } from "@/presentation/components/predictions/LiveMarketCards";
import { LiveScoreHeatmap } from "@/presentation/components/predictions/LiveScoreHeatmap";
import { LiveP0GuardBanner } from "@/presentation/components/predictions/LiveP0GuardBanner";
import LiveAgainstModelAlert from "@/presentation/components/predictions/LiveAgainstModelAlert";
import LiveHedgeAlert from "@/presentation/components/predictions/LiveHedgeAlert";
import { LiveRecalibrationBanner } from "@/presentation/components/predictions/LiveRecalibrationBanner";
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

function LiveBootstrapHero({
  homeTeam,
  awayTeam,
  score,
  minute,
  periodLabel,
}: {
  homeTeam: string;
  awayTeam: string;
  score: string;
  minute: number;
  periodLabel: string | null;
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
            {minute}&apos;
            {periodLabel ? ` · ${periodLabel}` : ""}
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

export function LiveDashboardPage() {
  const { eventId: eventIdParam } = useParams();
  const eventId = Number.parseInt(eventIdParam ?? "", 10);

  const {
    data,
    scoreTick,
    liveHeader,
    adviceSource,
    isLoading,
    isAdvicePending,
    isError,
    error,
    isFetching,
    refetch,
  } = useLiveAdviceQueries(eventId);

  const possessionHistory = useLivePossessionHistory(data);
  const recalibrationEvent = useLiveRecalibration(data, isFetching);

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
    ? {
        homeTeam: data.homeTeam,
        awayTeam: data.awayTeam,
        currentScore: data.currentScore,
        minute: data.minute,
        periodLabel: data.periodLabel,
      }
    : null);

  return (
    <PageTransition className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to={`/ao-vivo/${eventId}`}
          className="inline-flex items-center gap-2 text-sm text-slate-400 transition-colors hover:text-white"
        >
          <IconArrowLeft className="h-4 w-4" />
          Vista clássica
        </Link>
        <div className="flex items-center gap-2">
          <span className="rounded-full border border-neon-blue/30 bg-neon-blue/10 px-3 py-1 text-[11px] font-semibold text-neon-blue">
            Painel visual
          </span>
          <Link
            to="/ao-vivo"
            className="text-[11px] text-slate-500 hover:text-slate-300"
          >
            Todos os jogos
          </Link>
        </div>
      </div>

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
              <LiveDashboardHero
                data={data}
                liveHeader={liveHeader}
                adviceSource={adviceSource ?? "fast"}
                onRefresh={refetch}
                isFetching={isFetching}
              />

              <LiveRecalibrationBanner event={recalibrationEvent} />

              <LiveDirectionKpis data={data} />

              <LiveActionNowPanel data={data} trackBet={false} />

              <LiveHalfTicketsPanel data={data} />

              <LiveRemaining2hMarketsPanel data={data} />

              <LiveLongshotCombosPanel data={data} />

              <LiveP0GuardBanner guardrails={data.betGuardrails} />
              <LiveAgainstModelAlert alerts={data.againstModelAlerts ?? []} />
              <LiveHedgeAlert report={data.hedgeReport ?? null} />

              <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                <LivePossessionPanel data={data} history={possessionHistory} />
                <LiveMatchStatsPanel data={data} />
              </div>

              <LivePredictionEvolutionChart data={data} />

              <LiveEvLeaderboard data={data} />

              <LiveTrendSignals data={data} />

              <section className="rounded-2xl border border-white/8 bg-white/[0.02] p-4">
                <h2 className="mb-3 text-sm font-semibold text-white">Mercados com EV</h2>
                <LiveMarketCards data={data} />
              </section>

              <LiveScoreHeatmap data={data} />
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
    </PageTransition>
  );
}
