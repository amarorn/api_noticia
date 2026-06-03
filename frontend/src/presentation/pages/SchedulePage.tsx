import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getWcScheduleUseCase } from "@/application/container";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { ErrorState } from "@/presentation/components/ui/ErrorState";
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
        subtitle={`${schedule.competition} · ${schedule.totalMatches} jogos na fase de grupos`}
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
        <div className="flex flex-wrap items-center gap-2">
          <FilterChip
            active={selectedRound === "all"}
            onClick={() => setSelectedRound("all")}
            label="Todas as rodadas"
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
        </div>

        <WcScheduleTable
          schedule={schedule}
          selectedRound={selectedRound}
          selectedGroup={selectedGroup}
        />
      </section>
    </PageTransition>
  );
}

function PageHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <header className="mb-8">
      <h1 className="text-2xl font-black tracking-tight text-white md:text-3xl">{title}</h1>
      <p className="mt-1 text-sm text-slate-400">{subtitle}</p>
    </header>
  );
}

function FilterChip({
  label,
  active,
  onClick,
  count,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  count?: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-3.5 py-1.5 text-xs font-semibold transition-all ${
        active
          ? "bg-neon-green/15 text-neon-green ring-1 ring-neon-green/30"
          : "bg-white/5 text-slate-400 hover:bg-white/8 hover:text-slate-300"
      }`}
    >
      {label}
      {count != null && (
        <span className="ml-1.5 text-[10px] opacity-70">({count})</span>
      )}
    </button>
  );
}
