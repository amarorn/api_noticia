import type { SuperbetLiveAdvice } from "@/domain/entities";

const ACTION_LABELS: Record<string, string> = {
  cashout: "Cash-out agora",
  cashout_parcial: "Cash-out parcial (50–70%)",
  manter: "Manter aposta aberta",
  aguardar: "Aguardar — reavaliar em 3–5 min",
};

const TONE_STYLES: Record<string, string> = {
  protect: "border-red-500/40 bg-red-500/12",
  bet: "border-neon-green/40 bg-neon-green/12",
  "bet-light": "border-emerald-500/35 bg-emerald-500/10",
  wait: "border-amber-500/35 bg-amber-500/10",
  finished: "border-white/15 bg-white/5",
};

interface WatchItem {
  key: string;
  label: string;
  marketOdd: number;
  expectedValue: number;
  meetsThreshold: boolean;
}

interface ActionNow {
  tone: keyof typeof TONE_STYLES;
  headline: string;
  subline: string;
  showWatchList: boolean;
}

function evFromProb(prob: number, odd: number): number {
  return prob * odd - 1;
}

function buildFallbackWatchList(data: SuperbetLiveAdvice, threshold: number): WatchItem[] {
  const s = data.inplaySummary;
  const odds = data.h2hOdds;
  const specs: Array<{ key: string; label: string; prob: number | undefined; oddKey: string }> = [
    { key: "1", label: `${data.homeTeam} vence`, prob: s.probFinalHome, oddKey: "1" },
    { key: "X", label: "Empate", prob: s.probFinalDraw, oddKey: "X" },
    { key: "2", label: `${data.awayTeam} vence`, prob: s.probFinalAway, oddKey: "2" },
  ];
  const rows: WatchItem[] = [];
  for (const spec of specs) {
    const prob = spec.prob;
    const odd = odds[spec.oddKey];
    if (prob == null || odd == null || odd <= 1) continue;
    const ev = evFromProb(prob, odd);
    rows.push({
      key: spec.key,
      label: spec.label,
      marketOdd: odd,
      expectedValue: ev,
      meetsThreshold: ev >= threshold,
    });
  }
  return rows.sort((a, b) => b.expectedValue - a.expectedValue).slice(0, 3);
}

function resolveWatchList(data: SuperbetLiveAdvice, threshold: number): WatchItem[] {
  const fromStrategy = data.strategy?.watchList ?? [];
  if (fromStrategy.length > 0) {
    return fromStrategy.map((w) => ({
      key: `${w.market}-${w.outcome}`,
      label: w.label,
      marketOdd: w.marketOdd,
      expectedValue: w.expectedValue,
      meetsThreshold: w.meetsThreshold,
    }));
  }
  return buildFallbackWatchList(data, threshold);
}

