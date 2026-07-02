import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  getWcFriendliesUseCase,
  getWcSquadsIndexUseCase,
  getWcSquadUseCase,
  getWcScheduleUseCase,
  simulateWcMatchUseCase,
} from "@/application/container";
import { teamColor } from "@/data/teamColors";
import type { WcSquadSection } from "@/domain/entities";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { HeroPageHeader } from "@/presentation/components/layout/PageHeader";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { IconSearch } from "@/presentation/components/ui/Icons";
import { Skeleton } from "@/presentation/components/ui/Skeleton";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";
import { SquadPitchView } from "@/presentation/components/squads/SquadPitchView";
import { buildSquadMatchStatsLookup } from "@/presentation/utils/playerMatchStats";

const SECTION_COLORS: Record<string, string> = {
  GK: "#fbbf24",
  DEF: "#00d4ff",
  MID: "#00ff88",
  ATK: "#f97316",
  MID_FWD: "#a855f7",
};

const SECTION_LABEL: Record<string, string> = {
  GK: "Goleiros",
  DEF: "Defesa",
  MID: "Meio-campo",
  ATK: "Ataque",
  MID_FWD: "Meio / Ataque",
};

type SquadView = "pitch" | "list";

export function SquadsPage() {
  const [searchParams] = useSearchParams();
  const [selectedTeam, setSelectedTeam] = useState("Brasil");
  const [search, setSearch] = useState("");
  const [view, setView] = useState<SquadView>("pitch");

  const eventIdFromUrl = searchParams.get("eventId");
  const homeFromUrl = searchParams.get("home");
  const awayFromUrl = searchParams.get("away");
  const dateFromUrl = searchParams.get("date");

  const indexQuery = useQuery({
    queryKey: ["wc-squads-index"],
    queryFn: () => getWcSquadsIndexUseCase.execute(),
    staleTime: 30 * 60_000,
  });

  const scheduleQuery = useQuery({
    queryKey: ["wc-schedule"],
    queryFn: () => getWcScheduleUseCase.execute(),
    staleTime: 10 * 60_000,
  });

  const squadQuery = useQuery({
    queryKey: ["wc-squad", selectedTeam],
    queryFn: () => getWcSquadUseCase.execute(selectedTeam),
    enabled: Boolean(selectedTeam),
    staleTime: 30 * 60_000,
  });

  const friendliesQuery = useQuery({
    queryKey: ["wc-friendlies-squad", selectedTeam],
    queryFn: () =>
      getWcFriendliesUseCase.execute({
        team: selectedTeam,
        includeUpcoming: true,
        includeFinished: true,
      }),
    enabled: !eventIdFromUrl && Boolean(selectedTeam),
    staleTime: 5 * 60_000,
  });

  const matchForStats = useMemo(() => {
    if (eventIdFromUrl && homeFromUrl && awayFromUrl) {
      return {
        eventId: Number.parseInt(eventIdFromUrl, 10),
        homeTeam: homeFromUrl,
        awayTeam: awayFromUrl,
        matchDate: dateFromUrl,
      };
    }
    const friendly =
      friendliesQuery.data?.friendlies.find((item) => item.eventId != null) ?? null;
    if (!friendly?.eventId) return null;
    return {
      eventId: friendly.eventId,
      homeTeam: friendly.homeTeam,
      awayTeam: friendly.awayTeam,
      matchDate: friendly.matchDate,
    };
  }, [
    eventIdFromUrl,
    homeFromUrl,
    awayFromUrl,
    dateFromUrl,
    friendliesQuery.data,
  ]);

  const simulateQuery = useQuery({
    queryKey: [
      "wc-simulate-squad",
      matchForStats?.eventId,
      matchForStats?.homeTeam,
      matchForStats?.awayTeam,
    ],
    queryFn: () =>
      simulateWcMatchUseCase.execute({
        homeTeam: matchForStats!.homeTeam,
        awayTeam: matchForStats!.awayTeam,
        phase: "friendly",
        matchDate: matchForStats!.matchDate ?? undefined,
        sofascoreEventId: matchForStats!.eventId,
      }),
    enabled: Boolean(matchForStats?.eventId),
    staleTime: 5 * 60_000,
  });

  const matchLineup = useMemo(() => {
    if (!simulateQuery.data) return null;
    return selectedTeam === simulateQuery.data.homeTeam
      ? simulateQuery.data.fifaHomeLineup
      : simulateQuery.data.fifaAwayLineup;
  }, [simulateQuery.data, selectedTeam]);

  const matchFormation = useMemo(() => {
    if (!simulateQuery.data) return null;
    return selectedTeam === simulateQuery.data.homeTeam
      ? simulateQuery.data.fifaHomeTactics
      : simulateQuery.data.fifaAwayTactics;
  }, [simulateQuery.data, selectedTeam]);

  const matchBench = useMemo(() => {
    if (!simulateQuery.data) return null;
    return selectedTeam === simulateQuery.data.homeTeam
      ? simulateQuery.data.fifaHomeBench
      : simulateQuery.data.fifaAwayBench;
  }, [simulateQuery.data, selectedTeam]);

  const matchStatsLookup = useMemo(() => {
    if (!matchLineup?.length) return undefined;
    return buildSquadMatchStatsLookup(matchLineup, matchBench);
  }, [matchLineup, matchBench]);

  const teamGroup = useMemo(() => {
    if (!scheduleQuery.data || !selectedTeam) return null;
    for (const group of scheduleQuery.data.groups) {
      if (group.teams.includes(selectedTeam)) return group.id;
    }
    return null;
  }, [scheduleQuery.data, selectedTeam]);

  const filteredTeams = useMemo(() => {
    const teams = indexQuery.data?.teams ?? [];
    const q = search.trim().toLowerCase();
    if (!q) return teams;
    return teams.filter((t) => t.team.toLowerCase().includes(q));
  }, [indexQuery.data, search]);

  if (indexQuery.isLoading) {
    return (
      <PageTransition>
        <Skeleton className="h-36 w-full rounded-2xl" />
        <Skeleton className="h-96 w-full rounded-2xl" />
      </PageTransition>
    );
  }

  if (indexQuery.isError || !indexQuery.data) {
    return (
      <PageTransition>
        <ErrorState
          message={
            indexQuery.error instanceof Error
              ? indexQuery.error.message
              : "Falha ao carregar convocações"
          }
          onRetry={() => indexQuery.refetch()}
        />
      </PageTransition>
    );
  }

  const meta = indexQuery.data;

  return (
    <PageTransition>
      <HeroPageHeader
        title="Convocações Copa 2026"
        subtitle={`Listas oficiais de 26 jogadores · ${meta.teamCount} seleções`}
        badges={[{ label: `${meta.teamCount} seleções`, color: "purple" }]}
      />

      <div className="grid gap-6 lg:grid-cols-5">
        <aside className="lg:col-span-2 space-y-4">
          <div className="glass-card p-4 space-y-3">
            <p className="section-label">Selecionar seleção</p>
            <div className="relative">
              <IconSearch className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Buscar seleção…"
                className="select-field pl-9"
              />
            </div>
            <div className="max-h-[420px] overflow-y-auto rounded-xl border border-white/5">
              {filteredTeams.map((item) => {
                const active = item.team === selectedTeam;
                return (
                  <button
                    key={item.team}
                    type="button"
                    onClick={() => setSelectedTeam(item.team)}
                    className={`flex w-full items-center justify-between gap-2 border-b border-white/5 px-3 py-2.5 text-left text-sm transition-colors last:border-0 ${
                      active ? "bg-neon-green/8 text-white" : "text-slate-400 hover:bg-white/4"
                    }`}
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <TeamFlag team={item.team} size={22} />
                      <span className="truncate font-medium">{item.team}</span>
                    </span>
                    <span className="shrink-0 text-[11px] text-slate-500">
                      {item.playerCount}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </aside>

        <section className="lg:col-span-3">
          {squadQuery.isLoading && (
            <div className="glass-card space-y-4 p-6">
              <Skeleton className="h-8 w-1/2" />
              <Skeleton className="h-64 w-full" />
            </div>
          )}

          {squadQuery.isError && (
            <ErrorState
              message={
                squadQuery.error instanceof Error
                  ? squadQuery.error.message
                  : "Falha ao carregar elenco"
              }
              onRetry={() => squadQuery.refetch()}
            />
          )}

          {squadQuery.data && (
            <motion.div
              key={squadQuery.data.squad.team}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-4"
            >
              <div
                className="glass-card overflow-hidden"
                style={{ borderColor: `${teamColor(selectedTeam)}25` }}
              >
                <div
                  className="flex flex-wrap items-center justify-between gap-3 border-b border-white/6 px-5 py-4"
                  style={{ backgroundColor: `${teamColor(selectedTeam)}08` }}
                >
                  <div className="flex items-center gap-3">
                    <TeamFlag team={selectedTeam} size={44} rounded="md" />
                    <div>
                      <h2 className="text-xl font-bold text-white">{selectedTeam}</h2>
                      <p className="text-xs text-slate-500">
                        {squadQuery.data.squad.playerCount} convocados
                        {teamGroup && (
                          <span className="ml-2 rounded-md bg-neon-green/10 px-1.5 py-0.5 font-bold text-neon-green">
                            Grupo {teamGroup}
                          </span>
                        )}
                      </p>
                    </div>
                  </div>

                  <div className="flex rounded-xl border border-white/8 bg-black/20 p-0.5">
                    <button
                      type="button"
                      onClick={() => setView("pitch")}
                      className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                        view === "pitch"
                          ? "bg-neon-green/20 text-neon-green"
                          : "text-slate-500 hover:text-white"
                      }`}
                    >
                      Campo
                    </button>
                    <button
                      type="button"
                      onClick={() => setView("list")}
                      className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                        view === "list"
                          ? "bg-neon-green/20 text-neon-green"
                          : "text-slate-500 hover:text-white"
                      }`}
                    >
                      Lista
                    </button>
                  </div>
                </div>

                <div className="p-5">
                  {matchForStats && view === "pitch" ? (
                    <p className="mb-3 text-center text-[11px] text-slate-500">
                      Notas Sofascore do amistoso {matchForStats.homeTeam} x {matchForStats.awayTeam}
                      {simulateQuery.isFetching ? " · carregando…" : ""}
                    </p>
                  ) : null}
                  {view === "pitch" ? (
                    <SquadPitchView
                      squad={squadQuery.data.squad}
                      teamColor={teamColor(selectedTeam)}
                      matchStatsLookup={matchStatsLookup}
                      matchLineup={matchLineup}
                      matchFormation={matchFormation}
                    />
                  ) : (
                    <div className="space-y-5">
                      {squadQuery.data.squad.sections.map((section, i) => (
                        <SquadSectionBlock key={`${section.role}-${i}`} section={section} />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </section>
      </div>
    </PageTransition>
  );
}

function SquadSectionBlock({ section }: { section: WcSquadSection }) {
  const color = SECTION_COLORS[section.position] ?? "#64748b";
  const label = SECTION_LABEL[section.position] ?? section.role;
  let shirtNumber = 1;

  return (
    <div>
      <div className="mb-2 flex items-center gap-2">
        <span
          className="h-2 w-2 rounded-full"
          style={{ backgroundColor: color, boxShadow: `0 0 8px ${color}60` }}
        />
        <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400">
          {section.role || label}
        </h3>
        <span className="text-[11px] text-slate-500">({section.players.length})</span>
      </div>
      <ul className="divide-y divide-white/5 rounded-xl border border-white/5 overflow-hidden">
        {section.players.map((player) => {
          const num = shirtNumber++;
          return (
            <li
              key={player.name}
              className="flex items-center gap-3 bg-white/[0.02] px-4 py-2.5 text-sm"
            >
              <span
                className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-[10px] font-black"
                style={{ backgroundColor: `${color}25`, color }}
              >
                {num}
              </span>
              <span className="min-w-0 flex-1 font-medium text-white">{player.name}</span>
              <span className="truncate text-right text-xs text-slate-500">
                {player.club ?? "—"}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
