import type { CornersProjection, SuperbetLiveAdvice } from "@/domain/entities";
import { formatPercent } from "@/presentation/theme";
import { formatLongshotProbPct } from "@/presentation/utils/longshotCombos";

interface LiveCornersPanelProps {
  data: SuperbetLiveAdvice;
}

function lineLabel(key: string): string {
  const body = key.replace(/^(over|under)_/, "").replace("_", ".");
  return body;
}

function resolveProjection(data: SuperbetLiveAdvice): {
  source: "halftime" | "live" | null;
  homeObs: number;
  awayObs: number;
  expectedFtHome: number;
  expectedFtAway: number;
  expectedFtTotal: number;
  probHomeMore: number;
  probDraw: number;
  probAwayMore: number;
  mostLikely: string | null;
  lineProbs: Record<string, number>;
} | null {
  const ht = data.halftimeReport;
  if (ht?.applied) {
    return {
      source: "halftime",
      homeObs: ht.corners.observed1hHome,
      awayObs: ht.corners.observed1hAway,
      expectedFtHome:
        ht.corners.observed1hHome + (ht.corners.expected2hHome ?? 0),
      expectedFtAway:
        ht.corners.observed1hAway + (ht.corners.expected2hAway ?? 0),
      expectedFtTotal: ht.corners.expectedFtTotal,
      probHomeMore: ht.corners.probHomeMoreCorners ?? 0,
      probDraw: 0,
      probAwayMore: 0,
      mostLikely: null,
      lineProbs: ht.cornerLineProbs,
    };
  }

  const live: CornersProjection | null | undefined = data.cornersProjection;
  if (live) {
    return {
      source: "live",
      homeObs: live.observedHome,
      awayObs: live.observedAway,
      expectedFtHome: live.expectedFtHome,
      expectedFtAway: live.expectedFtAway,
      expectedFtTotal: live.expectedFtTotal,
      probHomeMore: live.probHomeMoreCorners,
      probDraw: live.probDrawCorners,
      probAwayMore: live.probAwayMoreCorners,
      mostLikely: live.mostLikelyCorners,
      lineProbs: live.lineProbs,
    };
  }

  const lineProbs = data.inplaySummary.cornerLineProbs ?? {};
  if (Object.keys(lineProbs).length === 0) return null;

  const homeObs = data.liveStats?.homeCorners ?? 0;
  const awayObs = data.liveStats?.awayCorners ?? 0;
  return {
    source: "live",
    homeObs,
    awayObs,
    expectedFtHome: homeObs,
    expectedFtAway: awayObs,
    expectedFtTotal: homeObs + awayObs,
    probHomeMore: 0,
    probDraw: 0,
    probAwayMore: 0,
    mostLikely: null,
    lineProbs,
  };
}

function cornerMarketRows(data: SuperbetLiveAdvice) {
  return (data.strategy?.marketScan ?? []).filter((r) => r.market.startsWith("corners_over_"));
}

