import { useMemo, useState } from "react";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import {
  MARKET_SECTIONS,
  VERDICT_CONFIG,
  type MarketGroup,
  type MarketSection,
  type Verdict,
} from "@/presentation/components/predictions/liveMarketGroups";
import {
  buildBetReason,
  probComparisonLabel,
  rankLabel,
  sortByVerdictAndEdge,
  TIER_CONFIG,
  type BetTier,
} from "@/presentation/components/predictions/liveBetInsights";
import { LiveTopPicks } from "@/presentation/components/predictions/LiveTopPicks";

type MarketScanRow = NonNullable<SuperbetLiveAdvice["strategy"]>["marketScan"][number];
type Opportunity = NonNullable<SuperbetLiveAdvice["strategy"]>["opportunities"][number];

function EvBar({ modelProb, impliedProb }: { modelProb: number; impliedProb: number }) {
  const modelPct = Math.min(100, Math.max(0, modelProb * 100));
  const impliedPct = Math.min(100, Math.max(0, impliedProb * 100));
  const edge = modelProb - impliedProb;

  return (
    <div className="relative mb-3">
      <div className="mb-1 flex justify-between text-[10px] text-slate-500">
        <span>Mercado {impliedPct.toFixed(0)}%</span>
        <span className={edge > 0 ? "text-neon-green" : "text-slate-500"}>
          Modelo {modelPct.toFixed(0)}%
        </span>
      </div>
      <div className="relative h-2 w-full overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-slate-500/40 transition-all duration-500"
          style={{ width: `${impliedPct}%` }}
        />
        <div
          className={`absolute inset-y-0 left-0 rounded-full transition-all duration-500 ${
            edge > 0 ? "bg-neon-green/70" : "bg-red-400/40"
          }`}
          style={{ width: `${modelPct}%` }}
        />
      </div>
    </div>
  );
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
  if (groupId === "totals" || groupId.endsWith("_totals")) {
    const direction = market?.includes("_over_") || market?.startsWith("over_") ? "over" : "over";
    key = `totals_${direction}`;
  } else {
    key = `${groupId}_${outcome}`;
  }
  const cfg = DIRECTION_CONFIG[key];
  if (!cfg) return null;
  return (
    <div className={`mb-2.5 flex items-center gap-2 rounded-xl border px-3 py-2 ${cfg.bgClass}`}>
      <span className={`text-sm font-extrabold tracking-wider ${cfg.textClass}`}>{cfg.label}</span>
      <span className="text-[11px] text-slate-400">{cfg.sub}</span>
    </div>
  );
}

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

  const hm1 = data.halfMarkets?.["1h"];
  if (hm1?.h2h) {
    push("1h_h2h", "1", `1º Tempo — ${data.homeTeam}`, s.probHtHome, hm1.h2h["1"]);
    push("1h_h2h", "X", "1º Tempo — Empate", s.probHtDraw, hm1.h2h["X"]);
    push("1h_h2h", "2", `1º Tempo — ${data.awayTeam}`, s.probHtAway, hm1.h2h["2"]);
  }
  const hm2 = data.halfMarkets?.["2h"];
  if (hm2?.h2h) {
    push("2h_h2h", "1", `2º Tempo — ${data.homeTeam}`, s.probShHome, hm2.h2h["1"]);
    push("2h_h2h", "X", "2º Tempo — Empate", s.probShDraw, hm2.h2h["X"]);
    push("2h_h2h", "2", `2º Tempo — ${data.awayTeam}`, s.probShAway, hm2.h2h["2"]);
  }

  const pushHalfTotals = (
    period: "1h" | "2h",
    totals: Record<string, Record<string, number>> | undefined,
    lineProbs: Record<string, number> | undefined,
    label: string,
  ) => {
    if (!totals || !lineProbs) return;
    for (const [lineKey, outcomes] of Object.entries(totals)) {
      const lineNum = lineKey.replace(".", "_");
      const overProb = lineProbs[`over_${lineNum}`];
      const underProb = lineProbs[`under_${lineNum}`];
      for (const [name, odd] of Object.entries(outcomes)) {
        if (name.toLowerCase().includes("mais") && overProb != null) {
          push(`${period}_over_${lineNum}`, "yes", `${label}: mais de ${lineKey} gols`, overProb, odd);
        }
        if (name.toLowerCase().includes("menos") && underProb != null) {
          push(`${period}_over_${lineNum}`, "no", `${label}: menos de ${lineKey} gols`, underProb, odd);
        }
      }
    }
  };

  pushHalfTotals("1h", data.firstHalfTotals, s.htLineProbs, "1º Tempo");
  pushHalfTotals("2h", data.secondHalfTotals, s.secondHalfLineProbs, "2º Tempo");

  const pushHalfExtras = (
    period: "1h" | "2h",
    hm: NonNullable<SuperbetLiveAdvice["halfMarkets"]>[string] | undefined,
    csProbs: Record<string, number> | undefined,
    exactTotals: Record<string, number> | undefined,
    hcapProbs: Record<string, number> | undefined,
    label: string,
  ) => {
    if (!hm) return;
    for (const [score, odd] of Object.entries(hm.correct_score ?? {})) {
      const prob = csProbs?.[score];
      if (prob != null) {
        push(`${period}_cs_${score.replace("x", "_")}`, "yes", `${label} RC ${score}`, prob, odd);
      }
    }
    for (const [goals, odd] of Object.entries(hm.exact_total ?? {})) {
      const prob = exactTotals?.[goals];
      if (prob != null) {
        const mk = goals.replace("+", "plus");
        push(`${period}_exact_${mk}`, "yes", `${label} — exatamente ${goals} gols`, prob, odd);
      }
    }
    for (const [line, sides] of Object.entries(hm.handicap ?? {})) {
      for (const [side, odd] of Object.entries(sides)) {
        const prob = hcapProbs?.[`${side}_${line}`];
        if (prob != null && odd < 50) {
          push(`${period}_hcap_${side}_${line}`, "yes", `${label} handicap ${line}`, prob, odd);
        }
      }
    }
  };

  pushHalfExtras("1h", hm1, s.htCorrectScores, s.htExactTotals, s.htHandicapProbs, "1º Tempo");
  pushHalfExtras("2h", hm2, s.shCorrectScores, s.shExactTotals, s.shHandicapProbs, "2º Tempo");

  for (const ap of data.aportes) {
    if (["h2h", "btts", "next_goal"].includes(ap.market) && !ap.market.startsWith("combo_")) {
      continue;
    }
    if (ap.market === "over_2_5") continue;
    push(ap.market, ap.outcome, ap.label, ap.modelProb, ap.marketOdd);
  }

  return rows;
}

