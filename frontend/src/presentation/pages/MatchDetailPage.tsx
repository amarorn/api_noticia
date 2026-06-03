import { Link, useLocation, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { predictWcMatchUseCase } from "@/application/container";
import type { WcPrediction } from "@/domain/entities";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import {
  ModelBreakdownChart,
  ProbabilityDonut,
} from "@/presentation/components/charts/ProbabilityCharts";
import { ConfidenceBadge, ConfidenceBar } from "@/presentation/components/predictions/ConfidenceBadge";
import { MatchContextPanel } from "@/presentation/components/predictions/MatchContextPanel";
import { PoissonFactorsPanel } from "@/presentation/components/predictions/PoissonFactorsPanel";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { SlowLoadingPanel } from "@/presentation/components/ui/SlowLoadingPanel";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { IconArrowLeft } from "@/presentation/components/ui/Icons";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";
import { formatPercent, outcomeColors } from "@/presentation/theme";

export function MatchDetailPage() {
  const { home, away } = useParams<{ home: string; away: string }>();
  const location = useLocation();
  const statePrediction = (location.state as { prediction?: WcPrediction } | null)?.prediction;

  const homeTeam = decodeURIComponent(home ?? "");
  const awayTeam = decodeURIComponent(away ?? "");

  const query = useQuery({
    queryKey: ["wc-match", homeTeam, awayTeam],
    queryFn: () =>
      predictWcMatchUseCase.execute({
        homeTeam,
        awayTeam,
        phase: "group",
      }),
    enabled: !!homeTeam && !!awayTeam && !statePrediction,
    initialData: statePrediction,
  });

  if (query.isLoading && !query.data) {
    return (
      <PageTransition>
        <SlowLoadingPanel
          active
          title={`Analisando ${homeTeam} x ${awayTeam}…`}
          hint="Montando palpite completo com breakdown dos modelos."
        />
        <DashboardSkeleton />
      </PageTransition>
    );
  }

  if (query.isError) {
    return (
      <PageTransition>
        <ErrorState
          message={
            query.error instanceof Error ? query.error.message : "Jogo não encontrado"
          }
          onRetry={() => query.refetch()}
        />
      </PageTransition>
    );
  }

  const pred = query.data!;
  const winnerColor = outcomeColors[pred.prediction];

  return (
    <PageTransition className="space-y-5">
      <Link
        to="/"
        className="inline-flex items-center gap-2 text-sm text-slate-400 transition-colors hover:text-white"
      >
        <IconArrowLeft className="h-4 w-4" />
        Voltar aos palpites
      </Link>

      {/* Match hero */}
      <div
        className="relative overflow-hidden rounded-2xl border"
        style={{ borderColor: `${winnerColor}25` }}
      >
        {/* Imagem de duelo gerada pelo modelo */}
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
          {/* Times */}
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

        {/* H2H strip */}
        <div className="border-t border-white/[0.05] px-6 py-3 sm:px-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <p className="text-xs text-slate-500">{pred.h2hSummary}</p>
            <ConfidenceBadge confidence={pred.confidence} prediction={pred.prediction} />
          </div>
        </div>
      </div>

      {/* Charts */}
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

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MetricCard title="Placar provável" value={pred.poissonScore} accent="green" />
        <MetricCard title="Gols esperados" value={pred.expectedGoals} accent="blue" />
        <MetricCard title="Prob. casa" value={formatPercent(pred.probHome)} accent="green" />
        <MetricCard title="Prob. fora" value={formatPercent(pred.probAway)} accent="purple" />
      </div>

      {/* Confidence + ensemble */}
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

      <div className="glass-card p-5">
        <p className="section-label">Contexto pré-jogo</p>
        <MatchContextPanel prediction={pred} />
      </div>
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
  accent: "green" | "blue" | "purple";
}) {
  const colorMap = {
    green: "text-neon-green border-neon-green/15 bg-neon-green/4",
    blue: "text-neon-blue border-neon-blue/15 bg-neon-blue/4",
    purple: "text-neon-purple border-neon-purple/15 bg-neon-purple/4",
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
