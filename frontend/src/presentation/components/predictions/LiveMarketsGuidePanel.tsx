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

const VERDICT_STYLES: Record<Verdict, { label: string; className: string }> = {
  apostar: {
    label: "Apostar",
    className: "border-neon-green/40 bg-neon-green/15 text-neon-green",
  },
  quase: {
    label: "Quase",
    className: "border-amber-500/35 bg-amber-500/10 text-amber-300",
  },
  sem_valor: {
    label: "Sem valor",
    className: "border-white/12 bg-white/5 text-slate-400",
  },
  sem_odds: {
    label: "Sem odds",
    className: "border-white/10 bg-white/[0.02] text-slate-500",
  },
};

interface RadarRow {
  group: MarketGroup;
  best: MarketScanRow | null;
  verdict: Verdict;
  verdictDetail: string;
  alternatives: MarketScanRow[];
}

function resolveVerdict(
  best: MarketScanRow | null,
  threshold: number,
  tier?: string,
): { verdict: Verdict; detail: string } {
  if (!best) {
    return { verdict: "sem_odds", detail: "Superbet não enviou odd neste refresh" };
  }
  const evPct = best.expectedValue * 100;
  const gap = threshold * 100 - evPct;
  if (best.meetsThreshold) {
    const stake =
      tier === "forte" || tier === "moderada"
        ? ` · stake sugerido R$ ${best.suggestedStakeValue.toFixed(0)}`
        : "";
    return {
      verdict: "apostar",
      detail: `EV +${evPct.toFixed(1)}% · edge ${best.edgePp >= 0 ? "+" : ""}${best.edgePp.toFixed(1)} pp${stake}`,
    };
  }
  if (best.expectedValue > 0) {
    return {
      verdict: "quase",
      detail: `EV +${evPct.toFixed(1)}% · faltam +${gap.toFixed(1)} pp para o limiar`,
    };
  }
  return {
    verdict: "sem_valor",
    detail: `EV ${evPct.toFixed(1)}% · modelo abaixo da odd da casa`,
  };
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
  push("over_2_5", "yes", "Over 2.5 gols", s.over25, data.aportes.find((a) => a.market === "over_2_5")?.marketOdd);
  push("over_3_5", "yes", "Over 3.5 gols", undefined, undefined);
  push("btts", "yes", "Ambos marcam", s.btts, data.bttsOdds.yes);
  push("btts", "no", "Ambos não marcam", s.btts != null ? 1 - s.btts : undefined, data.bttsOdds.no);
  push("next_goal", "home", `Próximo gol ${data.homeTeam}`, s.probNextGoalHome, data.nextGoalOdds.home);
  push("next_goal", "away", `Próximo gol ${data.awayTeam}`, s.probNextGoalAway, data.nextGoalOdds.away);

  return rows;
}

function buildRadar(data: SuperbetLiveAdvice): RadarRow[] {
  const scan =
    (data.strategy?.marketScan?.length ?? 0) > 0
      ? data.strategy!.marketScan
      : buildFallbackScan(data);
  const threshold = data.strategy?.minEdgeThreshold ?? 0.04;
  const oppByKey = new Map(
    (data.strategy?.opportunities ?? []).map((o) => [`${o.market}:${o.outcome}`, o]),
  );

  return MARKET_GROUPS.map((group) => {
    const rows = scan.filter((row) => group.matchMarket(row.market));
    if (rows.length === 0) {
      return {
        group,
        best: null,
        verdict: "sem_odds" as Verdict,
        verdictDetail: "Superbet não enviou odd neste refresh",
        alternatives: [],
      };
    }
    const best = rows.reduce((a, b) => (a.expectedValue > b.expectedValue ? a : b));
    const opp = oppByKey.get(`${best.market}:${best.outcome}`);
    const { verdict, detail } = resolveVerdict(best, threshold, opp?.tier);
    return {
      group,
      best,
      verdict,
      verdictDetail: detail,
      alternatives: rows.filter((r) => r !== best).slice(0, 2),
    };
  });
}

function formatCapturedAt(iso: string | null): string {
  if (!iso) return "agora";
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return "agora";
  }
}

interface LiveMarketsGuidePanelProps {
  data: SuperbetLiveAdvice;
}

