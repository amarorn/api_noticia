import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { registerComboProposalUseCase } from "@/application/container";
import type { ComboProposalContext } from "@/application/dtos/comboProposal";
import { formatProposalBasis } from "@/presentation/utils/comboProposalQualification";

interface SendComboProposalButtonProps {
  proposal: ComboProposalContext;
  className?: string;
  compact?: boolean;
}

function formatApiError(err: unknown): string {
  if (!(err instanceof Error)) return "Falha ao enviar";
  const msg = err.message;
  if (msg.startsWith("[object Object]") || msg === "[object Object]") {
    return "Erro na API — verifique se a chave API está configurada.";
  }
  return msg || "Falha ao enviar";
}

/** Envia proposta qualificada (modelo × odd Superbet, EV+) para a estação. */
export function SendComboProposalButton({
  proposal,
  className = "",
  compact = false,
}: SendComboProposalButtonProps) {
  const queryClient = useQueryClient();
  const [feedback, setFeedback] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const canSend = proposal.qualified && proposal.legs.length >= 1;

  const mutation = useMutation({
    mutationFn: () => registerComboProposalUseCase.execute(proposal),
    onSuccess: (res) => {
      setSent(true);
      setFeedback(res.message || "Proposta enviada à estação");
      void queryClient.invalidateQueries({ queryKey: ["user-open-bets"] });
      window.setTimeout(() => {
        setSent(false);
        setFeedback(null);
      }, 6000);
    },
    onError: (err: unknown) => {
      setSent(false);
      setFeedback(formatApiError(err));
      window.setTimeout(() => setFeedback(null), 8000);
    },
  });

  const label = compact ? "Enviar à estação" : "Enviar proposta à estação";
  const basis = formatProposalBasis(proposal);
  const buttonLabel = mutation.isPending
    ? "Enviando…"
    : sent
      ? "Enviado ✓"
      : label;

  return (
    <div className={`flex flex-col items-stretch gap-1 ${className}`}>
      <button
        type="button"
        disabled={mutation.isPending || sent || !canSend}
        title={
          canSend
            ? basis
            : proposal.disqualifyReason ?? "Proposta precisa cruzar modelo com odd Superbet."
        }
        onClick={() => mutation.mutate()}
        className={`rounded-lg border px-3 py-2 text-[11px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${
          sent
            ? "border-emerald-400/50 bg-emerald-500/25 text-emerald-100"
            : "border-violet-400/40 bg-violet-500/15 text-violet-200 hover:border-violet-300/60 hover:bg-violet-500/25"
        }`}
      >
        {buttonLabel}
      </button>
      {canSend && !sent && (
        <p className="text-[10px] text-slate-500">{basis}</p>
      )}
      {!canSend && proposal.disqualifyReason && (
        <p className="text-[10px] text-amber-400/90">{proposal.disqualifyReason}</p>
      )}
      {feedback && (
        <p
          className={`rounded-lg px-2 py-1.5 text-[11px] font-medium ${
            mutation.isError || (!sent && feedback.includes("Falha"))
              ? "border border-red-500/30 bg-red-500/10 text-red-200"
              : "border border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
          }`}
          aria-live="polite"
        >
          {feedback}
        </p>
      )}
      {!compact && canSend && !sent && (
        <p className="text-[10px] text-slate-500">
          Stake sugerido R$ {Math.max(1, Math.round(proposal.suggestedStake))} ·{" "}
          {proposal.legs.length} pernas
        </p>
      )}
    </div>
  );
}
