import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/infrastructure/api/client";

export interface SportradarPublicConfig {
  widget: string;
  language: string;
  embedAvailable: boolean;
  clientIdConfigured: boolean;
}

async function fetchSportradarConfig(): Promise<SportradarPublicConfig> {
  const raw = await apiFetch<{
    widget: string;
    language: string;
    embed_available: boolean;
    client_id_configured: boolean;
  }>("/config/sportradar");
  return {
    widget: raw.widget,
    language: raw.language,
    embedAvailable: raw.embed_available,
    clientIdConfigured: raw.client_id_configured,
  };
}

/** Indica se a API tem licença Sportradar para servir o LMT oficial. */
export function useSportradarConfig() {
  return useQuery({
    queryKey: ["sportradar-config"],
    queryFn: fetchSportradarConfig,
    staleTime: 60_000,
  });
}

/** URL do embed iframe (proxy Vite → API). */
export function sportradarLmtEmbedUrl(betradarId: string): string {
  return `/api/sportradar/lmt/${encodeURIComponent(betradarId)}`;
}
