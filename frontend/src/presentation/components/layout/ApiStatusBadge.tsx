import { IconWifi } from "@/presentation/components/ui/Icons";
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
        className="flex items-center gap-2 text-xs text-slate-500"
        role="status"
        aria-live="polite"
      >
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-600" />
        {!compact && "Conectando…"}
      </div>
    );
  }

  if (isError || !hasSignal) {
    return (
      <div
        className="flex items-center gap-2 rounded-xl border border-amber-500/25 bg-amber-500/8 px-3 py-1.5 text-xs text-amber-300"
        role="status"
        title="Inicie a API na porta 8000"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-amber-400" aria-hidden />
        {compact ? "Offline" : "API offline"}
      </div>
    );
  }

  return (
    <div
      className="flex items-center gap-2 rounded-xl border border-neon-green/20 bg-neon-green/5 px-3 py-1.5 text-xs"
      role="status"
    >
      <IconWifi className="h-3 w-3 shrink-0 text-neon-green" aria-hidden />
      <span className="font-medium text-neon-green">Online</span>
      {!compact && (
        <>
          <span className="text-white/20" aria-hidden>
            |
          </span>
          <span className="text-slate-400">
            {articlesSilver ?? 0} artigos
          </span>
        </>
      )}
    </div>
  );
}
