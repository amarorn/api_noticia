import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getSuperbetLiveUseCase } from "@/application/container";
import type { SuperbetLiveEvent } from "@/domain/entities";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { PageHeader } from "@/presentation/components/layout/PageHeader";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { FilterBar, FilterChip } from "@/presentation/components/ui/FilterBar";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";
import { IconChevronRight } from "@/presentation/components/ui/Icons";

type SportFilter = "football" | "all";

function formatOdds(odds: Record<string, number>): string | null {
  const parts: string[] = [];
  if (odds["1"]) parts.push(`1 ${odds["1"].toFixed(2)}`);
  if (odds["X"]) parts.push(`X ${odds["X"].toFixed(2)}`);
  if (odds["2"]) parts.push(`2 ${odds["2"].toFixed(2)}`);
  return parts.length > 0 ? parts.join(" · ") : null;
}

function minuteLabel(event: SuperbetLiveEvent): string {
  if (event.periodLabel) {
    return `${event.minute}' · ${event.periodLabel}`;
  }
  return event.minute > 0 ? `${event.minute}'` : "Ao vivo";
}

function buildInPlayLink(event: SuperbetLiveEvent): string {
  return `/ao-vivo/${event.eventId}`;
}

function isNationalTeam(name: string): boolean {
  const known = new Set([
    "Brasil",
    "Argentina",
    "Uruguai",
    "Chile",
    "Colômbia",
    "Equador",
    "Paraguai",
    "Peru",
    "Bolívia",
    "Venezuela",
    "México",
    "EUA",
    "Canadá",
    "Costa Rica",
    "Jamaica",
    "Alemanha",
    "França",
    "Espanha",
    "Itália",
    "Inglaterra",
    "Portugal",
    "Holanda",
    "Bélgica",
    "Croácia",
    "Suíça",
    "Dinamarca",
    "Áustria",
    "Polônia",
    "Sérvia",
    "Turquia",
    "Ucrânia",
    "Escócia",
    "Irlanda",
    "Noruega",
    "Suécia",
    "Japão",
    "Coreia do Sul",
    "Austrália",
    "Arábia Saudita",
    "Irã",
    "Qatar",
    "Egito",
    "Marrocos",
    "Nigéria",
    "Senegal",
    "Gana",
    "Camarões",
    "Costa do Marfim",
    "África do Sul",
    "Tunísia",
    "Argélia",
  ]);
  return known.has(name);
}

export function LivePage() {
  const [sportFilter, setSportFilter] = useState<SportFilter>("football");
  const [nationalOnly, setNationalOnly] = useState(false);

  const liveQuery = useQuery({
    queryKey: ["superbet-live", sportFilter],
    queryFn: () =>
      getSuperbetLiveUseCase.execute({
        sportId: sportFilter === "football" ? 5 : undefined,
        allSports: sportFilter === "all",
      }),
    staleTime: 15_000,
    refetchInterval: 30_000,
  });

  const rows = useMemo(() => {
    const events = liveQuery.data?.events ?? [];
    if (!nationalOnly) return events;
    return events.filter(
      (event) => isNationalTeam(event.homeTeam) || isNationalTeam(event.awayTeam),
    );
  }, [liveQuery.data?.events, nationalOnly]);

  return (
    <PageTransition>
      <PageHeader
        title="Ao vivo"
        subtitle="Jogos em andamento na Superbet — in-play, cash-out e aportes"
      />

      <section className="mb-6">
        <FilterBar label="Filtros">
          <FilterChip
            active={sportFilter === "football"}
            onClick={() => setSportFilter("football")}
            label="Futebol"
          />
          <FilterChip
            active={sportFilter === "all"}
            onClick={() => setSportFilter("all")}
            label="Todos os esportes"
          />
          <FilterChip
            active={nationalOnly}
            onClick={() => setNationalOnly((v) => !v)}
            label="Seleções"
          />
        </FilterBar>
      </section>

      {liveQuery.isLoading ? (
        <DashboardSkeleton />
      ) : liveQuery.isError ? (
        <ErrorState
          message={
            liveQuery.error instanceof Error
              ? liveQuery.error.message
              : "Falha ao carregar jogos ao vivo"
          }
          onRetry={() => liveQuery.refetch()}
        />
      ) : rows.length === 0 ? (
        <div className="rounded-2xl border border-white/8 bg-white/[0.02] px-6 py-12 text-center text-sm text-slate-400">
          Nenhum jogo ao vivo no momento na Superbet.
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-white/8 bg-white/[0.02]">
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-white/8 text-left text-[11px] uppercase tracking-widest text-slate-500">
                  <th className="px-4 py-3">Confronto</th>
                  <th className="px-4 py-3">Placar</th>
                  <th className="px-4 py-3">Tempo</th>
                  <th className="px-4 py-3">Odds 1X2</th>
                  <th className="px-4 py-3">Mercados</th>
                  <th className="px-4 py-3 text-right">Ação</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((event) => {
                  const odds = formatOdds(event.h2hOdds);
                  return (
                    <tr
                      key={event.eventId}
                      className="group border-b border-white/5 transition-colors hover:bg-white/[0.03]"
                    >
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-2 min-w-0">
                          <TeamFlag team={event.homeTeam} size={28} />
                          <span className="truncate font-medium text-white">{event.homeTeam}</span>
                          <span className="text-[11px] font-black text-slate-500">×</span>
                          <TeamFlag team={event.awayTeam} size={28} />
                          <span className="truncate font-medium text-white">{event.awayTeam}</span>
                        </div>
                        <span className="mt-1 block text-[11px] text-slate-500">
                          ID {event.eventId}
                          {event.betradarId ? ` · Betradar ${event.betradarId}` : ""}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 font-mono text-sm text-white">
                        {event.homeScore} × {event.awayScore}
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="inline-flex rounded-md bg-amber-500/15 px-2 py-1 text-[11px] font-semibold text-amber-300">
                          {minuteLabel(event)}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-xs text-slate-400">
                        {odds ?? "—"}
                      </td>
                      <td className="px-4 py-3.5 text-xs text-slate-400">
                        {event.marketCount > 0 ? event.marketCount : "—"}
                      </td>
                      <td className="px-4 py-3.5 text-right">
                        <Link
                          to={buildInPlayLink(event)}
                          className="inline-flex items-center gap-1 rounded-lg border border-amber-500/25 bg-amber-500/10 px-2.5 py-1.5 text-[11px] font-medium text-amber-300 hover:border-amber-400/40"
                        >
                          Abrir in-play
                          <IconChevronRight className="h-3 w-3" />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="border-t border-white/8 px-4 py-3 text-xs text-slate-500">
            {rows.length} jogo(s) ao vivo · fonte Superbet
            {liveQuery.data?.capturedAt
              ? ` · atualizado ${new Intl.DateTimeFormat("pt-BR", {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                }).format(new Date(liveQuery.data.capturedAt))}`
              : ""}
          </div>
        </div>
      )}
    </PageTransition>
  );
}
