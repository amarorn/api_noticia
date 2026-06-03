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
import { ErrorState } from "@/presentation/components/ui/ErrorState";
import { formatPercent } from "@/presentation/theme";

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

  return (
    <PageTransition className="space-y-6">
      <Link to="/" className="btn-ghost inline-flex text-sm">
        ← Voltar ao dashboard
      </Link>

      <div className="glass-card space-y-8 p-6 sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div>
            <p className="text-xs uppercase tracking-wider text-slate-500">Análise detalhada</p>
            <h1 className="mt-1 text-3xl font-bold text-white sm:text-4xl">
              {pred.homeTeam}{" "}
              <span className="text-slate-500 font-normal">x</span> {pred.awayTeam}
            </h1>
            <p className="mt-2 text-sm text-slate-400">{pred.h2hSummary}</p>
          </div>
          <ConfidenceBadge confidence={pred.confidence} prediction={pred.prediction} />
        </div>

        <div className="grid gap-8 lg:grid-cols-2">
          <div className="rounded-2xl bg-white/[0.02] p-4">
            <ProbabilityDonut
              probHome={pred.probHome}
              probDraw={pred.probDraw}
              probAway={pred.probAway}
              prediction={pred.prediction}
              height={280}
            />
          </div>
          <ModelBreakdownChart
            dixonColes={pred.modelBreakdown.dixonColes}
            logistic={pred.modelBreakdown.logistic}
            height={280}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard title="Placar provável" value={pred.poissonScore} accent="green" />
          <MetricCard title="Gols esperados" value={pred.expectedGoals} accent="blue" />
          <MetricCard
            title="Prob. vitória casa"
            value={formatPercent(pred.probHome)}
            accent="green"
          />
          <MetricCard
            title="Prob. vitória fora"
            value={formatPercent(pred.probAway)}
            accent="purple"
          />
        </div>

        <ConfidenceBar confidence={pred.confidence} />

        <div className="grid gap-4 sm:grid-cols-3">
          <EnsembleCard
            label="Peso Dixon-Coles"
            value={pred.modelBreakdown.ensembleWeights.dixonColes}
          />
          <EnsembleCard
            label="Peso Logística"
            value={pred.modelBreakdown.ensembleWeights.logistic}
          />
          <EnsembleCard
            label="Holdout 2022"
            value={pred.modelBreakdown.holdout2022Accuracy ?? 0}
            isPercent
          />
        </div>

        {pred.modelBreakdown.poissonFactors && (
          <PoissonFactorsPanel
            factors={pred.modelBreakdown.poissonFactors}
            homeTeam={pred.homeTeam}
            awayTeam={pred.awayTeam}
          />
        )}

        <section>
          <h2 className="mb-4 text-lg font-semibold text-white">Contexto pré-jogo</h2>
          <MatchContextPanel prediction={pred} />
        </section>
      </div>
    </PageTransition>
  );
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
  const colors = {
    green: "text-neon-green border-neon-green/20",
    blue: "text-neon-blue border-neon-blue/20",
    purple: "text-neon-purple border-neon-purple/20",
  };

  return (
    <div className={`rounded-xl border bg-white/[0.02] p-4 ${colors[accent]}`}>
      <p className="text-xs text-slate-500">{title}</p>
      <p className={`mt-1 text-xl font-bold ${colors[accent].split(" ")[0]}`}>{value}</p>
    </div>
  );
}

function EnsembleCard({
  label,
  value,
  isPercent,
}: {
  label: string;
  value: number;
  isPercent?: boolean;
}) {
  return (
    <div className="rounded-xl bg-white/5 p-4 text-center">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-white">
        {isPercent ? formatPercent(value) : formatPercent(value)}
      </p>
    </div>
  );
}
