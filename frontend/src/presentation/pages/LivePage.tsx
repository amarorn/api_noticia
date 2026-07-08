import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getBasketSuperbetLiveUseCase, getSuperbetLiveUseCase } from "@/application/container";
import type { BasketSuperbetLiveEvent, SuperbetLiveEvent } from "@/domain/entities";
import { useDataPulse } from "@/infrastructure/api/dataPulseStore";
import { useAdaptivePollClock } from "@/presentation/hooks/useAdaptivePollClock";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { AppTableShell } from "@/presentation/components/layout/AppTableShell";
import { PageHeader } from "@/presentation/components/layout/PageHeader";
import { SuperbetPulseBadge } from "@/presentation/components/layout/SuperbetPulseBadge";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { FilterBar, FilterChip } from "@/presentation/components/ui/FilterBar";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";
import { IconChevronRight } from "@/presentation/components/ui/Icons";
import { resolveAdaptiveLivePollMs } from "@/presentation/utils/adaptiveLivePoll";
import { buildInPlayLink } from "@/presentation/utils/matchSuperbetEvent";
import { formatScheduleDate, formatScheduleTime } from "@/presentation/utils/sofascore";

type SportFilter = "football" | "esport_fifa" | "basketball" | "all";
type TierFilter = "all" | "bettable" | "top" | "good" | "watch";

function matchesTierFilter(tier: SuperbetLiveEvent["betTier"], filter: TierFilter): boolean {
  const resolved = tier ?? "skip";
  switch (filter) {
    case "all":
      return true;
    case "bettable":
      return resolved === "top" || resolved === "good";
    case "top":
      return resolved === "top";
    case "good":
      return resolved === "good";
    case "watch":
      return resolved === "watch";
    default:
      return true;
  }
}

function formatOdds(odds: Record<string, number>): string | null {
  const parts: string[] = [];
  if (odds["1"]) parts.push(`1 ${odds["1"].toFixed(2)}`);
  if (odds["X"]) parts.push(`X ${odds["X"].toFixed(2)}`);
  if (odds["2"]) parts.push(`2 ${odds["2"].toFixed(2)}`);
  return parts.length > 0 ? parts.join(" · ") : null;
}

function minuteLabel(event: SuperbetLiveEvent): string {
  if (event.periodLabel) {
    return `${event.minute}' · ${event.periodLabel}`;
  }
  return event.minute > 0 ? `${event.minute}'` : "Ao vivo";
}

function buildInPlayLinkForEvent(event: SuperbetLiveEvent): string {
  return buildInPlayLink(event.eventId, event.utcDate);
}

function buildV2LinkForEvent(event: SuperbetLiveEvent): string {
  const qs = event.utcDate ? `?kickoff=${encodeURIComponent(event.utcDate)}` : "";
  return `/aovivo-v2/${event.eventId}${qs}`;
}

function buildBasketInPlayLink(event: BasketSuperbetLiveEvent): string {
  return `/ao-vivo/basquete/${event.eventId}`;
}

function formatBasketOdds(odds: Record<string, number>): string | null {
  const parts: string[] = [];
  if (odds["1"]) parts.push(`Casa ${odds["1"].toFixed(2)}`);
  if (odds["2"]) parts.push(`Fora ${odds["2"].toFixed(2)}`);
  return parts.length > 0 ? parts.join(" · ") : null;
}

function basketMinuteLabel(event: BasketSuperbetLiveEvent): string {
  if (event.periodLabel) {
    return `${event.minute}' · ${event.periodLabel}`;
  }
  return event.minute > 0 ? `${event.minute}'` : "Ao vivo";
}

