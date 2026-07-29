import type { BaseballSuperbetLiveAdvice } from "@/domain/entities";
import { secondsSince } from "@/presentation/components/live-operational/liveOperationalUtils";
import type { BaseballAdviceSource } from "@/presentation/utils/baseballLiveMerge";

export type BaseballQualityLevel = "ok" | "caution" | "warning" | "blocked";

export interface BaseballQualityItem {
  tone: "ok" | "warn" | "bad" | "muted";
  label: string;
  detail?: string;
}

export interface BaseballDataQualitySummary {
  level: BaseballQualityLevel;
  title: string;
  subtitle: string;
  items: BaseballQualityItem[];
}

const CATEGORY_LABELS: Record<string, string> = {
  moneyline: "Vencedor (ML)",
  totals: "Total corridas",
  spread: "Run line",
};

const ML_LINE_LABELS: Record<string, string> = {
  "1": "Casa",
  "2": "Fora",
};

export function formatBaseballScanCategory(category: string): string {
  return CATEGORY_LABELS[category] ?? category;
}

export function formatBaseballScanLine(category: string, line: string): string {
  if (category === "moneyline") return ML_LINE_LABELS[line] ?? line;
  if (category === "spread") return line.replace(/m/g, "-").replace(/p/g, "+").replace(/_/g, ".");
  return line;
}

export function buildBaseballDataQuality(
  data: BaseballSuperbetLiveAdvice,
  opts?: {
    adviceSource?: BaseballAdviceSource | null;
    scoreIsFresh?: boolean;
    capturedAt?: string | null;
  },
): BaseballDataQualitySummary {
  const dataAgeSec = secondsSince(opts?.capturedAt ?? data.capturedAt);
  const items: BaseballQualityItem[] = [];
  let level: BaseballQualityLevel = "ok";

  const bump = (next: BaseballQualityLevel) => {
    const rank = { ok: 0, caution: 1, warning: 2, blocked: 3 };
    if (rank[next] > rank[level]) level = next;
  };

  if (data.isFinished || !data.isLive) {
    items.push({ tone: "muted", label: "Partida", detail: data.isFinished ? "Encerrada" : "Fora do ar" });
    bump("blocked");
  } else {
    items.push({ tone: "ok", label: "Partida", detail: data.gamePhase?.label ?? `${data.inning}I ao vivo` });
  }

  if (data.superbetStale) {
    items.push({
      tone: "bad",
      label: "Feed Superbet",
      detail: "Snapshot stale — odds/placar podem estar defasados",
    });
    bump("warning");
  } else {
    items.push({ tone: "ok", label: "Feed Superbet", detail: "Snapshot recente" });
  }

  if (data.scoreStale?.scoreStale) {
    items.push({
      tone: "bad",
      label: "Placar",
      detail: data.scoreStale.warnings[0] ?? "Tick anterior à frente do snapshot",
    });
    bump("warning");
  } else if (opts?.scoreIsFresh === false) {
    items.push({
      tone: "warn",
      label: "Placar",
      detail: "Tick de score mais novo que o advice — aguardando recalibração",
    });
    bump("caution");
  } else {
    items.push({ tone: "ok", label: "Placar", detail: "Consistente com último tick" });
  }

  if (opts?.adviceSource === "fast" && data.isLive && !data.isFinished) {
    items.push({
      tone: "warn",
      label: "Modelo",
      detail: "Poll rápido (MC reduzido) — trend/cash-out no ciclo full",
    });
    bump("caution");
  } else if (opts?.adviceSource === "full") {
    items.push({ tone: "ok", label: "Modelo", detail: "Ciclo completo (trend + box score)" });
  }

  if (dataAgeSec != null) {
    const ageLabel =
      dataAgeSec <= 45
        ? `${dataAgeSec}s`
        : dataAgeSec <= 120
          ? `${Math.round(dataAgeSec / 60)} min`
          : `${Math.round(dataAgeSec / 60)} min (antigo)`;
    items.push({
      tone: dataAgeSec > 120 ? "bad" : dataAgeSec > 60 ? "warn" : "ok",
      label: "Idade do advice",
      detail: ageLabel,
    });
    if (dataAgeSec > 120) bump("warning");
    else if (dataAgeSec > 60) bump("caution");
  }

  const deadCount = data.betGuardrails?.deadMarkets?.length ?? 0;
  if (deadCount > 0) {
    items.push({
      tone: "warn",
      label: "Mercados mortos",
      detail: `${deadCount} linha(s) bloqueada(s) pelo estado do jogo`,
    });
    bump("caution");
  }

  if (data.betGuardrails?.blockNewBets) {
    items.push({
      tone: "bad",
      label: "Novas entradas",
      detail: data.betGuardrails.blockReason ?? "Bloqueio operacional ativo",
    });
    bump("blocked");
  } else if (data.betGuardrails?.extrasWarning) {
    items.push({
      tone: "warn",
      label: "Extras",
      detail: "Jogo pode ir para entradas extras — cautela em totais FT",
    });
    bump("caution");
  }

  if (data.confidence) {
    items.push({
      tone: data.confidence.score >= 0.55 ? "ok" : "warn",
      label: "Confiança modelo",
      detail: `${data.confidence.label} · edge máx ${data.confidence.maxEdgePp.toFixed(1)} pp`,
    });
  }

  const scanCount = data.strategy?.marketScan?.length ?? 0;
  items.push({
    tone: scanCount > 0 ? "ok" : "muted",
    label: "Scan de mercados",
    detail: scanCount > 0 ? `${scanCount} linha(s) benchmarked` : "Sem benchmark disponível",
  });

  const titles: Record<BaseballQualityLevel, string> = {
    ok: "Dados operacionais OK",
    caution: "Atenção — validar antes de entrar",
    warning: "Qualidade degradada",
    blocked: "Sem novas entradas",
  };

  const subtitles: Record<BaseballQualityLevel, string> = {
    ok: "Feed, placar e modelo alinhados para decisão.",
    caution: "Alguns sinais pedem confirmação ou ciclo full.",
    warning: "Stale ou placar inconsistente — evite stake até refresh.",
    blocked: "Encerrado ou guardrails ativos.",
  };

  return {
    level,
    title: titles[level],
    subtitle: subtitles[level],
    items,
  };
}

export function sortBaseballMarketScan(data: BaseballSuperbetLiveAdvice) {
  return [...(data.strategy?.marketScan ?? [])].sort(
    (a, b) => Math.abs(b.edgePp) - Math.abs(a.edgePp),
  );
}
