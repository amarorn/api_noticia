import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  getWcEditionMatchesUseCase,
  getWcEditionsUseCase,
  validateHistoricalMatchUseCase,
} from "@/application/container";
import type { WcHistoricalMatch } from "@/domain/entities";
import { HistoricalMatchPicker } from "@/presentation/components/historical/HistoricalMatchPicker";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { PageHeader } from "@/presentation/pages/DashboardPage";
import {
  ModelBreakdownChart,
  ProbabilityDonut,
} from "@/presentation/components/charts/ProbabilityCharts";
import { ConfidenceBar } from "@/presentation/components/predictions/ConfidenceBadge";
import { PoissonFactorsPanel } from "@/presentation/components/predictions/PoissonFactorsPanel";
import { ErrorState } from "@/presentation/components/ui/ErrorState";
import { Skeleton } from "@/presentation/components/ui/Skeleton";
import { formatPercent, outcomeColors, outcomeLabels } from "@/presentation/theme";

export function HistoricalValidationPage() {
  const [season, setSeason] = useState<number | null>(null);
  const [selectedMatch, setSelectedMatch] = useState<WcHistoricalMatch | null>(null);

  const editionsQuery = useQuery({
    queryKey: ["wc-editions"],
    queryFn: () => getWcEditionsUseCase.execute(),
  });

  const matchesQuery = useQuery({
    queryKey: ["wc-edition-matches", season],
    queryFn: () => getWcEditionMatchesUseCase.execute(season!),
    enabled: season != null,
  });

  const validateMutation = useMutation({
    mutationFn: () =>
      validateHistoricalMatchUseCase.execute({
        season: season!,
        matchId: selectedMatch!.matchId,
      }),
  });

  const handleSelectEdition = (s: number) => {
    setSeason(s);
    setSelectedMatch(null);
    validateMutation.reset();
  };

  const handleValidate = () => {
    if (season && selectedMatch) validateMutation.mutate();
  };

  return (
    <PageTransition className="space-y-8">
      <PageHeader
        title="Validar histórico"
        subtitle="Backtest jogo a jogo com recorte temporal — sem vazamento de dados futuros"
      />

      <section className="space-y-4">
        <StepLabel step={1} title="Escolha a Copa do Mundo" />
        {editionsQuery.isLoading && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
        )}
        {editionsQuery.isError && (
          <ErrorState
            message="Não foi possível carregar as edições"
            onRetry={() => editionsQuery.refetch()}
          />
        )}
        {editionsQuery.data && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            {editionsQuery.data.map((edition) => (
              <button
                key={edition.season}
                type="button"
                onClick={() => handleSelectEdition(edition.season)}
                className={`glass-card p-4 text-left transition-all hover:border-neon-blue/40 ${
                  season === edition.season
                    ? "border-neon-green/50 ring-1 ring-neon-green/30"
                    : ""
                }`}
              >
                <p className="text-2xl font-black text-white">{edition.season}</p>
                <p className="mt-1 text-xs text-slate-400 line-clamp-2">{edition.label}</p>
                <p className="mt-2 text-[10px] uppercase tracking-wider text-slate-500">
                  {edition.matchCount} jogos
                </p>
              </button>
            ))}
          </div>
        )}
      </section>

      {season != null && (
        <section className="space-y-4">
          <StepLabel step={2} title="Selecione o jogo" />
          <HistoricalMatchPicker
            matches={matchesQuery.data}
            isLoading={matchesQuery.isLoading}
            isError={matchesQuery.isError}
            onRetry={() => matchesQuery.refetch()}
            selectedMatch={selectedMatch}
            onSelect={(match) => {
              setSelectedMatch(match);
              validateMutation.reset();
            }}
          />
        </section>
      )}

      {selectedMatch && season != null && (
        <section className="space-y-4">
          <StepLabel step={3} title="Validar previsão" />
          <div className="flex flex-wrap items-center gap-4">
            <p className="text-sm text-slate-400">
              {selectedMatch.homeTeam} x {selectedMatch.awayTeam} — resultado real:{" "}
              <span className="font-semibold text-white">{selectedMatch.score}</span> (
              {selectedMatch.resultLabel})
            </p>
            <button
              type="button"
              onClick={handleValidate}
              disabled={validateMutation.isPending}
              className="btn-primary"
            >
              {validateMutation.isPending ? "Validando..." : "Validar previsão"}
            </button>
          </div>

          {validateMutation.isError && (
            <ErrorState
              message={
                validateMutation.error instanceof Error
                  ? validateMutation.error.message
                  : "Erro na validação"
              }
              onRetry={handleValidate}
            />
          )}

          {validateMutation.isPending && (
            <div className="glass-card space-y-4 p-6">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-48 w-full" />
            </div>
          )}

          <AnimatePresence>
            {validateMutation.data && (
              <ValidationResultPanel data={validateMutation.data} />
            )}
          </AnimatePresence>
        </section>
      )}
    </PageTransition>
  );
}

