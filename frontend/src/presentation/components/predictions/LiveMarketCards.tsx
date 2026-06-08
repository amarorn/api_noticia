import { useMemo, useState } from "react";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import { formatPercent } from "@/presentation/theme";

type MarketScanRow = NonNullable<SuperbetLiveAdvice["strategy"]>["marketScan"][number];
type Verdict = "apostar" | "quase" | "sem_valor" | "sem_odds";

interface MarketGroup {
  id: string;
  superbetName: string;
  matchMarket: (market: string) => boolean;
  note?: string;
}

const MARKET_GROUPS: MarketGroup[] = [
  {
    id: "h2h",
    superbetName: "Resultado Final",
    matchMarket: (m) => m === "h2h",
    note: "Pode suspender ao vivo — use Total ou 2º Gol se sumir.",
  },
  {
    id: "next_goal",
    superbetName: "2º Gol",
    matchMarket: (m) => m === "next_goal",
  },
  {
    id: "totals",
    superbetName: "Total de Gols",
    matchMarket: (m) => m.startsWith("over_"),
  },
  {
    id: "btts",
    superbetName: "Ambas as Equipes Marcam",
    matchMarket: (m) => m === "btts",
  },
];

const VERDICT_CONFIG: Record<Verdict, { label: string; cardClass: string; badgeClass: string; icon: string }> = {
  apostar: {
    label: "Apostar",
    cardClass: "border-neon-green/50 bg-neon-green/[0.07] shadow-[0_0_20px_rgba(0,255,136,0.06)]",
    badgeClass: "bg-neon-green/20 text-neon-green border border-neon-green/40",
    icon: "●",
  },
  quase: {
    label: "Quase",
    cardClass: "border-amber-500/40 bg-amber-500/[0.05]",
    badgeClass: "bg-amber-500/15 text-amber-300 border border-amber-500/35",
    icon: "◐",
  },
  sem_valor: {
    label: "Sem valor",
    cardClass: "border-white/10 bg-white/[0.02]",
    badgeClass: "bg-white/5 text-slate-400 border border-white/10",
    icon: "○",
  },
  sem_odds: {
    label: "Sem odds",
    cardClass: "border-white/6 bg-transparent opacity-60",
    badgeClass: "bg-white/[0.03] text-slate-600 border border-white/8",
    icon: "—",
  },
};

function buildFallbackScan(data: SuperbetLiveAdvice): MarketScanRow[] {
  const s = data.inplaySummary;
  const threshold = data.strategy?.minEdgeThreshold ?? 0.04;
  const rows: MarketScanRow[] = [];

  const push = (
    market: string,
    outcome: string,
    label: string,
    prob: number | undefined,
    odd: number | undefined,
  ) => {
    if (prob == null || prob <= 0 || odd == null || odd <= 1) return;
    const implied = 1 / odd;
    const ev = prob * odd - 1;
    rows.push({
      market,
      outcome,
      label,
      modelProb: prob,
      marketOdd: odd,
      impliedProb: implied,
      expectedValue: ev,
      edgePp: (prob - implied) * 100,
      suggestedStakePct: 0,
      suggestedStakeValue: 0,
      meetsThreshold: ev >= threshold,
    });
  };

  push("h2h", "1", `${data.homeTeam} vence`, s.probFinalHome, data.h2hOdds["1"]);
  push("h2h", "X", "Empate", s.probFinalDraw, data.h2hOdds["X"]);
  push("h2h", "2", `${data.awayTeam} vence`, s.probFinalAway, data.h2hOdds["2"]);
  push(
    "over_2_5",
    "yes",
    "Mais de 2.5 gols",
    s.over25,
    data.aportes.find((a) => a.market === "over_2_5")?.marketOdd,
  );
  push("btts", "yes", "Ambos marcam", s.btts, data.bttsOdds.yes);
  push(
    "btts",
    "no",
    "Ambos não marcam",
    s.btts != null ? 1 - s.btts : undefined,
    data.bttsOdds.no,
  );
  push(
    "next_goal",
    "home",
    `Próximo gol ${data.homeTeam}`,
    s.probNextGoalHome,
    data.nextGoalOdds.home,
  );
  push(
    "next_goal",
    "away",
    `Próximo gol ${data.awayTeam}`,
    s.probNextGoalAway,
    data.nextGoalOdds.away,
  );

  return rows;
}

