import { useCallback, useMemo, useState } from "react";
import type {
  LiveCopilot,
  LiveCopilotChatMessage,
  LiveCopilotTabId,
  LiveCopilotUiAction,
  LiveCopilotUiLeg,
} from "@/domain/entities";
import { useCopilotAgentActions } from "@/presentation/hooks/useCopilotAgentActions";
import { useLiveCopilotAgentMutation } from "@/presentation/hooks/useLiveCopilotAgentMutation";

interface UseLiveCopilotAgentSessionOptions {
  eventId: number;
  sport: "football" | "basketball" | "baseball";
  phase?: string;
  bankroll?: number;
  kickoff?: string;
  enabled: boolean;
  baseCopilot: LiveCopilot | undefined;
  onAddTicketLegs?: (legs: LiveCopilotUiLeg[]) => void;
  onSwitchTab?: (tab: LiveCopilotTabId) => void;
}

export function useLiveCopilotAgentSession(options: UseLiveCopilotAgentSessionOptions) {
  const [chatHistory, setChatHistory] = useState<LiveCopilotChatMessage[]>([]);
  const [pendingActions, setPendingActions] = useState<LiveCopilotUiAction[]>([]);
  const [agentOverlay, setAgentOverlay] = useState<LiveCopilot | null>(null);
  const [lastMode, setLastMode] = useState<string | null>(null);

  const mutation = useLiveCopilotAgentMutation({
    eventId: options.eventId,
    sport: options.sport,
    phase: options.phase,
    bankroll: options.bankroll,
    kickoff: options.kickoff,
  });

  const { executeActions } = useCopilotAgentActions({
    onAddTicketLegs: options.onAddTicketLegs,
    onSwitchTab: options.onSwitchTab,
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

        setChatHistory((prev) => [...prev, { role: "assistant", content: result.reply || result.momento }]);
        setAgentOverlay(result);
        setLastMode(result.mode);
        setPendingActions([]);

        if (result.uiActions.length > 0) {
          if (result.autoApplyUi) {
            executeActions(result.uiActions);
          } else {
            setPendingActions(result.uiActions);
          }
        }
      } catch (err) {
        const detail = err instanceof Error ? err.message : "Falha ao consultar agente";
        setChatHistory((prev) => [...prev, { role: "assistant", content: detail }]);
      }
    },
    [chatHistory, executeActions, mutation, options.enabled],
  );

  const applyPendingActions = useCallback(() => {
    if (pendingActions.length === 0) return;
    executeActions(pendingActions);
    setPendingActions([]);
  }, [executeActions, pendingActions]);

  const dismissPendingActions = useCallback(() => {
    setPendingActions([]);
  }, []);

  const agentChat = useMemo(() => {
    if (!options.baseCopilot?.enabled) return undefined;
    return {
      history: chatHistory,
      pendingActions,
      isPending: mutation.isPending,
      lastMode,
      onSend: (msg: string) => {
        void sendMessage(msg);
      },
      onApplyActions: applyPendingActions,
      onDismissActions: dismissPendingActions,
    };
  }, [
    applyPendingActions,
    chatHistory,
    dismissPendingActions,
    lastMode,
    mutation.isPending,
    options.baseCopilot?.enabled,
    pendingActions,
    sendMessage,
  ]);

  return {
    displayCopilot,
    agentChat,
    resetAgentSession: useCallback(() => {
      setChatHistory([]);
      setPendingActions([]);
      setAgentOverlay(null);
      setLastMode(null);
    }, []),
  };
}
