import { useMemo, useState } from "react";
import { Link, useLocation, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  getNewsCardsUseCase,
  getWcScheduleUseCase,
  predictWcCornersUseCase,
} from "@/application/container";
import type { WcPrediction } from "@/domain/entities";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import {
  ModelBreakdownChart,
  ProbabilityDonut,
} from "@/presentation/components/charts/ProbabilityCharts";
import { ConfidenceBadge, ConfidenceBar } from "@/presentation/components/predictions/ConfidenceBadge";
import { MatchContextPanel } from "@/presentation/components/predictions/MatchContextPanel";
import { CornersPredictionPanel } from "@/presentation/components/predictions/CornersPredictionPanel";
import { BetAdvicePanel } from "@/presentation/components/predictions/BetAdvicePanel";
import { InPlayPanel } from "@/presentation/components/predictions/InPlayPanel";
import { MonteCarloPanel } from "@/presentation/components/predictions/MonteCarloPanel";
import { PoissonFactorsPanel } from "@/presentation/components/predictions/PoissonFactorsPanel";
import { SofascoreFeptPanel } from "@/presentation/components/predictions/SofascoreFeptPanel";
import { SofascoreToggle } from "@/presentation/components/predictions/SofascoreToggle";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { SlowLoadingPanel } from "@/presentation/components/ui/SlowLoadingPanel";
import { NewsArticleCard } from "@/presentation/components/news/NewsArticleCard";
import { EmptyState, ErrorState } from "@/presentation/components/ui/EmptyState";
import { IconArrowLeft } from "@/presentation/components/ui/Icons";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";
import { formatPercent, outcomeColors } from "@/presentation/theme";
import { findMatchInSchedule, kickoffDateFromIso } from "@/presentation/utils/sofascore";
import { predictWithOptionalSofascore } from "@/presentation/utils/sofascorePredict";