function resolveVerdict(
  best: MarketScanRow | null,
): { verdict: Verdict; detail: string; stakeHint?: string } {
  if (!best) {
    return { verdict: "sem_odds", detail: "Superbet não enviou odd neste refresh" };
  }

  if (best.meetsThreshold) {
    const stakeHint =
      best.suggestedStakeValue > 0
        ? `R$ ${best.suggestedStakeValue.toFixed(0)} · ${best.suggestedStakePct}% da banca`
        : undefined;
    return {
      verdict: "apostar",
      detail: `Edge +${best.edgePp.toFixed(1)} pp · modelo acima do mercado`,
      stakeHint,
    };
  }
  if (best.edgePp > 0) {
    return {
      verdict: "quase",
      detail: `Edge +${best.edgePp.toFixed(1)} pp · aguardar linha abrir mais`,
    };
  }
  return {
    verdict: "sem_valor",
    detail: `Modelo ${(best.modelProb * 100).toFixed(0)}% ≤ mercado ${(best.impliedProb * 100).toFixed(0)}%`,
  };
}

interface MarketCardProps {
  group: MarketGroup;
  best: MarketScanRow | null;
  verdict: Verdict;
  detail: string;
  stakeHint?: string;
  alternatives: MarketScanRow[];
  matchedOpp?: Opportunity;
  minute: number;
  currentScore: string;
  confidence?: SuperbetLiveAdvice["confidence"];
}

