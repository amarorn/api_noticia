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
        title={`${round.competition}`}
        subtitle={`Rodada ${round.round} · Temporada ${round.season} · Fase ${round.phase}`}
        badges={[
          { label: `${round.predictions.length} jogos`, color: "blue" },
        ]}
      />

      <section>
        <p className="section-label">Palpites da rodada</p>
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

interface PageHeaderBadge {
  label: string;
  color?: "green" | "blue" | "purple" | "orange";
}

interface PageHeaderProps {
  title: string;
  subtitle: string;
  badges?: PageHeaderBadge[];
}

const badgeClasses: Record<NonNullable<PageHeaderBadge["color"]>, string> = {
  green: "border-neon-green/25 bg-neon-green/8 text-neon-green",
  blue: "border-neon-blue/25 bg-neon-blue/8 text-neon-blue",
  purple: "border-neon-purple/25 bg-neon-purple/8 text-neon-purple",
  orange: "border-neon-orange/25 bg-neon-orange/8 text-neon-orange",
};

function PageHeader({ title, subtitle, badges }: PageHeaderProps) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/[0.06]" style={{ minHeight: 160 }}>
      {/* Imagem hero gerada pelo modelo */}
      <img
        src="/images/hero-pitch.png"
        alt=""
        aria-hidden="true"
        className="absolute inset-0 h-full w-full object-cover object-center opacity-30"
        draggable={false}
      />
      {/* Overlay gradiente para manter legibilidade do texto */}
      <div className="absolute inset-0 bg-gradient-to-r from-surface/95 via-surface/80 to-surface/40" />
      <div className="relative p-6 sm:p-8">
        <h1 className="text-2xl font-extrabold gradient-text sm:text-3xl">{title}</h1>
        <p className="mt-1.5 text-sm text-slate-400">{subtitle}</p>
        {badges && badges.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {badges.map((b) => (
              <span
                key={b.label}
                className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${badgeClasses[b.color ?? "blue"]}`}
              >
                {b.label}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export { PageHeader };
