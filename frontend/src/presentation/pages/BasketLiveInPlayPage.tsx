import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { useLiveDashboardChrome } from "@/presentation/components/layout/liveDashboardChromeContext";
import { BasketGameLivePanel } from "@/presentation/components/basket/BasketGameLivePanel";
import {
  BASKET_LIVE_POLL_MS,
  formatCapturedAt,
} from "@/presentation/components/basket/basketLiveWidgets";

export function BasketLiveInPlayPage() {
  const params = useParams<{ eventId: string }>();
  const eventId = Number(params.eventId);
  const enabled = Number.isFinite(eventId) && eventId > 0;
  const { setChrome } = useLiveDashboardChrome();
  const [nextCountdown, setNextCountdown] = useState(Math.round(BASKET_LIVE_POLL_MS / 1000));
  const [meta, setMeta] = useState({
    isFetching: false,
    refetch: () => {},
    capturedAt: null as string | null,
    isLive: false,
  });

  const handleQueryMetaChange = useCallback(
    (next: {
      isFetching: boolean;
      refetch: () => void;
      capturedAt: string | null;
      isLive: boolean;
    }) => {
      setMeta(next);
    },
    [],
  );

  useEffect(() => {
    if (meta.isFetching) return;
    setNextCountdown(Math.round(BASKET_LIVE_POLL_MS / 1000));
  }, [meta.isFetching]);

  useEffect(() => {
    const id = window.setInterval(() => setNextCountdown((c) => Math.max(0, c - 1)), 1000);
    return () => window.clearInterval(id);
  }, []);

  const nextUpdateLabel = useMemo(
    () => `00:${String(nextCountdown).padStart(2, "0")}`,
    [nextCountdown],
  );
  const lastUpdateLabel = formatCapturedAt(meta.capturedAt);

  useEffect(() => {
    setChrome({
      isLive: meta.isLive,
      lastUpdate: lastUpdateLabel,
      nextUpdate: nextUpdateLabel,
      isFetching: meta.isFetching,
      onRefresh: () => meta.refetch(),
    });
    return () => setChrome(null);
  }, [meta.isLive, meta.isFetching, meta.refetch, lastUpdateLabel, nextUpdateLabel, setChrome]);

  if (!enabled) {
    return (
      <PageTransition live className="p-4">
        <p className="text-sm text-red-300">Evento inválido.</p>
      </PageTransition>
    );
  }

  return (
    <PageTransition live className="space-y-0 pb-24">
      <div className="-mx-2 sm:-mx-4">
        <BasketGameLivePanel
          eventId={eventId}
          showCopilot
          stickyHeader
          onQueryMetaChange={handleQueryMetaChange}
        />
      </div>
      <div className="live-glass-panel mx-4 flex items-center justify-center gap-3 px-4 py-3 text-[11px] text-slate-500">
        Atualizando odds de basquete e recalculando spread/total…
      </div>
    </PageTransition>
  );
}
