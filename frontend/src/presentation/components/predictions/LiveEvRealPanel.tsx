import type { SuperbetLiveAdvice } from "@/domain/entities";
import {
  bestMarketRow,
  buildExtraMarketRows,
  buildH2hMarketRows,
  evDisplayTone,
  sensitivityOddSteps,
} from "@/presentation/utils/liveModelMarketRows";

interface LiveEvRealPanelProps {
  data: SuperbetLiveAdvice;
}

/** Melhor EV real (modelo × odd casa) + sensibilidade à movimentação de linha. */
export function LiveEvRealPanel({ data }: LiveEvRealPanelProps) {
  const threshold = data.strategy?.minEdgeThreshold ?? 0.04;
  const h2h = buildH2hMarketRows(data, threshold);
  const extra = buildExtraMarketRows(data, threshold, 8);
  const all = [...h2h, ...extra];
  const best = bestMarketRow(all);

  const topOpp = data.strategy?.opportunities?.[0] ?? null;
  const headline = topOpp ?? best;
  if (!headline) return null;

  const isOpp = topOpp != null;
  const modelProb = isOpp ? topOpp.modelProb : best!.modelProb;
  const marketOdd = isOpp ? topOpp.marketOdd : best!.marketOdd;
  const ev = isOpp ? topOpp.expectedValue : best!.expectedValue;
  const label = isOpp ? topOpp.label : best!.label;
  const tone = evDisplayTone(ev, threshold);
  const evPct = ev * 100;

  const sensitivity = sensitivityOddSteps(modelProb, marketOdd);
  const worseStep = sensitivity.find((s) => s.odd < marketOdd && s.ev < ev);

  return (
    <section className="glass-card p-4" aria-label="EV real modelo versus mercado">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            EV real · modelo × casa
          </h2>
          <p className="text-[10px] text-slate-600">
            Limiar forte +7% · fraco abaixo −10%
          </p>
        </div>
        <span
          className={`rounded-lg border px-2.5 py-1 font-mono text-sm font-bold ${tone.bg} ${tone.text}`}
        >
          {tone.icon} {evPct >= 0 ? "+" : ""}
          {evPct.toFixed(1)}%
        </span>
      </div>

      <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-3">
        <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
          Melhor leitura agora
        </p>
        <p className="mt-1 text-sm font-semibold text-white">{label}</p>
        <p className="mt-1 font-mono text-xs text-slate-400">
          Modelo {(modelProb * 100).toFixed(0)}% · odd {marketOdd.toFixed(2)} · EV{" "}
          {evPct >= 0 ? "+" : ""}
          {evPct.toFixed(1)}%
        </p>
        {worseStep && (
          <p className="mt-2 text-[11px] text-amber-300/90">
            Se a odd cair para {worseStep.odd.toFixed(2)}, EV ={" "}
            {(worseStep.ev * 100).toFixed(0)}%
          </p>
        )}
      </div>

      {best && isOpp && best.label !== topOpp.label && (
        <p className="mt-2 text-[10px] text-slate-600">
          Top EV scan: {best.label} @ {best.marketOdd.toFixed(2)} (
          {(best.expectedValue * 100).toFixed(1)}%)
        </p>
      )}
    </section>
  );
}
