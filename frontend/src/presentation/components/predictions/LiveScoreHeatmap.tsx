import { useMemo } from "react";
import type { SuperbetLiveAdvice } from "@/domain/entities";

// ── Aproximação Poisson ────────────────────────────────────────────────────

function poissonProb(lambda: number, k: number): number {
  if (lambda <= 0) return k === 0 ? 1 : 0;
  let result = Math.exp(-lambda);
  for (let i = 1; i <= k; i++) result = (result * lambda) / i;
  return result;
}

/**
 * Estima λ_home e λ_away por grid search minimizando erro contra
 * as probabilidades de resultado final (home/draw/away).
 */
function estimateLambdas(probHome: number, probAway: number): [number, number] {
  let bestLh = 1.2,
    bestLa = 0.9,
    bestErr = Infinity;
  for (let lhStep = 2; lhStep <= 30; lhStep++) {
    const lh = lhStep * 0.15;
    for (let laStep = 2; laStep <= 30; laStep++) {
      const la = laStep * 0.15;
      let ph = 0,
        pa = 0;
      for (let h = 0; h <= 6; h++) {
        const ph_k = poissonProb(lh, h);
        for (let a = 0; a <= 6; a++) {
          const p = ph_k * poissonProb(la, a);
          if (h > a) ph += p;
          else if (a > h) pa += p;
        }
      }
      const err = Math.abs(ph - probHome) + Math.abs(pa - probAway);
      if (err < bestErr) {
        bestErr = err;
        bestLh = lh;
        bestLa = la;
      }
    }
  }
  return [bestLh, bestLa];
}

/**
 * Gera matriz de probabilidades de placar para um grid MAX_H x MAX_A.
 */
function buildScoreMatrix(
  lh: number,
  la: number,
  maxH = 4,
  maxA = 4,
): number[][] {
  return Array.from({ length: maxH + 1 }, (_, h) =>
    Array.from({ length: maxA + 1 }, (_, a) => poissonProb(lh, h) * poissonProb(la, a)),
  );
}

// ── Componente ─────────────────────────────────────────────────────────────

interface LiveScoreHeatmapProps {
  data: SuperbetLiveAdvice;
}

export function LiveScoreHeatmap({ data }: LiveScoreHeatmapProps) {
  const s = data.inplaySummary;

  const { matrix, maxProb, isApprox, topEntries } = useMemo(() => {
    // Preferência: scores vindos do backend (Monte Carlo)
    if (s.topFinalScores && Object.keys(s.topFinalScores).length > 0) {
      const matrix: number[][] = Array.from({ length: 5 }, () => Array(5).fill(0));
      Object.entries(s.topFinalScores).forEach(([score, prob]) => {
        const [h, a] = score.split("-").map(Number);
        if (h >= 0 && h <= 4 && a >= 0 && a <= 4) matrix[h][a] = prob;
      });
      const flat = matrix.flat().filter(Boolean);
      const max = flat.length > 0 ? Math.max(...flat) : 0.01;
      const entries = Object.entries(s.topFinalScores)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5);
      return { matrix, maxProb: max, isApprox: false, topEntries: entries };
    }

    // Fallback: estimativa Poisson a partir das probabilidades finais
    const [lh, la] = estimateLambdas(s.probFinalHome, s.probFinalAway);
    const mat = buildScoreMatrix(lh, la, 4, 4);
    const flat = mat.flat();
    const max = Math.max(...flat, 0.01);
    const entries: [string, number][] = [];
    mat.forEach((row, h) =>
      row.forEach((prob, a) => entries.push([`${h}-${a}`, prob])),
    );
    entries.sort((a, b) => b[1] - a[1]);
    return { matrix: mat, maxProb: max, isApprox: true, topEntries: entries.slice(0, 5) };
  }, [s]);

  const awayLabels = [0, 1, 2, 3, 4];
  const homeLabels = [0, 1, 2, 3, 4];

  return (
    <section className="rounded-2xl border border-white/8 bg-white/[0.02] p-4">
      {/* Cabeçalho */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-white">Placares mais prováveis</h2>
          <p className="text-[11px] text-slate-500">
            {isApprox ? "Aproximação Poisson" : "Simulação Monte Carlo"} · intensidade =
            probabilidade
          </p>
        </div>
        {/* Top 3 placares */}
        <div className="flex flex-wrap items-center gap-1.5">
          {topEntries.slice(0, 3).map(([score, prob], i) => (
            <span
              key={score}
              className={`rounded-lg border px-2.5 py-1 font-mono text-xs font-semibold ${
                i === 0
                  ? "border-white/20 bg-white/8 text-white"
                  : "border-white/8 bg-white/[0.03] text-slate-300"
              }`}
            >
              {score.replace("-", "–")}{" "}
              <span className="text-[10px] font-normal text-slate-400">
                {(prob * 100).toFixed(1)}%
              </span>
            </span>
          ))}
        </div>
      </div>

      {/* Grid */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[280px] border-collapse text-center">
          <thead>
            <tr>
              <th className="pb-2 pr-1 text-right text-[10px] font-normal text-slate-600">
                <span className="text-neon-green/70">{data.homeTeam.split(" ")[0]}</span>
                {" ↓ / "}
                <span className="text-sky-400/70">{data.awayTeam.split(" ")[0]}</span>
                {" →"}
              </th>
              {awayLabels.map((a) => (
                <th key={a} className="w-12 pb-2 text-[11px] font-semibold text-sky-400">
                  {a}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {homeLabels.map((h) => (
              <tr key={h}>
                <td className="py-0.5 pr-1 text-right text-[11px] font-semibold text-neon-green">
                  {h}
                </td>
                {awayLabels.map((a) => {
                  const prob = matrix[h]?.[a] ?? 0;
                  const intensity = maxProb > 0 ? prob / maxProb : 0;
                  const isHomeWin = h > a;
                  const isDraw = h === a;
                  // Cores: verde (casa vence), âmbar (empate), azul (fora vence)
                  const r = isDraw ? 251 : isHomeWin ? 0 : 56;
                  const g = isDraw ? 191 : isHomeWin ? 255 : 189;
                  const b = isDraw ? 36 : isHomeWin ? 136 : 248;
                  const alpha = Math.min(0.75, intensity * 0.75);
                  const isTopScore = topEntries
                    .slice(0, 3)
                    .some(([k]) => k === `${h}-${a}`);

                  return (
                    <td key={a} className="p-0.5">
                      <div
                        className={`flex h-10 w-full items-center justify-center rounded-lg transition-all duration-500 ${
                          isTopScore ? "ring-1 ring-white/25" : ""
                        }`}
                        style={{ backgroundColor: `rgba(${r},${g},${b},${alpha})` }}
                        title={`${h}–${a}: ${(prob * 100).toFixed(1)}%`}
                      >
                        <span
                          className={`font-mono text-[10px] font-bold ${
                            intensity > 0.55
                              ? "text-white"
                              : intensity > 0.2
                                ? "text-slate-300"
                                : "text-slate-600"
                          }`}
                        >
                          {prob > 0.001 ? `${(prob * 100).toFixed(1)}%` : "·"}
                        </span>
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legenda */}
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-[10px] text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-4 rounded bg-neon-green/40" />
          {data.homeTeam} vence
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-4 rounded bg-amber-400/40" />
          Empate
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-4 rounded bg-sky-400/40" />
          {data.awayTeam} vence
        </span>
        {isApprox && (
          <span className="text-slate-600">
            · estimativa independente do modelo in-play; atualiza com backend
          </span>
        )}
      </div>
    </section>
  );
}