function buildActionNow(data: SuperbetLiveAdvice, trackBet: boolean): ActionNow {
  if (data.isFinished) {
    return {
      tone: "finished",
      headline: "Jogo encerrado",
      subline: "Sem novas apostas in-play neste evento.",
      showWatchList: false,
    };
  }

  if (trackBet && data.cashout) {
    const action = data.cashout.action;
    if (action === "cashout" || action === "cashout_parcial") {
      return {
        tone: "protect",
        headline: ACTION_LABELS[action] ?? action,
        subline: data.cashout.reason,
        showWatchList: false,
      };
    }
    if (action === "manter") {
      return {
        tone: "wait",
        headline: "Manter aposta — sem sinal de saída",
        subline: data.cashout.reason,
        showWatchList: false,
      };
    }
  }

  const strategy = data.strategy;
  const top = strategy?.opportunities.find((o) => o.tier === "forte" || o.tier === "moderada")
    ?? strategy?.opportunities[0];

  const avoid = (strategy?.shields ?? [])
    .filter((s) => s.action === "evitar")
    .map((s) => s.title.replace(/^Evitar /, ""))
    .slice(0, 2);

  if (strategy?.posture === "defensivo" && !top) {
    return {
      tone: "protect",
      headline: "Aguardar — modo defensivo",
      subline:
        strategy.waitReason ||
        (avoid.length > 0
          ? `Não abra apostas novas. Evite: ${avoid.join(", ")}.`
          : "Não abra apostas novas neste minuto. Reavalie após gol ou em ~25s."),
      showWatchList: true,
    };
  }

  if (top && (top.tier === "forte" || top.tier === "moderada")) {
    const prefix = top.tier === "forte" ? "Aporte" : "Aporte moderado";
    return {
      tone: "bet",
      headline: `${prefix}: ${top.label} @ ${top.marketOdd.toFixed(2)} — R$ ${top.suggestedStakeValue.toFixed(0)}`,
      subline: `EV +${(top.expectedValue * 100).toFixed(1)}% · stake ${top.suggestedStakePct}% da banca${
        avoid.length > 0 ? ` · Evite: ${avoid.join(", ")}` : ""
      }`,
      showWatchList: false,
    };
  }

  if (top?.tier === "leve") {
    return {
      tone: "bet-light",
      headline: `Aporte leve: ${top.label} @ ${top.marketOdd.toFixed(2)} — R$ ${top.suggestedStakeValue.toFixed(0)}`,
      subline: `EV +${(top.expectedValue * 100).toFixed(1)}% (abaixo do ideal) · stake máx. ${top.suggestedStakePct}%${
        avoid.length > 0 ? ` · Evite: ${avoid.join(", ")}` : ""
      }`,
      showWatchList: false,
    };
  }

  const waitReason =
    strategy?.waitReason ||
    (avoid.length > 0
      ? `Nenhum mercado com edge suficiente. Evite: ${avoid.join(", ")}.`
      : "Nenhum mercado com edge suficiente neste minuto. Reavalie em ~25s.");

  return {
    tone: "wait",
    headline: "Aguardar — sem aposta recomendada",
    subline: waitReason,
    showWatchList: true,
  };
}

interface LiveActionNowPanelProps {
  data: SuperbetLiveAdvice;
  trackBet: boolean;
}

export function LiveActionNowPanel({ data, trackBet }: LiveActionNowPanelProps) {
  const action = buildActionNow(data, trackBet);
  const toneStyle = TONE_STYLES[action.tone] ?? TONE_STYLES.wait;
  const threshold = data.strategy?.minEdgeThreshold ?? 0.04;
  const watchList = action.showWatchList ? resolveWatchList(data, threshold) : [];

  return (
    <section
      className={`rounded-2xl border p-4 ${toneStyle}`}
      aria-live="polite"
      aria-label="O que fazer agora"
    >
      <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
        O que fazer agora
      </p>
      <p className="mt-1 text-base font-semibold text-white">{action.headline}</p>
      <p className="mt-1.5 text-sm text-slate-300">{action.subline}</p>

      {action.showWatchList && watchList.length > 0 && (
        <div className="mt-3 space-y-2 border-t border-white/10 pt-3">
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
            Monitorar (ainda não apostar)
          </p>
          <ul className="space-y-1.5">
            {watchList.map((item) => {
              const evPct = item.expectedValue * 100;
              const gap = threshold * 100 - evPct;
              const status = item.meetsThreshold
                ? "No limiar"
                : evPct < 0
                  ? "Sem valor"
                  : `Faltam +${gap.toFixed(1)} pp`;

              return (
                <li
                  key={item.key}
                  className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-0.5 text-xs text-slate-400"
                >
                  <span className="text-slate-300">
                    {item.label} @ {item.marketOdd.toFixed(2)}
                  </span>
                  <span>
                    EV {evPct >= 0 ? "+" : ""}
                    {evPct.toFixed(1)}% · {status}
                  </span>
                </li>
              );
            })}
          </ul>
          <p className="text-[11px] text-slate-500">
            Limiar in-play: EV +{(threshold * 100).toFixed(0)}%. Próximo refresh em ~25s ou após gol.
          </p>
        </div>
      )}
    </section>
  );
}
