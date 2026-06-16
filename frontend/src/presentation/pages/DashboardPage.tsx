import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
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
import { IconChevronRight, IconCalendar, IconFilter, IconWallet } from "@/presentation/components/ui/Icons";
import {
  buildMatchGroupLookup,
  groupForMatch,
  sortedGroupIds,
} from "@/presentation/utils/officialSchedule";
import { buildMatchTicketsPath } from "@/presentation/utils/matchSuperbetEvent";

export function DashboardPage() {
  const [selectedGroup, setSelectedGroup] = useState<string | "all">("all");
  const [activeRound, setActiveRound] = useState<number | "all">(1);
  const [selectedMatch, setSelectedMatch] = useState<{
    homeTeam: string;
    awayTeam: string;
  } | null>(null);

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

  const finishedStats = useMemo(() => {
    const finished = allPredictions.filter((p) => p.actualScore);
    const hits = finished.filter((p) => p.predictionHit === true).length;
    return { total: finished.length, hits };
  }, [allPredictions]);

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
    <PageTransition className="space-y-4">
      <HeroPageHeader
        title={roundMeta?.competition ?? "Copa do Mundo 2026"}
        subtitle={`Fase de grupos · Temporada ${roundMeta?.season ?? 2026} · ${allPredictions.length}/72 jogos`}
        badges={[{ label: gamesLabel, color: "blue" }]}
      />

      <QuickActions />

      <section className="info-panel glow-border relative space-y-2 p-3">
        <p className="font-semibold text-white text-xs flex items-center gap-2">
          <span className="inline-flex h-4 w-4 items-center justify-center rounded bg-neon-green/10 text-neon-green text-[10px]">?</span>
          Como ler estes palpites
        </p>
        <ul className="list-disc space-y-1 pl-4 text-[11px] leading-relaxed text-slate-400">
          <li><strong className="text-slate-300">Prob. palpite</strong> é a chance estimada do resultado (1/X/2).</li>
          <li>Jogos com <strong className="text-amber-300">incerteza alta</strong> são equilibrados — evite apostas grandes.</li>
          <li>Palpite <strong className="text-sky-300">X</strong> pode aparecer quando probabilidades estão próximas.</li>
          {finishedStats.total > 0 && (
            <li>
              Acertos: <strong className="text-neon-green">{finishedStats.hits}/{finishedStats.total}</strong>
              {" "}({((finishedStats.hits / finishedStats.total) * 100).toFixed(0)}%).
            </li>
          )}
        </ul>
      </section>

      <section className="space-y-2">
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
          <StaggerContainer className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {filteredPredictions.map((pred: WcPrediction, i: number) => {
              const matchKey = `${pred.homeTeam}::${pred.awayTeam}`;
              const isSelected =
                selectedMatch?.homeTeam === pred.homeTeam &&
                selectedMatch?.awayTeam === pred.awayTeam;
              return (
                <StaggerItem key={matchKey}>
                  <MatchCard
                    prediction={pred}
                    index={i}
                    group={groupForMatch(pred.homeTeam, pred.awayTeam, groupLookup)}
                    selected={isSelected}
                    onSelect={() =>
                      setSelectedMatch((current) =>
                        current?.homeTeam === pred.homeTeam &&
                        current?.awayTeam === pred.awayTeam
                          ? null
                          : { homeTeam: pred.homeTeam, awayTeam: pred.awayTeam },
                      )
                    }
                  />
                </StaggerItem>
              );
            })}
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

      {selectedMatch && (
        <motion.div
          initial={{ opacity: 0, y: 16, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 8, scale: 0.98 }}
          transition={{ type: "spring", stiffness: 380, damping: 28 }}
          className="fixed bottom-3 left-1/2 z-50 flex w-[calc(100%-2rem)] max-w-md -translate-x-1/2 items-center gap-2.5 rounded-xl border border-neon-purple/25 bg-surface-100/95 px-3 py-2 shadow-lg backdrop-blur-xl"
        >
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-white">
              {selectedMatch.homeTeam} × {selectedMatch.awayTeam}
            </p>
            <p className="text-[10px] text-slate-400">Bilhetes longshot R$ 5 → R$ 500+</p>
          </div>
          <Link
            to={buildMatchTicketsPath(selectedMatch.homeTeam, selectedMatch.awayTeam)}
            className="inline-flex shrink-0 items-center gap-1 rounded-xl border border-neon-purple/40 bg-neon-purple/15 px-3 py-2 text-xs font-semibold text-neon-purple/90 transition-all hover:bg-neon-purple/25"
          >
            <IconWallet className="h-3.5 w-3.5" />
            Ver bilhetes
            <IconChevronRight className="h-3 w-3" />
          </Link>
        </motion.div>
      )}
    </PageTransition>
  );
}
