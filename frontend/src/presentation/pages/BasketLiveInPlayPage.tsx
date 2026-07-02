import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getBasketSuperbetLiveAdviceUseCase } from "@/application/container";
import type { BasketAporteAdvice, BasketQuarterScore } from "@/domain/entities";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { IconArrowLeft } from "@/presentation/components/ui/Icons";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";

const LIVE_POLL_MS = 5_000;

function formatPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(0)}%`;
}

function formatPoints(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(1);
}

function ActionBadge({ action }: { action: string }) {
  const styles: Record<string, string> = {
    bet: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    strong_bet: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
    watch: "bg-amber-500/15 text-amber-300 border-amber-500/25",
    avoid: "bg-slate-500/10 text-slate-400 border-white/10",
  };
  const cls = styles[action] ?? styles.watch;
  return (
    <span className={`inline-flex rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${cls}`}>
      {action}
    </span>
  );
}

function QuarterScoreTable({
  periods,
  homeTeam,
  awayTeam,
  currentQuarterInProgress,
}: {
  periods: BasketQuarterScore[];
  homeTeam: string;
  awayTeam: string;
  currentQuarterInProgress: number | null;
}) {
  if (periods.length === 0) {
    return <p className="px-5 py-6 text-sm text-slate-500">Placar por quarto ainda não disponível.</p>;
  }
  const homeTotal = periods.reduce((sum, p) => sum + p.home, 0);
  const awayTotal = periods.reduce((sum, p) => sum + p.away, 0);
  return (
    <div className="overflow-x-auto px-5 pb-5">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-widest text-slate-500">
            <th className="py-2 pr-3">Time</th>
            {periods.map((p) => (
              <th key={p.num} className="px-2 py-2 text-center">
                Q{p.num}
                {p.num === currentQuarterInProgress ? <span className="text-amber-300"> •</span> : ""}
              </th>
            ))}
            <th className="px-2 py-2 text-center">Total</th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-t border-white/5">
            <td className="py-2 pr-3 font-medium text-white">{homeTeam}</td>
            {periods.map((p) => (
              <td key={p.num} className="px-2 py-2 text-center font-mono text-slate-300">
                {p.home}
              </td>
            ))}
            <td className="px-2 py-2 text-center font-mono font-semibold text-white">{homeTotal}</td>
          </tr>
          <tr className="border-t border-white/5">
            <td className="py-2 pr-3 font-medium text-white">{awayTeam}</td>
            {periods.map((p) => (
              <td key={p.num} className="px-2 py-2 text-center font-mono text-slate-300">
                {p.away}
              </td>
            ))}
            <td className="px-2 py-2 text-center font-mono font-semibold text-white">{awayTotal}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function AporteRow({ aporte }: { aporte: BasketAporteAdvice }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-white/5 px-4 py-3 last:border-b-0">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-white">{aporte.label}</p>
        <p className="text-[11px] text-slate-500">
          {aporte.market} · modelo {formatPct(aporte.modelProb)} · odd {aporte.marketOdd.toFixed(2)}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <span className="font-mono text-xs text-emerald-300">
          EV {aporte.expectedValue >= 0 ? "+" : ""}
          {(aporte.expectedValue * 100).toFixed(1)}%
        </span>
        <ActionBadge action={aporte.action} />
      </div>
    </div>
  );
}

export function BasketLiveInPlayPage() {
  const params = useParams<{ eventId: string }>();
  const eventId = Number(params.eventId);
  const enabled = Number.isFinite(eventId) && eventId > 0;

  const adviceQuery = useQuery({
    queryKey: ["basket-superbet-live-advice", eventId],
    queryFn: () => getBasketSuperbetLiveAdviceUseCase.execute({ eventId, fast: true }),
    enabled,
    staleTime: 8_000,
    refetchInterval: (q) => {
      const d = q.state.data;
      if (!d?.isLive || d?.isFinished) return false;
      return LIVE_POLL_MS;
    },
  });

  const data = adviceQuery.data;

  return (
    <PageTransition>
      <Link
        to="/ao-vivo"
        className="mb-4 inline-flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-white"
      >
        <IconArrowLeft className="h-3.5 w-3.5" />
        Voltar para ao vivo
      </Link>

      {adviceQuery.isLoading ? (
        <DashboardSkeleton />
      ) : adviceQuery.isError || !data ? (
        <ErrorState
          message={
            adviceQuery.error instanceof Error
              ? adviceQuery.error.message
              : "Falha ao carregar dados do jogo de basquete"
          }
          onRetry={() => adviceQuery.refetch()}
        />
      ) : (
        <>
          <div className="mb-6 rounded-2xl border border-white/8 bg-white/[0.02] p-5">
            <div className="flex items-center justify-between gap-4">
              <div className="flex min-w-0 flex-1 items-center gap-2">
                <TeamFlag team={data.homeTeam} size={28} />
                <span className="truncate text-base font-semibold text-white">{data.homeTeam}</span>
              </div>
              <div className="flex flex-col items-center gap-1 px-4">
                <span className="font-mono text-2xl font-bold text-white">
                  {data.currentScore ?? "0 x 0"}
                </span>
                <span className="rounded-md bg-amber-500/15 px-2 py-0.5 text-[11px] font-semibold text-amber-300">
                  {data.periodLabel ? `${data.minute}' · ${data.periodLabel}` : `${data.minute}'`}
                </span>
              </div>
              <div className="flex min-w-0 flex-1 items-center justify-end gap-2">
                <span className="truncate text-base font-semibold text-white">{data.awayTeam}</span>
                <TeamFlag team={data.awayTeam} size={28} />
              </div>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-3">
              <div className="rounded-xl border border-white/8 bg-white/[0.02] p-3 text-center">
                <p className="text-[11px] uppercase tracking-wide text-slate-500">{data.homeTeam}</p>
                <p className="mt-1 font-mono text-xl font-bold text-emerald-300">
                  {formatPct(data.inplaySummary.probHomeWin)}
                </p>
              </div>
              <div className="rounded-xl border border-white/8 bg-white/[0.02] p-3 text-center">
                <p className="text-[11px] uppercase tracking-wide text-slate-500">{data.awayTeam}</p>
                <p className="mt-1 font-mono text-xl font-bold text-purple-300">
                  {formatPct(data.inplaySummary.probAwayWin)}
                </p>
              </div>
            </div>

            {data.confidence ? (
              <div className="mt-4 rounded-xl border border-white/8 bg-white/[0.02] px-4 py-3">
                <p className="text-xs font-semibold text-white">
                  Confiança: {data.confidence.label} ({(data.confidence.score * 100).toFixed(0)}%)
                </p>
                <p className="mt-0.5 text-[11px] text-slate-500">
                  Maior edge encontrado: {data.confidence.maxEdgePp.toFixed(1)} p.p.
                </p>
              </div>
            ) : null}
          </div>

          <section className="mb-6 rounded-2xl border border-white/8 bg-white/[0.02]">
            <h2 className="px-5 pt-5 text-xs font-semibold uppercase tracking-widest text-slate-400">
              Placar por quarto
            </h2>
            <QuarterScoreTable
              periods={data.basketPeriods}
              homeTeam={data.homeTeam}
              awayTeam={data.awayTeam}
              currentQuarterInProgress={
                data.basketPeriods.length > 0
                  ? data.basketPeriods[data.basketPeriods.length - 1].num
                  : null
              }
            />
          </section>

          {data.inplaySummary.nextQuarterNumber != null ? (
            <section className="mb-6 rounded-2xl border border-white/8 bg-white/[0.02] p-5">
              <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-400">
                Projeção pro Q{data.inplaySummary.nextQuarterNumber} (modelo)
              </h2>
              <div className="grid grid-cols-2 gap-3 text-center">
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-slate-500">{data.homeTeam}</p>
                  <p className="mt-1 font-mono text-xl font-bold text-emerald-300">
                    {formatPoints(data.inplaySummary.nextQuarterProjectionHome)}
                  </p>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-slate-500">{data.awayTeam}</p>
                  <p className="mt-1 font-mono text-xl font-bold text-purple-300">
                    {formatPoints(data.inplaySummary.nextQuarterProjectionAway)}
                  </p>
                </div>
              </div>
            </section>
          ) : null}

          <section className="mb-6 rounded-2xl border border-white/8 bg-white/[0.02] p-5">
            <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-400">
              Cestas &amp; Projeções até o fim
            </h2>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div>
                <p className="text-[11px] uppercase tracking-wide text-slate-500">{data.homeTeam}</p>
                <p className="mt-1 font-mono text-lg font-semibold text-white">
                  {formatPoints(data.inplaySummary.expectedFinalHome)}
                </p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-wide text-slate-500">Total</p>
                <p className="mt-1 font-mono text-lg font-semibold text-white">
                  {formatPoints(data.inplaySummary.expectedTotal)}
                </p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-wide text-slate-500">{data.awayTeam}</p>
                <p className="mt-1 font-mono text-lg font-semibold text-white">
                  {formatPoints(data.inplaySummary.expectedFinalAway)}
                </p>
              </div>
            </div>
            {data.inplaySummary.marketSpreadLine != null || data.inplaySummary.marketTotalLine != null ? (
              <p className="mt-4 text-[11px] text-slate-500">
                {data.inplaySummary.marketSpreadLine != null
                  ? `Linha de handicap: ${data.inplaySummary.marketSpreadLine > 0 ? "+" : ""}${data.inplaySummary.marketSpreadLine}`
                  : ""}
                {data.inplaySummary.marketSpreadLine != null && data.inplaySummary.marketTotalLine != null
                  ? " · "
                  : ""}
                {data.inplaySummary.marketTotalLine != null
                  ? `Linha de total de pontos: ${data.inplaySummary.marketTotalLine}`
                  : ""}
              </p>
            ) : null}
          </section>

          <section className="rounded-2xl border border-white/8 bg-white/[0.02]">
            <h2 className="px-5 pt-5 text-xs font-semibold uppercase tracking-widest text-slate-400">
              Aportes sugeridos
            </h2>
            {data.aportes.length === 0 ? (
              <p className="px-5 py-6 text-sm text-slate-500">Nenhuma oportunidade de aporte no momento.</p>
            ) : (
              <div className="mt-3">
                {data.aportes.map((aporte, idx) => (
                  <AporteRow key={`${aporte.market}-${aporte.outcome}-${idx}`} aporte={aporte} />
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </PageTransition>
  );
}