function StepLabel({ step, title }: { step: number; title: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-neon-blue/20 text-sm font-bold text-neon-blue">
        {step}
      </span>
      <h2 className="text-lg font-semibold text-white">{title}</h2>
    </div>
  );
}

function ValidationResultPanel({
  data,
}: {
  data: Awaited<ReturnType<typeof validateHistoricalMatchUseCase.execute>>;
}) {
  const { match, correct, prediction, cutoffNote } = data;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0 }}
      className="space-y-6"
    >
      <motion.div
        initial={{ scale: 0.9 }}
        animate={{ scale: 1 }}
        className={`flex flex-col items-center justify-center rounded-2xl border-2 p-8 ${
          correct
            ? "border-neon-green/50 bg-neon-green/10"
            : "border-red-500/50 bg-red-500/10"
        }`}
      >
        <motion.p
          initial={{ y: 8, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.1 }}
          className={`text-4xl font-black tracking-tight sm:text-5xl ${
            correct ? "text-neon-green" : "text-red-400"
          }`}
        >
          {correct ? "ACERTOU" : "ERROU"}
        </motion.p>
        <p className="mt-2 text-sm text-slate-400">{cutoffNote}</p>
      </motion.div>

      <div className="grid gap-4 md:grid-cols-2">
        <CompareCard
          title="Palpite IA"
          outcome={prediction}
          subtitle={outcomeLabels[prediction]}
          accent={outcomeColors[prediction]}
          extra={formatPercent(data.confidence)}
        />
        <CompareCard
          title="Resultado real"
          outcome={match.actualResult}
          subtitle={match.actualResultLabel}
          accent={outcomeColors[match.actualResult]}
          extra={match.actualScore}
        />
      </div>

      <div className="glass-card space-y-6 p-6">
        <h3 className="text-xl font-bold text-white">
          {match.homeTeam} x {match.awayTeam}
        </h3>
        <p className="text-sm text-slate-400">{data.h2hSummary}</p>

        <div className="grid gap-6 md:grid-cols-2">
          <ProbabilityDonut
            probHome={data.probHome}
            probDraw={data.probDraw}
            probAway={data.probAway}
            prediction={data.prediction}
          />
          <ModelBreakdownChart
            dixonColes={data.modelBreakdown.dixonColes}
            logistic={data.modelBreakdown.logistic}
          />
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatBox label="Placar real" value={match.actualScore} />
          <StatBox label="Placar provável (Dixon-Coles)" value={data.poissonScore} />
          <StatBox label="Gols esperados" value={data.expectedGoals} />
          <StatBox label="Fase" value={match.phaseLabel} />
        </div>

        <ConfidenceBar confidence={data.confidence} />

        {data.modelBreakdown.poissonFactors && (
          <PoissonFactorsPanel
            factors={data.modelBreakdown.poissonFactors}
            homeTeam={match.homeTeam}
            awayTeam={match.awayTeam}
          />
        )}

        <div className="rounded-xl bg-white/5 p-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-500">
            Contexto (pré-jogo)
          </p>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-300">
            {data.context}
          </p>
        </div>
      </div>
    </motion.div>
  );
}

function CompareCard({
  title,
  outcome,
  subtitle,
  accent,
  extra,
}: {
  title: string;
  outcome: string;
  subtitle: string;
  accent: string;
  extra: string;
}) {
  return (
    <div className="glass-card p-6 text-center">
      <p className="text-xs uppercase tracking-wider text-slate-500">{title}</p>
      <p
        className="mt-3 text-5xl font-black"
        style={{ color: accent }}
      >
        {outcome}
      </p>
      <p className="mt-2 text-sm text-slate-300">{subtitle}</p>
      <p className="mt-1 text-lg font-bold text-white">{extra}</p>
    </div>
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