function resolveVerdict(
  best: MarketScanRow | null,
  threshold: number,
): { verdict: Verdict; detail: string; stakeHint?: string } {
  if (!best) {
    return { verdict: "sem_odds", detail: "Superbet não enviou odd neste refresh" };
  }
  const evPct = best.expectedValue * 100;
  const gap = threshold * 100 - evPct;
  if (best.meetsThreshold) {
    const stakeHint =
      best.suggestedStakeValue > 0
        ? `R$ ${best.suggestedStakeValue.toFixed(0)} · ${best.suggestedStakePct}% da banca`
        : undefined;
    return {
      verdict: "apostar",
      detail: `EV +${evPct.toFixed(1)}% · edge ${best.edgePp >= 0 ? "+" : ""}${best.edgePp.toFixed(1)} pp`,
      stakeHint,
    };
  }
  if (best.expectedValue > 0) {
    return {
      verdict: "quase",
      detail: `EV +${evPct.toFixed(1)}% · faltam +${gap.toFixed(1)} pp`,
    };
  }
  return {
    verdict: "sem_valor",
    detail: `EV ${evPct.toFixed(1)}% · casa acima do modelo`,
  };
}

const DIRECTION_CONFIG: Record<
  string,
  { label: string; sub: string; bgClass: string; textClass: string }
> = {
  btts_yes: {
    label: "SIM",
    sub: "Apostar que ambas as equipes marcam",
    bgClass: "bg-neon-green/15 border-neon-green/30",
    textClass: "text-neon-green",
  },
  btts_no: {
    label: "NÃO",
    sub: "Apostar que ao menos uma equipe NÃO marca",
    bgClass: "bg-amber-500/15 border-amber-500/30",
    textClass: "text-amber-300",
  },
  totals_over: {
    label: "MAIS",
    sub: "Apostar que sairão MAIS gols que a linha",
    bgClass: "bg-neon-green/15 border-neon-green/30",
    textClass: "text-neon-green",
  },
  totals_under: {
    label: "MENOS",
    sub: "Apostar que sairão MENOS gols que a linha",
    bgClass: "bg-sky-500/15 border-sky-500/25",
    textClass: "text-sky-300",
  },
  next_goal_home: {
    label: "GOL DA CASA",
    sub: "Próximo gol marcado pelo time da casa",
    bgClass: "bg-sky-500/15 border-sky-500/25",
    textClass: "text-sky-300",
  },
  next_goal_away: {
    label: "GOL VISITANTE",
    sub: "Próximo gol marcado pelo time visitante",
    bgClass: "bg-violet-500/15 border-violet-500/25",
    textClass: "text-violet-300",
  },
  next_goal_nogoal: {
    label: "SEM MAIS GOLS",
    sub: "Sem mais gols no jogo",
    bgClass: "bg-slate-500/15 border-slate-500/20",
    textClass: "text-slate-400",
  },
};

function DirectionBadge({
  outcome,
  groupId,
  market,
}: {
  outcome: string;
  groupId: string;
  market?: string;
}) {
  let key: string;
  if (groupId === "totals") {
    // Market é tipo "over_2_5" ou "under_2_5"
    const direction = market?.startsWith("under_") ? "under" : "over";
    key = `totals_${direction}`;
  } else {
    key = `${groupId}_${outcome}`;
  }
  const cfg = DIRECTION_CONFIG[key];
  if (!cfg) return null;
  return (
    <div className={`mb-2.5 flex items-center gap-2 rounded-xl border px-3 py-2 ${cfg.bgClass}`}>
      <span className={`text-sm font-extrabold tracking-wider ${cfg.textClass}`}>
        {cfg.label}
      </span>
      <span className="text-[11px] text-slate-400">{cfg.sub}</span>
    </div>
  );
}

interface MarketCardProps {
  group: MarketGroup;
  best: MarketScanRow | null;
  verdict: Verdict;
  detail: string;
  stakeHint?: string;
  alternatives: MarketScanRow[];
  threshold: number;
}

