import { motion, AnimatePresence } from "framer-motion";
import type { BetAdvice } from "@/infrastructure/hooks/useHedgeReport";
import type { HedgeReport } from "@/infrastructure/hooks/useHedgeReport";

interface Props {
  report: HedgeReport | null;
}

const URGENCY_STYLES: Record<string, { bg: string; border: string; icon: string }> = {
  critical: { bg: "bg-red-900/40", border: "border-red-500/60", icon: "🚨" },
  high: { bg: "bg-orange-900/30", border: "border-orange-500/50", icon: "⚠️" },
  medium: { bg: "bg-yellow-900/20", border: "border-yellow-500/40", icon: "🛡️" },
  low: { bg: "bg-emerald-900/20", border: "border-emerald-500/30", icon: "✓" },
};

const MARKET_LABELS: Record<string, string> = {
  h2h: "Resultado Final",
  btts: "Ambas Marcam",
  next_goal: "Próximo Gol",
};

function marketLabel(market: string): string {
  if (market.startsWith("totals")) {
    const line = market.split("_")[1] || "2.5";
    return `Total de Gols ${line}`;
  }
  return MARKET_LABELS[market] || market;
}

function outcomeLabel(outcome: string, market: string): string {
  if (market === "h2h") {
    if (outcome === "home" || outcome === "1") return "Casa vence";
    if (outcome === "away" || outcome === "2") return "Fora vence";
    if (outcome === "draw" || outcome === "X") return "Empate";
  }
  if (outcome === "over") return "Mais gols";
  if (outcome === "under") return "Menos gols";
  if (outcome === "yes") return "Sim";
  if (outcome === "no") return "Não";
  return outcome;
}

function AdviceCard({ advice }: { advice: BetAdvice }) {
  const style = URGENCY_STYLES[advice.urgency] || URGENCY_STYLES.low;

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className={`${style.bg} ${style.border} border rounded-lg p-3 mb-2`}
    >
      {/* Cabeçalho: ação + mercado */}
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-semibold text-slate-200">
          {style.icon} {advice.action === "cashout" && "CASH-OUT"}
          {advice.action === "hedge" && "PROTEGER"}
          {advice.action === "hold" && "MANTER"}
          {advice.action === "shift" && "MOVER"}
        </span>
        <span className="text-xs text-slate-400">
          {marketLabel(advice.market)} · {outcomeLabel(advice.outcome, advice.market)}
        </span>
      </div>

      {/* Detalhes da aposta */}
      <div className="flex items-center gap-3 text-xs text-slate-300 mb-1">
        <span>Stake R$ {advice.stake.toFixed(2)}</span>
        <span>@ {advice.odds_placed.toFixed(2)}</span>
        <span className={advice.ev_remaining >= 0 ? "text-emerald-400" : "text-red-400"}>
          EV {(advice.ev_remaining * 100).toFixed(0)}%
        </span>
        <span>Prob {(advice.prob_current * 100).toFixed(1)}%</span>
      </div>

      {/* Raciocínio */}
      <p className="text-xs text-slate-400 leading-relaxed">{advice.reasoning}</p>

      {/* Sugestão de hedge */}
      {advice.hedge && (
        <div className="mt-2 bg-slate-800/50 rounded p-2 border border-slate-600/30">
          <p className="text-xs text-amber-300 font-medium">
            Contra-aposta sugerida: R$ {advice.hedge.stake_suggested.toFixed(2)} em{" "}
            {outcomeLabel(advice.hedge.outcome, advice.hedge.market)} @ {advice.hedge.odd_current.toFixed(2)}
          </p>
          <p className="text-xs text-slate-400 mt-0.5">
            Garante R$ {advice.hedge.guaranteed_return.toFixed(2)} independente do resultado
          </p>
        </div>
      )}
    </motion.div>
  );
}

/**
 * Painel de alertas de hedge exibido no topo do Ao Vivo.
 * Mostra sugestões de proteção para apostas abertas do usuário.
 */
export default function LiveHedgeAlert({ report }: Props) {
  if (!report || report.advices.length === 0) return null;

  // Ordenar por urgência: critical > high > medium > low
  const urgencyOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
  const sorted = [...report.advices].sort(
    (a, b) => (urgencyOrder[a.urgency] ?? 4) - (urgencyOrder[b.urgency] ?? 4)
  );

  const hasCritical = sorted.some((a) => a.urgency === "critical");

  return (
    <div className={`rounded-xl p-4 mb-4 ${hasCritical ? "bg-red-950/30 border border-red-700/40" : "bg-slate-800/40 border border-slate-700/30"}`}>
      {/* Título */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-slate-200">
          {hasCritical ? "🚨 ALERTA — Suas Apostas" : "🎯 Suas Apostas · Monitor"}
        </h3>
        <span className="text-xs text-slate-400">
          R$ {report.total_at_risk.toFixed(0)} em risco · {report.advices.length} aposta(s)
        </span>
      </div>

      {/* Summary */}
      <p className="text-xs text-slate-300 mb-3">{report.summary}</p>

      {/* Cards de aconselhamento */}
      <AnimatePresence>
        {sorted.map((advice) => (
          <AdviceCard key={advice.bet_id} advice={advice} />
        ))}
      </AnimatePresence>
    </div>
  );
}
