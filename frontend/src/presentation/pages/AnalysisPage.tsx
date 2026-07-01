import { MatchDetailPage } from "@/presentation/pages/MatchDetailPage";

/** Análise completa — alias PT-BR de /match/:home/:away */
export function AnalysisPage() {
  return <MatchDetailPage routeHomeKey="mandante" routeAwayKey="visitante" />;
}
