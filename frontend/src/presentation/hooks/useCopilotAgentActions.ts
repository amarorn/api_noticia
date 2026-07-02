import { useCallback } from "react";
import type { LiveCopilotTabId, LiveCopilotUiAction, LiveCopilotUiLeg } from "@/domain/entities";
import { useToast } from "@/presentation/components/ui/toast/ToastContext";

interface UseCopilotAgentActionsOptions {
  onAddTicketLegs?: (legs: LiveCopilotUiLeg[]) => void;
  onSwitchTab?: (tab: LiveCopilotTabId) => void;
}

export function useCopilotAgentActions(options: UseCopilotAgentActionsOptions = {}) {
  const { addToast } = useToast();

  const executeActions = useCallback(
    (actions: LiveCopilotUiAction[]) => {
      for (const action of actions) {
        if (action.type === "notify") {
          const text = action.body || action.title || "Copiloto";
          addToast(text, "info");
          continue;
        }
        if (action.type === "add_ticket_legs") {
          if (action.legs.length > 0 && options.onAddTicketLegs) {
            options.onAddTicketLegs(action.legs);
            addToast("Pernas adicionadas ao simulador.", "success");
          } else if (action.legs.length > 0) {
            addToast("Simulador indisponível nesta tela.", "info");
          }
          continue;
        }
        if (action.type === "switch_tab" && action.tab) {
          options.onSwitchTab?.(action.tab);
        }
      }
    },
    [addToast, options.onAddTicketLegs, options.onSwitchTab],
  );

  return { executeActions };
}
