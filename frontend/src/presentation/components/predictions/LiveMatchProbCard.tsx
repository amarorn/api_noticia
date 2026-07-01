import type { SuperbetLiveAdvice } from "@/domain/entities";

interface Props {
  data: SuperbetLiveAdvice;
}

const HOME_COLOR = "#38bdf8";
const DRAW_COLOR = "#94a3b8";
const AWAY_COLOR = "#fb923c";

// ── Anel circular ──────────────────────────────────────────────────────────────
function ProbRing({ prob, color, label }: { prob: number; color: string; label: string }) {
  const pct = Math.round(prob * 100);
  const r = 26;
  const circ = 2 * Math.PI * r;
  const filled = (pct / 100) * circ;
  return (
    <div className="relative flex h-[68px] w-[68px] shrink-0 items-center justify-center">
      <svg viewBox="0 0 64 64" className="absolute inset-0 h-full w-full -rotate-90">
        <circle cx="32" cy="32" r={r} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="5.5" />
        <circle
          cx="32" cy="32" r={r} fill="none" stroke={color} strokeWidth="5.5"
          strokeDasharray={`${filled.toFixed(2)} ${circ.toFixed(2)}`}
          strokeLinecap="round"
          style={{ transition: "stroke-dasharray 0.6s ease" }}
        />
      </svg>
      <div className="flex flex-col items-center">
        <span className="font-mono text-base font-bold leading-none text-white">{pct}%</span>
        <span className="mt-0.5 text-[9px] font-semibold uppercase tracking-wide" style={{ color }}>
          {label}
        </span>
      </div>
    </div>
  );
}

// ── Linha de stat home | label | away ─────────────────────────────────────────
function StatRow({
  label,
  homeVal,
  awayVal,
  format = (v: number) => String(v),
  icon,
}: {
  label: string;
  homeVal: number | null | undefined;
  awayVal: number | null | undefined;
  format?: (v: number) => string;
  icon?: string;
}) {
  if (homeVal == null && awayVal == null) return null;
  const h = homeVal ?? 0;
  const a = awayVal ?? 0;
  const homeWins = h > a;
  const awayWins = a > h;
  return (
    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-1 text-[11px]">
      <span
        className="text-right font-mono font-semibold"
        style={{ color: homeWins ? HOME_COLOR : "#64748b" }}
      >
        {format(h)}
      </span>
      <span className="w-20 text-center text-[9px] text-slate-500">
        {icon} {label}
      </span>
      <span
        className="text-left font-mono font-semibold"
        style={{ color: awayWins ? AWAY_COLOR : "#64748b" }}
      >
        {format(a)}
      </span>
    </div>
  );
}

// ── Barra de posse ─────────────────────────────────────────────────────────────
function PossessionBar({ homePct }: { homePct: number }) {
  return (
    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-1 text-[11px]">
      <span className="text-right font-mono font-semibold" style={{ color: HOME_COLOR }}>
        {Math.round(homePct)}%
      </span>
      <div className="relative h-1.5 w-20 overflow-hidden rounded-full bg-white/8">
        <div
          className="absolute inset-y-0 left-0 rounded-full transition-all duration-500"
          style={{ width: `${homePct}%`, backgroundColor: HOME_COLOR, opacity: 0.7 }}
        />
      </div>
      <span className="text-left font-mono font-semibold" style={{ color: AWAY_COLOR }}>
        {Math.round(100 - homePct)}%
      </span>
    </div>
  );
}

// ── Label de seção ─────────────────────────────────────────────────────────────
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 pb-1 pt-0.5">
      <span className="text-[9px] font-bold uppercase tracking-widest text-slate-600">
        {children}
      </span>
      <span className="h-px flex-1 bg-white/5" />
    </div>
  );
}

