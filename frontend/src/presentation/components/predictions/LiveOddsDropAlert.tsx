import { useState } from "react";
import type { OddsDropAlert } from "@/presentation/hooks/useOddsDropMonitor";

interface Props {
  alerts: OddsDropAlert[];
  onDismiss?: (id: string) => void;
}

const SEVERITY_STYLES = {
  critical: {
    border: "border-red-500/40",
    bg: "bg-red-500/10",
    dot: "bg-red-400",
    text: "text-red-300",
    badge: "bg-red-500/20 text-red-300",
    label: "ALERTA",
  },
  warning: {
    border: "border-amber-500/30",
    bg: "bg-amber-500/8",
    dot: "bg-amber-400",
    text: "text-amber-200",
    badge: "bg-amber-500/15 text-amber-300",
    label: "ATENÇÃO",
  },
  info: {
    border: "border-neon-blue/20",
    bg: "bg-neon-blue/5",
    dot: "bg-neon-blue",
    text: "text-slate-300",
    badge: "bg-neon-blue/10 text-neon-blue",
    label: "INFO",
  },
};

function ProbBar({ prev, curr }: { prev: number; curr: number }) {
  const pct = (v: number) => `${Math.round(Math.min(1, Math.max(0, v)) * 100)}%`;
  return (
    <div className="flex items-center gap-2 text-[10px] font-mono">
      <span className="text-slate-500">{pct(prev)}</span>
      <div className="relative h-1.5 w-16 overflow-hidden rounded-full bg-white/10">
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-slate-500/60"
          style={{ width: pct(prev) }}
        />
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-red-400"
          style={{ width: pct(curr) }}
        />
      </div>
      <span className="text-red-300">{pct(curr)}</span>
    </div>
  );
}

export function LiveOddsDropAlert({ alerts, onDismiss }: Props) {
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const visible = alerts.filter((a) => !dismissed.has(a.id));
  if (visible.length === 0) return null;

  const dismiss = (id: string) => {
    setDismissed((prev) => new Set([...prev, id]));
    onDismiss?.(id);
  };

  const hasCritical = visible.some((a) => a.severity === "critical");

  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="flex items-center gap-2">
        <span
          className={`h-2 w-2 rounded-full animate-pulse ${hasCritical ? "bg-red-400" : "bg-amber-400"}`}
        />
        <span className="text-[11px] font-semibold text-slate-300">
          Monitor de Risco
        </span>
        <span className="rounded-full bg-white/8 px-1.5 py-0.5 text-[9px] text-slate-500">
          {visible.length} sinal{visible.length > 1 ? "is" : ""}
        </span>
      </div>

      {visible.map((alert) => {
        const s = SEVERITY_STYLES[alert.severity];
        return (
          <div
            key={alert.id}
            className={`relative rounded-xl border ${s.border} ${s.bg} p-3`}
          >
            <div className="flex items-start gap-2.5">
              {/* Dot */}
              <span className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${s.dot}`} />

              <div className="flex-1 min-w-0">
                {/* Badge + minuto */}
                <div className="mb-1 flex items-center gap-2">
                  <span className={`rounded-md px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide ${s.badge}`}>
                    {s.label}
                  </span>
                  <span className="text-[9px] text-slate-600 font-mono">{alert.minute}&apos;</span>
                </div>

                {/* Mensagem */}
                <p className={`text-[11px] leading-snug ${s.text}`}>{alert.message}</p>

                {/* Barra de queda */}
                {alert.market !== "posture" && (
                  <div className="mt-2">
                    <ProbBar prev={alert.prevProb} curr={alert.currProb} />
                  </div>
                )}
              </div>

              {/* Dismiss */}
              <button
                type="button"
                onClick={() => dismiss(alert.id)}
                className="shrink-0 rounded-md p-1 text-slate-600 transition-colors hover:text-slate-400"
                aria-label="Dispensar alerta"
              >
                ✕
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
