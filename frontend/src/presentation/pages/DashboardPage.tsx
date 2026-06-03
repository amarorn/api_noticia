import { useQuery } from "@tanstack/react-query";
import {
  getValueBetsUseCase,
  getWcRoundUseCase,
} from "@/application/container";
import { ApiError } from "@/infrastructure/api/client";
import { PageTransition, StaggerContainer, StaggerItem } from "@/presentation/components/layout/PageTransition";
import { MatchCard } from "@/presentation/components/predictions/MatchCard";
import { ValueBetsSection } from "@/presentation/components/predictions/ValueBetCard";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { ErrorState } from "@/presentation/components/ui/ErrorState";

export function DashboardPage() {
  const roundQuery = useQuery({
    queryKey: ["wc-round"],
    queryFn: () => getWcRoundUseCase.execute(),
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
  });

  const valueQuery = useQuery({
    queryKey: ["wc-value"],
    queryFn: () => getValueBetsUseCase.execute(),
    retry: false,
  });

  const valueError =
    valueQuery.error instanceof ApiError
      ? valueQuery.error.message
      : valueQuery.error
        ? "Erro ao carregar value bets"
        : null;

  if (roundQuery.isLoading) {
    return (
      <PageTransition>
        <PageHeader
          title="Copa do Mundo 2026"
          subtitle="Carregando palpites… Se a API acabou de subir, o treino dos modelos pode levar até 1 minuto."
        />
        <DashboardSkeleton />
      </PageTransition>
    );
  }

  if (roundQuery.isError) {
    return (
      <PageTransition>
        <ErrorState
          message={
            roundQuery.error instanceof Error
              ? roundQuery.error.message
              : "Falha ao carregar rodada"
          }
          onRetry={() => roundQuery.refetch()}
        />
      </PageTransition>
    );
  }

  const round = roundQuery.data!;

  return (
    <PageTransition className="space-y-10">
      <PageHeader
        title={`${round.competition} — Rodada ${round.round}`}
        subtitle={`Temporada ${round.season} • Fase: ${round.phase} • ${round.predictions.length} jogos`}
      />

      <section>
        <h2 className="mb-4 text-lg font-semibold text-white">Palpites da rodada</h2>
        <StaggerContainer className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {round.predictions.map((pred, i) => (
            <StaggerItem key={`${pred.homeTeam}-${pred.awayTeam}`}>
              <MatchCard prediction={pred} index={i} />
            </StaggerItem>
          ))}
        </StaggerContainer>
      </section>

      <ValueBetsSection
        edges={valueQuery.data?.edges ?? []}
        matchedGames={valueQuery.data?.matchedGames ?? 0}
        totalGames={valueQuery.data?.totalScheduleGames ?? round.predictions.length}
        loading={valueQuery.isLoading}
        error={valueError}
      />
    </PageTransition>
  );
}

function PageHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div>
      <h1 className="text-3xl font-bold gradient-text sm:text-4xl">{title}</h1>
      <p className="mt-2 text-slate-400">{subtitle}</p>
    </div>
  );
}

export { PageHeader };
