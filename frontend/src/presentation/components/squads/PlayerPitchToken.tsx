import { motion } from "framer-motion";
import { resolvePlayerPortrait, shortPlayerName } from "@/presentation/utils/playerPortrait";

export interface PitchPlayer {
  name: string;
  club: string | null;
  number: number;
  position: string;
}

interface PlayerPitchTokenProps {
  player: PitchPlayer;
  teamName: string;
  teamColor: string;
  positionColor: string;
  index?: number;
  compact?: boolean;
}

export function PlayerPitchToken({
  player,
  teamName,
  teamColor,
  positionColor,
  index = 0,
  compact = false,
}: PlayerPitchTokenProps) {
  const portrait = resolvePlayerPortrait(player.name, teamName);
  const size = compact ? 40 : 52;
  const displayName = shortPlayerName(player.name);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.85, y: 8 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.04, 0.5), duration: 0.25 }}
      className="flex flex-col items-center gap-1"
      style={{ width: compact ? 56 : 72 }}
      title={`${player.number} — ${player.name}${player.club ? ` (${player.club})` : ""}`}
    >
      <div className="relative" style={{ width: size, height: size }}>
        <div
          className="absolute inset-0 rounded-full p-[2px]"
          style={{
            background: `linear-gradient(135deg, ${positionColor}, ${teamColor})`,
            boxShadow: `0 4px 16px ${positionColor}35`,
          }}
        >
          <div className="relative h-full w-full overflow-hidden rounded-full bg-surface">
            <img
              src={portrait}
              alt={player.name}
              className="h-full w-full object-cover object-top"
              loading="lazy"
              draggable={false}
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/50 via-transparent to-transparent" />
          </div>
        </div>

        <span
          className="absolute -left-1 -top-1 flex h-5 min-w-[20px] items-center justify-center rounded-md px-1 text-[9px] font-black shadow-md"
          style={{ backgroundColor: teamColor, color: "#0a0f1a" }}
        >
          {player.number}
        </span>
      </div>

      <p className="max-w-full truncate text-center text-[9px] font-bold leading-tight text-white">
        {displayName}
      </p>
      {!compact && player.club && (
        <p className="max-w-full truncate text-center text-[8px] text-slate-500">{player.club}</p>
      )}
    </motion.div>
  );
}
