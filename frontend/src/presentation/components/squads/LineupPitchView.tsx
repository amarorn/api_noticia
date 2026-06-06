import { useMemo } from "react";
import type { WcSimulationLineupPlayer } from "@/domain/entities";
import { placeStartersOnPitch } from "@/presentation/utils/pitchPlacement";
import { PitchField } from "./PitchField";
import { PlayerPitchToken } from "./PlayerPitchToken";

const LINE_COLOR: Record<string, string> = {
  goleiro: "#fbbf24",
  defesa: "#00d4ff",
  meio: "#00ff88",
  ataque: "#f97316",
};

interface LineupPitchViewProps {
  team: string;
  teamColor: string;
  formation: string | null;
  lineup: WcSimulationLineupPlayer[];
}

export function LineupPitchView({ team, teamColor, formation, lineup }: LineupPitchViewProps) {
  const placed = useMemo(
    () => placeStartersOnPitch(lineup, formation),
    [lineup, formation],
  );

  if (placed.length === 0) return null;

  const footer = formation ? (
    <div className="border-t border-white/8 bg-black/25 px-4 py-2 text-center text-[11px] text-slate-400">
      Esquema {formation} · passe o mouse sobre o jogador para ver nota e cartões
    </div>
  ) : null;

  return (
    <PitchField footer={footer}>
      {placed.map((player, index) => (
        <div
          key={`${player.name}-${player.number}`}
          className="absolute z-10 overflow-visible -translate-x-1/2 -translate-y-1/2"
          style={{ left: `${player.x}%`, top: `${player.y}%` }}
        >
          <PlayerPitchToken
            player={player}
            teamName={team}
            teamColor={teamColor}
            positionColor={LINE_COLOR[player.line ?? "meio"] ?? "#64748b"}
            index={index}
            compact
          />
        </div>
      ))}
    </PitchField>
  );
}
