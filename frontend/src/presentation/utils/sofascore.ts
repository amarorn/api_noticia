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

export function formatScheduleDate(kickoff: string | null | undefined): string {
  if (!kickoff) return "—";
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      weekday: "short",
      day: "2-digit",
      month: "short",
    }).format(new Date(kickoff));
  } catch {
    return kickoff.split("T")[0] ?? "—";
  }
}

export function formatScheduleTime(kickoff: string | null | undefined): string {
  if (!kickoff) return "—";
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(kickoff));
  } catch {
    return "—";
  }
}

/** Bilhete combo pré-jogo só faz sentido antes do apito inicial. */
export function isMatchPregame(kickoff: string | null | undefined): boolean {
  if (!kickoff) return true;
  const startMs = new Date(kickoff).getTime();
  if (Number.isNaN(startMs)) return true;
  return startMs > Date.now();
}
