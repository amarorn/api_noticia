import { motion, AnimatePresence } from "framer-motion";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import { formatPercent, outcomeLabels } from "@/presentation/theme";

export type AgainstModelAlert = NonNullable<
  SuperbetLiveAdvice["againstModelAlerts"]
>[number];

interface Props {
  alerts: AgainstModelAlert[] | null | undefined;
}

const SEVERITY_STYLES: Record<
  string,
  { bg: string; border: string; title: string; icon: string }
> = {
  critical: {
    bg: "bg-red-950/50",
    border: "border-red-500/70",
    title: "Aposta contra o modelo",
    icon: "⛔",
  },
  high: {
    bg: "bg-red-900/35",
    border: "border-red-500/50",
    title: "Contra o palpite ao vivo",
    icon: "🚨",
  },
  medium: {
    bg: "bg-orange-950/30",
    border: "border-orange-500/40",
    title: "Contra o palpite pré-jogo",
    icon: "⚠️",
  },
};

function AlertCard({ alert }: { alert: AgainstModelAlert }) {
  const style = SEVERITY_STYLES[alert.severity] ?? SEVERITY_STYLES.medium;

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      className={`${style.bg} ${style.border} rounded-lg border p-3`}
    >
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-bold text-red-200">
          {style.icon} {style.title}
        </p>
        <span className="rounded-md bg-red-500/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-red-300">
          R$ {alert.stake.toFixed(2)} · {alert.betOutcome}
        </span>
      </div>

      <p className="text-xs leading-relaxed text-red-100/90">{alert.message}</p>

      <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-slate-300">
        {alert.againstPregame && (
          <span>
            Pré-jogo: <strong className="text-white">{alert.pregamePalpite}</strong>{" "}
            ({formatPercent(alert.pregameProb)})
          </span>
        )}
        {alert.againstInplay && (
          <span>
            Ao vivo: <strong className="text-white">{alert.inplayPalpite}</strong>{" "}
            ({formatPercent(alert.inplayProb)})
          </span>
        )}
      </div>

      <p className="mt-2 text-[10px] text-slate-500">
        Você apostou em{" "}
        <span className="text-slate-300">{outcomeLabels[alert.betOutcome]}</span>
        {" · "}
        {alert.betOutcomeLabel}
      </p>
    </motion.div>
  );
}

/** Alerta vermelho quando bilhetes 1X2 divergem do palpite pré-jogo ou in-play. */
export default function LiveAgainstModelAlert({ alerts }: Props) {
  if (!alerts || alerts.length === 0) return null;

  const hasCritical = alerts.some((a) => a.severity === "critical");

  return (
    <section
      className={`rounded-xl border p-4 ${
        hasCritical
          ? "border-red-600/60 bg-red-950/40 shadow-[0_0_24px_rgba(239,68,68,0.12)]"
          : "border-red-700/40 bg-red-950/25"
      }`}
      aria-live="polite"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-bold text-red-200">
          {hasCritical
            ? "⛔ Não siga este bilhete — modelo discorda"
            : "⚠️ Atenção — aposta contra o palpite"}
        </h3>
        <span className="text-xs text-red-300/80">
          {alerts.length} alerta{alerts.length > 1 ? "s" : ""}
        </span>
      </div>

      <AnimatePresence>
        <div className="space-y-2">
          {alerts.map((alert, i) => (
            <AlertCard key={alert.betId ?? `draft-${i}`} alert={alert} />
          ))}
        </div>
      </AnimatePresence>
    </section>
  );
}
