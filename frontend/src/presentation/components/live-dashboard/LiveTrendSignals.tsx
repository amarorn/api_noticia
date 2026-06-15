import { motion } from "framer-motion";
import type { SuperbetLiveAdvice } from "@/domain/entities";

interface LiveTrendSignalsProps {
  data: SuperbetLiveAdvice;
}

const urgencyStyles: Record<string, string> = {
  alta: "border-red-500/40 bg-red-500/10 text-red-200",
  media: "border-amber-500/35 bg-amber-500/10 text-amber-200",
  baixa: "border-sky-500/30 bg-sky-500/10 text-sky-200",
};

export function LiveTrendSignals({ data }: LiveTrendSignalsProps) {
  const report = data.trendReport;
  if (!report || (report.signals.length === 0 && !report.positionAdvice)) return null;

  const advice = report.positionAdvice;

  return (
    <section className="rounded-2xl border border-violet-500/20 bg-violet-500/[0.04] p-4">
      <h2 className="text-sm font-semibold text-white">Sinais de tendência</h2>
      <p className="text-[11px] text-slate-500">Momentum e reposicionamento sugerido</p>

      {advice && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className={`mt-4 rounded-xl border px-4 py-3 ${urgencyStyles[advice.urgency] ?? urgencyStyles.baixa}`}
        >
          <p className="text-[10px] font-bold uppercase tracking-widest opacity-70">
            {advice.action.replace(/_/g, " ")} · urgência {advice.urgency}
          </p>
          <p className="mt-1 text-sm font-medium">{advice.reasoning}</p>
          {advice.repositionDetail && (
            <p className="mt-2 text-xs opacity-90">
              → {advice.repositionDetail}
              {advice.repositionOdd ? ` @ ${advice.repositionOdd.toFixed(2)}` : ""}
            </p>
          )}
        </motion.div>
      )}

      {report.signals.length > 0 && (
        <ul className="mt-4 space-y-2">
          {report.signals.slice(0, 5).map((signal) => (
            <li
              key={`${signal.type}-${signal.minute}-${signal.description.slice(0, 20)}`}
              className="flex items-start gap-3 rounded-xl border border-white/8 bg-black/20 px-3 py-2.5"
            >
              <span
                className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/5 text-xs font-bold text-violet-300"
                title="Força do sinal"
              >
                {Math.round(signal.strength * 100)}
              </span>
              <div className="min-w-0">
                <p className="text-xs font-semibold text-white">
                  {signal.type.replace(/_/g, " ")} · {signal.direction}
                  {signal.minute != null ? ` (${signal.minute}')` : ""}
                </p>
                <p className="mt-0.5 text-xs text-slate-400">{signal.description}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