export function LiveMarketsGuidePanel({ data }: LiveMarketsGuidePanelProps) {
  const [showAvoid, setShowAvoid] = useState(false);
  const threshold = data.strategy?.minEdgeThreshold ?? 0.04;
  const radar = useMemo(() => buildRadar(data), [data]);
  const apostarCount = radar.filter((r) => r.verdict === "apostar").length;
  const hasCombos = (data.analysisCoverage?.combos.length ?? 0) > 0;

  return (
    <section className="rounded-2xl border border-white/8 bg-white/[0.02] p-5">
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-white">Modelo vs Superbet — mercados ao vivo</h2>
        <p className="mt-1 text-xs text-slate-500">
          Cruzamento direto: odd da casa, P(modelo), EV e veredito · refresh{" "}
          {formatCapturedAt(data.capturedAt)} · limiar EV +{(threshold * 100).toFixed(0)}%
        </p>
        {data.strategy?.waitReason && apostarCount === 0 && (
          <p className="mt-2 text-xs text-amber-300/90">{data.strategy.waitReason}</p>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-left text-xs">
          <thead>
            <tr className="border-b border-white/10 text-[10px] uppercase tracking-wider text-slate-500">
              <th className="pb-2 pr-3 font-semibold">Mercado Superbet</th>
              <th className="pb-2 pr-3 font-semibold">Melhor palpite</th>
              <th className="pb-2 pr-3 font-semibold">Odd</th>
              <th className="pb-2 pr-3 font-semibold">Modelo</th>
              <th className="pb-2 pr-3 font-semibold">EV</th>
              <th className="pb-2 font-semibold">Veredito</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/6">
            {radar.map((row) => {
              const style = VERDICT_STYLES[row.verdict];
              const highlighted = row.verdict === "apostar";
              return (
                <tr
                  key={row.group.id}
                  className={highlighted ? "bg-neon-green/[0.04]" : undefined}
                >
                  <td className="py-3 pr-3 align-top">
                    <p className="font-medium text-white">{row.group.superbetName}</p>
                    {row.group.note && (
                      <p className="mt-0.5 text-[10px] text-slate-500">{row.group.note}</p>
                    )}
                    {row.alternatives.length > 0 && (
                      <p className="mt-1 text-[10px] text-slate-500">
                        Também:{" "}
                        {row.alternatives
                          .map(
                            (a) =>
                              `${a.label.split(" ").slice(-2).join(" ")} EV ${(a.expectedValue * 100).toFixed(0)}%`,
                          )
                          .join(" · ")}
                      </p>
                    )}
                  </td>
                  <td className="py-3 pr-3 align-top text-slate-300">
                    {row.best?.label ?? "—"}
                  </td>
                  <td className="py-3 pr-3 align-top font-mono text-slate-300">
                    {row.best ? row.best.marketOdd.toFixed(2) : "—"}
                  </td>
                  <td className="py-3 pr-3 align-top font-mono text-slate-300">
                    {row.best ? formatPercent(row.best.modelProb) : "—"}
                  </td>
                  <td className="py-3 pr-3 align-top font-mono">
                    {row.best ? (
                      <span
                        className={
                          row.best.expectedValue >= threshold
                            ? "text-neon-green"
                            : row.best.expectedValue > 0
                              ? "text-amber-300"
                              : "text-slate-500"
                        }
                      >
                        {row.best.expectedValue >= 0 ? "+" : ""}
                        {(row.best.expectedValue * 100).toFixed(1)}%
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="py-3 align-top">
                    <span
                      className={`inline-block rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${style.className}`}
                    >
                      {style.label}
                    </span>
                    <p className="mt-1 max-w-[200px] text-[10px] text-slate-500">
                      {row.verdictDetail}
                    </p>
                  </td>
                </tr>
              );
            })}
            {hasCombos && (
              <tr>
                <td className="py-3 pr-3 text-slate-300">Combos (&amp;)</td>
                <td colSpan={4} className="py-3 pr-3 text-slate-500">
                  Odds na casa ({data.analysisCoverage?.combos.length} tipos) — scan automático em
                  breve
                </td>
                <td className="py-3">
                  <span className="inline-block rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-semibold uppercase text-slate-500">
                    Manual
                  </span>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-[11px] text-slate-500">
        <span className="text-neon-green">Apostar</span> = EV ≥ limiar ·{" "}
        <span className="text-amber-300">Quase</span> = EV positivo mas abaixo ·{" "}
        <span className="text-slate-400">Sem valor</span> = casa precificou acima do modelo. Siga
        também o bloco &quot;O que fazer agora&quot; para stake e correlações.
      </p>

      <button
        type="button"
        onClick={() => setShowAvoid((v) => !v)}
        className="mt-3 text-[11px] text-slate-500 underline-offset-2 hover:text-slate-300 hover:underline"
      >
        {showAvoid ? "Ocultar" : "Ver"} mercados que não analisamos (placar exato, asiático, 2º
        tempo…)
      </button>

      {showAvoid && (
        <p className="mt-2 text-[11px] leading-relaxed text-slate-600">
          Total por time, asiático, resultado correto, último gol, janelas de 5/10/15 min, 2º tempo,
          ímpar/par, método do gol, combos com &quot;ou&quot; — fora do modelo in-play.
        </p>
      )}
    </section>
  );
}
