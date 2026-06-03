import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  getWcTeamsUseCase,
  predictWcMatchUseCase,
} from "@/application/container";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { PageHeader } from "@/presentation/pages/DashboardPage";
import {
  ModelBreakdownChart,
  ProbabilityDonut,
} from "@/presentation/components/charts/ProbabilityCharts";
import { ConfidenceBadge, ConfidenceBar } from "@/presentation/components/predictions/ConfidenceBadge";
import { MatchContextPanel } from "@/presentation/components/predictions/MatchContextPanel";
import { PoissonFactorsPanel } from "@/presentation/components/predictions/PoissonFactorsPanel";
import { ErrorState } from "@/presentation/components/ui/ErrorState";
import { Skeleton } from "@/presentation/components/ui/Skeleton";
import { phases } from "@/presentation/theme";
import { motion } from "framer-motion";

export function PredictPage() {
  const [homeTeam, setHomeTeam] = useState("Brasil");
  const [awayTeam, setAwayTeam] = useState("Marrocos");
  const [phase, setPhase] = useState("group");

  const teamsQuery = useQuery({
    queryKey: ["wc-teams"],
    queryFn: () => getWcTeamsUseCase.execute(),
  });

  const predictMutation = useMutation({
    mutationFn: () =>
      predictWcMatchUseCase.execute({ homeTeam, awayTeam, phase }),
  });

  const teams = teamsQuery.data ?? [];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (homeTeam && awayTeam && homeTeam !== awayTeam) {
      predictMutation.mutate();
    }
  };

  return (
    <PageTransition className="space-y-8">
      <PageHeader
        title="Palpite avulso"
        subtitle="Selecione as seleções e a fase para gerar previsão com ensemble Dixon-Coles + Logística"
      />

      <div className="grid gap-8 lg:grid-cols-5">
        <form onSubmit={handleSubmit} className="glass-card space-y-5 p-6 lg:col-span-2">
          <div>
            <label htmlFor="home" className="mb-1.5 block text-xs font-medium text-slate-400">
              Mandante
            </label>
            {teamsQuery.isLoading ? (
              <Skeleton className="h-10 w-full" />
            ) : (
              <select
                id="home"
                value={homeTeam}
                onChange={(e) => setHomeTeam(e.target.value)}
                className="input-field"
              >
                {teams.map((t) => (
                  <option key={t} value={t} className="bg-surface">
                    {t}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div>
            <label htmlFor="away" className="mb-1.5 block text-xs font-medium text-slate-400">
              Visitante
            </label>
            <select
              id="away"
              value={awayTeam}
              onChange={(e) => setAwayTeam(e.target.value)}
              className="input-field"
            >
              {teams.map((t) => (
                <option key={t} value={t} className="bg-surface">
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="phase" className="mb-1.5 block text-xs font-medium text-slate-400">
              Fase
            </label>
            <select
              id="phase"
              value={phase}
              onChange={(e) => setPhase(e.target.value)}
              className="input-field"
            >
              {phases.map((p) => (
                <option key={p.value} value={p.value} className="bg-surface">
                  {p.label}
                </option>
              ))}
            </select>
          </div>

          <button
            type="submit"
            disabled={predictMutation.isPending || homeTeam === awayTeam}
            className="btn-primary w-full"
          >
            {predictMutation.isPending ? "Calculando..." : "Gerar palpite"}
          </button>

          {homeTeam === awayTeam && (
            <p className="text-xs text-amber-400">Selecione times diferentes.</p>
          )}
        </form>

        <div className="lg:col-span-3">
          {predictMutation.isError && (
            <ErrorState
              message={
                predictMutation.error instanceof Error
                  ? predictMutation.error.message
                  : "Erro na previsão"
              }
              onRetry={() => predictMutation.mutate()}
            />
          )}

          {!predictMutation.data && !predictMutation.isPending && !predictMutation.isError && (
            <div className="glass-card flex h-full min-h-[320px] flex-col items-center justify-center p-8 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white/5 text-2xl font-black text-slate-600">
                VS
              </div>
              <p className="mt-4 text-slate-400">
                Configure o confronto e clique em Gerar palpite
              </p>
            </div>
          )}

          {predictMutation.isPending && (
            <div className="glass-card space-y-4 p-6">
              <Skeleton className="h-8 w-1/2" />
              <Skeleton className="h-48 w-full" />
              <Skeleton className="h-32 w-full" />
            </div>
          )}

          {predictMutation.data && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-card space-y-6 p-6"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="text-2xl font-bold text-white">
                    {predictMutation.data.homeTeam} x {predictMutation.data.awayTeam}
                  </h2>
                  <p className="text-sm text-slate-400">{predictMutation.data.h2hSummary}</p>
                </div>
                <ConfidenceBadge
                  confidence={predictMutation.data.confidence}
                  prediction={predictMutation.data.prediction}
                />
              </div>

              <div className="grid gap-6 md:grid-cols-2">
                <ProbabilityDonut
                  probHome={predictMutation.data.probHome}
                  probDraw={predictMutation.data.probDraw}
                  probAway={predictMutation.data.probAway}
                  prediction={predictMutation.data.prediction}
                />
                <ModelBreakdownChart
                  dixonColes={predictMutation.data.modelBreakdown.dixonColes}
                  logistic={predictMutation.data.modelBreakdown.logistic}
                />
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <StatBox label="Placar provável" value={predictMutation.data.poissonScore} />
                <StatBox label="Gols esperados" value={predictMutation.data.expectedGoals} />
                <StatBox
                  label="Holdout 2022"
                  value={
                    predictMutation.data.modelBreakdown.holdout2022Accuracy != null
                      ? `${(predictMutation.data.modelBreakdown.holdout2022Accuracy * 100).toFixed(1)}%`
                      : "N/A"
                  }
                />
                <StatBox
                  label="Peso Dixon-Coles"
                  value={`${(predictMutation.data.modelBreakdown.ensembleWeights.dixonColes * 100).toFixed(0)}%`}
                />
              </div>

              <ConfidenceBar confidence={predictMutation.data.confidence} />

              {predictMutation.data.modelBreakdown.poissonFactors && (
                <PoissonFactorsPanel
                  factors={predictMutation.data.modelBreakdown.poissonFactors}
                  homeTeam={predictMutation.data.homeTeam}
                  awayTeam={predictMutation.data.awayTeam}
                />
              )}

              <div>
                <p className="mb-4 text-xs font-medium uppercase tracking-wider text-slate-500">
                  Contexto pré-jogo
                </p>
                <MatchContextPanel prediction={predictMutation.data} />
              </div>
            </motion.div>
          )}
        </div>
      </div>
    </PageTransition>
  );
}

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-white/5 p-3 text-center">
      <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-bold text-white">{value}</p>
    </div>
  );
}
