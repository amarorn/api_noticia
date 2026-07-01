import {
  formatSuperbetCaptureAge,
  useDataPulse,
} from "@/infrastructure/api/dataPulseStore";
import {
  livePollTierLabel,
  resolveAdaptiveLivePollMs,
} from "@/presentation/utils/adaptiveLivePoll";

interface SuperbetPulseBadgeProps {
  eventId?: number;
  compact?: boolean;
  /** Intervalo adaptativo ativo na página (ex.: useLiveAdviceQueries.pollMs). */
  adaptivePollMs?: number;
  adaptivePollTier?: "normal" | "accelerated" | "urgent";
}

export function SuperbetPulseBadge({
  eventId,
  compact = false,
  adaptivePollMs,
  adaptivePollTier,
}: SuperbetPulseBadgeProps) {
  const pulse = useDataPulse();
  const superbet = pulse?.superbetLive;
  const age = formatSuperbetCaptureAge(superbet?.lastCaptureAt ?? null);
  const pollIntervalSec = superbet?.pollIntervalSec ?? 0;
  const pollPlan = resolveAdaptiveLivePollMs(superbet, { eventId });
  const activeTier = adaptivePollTier ?? pollPlan.tier;
  const activeFastMs = adaptivePollMs ?? pollPlan.fast;

  if (!superbet?.lastCaptureAt) {
    return (
      <span
        className="rounded-md border border-slate-600/40 bg-slate-800/40 px-2 py-1 text-slate-400"
        title="Nenhuma captura Superbet registrada nesta sessão da API"
      >
        {compact ? "Odds —" : "Superbet: sem captura"}
      </span>
    );
  }

  const capturedMs = Date.parse(superbet.lastCaptureAt);
  const ageSec = Number.isFinite(capturedMs)
    ? Math.max(0, Math.round((Date.now() - capturedMs) / 1000))
    : null;
  const isOld =
    superbet.stale ||
    activeTier !== "normal" ||
    (ageSec != null && pollIntervalSec > 0 && ageSec > pollIntervalSec * 1.5);

  const matchesEvent =
    eventId != null &&
    superbet.primaryEventId != null &&
    superbet.primaryEventId === eventId;

  const pollHint =
    activeTier !== "normal" ? ` · refresh ${Math.round(activeFastMs / 1000)}s` : "";

  const label = superbet.stale
    ? compact
      ? `Odds cache${pollHint}`
      : `Odds em cache (Superbet indisponível)${pollHint}`
    : compact
      ? `Odds ${age ?? "?"}${pollHint}`
      : `Odds Superbet · ${age ?? "?"} atrás${pollHint}`;

  return (
    <span
      className={`rounded-md border px-2 py-1 ${
        isOld
          ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
          : "border-emerald-500/25 bg-emerald-500/10 text-emerald-300"
      }`}
      title={[
        superbet.stale ? "Última resposta usou fallback stale" : "Última captura HTTP Superbet",
        age ? `há ${age}` : "",
        pollIntervalSec > 0 ? `poll background ~${pollIntervalSec}s` : "",
        activeTier !== "normal" ? livePollTierLabel(activeTier) : "poll normal",
        activeTier !== "normal" ? `frontend refresh ~${Math.round(activeFastMs / 1000)}s` : "",
        superbet.liveEventsCount > 0
          ? `${superbet.liveEventsCount} evento(s) live no registro`
          : "",
        matchesEvent ? "evento primário desta página" : "",
      ]
        .filter(Boolean)
        .join(" · ")}
    >
      {label}
      {!compact && superbet.liveEventsCount > 1 ? ` · ${superbet.liveEventsCount} live` : ""}
    </span>
  );
}
