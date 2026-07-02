import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getWcFriendliesUseCase, getWcTeamsUseCase } from "@/application/container";
import type { WcFriendlyMatch } from "@/domain/entities";
import { AppTableShell } from "@/presentation/components/layout/AppTableShell";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { PageHeader } from "@/presentation/components/layout/PageHeader";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { FilterBar, FilterChip } from "@/presentation/components/ui/FilterBar";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";
import { IconChevronRight } from "@/presentation/components/ui/Icons";

type StatusFilter = "all" | "upcoming" | "finished";

function formatMatchDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      weekday: "short",
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case "finished":
      return "Disputado";
    case "notstarted":
      return "Agendado";
    case "live":
    case "inprogress":
      return "Ao vivo";
    case "postponed":
      return "Adiado";
    case "canceled":
    case "cancelled":
      return "Cancelado";
    default:
      return status;
  }
}

function statusClass(status: string): string {
  if (status === "finished") return "bg-slate-500/15 text-slate-300";
  if (status === "notstarted") return "bg-neon-green/10 text-neon-green";
  if (status === "live" || status === "inprogress") return "bg-amber-500/15 text-amber-300";
  return "bg-white/8 text-slate-400";
}

function opponentFor(match: WcFriendlyMatch, team: string): string {
  return match.homeTeam === team ? match.awayTeam : match.homeTeam;
}

function scoreFor(match: WcFriendlyMatch): string {
  if (match.homeScore == null || match.awayScore == null) return "—";
  return `${match.homeScore} × ${match.awayScore}`;
}

function friendlyRowKey(match: WcFriendlyMatch): string {
  return `${match.eventId ?? "na"}-${match.fifaMatchId ?? "na"}-${match.matchDate ?? "na"}`;
}

function sourceBadgeLabel(source: string): string {
  if (source === "sofascore") return "Sofascore";
  if (source === "fifa") return "FIFA";
  return source;
}

function buildLiveLink(match: WcFriendlyMatch): string | null {
  const live = match.status === "live" || match.status === "inprogress";
  if (!live || match.homeScore == null || match.awayScore == null) return null;
  const params = new URLSearchParams({
    source: "friendly",
    phase: "friendly",
    liveHome: String(match.homeScore),
    liveAway: String(match.awayScore),
  });
  return `/match/${encodeURIComponent(match.homeTeam)}/${encodeURIComponent(match.awayTeam)}?${params}`;
}

function buildPredictLink(match: WcFriendlyMatch): string {
  const params = new URLSearchParams({
    home: match.homeTeam,
    away: match.awayTeam,
    sofascore: "1",
    source: "friendly",
    phase: "round_16",
    simulate: "1",
  });
  if (match.eventId != null) {
    params.set("eventId", String(match.eventId));
  }
  if (match.fifaMatchId) {
    params.set("fifaMatchId", match.fifaMatchId);
  }
  if (match.matchDate) {
    params.set("date", match.matchDate.slice(0, 10));
  }
  return `/predict?${params.toString()}`;
}