function MarketCard({
  group,
  best,
  verdict,
  detail,
  stakeHint,
  alternatives,
  matchedOpp,
  minute,
  currentScore,
  confidence,
}: MarketCardProps) {
  const isTopPick = matchedOpp != null && matchedOpp.rank <= 3;
  const tier = (matchedOpp?.tier as BetTier) ?? (verdict === "apostar" ? "leve" : undefined);
  const tierCfg = tier ? TIER_CONFIG[tier] : null;

  const cfg =
    isTopPick && tierCfg
      ? { ...VERDICT_CONFIG.apostar, cardClass: tierCfg.cardClass, badgeClass: tierCfg.badgeClass }
      : VERDICT_CONFIG[verdict];

  const showDirection =
    group.id === "totals" ||
    group.id === "btts" ||
    group.id === "next_goal" ||
    group.id.endsWith("_totals");

  const whyReason =
    best && (verdict === "apostar" || isTopPick)
      ? buildBetReason({
          label: best.label,
          market: best.market,
          outcome: best.outcome,
          modelProb: best.modelProb,
          impliedProb: best.impliedProb,
          edgePp: best.edgePp,
          tier: matchedOpp?.tier,
          rank: matchedOpp?.rank,
          minute,
          currentScore,
          timing: matchedOpp?.timing,
          timingReason: matchedOpp?.timingReason,
          fundamentacao: matchedOpp?.fundamentacao,
          confidenceLabel: confidence?.label,
          confidenceScore: confidence?.score,
        })
      : null;

  return (
    <article
      className={`relative overflow-hidden rounded-2xl border p-4 transition-all ${cfg.cardClass}`}
    >
      {isTopPick && matchedOpp?.rank === 1 && (
        <div
          className="pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full bg-neon-green/10 blur-xl"
          aria-hidden
        />
      )}

      <div className="relative mb-3 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-white">{group.superbetName}</p>
          {group.note && <p className="mt-0.5 text-[10px] text-slate-500">{group.note}</p>}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          {matchedOpp && (
            <span
              className={`rounded-md border px-1.5 py-0.5 font-mono text-[10px] font-bold ${
                matchedOpp.rank === 1
                  ? "border-neon-green/50 bg-neon-green/20 text-neon-green"
                  : "border-white/15 bg-white/5 text-slate-400"
              }`}
            >
              {rankLabel(matchedOpp.rank)}
            </span>
          )}
          <span
            className={`rounded-lg px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide ${cfg.badgeClass}`}
          >
            {VERDICT_CONFIG[verdict].icon}{" "}
            {tierCfg && verdict === "apostar" ? tierCfg.label : VERDICT_CONFIG[verdict].label}
          </span>
        </div>
      </div>

      {best ? (
        <>
          <EvBar modelProb={best.modelProb} impliedProb={best.impliedProb} />
          {showDirection && (
            <DirectionBadge outcome={best.outcome} groupId={group.id} market={best.market} />
          )}
          <p className="truncate text-sm font-medium text-slate-200" title={best.label}>
            {best.label}
          </p>
          <p className="mt-1.5 font-mono text-xs text-slate-400">
            {probComparisonLabel(best.modelProb, best.impliedProb)}
          </p>
          <p className="mt-0.5 text-[10px] text-slate-600">Odd ref. {best.marketOdd.toFixed(2)}</p>
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

          {whyReason && (
            <div
              className={`mt-2.5 rounded-xl border px-3 py-2 ${
                isTopPick
                  ? "border-neon-green/20 bg-neon-green/[0.06]"
                  : "border-white/8 bg-white/[0.03]"
              }`}
            >
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                Fundamentação do modelo
              </p>
              <p className="mt-1 text-[11px] leading-relaxed text-slate-400">{whyReason}</p>
            </div>
          )}

          {stakeHint && (
            <p className="mt-2 rounded-lg bg-neon-green/10 px-2.5 py-1.5 text-xs font-semibold text-neon-green">
              Stake sugerido: {stakeHint}
            </p>
          )}
          {alternatives.length > 0 && (
            <p className="mt-2 text-[10px] text-slate-600">
              Alternativas:{" "}
              {alternatives
                .map(
                  (a) =>
                    `${a.label.split(" ").slice(-2).join(" ")} EV ${(a.expectedValue * 100).toFixed(0)}%`,
                )
                .join(" · ")}
            </p>
          )}
        </>
      ) : (
        <p className="text-xs text-slate-600">{detail}</p>
      )}
    </article>
  );
}

interface SectionCards {
  section: MarketSection;
  cards: Array<{
    group: MarketGroup;
    best: MarketScanRow | null;
    verdict: Verdict;
    detail: string;
    stakeHint?: string;
    alternatives: MarketScanRow[];
    matchedOpp?: Opportunity;
  }>;
}

