import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getValueBetsUseCase,
  getWcRoundUseCase,
  getWcScheduleUseCase,
} from "@/application/container";
import type { WcPrediction } from "@/domain/entities";
import { ApiError } from "@/infrastructure/api/client";
import { PageTransition, StaggerContainer, StaggerItem } from "@/presentation/components/layout/PageTransition";
import { HeroPageHeader } from "@/presentation/components/layout/PageHeader";
import { QuickActions } from "@/presentation/components/layout/QuickActions";
import { MatchCard } from "@/presentation/components/predictions/MatchCard";
import { ValueBetsSection } from "@/presentation/components/predictions/ValueBetCard";
import { FilterBar, FilterChip } from "@/presentation/components/ui/FilterBar";
import { RoundTabs } from "@/presentation/components/ui/RoundTabs";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { SlowLoadingPanel } from "@/presentation/components/ui/SlowLoadingPanel";
import { EmptyState, ErrorState } from "@/presentation/components/ui/EmptyState";
import { IconCalendar, IconFilter } from "@/presentation/components/ui/Icons";
import {
  buildMatchGroupLookup,
  groupForMatch,
  sortedGroupIds,
} from "@/presentation/utils/officialSchedule";

export function DashboardPage() {
  const [selectedGroup, setSelectedGroup] = useState<string | "all">("all");
  const [activeRound, setActiveRound] = useState<number | "all">(1);

  const round1Query = useQuery({
    queryKey: ["wc-round", 1],
    queryFn: () => getWcRoundUseCase.execute(1),
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
  });

  const round2Query = useQuery({
    queryKey: ["wc-round", 2],
    queryFn: () => getWcRoundUseCase.execute(2),
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
    enabled: round1Query.isSuccess,
  });

  const round3Query = useQuery({
    queryKey: ["wc-round", 3],
    queryFn: () => getWcRoundUseCase.execute(3),
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
    enabled: round1Query.isSuccess,
  });

  const scheduleQuery = useQuery({
    queryKey: ["wc-schedule"],
    queryFn: () => getWcScheduleUseCase.execute(),
    staleTime: 10 * 60_000,
  });

  const roundQueries: Record<number, typeof round1Query> = {
    1: round1Query,
    2: round2Query,
    3: round3Query,
  };

  const allPredictions = useMemo(() => {
    const merged: WcPrediction[] = [];
    for (const query of [round1Query, round2Query, round3Query]) {
      if (query.data?.predictions) {
        merged.push(...query.data.predictions);
      }
    }
    return merged;
  }, [round1Query.data, round2Query.data, round3Query.data]);

  const currentPredictions = useMemo(() => {
    if (activeRound === "all") return allPredictions;
    const q = roundQueries[activeRound as number];
    return q.data?.predictions ?? [];
  }, [activeRound, allPredictions, round1Query.data, round2Query.data, round3Query.data]);

  const roundMeta = round1Query.data ?? round2Query.data ?? round3Query.data;

  const groupLookup = useMemo(
    () => (scheduleQuery.data ? buildMatchGroupLookup(scheduleQuery.data) : new Map()),
    [scheduleQuery.data],
  );

  const groupIds = useMemo(
    () => (scheduleQuery.data ? sortedGroupIds(scheduleQuery.data) : []),
    [scheduleQuery.data],
  );

  const filteredPredictions = useMemo(() => {
    if (selectedGroup === "all") return currentPredictions;
    return currentPredictions.filter((pred) => {
      const group = groupForMatch(pred.homeTeam, pred.awayTeam, groupLookup);
      return group === selectedGroup;
    });
  }, [currentPredictions, selectedGroup, groupLookup]);

  const roundCounts = useMemo(() => {
    const counts = new Map<number, number>();
    for (let r = 1; r <= 3; r++) {
      const q = roundQueries[r as 1 | 2 | 3];
      counts.set(r, q.data?.predictions?.length ?? 0);
    }
    return counts;
  }, [round1Query.data, round2Query.data, round3Query.data]);

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

  const isLoadingCurrent = activeRound === "all"
    ? round1Query.isLoading
    : roundQueries[activeRound as number].isLoading;

  const isFetchingCurrent = activeRound === "all"
    ? (round1Query.isFetching || round2Query.isFetching || round3Query.isFetching)
    : roundQueries[activeRound as number].isFetching;

  if (round1Query.isLoading) {
    return (
      <PageTransition>
        <HeroPageHeader
          title="Copa do Mundo 2026"
          subtitle="Palpites da fase de grupos · 72 jogos oficiais"
        />
        <SlowLoadingPanel
          active
          title="Gerando palpites da rodada 1…"
          hint="Carregamos a rodada 1 primeiro (~24 jogos). Rodadas 2 e 3 entram em seguida."
        />
        <DashboardSkeleton />
      </PageTransition>
    );
  }

  if (round1Query.isError) {
    return (
      <PageTransition>
        <ErrorState
          title="Não foi possível carregar os palpites"
          message={
            round1Query.error instanceof Error
              ? round1Query.error.message
              : "Verifique se a API está rodando (./scripts/dev-api-stable.sh)"
          }
          onRetry={() => round1Query.refetch()}
        />
      </PageTransition>
    );
  }

  const gamesLabel = `${filteredPredictions.length} ${filteredPredictions.length === 1 ? "jogo" : "jogos"}`;

  const tabs = [
    { value: 1 as const, label: "Rodada 1", count: roundCounts.get(1) },
    { value: 2 as const, label: "Rodada 2", count: roundCounts.get(2) },
    { value: 3 as const, label: "Rodada 3", count: roundCounts.get(3) },
    { value: "all" as const, label: "Todas", count: allPredictions.length },
  ];

  return (
    <PageTransition className="space-y-8">
      <HeroPageHeader
        title={roundMeta?.competition ?? "Copa do Mundo 2026"}
        subtitle={`Fase de grupos · Temporada ${roundMeta?.season ?? 2026} · ${allPredictions.length}/72 jogos carregados`}
        badges={[{ label: gamesLabel, color: "blue" }]}
      />

      <QuickActions />

      <section className="space-y-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="section-label m-0">Rodada</p>
        </div>
        <RoundTabs tabs={tabs} active={activeRound} onChange={setActiveRound} />
      </section>

      {groupIds.length > 0 && (
        <FilterBar label="Filtrar por grupo">
          <FilterChip
            label="Todos"
            active={selectedGroup === "all"}
            onClick={() => setSelectedGroup("all")}
          />
          {groupIds.map((gid) => (
            <FilterChip
              key={gid}
              label={`Gr. ${gid}`}
              active={selectedGroup === gid}
              onClick={() => setSelectedGroup(gid)}
            />
          ))}
        </FilterBar>
      )}

      {isFetchingCurrent && !isLoadingCurrent && (
        <SlowLoadingPanel
          active
          title={`Carregando rodada ${activeRound}…`}
          hint="Os palpites já visíveis continuam disponíveis."
        />
      )}

      <section>
        <p className="section-label">Palpites</p>
        {filteredPredictions.length === 0 ? (
          <EmptyState
            title="Nenhum jogo neste filtro"
            description={
              isFetchingCurrent
                ? "Aguarde o carregamento da rodada ou limpe os filtros."
                : "Tente outro grupo ou rodada."
            }
            icon={isFetchingCurrent ? IconCalendar : IconFilter}
            iconColor={isFetchingCurrent ? "#00d4ff" : "#a855f7"}
            action={
              selectedGroup !== "all" ? (
                <button
                  type="button"
                  className="btn-ghost mt-2"
                  onClick={() => setSelectedGroup("all")}
                >
                  Limpar filtros
                </button>
              ) : undefined
            }
          />
        ) : (
          <StaggerContainer className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filteredPredictions.map((pred: WcPrediction, i: number) => (
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
        totalGames={valueQuery.data?.totalScheduleGames ?? 72}
        loading={valueQuery.isLoading}
        error={valueError}
      />
    </PageTransition>
  );
}
