import type { SuperbetLiveAdvice } from "@/domain/entities";
import { buildBetReason, TIMING_CONFIG } from "@/presentation/components/predictions/liveBetInsights";

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
  whyBet?: string;
  timing?: string;
  timingLabel?: string;
  stakeHint?: string;
  showWatchList: boolean;
  directionBadge?: { label: string; colorClass: string };
  confidenceWarning?: string;
}

function evFromProb(prob: number, odd: number): number {
  return prob * odd - 1;
}

/** Resolve badge de direção para o apostador saber exatamente o que fazer. */
function resolveDirectionBadge(
  market: string,
  outcome: string,
): { label: string; colorClass: string } | undefined {
  if (market.startsWith("over_")) {
    return { label: "MAIS GOLS", colorClass: "bg-neon-green/20 text-neon-green border-neon-green/40" };
  }
  if (market.startsWith("under_")) {
    return { label: "MENOS GOLS", colorClass: "bg-sky-500/20 text-sky-300 border-sky-500/40" };
  }
  if (market === "btts" && outcome === "yes") {
    return { label: "SIM — AMBOS MARCAM", colorClass: "bg-neon-green/20 text-neon-green border-neon-green/40" };
  }
  if (market === "btts" && outcome === "no") {
    return { label: "NÃO — ALGUM NÃO MARCA", colorClass: "bg-amber-500/20 text-amber-300 border-amber-500/40" };
  }
  return undefined;
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

function buildWhyBet(
  top: NonNullable<SuperbetLiveAdvice["strategy"]>["opportunities"][number],
  data: SuperbetLiveAdvice,
): string {
  if (top.fundamentacao) {
    return top.timingReason
      ? `${top.fundamentacao} ${top.timingReason}`
      : top.fundamentacao;
  }
  return buildBetReason({
    label: top.label,
    market: top.market,
    outcome: top.outcome,
    modelProb: top.modelProb,
    impliedProb: top.impliedProb ?? 1 / top.marketOdd,
    edgePp: top.edgePp,
    tier: top.tier,
    rank: top.rank,
    minute: data.minute,
    currentScore: data.currentScore ?? undefined,
    timing: top.timing,
    timingReason: top.timingReason,
    confidenceLabel: data.confidence?.label,
    confidenceScore: data.confidence?.score,
  });
}

function buildActionNow(data: SuperbetLiveAdvice, trackBet: boolean): ActionState {
  if (data.isFinished) {
    return {
      tone: "finished",
      headline: "Jogo encerrado",
      subline: "Não há mais apostas neste evento.",
      showWatchList: false,
    };
  }

  const guardrails = data.betGuardrails;
  if (guardrails?.blockNewBets && !trackBet) {
    return {
      tone: "protect",
      headline: `NÃO APOSTE — janela fechada após ${guardrails.blockMinute}'`,
      subline:
        guardrails.blockReason ??
        "Novos aportes desativados. Monitore bilhetes abertos ou faça cash-out.",
      showWatchList: false,
    };
  }

  const conf = data.confidence;
  const confWarning =
    conf && conf.score < 0.3
      ? "⚠️ Dados insuficientes — modelo genérico. Não aposte valores altos."
      : undefined;

  if (trackBet && data.cashout) {
    const action = data.cashout.action;
    if (action === "cashout" || action === "cashout_parcial") {
      return {
        tone: "protect",
        headline: "SAIA AGORA — proteja seu dinheiro",
        subline: data.cashout.reason,
        showWatchList: false,
        confidenceWarning: confWarning,
      };
    }
    if (action === "manter") {
      return {
        tone: "wait",
        headline: "Fique na aposta — está indo bem",
        subline: data.cashout.reason,
        showWatchList: false,
        confidenceWarning: confWarning,
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

  // MODO DEFENSIVO — sem oportunidades claras
  if (strategy?.posture === "defensivo" && !top) {
    return {
      tone: "protect",
      headline: "NÃO APOSTE neste jogo agora",
      subline:
        strategy.waitReason ||
        (avoid.length > 0
          ? `O jogo está arriscado. Evite: ${avoid.join(", ")}.`
          : "Não encontramos vantagem neste momento. Espere o próximo refresh em ~25s."),
      showWatchList: true,
      confidenceWarning: confWarning,
    };
  }

  // OPORTUNIDADE FORTE — pode apostar com confiança
  if (top && top.tier === "forte" && top.timing !== "aguardar") {
    const stakeHint =
      top.timing === "agora" && top.suggestedStakeValue > 0
        ? `R$ ${top.suggestedStakeValue.toFixed(0)} (${top.suggestedStakePct}% da banca)`
        : undefined;
    const timingCfg = TIMING_CONFIG[top.timing ?? "monitorar"] ?? TIMING_CONFIG.monitorar;
    const implied = top.impliedProb ?? 1 / top.marketOdd;
    return {
      tone: top.timing === "agora" ? "bet" : "bet-light",
      headline:
        top.timing === "agora"
          ? `ENTRAR: ${top.label}`
          : `MONITORAR: ${top.label}`,
      subline: `Modelo ${(top.modelProb * 100).toFixed(0)}% vs mercado ${(implied * 100).toFixed(0)}% · edge +${top.edgePp.toFixed(1)} pp${
        avoid.length > 0 ? ` · Evitar: ${avoid.join(", ")}` : ""
      }`,
      whyBet: buildWhyBet(top, data),
      timing: top.timing,
      timingLabel: timingCfg.label,
      stakeHint,
      showWatchList: top.timing !== "agora",
      directionBadge: resolveDirectionBadge(top.market, top.outcome),
      confidenceWarning: confWarning,
    };
  }

  // OPORTUNIDADE MODERADA
  if (top && top.tier === "moderada" && top.timing !== "aguardar") {
    const stakeHint =
      top.timing === "agora" && top.suggestedStakeValue > 0
        ? `R$ ${top.suggestedStakeValue.toFixed(0)} (máx. ${top.suggestedStakePct}%)`
        : undefined;
    const implied = top.impliedProb ?? 1 / top.marketOdd;
    return {
      tone: "bet-light",
      headline: `LEITURA SÓLIDA: ${top.label}`,
      subline: `Probabilidade real ${(top.modelProb * 100).toFixed(0)}% · mercado ${(implied * 100).toFixed(0)}% · +${top.edgePp.toFixed(1)} pp${
        avoid.length > 0 ? ` · Cuidado: ${avoid.join(", ")}` : ""
      }`,
      whyBet: buildWhyBet(top, data),
      timing: top.timing,
      stakeHint,
      showWatchList: true,
      directionBadge: resolveDirectionBadge(top.market, top.outcome),
      confidenceWarning: confWarning,
    };
  }

  if (top && top.timing === "aguardar") {
    return {
      tone: "wait",
      headline: "AGUARDAR — linha ainda não favorece",
      subline: top.timingReason ?? "O modelo vê valor, mas a odd ainda não abriu o suficiente.",
      whyBet: buildWhyBet(top, data),
      showWatchList: true,
      confidenceWarning: confWarning,
    };
  }

  // OPORTUNIDADE LEVE — só para quem entende
  if (top?.tier === "leve") {
    return {
      tone: "wait",
      headline: "AGUARDE — oportunidade fraca",
      subline: `O modelo encontrou ${top.label} @ ${top.marketOdd.toFixed(2)}, mas o valor é pequeno. Melhor esperar um momento melhor.`,
      showWatchList: true,
      confidenceWarning: confWarning,
    };
  }

  // SEM OPORTUNIDADES
  const waitReason =
    strategy?.waitReason ||
    (avoid.length > 0
      ? `Nenhuma aposta segura agora. Evite: ${avoid.join(", ")}.`
      : "Nenhuma oportunidade clara neste momento. Reavalie em ~25s.");

  return {
    tone: "wait",
    headline: "AGUARDE — sem aposta recomendada",
    subline: waitReason,
    showWatchList: true,
    confidenceWarning: confWarning,
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
          {action.directionBadge && (
            <span
              className={`mt-2 inline-block rounded-lg border px-3 py-1.5 text-sm font-extrabold tracking-wide ${action.directionBadge.colorClass}`}
            >
              {action.directionBadge.label}
            </span>
          )}
          <p className="mt-1.5 text-sm text-slate-300">{action.subline}</p>

          {action.whyBet && (
            <div className="mt-3 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2.5">
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                Fundamentação do modelo
              </p>
              <p className="mt-1 text-xs leading-relaxed text-slate-300">{action.whyBet}</p>
            </div>
          )}

          {/* Alerta de confiança baixa nos dados */}
          {action.confidenceWarning && (
            <div className="mt-2 flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2">
              <span className="text-sm" aria-hidden="true">⚠️</span>
              <p className="text-xs text-amber-300">{action.confidenceWarning}</p>
            </div>
          )}

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
