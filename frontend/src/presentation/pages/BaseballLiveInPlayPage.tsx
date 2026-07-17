import { useEffect, useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getBaseballSuperbetLiveAdviceUseCase } from "@/application/container";
import type { BaseballSuperbetLiveAdvice } from "@/domain/entities";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { useLiveDashboardChrome } from "@/presentation/components/layout/liveDashboardChromeContext";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";

const LIVE_POLL_MS = 8_000;

function formatPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(0)}%`;
}

function formatNum(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

function formatCapturedAt(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date(iso));
  } catch {
    return "—";
  }
}

export function BaseballLiveInPlayPage() {
  const { eventId: eventIdParam } = useParams();
  const eventId = Number(eventIdParam);
  const { setChrome } = useLiveDashboardChrome();

  const adviceQuery = useQuery({
    queryKey: ["baseball-superbet-live-advice", eventId],
    queryFn: () =>
      getBaseballSuperbetLiveAdviceUseCase.execute({
        eventId,
        bankroll: 1000,
        fast: true,
      }),
    enabled: Number.isFinite(eventId) && eventId > 0,
    refetchInterval: LIVE_POLL_MS,
  });

  const data = adviceQuery.data as BaseballSuperbetLiveAdvice | undefined;
  const summary = data?.inplaySummary;

  useEffect(() => {
    setChrome({
      isLive: Boolean(data?.isLive),
      lastUpdate: formatCapturedAt(data?.capturedAt),
      nextUpdate: `${Math.round(LIVE_POLL_MS / 1000)}s`,
      isFetching: adviceQuery.isFetching,
      onRefresh: () => {
        void adviceQuery.refetch();
      },
    });
    return () => setChrome(null);
  }, [data?.isLive, data?.capturedAt, adviceQuery.isFetching, adviceQuery.refetch, setChrome]);

  const topAportes = useMemo(
    () => (data?.aportes ?? []).filter((a) => a.action === "apostar").slice(0, 5),
    [data?.aportes],
  );

  if (!Number.isFinite(eventId) || eventId <= 0) {
    return (
      <PageTransition>
        <ErrorState message="Evento inválido." />
      </PageTransition>
    );
  }

  return (
    <PageTransition>
      <div className="mx-auto max-w-5xl space-y-6 px-4 py-6">
        <div className="flex items-center justify-between gap-3">
          <Link to="/ao-vivo" className="text-sm text-slate-400 hover:text-white">
            ← Ao vivo
          </Link>
          {data?.superbetStale ? (
            <span className="rounded-full bg-amber-500/15 px-2.5 py-1 text-[11px] text-amber-300">
              Snapshot stale
            </span>
          ) : null}
        </div>

        {adviceQuery.isLoading ? (
          <DashboardSkeleton />
        ) : adviceQuery.isError || !data ? (
          <ErrorState
            message={
              adviceQuery.error instanceof Error
                ? adviceQuery.error.message
                : "Falha ao carregar advice de beisebol"
            }
            onRetry={() => adviceQuery.refetch()}
          />
        ) : (
          <>
            <section className="rounded-2xl border border-white/10 bg-black/30 p-5">
              <div className="mb-2 text-xs uppercase tracking-wider text-emerald-400/80">
                Beisebol · {data.periodLabel ?? `${data.inning}I`}
                {data.isLive ? " · ao vivo" : ""}
              </div>
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex min-w-0 items-center gap-3">
                  <TeamFlag team={data.homeTeam} size={36} />
                  <div>
                    <div className="font-semibold text-white">{data.homeTeam}</div>
                    <div className="text-xs text-slate-500">mandante</div>
                  </div>
                </div>
                <div className="font-mono text-3xl font-black text-white">
                  {data.currentScore ?? "0x0"}
                </div>
                <div className="flex min-w-0 items-center gap-3">
                  <div className="text-right">
                    <div className="font-semibold text-white">{data.awayTeam}</div>
                    <div className="text-xs text-slate-500">visitante</div>
                  </div>
                  <TeamFlag team={data.awayTeam} size={36} />
                </div>
              </div>
            </section>

            <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-xl border border-white/8 bg-black/25 p-4">
                <div className="text-[11px] text-slate-500">P(casa)</div>
                <div className="text-2xl font-bold text-blue-300">
                  {formatPct(summary?.probHomeWin)}
                </div>
                <div className="text-[11px] text-slate-500">
                  proj. {formatNum(summary?.expectedFinalHome)}
                </div>
              </div>
              <div className="rounded-xl border border-white/8 bg-black/25 p-4">
                <div className="text-[11px] text-slate-500">P(fora)</div>
                <div className="text-2xl font-bold text-orange-300">
                  {formatPct(summary?.probAwayWin)}
                </div>
                <div className="text-[11px] text-slate-500">
                  proj. {formatNum(summary?.expectedFinalAway)}
                </div>
              </div>
              <div className="rounded-xl border border-white/8 bg-black/25 p-4">
                <div className="text-[11px] text-slate-500">Total esperado</div>
                <div className="text-2xl font-bold text-white">
                  {formatNum(summary?.expectedTotal)}
                </div>
                <div className="text-[11px] text-slate-500">
                  restante {formatNum(summary?.remainingInnings)} ent.
                  {summary?.marketTotalLine != null
                    ? ` · linha ${formatNum(summary.marketTotalLine)}`
                    : ""}
                </div>
              </div>
              <div className="rounded-xl border border-white/8 bg-black/25 p-4">
                <div className="text-[11px] text-slate-500">Ritmo (R/ent)</div>
                <div className="text-sm text-slate-200">
                  {formatNum(summary?.rpiHome, 2)} × {formatNum(summary?.rpiAway, 2)}
                </div>
                <div className="text-[11px] text-slate-500">
                  conf. {data.confidence?.label ?? "—"} · sim {summary?.nSimulations ?? "—"}
                </div>
              </div>
            </section>

            {data.baseballInnings.length > 0 ? (
              <section className="overflow-x-auto rounded-xl border border-white/8 bg-black/20 p-3">
                <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Por entrada
                </div>
                <table className="min-w-full text-center text-sm">
                  <thead>
                    <tr className="text-slate-500">
                      <th className="px-2 py-1 text-left">Time</th>
                      {data.baseballInnings.map((inn) => (
                        <th key={inn.num} className="px-2 py-1">
                          {inn.num}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className="px-2 py-1 text-left text-slate-300">{data.homeTeam}</td>
                      {data.baseballInnings.map((inn) => (
                        <td key={`h-${inn.num}`} className="px-2 py-1 font-mono text-white">
                          {inn.home}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-2 py-1 text-left text-slate-300">{data.awayTeam}</td>
                      {data.baseballInnings.map((inn) => (
                        <td key={`a-${inn.num}`} className="px-2 py-1 font-mono text-white">
                          {inn.away}
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </section>
            ) : null}

            <section className="rounded-xl border border-white/8 bg-black/25 p-4">
              <div className="mb-3 text-sm font-semibold text-white">Aportes sugeridos</div>
              {topAportes.length === 0 ? (
                <p className="text-sm text-slate-500">
                  Nenhum edge acima do mínimo no momento (moneyline / run line / total).
                </p>
              ) : (
                <ul className="space-y-2">
                  {topAportes.map((a) => (
                    <li
                      key={`${a.market}-${a.outcome}-${a.label}`}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2"
                    >
                      <div>
                        <div className="text-sm font-medium text-white">{a.label}</div>
                        <div className="text-[11px] text-slate-500">
                          {a.market} · odd {a.marketOdd.toFixed(2)} · modelo{" "}
                          {formatPct(a.modelProb)}
                        </div>
                      </div>
                      <div className="text-right text-sm">
                        <div className="font-mono text-emerald-300">
                          EV {(a.expectedValue * 100).toFixed(1)}%
                        </div>
                        {a.suggestedStakeValue != null ? (
                          <div className="text-[11px] text-slate-400">
                            R$ {a.suggestedStakeValue.toFixed(2)}
                          </div>
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </div>
    </PageTransition>
  );
}