function BasketEventRow({ event }: { event: BasketSuperbetLiveEvent }) {
  const odds = formatBasketOdds(event.h2hOdds);
  const schedule = formatEventSchedule(event.utcDate);

  return (
    <tr
      key={event.eventId}
      className="group border-b border-white/5 transition-colors hover:bg-white/[0.03]"
    >
      <td className="px-4 py-3.5">
        <div className="flex min-w-0 items-center gap-2">
          <TeamFlag team={event.homeTeam} size={28} />
          <span className="truncate font-medium text-white">{event.homeTeam}</span>
          <span className="text-[11px] font-black text-slate-500">×</span>
          <TeamFlag team={event.awayTeam} size={28} />
          <span className="truncate font-medium text-white">{event.awayTeam}</span>
        </div>
        <span className="mt-1 block text-[11px] text-slate-500">
          ID {event.eventId}
          {event.betradarId ? ` · Betradar ${event.betradarId}` : ""}
        </span>
      </td>
      <td className="hidden px-3 py-3.5 text-xs text-slate-400 whitespace-nowrap md:table-cell">
        <span className="block">{schedule.date}</span>
        <span className="block font-semibold text-slate-300">{schedule.time}</span>
      </td>
      <td className="px-4 py-3.5 font-mono text-sm text-white">
        {event.homeScore} × {event.awayScore}
      </td>
      <td className="hidden px-4 py-3.5 sm:table-cell">
        <span className="inline-flex rounded-md bg-amber-500/15 px-2 py-1 text-[11px] font-semibold text-amber-300">
          {basketMinuteLabel(event)}
        </span>
      </td>
      <td className="hidden px-4 py-3.5 text-xs text-slate-400 md:table-cell">{odds ?? "—"}</td>
      <td className="hidden px-4 py-3.5 text-xs text-slate-400 lg:table-cell">
        {event.marketCount > 0 ? event.marketCount : "—"}
      </td>
      <td className="px-4 py-3.5 text-right">
        <Link
          to={buildBasketInPlayLink(event)}
          className="inline-flex items-center gap-1 rounded-lg border border-amber-500/25 bg-amber-500/10 px-2.5 py-1.5 text-[11px] font-medium text-amber-300 hover:border-amber-400/40"
        >
          Abrir painel
          <IconChevronRight className="h-3 w-3" />
        </Link>
      </td>
    </tr>
  );
}

function formatEventSchedule(utcDate: string | null): { date: string; time: string } {
  return {
    date: formatScheduleDate(utcDate),
    time: formatScheduleTime(utcDate),
  };
}

function isNationalTeam(name: string): boolean {
  const known = new Set([
    "Brasil",
    "Argentina",
    "Uruguai",
    "Chile",
    "Colômbia",
    "Equador",
    "Paraguai",
    "Peru",
    "Bolívia",
    "Venezuela",
    "México",
    "EUA",
    "Canadá",
    "Costa Rica",
    "Jamaica",
    "Alemanha",
    "França",
    "Espanha",
    "Itália",
    "Inglaterra",
    "Portugal",
    "Holanda",
    "Bélgica",
    "Croácia",
    "Suíça",
    "Dinamarca",
    "Áustria",
    "Polônia",
    "Sérvia",
    "Turquia",
    "Ucrânia",
    "Escócia",
    "Irlanda",
    "Noruega",
    "Suécia",
    "Japão",
    "Coreia do Sul",
    "Austrália",
    "Arábia Saudita",
    "Irã",
    "Qatar",
    "Egito",
    "Marrocos",
    "Nigéria",
    "Senegal",
    "Gana",
    "Camarões",
    "Costa do Marfim",
    "África do Sul",
    "Tunísia",
    "Argélia",
  ]);
  return known.has(name);
}

const TIER_STYLES: Record<
  NonNullable<SuperbetLiveEvent["betTier"]>,
  { badge: string; row: string }
> = {
  top: {
    badge: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
    row: "border-l-2 border-l-emerald-500/60 bg-emerald-500/[0.04]",
  },
  good: {
    badge: "bg-sky-500/20 text-sky-300 border-sky-500/30",
    row: "border-l-2 border-l-sky-500/40 bg-sky-500/[0.03]",
  },
  watch: {
    badge: "bg-amber-500/15 text-amber-300 border-amber-500/25",
    row: "",
  },
  skip: {
    badge: "bg-slate-500/10 text-slate-400 border-white/10",
    row: "opacity-70",
  },
  blocked: {
    badge: "bg-rose-500/10 text-rose-400 border-rose-500/20",
    row: "opacity-50",
  },
};

function BetTierBadge({ event }: { event: SuperbetLiveEvent }) {
  const tier = event.betTier ?? "skip";
  const style = TIER_STYLES[tier];
  const short =
    tier === "top"
      ? "⭐ TOP"
      : tier === "good"
        ? "✓ Bom"
        : tier === "watch"
          ? "👁 Monitorar"
          : tier === "blocked"
            ? "⛔ Evitar"
            : "—";

  return (
    <div className="flex flex-col gap-1">
      <span
        className={`inline-flex w-fit rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${style.badge}`}
      >
        {short}
      </span>
      {event.betLabel ? (
        <span className="max-w-[220px] text-[11px] leading-snug text-slate-400">{event.betLabel}</span>
      ) : null}
    </div>
  );
}