// ── H2H summary bar ────────────────────────────────────────────────────────────
function H2hBar({
  homeWins, draws, awayWins, sinceYear,
}: {
  homeWins: number; draws: number; awayWins: number; sinceYear: number | null;
}) {
  const total = homeWins + draws + awayWins;
  if (total === 0) return null;
  const hw = (homeWins / total) * 100;
  const dw = (draws / total) * 100;
  const aw = (awayWins / total) * 100;
  return (
    <div className="space-y-1.5">
      <div className="flex h-5 overflow-hidden rounded-lg">
        {hw > 0 && (
          <div style={{ width: `${hw}%`, backgroundColor: "rgba(14,116,144,0.55)" }}
            className="flex items-center justify-center">
            <span className="font-mono text-[10px] font-bold" style={{ color: HOME_COLOR }}>{homeWins}</span>
          </div>
        )}
        {dw > 0 && (
          <div style={{ width: `${dw}%`, backgroundColor: "rgba(71,85,105,0.55)" }}
            className="flex items-center justify-center">
            <span className="font-mono text-[10px] font-bold text-slate-400">{draws}</span>
          </div>
        )}
        {aw > 0 && (
          <div style={{ width: `${aw}%`, backgroundColor: "rgba(194,65,12,0.45)" }}
            className="flex items-center justify-center">
            <span className="font-mono text-[10px] font-bold" style={{ color: AWAY_COLOR }}>{awayWins}</span>
          </div>
        )}
      </div>
      <div className="flex justify-between px-0.5 text-[9px] text-slate-600">
        <span style={{ color: HOME_COLOR, opacity: 0.7 }}>Vitórias casa</span>
        <span>{sinceYear ? `desde ${sinceYear}` : `${total} jogos`}</span>
        <span style={{ color: AWAY_COLOR, opacity: 0.7 }}>Vitórias fora</span>
      </div>
    </div>
  );
}