export function MatchDetailPage({
  routeHomeKey = "home",
  routeAwayKey = "away",
}: {
  routeHomeKey?: string;
  routeAwayKey?: string;
} = {}) {
  const params = useParams<Record<string, string | undefined>>();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const sofascoreFromUrl = searchParams.get("sofascore") === "1";
  const friendlyFromUrl = searchParams.get("source") === "friendly";
  const phaseFromUrl = searchParams.get("phase");
  const liveHomeScore = Number.parseInt(searchParams.get("liveHome") ?? "", 10);
  const liveAwayScore = Number.parseInt(searchParams.get("liveAway") ?? "", 10);
  const liveMinute = Number.parseInt(searchParams.get("minute") ?? "", 10);
  const superbetEventId = Number.parseInt(searchParams.get("superbet") ?? "", 10);
  const statePrediction = !sofascoreFromUrl
    ? (location.state as { prediction?: WcPrediction } | null)?.prediction
    : undefined;

  const homeTeam = decodeURIComponent(params[routeHomeKey] ?? params.home ?? "");
  const awayTeam = decodeURIComponent(params[routeAwayKey] ?? params.away ?? "");

  const [useSofascore, setUseSofascore] = useState(sofascoreFromUrl);
  const [sofascoreEventIdInput, setSofascoreEventIdInput] = useState("");

  const scheduleQuery = useQuery({
    queryKey: ["wc-schedule"],
    queryFn: () => getWcScheduleUseCase.execute(),
    staleTime: 10 * 60_000,
  });

  const scheduleMatch = useMemo(
    () =>
      scheduleQuery.data
        ? findMatchInSchedule(scheduleQuery.data, homeTeam, awayTeam)
        : undefined,
    [scheduleQuery.data, homeTeam, awayTeam],
  );

  const matchPhase = useMemo(() => {
    if (scheduleMatch?.phase) return scheduleMatch.phase;
    if (phaseFromUrl) return phaseFromUrl;
    if (friendlyFromUrl || (scheduleQuery.isSuccess && !scheduleMatch)) return "friendly";
    return "group";
  }, [scheduleMatch, phaseFromUrl, friendlyFromUrl, scheduleQuery.isSuccess]);

  const inPlayDefaults = useMemo(
    () => ({
      homeScore: Number.isFinite(liveHomeScore) ? liveHomeScore : 0,
      awayScore: Number.isFinite(liveAwayScore) ? liveAwayScore : 0,
      minute: Number.isFinite(liveMinute) ? liveMinute : 0,
    }),
    [liveHomeScore, liveAwayScore, liveMinute],
  );

  const manualSofascoreEventId = useMemo(() => {
    const parsed = Number.parseInt(sofascoreEventIdInput, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
  }, [sofascoreEventIdInput]);

  const kickoffDate = kickoffDateFromIso(scheduleMatch?.kickoff);
  const canResolveSofascore =
    manualSofascoreEventId != null || kickoffDate != null;

  const query = useQuery({
    queryKey: [
      "wc-match",
      homeTeam,
      awayTeam,
      matchPhase,
      useSofascore,
      manualSofascoreEventId,
      kickoffDate,
    ],
    queryFn: () =>
      predictWithOptionalSofascore({
        homeTeam,
        awayTeam,
        phase: matchPhase,
        useSofascore,
        manualEventId: manualSofascoreEventId,
        kickoffDate,
      }),
    enabled:
      !!homeTeam &&
      !!awayTeam &&
      (!useSofascore || canResolveSofascore),
    initialData: statePrediction,
    staleTime: useSofascore ? 0 : 5 * 60_000,
  });

  const cornersQuery = useQuery({
    queryKey: ["wc-corners", homeTeam, awayTeam, scheduleMatch?.phase],
    queryFn: () =>
      predictWcCornersUseCase.execute({
        homeTeam,
        awayTeam,
        phase: scheduleMatch?.phase ?? "group",
      }),
    enabled: !!homeTeam && !!awayTeam,
    staleTime: 5 * 60_000,
  });

  const newsQuery = useQuery({
    queryKey: ["news-cards", homeTeam, awayTeam],
    queryFn: () =>
      getNewsCardsUseCase.execute({
        homeTeam,
        awayTeam,
        limit: 6,
        days: 14,
      }),
    enabled: !!homeTeam && !!awayTeam,
    staleTime: 60_000,
  });

  const needsSofascoreResolution = useSofascore && !canResolveSofascore;
  const awaitingPrediction =
    !query.data &&
    (query.isLoading ||
      query.isFetching ||
      (needsSofascoreResolution && scheduleQuery.isLoading));

  if (awaitingPrediction) {
    return (
      <PageTransition>
        <SlowLoadingPanel
          active
          title={`Analisando ${homeTeam} x ${awayTeam}…`}
          hint={
            useSofascore
              ? "Buscando escalação no Sofascore e montando palpite com FEPT."
              : "Montando palpite completo com breakdown dos modelos."
          }
        />
        <DashboardSkeleton />
      </PageTransition>
    );
  }

  if (query.isError) {
    return (
      <PageTransition>
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm text-slate-400 transition-colors hover:text-white"
        >
          <IconArrowLeft className="h-4 w-4" />
          Voltar aos palpites
        </Link>
        <ErrorState
          message={
            query.error instanceof Error ? query.error.message : "Jogo não encontrado"
          }
          onRetry={() => query.refetch()}
        />
        <InPlayPanel
          homeTeam={homeTeam}
          awayTeam={awayTeam}
          phase={matchPhase}
          initialHomeScore={inPlayDefaults.homeScore}
          initialAwayScore={inPlayDefaults.awayScore}
          initialMinute={inPlayDefaults.minute}
          superbetEventId={
            Number.isFinite(superbetEventId) && superbetEventId > 0
              ? superbetEventId
              : undefined
          }
        />
        <BetAdvicePanel
          homeTeam={homeTeam}
          awayTeam={awayTeam}
          phase={matchPhase}
          superbetEventId={
            Number.isFinite(superbetEventId) && superbetEventId > 0
              ? superbetEventId
              : undefined
          }
        />
      </PageTransition>
    );
  }

  if (!query.data) {
    return (
      <PageTransition>
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm text-slate-400 transition-colors hover:text-white"
        >
          <IconArrowLeft className="h-4 w-4" />
          Voltar aos palpites
        </Link>
        <SofascoreToggle
          enabled={useSofascore}
          onChange={setUseSofascore}
          eventId={sofascoreEventIdInput}
          onEventIdChange={setSofascoreEventIdInput}
          hint={
            kickoffDate
              ? `Busca automática pela data ${kickoffDate}`
              : "Informe o ID do evento ou aguarde a tabela oficial carregar"
          }
        />
        <p className="rounded-xl border border-amber-500/20 bg-amber-500/8 px-3 py-2 text-xs text-amber-400">
          Não foi possível obter a data deste jogo na tabela oficial. Informe o ID do evento
          Sofascore manualmente.
        </p>
      </PageTransition>
    );
  }

  const pred = query.data;
  const winnerColor = outcomeColors[pred.prediction];

  return (
    <PageTransition>
      <Link
        to="/"
        className="inline-flex items-center gap-2 text-sm text-slate-400 transition-colors hover:text-white"
      >
        <IconArrowLeft className="h-4 w-4" />
        Voltar aos palpites
      </Link>

      <SofascoreToggle
        enabled={useSofascore}
        onChange={setUseSofascore}
        eventId={sofascoreEventIdInput}
        onEventIdChange={setSofascoreEventIdInput}
        hint={
          kickoffDate
            ? `Busca automática pela data ${kickoffDate}`
            : "Informe o ID do evento ou aguarde a tabela oficial carregar"
        }
      />

      {useSofascore && !canResolveSofascore && (
        <p className="rounded-xl border border-amber-500/20 bg-amber-500/8 px-3 py-2 text-xs text-amber-400">
          Não foi possível obter a data deste jogo na tabela oficial. Informe o ID do evento
          Sofascore manualmente.
        </p>
      )}

      {query.isFetching && query.data && (
        <p className="text-xs text-slate-500">Atualizando palpite…</p>
      )}

      {/* Match hero */}
      <div
        className="live-scoreboard glow-border relative overflow-hidden rounded-2xl"
        style={{ borderColor: `${winnerColor}40` }}
      >
        <img
          src="/images/match-duel-banner.png"
          alt=""
          aria-hidden="true"
          className="absolute inset-0 h-full w-full object-cover object-center opacity-[0.12]"
          draggable={false}
        />
        <div
          className="absolute inset-0 opacity-20"
          style={{ background: `radial-gradient(ellipse at top right, ${winnerColor}, transparent 60%)` }}
        />
        <div className="relative flex flex-wrap items-center justify-between gap-6 px-6 py-6 sm:px-8">
          <div className="flex items-center gap-4">
            <TeamHeroAvatar name={pred.homeTeam} />
            <div>
              <p className="text-[11px] uppercase tracking-widest text-slate-500">Mandante</p>
              <p className="text-xl font-extrabold text-white">{pred.homeTeam}</p>
              <p className="text-sm font-semibold" style={{ color: outcomeColors["1"] }}>
                {formatPercent(pred.probHome)}
              </p>
            </div>
          </div>

          <div className="flex flex-col items-center gap-1">
            <div
              className="rounded-xl px-4 py-2 text-center"
              style={{ backgroundColor: `${winnerColor}12`, border: `1px solid ${winnerColor}25` }}
            >
              <p className="text-[10px] uppercase tracking-widest text-slate-500">Palpite</p>
              <p className="text-2xl font-black" style={{ color: winnerColor }}>
                {pred.prediction}
              </p>
            </div>
            <p className="text-[11px] text-slate-500">
              {formatPercent(pred.probDraw)} empate
            </p>
          </div>

          <div className="flex items-center gap-4 text-right">
            <div>
              <p className="text-[11px] uppercase tracking-widest text-slate-500">Visitante</p>
              <p className="text-xl font-extrabold text-white">{pred.awayTeam}</p>
              <p className="text-sm font-semibold" style={{ color: outcomeColors["2"] }}>
                {formatPercent(pred.probAway)}
              </p>
            </div>
            <TeamHeroAvatar name={pred.awayTeam} />
          </div>
        </div>

        <div className="border-t border-white/[0.05] px-6 py-3 sm:px-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <p className="text-xs text-slate-500">{pred.h2hSummary}</p>
            <ConfidenceBadge confidence={pred.confidence} prediction={pred.prediction} />
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="glass-card p-4">
          <ProbabilityDonut
            probHome={pred.probHome}
            probDraw={pred.probDraw}
            probAway={pred.probAway}
            prediction={pred.prediction}
            height={260}
          />
        </div>
        <div className="glass-card p-4">
          <ModelBreakdownChart
            dixonColes={pred.modelBreakdown.dixonColes}
            logistic={pred.modelBreakdown.logistic}
            height={260}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <MetricCard title="Placar provável" value={pred.poissonScore} accent="green" />
        <MetricCard title="Gols esperados" value={pred.expectedGoals} accent="blue" />
        <MetricCard
          title="Escanteios esp."
          value={cornersQuery.data?.expectedCorners ?? "…"}
          accent="amber"
        />
        <MetricCard title="Prob. casa" value={formatPercent(pred.probHome)} accent="green" />
        <MetricCard title="Prob. fora" value={formatPercent(pred.probAway)} accent="purple" />
      </div>

      {cornersQuery.isLoading && (
        <p className="text-xs text-slate-500">Calculando escanteios…</p>
      )}
      {cornersQuery.isError && (
        <p className="rounded-xl border border-amber-500/20 bg-amber-500/8 px-3 py-2 text-xs text-amber-400">
          Não foi possível carregar a previsão de escanteios.
        </p>
      )}
      {cornersQuery.data && <CornersPredictionPanel prediction={cornersQuery.data} />}

      <div className="glass-card p-5 space-y-4">
        <ConfidenceBar confidence={pred.confidence} />
        <div className="grid gap-3 sm:grid-cols-3">
          <EnsembleCard label="Peso Dixon-Coles" value={pred.modelBreakdown.ensembleWeights.dixonColes} />
          <EnsembleCard label="Peso Logística" value={pred.modelBreakdown.ensembleWeights.logistic} />
          <EnsembleCard label="Holdout 2022" value={pred.modelBreakdown.holdout2022Accuracy ?? 0} />
        </div>
      </div>

      {pred.modelBreakdown.poissonFactors && (
        <PoissonFactorsPanel
          factors={pred.modelBreakdown.poissonFactors}
          homeTeam={pred.homeTeam}
          awayTeam={pred.awayTeam}
        />
      )}

      {pred.modelBreakdown.monteCarlo && (
        <MonteCarloPanel simulation={pred.modelBreakdown.monteCarlo} />
      )}

      <InPlayPanel
        homeTeam={pred.homeTeam}
        awayTeam={pred.awayTeam}
        phase={matchPhase}
        initialHomeScore={inPlayDefaults.homeScore}
        initialAwayScore={inPlayDefaults.awayScore}
        initialMinute={inPlayDefaults.minute}
        superbetEventId={
          Number.isFinite(superbetEventId) && superbetEventId > 0
            ? superbetEventId
            : undefined
        }
      />

      <BetAdvicePanel
        homeTeam={pred.homeTeam}
        awayTeam={pred.awayTeam}
        phase={matchPhase}
        superbetEventId={
          Number.isFinite(superbetEventId) && superbetEventId > 0
            ? superbetEventId
            : undefined
        }
      />

      <SofascoreFeptPanel fept={pred.modelBreakdown.kxlFept} />

      <div className="glass-card p-5">
        <p className="section-label">Contexto pré-jogo</p>
        <MatchContextPanel prediction={pred} />
      </div>

      <section className="space-y-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <p className="section-label">Notícias do confronto</p>
            <h2 className="text-lg font-semibold text-white">
              Cobertura recente
            </h2>
          </div>
          {newsQuery.data && newsQuery.data.total > 0 && (
            <span className="text-xs text-slate-500">
              {newsQuery.data.total} no lake (14 dias)
            </span>
          )}
        </div>

        {newsQuery.isLoading && (
          <p className="text-sm text-slate-500">Carregando notícias…</p>
        )}

        {newsQuery.isError && (
          <p className="text-sm text-slate-500">
            Não foi possível carregar notícias para este jogo.
          </p>
        )}

        {newsQuery.data && newsQuery.data.cards.length === 0 && !newsQuery.isLoading && (
          <EmptyState
            title="Sem notícias recentes"
            description={`Nenhuma matéria nos últimos 14 dias citando ${homeTeam} ou ${awayTeam}.`}
          />
        )}

        {newsQuery.data && newsQuery.data.cards.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {newsQuery.data.cards.map((article, index) => (
              <NewsArticleCard key={article.id} article={article} index={index} />
            ))}
          </div>
        )}
      </section>
    </PageTransition>
  );
}

function TeamHeroAvatar({ name }: { name: string }) {
  return <TeamFlag team={name} size={56} rounded="md" />;
}

function MetricCard({
  title,
  value,
  accent,
}: {
  title: string;
  value: string;
  accent: "green" | "blue" | "purple" | "amber";
}) {
  const colorMap = {
    green: "text-neon-green border-neon-green/15 bg-neon-green/4",
    blue: "text-neon-blue border-neon-blue/15 bg-neon-blue/4",
    purple: "text-neon-purple border-neon-purple/15 bg-neon-purple/4",
    amber: "text-amber-300 border-amber-500/15 bg-amber-500/4",
  };

  return (
    <div className={`rounded-xl border p-4 ${colorMap[accent]}`}>
      <p className="text-[11px] uppercase tracking-wider text-slate-500">{title}</p>
      <p className={`mt-1 text-xl font-bold ${colorMap[accent].split(" ")[0]}`}>{value}</p>
    </div>
  );
}

function EnsembleCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl bg-white/[0.03] p-4 text-center">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-white">{formatPercent(value)}</p>
    </div>
  );
}
