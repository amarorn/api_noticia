import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import type { BasketSuperbetLiveAdvice, BasketSuperbetLiveEvent } from "@/domain/entities";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { useLiveDashboardChrome } from "@/presentation/components/layout/liveDashboardChromeContext";
import { PageHeader } from "@/presentation/components/layout/PageHeader";
import { BasketGameLivePanel } from "@/presentation/components/basket/BasketGameLivePanel";
import { BasketMultiGameTicketPanel } from "@/presentation/components/predictions/BasketMultiGameTicketPanel";
import {
  BASKET_LIVE_POLL_MS,
  formatCapturedAt,
} from "@/presentation/components/basket/basketLiveWidgets";

function parseEventIds(raw: string | null): number[] {
  if (!raw) return [];
  return [...new Set(raw.split(",").map((part) => Number.parseInt(part.trim(), 10)).filter((id) => id > 0))];
}

export function buildBasketMultiLiveLink(eventIds: number[]): string {
  return `/ao-vivo/basquete/multi?events=${eventIds.join(",")}`;
}

export function BasketMultiLiveInPlayPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const eventIds = useMemo(() => parseEventIds(searchParams.get("events")), [searchParams]);
  const { setChrome } = useLiveDashboardChrome();
  const [adviceByEvent, setAdviceByEvent] = useState<Record<number, BasketSuperbetLiveAdvice>>({});
  const [nextCountdown, setNextCountdown] = useState(Math.round(BASKET_LIVE_POLL_MS / 1000));
  const [isFetchingAny, setIsFetchingAny] = useState(false);

  useEffect(() => {
    if (eventIds.length >= 2) return;
    navigate("/ao-vivo?sport=basketball", { replace: true });
  }, [eventIds.length, navigate]);

  const handleAdviceLoaded = useCallback((data: BasketSuperbetLiveAdvice) => {
    setAdviceByEvent((prev) => ({
      ...prev,
      [data.superbetEventId]: data,
    }));
  }, []);

  const eventsForTicket: BasketSuperbetLiveEvent[] = useMemo(
    () =>
      eventIds.map((eventId) => {
        const advice = adviceByEvent[eventId];
        const scoreParts = (advice?.currentScore ?? "0x0").split(/x/i).map((s) => Number.parseInt(s.trim(), 10) || 0);
        return {
          eventId,
          homeTeam: advice?.homeTeam ?? `Jogo ${eventId}`,
          awayTeam: advice?.awayTeam ?? "…",
          eventName: advice ? `${advice.homeTeam}·${advice.awayTeam}` : String(eventId),
          sportId: advice?.sportId ?? 0,
          tournamentId: null,
          utcDate: advice?.capturedAt,
          betradarId: null,
          minute: advice?.minute ?? 0,
          homeScore: scoreParts[0] ?? 0,
          awayScore: scoreParts[1] ?? 0,
          periodLabel: advice?.periodLabel ?? null,
          status: advice?.status ?? null,
          marketCount: 0,
          h2hOdds: advice?.h2hOdds ?? {},
          capturedAt: advice?.capturedAt ?? new Date().toISOString(),
        };
      }),
    [adviceByEvent, eventIds],
  );

  const liveCount = useMemo(
    () => Object.values(adviceByEvent).filter((a) => a.isLive && !a.isFinished).length,
    [adviceByEvent],
  );

  const latestCapturedAt = useMemo(() => {
    const stamps = Object.values(adviceByEvent)
      .map((a) => a.capturedAt)
      .filter(Boolean) as string[];
    if (stamps.length === 0) return null;
    return stamps.sort()[stamps.length - 1] ?? null;
  }, [adviceByEvent]);

  useEffect(() => {
    if (isFetchingAny) return;
    setNextCountdown(Math.round(BASKET_LIVE_POLL_MS / 1000));
  }, [isFetchingAny]);

  useEffect(() => {
    const id = window.setInterval(() => setNextCountdown((c) => Math.max(0, c - 1)), 1000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    setChrome({
      isLive: liveCount > 0,
      lastUpdate: formatCapturedAt(latestCapturedAt),
      nextUpdate: `00:${String(nextCountdown).padStart(2, "0")}`,
      isFetching: isFetchingAny,
      onRefresh: () => window.location.reload(),
    });
    return () => setChrome(null);
  }, [isFetchingAny, latestCapturedAt, liveCount, nextCountdown, setChrome]);

  if (eventIds.length < 2) {
    return null;
  }

  return (
    <PageTransition live className="space-y-0 pb-24">
      <div className="px-2 sm:px-4">
        <PageHeader
          title="Basquete · painel multi-jogo"
          subtitle={`${eventIds.length} jogos · ${liveCount} ao vivo · métricas operacionais por confronto`}
        >
          <Link
            to="/ao-vivo?sport=basketball"
            className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:text-white"
          >
            Voltar à lista
          </Link>
        </PageHeader>

        <nav className="live-glass-panel mb-4 flex flex-wrap gap-2 p-3">
          {eventIds.map((eventId) => {
            const advice = adviceByEvent[eventId];
            const label = advice
              ? `${advice.homeTeam} × ${advice.awayTeam}`
              : `Jogo #${eventId}`;
            return (
              <a
                key={eventId}
                href={`#basket-game-${eventId}`}
                className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] text-slate-300 hover:border-amber-500/30 hover:text-amber-200"
              >
                {label}
              </a>
            );
          })}
        </nav>

        <BasketMultiGameTicketPanel
          events={eventsForTicket}
          selectedEventIds={eventIds}
          onClearSelection={() => navigate("/ao-vivo?sport=basketball")}
        />

        {eventIds.map((eventId, index) => (
          <BasketGameLivePanel
            key={eventId}
            eventId={eventId}
            collapsible
            defaultExpanded={index === 0}
            stickyHeader={false}
            anchorId={`basket-game-${eventId}`}
            onAdviceLoaded={handleAdviceLoaded}
            onQueryMetaChange={(meta) => {
              if (meta.isFetching) setIsFetchingAny(true);
              else setIsFetchingAny(false);
            }}
          />
        ))}
      </div>
    </PageTransition>
  );
}
