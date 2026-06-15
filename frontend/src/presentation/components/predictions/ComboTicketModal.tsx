import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { getWcComboTicketUseCase } from "@/application/container";
import type { WcScheduleMatch } from "@/domain/entities";
import { ComboTicketPanel } from "@/presentation/components/predictions/ComboTicketPanel";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { IconX } from "@/presentation/components/ui/Icons";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";
import { isMatchPregame } from "@/presentation/utils/sofascore";

interface ComboTicketModalProps {
  match: WcScheduleMatch | null;
  open: boolean;
  onClose: () => void;
}

function formatKickoff(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      weekday: "short",
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export function ComboTicketModal({ match, open, onClose }: ComboTicketModalProps) {
  const pregame = match != null && isMatchPregame(match.kickoff);

  const comboQuery = useQuery({
    queryKey: ["wc-combo-ticket", match?.homeTeam, match?.awayTeam],
    queryFn: () =>
      getWcComboTicketUseCase.execute({
        homeTeam: match!.homeTeam,
        awayTeam: match!.awayTeam,
        bankroll: 1000,
      }),
    enabled: open && pregame && Boolean(match?.homeTeam && match?.awayTeam),
    staleTime: 5 * 60_000,
  });

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open || !match || !pregame) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-end justify-center p-0 sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="combo-ticket-title"
    >
      <button
        type="button"
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        aria-label="Fechar bilhete combo"
        onClick={onClose}
      />

      <div className="relative z-10 flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-t-2xl border border-white/10 bg-surface shadow-2xl sm:rounded-2xl">
        <header className="flex shrink-0 items-start justify-between gap-4 border-b border-white/8 px-5 py-4">
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-widest text-neon-blue">
              Bilhete combo · pré-jogo
            </p>
            <h2 id="combo-ticket-title" className="mt-1 text-lg font-semibold text-white">
              {match.homeTeam} × {match.awayTeam}
            </h2>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span className="inline-flex items-center gap-1.5">
                <TeamFlag team={match.homeTeam} size={18} />
                <span>Grupo {match.group}</span>
              </span>
              {match.kickoff && <span>· {formatKickoff(match.kickoff)}</span>}
              {match.venue && <span>· {match.venue}</span>}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-white/10 p-2 text-slate-400 transition-colors hover:border-white/20 hover:text-white"
            aria-label="Fechar"
          >
            <IconX className="h-4 w-4" />
          </button>
        </header>

        <div className="overflow-y-auto px-5 py-4">
          {comboQuery.isLoading && (
            <div className="space-y-3 py-6">
              <div className="h-4 w-2/3 animate-pulse rounded bg-white/10" />
              <div className="h-24 animate-pulse rounded-xl bg-white/5" />
              <div className="h-24 animate-pulse rounded-xl bg-white/5" />
              <p className="text-center text-xs text-slate-500">Montando combo com padrões KXL…</p>
            </div>
          )}

          {comboQuery.isError && (
            <ErrorState
              title="Falha ao montar bilhete"
              message={
                comboQuery.error instanceof Error
                  ? comboQuery.error.message
                  : "Verifique se a API está rodando."
              }
              onRetry={() => comboQuery.refetch()}
            />
          )}

          {comboQuery.isSuccess && (
            <ComboTicketPanel
              homeTeam={match.homeTeam}
              awayTeam={match.awayTeam}
              ticket={comboQuery.data}
            />
          )}
        </div>
      </div>
    </div>
  );
}
