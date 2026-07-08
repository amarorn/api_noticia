import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { resolveLiveAdvicePhase } from "@/presentation/utils/liveAdvicePhase";
import { useLiveOperationalData } from "@/presentation/components/live-operational/useLiveOperationalData";
import { LiveDashboardContentV2, type LiveTabV2 } from "@/presentation/components/live-v2/live-dashboard-content-v2";

function numberParam(value: string | null, fallback: number) {
  if (!value) return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

/** A captura "fast" ainda assim pode levar bastante tempo no backend — mostra tempo decorrido em vez de deixar a tela parada. */
function LoadingElapsedV2() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => window.clearInterval(id);
  }, []);
  return (
    <p className="mt-3 text-center text-xs text-slate-500" aria-live="polite">
      Capturando odds e recalculando sinais na Superbet... {seconds}s
    </p>
  );
}

export function LiveOperationalPage() {
  const { eventId: eventIdParam } = useParams();
  const [searchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState<LiveTabV2>("resumo");
  const eventId = Number.parseInt(eventIdParam ?? "", 10);
  const phase = resolveLiveAdvicePhase(searchParams);
  const kickoff = searchParams.get("kickoff");
  const bankroll = numberParam(searchParams.get("bankroll"), 1000);

  const {
    data,
    scoreTick,
    isLoading,
    isAdvicePending,
    isError,
    error,
    isFetching,
    refetch,
    pollMs,
  } = useLiveOperationalData(eventId, bankroll, kickoff, phase);

  if (!Number.isFinite(eventId) || eventId <= 0) {
    return (
      <PageTransition>
        <ErrorState message="ID do evento inválido." />
        <Link to="/ao-vivo" className="mt-4 inline-flex text-sm text-neon-green hover:underline">
          Voltar à lista ao vivo
        </Link>
      </PageTransition>
    );
  }

  if (isLoading) {
    return (
      <PageTransition>
        <DashboardSkeleton />
        <LoadingElapsedV2 />
      </PageTransition>
    );
  }

  if (isError || !data) {
    return (
      <PageTransition>
        <ErrorState
          message={error instanceof Error ? error.message : "Falha ao capturar jogo na Superbet"}
          onRetry={refetch}
        />
      </PageTransition>
    );
  }

  return (
    <PageTransition>
      <LiveDashboardContentV2
        data={data}
        scoreTick={scoreTick}
        eventId={eventId}
        bankroll={bankroll}
        pollFastMs={pollMs.fast}
        isFetching={isFetching}
        isAdvicePending={isAdvicePending}
        onRefresh={refetch}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />
    </PageTransition>
  );
}