/** Projeção Poisson de escanteios ao vivo + linhas vs Superbet. */
export function LiveCornersPanel({ data }: LiveCornersPanelProps) {
  if (data.isFinished) return null;

  const projection = resolveProjection(data);
  const cornerMarkets = cornerMarketRows(data);
  const hasCornersOdds = data.analysisCoverage?.corners ?? cornerMarkets.length > 0;

  if (!projection && !hasCornersOdds) return null;

  const lineKeys = projection
    ? [...new Set(Object.keys(projection.lineProbs).filter((k) => k.startsWith("over_")))].sort()
    : [];

  return (
    <section
      className="rounded-2xl border border-amber-500/20 bg-amber-500/[0.04] p-4"
      aria-label="Projeção de escanteios"
    >
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-amber-200">Escanteios — modelo ao vivo</h2>
          <p className="mt-0.5 text-[11px] text-slate-500">
            Poisson condicionado ao placar de cantos e minuto · linhas alinhadas à Superbet
          </p>
        </div>
        {projection?.source === "halftime" && (
          <span className="rounded-full border border-sky-400/30 bg-sky-500/10 px-2 py-0.5 text-[10px] text-sky-200">
            Recalibração intervalo
          </span>
        )}
      </div>

      {projection && (
        <>
          <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div className="rounded-lg border border-white/8 bg-black/20 px-3 py-2">
              <p className="text-[10px] uppercase text-slate-500">Agora</p>
              <p className="mt-0.5 font-mono text-lg font-bold text-white">
                {projection.homeObs}×{projection.awayObs}
              </p>
              <p className="text-[10px] text-slate-500">
                {data.homeTeam} × {data.awayTeam}
              </p>
            </div>
            <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2">
              <p className="text-[10px] uppercase text-slate-500">Total esperado FT</p>
              <p className="mt-0.5 font-mono text-lg font-bold text-amber-300">
                {projection.expectedFtTotal.toFixed(1)}
              </p>
              <p className="text-[10px] text-slate-500">
                ~{projection.expectedFtHome.toFixed(1)} / {projection.expectedFtAway.toFixed(1)}
              </p>
            </div>
            {projection.mostLikely && (
              <div className="rounded-lg border border-white/8 bg-black/20 px-3 py-2">
                <p className="text-[10px] uppercase text-slate-500">Placar provável</p>
                <p className="mt-0.5 font-mono text-lg font-bold text-neon-green">
                  {projection.mostLikely}
                </p>
              </div>
            )}
            <div className="rounded-lg border border-white/8 bg-black/20 px-3 py-2">
              <p className="text-[10px] uppercase text-slate-500">Mais escanteios</p>
              <p className="mt-0.5 text-xs text-slate-300">
                Casa {formatLongshotProbPct(projection.probHomeMore)}
              </p>
              <p className="text-xs text-slate-300">
                Fora {formatLongshotProbPct(projection.probAwayMore)}
              </p>
              {projection.probDraw > 0 && (
                <p className="text-[10px] text-slate-500">
                  Empate {formatLongshotProbPct(projection.probDraw)}
                </p>
              )}
            </div>
          </div>

          {lineKeys.length > 0 && (
            <div className="mb-3">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                Linhas de total (modelo)
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                {lineKeys.map((overKey) => {
                  const line = lineLabel(overKey);
                  const underKey = `under_${line.replace(".", "_")}`;
                  const overProb = projection.lineProbs[overKey] ?? 0;
                  const underProb = projection.lineProbs[underKey] ?? 1 - overProb;
                  const marketRow = cornerMarkets.find(
                    (r) => r.market === `corners_over_${line.replace(".", "_")}`,
                  );
                  return (
                    <div
                      key={overKey}
                      className="rounded-lg border border-white/8 bg-black/20 px-3 py-2 text-xs"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-mono text-slate-300">Total {line}</span>
                        {marketRow && (
                          <span className="font-mono text-amber-300">
                            @{marketRow.marketOdd.toFixed(2)}
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-slate-400">
                        <span className="text-neon-green">Mais {formatPercent(overProb)}</span>
                        <span className="mx-1 text-slate-600">·</span>
                        <span>Menos {formatPercent(underProb)}</span>
                      </p>
                      {marketRow && (
                        <p className="mt-0.5 text-[10px] text-slate-500">
                          EV mais {(marketRow.expectedValue * 100).toFixed(1)}% · edge{" "}
                          {marketRow.edgePp.toFixed(1)} pp
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}

      {!projection && cornerMarkets.length > 0 && (
        <p className="text-xs text-slate-500">
          Aguardando refresh completo (~60s) para projeção Poisson. Mercados de escanteios já
          disponíveis no scan.
        </p>
      )}

      <p className="text-[10px] leading-relaxed text-slate-600">
        Pré-jogo detalhado: página do jogo ou{" "}
        <code className="rounded bg-white/5 px-1">POST /worldcup/corners/predict</code>. Com
        histórico Sofascore o λ fica mais calibrado; sem lake usa proxy de gols.
      </p>
    </section>
  );
}
