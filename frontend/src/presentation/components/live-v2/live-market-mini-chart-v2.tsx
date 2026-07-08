import type { OddsHistoryPoint } from "@/presentation/components/live-operational/useMarketOperationalRows";

function normalize(points: OddsHistoryPoint[]) {
  if (points.length === 0) return [];
  const values = points.map((p) => p.odd);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 0.01);
  return values.map((v) => 14 + ((max - v) / range) * 68);
}

const GRID_LINES_Y = [14, 48, 82];

export function LiveMarketMiniChartV2({ label, points }: { label: string; points: OddsHistoryPoint[] }) {
  const y = normalize(points);
  const polyline =
    y.length > 1 ? y.map((yy, idx) => `${8 + idx * (184 / Math.max(y.length - 1, 1))},${yy}`).join(" ") : "";
  const last = y[y.length - 1];
  const lastX = 8 + (y.length - 1) * (184 / Math.max(y.length - 1, 1));

  return (
    <section className="panel-v2 p-4 sm:p-5">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-xs font-black uppercase tracking-[0.12em] text-slate-400">Evolução da odd</h2>
          <p className="truncate text-xs text-slate-500">{label || "Mercado recomendado"}</p>
        </div>
        <span className="chip-v2">{points.length} capturas</span>
      </div>
      <div className="panel-soft-v2 mt-3 h-32 overflow-hidden">
        {points.length > 1 ? (
          <svg viewBox="0 0 200 96" className="h-full w-full" role="img" aria-label="Evolução da odd">
            <defs>
              <linearGradient id="mini-chart-area-v2" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgba(45,212,191,0.35)" />
                <stop offset="100%" stopColor="rgba(45,212,191,0)" />
              </linearGradient>
            </defs>
            {GRID_LINES_Y.map((gy) => (
              <line key={gy} x1="8" y1={gy} x2="192" y2={gy} stroke="rgba(148,163,184,0.12)" strokeWidth="1" />
            ))}
            <polygon points={`8,96 ${polyline} ${lastX},96`} fill="url(#mini-chart-area-v2)" stroke="none" />
            <polyline points={polyline} fill="none" stroke="rgb(45,212,191)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            {last != null && <circle cx={lastX} cy={last} r="3.2" fill="#22d3ee" stroke="#020617" strokeWidth="1.4" />}
          </svg>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-1 text-slate-500">
            <span className="text-xs font-semibold">Histórico insuficiente</span>
            <span className="text-[10px] text-slate-600">Aguardando mais capturas desse mercado</span>
          </div>
        )}
      </div>
    </section>
  );
}
