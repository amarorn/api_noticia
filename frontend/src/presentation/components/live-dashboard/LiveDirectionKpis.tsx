import { motion } from "framer-motion";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import { formatPercent } from "@/presentation/theme";

interface LiveDirectionKpisProps {
  data: SuperbetLiveAdvice;
}

const cardMotion = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
};

function KpiCard({
  label,
  value,
  hint,
  accent,
  delay = 0,
}: {
  label: string;
  value: string;
  hint: string;
  accent: string;
  delay?: number;
}) {
  return (
    <motion.div
      {...cardMotion}
      transition={{ delay }}
      className="group relative overflow-hidden rounded-2xl border border-white/8 bg-white/[0.03] p-4 backdrop-blur-sm"
    >
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-0.5 opacity-80"
        style={{ background: accent }}
      />
      <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{label}</p>
      <p className="mt-2 font-mono text-xl font-bold text-white">{value}</p>
      <p className="mt-1 text-xs leading-relaxed text-slate-400">{hint}</p>
    </motion.div>
  );
}

export function LiveDirectionKpis({ data }: LiveDirectionKpisProps) {
  const top = data.strategy?.opportunities[0];
  const scanBest = [...(data.strategy?.marketScan ?? [])]
    .filter((r) => r.expectedValue > 0)
    .sort((a, b) => b.expectedValue - a.expectedValue)[0];
  const trend = data.trendReport?.positionAdvice;
  const conf = data.confidence;

  const postureLabel: Record<string, string> = {
    agressivo: "Agressivo",
    neutro: "Neutro",
    defensivo: "Defensivo",
  };

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <KpiCard
        label="Postura"
        value={postureLabel[data.strategy?.posture ?? "neutro"] ?? "Neutro"}
        hint={
          data.strategy?.waitReason ||
          `${data.strategy?.opportunityCount ?? 0} oportunidades mapeadas`
        }
        accent="#00ff88"
        delay={0.05}
      />
      <KpiCard
        label="Melhor EV"
        value={
          top && top.tier !== "abaixo_limiar"
            ? `+${(top.expectedValue * 100).toFixed(1)}%`
            : scanBest
              ? `+${(scanBest.expectedValue * 100).toFixed(1)}%`
              : "—"
        }
        hint={
          top && top.tier !== "abaixo_limiar"
            ? top.label
            : scanBest
              ? scanBest.label
              : "Sem valor acima do limiar"
        }
        accent="#38bdf8"
        delay={0.1}
      />
      <KpiCard
        label="Confiança modelo"
        value={conf ? `${Math.round(conf.score * 100)}%` : "—"}
        hint={conf?.reason ?? "Sem leitura de confiança"}
        accent="#a855f7"
        delay={0.15}
      />
      <KpiCard
        label="Tendência jogo"
        value={
          trend?.action
            ? trend.action.replace(/_/g, " ")
            : data.trendReport?.dominantTrend?.replace(/_/g, " ") ?? "Neutra"
        }
        hint={
          trend?.reasoning ??
          (data.inplaySummary.over25 != null
            ? `Over 2.5 ${formatPercent(data.inplaySummary.over25)} · BTTS ${formatPercent(data.inplaySummary.btts ?? 0)}`
            : "Aguardando sinais")
        }
        accent="#fbbf24"
        delay={0.2}
      />
    </div>
  );
}
