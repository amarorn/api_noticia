import type { LiveRecalibrationEvent } from "@/presentation/utils/liveRecalibration";
import { useElapsedSeconds } from "@/presentation/hooks/useElapsedSeconds";

const REASON_STYLE: Record<
  LiveRecalibrationEvent["reason"],
  { border: string; bg: string; icon: string; title: string }
> = {
  goal: {
    border: "border-neon-green/40",
    bg: "bg-neon-green/[0.08]",
    icon: "⚽",
    title: "Gol — modelo recalibrado",
  },
  halftime: {
    border: "border-sky-500/40",
    bg: "bg-sky-500/[0.08]",
    icon: "⏸",
    title: "Intervalo — 2T recalibrado",
  },
  minute: {
    border: "border-amber-500/35",
    bg: "bg-amber-500/[0.06]",
    icon: "↻",
    title: "Modelo atualizado",
  },
  refresh: {
    border: "border-white/15",
    bg: "bg-white/[0.04]",
    icon: "↻",
    title: "Refresh do palpite",
  },
};

interface LiveRecalibrationBannerProps {
  event: LiveRecalibrationEvent | null;
}

export function LiveRecalibrationBanner({ event }: LiveRecalibrationBannerProps) {
  const elapsed = useElapsedSeconds(Boolean(event));

  if (!event) return null;

  const style = REASON_STYLE[event.reason];
  const fade = elapsed > 22;

  return (
    <div
      className={`flex items-start gap-3 rounded-xl border px-4 py-3 transition-opacity duration-700 ${style.border} ${style.bg} ${
        fade ? "opacity-60" : "opacity-100"
      }`}
      role="status"
      aria-live="polite"
    >
      <span className="mt-0.5 text-lg leading-none" aria-hidden>
        {style.icon}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
          {style.title}
        </p>
        <p className="mt-0.5 text-sm font-semibold text-white">{event.message}</p>
        {event.detail && (
          <p className="mt-1 text-[11px] text-slate-400">{event.detail}</p>
        )}
        {event.maxProbShiftPp >= 3 && event.reason === "goal" && !event.detail && (
          <p className="mt-1 text-[11px] text-neon-green/80">
            Probabilidades 1X2 ajustadas (Δ até {event.maxProbShiftPp.toFixed(1)} pp)
          </p>
        )}
      </div>
      <span className="shrink-0 font-mono text-[10px] text-slate-500">
        {Math.max(0, 28 - elapsed)}s
      </span>
    </div>
  );
}
