import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSuperbetLiveUseCase, getWcScheduleUseCase } from "@/application/container";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { PageHeader } from "@/presentation/components/layout/PageHeader";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { FilterBar, FilterChip } from "@/presentation/components/ui/FilterBar";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import {
  WcGroupGrid,
  WcScheduleTable,
} from "@/presentation/components/schedule/WcScheduleTable";

export function SchedulePage() {
  const [selectedRound, setSelectedRound] = useState<number | "all">("all");
  const [selectedGroup, setSelectedGroup] = useState<string | "all">("all");

  const scheduleQuery = useQuery({
    queryKey: ["wc-schedule"],
    queryFn: () => getWcScheduleUseCase.execute(),
    staleTime: 10 * 60_000,
  });

  const liveQuery = useQuery({
    queryKey: ["superbet-live-schedule"],
    queryFn: () => getSuperbetLiveUseCase.execute({ rank: false }),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });

  const roundCounts = useMemo(() => {
    if (!scheduleQuery.data) return new Map<number, number>();
    const counts = new Map<number, number>();
    for (const m of scheduleQuery.data.matches) {
      counts.set(m.round, (counts.get(m.round) ?? 0) + 1);
    }
    return counts;
  }, [scheduleQuery.data]);

  if (scheduleQuery.isLoading) {
    return (
      <PageTransition>
        <PageHeader
          title="Tabela de jogos"
          subtitle="Carregando calendário da fase de grupos…"
        />
        <DashboardSkeleton />
      </PageTransition>
    );
  }

  if (scheduleQuery.isError || !scheduleQuery.data) {
    return (
      <PageTransition>
        <ErrorState
          message={
            scheduleQuery.error instanceof Error
              ? scheduleQuery.error.message
              : "Falha ao carregar calendário"
          }
          onRetry={() => scheduleQuery.refetch()}
        />
      </PageTransition>
    );
  }

  const schedule = scheduleQuery.data;

  return (
    <PageTransition>
      <PageHeader
        title="Tabela de jogos"
        subtitle={
          schedule.predictionsSummary
            ? `${schedule.competition} · ${schedule.totalMatches} jogos · ${schedule.predictionsSummary.draws} empates previstos`
            : `${schedule.competition} · ${schedule.totalMatches} jogos na fase de grupos`
        }
      />

      <section className="mb-8 space-y-3">
        <h2 className="text-xs font-bold uppercase tracking-widest text-slate-500">
          Grupos
        </h2>
        <WcGroupGrid
          groups={schedule.groups}
          selectedGroup={selectedGroup}
          onSelectGroup={setSelectedGroup}
        />
      </section>

      <section className="space-y-4">
        <FilterBar label="Rodada">
          <FilterChip
            active={selectedRound === "all"}
            onClick={() => setSelectedRound("all")}
            label="Todas"
          />
          {schedule.matchdays.map((round) => (
            <FilterChip
              key={round}
              active={selectedRound === round}
              onClick={() => setSelectedRound(round)}
              label={`Rodada ${round}`}
              count={roundCounts.get(round)}
            />
          ))}
          {selectedGroup !== "all" && (
            <FilterChip
              active
              onClick={() => setSelectedGroup("all")}
              label={`Grupo ${selectedGroup} ✕`}
            />
          )}
        </FilterBar>

        <WcScheduleTable
          schedule={schedule}
          selectedRound={selectedRound}
          selectedGroup={selectedGroup}
          liveEvents={liveQuery.data?.events ?? []}
        />
      </section>
    </PageTransition>
  );
}
