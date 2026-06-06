import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { resolvePlayerPortrait, shortPlayerName } from "@/presentation/utils/playerPortrait";
import {
  buildReserveHoverStats,
  lookupPlayerStats,
  type PlayerMatchStats,
} from "@/presentation/utils/playerMatchStats";
import { PlayerPitchHoverCard } from "./PlayerPitchHoverCard";

export interface PitchPlayer {
  name: string;
  club: string | null;
  number: number;
  position: string;
  line?: string | null;
  sofascoreRating?: number | null;
  isCaptain?: boolean;
  yellowCards?: number;
  redCards?: number;
  isStarter?: boolean;
}

interface PlayerPitchTokenProps {
  player: PitchPlayer;
  teamName: string;
  teamColor: string;
  positionColor: string;
  index?: number;
  compact?: boolean;
  variant?: "pitch" | "bench";
  tooltipPlacement?: "top" | "left";
  matchStatsLookup?: Map<string, PlayerMatchStats>;
}

export function PlayerPitchToken({
  player,
  teamName,
  teamColor,
  positionColor,
  index = 0,
  compact = false,
  variant = "pitch",
  tooltipPlacement = "top",
  matchStatsLookup,
}: PlayerPitchTokenProps) {
  const [hovered, setHovered] = useState(false);
  const portrait = resolvePlayerPortrait(player.name, teamName);
  const isBench = variant === "bench";
  const size = isBench ? 32 : compact ? 40 : 52;
  const displayName = shortPlayerName(player.name);
  const tokenWidth = isBench ? 52 : compact ? 56 : 72;
  const inlineStats: PlayerMatchStats | undefined =
    player.isStarter || player.sofascoreRating != null
      ? {
          name: player.name,
          position: player.position,
          line: player.line ?? null,
          sofascoreRating: player.sofascoreRating ?? null,
          isCaptain: player.isCaptain ?? false,
          yellowCards: player.yellowCards ?? 0,
          redCards: player.redCards ?? 0,
          isStarter: player.isStarter ?? true,
        }
      : undefined;
  const matchStats =
    inlineStats ??
    lookupPlayerStats(player.name, matchStatsLookup) ??
    (isBench || player.isStarter === false ? buildReserveHoverStats(player) : undefined);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.85, y: 8 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.04, 0.5), duration: 0.25 }}
      className={`relative flex flex-col items-center gap-0.5 ${isBench ? "opacity-90" : ""}`}
      style={{ width: tokenWidth }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setHovered(true)}
      onBlur={() => setHovered(false)}
    >
      <div className="relative" style={{ width: size, height: size }}>
        <AnimatePresence>
          {hovered ? (
            <motion.div
              initial={{ opacity: 0, y: tooltipPlacement === "left" ? 0 : -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: tooltipPlacement === "left" ? 0 : -2 }}
              className={`absolute z-30 ${
                tooltipPlacement === "left"
                  ? "right-full top-1/2 mr-2 -translate-y-1/2"
                  : "bottom-full left-1/2 mb-3 -translate-x-1/2"
              }`}
            >
              <PlayerPitchHoverCard
                playerName={player.name}
                club={player.club}
                squadPosition={player.position}
                matchStats={matchStats}
              />
            </motion.div>
          ) : null}
        </AnimatePresence>
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
          className={`absolute -left-1 -top-1 flex items-center justify-center rounded-md font-black shadow-md ${
            isBench ? "h-4 min-w-[16px] px-0.5 text-[9px]" : "h-5 min-w-[20px] px-1 text-[10px]"
          }`}
          style={{ backgroundColor: teamColor, color: "#0a0f1a" }}
        >
          {player.number}
        </span>
        {(matchStats?.yellowCards ?? 0) > 0 ? (
          <span
            className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-sm bg-amber-400 shadow"
            title="Cartão amarelo"
          />
        ) : null}
        {(matchStats?.redCards ?? 0) > 0 ? (
          <span
            className="absolute -right-1 top-3 h-2.5 w-2.5 rounded-sm bg-red-500 shadow"
            title="Cartão vermelho"
          />
        ) : null}
      </div>

      <p
        className={`max-w-full truncate text-center font-bold leading-tight text-white ${
          isBench ? "text-[9px]" : "text-[10px]"
        }`}
      >
        {displayName}
        {matchStats?.sofascoreRating != null ? (
          <span className="ml-0.5 font-mono text-[8px] text-neon-green/90">
            {matchStats.sofascoreRating.toFixed(2)}
          </span>
        ) : null}
      </p>
      {!compact && !isBench && player.club && (
        <p className="max-w-full truncate text-center text-[10px] text-slate-500">{player.club}</p>
      )}
    </motion.div>
  );
}
