import { useMutation } from "@tanstack/react-query";
import { postLiveCopilotAgentUseCase } from "@/application/container";
import type { LiveCopilotChatMessage } from "@/domain/entities";

export function useLiveCopilotAgentMutation(options: {
  eventId: number;
  sport: "football" | "basketball";
  phase?: string;
  bankroll?: number;
  fast?: boolean;
  kickoff?: string;
}) {
  return useMutation({
    mutationFn: (payload: { message: string; history: LiveCopilotChatMessage[] }) =>
      postLiveCopilotAgentUseCase.execute({
        eventId: options.eventId,
        sport: options.sport,
        message: payload.message,
        history: payload.history,
        phase: options.phase,
        bankroll: options.bankroll,
        fast: options.fast,
        kickoff: options.kickoff,
      }),
  });
}
