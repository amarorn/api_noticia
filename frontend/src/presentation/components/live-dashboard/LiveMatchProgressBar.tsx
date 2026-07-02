interface LiveMatchProgressBarProps {
  minute: number;
  isLive: boolean;
  /** Duração regulamentar do jogo (90 futebol, 48 NBA). */
  matchMinutes?: number;
}

export function LiveMatchProgressBar({
  minute,
  isLive,
  matchMinutes = 90,
}: LiveMatchProgressBarProps) {
  const pct = Math.min(100, (minute / matchMinutes) * 100);
  const extraTime = minute > matchMinutes;

  return (
    <div className="relative w-full pt-1">
      <div className="live-progress-track">
        <div
          className="live-progress-fill transition-all duration-1000"
          style={{
            width: `${pct}%`,
            background: extraTime
              ? "linear-gradient(90deg, #ff9f43, #ff4d6d)"
              : "linear-gradient(90deg, #00f5a0, #00e0ff)",
          }}
        />
        {isLive && (
          <div className="live-progress-thumb" style={{ left: `${pct}%` }} aria-hidden />
        )}
      </div>
      {isLive && (
        <div
          className="absolute -top-5 -translate-x-1/2"
          style={{ left: `${pct}%` }}
        >
          <span className="whitespace-nowrap rounded-full border border-neon-green/50 bg-surface-100 px-2 py-0.5 text-[9px] font-bold text-neon-green shadow-[0_0_12px_rgba(0,245,160,0.45)]">
            {minute}&apos;{extraTime ? "+" : ""}
          </span>
        </div>
      )}
    </div>
  );
}