function MarketCard({ group, best, verdict, detail, stakeHint, alternatives }: MarketCardProps) {
  const cfg = VERDICT_CONFIG[verdict];

  return (
    <div className={`rounded-2xl border p-4 transition-all ${cfg.cardClass}`}>
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-white">{group.superbetName}</p>
          {group.note && <p className="mt-0.5 text-[10px] text-slate-500">{group.note}</p>}
        </div>
        <span
          className={`shrink-0 rounded-lg px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide ${cfg.badgeClass}`}
        >
          {cfg.icon} {cfg.label}
        </span>
      </div>

      {best ? (
        <>
          {/* Badge de direção para totais, BTTS e próximo gol */}
          {(group.id === "totals" || group.id === "btts" || group.id === "next_goal") && (
            <DirectionBadge outcome={best.outcome} groupId={group.id} market={best.market} />
          )}
          <p className="truncate text-sm font-medium text-slate-200" title={best.label}>
            {best.label}
          </p>
          <div className="mt-1.5 flex items-baseline gap-3">
            <span className="font-mono text-lg font-bold text-white">
              {best.marketOdd.toFixed(2)}
            </span>
            <span className="text-xs text-slate-400">
              Modelo {formatPercent(best.modelProb)}
            </span>
          </div>
          <p
            className={`mt-1.5 text-xs ${
              verdict === "apostar"
                ? "text-neon-green"
                : verdict === "quase"
                  ? "text-amber-300"
                  : "text-slate-500"
            }`}
          >
            {detail}
          </p>
          {stakeHint && (
            <p className="mt-2 rounded-lg bg-neon-green/10 px-2.5 py-1.5 text-xs font-semibold text-neon-green">
              Stake sugerido: {stakeHint}
            </p>
          )}
          {alternatives.length > 0 && (
            <p className="mt-2 text-[10px] text-slate-600">
              Alternativas:{" "}
              {alternatives
                .map((a) => `${a.label.split(" ").slice(-2).join(" ")} EV ${(a.expectedValue * 100).toFixed(0)}%`)
                .join(" · ")}
            </p>
          )}
        </>
      ) : (
        <p className="text-xs text-slate-600">{detail}</p>
      )}
    </div>
  );
}

interface LiveMarketCardsProps {
  data: SuperbetLiveAdvice;
}

export function LiveMarketCards({ data }: LiveMarketCardsProps) {
  const [showExtra, setShowExtra] = useState(false);
  const threshold = data.strategy?.minEdgeThreshold ?? 0.04;

  const cards = useMemo(() => {
    const scan =
      (data.strategy?.marketScan?.length ?? 0) > 0
        ? data.strategy!.marketScan
        : buildFallbackScan(data);
    const oppByKey = new Map(
      (data.strategy?.opportunities ?? []).map((o) => [`${o.market}:${o.outcome}`, o]),
    );

    return MARKET_GROUPS.map((group) => {
      const rows = scan.filter((row) => group.matchMarket(row.market));
      if (rows.length === 0) {
        return {
          group,
          best: null as MarketScanRow | null,
          verdict: "sem_odds" as Verdict,
          detail: "Superbet não enviou odd neste refresh",
          stakeHint: undefined as string | undefined,
          alternatives: [] as MarketScanRow[],
        };
      }
      const best = rows.reduce((a, b) => (a.expectedValue > b.expectedValue ? a : b));
      const opp = oppByKey.get(`${best.market}:${best.outcome}`);
      const resolved = resolveVerdict(best, threshold);
      if (opp && resolved.verdict === "apostar" && opp.suggestedStakeValue > 0) {
        resolved.stakeHint = `R$ ${opp.suggestedStakeValue.toFixed(0)} · ${opp.suggestedStakePct}% da banca`;
      }
      return {
        group,
        best,
        ...resolved,
        alternatives: rows.filter((r) => r !== best).slice(0, 2),
      };
    });
  }, [data, threshold]);

  const apostarCount = cards.filter((c) => c.verdict === "apostar").length;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-white">Mercados ao vivo</h2>
          <p className="text-[11px] text-slate-500">
            {apostarCount > 0
              ? `${apostarCount} mercado${apostarCount > 1 ? "s" : ""} com sinal verde`
              : "Nenhum mercado com sinal verde neste momento"}{" "}
            · limiar EV +{(threshold * 100).toFixed(0)}%
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {cards.map((card) => (
          <MarketCard key={card.group.id} threshold={threshold} {...card} />
        ))}
      </div>

      <div className="mt-3">
        <button
          type="button"
          onClick={() => setShowExtra((v) => !v)}
          className="text-[11px] text-slate-600 underline-offset-2 hover:text-slate-400 hover:underline"
        >
          {showExtra ? "Ocultar" : "Ver"} mercados não analisados
        </button>
        {showExtra && (
          <p className="mt-2 text-[11px] leading-relaxed text-slate-600">
            Total por time, asiático, resultado correto, último gol, janelas de tempo, 2º tempo,
            ímpar/par, método do gol, combos — fora do modelo in-play atual.
          </p>
        )}
      </div>
    </div>
  );
}
