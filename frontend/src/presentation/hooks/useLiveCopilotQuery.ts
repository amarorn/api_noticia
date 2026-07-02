import { useQuery } from "@tanstack/react-query";
import { useRef } from "react";
import { getLiveCopilotUseCase } from "@/application/container";
import { apiFetch } from "@/infrastructure/api/client";
import { mapLiveCopilot } from "@/infrastructure/mappers";

const COPILOT_POLL_MS = 25_000;

export function useLiveCopilotQuery(options: {
  eventId: number;
  sport: "football" | "basketball";
  phase?: string;
  bankroll?: number;
  enabled?: boolean;
}) {
  const { eventId, sport, phase, bankroll = 1000, enabled = true } = options;
  const preferLatestRef = useRef(true);

  return useQuery({
    queryKey: ["live-copilot", sport, eventId, phase, bankroll],
    queryFn: async () => {
      if (preferLatestRef.current && sport === "football") {
        preferLatestRef.current = false;
        try {
          const stale = await apiFetch<Parameters<typeof mapLiveCopilot>[0]>(
            `/worldcup/superbet/live/${eventId}/copilot/latest`,
            { timeoutMs: 8_000 },
          );
          return mapLiveCopilot(stale);
        } catch {
          /* poll ainda não aqueceu */
        }
      }

      return getLiveCopilotUseCase.execute({
        eventId,
        sport,
        phase,
        bankroll,
        fast: true,
      });
    },
    enabled: enabled && Number.isFinite(eventId) && eventId > 0,
    refetchInterval: (query) => {
      if (!enabled) return false;
      const data = query.state.data;
      if (data && !data.enabled) return false;
      return COPILOT_POLL_MS;
    },
    staleTime: 20_000,
    retry: 1,
  });
}
