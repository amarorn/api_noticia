import type { WcSimulationLineupPlayer } from "@/domain/entities";
import type { PitchPlayer } from "@/presentation/components/squads/PlayerPitchToken";

export interface PlacedPitchPlayer extends PitchPlayer {
  x: number;
  y: number;
}

const LINE_TO_POSITION: Record<string, string> = {
  goleiro: "GK",
  defesa: "DEF",
  meio: "MID",
  ataque: "ATK",
};

/** Normaliza linha/posição (FIFA, Sofascore G/D/M/F ou texto PT). */
export function normalizeLine(position: string | null, line?: string | null): string {
  const raw = (line ?? position ?? "").toLowerCase().trim();
  if (!raw) return "meio";

  if (raw === "g" || raw === "gk" || raw.includes("goleiro") || raw.includes("goal")) {
    return "goleiro";
  }
  if (raw === "d" || raw.includes("def") || raw.includes("zagueiro") || raw.includes("lateral")) {
    return "defesa";
  }
  if (
    raw === "f" ||
    raw === "fw" ||
    raw === "st" ||
    raw.includes("ata") ||
    raw.includes("forward") ||
    raw.includes("striker")
  ) {
    return "ataque";
  }
  if (raw === "m" || raw.includes("meio") || raw.includes("mid")) {
    return "meio";
  }
  return "meio";
}

export function parseFormation(formation: string | null): number[] {
  if (!formation) return [4, 3, 3];
  const parts = formation
    .split("-")
    .map((n) => Number.parseInt(n.trim(), 10))
    .filter((n) => Number.isFinite(n) && n > 0);
  return parts.length > 0 ? parts : [4, 3, 3];
}

export function distributeRow(count: number): number[] {
  if (count <= 0) return [];
  const margin = count === 1 ? 50 : 12;
  const span = 100 - margin * 2;
  if (count === 1) return [50];
  return Array.from({ length: count }, (_, i) => margin + (i / (count - 1)) * span);
}

function toPlaced(
  player: WcSimulationLineupPlayer,
  line: string,
  x: number,
  y: number,
  shirt: { value: number },
): PlacedPitchPlayer {
  const number = player.shirtNumber ?? shirt.value++;
  return {
    name: player.name,
    club: null,
    number,
    position: LINE_TO_POSITION[line] ?? line.toUpperCase(),
    line,
    sofascoreRating: player.sofascoreRating ?? null,
    isCaptain: player.isCaptain,
    yellowCards: player.yellowCards ?? 0,
    redCards: player.redCards ?? 0,
    isStarter: true,
    x,
    y,
  };
}

function placeRow(
  pool: WcSimulationLineupPlayer[],
  line: string,
  y: number,
  placed: PlacedPitchPlayer[],
  shirt: { value: number },
): void {
  const xs = distributeRow(pool.length);
  pool.forEach((player, index) => {
    placed.push(toPlaced(player, line, xs[index] ?? 50, y, shirt));
  });
}

/**
 * Posiciona todos os titulares da escalação (FIFA/Sofascore) no campo.
 * A formação só define as linhas visuais — nunca descarta jogador da API.
 */
export function placeStartersOnPitch(
  players: WcSimulationLineupPlayer[],
  formation: string | null,
): PlacedPitchPlayer[] {
  if (players.length === 0) return [];

  const buckets: Record<string, WcSimulationLineupPlayer[]> = {
    goleiro: [],
    defesa: [],
    meio: [],
    ataque: [],
  };

  for (const player of players) {
    const line = normalizeLine(player.position, player.line ?? null);
    buckets[line].push(player);
  }

  const parts = parseFormation(formation);
  const placed: PlacedPitchPlayer[] = [];
  const shirt = { value: 1 };

  placeRow(buckets.goleiro, "goleiro", 88, placed, shirt);
  placeRow(buckets.defesa, "defesa", 74, placed, shirt);

  const meios = [...buckets.meio];
  const atacantes = [...buckets.ataque];

  if (parts.length >= 4) {
    const holding = meios.splice(0, parts[1]);
    const attackingMid = meios.splice(0, parts[2]);
    const strikers = [...meios, ...atacantes];

    placeRow(holding, "meio", 62, placed, shirt);
    placeRow(attackingMid, "meio", 46, placed, shirt);
    placeRow(strikers, "ataque", 26, placed, shirt);
  } else if (parts.length === 3) {
    placeRow(meios, "meio", 52, placed, shirt);
    placeRow(atacantes, "ataque", 28, placed, shirt);
  } else {
    placeRow(meios, "meio", 52, placed, shirt);
    placeRow(atacantes, "ataque", 28, placed, shirt);
  }

  const placedNames = new Set(placed.map((p) => p.name));
  const missing = players.filter((p) => !placedNames.has(p.name));
  if (missing.length > 0) {
    placeRow(missing, "meio", 38, placed, shirt);
  }

  return placed;
}
