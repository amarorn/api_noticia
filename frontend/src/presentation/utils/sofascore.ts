import type { WcSchedule, WcScheduleMatch } from "@/domain/entities";

export function findMatchInSchedule(
  schedule: WcSchedule,
  home: string,
  away: string,
): WcScheduleMatch | undefined {
  return (
    schedule.matches.find((m) => m.homeTeam === home && m.awayTeam === away) ??
    schedule.matches.find((m) => m.homeTeam === away && m.awayTeam === home)
  );
}

export function kickoffDateFromIso(kickoff: string | null | undefined): string | null {
  if (!kickoff) return null;
  const day = kickoff.split("T")[0];
  return /^\d{4}-\d{2}-\d{2}$/.test(day) ? day : null;
}

/** Bilhete combo pré-jogo só faz sentido antes do apito inicial. */
export function isMatchPregame(kickoff: string | null | undefined): boolean {
  if (!kickoff) return true;
  const startMs = new Date(kickoff).getTime();
  if (Number.isNaN(startMs)) return true;
  return startMs > Date.now();
}
