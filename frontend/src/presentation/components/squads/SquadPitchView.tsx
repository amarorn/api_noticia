import { useMemo } from "react";
import type { WcSquad } from "@/domain/entities";
import { assignSquadNumbers } from "@/presentation/utils/playerPortrait";
import { PlayerPitchToken, type PitchPlayer } from "./PlayerPitchToken";

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

function placeSection(
  players: PitchPlayer[],
  position: string,
  startIndex: number,
): { placed: PlacedPlayer[]; nextIndex: number } {
  const yLines = LINE_Y[position] ?? [50];
  const perRow = Math.ceil(players.length / yLines.length);
  const placed: PlacedPlayer[] = [];
  let idx = 0;

  yLines.forEach((y, rowIdx) => {
    const rowPlayers = players.slice(rowIdx * perRow, (rowIdx + 1) * perRow);
    const xs = distributeRow(rowPlayers.length);
    rowPlayers.forEach((player, i) => {
      placed.push({ ...player, x: xs[i] ?? 50, y });
      idx += 1;
    });
  });

  return { placed, nextIndex: startIndex + idx };
}

interface SquadPitchViewProps {
  squad: WcSquad;
  teamColor: string;
}

export function SquadPitchView({ squad, teamColor }: SquadPitchViewProps) {
  const { placedPlayers, sections } = useMemo(() => {
    const { sections: numbered } = assignSquadNumbers(squad);
    const allPlaced: PlacedPlayer[] = [];
    let animIndex = 0;

    const sectionMeta = numbered.map((section) => {
      const players: PitchPlayer[] = section.players.map((p) => ({
        name: p.name,
        club: p.club,
        number: p.number,
        position: section.position,
      }));

      const { placed, nextIndex } = placeSection(players, section.position, animIndex);
      animIndex = nextIndex;
      allPlaced.push(...placed);

      return {
        position: section.position,
        role: section.role,
        color: POSITION_COLOR[section.position] ?? "#64748b",
        count: players.length,
      };
    });

    return { placedPlayers: allPlaced, sections: sectionMeta };
  }, [squad]);

  return (
    <div className="space-y-4">
      <div className="relative mx-auto w-full max-w-3xl overflow-hidden rounded-2xl border border-neon-green/15 shadow-[inset_0_0_60px_rgba(0,255,136,0.06)]">
        <div
          className="relative aspect-[68/105] w-full"
          style={{
            background:
              "linear-gradient(180deg, #0d4a28 0%, #0a3d22 35%, #0a3d22 65%, #0d4a28 100%)",
          }}
        >
          <PitchMarkings />

          {placedPlayers.map((player, i) => (
            <div
              key={`${player.name}-${player.number}`}
              className="absolute z-10 -translate-x-1/2 -translate-y-1/2"
              style={{ left: `${player.x}%`, top: `${player.y}%` }}
            >
              <PlayerPitchToken
                player={player}
                teamName={squad.team}
                teamColor={teamColor}
                positionColor={POSITION_COLOR[player.position] ?? "#64748b"}
                index={i}
                compact={placedPlayers.length > 18}
              />
            </div>
          ))}
        </div>

        <div className="flex flex-wrap justify-center gap-3 border-t border-white/8 bg-black/25 px-4 py-2.5">
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
      </div>
    </div>
  );
}

function PitchMarkings() {
  return (
    <svg
      className="pointer-events-none absolute inset-0 h-full w-full opacity-35"
      viewBox="0 0 68 105"
      preserveAspectRatio="none"
      aria-hidden
    >
      <rect x="2" y="2" width="64" height="101" fill="none" stroke="white" strokeWidth="0.4" />
      <line x1="34" y1="2" x2="34" y2="103" stroke="white" strokeWidth="0.35" />
      <circle cx="34" cy="52.5" r="9" fill="none" stroke="white" strokeWidth="0.35" />
      <circle cx="34" cy="52.5" r="0.8" fill="white" />
      <rect x="18" y="2" width="32" height="14" fill="none" stroke="white" strokeWidth="0.3" />
      <rect x="18" y="89" width="32" height="14" fill="none" stroke="white" strokeWidth="0.3" />
      {[20, 40, 60, 80].map((y) => (
        <rect key={y} x="0" y={y} width="68" height="10" fill="white" fillOpacity="0.03" />
      ))}
    </svg>
  );
}