export function FriendliesPage() {
  const [team, setTeam] = useState("Brasil");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const teamsQuery = useQuery({
    queryKey: ["wc-teams"],
    queryFn: () => getWcTeamsUseCase.execute(),
    staleTime: 30 * 60_000,
  });

  const includeFinished = statusFilter !== "upcoming";
  const includeUpcoming = statusFilter !== "finished";

  const friendliesQuery = useQuery({
    queryKey: ["wc-friendlies", team, includeFinished, includeUpcoming],
    queryFn: () =>
      getWcFriendliesUseCase.execute({
        team,
        includeFinished,
        includeUpcoming,
      }),
    enabled: Boolean(team),
    staleTime: 5 * 60_000,
  });

  const teamOptions = useMemo(() => {
    const teams = teamsQuery.data ?? [];
    if (teams.length === 0) return [team];
    return teams.includes(team) ? teams : [team, ...teams];
  }, [teamsQuery.data, team]);

  const rows = friendliesQuery.data?.friendlies ?? [];

  if (teamsQuery.isLoading) {
    return (
      <PageTransition>
        <PageHeader title="Amistosos" subtitle="Carregando seleções…" />
        <DashboardSkeleton />
      </PageTransition>
    );
  }

  return (
    <PageTransition>
      <PageHeader
        title="Amistosos"
        subtitle={`Calendário ${new Date().getFullYear()} · Sofascore + janela FIFA`}
      />

      <section className="mb-6 grid gap-4 md:grid-cols-[minmax(0,280px)_1fr]">
        <label className="block space-y-2">
          <span className="text-xs font-bold uppercase tracking-widest text-slate-500">
            Seleção
          </span>
          <select
            value={team}
            onChange={(e) => setTeam(e.target.value)}
            className="app-input w-full"
          >
            {teamOptions.map((name) => (
              <option key={name} value={name} className="bg-slate-900">
                {name}
              </option>
            ))}
          </select>
        </label>

        <FilterBar label="Período">
          <FilterChip
            active={statusFilter === "all"}
            onClick={() => setStatusFilter("all")}
            label="Todos"
          />
          <FilterChip
            active={statusFilter === "upcoming"}
            onClick={() => setStatusFilter("upcoming")}
            label="Futuros"
          />
          <FilterChip
            active={statusFilter === "finished"}
            onClick={() => setStatusFilter("finished")}
            label="Disputados"
          />
        </FilterBar>
      </section>

      {friendliesQuery.isLoading ? (
        <DashboardSkeleton />
      ) : friendliesQuery.isError ? (
        <ErrorState
          message={
            friendliesQuery.error instanceof Error
              ? friendliesQuery.error.message
              : "Falha ao carregar amistosos"
          }
          onRetry={() => friendliesQuery.refetch()}
        />
      ) : rows.length === 0 ? (
        <div className="app-empty-state">
          Nenhum amistoso em {new Date().getFullYear()} para {team} com os filtros atuais.
        </div>
      ) : (
        <AppTableShell
          footer={
            <>
              {rows.length} amistoso(s) em {friendliesQuery.data?.year ?? new Date().getFullYear()} ·
              fonte {friendliesQuery.data?.source ?? "sofascore"}
            </>
          }
        >
            <table className="min-w-full text-sm">
              <thead>
                <tr>
                  <th className="px-4 py-3">Data</th>
                  <th className="px-4 py-3">Confronto</th>
                  <th className="px-4 py-3">Placar</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Fontes</th>
                  <th className="px-4 py-3 text-right">Ação</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((match) => {
                  const opponent = opponentFor(match, team);
                  return (
                    <tr
                      key={friendlyRowKey(match)}
                      className="group border-b border-white/5 transition-colors hover:bg-white/[0.03]"
                    >
                      <td className="px-4 py-3.5 whitespace-nowrap text-xs text-slate-400">
                        {formatMatchDate(match.matchDate)}
                      </td>
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-2 min-w-0">
                          <TeamFlag team={team} size={28} />
                          <span className="font-medium text-white">{team}</span>
                          <span className="text-[11px] font-black text-slate-500">
                            {match.isHome ? "×" : "@"}
                          </span>
                          <TeamFlag team={opponent} size={28} />
                          <span className="truncate font-medium text-white">{opponent}</span>
                        </div>
                        <span className="mt-1 block text-[11px] text-slate-500">
                          {match.tournament}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 font-mono text-sm text-white">
                        {scoreFor(match)}
                      </td>
                      <td className="px-4 py-3.5">
                        <span
                          className={`inline-flex rounded-md px-2 py-1 text-[11px] font-semibold ${statusClass(match.status)}`}
                        >
                          {statusLabel(match.status)}
                        </span>
                      </td>
                      <td className="px-4 py-3.5">
                        <div className="flex flex-wrap gap-1">
                          {match.sources.map((source) => (
                            <span
                              key={source}
                              className="inline-flex rounded-md border border-white/8 bg-white/4 px-1.5 py-0.5 text-[10px] font-medium text-slate-400"
                            >
                              {sourceBadgeLabel(source)}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-3.5 text-right">
                        <div className="flex flex-wrap justify-end gap-1.5 opacity-0 transition-all group-hover:opacity-100">
                          {buildLiveLink(match) && (
                            <Link
                              to={buildLiveLink(match)!}
                              className="inline-flex items-center gap-1 rounded-lg border border-amber-500/25 bg-amber-500/10 px-2.5 py-1.5 text-[11px] font-medium text-amber-300 hover:border-amber-400/40"
                            >
                              Ao vivo
                              <IconChevronRight className="h-3 w-3" />
                            </Link>
                          )}
                          <Link
                            to={buildPredictLink(match)}
                            className="inline-flex items-center gap-1 rounded-lg border border-white/8 bg-white/4 px-2.5 py-1.5 text-[11px] font-medium text-slate-400 hover:border-neon-green/30 hover:text-neon-green"
                          >
                            Palpite
                            <IconChevronRight className="h-3 w-3" />
                          </Link>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
        </AppTableShell>
      )}
    </PageTransition>
  );
}
