interface HexBrandMarkProps {
  size?: "sm" | "md";
}

export function HexBrandMark({ size = "md" }: HexBrandMarkProps) {
  const px = size === "sm" ? 34 : 40;

  return (
    <div className="relative shrink-0" style={{ width: px, height: px }}>
      <svg
        viewBox="0 0 44 48"
        width={px}
        height={px}
        className="drop-shadow-[0_0_14px_rgba(0,245,160,0.35)]"
        aria-hidden
      >
        <defs>
          <linearGradient id="hexBrandStroke" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#00f5a0" />
            <stop offset="100%" stopColor="#00e0ff" />
          </linearGradient>
        </defs>
        <path
          d="M22 2 L40 12 V36 L22 46 L4 36 V12 Z"
          fill="rgba(0,245,160,0.06)"
          stroke="url(#hexBrandStroke)"
          strokeWidth="1.5"
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center font-display text-[11px] font-black tracking-tight text-neon-green">
        AI
      </span>
    </div>
  );
}
