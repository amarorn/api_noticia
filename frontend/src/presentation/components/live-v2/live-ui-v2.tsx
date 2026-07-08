import type { ReactNode } from "react";

export type ToneV2 = "green" | "amber" | "red" | "cyan" | "slate";

const PILL_TONE: Record<ToneV2, string> = {
  green: "bg-emerald-400 text-slate-950",
  amber: "bg-amber-300 text-slate-950",
  red: "bg-red-400 text-white",
  cyan: "bg-cyan-300 text-slate-950",
  slate: "bg-slate-500 text-white",
};

export function StatusPillV2({ label, tone }: { label: string; tone: ToneV2 }) {
  return <span className={`pill-v2 ${PILL_TONE[tone]}`}>{label}</span>;
}

const CHIP_TONE: Record<ToneV2, string> = {
  green: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  amber: "border-amber-400/30 bg-amber-400/10 text-amber-200",
  red: "border-red-400/30 bg-red-400/10 text-red-200",
  cyan: "border-cyan-300/30 bg-cyan-400/10 text-cyan-200",
  slate: "chip-v2",
};

export function ChipV2({ label, tone = "slate", icon }: { label: string; tone?: ToneV2; icon?: ReactNode }) {
  return (
    <span className={`chip-v2 ${tone === "slate" ? "" : CHIP_TONE[tone]}`}>
      {icon}
      {label}
    </span>
  );
}

export function MiniBarV2({ pct, tone = "cyan" }: { pct: number; tone?: ToneV2 }) {
  const fillTone: Record<ToneV2, string> = {
    green: "linear-gradient(90deg, rgba(16,185,129,0.9), rgba(45,212,191,0.65))",
    amber: "linear-gradient(90deg, rgba(251,191,36,0.9), rgba(251,146,60,0.65))",
    red: "linear-gradient(90deg, rgba(248,113,113,0.9), rgba(239,68,68,0.65))",
    cyan: "linear-gradient(90deg, rgba(20,184,166,0.9), rgba(45,212,191,0.65))",
    slate: "linear-gradient(90deg, rgba(148,163,184,0.9), rgba(100,116,139,0.65))",
  };
  return (
    <div className="bar-track-v2" title={`${pct}%`}>
      <div
        className="bar-fill-v2"
        style={{ width: `${Math.max(0, Math.min(100, pct))}%`, background: fillTone[tone] }}
      />
    </div>
  );
}

const GAUGE_COLOR: Record<ToneV2, string> = {
  green: "#10b981",
  amber: "#fbbf24",
  red: "#f87171",
  cyan: "#22d3ee",
  slate: "#94a3b8",
};

export function RadialGaugeV2({
  pct,
  label,
  sublabel,
  tone = "cyan",
}: {
  pct: number;
  label: string;
  sublabel?: string;
  tone?: ToneV2;
}) {
  const clamped = Math.max(0, Math.min(100, pct));
  const color = GAUGE_COLOR[tone];
  return (
    <div
      className="gauge-v2"
      style={{ background: `conic-gradient(${color} ${clamped * 3.6}deg, rgba(148,163,184,0.14) 0deg)` }}
    >
      <div className="gauge-v2-inner">
        <span>{label}</span>
        {sublabel && <span className="gauge-v2-label">{sublabel}</span>}
      </div>
    </div>
  );
}

export function ScoreShieldV2({
  score,
  status,
}: {
  score: number;
  status: "Excelente" | "Boa" | "Atenção" | "Fraca" | "Crítica";
}) {
  const tone = status === "Excelente" || status === "Boa" ? "green" : status === "Atenção" ? "amber" : "red";
  return (
    <div className={`score-shield-v2 ${tone === "green" ? "score-shield-v2--green" : tone === "red" ? "score-shield-v2--red" : ""}`}>
      <span className="text-3xl font-black text-white">{score}</span>
      <span className="mt-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-200">{status}</span>
    </div>
  );
}

export function SectionTitleV2({ title, icon, right }: { title: string; icon?: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <div className="flex items-center gap-1.5">
        {icon && <span className="text-slate-400">{icon}</span>}
        <h2 className="text-xs font-black uppercase tracking-widest text-slate-400">{title}</h2>
      </div>
      {right}
    </div>
  );
}