function buildSectionCards(
  scan: MarketScanRow[],
  data: SuperbetLiveAdvice,
): SectionCards[] {
  const oppByKey = new Map(
    (data.strategy?.opportunities ?? []).map((o) => [`${o.market}:${o.outcome}`, o]),
  );
  const oppByMarket = new Map(
    (data.strategy?.opportunities ?? []).map((o) => [o.market, o]),
  );

  return MARKET_SECTIONS.flatMap((section) => {
    const cards = section.groups.map((group) => {
      const rows = scan.filter((row) => group.matchMarket(row.market));
      if (rows.length === 0) {
        const waitingHalftime =
          section.id === "props" &&
          group.id === "cards" &&
          data.isLive &&
          data.minute <= 45 &&
          Boolean(data.analysisCoverage?.yellowCards);
        return {
          group,
          best: null as MarketScanRow | null,
          verdict: "sem_odds" as Verdict,
          detail: waitingHalftime
            ? "Cartões FT calibrados após o intervalo (poll completo ~60s)"
            : "Mercado não disponível para este evento",
          stakeHint: undefined as string | undefined,
          alternatives: [] as MarketScanRow[],
          matchedOpp: undefined as Opportunity | undefined,
        };
      }
      const best = rows.reduce((a, b) => (a.expectedValue > b.expectedValue ? a : b));
      const opp =
        oppByKey.get(`${best.market}:${best.outcome}`) ?? oppByMarket.get(best.market);
      const resolved = resolveVerdict(best);
      if (opp && resolved.verdict === "apostar" && opp.suggestedStakeValue > 0) {
        resolved.stakeHint = `R$ ${opp.suggestedStakeValue.toFixed(0)} · ${opp.suggestedStakePct}% da banca`;
      }
      return {
        group,
        best,
        ...resolved,
        alternatives: rows.filter((r) => r !== best).slice(0, 2),
        matchedOpp: opp,
      };
    });

    const sortedCards = sortByVerdictAndEdge(cards);

    const hasHalfData =
      section.id === "1h"
        ? Boolean(
            data.analysisCoverage?.firstHalf ||
              data.halfMarkets?.["1h"] ||
              data.firstHalfTotals ||
              (data.inplaySummary.probHtHome != null && data.isLive),
          )
        : section.id === "2h"
          ? Boolean(
              data.analysisCoverage?.secondHalf ||
                data.halfMarkets?.["2h"] ||
                data.secondHalfTotals ||
                (data.inplaySummary.probShHome != null && data.isLive),
            )
          : section.id === "props"
            ? Boolean(
                data.analysisCoverage?.corners ||
                  data.analysisCoverage?.yellowCards ||
                  Object.keys(data.inplaySummary.cornerLineProbs ?? {}).length > 0 ||
                  Object.keys(data.inplaySummary.cardLineProbs ?? {}).length > 0 ||
                  (data.isLive && data.minute > 45),
              )
            : true;

    const hasScanRows = sortedCards.some((c) => c.best != null);
    const showLiveHalf = data.isLive && !data.isFinished && section.id !== "core";
    if (section.id !== "core" && !hasHalfData && !hasScanRows && !showLiveHalf) {
      return [];
    }

    return [{ section, cards: sortedCards }];
  });
}

interface LiveMarketCardsProps {
  data: SuperbetLiveAdvice;
}

export function LiveMarketCards({ data }: LiveMarketCardsProps) {
  const [showExtra, setShowExtra] = useState(false);

  const hcapAlert = data.strategy?.shields?.find(
    (s) =>
      s.priority === "alta" &&
      s.action === "evitar" &&
      s.title.toLowerCase().includes("handicap agressivo"),
  );

  const sections = useMemo(() => {
    const scan =
      (data.strategy?.marketScan?.length ?? 0) > 0
        ? data.strategy!.marketScan
        : buildFallbackScan(data);
    return buildSectionCards(scan, data);
  }, [data]);

  const allCards = sections.flatMap((s) => s.cards);
  const apostarCount = allCards.filter((c) => c.verdict === "apostar").length;
  const hasTopPicks = (data.strategy?.opportunities?.length ?? 0) > 0;

  return (
    <div>
      <LiveTopPicks data={data} />

      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-white">
            {hasTopPicks ? "Todos os mercados" : "Mercados ao vivo"}
          </h2>
          <p className="text-[11px] text-slate-500">
            {apostarCount > 0
              ? `${apostarCount} mercado${apostarCount > 1 ? "s" : ""} com edge do modelo · ordenados por probabilidade real`
              : "Nenhum mercado com edge suficiente neste momento"}{" "}
            · mínimo +{((data.strategy?.minEdgeThreshold ?? 0.04) * 100).toFixed(0)} pp implícito
          </p>
        </div>
      </div>

      <div className="space-y-6">
        {sections.map(({ section, cards }) => (
          <div key={section.id}>
            {section.id !== "core" && (
              <h3 className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                {section.title}
              </h3>
            )}
            {section.id === "2h" && hcapAlert && (
              <div className="mb-2.5 rounded-xl border border-red-500/40 bg-red-500/10 px-3 py-2.5">
                <p className="text-xs font-semibold text-red-200">{hcapAlert.title}</p>
                <p className="mt-1 text-[11px] leading-relaxed text-slate-400">{hcapAlert.reason}</p>
              </div>
            )}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {cards.map((card) => (
                <MarketCard
                  key={card.group.id}
                  minute={data.minute}
                  currentScore={data.currentScore ?? "0x0"}
                  confidence={data.confidence}
                  {...card}
                />
              ))}
            </div>
          </div>
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
            Escanteios, cartões, último gol, janelas de 5/10/15 min, ímpar/par e método do gol ainda
            não entram no modelo in-play.
          </p>
        )}
      </div>
    </div>
  );
}