function TopPickCard({ event }: { event: SuperbetLiveEvent }) {
  return (
    <Link
      to={buildInPlayLinkForEvent(event)}
      className="group flex min-w-[260px] flex-1 flex-col gap-2 rounded-xl border border-emerald-500/25 bg-emerald-500/[0.06] p-4 transition-colors hover:border-emerald-400/40 hover:bg-emerald-500/10"
    >
      <div className="flex items-center gap-2">
        <TeamFlag team={event.homeTeam} size={24} />
        <span className="truncate text-sm font-semibold text-white">{event.homeTeam}</span>
        <span className="font-mono text-xs text-emerald-300">
          {event.homeScore}×{event.awayScore}
        </span>
        <span className="truncate text-sm font-semibold text-white">{event.awayTeam}</span>
        <TeamFlag team={event.awayTeam} size={24} />
      </div>
      <p className="text-xs text-emerald-200/90">{event.betLabel ?? "Melhor oportunidade agora"}</p>
      <span className="text-[11px] text-slate-500">
        {minuteLabel(event)}
        {event.betTopEv != null ? ` · EV +${(event.betTopEv * 100).toFixed(0)}%` : ""}
      </span>
    </Link>
  );
}

function LiveEventRow({ event }: { event: SuperbetLiveEvent }) {
  const odds = formatOdds(event.h2hOdds);
  const tier = event.betTier ?? "skip";
  const rowStyle = TIER_STYLES[tier].row;
  const schedule = formatEventSchedule(event.utcDate);

  return (
    <tr
      key={event.eventId}
      className={`group border-b border-white/5 transition-colors hover:bg-white/[0.03] ${rowStyle}`}
    >
      <td className="hidden px-4 py-3.5 sm:table-cell">
        <BetTierBadge event={event} />
      </td>
      <td className="px-4 py-3.5">
        <div className="flex min-w-0 items-center gap-2">
          <TeamFlag team={event.homeTeam} size={28} />
          <span className="truncate font-medium text-white">{event.homeTeam}</span>
          <span className="text-[11px] font-black text-slate-500">×</span>
          <TeamFlag team={event.awayTeam} size={28} />
          <span className="truncate font-medium text-white">{event.awayTeam}</span>
        </div>
        <span className="mt-1 block text-[11px] text-slate-500">
          ID {event.eventId}
          {event.betradarId ? ` · Betradar ${event.betradarId}` : ""}
        </span>
      </td>
      <td className="hidden px-3 py-3.5 text-xs text-slate-400 whitespace-nowrap md:table-cell">
        <span className="block">{schedule.date}</span>
        <span className="block font-semibold text-slate-300">{schedule.time}</span>
      </td>
      <td className="px-4 py-3.5 font-mono text-sm text-white">
        {event.homeScore} × {event.awayScore}
      </td>
      <td className="hidden px-4 py-3.5 sm:table-cell">
        <span className="inline-flex rounded-md bg-amber-500/15 px-2 py-1 text-[11px] font-semibold text-amber-300">
          {minuteLabel(event)}
        </span>
      </td>
      <td className="hidden px-4 py-3.5 text-xs text-slate-400 md:table-cell">{odds ?? "—"}</td>
      <td className="hidden px-4 py-3.5 text-xs text-slate-400 lg:table-cell">
        {event.marketCount > 0 ? event.marketCount : "—"}
      </td>
      <td className="px-4 py-3.5 text-right">
        <div className="flex flex-col items-end gap-1.5">
          <Link
            to={buildInPlayLinkForEvent(event)}
            className="inline-flex items-center gap-1 rounded-lg border border-amber-500/25 bg-amber-500/10 px-2.5 py-1.5 text-[11px] font-medium text-amber-300 hover:border-amber-400/40"
          >
            Abrir painel
            <IconChevronRight className="h-3 w-3" />
          </Link>
          <Link
            to={buildV2LinkForEvent(event)}
            className="inline-flex items-center gap-1 rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1.5 text-[11px] font-medium text-emerald-300 hover:border-emerald-400/40"
            title="Nova tela ao vivo v2"
          >
            V2
            <IconChevronRight className="h-3 w-3" />
          </Link>
        </div>
      </td>
    </tr>
  );
}

