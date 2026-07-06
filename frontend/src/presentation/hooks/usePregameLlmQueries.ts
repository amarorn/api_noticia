import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/infrastructure/api/client";

export interface PregameResearchResponse {
  home_team: string;
  away_team: string;
  model_data?: Record<string, unknown>;
  web_research: { text: string; citations: string[] };
  synthesis: Record<string, unknown> | null;
  provider?: string;
  errors: Record<string, string>;
  from_cache: boolean;
  cached_at?: number;
  pregame_context?: Record<string, unknown> | null;
}

export function usePregameResearchQuery(options: {
  home: string;
  away: string;
  phase: string;
  enabled?: boolean;
}) {
  const { home, away, phase, enabled = true } = options;
  return useQuery<PregameResearchResponse>({
    queryKey: ["pregame-research", home, away, phase, "auto"],
    queryFn: () =>
      apiFetch(
        `/worldcup/pregame/research?home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}&phase=${phase}`,
        { timeoutMs: 120_000 },
      ),
    enabled: enabled && Boolean(home && away),
    staleTime: 60 * 60 * 1000,
    retry: 0,
  });
}

export interface PregameSummaryResponse {
  enabled: boolean;
  home_team: string;
  away_team: string;
  narrative: string;
  confianca: string;
  acao_sugerida: string;
  alertas: string[];
  modelo_vs_noticias?: string | null;
  from_cache: boolean;
  provider: string;
  error?: string | null;
}

export function usePregameSummaryQuery(options: {
  home: string;
  away: string;
  phase: string;
  enabled?: boolean;
}) {
  const { home, away, phase, enabled = true } = options;
  return useQuery<PregameSummaryResponse>({
    queryKey: ["pregame-summary", home, away, phase],
    queryFn: () =>
      apiFetch(
        `/worldcup/pregame/summary?home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}&phase=${phase}`,
        { timeoutMs: 45_000 },
      ),
    enabled: enabled && Boolean(home && away),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}
