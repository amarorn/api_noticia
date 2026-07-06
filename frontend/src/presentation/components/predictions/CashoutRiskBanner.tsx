import { useState } from "react";
import type { CashoutRiskAssessment } from "@/presentation/utils/cashoutRiskAssessment";
import { formatBrl } from "@/presentation/utils/cashoutRiskAssessment";
import { executeCashoutViaExtension } from "@/presentation/utils/executeCashoutViaExtension";

const ACTION_STYLES: Record<
  CashoutRiskAssessment["action"],
  { border: string; bg: string; badge: string; badgeText: string }
> = {
  exit_now: {
    border: "border-red-500/45",
    bg: "bg-red-500/10",
    badge: "bg-red-500/25",
    badgeText: "text-red-200",
  },
  protect_stake: {
    border: "border-amber-500/45",
    bg: "bg-amber-500/10",
    badge: "bg-amber-500/25",
    badgeText: "text-amber-100",
  },
  consider_exit: {
    border: "border-orange-500/35",
    bg: "bg-orange-500/8",
    badge: "bg-orange-500/20",
    badgeText: "text-orange-200",
  },
  hold: {
    border: "border-white/10",
    bg: "bg-white/[0.02]",
    badge: "bg-white/10",
    badgeText: "text-slate-400",
  },
  dead: {
    border: "border-red-500/30",
    bg: "bg-red-500/5",
    badge: "bg-red-500/15",
    badgeText: "text-red-300",
  },
};

const ACTION_LABELS: Record<CashoutRiskAssessment["action"], string> = {
  exit_now: "Sair agora",
  protect_stake: "Proteger valor",
  consider_exit: "Avaliar saída",
  hold: "Segurar",
  dead: "Perdido",
};

interface CashoutRiskBannerProps {
  assessment: CashoutRiskAssessment;
  compact?: boolean;
  ticketCode?: string | null;
  betId?: string;
}

export function CashoutRiskBanner({
  assessment,
  compact = false,
  ticketCode,
  betId,
}: CashoutRiskBannerProps) {
  const [executing, setExecuting] = useState(false);
  const [execMsg, setExecMsg] = useState<string | null>(null);

  if (!assessment.alert && assessment.action === "hold") return null;

  const style = ACTION_STYLES[assessment.action];
  const canExecute =
    Boolean(ticketCode) &&
    assessment.cashoutValue != null &&
    assessment.cashoutValue > 0 &&
    assessment.action !== "dead";

  const handleExecute = async () => {
    if (!ticketCode || executing) return;
    setExecuting(true);
    setExecMsg(null);
    const minValue = assessment.stake * 0.5;
    const result = await executeCashoutViaExtension({
      ticketCode,
      betId,
      minValue,
    });
    setExecuting(false);
    if (result.ok) {
      setExecMsg(
        `Cash-out enviado (${result.method === "api" ? "API" : "Superbet"}) — confira Minhas Apostas.`,
      );
    } else {
      setExecMsg(result.error || "Falhou — abra Minhas Apostas na Superbet logado.");
    }
  };

  return (
    <div className={`rounded-xl border p-4 ${style.border} ${style.bg}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span
              className={`rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${style.badge} ${style.badgeText}`}
            >
              {ACTION_LABELS[assessment.action]}
            </span>
            {assessment.cashoutValue != null && assessment.cashoutValue > 0 && (
              <span className="font-mono text-sm font-bold text-white">
                Cash-out {formatBrl(assessment.cashoutValue)}
              </span>
            )}
          </div>
          <p className="text-sm font-semibold text-white">{assessment.title}</p>
          <p className="mt-1 text-xs leading-relaxed text-slate-300">{assessment.message}</p>
          {assessment.cashoutPctOfStake != null && assessment.cashoutPctOfStake >= 0.5 && (
            <p className="mt-2 text-[11px] text-slate-400">
              Recupera {Math.round(assessment.cashoutPctOfStake * 100)}% da aposta (
              {formatBrl(assessment.stake)} → {formatBrl(assessment.cashoutValue ?? 0)})
            </p>
          )}
        </div>
        {canExecute && (
          <button
            type="button"
            disabled={executing}
            onClick={() => void handleExecute()}
            className="shrink-0 rounded-lg border border-red-400/40 bg-red-500/20 px-3 py-2 text-xs font-bold text-red-100 hover:bg-red-500/30 disabled:opacity-50"
          >
            {executing ? "Executando…" : "Cash-out agora"}
          </button>
        )}
      </div>
      {execMsg && <p className="mt-2 text-[11px] text-slate-400">{execMsg}</p>}

      {!compact && assessment.legs.length > 0 && (
        <ul className="mt-3 space-y-1.5 border-t border-white/10 pt-3">
          {assessment.legs.map((leg) => (
            <li key={`${leg.market}-${leg.outcome}`} className="flex items-start gap-2 text-[11px]">
              <LegStatusDot status={leg.status} />
              <span className="text-slate-300">
                {leg.label}
                {leg.reason ? (
                  <span className="block text-slate-500">{leg.reason}</span>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function LegStatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    won: "bg-neon-green",
    lost: "bg-red-400",
    critical: "bg-red-400 animate-pulse",
    at_risk: "bg-amber-400",
    pending: "bg-slate-600",
    ok: "bg-slate-500",
  };
  return (
    <span
      className={`mt-1 h-2 w-2 shrink-0 rounded-full ${colors[status] ?? "bg-slate-600"}`}
      aria-hidden
    />
  );
}
