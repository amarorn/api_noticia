import { useMutation, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/infrastructure/api/client";
import { mapLiveCopilot, mapLiveCopilotAgent } from "@/infrastructure/mappers";
import type { LiveCopilot, LiveCopilotChatMessage } from "@/domain/entities";
import { useCallback, useState } from "react";

export function usePregameCopilotQuery(options: {
  home: string;
  away: string;
  phase: string;
  enabled?: boolean;
}) {
  const { home, away, phase, enabled = true } = options;
  return useQuery({
    queryKey: ["pregame-copilot", home, away, phase],
    queryFn: async () => {
      const raw = await apiFetch<Parameters<typeof mapLiveCopilot>[0]>(
        `/worldcup/pregame/copilot?home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}&phase=${phase}`,
        { timeoutMs: 45_000 },
      );
      return mapLiveCopilot(raw);
    },
    enabled: enabled && Boolean(home && away),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}

export function usePregameCopilotAgentSession(options: {
  home: string;
  away: string;
  phase: string;
  enabled?: boolean;
  baseCopilot: LiveCopilot | undefined;
  onSwitchTab?: (tab: string) => void;
}) {
  const [chatHistory, setChatHistory] = useState<LiveCopilotChatMessage[]>([]);
  const [agentOverlay, setAgentOverlay] = useState<LiveCopilot | null>(null);

  const mutation = useMutation({
    mutationFn: async (payload: { message: string; history: LiveCopilotChatMessage[] }) => {
      const raw = await apiFetch<Record<string, unknown>>(
        `/worldcup/pregame/copilot/agent`,
        {
          method: "POST",
          body: JSON.stringify({
            home: options.home,
            away: options.away,
            phase: options.phase,
            message: payload.message,
            history: payload.history,
          }),
          timeoutMs: 90_000,
        },
      );
      return mapLiveCopilotAgent(raw);
    },
  });

  const displayCopilot = agentOverlay ?? options.baseCopilot;

  const sendMessage = useCallback(
    async (message: string) => {
      if (!options.enabled || mutation.isPending) return;
      const trimmed = message.trim();
      if (!trimmed) return;

      setChatHistory((prev) => [...prev, { role: "user", content: trimmed }]);

      try {
        const result = await mutation.mutateAsync({
          message: trimmed,
          history: chatHistory,
        });
        setChatHistory((prev) => [
          ...prev,
          { role: "assistant", content: result.reply || result.momento },
        ]);
        setAgentOverlay(result);

        if (result.autoApplyUi) {
          for (const action of result.uiActions) {
            if (action.type === "switch_tab" && action.tab && options.onSwitchTab) {
              options.onSwitchTab(action.tab);
            }
          }
        }
      } catch (err) {
        const detail = err instanceof Error ? err.message : "Falha ao consultar agente";
        setChatHistory((prev) => [...prev, { role: "assistant", content: detail }]);
      }
    },
    [chatHistory, mutation, options],
  );

  return {
    displayCopilot,
    agentChat: {
      history: chatHistory,
      pendingActions: [] as never[],
      isPending: mutation.isPending,
      lastMode: mutation.data?.mode ?? null,
      onSend: sendMessage,
      onApplyActions: () => {},
      onDismissActions: () => {},
    },
  };
}
