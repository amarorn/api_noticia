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
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { SlowLoadingPanel } from "@/presentation/components/ui/SlowLoadingPanel";
import { EmptyState, ErrorState } from "@/presentation/components/ui/ErrorState";
import {
  buildMatchGroupLookup,
  buildMatchRoundLookup,
  groupForMatch,
  roundForMatchPair,
  sortedGroupIds,
} from "@/presentation/utils/officialSchedule";

export function DashboardPage() {
  const [selectedGroup, setSelectedGroup] = useState<string | "all">("all");
  const [selectedRound, setSelectedRound] = useState<number | "all">("all");

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

  const allPredictions = useMemo(() => {
    const merged: WcPrediction[] = [];
    for (const query of [round1Query, round2Query, round3Query]) {
      if (query.data?.predictions) {
        merged.push(...query.data.predictions);
      }
    }
    return merged;
  }, [round1Query.data, round2Query.data, round3Query.data]);

  const roundMeta = round1Query.data ?? round2Query.data ?? round3Query.data;

  const groupLookup = useMemo(
    () => (scheduleQuery.data ? buildMatchGroupLookup(scheduleQuery.data) : new Map()),
    [scheduleQuery.data],
  );

  const roundLookup = useMemo(
    () => (scheduleQuery.data ? buildMatchRoundLookup(scheduleQuery.data) : new Map()),
    [scheduleQuery.data],
  );

  const groupIds = useMemo(
    () => (scheduleQuery.data ? sortedGroupIds(scheduleQuery.data) : []),
    [scheduleQuery.data],
  );

  const matchdays = scheduleQuery.data?.matchdays ?? [];

  const filteredPredictions = useMemo(() => {
    return allPredictions.filter((pred) => {
      const group = groupForMatch(pred.homeTeam, pred.awayTeam, groupLookup);
      const round = roundForMatchPair(pred.homeTeam, pred.awayTeam, roundLookup);
      if (selectedGroup !== "all" && group !== selectedGroup) return false;
      if (selectedRound !== "all" && round !== selectedRound) return false;
      return true;
    });
  }, [allPredictions, selectedGroup, selectedRound, groupLookup, roundLookup]);

  const roundCounts = useMemo(() => {
    const counts = new Map<number, number>();
    for (const pred of allPredictions) {
      const r = roundForMatchPair(pred.homeTeam, pred.awayTeam, roundLookup);
      if (r != null) counts.set(r, (counts.get(r) ?? 0) + 1);
    }
    return counts;
  }, [allPredictions, roundLookup]);

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

  const hasFilters = selectedGroup !== "all" || selectedRound !== "all";
  const loadingMoreRounds =
    round1Query.isSuccess &&
    (round2Query.isFetching || round3Query.isFetching) &&
    allPredictions.length < 72;

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

  const gamesLabel = buildGamesLabel(filteredPredictions.length, selectedGroup, selectedRound);

  return (
    <PageTransition className="space-y-8">
      <HeroPageHeader
        title={roundMeta?.competition ?? "Copa do Mundo 2026"}
        subtitle={`Fase de grupos · Temporada ${roundMeta?.season ?? 2026} · ${allPredictions.length}/72 jogos carregados`}
        badges={[{ label: gamesLabel, color: "blue" }]}
      />

      {loadingMoreRounds && (
        <SlowLoadingPanel
          active
          title="Carregando rodadas 2 e 3…"
          hint="Os palpites já visíveis da rodada 1 continuam disponíveis enquanto o restante é calculado."
        />
      )}

      <QuickActions />

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

      {matchdays.length > 0 && (
        <FilterBar label="Filtrar por rodada">
          <FilterChip
            label="Todas"
            active={selectedRound === "all"}
            onClick={() => setSelectedRound("all")}
          />
          {matchdays.map((rd) => (
            <FilterChip
              key={rd}
              label={`Rodada ${rd}`}
              active={selectedRound === rd}
              onClick={() => setSelectedRound(rd)}
              count={roundCounts.get(rd)}
            />
          ))}
        </FilterBar>
      )}

      <section>
        <p className="section-label">Palpites</p>
        {filteredPredictions.length === 0 ? (
          <EmptyState
            title="Nenhum jogo neste filtro"
            description={
              loadingMoreRounds
                ? "Aguarde o carregamento das demais rodadas ou limpe os filtros."
                : "Tente outro grupo ou rodada, ou volte para ver todos os 72 jogos."
            }
            action={
              hasFilters ? (
                <button
                  type="button"
                  className="btn-ghost mt-2"
                  onClick={() => {
                    setSelectedGroup("all");
                    setSelectedRound("all");
                  }}
                >
                  Limpar filtros
                </button>
              ) : undefined
            }
          />
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
        totalGames={valueQuery.data?.totalScheduleGames ?? 72}
        loading={valueQuery.isLoading}
        error={valueError}
      />
    </PageTransition>
  );
}

function buildGamesLabel(
  count: number,
  group: string | "all",
  round: number | "all",
): string {
  const parts: string[] = [`${count} jogos`];
  if (group !== "all") parts.push(`Gr. ${group}`);
  if (round !== "all") parts.push(`R${round}`);
  return parts.join(" · ");
}
