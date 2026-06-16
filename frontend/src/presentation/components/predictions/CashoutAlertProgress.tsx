import { motion } from "framer-motion";
import { IconBell } from "@/presentation/components/ui/Icons";
import type { CashoutAlertConfig } from "@/presentation/utils/cashoutAlertStorage";
import { CASHOUT_APPROACH_RATIO } from "@/presentation/utils/cashoutAlertStorage";

interface CashoutAlertProgressProps {
  config: CashoutAlertConfig;
  currentCashout: number | null;
  compact?: boolean;
}

function formatBrl(value: number): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

type AlertPhase = "idle" | "tracking" | "approach" | "reached" | "no-data";

function resolvePhase(
  config: CashoutAlertConfig,
  current: number | null,
  target: number,
): AlertPhase {
  if (!config.enabled || target <= 0) return "idle";
  if (current == null || current <= 0) return "no-data";
  if (current >= target) return "reached";
  if (current >= target * CASHOUT_APPROACH_RATIO) return "approach";
  return "tracking";
}

const PHASE_UI: Record<
  AlertPhase,
  { label: string; sub: string; bar: string; ring: string; pulse?: boolean }
> = {
  idle: {
    label: "Alertas desligados",
    sub: "Edite o bilhete para definir uma meta",
    bar: "bg-slate-600",
    ring: "border-white/10 bg-white/[0.03]",
  },
  "no-data": {
    label: "Aguardando cash-out",
    sub: "Capture o bilhete na extensão ou informe o valor manualmente",
    bar: "bg-slate-600",
    ring: "border-amber-500/20 bg-amber-500/[0.04]",
  },
  tracking: {
    label: "A caminho da meta",
    sub: "Cash-out subindo — monitorando",
    bar: "bg-neon-blue",
    ring: "border-neon-blue/25 bg-neon-blue/[0.06]",
  },
  approach: {
    label: "Quase na meta",
    sub: "Cash-out a ≥ 95% — prepare a saída",
    bar: "bg-amber-400",
    ring: "border-amber-400/35 bg-amber-500/10",
    pulse: true,
  },
  reached: {
    label: "Meta atingida",
    sub: "Cash-out bateu ou passou o valor definido",
    bar: "bg-neon-green",
    ring: "border-neon-green/40 bg-neon-green/10",
    pulse: true,
  },
};

export function CashoutAlertProgress({
  config,
  currentCashout,
  compact = false,
}: CashoutAlertProgressProps) {
  const target = config.target;
  if (!config.enabled || target == null || target <= 0) {
    if (compact) return null;
    return (
      <div className="rounded-xl border border-dashed border-white/10 px-3 py-2 text-[11px] text-slate-500">
        <IconBell className="mr-1 inline h-3.5 w-3.5 opacity-50" />
        Sem meta de alerta — edite para configurar
      </div>
    );
  }

  const progress =
    currentCashout != null && currentCashout > 0
      ? Math.min(100, (currentCashout / target) * 100)
      : 0;
  const phase = resolvePhase(config, currentCashout, target);
  const ui = PHASE_UI[phase];
  const remaining =
    currentCashout != null && currentCashout > 0
      ? Math.max(0, target - currentCashout)
      : null;

  return (
    <div className={`rounded-xl border p-3 ${ui.ring}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span
            className={`flex h-7 w-7 items-center justify-center rounded-lg ${
              phase === "reached"
                ? "bg-neon-green/20 text-neon-green"
                : phase === "approach"
                  ? "bg-amber-500/20 text-amber-300"
                  : "bg-white/10 text-slate-400"
            }`}
          >
            <IconBell className={`h-3.5 w-3.5 ${ui.pulse ? "animate-pulse" : ""}`} />
          </span>
          <div>
            <p className="text-xs font-semibold text-white">{ui.label}</p>
            <p className="text-[10px] text-slate-400">{ui.sub}</p>
          </div>
        </div>
        {!compact && (
          <div className="text-right">
            <p className="font-mono text-lg font-bold text-white">
              {currentCashout != null && currentCashout > 0
                ? formatBrl(currentCashout)
                : "—"}
            </p>
            <p className="text-[10px] text-slate-500">meta {formatBrl(target)}</p>
          </div>
        )}
      </div>

      <div className="relative mt-3">
        <div className="h-2.5 overflow-hidden rounded-full bg-black/30">
          <motion.div
            className={`h-full rounded-full ${ui.bar}`}
            initial={false}
            animate={{ width: `${progress}%` }}
            transition={{ type: "spring", stiffness: 120, damping: 20 }}
          />
        </div>
        <span
          className="absolute top-1/2 h-3 w-0.5 -translate-y-1/2 rounded-full bg-amber-300/80"
          style={{ left: `${CASHOUT_APPROACH_RATIO * 100}%` }}
          title={`Alerta "quase lá" (${Math.round(CASHOUT_APPROACH_RATIO * 100)}%)`}
        />
      </div>

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[10px]">
        <span className="font-mono text-slate-500">{progress.toFixed(0)}% da meta</span>
        {remaining != null && phase !== "reached" && (
          <span className="text-slate-400">Faltam {formatBrl(remaining)}</span>
        )}
        {phase === "reached" && (
          <span className="font-semibold text-neon-green">Hora de decidir o cash-out</span>
        )}
      </div>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {config.notifyApproach && (
          <span className="rounded-full border border-amber-400/30 bg-amber-500/10 px-2 py-0.5 text-[9px] font-medium uppercase tracking-wide text-amber-200">
            Quase lá
          </span>
        )}
        {config.notifyReach && (
          <span className="rounded-full border border-neon-green/30 bg-neon-green/10 px-2 py-0.5 text-[9px] font-medium uppercase tracking-wide text-neon-green">
            Meta batida
          </span>
        )}
      </div>
    </div>
  );
}
