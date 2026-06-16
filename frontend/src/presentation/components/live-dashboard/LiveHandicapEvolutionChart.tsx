import type { SuperbetLiveAdvice } from "@/domain/entities";
import { LivePredictionEvolutionChart } from "@/presentation/components/live-dashboard/LivePredictionEvolutionChart";

interface LiveHandicapEvolutionChartProps {
  data: SuperbetLiveAdvice;
  /** @deprecated histórico interno via useLivePredictionHistory */
  history?: unknown;
}

/** @deprecated Use LivePredictionEvolutionChart */
export function LiveHandicapEvolutionChart({ data }: LiveHandicapEvolutionChartProps) {
  return <LivePredictionEvolutionChart data={data} />;
}
