import type { PlayerMatchStats } from "@/presentation/utils/playerMatchStats";
import { PlayerPitchToken, type PitchPlayer } from "./PlayerPitchToken";

const POSITION_COLOR: Record<string, string> = {
  GK: "#fbbf24",
  DEF: "#00d4ff",
  MID: "#00ff88",
  ATK: "#f97316",
  MID_FWD: "#a855f7",
};

interface ReserveBenchPanelProps {
  players: PitchPlayer[];
  teamName: string;
  teamColor: string;
  matchStatsLookup?: Map<string, PlayerMatchStats>;
}

export function ReserveBenchPanel({
  players,
  teamName,
  teamColor,
  matchStatsLookup,
}: ReserveBenchPanelProps) {
  if (players.length === 0) return null;

  return (
    <aside className="relative z-20 flex w-full shrink-0 flex-col overflow-visible rounded-xl border border-white/10 bg-slate-950/80 md:w-36 lg:w-40">
      <div className="border-b border-white/8 px-3 py-2">
        <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
          Banco
        </p>
        <p className="text-[11px] text-slate-500">{players.length} reservas</p>
      </div>
      <div className="flex max-h-[520px] flex-col gap-2 overflow-visible p-2 md:max-h-none">
        {players.map((player, index) => (
          <div key={`${player.name}-${player.number}`} className="relative z-0 hover:z-50">
            <PlayerPitchToken
              player={{ ...player, isStarter: false }}
              teamName={teamName}
              teamColor={teamColor}
              positionColor={POSITION_COLOR[player.position] ?? "#64748b"}
              index={index}
              variant="bench"
              tooltipPlacement="left"
              matchStatsLookup={matchStatsLookup}
            />
          </div>
        ))}
      </div>
    </aside>
  );
}
