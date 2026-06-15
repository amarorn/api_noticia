import { motion } from "framer-motion";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import { formatPercent } from "@/presentation/theme";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";

interface LiveHeader {
  currentScore: string | null;
  minute: number;
  periodLabel: string | null;
}

interface LiveDashboardHeroProps {
  data: SuperbetLiveAdvice;
  liveHeader: LiveHeader | null;
  adviceSource: "fast" | "full";
  onRefresh: () => void;
  isFetching: boolean;
}

function pickModelFavorite(data: SuperbetLiveAdvice) {
  const s = data.inplaySummary;
  const rows = [
    { key: "1" as const, team: data.homeTeam, prob: s.probFinalHome },
    { key: "X" as const, team: "Empate", prob: s.probFinalDraw },
    { key: "2" as const, team: data.awayTeam, prob: s.probFinalAway },
  ];
  return rows.reduce((a, b) => (b.prob > a.prob ? b : a));
}

export function LiveDashboardHero({
  data,
  liveHeader,
  adviceSource,
  onRefresh,
  isFetching,
}: LiveDashboardHeroProps) {
  const score =
    liveHeader?.currentScore?.replace("x", " × ") ??
    data.currentScore?.replace("x", " × ") ??
    "0 × 0";
  const minute = liveHeader?.minute ?? data.minute;
  const period = liveHeader?.periodLabel ?? data.periodLabel;
  const fav = pickModelFavorite(data);
  const topOpp = data.strategy?.opportunities[0];

  const directionLabel =
    topOpp && topOpp.tier !== "abaixo_limiar"
      ? topOpp.label
      : data.strategy?.posture === "agressivo"
        ? "Buscar valor"
        : data.strategy?.posture === "defensivo"
          ? "Proteger banca"
          : "Aguardar sinal";

  const directionTone =
    topOpp && topOpp.tier !== "abaixo_limiar"
      ? "from-neon-green/20 via-emerald-500/10 to-transparent border-neon-green/30"
      : "from-amber-500/15 via-orange-500/5 to-transparent border-amber-500/25";

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-slate-900/80 via-slate-900/40 to-slate-950/90 p-5 shadow-[0_24px_80px_rgba(0,0,0,0.45)] backdrop-blur-xl"
    >
      <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-neon-green/10 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-20 -left-10 h-40 w-40 rounded-full bg-neon-blue/10 blur-3xl" />

      <div className="relative flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 flex-1 flex-col gap-4 lg:flex-row lg:items-center">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <TeamFlag team={data.homeTeam} size={44} />
            <div className="min-w-0 flex-1 text-center lg:text-left">
              <p className="truncate text-sm font-medium text-slate-300">{data.homeTeam}</p>
            </div>
          </div>

          <div className="flex shrink-0 flex-col items-center px-2">
            <p className="font-mono text-4xl font-bold tracking-tight text-white">{score}</p>
            <div className="mt-1 flex items-center gap-2 rounded-full border border-white/10 bg-black/30 px-3 py-1 text-xs font-semibold text-amber-200">
              {data.isLive && !data.isFinished && (
                <span className="h-2 w-2 animate-pulse rounded-full bg-red-500" />
              )}
              <span>
                {minute}&apos;{period ? ` · ${period}` : ""}
              </span>
            </div>
          </div>

          <div className="flex min-w-0 flex-1 items-center justify-end gap-3">
            <div className="min-w-0 text-right">
              <p className="truncate text-sm font-medium text-slate-300">{data.awayTeam}</p>
            </div>
            <TeamFlag team={data.awayTeam} size={44} />
          </div>
        </div>

        <button
          type="button"
          onClick={onRefresh}
          disabled={isFetching}
          className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-400 transition hover:border-white/20 hover:text-white disabled:opacity-50"
        >
          {isFetching ? "Atualizando…" : adviceSource === "full" ? "Completo" : "Rápido"}
        </button>
      </div>

      <div
        className={`relative mt-5 rounded-2xl border bg-gradient-to-r px-4 py-3 ${directionTone}`}
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500">
              Direcionamento agora
            </p>
            <p className="mt-1 text-lg font-semibold text-white">{directionLabel}</p>
            <p className="mt-0.5 text-xs text-slate-400">
              Modelo favorece {fav.team} ({formatPercent(fav.prob)})
              {topOpp && topOpp.tier !== "abaixo_limiar"
                ? ` · EV ${(topOpp.expectedValue * 100).toFixed(1)}%`
                : ""}
            </p>
          </div>
          <div className="flex gap-2">
            {[
              { label: "1", prob: data.inplaySummary.probFinalHome, color: "#00ff88" },
              { label: "X", prob: data.inplaySummary.probFinalDraw, color: "#00d4ff" },
              { label: "2", prob: data.inplaySummary.probFinalAway, color: "#a855f7" },
            ].map(({ label, prob, color }) => (
              <div
                key={label}
                className="flex min-w-[52px] flex-col items-center rounded-xl border border-white/10 bg-black/25 px-2 py-2"
              >
                <span className="text-[10px] font-bold" style={{ color }}>
                  {label}
                </span>
                <span className="font-mono text-sm font-semibold text-white">
                  {(prob * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </motion.section>
  );
}
