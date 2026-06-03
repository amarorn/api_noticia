import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getValueBetsUseCase,
  getWcRoundUseCase,
  getWcScheduleUseCase,
} from "@/application/container";
import { ApiError } from "@/infrastructure/api/client";
import { PageTransition, StaggerContainer, StaggerItem } from "@/presentation/components/layout/PageTransition";
import { MatchCard } from "@/presentation/components/predictions/MatchCard";
import { ValueBetsSection } from "@/presentation/components/predictions/ValueBetCard";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { ErrorState } from "@/presentation/components/ui/ErrorState";
import {
  buildMatchGroupLookup,
  groupForMatch,
  sortedGroupIds,
} from "@/presentation/utils/officialSchedule";

export function DashboardPage() {
  const [selectedGroup, setSelectedGroup] = useState<string | "all">("all");

  const roundQuery = useQuery({
    queryKey: ["wc-round"],
    queryFn: () => getWcRoundUseCase.execute(),
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
  });

  const scheduleQuery = useQuery({
    queryKey: ["wc-schedule"],
    queryFn: () => getWcScheduleUseCase.execute(),
    staleTime: 10 * 60_000,
  });

  const groupLookup = useMemo(
    () => (scheduleQuery.data ? buildMatchGroupLookup(scheduleQuery.data) : new Map()),
    [scheduleQuery.data],
  );

  const groupIds = useMemo(
    () => (scheduleQuery.data ? sortedGroupIds(scheduleQuery.data) : []),
    [scheduleQuery.data],
  );

  const filteredPredictions = useMemo(() => {
    const predictions = roundQuery.data?.predictions ?? [];
    if (selectedGroup === "all") return predictions;
    return predictions.filter(
      (pred) => groupForMatch(pred.homeTeam, pred.awayTeam, groupLookup) === selectedGroup,
    );
  }, [roundQuery.data, selectedGroup, groupLookup]);

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
  const gamesLabel =
    selectedGroup === "all"
      ? `${filteredPredictions.length} jogos`
      : `Grupo ${selectedGroup} · ${filteredPredictions.length} jogos`;

  return (
    <PageTransition className="space-y-10">
      <PageHeader
        title={`${round.competition}`}
        subtitle={`Rodada ${round.round} · Temporada ${round.season} · Fase ${round.phase}`}
        badges={[{ label: gamesLabel, color: "blue" }]}
      />

      {groupIds.length > 0 && (
        <section className="space-y-3">
          <p className="section-label">Filtrar por grupo</p>
          <div className="flex flex-wrap gap-2">
            <GroupFilterChip
              label="Todos"
              active={selectedGroup === "all"}
              onClick={() => setSelectedGroup("all")}
            />
            {groupIds.map((gid) => (
              <GroupFilterChip
                key={gid}
                label={gid}
                active={selectedGroup === gid}
                onClick={() => setSelectedGroup(gid)}
              />
            ))}
          </div>
        </section>
      )}

      <section>
        <p className="section-label">Palpites da rodada</p>
        {filteredPredictions.length === 0 ? (
          <div className="glass-card flex flex-col items-center justify-center gap-2 py-16 text-center">
            <p className="text-sm text-slate-400">Nenhum jogo neste grupo.</p>
          </div>
        ) : (
          <StaggerContainer className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filteredPredictions.map((pred, i) => (
              <StaggerItem key={`${pred.homeTeam}-${pred.awayTeam}`}>
                <MatchCard
                  prediction={pred}
                  index={i}
                  group={groupForMatch(pred.homeTeam, pred.awayTeam, groupLookup)}
                />
              </StaggerItem>
            ))}
          </StaggerContainer>
        )}
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

function GroupFilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex h-9 min-w-9 items-center justify-center rounded-full px-3 text-xs font-bold transition-all ${
        active
          ? "bg-neon-green/15 text-neon-green ring-1 ring-neon-green/30"
          : "bg-white/5 text-slate-400 hover:bg-white/8 hover:text-slate-300"
      }`}
    >
      {label}
    </button>
  );
}
