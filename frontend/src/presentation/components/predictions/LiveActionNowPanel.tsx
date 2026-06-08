import type { SuperbetLiveAdvice } from "@/domain/entities";

const ACTION_LABELS: Record<string, string> = {
  cashout: "Cash-out agora",
  cashout_parcial: "Cash-out parcial (50–70%)",
  manter: "Manter aposta aberta",
  aguardar: "Aguardar — reavaliar em 3–5 min",
};

type Tone = "protect" | "bet" | "bet-light" | "wait" | "finished";

const TONE_CONFIG: Record<
  Tone,
  { wrapper: string; accent: string; icon: string; labelColor: string }
> = {
  bet: {
    wrapper:
      "border-2 border-neon-green/60 bg-gradient-to-br from-neon-green/10 to-neon-green/[0.04] shadow-[0_0_32px_rgba(0,255,136,0.10)]",
    accent: "text-neon-green",
    icon: "●",
    labelColor: "text-neon-green/70",
  },
  "bet-light": {
    wrapper:
      "border-2 border-emerald-400/50 bg-gradient-to-br from-emerald-500/8 to-transparent",
    accent: "text-emerald-300",
    icon: "◑",
    labelColor: "text-emerald-400/70",
  },
  wait: {
    wrapper:
      "border-2 border-amber-500/40 bg-gradient-to-br from-amber-500/8 to-transparent",
    accent: "text-amber-300",
    icon: "◐",
    labelColor: "text-amber-400/70",
  },
  protect: {
    wrapper:
      "border-2 border-red-500/50 bg-gradient-to-br from-red-500/10 to-transparent",
    accent: "text-red-300",
    icon: "▲",
    labelColor: "text-red-400/70",
  },
  finished: {
    wrapper: "border border-white/12 bg-white/[0.03]",
    accent: "text-slate-300",
    icon: "■",
    labelColor: "text-slate-500",
  },
};

interface WatchItem {
  key: string;
  label: string;
  marketOdd: number;
  expectedValue: number;
  meetsThreshold: boolean;
}

interface ActionState {
  tone: Tone;
  headline: string;
  subline: string;
  stakeHint?: string;
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

function buildActionNow(data: SuperbetLiveAdvice, trackBet: boolean): ActionState {
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
  const top =
    strategy?.opportunities.find((o) => o.tier === "forte" || o.tier === "moderada") ??
    strategy?.opportunities[0];

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
    const prefix = top.tier === "forte" ? "Apostar" : "Apostar (moderado)";
    const stakeHint =
      top.suggestedStakeValue > 0
        ? `R$ ${top.suggestedStakeValue.toFixed(0)} · ${top.suggestedStakePct}% da banca`
        : undefined;
    return {
      tone: "bet",
      headline: `${prefix}: ${top.label} @ ${top.marketOdd.toFixed(2)}`,
      subline: `EV +${(top.expectedValue * 100).toFixed(1)}%${
        avoid.length > 0 ? ` · Evite: ${avoid.join(", ")}` : ""
      }`,
      stakeHint,
      showWatchList: false,
    };
  }

  if (top?.tier === "leve") {
    const stakeHint =
      top.suggestedStakeValue > 0
        ? `R$ ${top.suggestedStakeValue.toFixed(0)} · máx. ${top.suggestedStakePct}% da banca`
        : undefined;
    return {
      tone: "bet-light",
      headline: `Apostar (leve): ${top.label} @ ${top.marketOdd.toFixed(2)}`,
      subline: `EV +${(top.expectedValue * 100).toFixed(1)}% (abaixo do ideal)${
        avoid.length > 0 ? ` · Evite: ${avoid.join(", ")}` : ""
      }`,
      stakeHint,
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
  const cfg = TONE_CONFIG[action.tone];
  const threshold = data.strategy?.minEdgeThreshold ?? 0.04;
  const watchList = action.showWatchList ? resolveWatchList(data, threshold) : [];

  return (
    <section
      className={`rounded-2xl p-5 ${cfg.wrapper}`}
      aria-live="polite"
      aria-label="O que fazer agora"
    >
      <div className="flex items-start gap-4">
        {/* Ícone de sinal */}
        <div
          className={`mt-0.5 shrink-0 text-3xl leading-none ${cfg.accent}`}
          aria-hidden="true"
        >
          {cfg.icon}
        </div>

        {/* Conteúdo principal */}
        <div className="min-w-0 flex-1">
          <p className={`text-[10px] font-bold uppercase tracking-widest ${cfg.labelColor}`}>
            O que fazer agora
          </p>
          <p className={`mt-1 text-xl font-bold leading-tight ${cfg.accent}`}>
            {action.headline}
          </p>
          <p className="mt-1.5 text-sm text-slate-300">{action.subline}</p>

          {/* Stake em destaque */}
          {action.stakeHint && (
            <div
              className={`mt-3 inline-flex items-center gap-2 rounded-xl border px-3 py-2 ${
                action.tone === "bet"
                  ? "border-neon-green/30 bg-neon-green/10"
                  : "border-emerald-400/25 bg-emerald-500/8"
              }`}
            >
              <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
                Stake
              </span>
              <span className={`font-mono text-sm font-bold ${cfg.accent}`}>
                {action.stakeHint}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Watch list — pills horizontais */}
      {action.showWatchList && watchList.length > 0 && (
        <div className="mt-4 border-t border-white/10 pt-4">
          <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-slate-500">
            No radar (não apostar agora — monitorar)
          </p>
          <div className="flex flex-wrap gap-2">
            {watchList.map((item) => {
              const evPct = item.expectedValue * 100;
              const gap = threshold * 100 - evPct;
              return (
                <span
                  key={item.key}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-2.5 py-1.5 text-xs"
                >
                  <span className="text-slate-300">
                    {item.label} @ {item.marketOdd.toFixed(2)}
                  </span>
                  <span className="text-slate-500">
                    EV {evPct >= 0 ? "+" : ""}
                    {evPct.toFixed(1)}%
                    {evPct < threshold * 100 && gap > 0 && ` · faltam +${gap.toFixed(1)} pp`}
                  </span>
                </span>
              );
            })}
          </div>
          <p className="mt-2 text-[11px] text-slate-600">
            Limiar in-play: EV +{(threshold * 100).toFixed(0)}% · próximo refresh ~25s
          </p>
        </div>
      )}
    </section>
  );
}
