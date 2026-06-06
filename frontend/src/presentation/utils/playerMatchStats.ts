import type { KxlFeptPlayer, WcSimulationLineupPlayer } from "@/domain/entities";
import type { PitchPlayer } from "@/presentation/components/squads/PlayerPitchToken";

export interface PlayerMatchStats {
  name: string;
  position: string | null;
  line: string | null;
  sofascoreRating: number | null;
  isCaptain: boolean;
  yellowCards: number;
  redCards: number;
  isStarter: boolean;
}

function normalizeKey(name: string): string {
  return name
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function lastToken(name: string): string {
  const parts = normalizeKey(name).split(" ").filter(Boolean);
  return parts[parts.length - 1] ?? normalizeKey(name);
}

export function buildPlayerStatsLookup(
  starters: Array<WcSimulationLineupPlayer | KxlFeptPlayer>,
): Map<string, PlayerMatchStats> {
  const map = new Map<string, PlayerMatchStats>();

  for (const raw of starters) {
    const stats: PlayerMatchStats = {
      name: raw.name,
      position: raw.position ?? null,
      line: "line" in raw ? (raw.line ?? null) : null,
      sofascoreRating: raw.sofascoreRating ?? null,
      isCaptain: "isCaptain" in raw ? Boolean(raw.isCaptain) : false,
      yellowCards: "yellowCards" in raw ? (raw.yellowCards ?? 0) : 0,
      redCards: "redCards" in raw ? (raw.redCards ?? 0) : 0,
      isStarter: "isStarter" in raw ? Boolean(raw.isStarter ?? true) : true,
    };

    const keys = new Set([
      normalizeKey(stats.name),
      lastToken(stats.name),
    ]);

    for (const key of keys) {
      if (key) map.set(key, stats);
    }
  }

  return map;
}

const SECTION_LABEL: Record<string, string> = {
  GK: "Goleiro",
  DEF: "Defesa",
  MID: "Meio",
  ATK: "Ataque",
  MID_FWD: "Meio / Ataque",
};

export function buildSquadMatchStatsLookup(
  starters: WcSimulationLineupPlayer[] | null | undefined,
  bench: WcSimulationLineupPlayer[] | null | undefined,
): Map<string, PlayerMatchStats> {
  const map = buildPlayerStatsLookup([
    ...(starters ?? []).map((p) => ({ ...p, isStarter: true })),
    ...(bench ?? []).map((p) => ({ ...p, isStarter: false })),
  ]);
  return map;
}

export function buildReserveHoverStats(player: PitchPlayer): PlayerMatchStats {
  return {
    name: player.name,
    position: SECTION_LABEL[player.position] ?? player.position,
    line: player.line ?? null,
    sofascoreRating: player.sofascoreRating ?? null,
    isCaptain: player.isCaptain ?? false,
    yellowCards: player.yellowCards ?? 0,
    redCards: player.redCards ?? 0,
    isStarter: false,
  };
}

export function isPlayerInMatchLineup(
  playerName: string,
  lookup: Map<string, PlayerMatchStats> | undefined,
): boolean {
  const stats = lookupPlayerStats(playerName, lookup);
  return stats?.isStarter ?? false;
}

export function lookupPlayerStats(
  playerName: string,
  lookup: Map<string, PlayerMatchStats> | undefined,
): PlayerMatchStats | undefined {
  if (!lookup || lookup.size === 0) return undefined;
  const full = normalizeKey(playerName);
  if (lookup.has(full)) return lookup.get(full);
  const token = lastToken(playerName);
  if (lookup.has(token)) return lookup.get(token);

  for (const [key, stats] of lookup) {
    if (full.includes(key) || key.includes(token)) {
      return stats;
    }
  }
  return undefined;
}
