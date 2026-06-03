import { useQuery } from "@tanstack/react-query";
import { getBrasileiraoRoundUseCase } from "@/application/container";
import { PageTransition, StaggerContainer, StaggerItem } from "@/presentation/components/layout/PageTransition";
import { BrasileiraoCard } from "@/presentation/components/predictions/MatchCard";
import { PageHeader } from "@/presentation/pages/DashboardPage";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { ErrorState } from "@/presentation/components/ui/ErrorState";

export function BrasileiraoPage() {
  const query = useQuery({
    queryKey: ["brasileirao-round"],
    queryFn: () => getBrasileiraoRoundUseCase.execute(),
  });

  if (query.isLoading) {
    return (
      <PageTransition>
        <PageHeader title="Brasileirão" subtitle="Carregando palpites..." />
        <DashboardSkeleton />
      </PageTransition>
    );
  }

  if (query.isError) {
    return (
      <PageTransition>
        <ErrorState
          message={
            query.error instanceof Error
              ? query.error.message
              : "Falha ao carregar rodada"
          }
          onRetry={() => query.refetch()}
        />
      </PageTransition>
    );
  }

  const round = query.data!;

  return (
    <PageTransition className="space-y-8">
      <PageHeader
        title={`${round.competition} — Rodada ${round.roundNumber}`}
        subtitle="Previsões heurísticas baseadas em notícias e contexto dos times"
      />

      <StaggerContainer className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {round.predictions.map((p, i) => (
          <StaggerItem key={`${p.homeTeam}-${p.awayTeam}`}>
            <BrasileiraoCard
              homeTeam={p.homeTeam}
              awayTeam={p.awayTeam}
              prediction={p.prediction}
              confidence={p.confidence}
              reason={p.reason}
              newsCount={p.newsCount}
              index={i}
            />
          </StaggerItem>
        ))}
      </StaggerContainer>
    </PageTransition>
  );
}
