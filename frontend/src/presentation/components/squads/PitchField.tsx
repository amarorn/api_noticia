import type { ReactNode } from "react";

interface PitchFieldProps {
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}

export function PitchField({ children, footer, className = "" }: PitchFieldProps) {
  return (
    <div
      className={`relative min-w-0 flex-1 overflow-visible rounded-2xl border border-neon-green/15 shadow-[inset_0_0_60px_rgba(0,255,136,0.06)] ${className}`}
    >
      <div
        className="relative aspect-[68/105] w-full overflow-visible"
        style={{
          background:
            "linear-gradient(180deg, #0d4a28 0%, #0a3d22 35%, #0a3d22 65%, #0d4a28 100%)",
        }}
      >
        <PitchMarkings />
        {children}
      </div>
      {footer}
    </div>
  );
}

export function PitchMarkings() {
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
