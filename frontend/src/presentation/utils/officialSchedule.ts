import type { WcSchedule, WcScheduleMatch } from "@/domain/entities";

export function matchesForPhase(
  schedule: WcSchedule,
  phase: string,
): WcScheduleMatch[] {
  return schedule.matches.filter((m) => m.phase === phase);
}

export function homeTeamsInSchedule(matches: WcScheduleMatch[]): string[] {
  return [...new Set(matches.map((m) => m.homeTeam))].sort((a, b) =>
    a.localeCompare(b, "pt-BR"),
  );
}

export function awayOpponentsForHome(
  home: string,
  matches: WcScheduleMatch[],
): string[] {
  return matches.filter((m) => m.homeTeam === home).map((m) => m.awayTeam);
}

export function findOfficialMatch(
  home: string,
  away: string,
  matches: WcScheduleMatch[],
): WcScheduleMatch | undefined {
  return matches.find((m) => m.homeTeam === home && m.awayTeam === away);
}

export function findReverseOfficialMatch(
  home: string,
  away: string,
  matches: WcScheduleMatch[],
): WcScheduleMatch | undefined {
  return matches.find((m) => m.homeTeam === away && m.awayTeam === home);
}

export function phasesInSchedule(schedule: WcSchedule): string[] {
  return [...new Set(schedule.matches.map((m) => m.phase))];
}

export function buildMatchGroupLookup(schedule: WcSchedule): Map<string, string> {
  const map = new Map<string, string>();
  for (const match of schedule.matches) {
    if (match.group) {
      map.set(`${match.homeTeam}|${match.awayTeam}`, match.group);
    }
  }
  return map;
}

export function groupForMatch(
  home: string,
  away: string,
  lookup: Map<string, string>,
): string | null {
  return lookup.get(`${home}|${away}`) ?? null;
}

export function sortedGroupIds(schedule: WcSchedule): string[] {
  return schedule.groups.map((g) => g.id).sort();
}

export function buildMatchRoundLookup(schedule: WcSchedule): Map<string, number> {
  const map = new Map<string, number>();
  for (const match of schedule.matches) {
    map.set(`${match.homeTeam}|${match.awayTeam}`, match.round);
  }
  return map;
}

export function roundForMatchPair(
  home: string,
  away: string,
  lookup: Map<string, number>,
): number | null {
  return lookup.get(`${home}|${away}`) ?? null;
}

export function formatOfficialMatchLabel(
  home: string,
  away: string,
  group: string | null,
  round: number | null,
): string {
  const base = `${home} x ${away}`;
  const parts: string[] = [];
  if (group) parts.push(`Gr. ${group}`);
  if (round) parts.push(`R${round}`);
  return parts.length ? `${base} · ${parts.join(" · ")}` : base;
}
