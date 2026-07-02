import { useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  getSuperbetLiveUseCase,
  getWcComboTicketUseCase,
} from "@/application/container";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { HeroPageHeader } from "@/presentation/components/layout/PageHeader";
import { ComboTicketPanel } from "@/presentation/components/predictions/ComboTicketPanel";
import { LiveBestCombosPanel } from "@/presentation/components/predictions/LiveBestCombosPanel";
import { LiveLongshotCombosPanel } from "@/presentation/components/predictions/LiveLongshotCombosPanel";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";
import { IconChevronRight, IconWallet } from "@/presentation/components/ui/Icons";
import { useLiveAdviceQueries } from "@/presentation/hooks/useLiveAdviceQueries";
import {
  findSuperbetEventForMatch,
  buildMatchTicketsPath,
} from "@/presentation/utils/matchSuperbetEvent";
import {
  LONGSHOT_MIN_RETURN_BRL,
  LONGSHOT_STAKE_BRL,
} from "@/presentation/utils/longshotCombos";

const TICKET_BANKROLL = 500;

export function MatchTicketsPage() {
  const { home = "", away = "" } = useParams();
  const [searchParams] = useSearchParams();
  const homeTeam = decodeURIComponent(home);
  const awayTeam = decodeURIComponent(away);
  const eventIdFromUrl = Number.parseInt(searchParams.get("superbetEventId") ?? "", 10);
  const superbetEventIdFromUrl =
    Number.isFinite(eventIdFromUrl) && eventIdFromUrl > 0 ? eventIdFromUrl : undefined;

  const liveListQuery = useQuery({
    queryKey: ["superbet-live-list"],
    queryFn: () => getSuperbetLiveUseCase.execute(),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });

  const matchedEvent = useMemo(
    () => findSuperbetEventForMatch(liveListQuery.data?.events, homeTeam, awayTeam),
    [liveListQuery.data?.events, homeTeam, awayTeam],
  );

  const resolvedEventId = matchedEvent?.eventId ?? superbetEventIdFromUrl;

  const liveAdvice = useLiveAdviceQueries(resolvedEventId ?? 0, TICKET_BANKROLL);

  const comboQuery = useQuery({
    queryKey: ["wc-combo-ticket", homeTeam, awayTeam, resolvedEventId],
    queryFn: () =>
      getWcComboTicketUseCase.execute({
        homeTeam,
        awayTeam,
        bankroll: TICKET_BANKROLL,
        superbetEventId: resolvedEventId,
      }),
    enabled: Boolean(homeTeam && awayTeam),
    staleTime: 5 * 60_000,
  });

  if (!homeTeam || !awayTeam) {
    return (
      <PageTransition>
        <ErrorState title="Jogo inválido" message="Selecione um confronto no dashboard." />
        <Link to="/" className="btn-primary mt-4 inline-flex">
          Voltar ao dashboard
        </Link>
      </PageTransition>
    );
  }

  const isLive = Boolean(matchedEvent && liveAdvice.data && !liveAdvice.data.isFinished);
  const comboOdd = comboQuery.data?.comboOdd ?? null;
  const longshotReturn =
    comboOdd != null ? Math.round(LONGSHOT_STAKE_BRL * comboOdd * 100) / 100 : null;

  return (
    <PageTransition>
      <HeroPageHeader
        title={`${homeTeam} × ${awayTeam}`}
        subtitle="Monte bilhetes com R$ 5 e alvo de retorno alto (longshot @100+)"
        badges={[
          {
            label: isLive ? "Ao vivo · odds Superbet" : "Pré-jogo · padrões KXL",
            color: isLive ? "green" : "blue",
          },
        ]}
      />

      <section className="glass-card overflow-hidden p-0">
        <div className="border-b border-white/8 bg-gradient-to-br from-violet-500/15 via-transparent to-emerald-500/10 px-5 py-6">
          <div className="flex flex-wrap items-center gap-4">
            <TeamFlag team={homeTeam} size={48} />
            <div className="min-w-0 flex-1 text-center sm:text-left">
              <p className="text-[10px] font-bold uppercase tracking-widest text-violet-300">
                Bilhete longshot
              </p>
              <p className="mt-1 font-mono text-3xl font-black text-white">
                R$ {LONGSHOT_STAKE_BRL.toFixed(2)}
                <span className="mx-2 text-slate-500">→</span>
                <span className="text-neon-green">R$ {LONGSHOT_MIN_RETURN_BRL}+</span>
              </p>
              <p className="mt-2 max-w-xl text-xs leading-relaxed text-slate-400">
                Combinações com odd combinada ≥{" "}
                {(LONGSHOT_MIN_RETURN_BRL / LONGSHOT_STAKE_BRL).toFixed(0)}×. Ordenadas pela
                probabilidade do modelo — verde = menor risco entre as opções.
              </p>
            </div>
            <TeamFlag team={awayTeam} size={48} />
          </div>
        </div>

        <div className="flex flex-wrap gap-3 px-5 py-4">
          <Link to="/" className="btn-ghost text-xs">
            ← Dashboard
          </Link>
          {resolvedEventId && (
            <Link
              to={`/ao-vivo/${resolvedEventId}`}
              className="inline-flex items-center gap-1 rounded-lg border border-neon-green/30 bg-neon-green/10 px-3 py-1.5 text-xs font-medium text-neon-green"
            >
              Abrir ao vivo
              <IconChevronRight className="h-3 w-3" />
            </Link>
          )}
        </div>
      </section>

      {liveListQuery.isLoading && <DashboardSkeleton />}

      {isLive && liveAdvice.data && (
        <>
          <LiveBestCombosPanel data={liveAdvice.data} />
          <LiveLongshotCombosPanel data={liveAdvice.data} />
        </>
      )}

      {!isLive && !liveListQuery.isLoading && (
        <section className="rounded-2xl border border-amber-500/25 bg-amber-500/[0.06] px-5 py-4 text-sm text-amber-100/90">
          <p className="font-semibold text-amber-200">Longshots ao vivo indisponíveis</p>
          <p className="mt-1 text-xs leading-relaxed text-amber-100/75">
            As combinações R$ {LONGSHOT_STAKE_BRL} → R$ {LONGSHOT_MIN_RETURN_BRL}+ usam odds
            reais da Superbet. Quando o jogo entrar ao vivo, volte aqui ou abra{" "}
            <Link to="/ao-vivo" className="underline">
              Ao vivo
            </Link>
            .
          </p>
        </section>
      )}

      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <IconWallet className="h-4 w-4 text-neon-blue" />
          <h2 className="text-sm font-semibold text-white">Combo KXL · estudo pré-jogo</h2>
        </div>

        {comboQuery.isLoading && (
          <div className="space-y-3 py-4">
            <div className="h-24 animate-pulse rounded-xl bg-white/5" />
            <p className="text-center text-xs text-slate-500">Montando bilhete com padrões KXL…</p>
          </div>
        )}

        {comboQuery.isError && (
          <ErrorState
            title="Falha ao montar bilhete"
            message={
              comboQuery.error instanceof Error
                ? comboQuery.error.message
                : "Verifique se a API está rodando."
            }
            onRetry={() => comboQuery.refetch()}
          />
        )}

        {comboQuery.isSuccess && (
          <>
            {longshotReturn != null && longshotReturn >= LONGSHOT_MIN_RETURN_BRL && (
              <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/[0.08] px-4 py-3 text-sm">
                <p className="font-medium text-emerald-200">
                  Combo KXL @ {comboOdd!.toFixed(2)} — R$ {LONGSHOT_STAKE_BRL.toFixed(2)} retorna
                  R$ {longshotReturn.toFixed(2)}
                </p>
                <p className="mt-1 text-xs text-emerald-100/70">
                  Use o combo abaixo no Criar Aposta da Superbet (requer extensão instalada).
                </p>
              </div>
            )}
            <ComboTicketPanel
              homeTeam={homeTeam}
              awayTeam={awayTeam}
              ticket={comboQuery.data}
              superbetEventId={resolvedEventId ?? null}
            />
          </>
        )}
      </section>
    </PageTransition>
  );
}

export { buildMatchTicketsPath };
