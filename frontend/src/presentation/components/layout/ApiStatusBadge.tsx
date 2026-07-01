import { useDataPulse } from "@/infrastructure/api/dataPulseStore";
import type { HealthStatus } from "@/domain/entities";

interface ApiStatusBadgeProps {
  health: HealthStatus | undefined;
  isPending: boolean;
  isError: boolean;
  compact?: boolean;
}

export function ApiStatusBadge({
  health,
  isPending,
  isError,
  compact = false,
}: ApiStatusBadgeProps) {
  const pulse = useDataPulse();
  const articlesSilver = pulse?.articlesSilver ?? health?.articlesSilver;
  const hasSignal = pulse != null || health != null;

  if (isPending && !hasSignal) {
    return (
      <div
        className="flex items-center gap-2 text-xs"
        role="status"
        aria-live="polite"
      >
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-600" />
        <span className="font-mono text-slate-500">{!compact && "Connecting..."}</span>
      </div>
    );
  }

  if (isError || !hasSignal) {
    return (
      <div
        className="flex items-center gap-2 rounded-xl px-3 py-1.5 text-xs"
        role="status"
        title="Inicie a API na porta 8000"
        style={{
          border: "1px solid rgba(255, 159, 67, 0.25)",
          background: "rgba(255, 159, 67, 0.05)",
          color: "#ff9f43",
        }}
      >
        <span className="h-1.5 w-1.5 rounded-full" style={{ background: "#ff9f43" }} aria-hidden />
        <span className="font-mono font-semibold">{compact ? "OFFLINE" : "API OFFLINE"}</span>
      </div>
    );
  }

  return (
    <div
      className="flex items-center gap-2 rounded-xl px-3 py-1.5 text-xs"
      role="status"
      style={{
        border: "1px solid rgba(0, 245, 160, 0.15)",
        background: "rgba(0, 245, 160, 0.04)",
      }}
    >
      <span className="relative flex h-2 w-2 items-center justify-center" aria-hidden>
        <span
          className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-75"
          style={{ background: "rgba(0, 245, 160, 0.50)" }}
        />
        <span className="relative inline-flex h-1.5 w-1.5 rounded-full" style={{ background: "#00f5a0" }} />
      </span>
      <span className="font-mono font-semibold text-neon-green">ONLINE</span>
      {!compact && (
        <>
          <span className="font-mono text-[10px]" style={{ color: "rgba(148, 163, 184, 0.30)" }} aria-hidden>
            ::
          </span>
          <span className="font-mono text-[11px] text-slate-400">
            {typeof articlesSilver === "number" ? articlesSilver.toLocaleString("pt-BR") : 0}
          </span>
        </>
      )}
    </div>
  );
}