export function LivePage() {
  const [sportFilter, setSportFilter] = useState<SportFilter>("esport_fifa");
  const [nationalOnly, setNationalOnly] = useState(false);
  const [tierFilter, setTierFilter] = useState<TierFilter>("all");
  const pulse = useDataPulse();
  const pollClock = useAdaptivePollClock(true);
  const listPollMs = useMemo(() => {
    void pollClock;
    return resolveAdaptiveLivePollMs(pulse?.superbetLive).list;
  }, [pollClock, pulse]);

  const isBasketball = sportFilter === "basketball";

  const liveQuery = useQuery({
    queryKey: ["superbet-live", sportFilter],
    queryFn: () =>
      getSuperbetLiveUseCase.execute({
        sportId: sportFilter === "football" ? 5 : sportFilter === "esport_fifa" ? 75 : undefined,
        allSports: sportFilter === "all",
        rank: true,
      }),
    enabled: !isBasketball,
    staleTime: 15_000,
    refetchInterval: listPollMs,
  });

  const basketLiveQuery = useQuery({
    queryKey: ["basket-superbet-live"],
    queryFn: () => getBasketSuperbetLiveUseCase.execute({ allSports: false }),
    enabled: isBasketball,
    staleTime: 15_000,
    refetchInterval: listPollMs,
  });

  const baseEvents = useMemo(() => {
    const events = liveQuery.data?.events ?? [];
    if (!nationalOnly) return events;
    return events.filter(
      (event) => isNationalTeam(event.homeTeam) || isNationalTeam(event.awayTeam),
    );
  }, [liveQuery.data?.events, nationalOnly]);

  const tierCounts = useMemo(() => {
    const counts = { all: baseEvents.length, bettable: 0, top: 0, good: 0, watch: 0 };
    for (const event of baseEvents) {
      const tier = event.betTier ?? "skip";
      if (tier === "top") counts.top += 1;
      if (tier === "good") counts.good += 1;
      if (tier === "watch") counts.watch += 1;
      if (tier === "top" || tier === "good") counts.bettable += 1;
    }
    return counts;
  }, [baseEvents]);

  const rows = useMemo(() => {
    const filtered = baseEvents.filter((event) => matchesTierFilter(event.betTier, tierFilter));
    return [...filtered].sort((a, b) => (b.betRankScore ?? 0) - (a.betRankScore ?? 0));
  }, [baseEvents, tierFilter]);

  const topPicks = useMemo(
    () =>
      rows
        .filter((event) => event.betTier === "top" || event.betTier === "good")
        .slice(0, 4),
    [rows],
  );

  const emptyMessage =
    baseEvents.length === 0
      ? "Nenhum jogo ao vivo no momento na Superbet."
      : "Nenhum jogo corresponde aos filtros selecionados.";

  const tierFilterLabel: Record<TierFilter, string> = {
    all: "todos",
    bettable: "para palpitar",
    top: "TOP",
    good: "bom",
    watch: "monitorar",
  };

  return (
    <PageTransition>
      <PageHeader
        title="Ao vivo"
        subtitle="Jogos em andamento na Superbet — ordenados por melhor oportunidade de palpite"
      >
        <SuperbetPulseBadge />
      </PageHeader>

      <section className="mb-6 space-y-4">
        <FilterBar label="Esporte">
          <FilterChip
            active={sportFilter === "football"}
            onClick={() => setSportFilter("football")}
            label="Futebol"
          />
          <FilterChip
            active={sportFilter === "esport_fifa"}
            onClick={() => setSportFilter("esport_fifa")}
            label="E-Sport FIFA"
          />
          <FilterChip
            active={sportFilter === "basketball"}
            onClick={() => setSportFilter("basketball")}
            label="🏀 Basquete"
          />
          <FilterChip
            active={sportFilter === "all"}
            onClick={() => setSportFilter("all")}
            label="Todos os esportes"
          />
          <FilterChip
            active={nationalOnly}
            onClick={() => setNationalOnly((v) => !v)}
            label="Seleções"
          />
        </FilterBar>

        {!isBasketball ? (
          <FilterBar label="Palpite">
            <FilterChip
              active={tierFilter === "all"}
              onClick={() => setTierFilter("all")}
              label="Todos"
              count={tierCounts.all}
            />
            <FilterChip
              active={tierFilter === "bettable"}
              onClick={() => setTierFilter("bettable")}
              label="Para palpitar"
              count={tierCounts.bettable}
            />
            <FilterChip
              active={tierFilter === "top"}
              onClick={() => setTierFilter("top")}
              label="⭐ TOP"
              count={tierCounts.top}
            />
            <FilterChip
              active={tierFilter === "good"}
              onClick={() => setTierFilter("good")}
              label="✓ Bom"
              count={tierCounts.good}
            />
            <FilterChip
              active={tierFilter === "watch"}
              onClick={() => setTierFilter("watch")}
              label="👁 Monitorar"
              count={tierCounts.watch}
            />
          </FilterBar>
        ) : null}
      </section>

      {isBasketball ? (
        basketLiveQuery.isLoading ? (
          <DashboardSkeleton />
        ) : basketLiveQuery.isError ? (
          <ErrorState
            message={
              basketLiveQuery.error instanceof Error
                ? basketLiveQuery.error.message
                : "Falha ao carregar jogos de basquete ao vivo"
            }
            onRetry={() => basketLiveQuery.refetch()}
          />
        ) : (basketLiveQuery.data?.events.length ?? 0) === 0 ? (
          <div className="app-empty-state">
            Nenhum jogo de basquete ao vivo no momento na Superbet.
          </div>
        ) : (
          <AppTableShell
            footer={
              <>
                {basketLiveQuery.data?.events.length ?? 0} jogo(s) exibido(s) · fonte Superbet
                {basketLiveQuery.data?.capturedAt
                  ? ` · atualizado ${new Intl.DateTimeFormat("pt-BR", {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                    }).format(new Date(basketLiveQuery.data.capturedAt))}`
                  : ""}
              </>
            }
          >
            <table className="min-w-full text-sm">
              <thead>
                <tr>
                  <th className="px-4 py-3">Confronto</th>
                  <th className="hidden px-3 py-3 md:table-cell">Data / hora</th>
                  <th className="px-4 py-3">Placar</th>
                  <th className="hidden px-4 py-3 sm:table-cell">Tempo</th>
                  <th className="hidden px-4 py-3 md:table-cell">Odds vencedor</th>
                  <th className="hidden px-4 py-3 lg:table-cell">Mercados</th>
                  <th className="px-4 py-3 text-right">Ação</th>
                </tr>
              </thead>
              <tbody>
                {(basketLiveQuery.data?.events ?? []).map((event) => (
                  <BasketEventRow key={event.eventId} event={event} />
                ))}
              </tbody>
            </table>
          </AppTableShell>
        )
      ) : liveQuery.isLoading ? (
        <DashboardSkeleton />
      ) : liveQuery.isError ? (
        <ErrorState
          message={
            liveQuery.error instanceof Error
              ? liveQuery.error.message
              : "Falha ao carregar jogos ao vivo"
          }
          onRetry={() => liveQuery.refetch()}
        />
      ) : rows.length === 0 ? (
        <div className="app-empty-state">{emptyMessage}</div>
      ) : (
        <>
          {topPicks.length > 0 ? (
            <section className="live-glass-panel mb-6 p-4">
              <h2 className="section-label mb-3">Melhores agora</h2>
              <div className="flex flex-wrap gap-3">
                {topPicks.map((event) => (
                  <TopPickCard key={event.eventId} event={event} />
                ))}
              </div>
            </section>
          ) : null}

          <AppTableShell
            footer={
              <>
                {rows.length} jogo(s) exibido(s)
                {tierFilter !== "all" ? ` · filtro: ${tierFilterLabel[tierFilter]}` : ""}
                {nationalOnly ? " · seleções" : ""}
                {" · "}ordenados por score de palpite · fonte Superbet
                {liveQuery.data?.capturedAt
                  ? ` · atualizado ${new Intl.DateTimeFormat("pt-BR", {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                    }).format(new Date(liveQuery.data.capturedAt))}`
                  : ""}
              </>
            }
          >
            <table className="min-w-full text-sm">
              <thead>
                <tr>
                  <th className="hidden px-4 py-3 sm:table-cell">Palpite</th>
                  <th className="px-4 py-3">Confronto</th>
                  <th className="hidden px-3 py-3 md:table-cell">Data / hora</th>
                  <th className="px-4 py-3">Placar</th>
                  <th className="hidden px-4 py-3 sm:table-cell">Tempo</th>
                  <th className="hidden px-4 py-3 md:table-cell">Odds 1X2</th>
                  <th className="hidden px-4 py-3 lg:table-cell">Mercados</th>
                  <th className="px-4 py-3 text-right">Ação</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((event) => (
                  <LiveEventRow key={event.eventId} event={event} />
                ))}
              </tbody>
            </table>
          </AppTableShell>
        </>
      )}
    </PageTransition>
  );
}