// ── Componente principal ───────────────────────────────────────────────────────
export function LiveMatchProbCard({ data }: Props) {
  const s = data.inplaySummary;
  const stats = data.liveStats;
  const h2h = data.scorealarm?.h2h ?? null;

  const segments = [
    { key: "1", label: data.homeTeam, prob: s.probFinalHome, barBg: "rgba(14,116,144,0.45)", color: HOME_COLOR },
    { key: "X", label: "Empate",       prob: s.probFinalDraw, barBg: "rgba(71,85,105,0.55)",  color: DRAW_COLOR },
    { key: "2", label: data.awayTeam,  prob: s.probFinalAway, barBg: "rgba(194,65,12,0.45)", color: AWAY_COLOR },
  ];
  const leading = segments.reduce((a, b) => (b.prob > a.prob ? b : a));

  const topOpp = data.strategy?.opportunities?.find((o) => o.tier !== "abaixo_limiar");

  const ngHome  = s.probNextGoalHome ?? null;
  const ngAway  = s.probNextGoalAway ?? null;
  const ngNone  = s.probNoMoreGoals ?? null;
  // Stats disponíveis
  const hasPoss    = stats?.homePossessionPct != null && stats?.awayPossessionPct != null;
  const hasXg      = stats?.homeXg != null || stats?.awayXg != null;
  const hasNextGoal = ngHome != null || ngAway != null;
  const hasH2h     = h2h != null && (h2h.homeWins + h2h.draws + h2h.awayWins) > 0;

  return (
    <section className="overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-slate-900/80 via-slate-900/50 to-slate-950/90 backdrop-blur-sm">

      {/* ── Topo: times + anel ── */}
      <div className="flex items-center gap-3 px-4 pb-3 pt-4">
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-sm font-bold" style={{ color: HOME_COLOR }}>
            {data.homeTeam}
          </span>
          {ngHome != null && (
            <span className="mt-0.5 text-[10px] text-slate-500">
              {Math.round(ngHome * 100)}% próx. gol
            </span>
          )}
        </div>
        <div className="shrink-0 px-2 text-center">
          <span className="text-xs font-bold text-slate-600">VS</span>
        </div>
        <div className="flex min-w-0 flex-1 flex-col items-end">
          <span className="truncate text-sm font-bold" style={{ color: AWAY_COLOR }}>
            {data.awayTeam}
          </span>
          {ngAway != null && (
            <span className="mt-0.5 text-[10px] text-slate-500">
              {Math.round(ngAway * 100)}% próx. gol
            </span>
          )}
        </div>
        <ProbRing prob={leading.prob} color={leading.color} label={leading.key} />
      </div>

      {/* ── Barra 1X2 ── */}
      <div className="px-4">
        <div className="flex h-7 overflow-hidden rounded-xl">
          {segments.map(({ key, prob, barBg, color }) => {
            const pct = prob * 100;
            if (pct < 1) return null;
            return (
              <div
                key={key}
                style={{
                  width: `${pct.toFixed(1)}%`,
                  backgroundColor: barBg,
                  minWidth: "36px",
                  borderRight: key !== "2" ? "1px solid rgba(0,0,0,0.25)" : undefined,
                }}
                className="flex items-center justify-center transition-all duration-500"
              >
                <span className="font-mono text-[11px] font-bold" style={{ color }}>
                  {Math.round(pct)}%
                </span>
              </div>
            );
          })}
        </div>
        <div className="mt-1 flex">
          {segments.map(({ key, label, prob, color }) => {
            const pct = prob * 100;
            if (pct < 1) return null;
            return (
              <div key={key} style={{ width: `${pct.toFixed(1)}%`, minWidth: "36px" }} className="flex justify-center">
                <span className="truncate text-[9px] font-medium" style={{ color, opacity: 0.75 }}>
                  {label === "Empate" ? "X" : label.split(" ")[0]}
                </span>
              </div>
            );
          })}
        </div>

        {/* Badge de confiança + sem gol */}
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-[11px]">
            <span className="font-bold" style={{ color: leading.color }}>{leading.key}</span>
            <span className="text-slate-400">{Math.round(leading.prob * 100)}% conf.</span>
          </span>
          {ngNone != null && (
            <span className="inline-flex items-center gap-1 text-[10px] text-slate-600">
              <span className="h-1.5 w-1.5 rounded-full bg-slate-700" />
              {Math.round(ngNone * 100)}% sem gol
            </span>
          )}
        </div>
      </div>

      {/* Stats compactas — xG e posse apenas (as demais ficam no LiveStatsProjectionPanel) */}
      {(hasPoss || hasXg || hasNextGoal) && (
        <div className="mt-3 space-y-1 border-t border-white/6 px-4 py-3">
          <SectionLabel>Stats ao vivo</SectionLabel>
          {hasPoss && <PossessionBar homePct={stats!.homePossessionPct!} />}
          {hasXg && (
            <StatRow label="xG" homeVal={stats?.homeXg} awayVal={stats?.awayXg}
              format={(v) => v.toFixed(2)} icon="⚽" />
          )}
          {hasNextGoal && (
            <StatRow label="Próx. gol" homeVal={ngHome} awayVal={ngAway}
              format={(v) => `${Math.round(v * 100)}%`} icon="⚡" />
          )}
        </div>
      )}

      {/* ── H2H ── */}
      {hasH2h && (
        <div className="space-y-2 border-t border-white/6 px-4 py-3">
          <SectionLabel>Histórico H2H</SectionLabel>
          <H2hBar
            homeWins={h2h!.homeWins}
            draws={h2h!.draws}
            awayWins={h2h!.awayWins}
            sinceYear={h2h!.sinceYear}
          />
        </div>
      )}

      {/* ── Oportunidade top ── */}
      {topOpp && (
        <div className="flex items-center justify-between border-t border-white/6 px-4 py-2.5">
          <div className="flex min-w-0 items-center gap-2">
            <span className="text-sm">🔥</span>
            <span className="truncate text-sm text-white">{topOpp.label}</span>
            {topOpp.edgePp > 0 && (
              <span className="shrink-0 rounded bg-neon-green/10 px-1.5 py-0.5 text-[10px] font-semibold text-neon-green">
                +{topOpp.edgePp.toFixed(1)}pp
              </span>
            )}
          </div>
          {topOpp.marketOdd > 0 && (
            <span className="ml-3 shrink-0 font-mono text-sm font-bold text-neon-green">
              {topOpp.marketOdd.toFixed(2)}
            </span>
          )}
        </div>
      )}
    </section>
  );
}
