import type { SuperbetLiveAdvice } from "@/domain/entities";
import type { MarketOperationalRow } from "./useMarketOperationalRows";

export type OperationalStatus = "entrar" | "aguardar" | "evitar" | "suspenso" | "desatualizado";

export interface OperationalDecision {
  status: OperationalStatus;
  title: string;
  reason: string;
  fairOdd: number | null;
  isFresh: boolean;
  dataAgeSec: number | null;
  pick: (MarketOperationalRow & { confidenceLabel: string }) | null;
}

export function secondsSince(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const ts = Date.parse(iso);
  if (Number.isNaN(ts)) return null;
  return Math.max(0, Math.floor((Date.now() - ts) / 1000));
}

export function formatOdd(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value) || value <= 1) return "-";
  return value.toFixed(2);
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value == null || !Number.isFinite(value)) return "-";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatMoney(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "-";
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

type AdviceSource = {
  market: string;
  outcome: string;
  label: string;
  modelProb: number;
  marketOdd: number;
  expectedValue: number;
  suggestedStakeValue?: number;
  impliedProb?: number;
  edgePp?: number;
  action?: string;
  fundamentacao?: string;
  timingReason?: string;
};

function isAdviceStale(data: SuperbetLiveAdvice): boolean {
  return Boolean((data as SuperbetLiveAdvice & { superbetStale?: boolean }).superbetStale);
}

function confidenceLabel(score: number): string {
  if (score >= 0.7) return "Alta";
  if (score >= 0.5) return "Média";
  return "Baixa";
}

function mapPostureToStatus(posture: string | undefined): OperationalStatus {
  const p = (posture ?? "").toLowerCase();
  if (p.includes("agress") || p.includes("entrar") || p.includes("attack")) return "entrar";
  if (p.includes("evitar") || p.includes("defens") || p.includes("stop")) return "evitar";
  if (p.includes("susp") || p.includes("revis")) return "suspenso";
  return "aguardar";
}

export function buildOperationalDecision(data: SuperbetLiveAdvice): OperationalDecision {
  const dataAgeSec = secondsSince(data.capturedAt);
  const isFresh = dataAgeSec != null && dataAgeSec <= 90 && !isAdviceStale(data);

  const topOpp = data.strategy?.opportunities?.[0] as AdviceSource | undefined;
  const topScan = [...(data.strategy?.marketScan ?? [])].sort(
    (a, b) => b.expectedValue - a.expectedValue,
  )[0] as AdviceSource | undefined;
  const topAporte = [...(data.aportes ?? [])].sort((a, b) => b.expectedValue - a.expectedValue)[0] as
    | AdviceSource
    | undefined;

  const source = topOpp ?? topScan ?? topAporte;
  const modelProb = source?.modelProb ?? 0;
  const fairOdd = modelProb > 0 ? 1 / modelProb : null;

  let status: OperationalStatus = mapPostureToStatus(data.strategy?.posture);
  let reason =
    data.strategy?.waitReason ||
    data.strategy?.shields?.[0]?.reason ||
    "Aguardando sinal operacional com edge e dados frescos.";

  if (!data.isLive || data.isFinished) {
    status = "evitar";
    reason = "Partida encerrada ou fora do ar — sem novas entradas.";
  } else if (isAdviceStale(data) || (dataAgeSec != null && dataAgeSec > 120)) {
    status = "desatualizado";
    reason = "Snapshot Superbet stale ou captura antiga — aguarde refresh antes de apostar.";
  } else if ((data.scoreStale?.scoreStale || data.scoreStale?.warnings?.length) && !source) {
    status = "suspenso";
    reason = data.scoreStale?.warnings?.[0] ?? "Placar/fonte pode estar divergente.";
  } else if (source && source.expectedValue > 0 && (topOpp?.action === "apostar" || topAporte?.action === "apostar")) {
    status = "entrar";
    reason = topOpp?.fundamentacao ?? topOpp?.timingReason ?? "Melhor oportunidade EV+ com confiança operacional.";
  } else if (source && source.expectedValue > 0) {
    status = "aguardar";
    reason = "Edge positivo, mas stake/Kelly abaixo do limiar de entrada imediata.";
  } else if (data.strategy?.strongOpportunityCount === 0) {
    status = "aguardar";
    reason = data.strategy?.waitReason || "Nenhum mercado forte acima do limiar mínimo.";
  }

  const shield = data.strategy?.shields?.find((s) => s.action === "evitar" || s.action === "aguardar");
  if (shield && status === "entrar" && shield.priority === "alta") {
    status = mapPostureToStatus(shield.action);
    reason = shield.reason;
  }

  const confidenceScore = Math.min(
    0.95,
    Math.max(0.05, (data.confidence?.score ?? 0.5) * 0.6 + Math.min(0.35, Math.max(0, (source?.expectedValue ?? 0) * 2))),
  );

  const pick: OperationalDecision["pick"] = source
    ? {
        key: `${source.market}:${source.outcome}`,
        label: source.label,
        market: source.market,
        outcome: source.outcome,
        type: "Mercado",
        period: "Jogo",
        marketOdd: source.marketOdd,
        fairOdd,
        modelProb: source.modelProb,
        impliedProb: source.impliedProb ?? 1 / Math.max(source.marketOdd, 1.01),
        expectedValue: source.expectedValue,
        edgePp: source.edgePp ?? (source.modelProb - 1 / source.marketOdd) * 100,
        suggestedStakeValue: Number(source.suggestedStakeValue ?? 0),
        pressureEstimate: 0,
        pressureLabel: "média",
        direction: "estavel",
        lastChangedAt: data.capturedAt,
        lastChangedAgeSec: dataAgeSec,
        confidenceScore,
        confidenceLabel: confidenceLabel(confidenceScore),
        status: status === "entrar" ? "ativo" : status === "evitar" ? "evitar" : "aguardar",
        action: source.action ?? (status === "entrar" ? "apostar" : "monitorar"),
      }
    : null;

  const titles: Record<OperationalStatus, string> = {
    entrar: "Entrada recomendada",
    aguardar: "Aguardar melhor linha",
    evitar: "Evitar novas entradas",
    suspenso: "Revisar antes de agir",
    desatualizado: "Dados desatualizados",
  };

  return {
    status,
    title: titles[status],
    reason,
    fairOdd,
    isFresh,
    dataAgeSec,
    pick,
  };
}
