import { useMemo } from "react";
import type { WcSimulationLineupPlayer, WcSquad } from "@/domain/entities";
import { assignSquadNumbers } from "@/presentation/utils/playerPortrait";
import { placeStartersOnPitch } from "@/presentation/utils/pitchPlacement";
import {
  isPlayerInMatchLineup,
  type PlayerMatchStats,
} from "@/presentation/utils/playerMatchStats";
import { PitchField } from "./PitchField";
import { PlayerPitchToken, type PitchPlayer } from "./PlayerPitchToken";
import { ReserveBenchPanel } from "./ReserveBenchPanel";

const LINE_Y: Record<string, number[]> = {
  GK: [88],
  DEF: [74, 66],
  MID_FWD: [42],
  MID: [50, 42],
  ATK: [22, 14],
};

const POSITION_COLOR: Record<string, string> = {
  GK: "#fbbf24",
  DEF: "#00d4ff",
  MID: "#00ff88",
  ATK: "#f97316",
  MID_FWD: "#a855f7",
};

interface PlacedPlayer extends PitchPlayer {
  x: number;
  y: number;
}

function distributeRow(count: number): number[] {
  if (count <= 0) return [];
  const margin = count === 1 ? 50 : 10;
  const span = 100 - margin * 2;
  if (count === 1) return [50];
  return Array.from({ length: count }, (_, i) => margin + (i / (count - 1)) * span);
}

function placeSection(players: PitchPlayer[], position: string): PlacedPlayer[] {
  const yLines = LINE_Y[position] ?? [50];
  const perRow = Math.ceil(players.length / yLines.length);
  const placed: PlacedPlayer[] = [];

  yLines.forEach((y, rowIdx) => {
    const rowPlayers = players.slice(rowIdx * perRow, (rowIdx + 1) * perRow);
    const xs = distributeRow(rowPlayers.length);
    rowPlayers.forEach((player, i) => {
      placed.push({ ...player, x: xs[i] ?? 50, y });
    });
  });

  return placed;
}

interface SquadPitchViewProps {
  squad: WcSquad;
  teamColor: string;
  matchStatsLookup?: Map<string, PlayerMatchStats>;
  matchLineup?: WcSimulationLineupPlayer[] | null;
  matchFormation?: string | null;
}

export function SquadPitchView({
  squad,
  teamColor,
  matchStatsLookup,
  matchLineup,
  matchFormation,
}: SquadPitchViewProps) {
  const lineupMode = Boolean(matchLineup && matchLineup.length > 0);

  const { fieldPlayers, reservePlayers, sections, formationLabel } = useMemo(() => {
    const { sections: numbered } = assignSquadNumbers(squad);

    if (lineupMode && matchLineup) {
      const startersOnField = placeStartersOnPitch(matchLineup, matchFormation ?? null);
      const reserves: PitchPlayer[] = [];

      for (const section of numbered) {
        for (const player of section.players) {
          if (isPlayerInMatchLineup(player.name, matchStatsLookup)) continue;
          reserves.push({
            name: player.name,
            club: player.club,
            number: player.number,
            position: section.position,
            isStarter: false,
          });
        }
      }

      return {
        fieldPlayers: startersOnField,
        reservePlayers: reserves,
        sections: numbered.map((section) => ({
          position: section.position,
          role: section.role,
          color: POSITION_COLOR[section.position] ?? "#64748b",
          count: section.players.length,
        })),
        formationLabel: matchFormation,
      };
    }

    const allPlaced: PlacedPlayer[] = [];
    const sectionMeta = numbered.map((section) => {
      const players: PitchPlayer[] = section.players.map((p) => ({
        name: p.name,
        club: p.club,
        number: p.number,
        position: section.position,
      }));
      const placed = placeSection(players, section.position);
      allPlaced.push(...placed);
      return {
        position: section.position,
        role: section.role,
        color: POSITION_COLOR[section.position] ?? "#64748b",
        count: players.length,
      };
    });

    return {
      fieldPlayers: allPlaced,
      reservePlayers: [] as PitchPlayer[],
      sections: sectionMeta,
      formationLabel: null,
    };
  }, [squad, lineupMode, matchLineup, matchFormation, matchStatsLookup]);

  const legend = (
    <div className="flex flex-wrap justify-center gap-3 border-t border-white/8 bg-black/25 px-4 py-2.5">
      {formationLabel ? (
        <span className="text-[10px] font-semibold text-neon-green/90">
          Titulares · {formationLabel}
        </span>
      ) : null}
      {sections.map((s) => (
        <span key={s.position} className="flex items-center gap-1.5 text-[10px] text-slate-400">
          <span
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: s.color, boxShadow: `0 0 6px ${s.color}` }}
          />
          {s.role.replace(/:$/, "")} ({s.count})
        </span>
      ))}
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-stretch">
        <PitchField footer={legend}>
          {fieldPlayers.map((player, i) => (
            <div
              key={`${player.name}-${player.number}`}
              className="absolute z-10 overflow-visible -translate-x-1/2 -translate-y-1/2"
              style={{ left: `${player.x}%`, top: `${player.y}%` }}
            >
              <PlayerPitchToken
                player={player}
                teamName={squad.team}
                teamColor={teamColor}
                positionColor={
                  POSITION_COLOR[player.position] ??
                  POSITION_COLOR[player.line?.toUpperCase() ?? ""] ??
                  "#64748b"
                }
                index={i}
                compact
                matchStatsLookup={matchStatsLookup}
              />
            </div>
          ))}
        </PitchField>

        {reservePlayers.length > 0 ? (
          <ReserveBenchPanel
            players={reservePlayers}
            teamName={squad.team}
            teamColor={teamColor}
            matchStatsLookup={matchStatsLookup}
          />
        ) : null}
      </div>
    </div>
  );
}
