import { useState } from "react";
import { formatPercent } from "@/presentation/theme";

interface StandaloneEvPanelProps {
  homeTeam: string;
  awayTeam: string;
  probabilities: Record<string, number> | undefined;
}

const MARKET_OPTIONS = [
  { value: "1", label: "Vitória mandante (1)" },
  { value: "X", label: "Empate (X)" },
  { value: "2", label: "Vitória visitante (2)" },
] as const;

function computeEv(prob: number, odd: number): number {
  if (odd <= 1 || prob <= 0) return -1;
  return prob * odd - 1;
}

function classifyEv(ev: number): { label: string; tone: string } {
  if (ev <= 0) return { label: "Evitar — EV negativo", tone: "text-red-400" };
  if (ev <= 0.05) return { label: "Sem valor — EV ≤ 5%", tone: "text-amber-300" };
  if (ev <= 0.1) return { label: "Observar — value leve", tone: "text-yellow-300" };
  return { label: "Value bet — EV > 10%", tone: "text-emerald-400" };
}

export function StandaloneEvPanel({ homeTeam, awayTeam, probabilities }: StandaloneEvPanelProps) {
  const [market, setMarket] = useState<string>("1");
  const [manualOdd, setManualOdd] = useState("");

  const prob = probabilities?.[market] ?? 0;
  const odd = Number.parseFloat(manualOdd.replace(",", "."));
  const hasOdd = Number.isFinite(odd) && odd > 1;
  const ev = hasOdd ? computeEv(prob, odd) : null;
  const recommendation = ev != null ? classifyEv(ev) : null;
  const showRecommendation = ev != null && ev > 0.05;

  return (
    <section className="glass-card space-y-4 p-4">
      <div>
        <h3 className="text-sm font-semibold text-white">Palpite avulso — EV manual</h3>
        <p className="mt-1 text-xs text-slate-400">
          {homeTeam || "Mandante"} × {awayTeam || "Visitante"} — recomendação só com EV &gt; 5%
        </p>
      </div>

      {!probabilities ? (
        <p className="text-xs text-slate-500">Gere o palpite acima para ver probabilidades do modelo.</p>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            {MARKET_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setMarket(opt.value)}
                className={`rounded-lg border px-3 py-2 text-left text-xs ${
                  market === opt.value
                    ? "border-neon-green/40 bg-neon-green/10 text-neon-green"
                    : "border-white/8 text-slate-300"
                }`}
              >
                <span className="block font-medium">{opt.label}</span>
                <span className="font-mono text-[11px] opacity-80">
                  P = {formatPercent(probabilities[opt.value] ?? 0)}
                </span>
              </button>
            ))}
          </div>

          <label className="block text-xs text-slate-400">
            Odd manual (opcional)
            <input
              type="text"
              inputMode="decimal"
              placeholder="Ex: 2.35"
              value={manualOdd}
              onChange={(e) => setManualOdd(e.target.value)}
              className="mt-1 w-full rounded-lg border border-white/8 bg-black/25 px-3 py-2 font-mono text-sm text-white"
            />
          </label>

          {hasOdd && ev != null && (
            <div className="rounded-lg border border-white/8 bg-slate-900/40 p-3 text-xs">
              <p className="text-slate-400">
                Prob. modelo: <span className="font-mono text-white">{formatPercent(prob)}</span>
              </p>
              <p className="text-slate-400">
                EV:{" "}
                <span className={`font-mono font-semibold ${ev > 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {(ev * 100).toFixed(1)}%
                </span>
              </p>
              <p className={`mt-2 font-semibold ${recommendation?.tone}`}>{recommendation?.label}</p>
              {showRecommendation ? (
                <p className="mt-1 text-emerald-300/90">
                  Recomendação: considerar entrada conservadora neste mercado.
                </p>
              ) : (
                <p className="mt-1 text-slate-500">Não recomendar — EV insuficiente ou negativo.</p>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}
