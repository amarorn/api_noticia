import type { ReactNode } from "react";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import type { MarketOperationalRow } from "@/presentation/components/live-operational/useMarketOperationalRows";
import type { DataQualityReport } from "@/presentation/components/live-operational/dataQuality";
import {
  IconActivity,
  IconAlertTriangle,
  IconBell,
  IconClock,
  IconDatabase,
  IconInfo,
  IconShieldCheck,
  IconTrendingUp,
} from "@/presentation/components/ui/Icons";
import { ScoreShieldV2, RadialGaugeV2, SectionTitleV2 } from "./live-ui-v2";

const ALERT_META: Record<string, { severity: "Alto" | "Médio"; icon: ReactNode }> = {
  "Dados potencialmente desatualizados.": { severity: "Alto", icon: <IconAlertTriangle className="h-4 w-4" /> },
  "Frequência de atualização abaixo do ideal.": { severity: "Alto", icon: <IconActivity className="h-4 w-4" /> },
  "Há muitos mercados com campos incompletos.": { severity: "Médio", icon: <IconAlertTriangle className="h-4 w-4" /> },
  "Muitos mercados em estado de evitar/revisar.": { severity: "Médio", icon: <IconInfo className="h-4 w-4" /> },
  "Odds mudando rápido demais em múltiplos mercados.": { severity: "Médio", icon: <IconActivity className="h-4 w-4" /> },
  "Baixa confiança média dos sinais.": { severity: "Médio", icon: <IconShieldCheck className="h-4 w-4" /> },
  "Há inconsistência entre EV alto e baixa confiança.": { severity: "Alto", icon: <IconAlertTriangle className="h-4 w-4" /> },
  "Placar ou fonte pode estar divergente.": { severity: "Alto", icon: <IconAlertTriangle className="h-4 w-4" /> },
  "Resposta Superbet veio de fallback/stale.": { severity: "Alto", icon: <IconAlertTriangle className="h-4 w-4" /> },
};
const DEFAULT_ALERT_META = { severity: "Médio" as const, icon: <IconInfo className="h-4 w-4" /> };

const SEVERITY_TONE: Record<"Alto" | "Médio", string> = {
  Alto: "border-red-400/30 bg-red-400/10 text-red-300",
  Médio: "border-amber-400/30 bg-amber-400/10 text-amber-300",
};

function GaugeMetricCard({
  icon,
  label,
  pct,
  displayValue,
  tone,
  caption,
}: {
  icon: ReactNode;
  label: string;
  pct: number;
  displayValue: string;
  tone: "green" | "amber" | "red" | "cyan";
  caption: string;
}) {
  const captionTone: Record<string, string> = {
    green: "text-emerald-300",
    amber: "text-amber-300",
    red: "text-red-300",
    cyan: "text-cyan-300",
  };
  return (
    <div className="panel-v2 flex flex-col items-center p-4 text-center">
      <span className="mb-2 grid h-7 w-7 place-items-center rounded-lg border border-white/8 bg-white/[0.04] text-slate-400">
        {icon}
      </span>
      <p className="text-[9px] font-black uppercase tracking-[0.12em] text-slate-500">{label}</p>
      <div className="mt-3">
        <RadialGaugeV2 pct={pct} label={displayValue} tone={tone} />
      </div>
      <p className={`mt-3 text-[11px] font-bold ${captionTone[tone]}`}>{caption}</p>
    </div>
  );
}

export function LiveDataQualityV2({
  data,
  rows,
  report,
  onOpenMarkets,
}: {
  data: SuperbetLiveAdvice;
  rows: MarketOperationalRow[];
  report: DataQualityReport;
  onOpenMarkets?: () => void;
}) {
  const confidencePct = Math.round(report.avgConfidence * 100);
  const confidenceTone: "green" | "amber" | "red" = confidencePct >= 70 ? "green" : confidencePct >= 50 ? "amber" : "red";
  const confidenceCaption = confidencePct >= 70 ? "Confiança forte" : confidencePct >= 50 ? "Baixa confiança" : "Confiança crítica";

  const intervalSec = report.avgUpdateSec ?? 0;
  const intervalPct = Math.max(0, Math.min(100, 100 - (intervalSec / 60) * 100));
  const intervalTone: "green" | "amber" | "red" = intervalSec <= 20 ? "green" : intervalSec <= 40 ? "amber" : "red";

  const completeTone: "green" | "amber" | "red" = report.completePct >= 90 ? "green" : report.completePct >= 70 ? "amber" : "red";
  const completeCaption = report.completePct >= 90 ? "Saudável" : report.completePct >= 70 ? "Atenção" : "Crítico";

  const evTone: "green" | "amber" | "red" = report.positiveEvPct >= 40 ? "green" : report.positiveEvPct >= 20 ? "amber" : "red";
  const evCaption = report.positiveEvPct >= 40 ? "Saudável" : report.positiveEvPct >= 20 ? "Abaixo do ideal" : "Crítico";

  const ageSec = data.capturedAt ? Math.floor((Date.now() - Date.parse(data.capturedAt)) / 1000) : null;

  return (
    <div className="space-y-4">
      {/* Primeira linha: score + 5 gauges + alertas */}
      <div className="grid gap-3 xl:grid-cols-[minmax(280px,1.3fr)_repeat(4,minmax(0,1fr))_minmax(140px,1fr)]">
        <div className="panel-v2 flex items-center gap-5 p-5 sm:p-6">
          <ScoreShieldV2 score={report.score} status={report.status} />
          <div className="min-w-0">
            <p className="text-xs font-black uppercase tracking-widest text-slate-500">Qualidade dos dados</p>
            <p className="mt-2 text-xs text-slate-400">
              {report.status === "Fraca"
                ? "Qualidade abaixo do ideal. Atenção com sinais instáveis e mercados suspensos."
                : report.status === "Crítica"
                ? "Qualidade crítica. Evite decisões até a próxima captura válida."
                : report.status === "Atenção"
                ? "Qualidade em atenção. Revise os alertas antes de confiar totalmente nos sinais."
                : "Dados frescos e consistentes. Sinais aptos para decisão."}
            </p>
          </div>
        </div>

        <GaugeMetricCard
          icon={<IconShieldCheck className="h-4 w-4" />}
          label="Confiança Média"
          pct={confidencePct}
          displayValue={`${confidencePct}%`}
          tone={confidenceTone}
          caption={confidenceCaption}
        />
        <GaugeMetricCard
          icon={<IconClock className="h-4 w-4" />}
          label="Intervalo Médio"
          pct={intervalPct}
          displayValue={intervalSec ? `${intervalSec}s` : "N/D"}
          tone={intervalTone}
          caption="Atualização"
        />
        <GaugeMetricCard
          icon={<IconDatabase className="h-4 w-4" />}
          label="Mercados Completos"
          pct={report.completePct}
          displayValue={`${report.completePct}%`}
          tone={completeTone}
          caption={completeCaption}
        />
        <GaugeMetricCard
          icon={<IconTrendingUp className="h-4 w-4" />}
          label="EV Positivo"
          pct={report.positiveEvPct}
          displayValue={`${report.positiveEvPct}%`}
          tone={evTone}
          caption={evCaption}
        />
        <div className={`panel-v2 flex flex-col items-center justify-center p-4 text-center ${report.alerts.length > 0 ? "border-amber-400/25 bg-amber-400/[0.06]" : ""}`}>
          <IconBell className="h-6 w-6 text-amber-300" />
          <p className="mt-2 font-mono text-3xl font-black text-white">{report.alerts.length}</p>
          <p className="text-[10px] font-black uppercase tracking-[0.12em] text-slate-500">Alertas Ativos</p>
          <p className="mt-1 text-[11px] font-semibold text-amber-300">itens ativos</p>
        </div>
      </div>

      {/* Alertas + Frescor */}
      <div className="grid gap-4 xl:grid-cols-2">
        <section className="panel-v2 p-4 sm:p-5">
          <SectionTitleV2
            title={`Alertas Ativos ${report.alerts.length > 0 ? `(${report.alerts.length})` : ""}`}
            icon={<IconBell className="h-3.5 w-3.5" />}
          />
          {report.alerts.length === 0 ? (
            <p className="mt-3 rounded-xl border border-emerald-400/20 bg-emerald-400/10 px-3 py-3 text-sm text-emerald-200">
              Sem alertas relevantes. Dados aptos para leitura operacional.
            </p>
          ) : (
            <div className="mt-3 space-y-2">
              {report.alerts.map((alert) => {
                const meta = ALERT_META[alert] ?? DEFAULT_ALERT_META;
                return (
                  <div
                    key={alert}
                    className="flex items-center gap-3 rounded-xl border border-white/8 bg-white/[0.03] px-3 py-2.5 text-sm text-slate-200"
                  >
                    <span className="shrink-0 text-amber-300">{meta.icon}</span>
                    <span className="min-w-0 flex-1">{alert}</span>
                    <span className={`pill-v2 shrink-0 border px-2 py-0.5 text-[10px] ${SEVERITY_TONE[meta.severity]}`}>
                      {meta.severity}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        <section className="panel-v2 p-4 sm:p-5">
          <div className="mb-4 flex items-center justify-between gap-3">
            <SectionTitleV2 title="Frescor dos Dados" icon={<IconClock className="h-3.5 w-3.5" />} />
            <span className="pill-v2 border border-emerald-400/25 bg-emerald-400/10 text-emerald-300">
              Atual: {ageSec != null ? `${ageSec}s` : "sem captura"}
            </span>
          </div>

          <div className="relative mt-6 px-2">
            <div className="h-1 rounded-full bg-white/8">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: "75%", background: "linear-gradient(90deg, #10b981, #fbbf24)" }}
              />
            </div>
            <div className="mt-4 flex items-center justify-between">
              {[
                { label: "15m", status: "Muito bom", tone: "#10b981" },
                { label: "10m", status: "Bom", tone: "#10b981" },
                { label: "5m", status: "Atenção", tone: "#22d3ee" },
                { label: "2m", status: "Ruim", tone: "#fbbf24" },
                { label: "Agora", status: "Crítico", tone: "#f87171" },
              ].map((bucket, i) => (
                <div key={bucket.label} className="flex flex-col items-center gap-1 text-center" style={{ width: "20%" }}>
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{
                      background: i === 3 ? bucket.tone : "rgba(148,163,184,0.25)",
                      boxShadow: i === 3 ? `0 0 10px ${bucket.tone}` : "none",
                    }}
                  />
                  <span className="text-[10px] font-bold text-slate-400">{bucket.label}</span>
                  <span className="text-[9px] text-slate-600">{bucket.status}</span>
                </div>
              ))}
            </div>
          </div>

          {report.avgUpdateSec != null && report.avgUpdateSec > 20 && (
            <div className="mt-4 flex items-start gap-2 rounded-xl border border-amber-400/20 bg-amber-400/[0.06] px-3 py-2.5 text-xs text-amber-100">
              <span className="mt-0.5 shrink-0 text-amber-300">⏱</span>
              Intervalo de atualização {report.avgUpdateSec}s está acima do ideal (≤ 20s). Maior latência pode impactar a precisão dos sinais.
            </div>
          )}
        </section>
      </div>

      {/* Mercados suspeitos + Distribuição */}
      <div className="grid gap-4 xl:grid-cols-2">
        <LiveSuspiciousMarketsV2 rows={rows} onOpenMarkets={onOpenMarkets} />
        <LiveMarketDistributionV2 rows={rows} />
      </div>
    </div>
  );
}

function LiveSuspiciousMarketsV2({ rows, onOpenMarkets }: { rows: MarketOperationalRow[]; onOpenMarkets?: () => void }) {
  const total = rows.length || 1;
  const counts = { alta: 0, media: 0, baixa: 0 };
  for (const row of rows) {
    if (row.status === "evitar") counts.alta += 1;
    else if (row.confidenceScore < 0.5 || row.direction === "esticando") counts.media += 1;
    else counts.baixa += 1;
  }
  const pct = (tier: "alta" | "media" | "baixa") => Math.round((counts[tier] / total) * 100);
  const riskPct = pct("alta") + pct("media");
  const colors = { alta: "#f87171", media: "#fbbf24", baixa: "#10b981" };
  const labels = { alta: "Alta suspeita", media: "Média suspeita", baixa: "Baixa suspeita" };

  return (
    <section className="panel-v2 p-4 sm:p-5">
      <SectionTitleV2 title="Mercados Suspeitos" icon={<IconInfo className="h-3.5 w-3.5" />} />
      <p className="mt-2 font-mono text-4xl font-black text-red-400">{riskPct}%</p>
      <p className="text-xs text-slate-500">dos mercados apresentam sinais de risco</p>

      <div className="mt-5 flex h-2 overflow-hidden rounded-full bg-white/8">
        {(["alta", "media", "baixa"] as const).map((tier) => (
          <div key={tier} style={{ width: `${pct(tier)}%`, background: colors[tier] }} />
        ))}
      </div>

      <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
        {(["alta", "media", "baixa"] as const).map((tier) => (
          <span key={tier} className="flex items-center gap-1.5 text-xs font-semibold text-slate-400">
            <span className="h-2 w-2 rounded-full" style={{ background: colors[tier] }} />
            {pct(tier)}% {labels[tier]}
          </span>
        ))}
      </div>

      {onOpenMarkets && (
        <button type="button" onClick={onOpenMarkets} className="mt-4 text-xs font-bold text-neon-green hover:underline">
          Ver mercados →
        </button>
      )}
    </section>
  );
}

function LiveMarketDistributionV2({ rows }: { rows: MarketOperationalRow[] }) {
  const total = rows.length || 1;
  const counts = { encurtando: 0, esticando: 0, estavel: 0, suspensos: 0 };
  for (const row of rows) {
    if (row.status === "evitar") counts.suspensos += 1;
    else if (row.direction === "encurtando") counts.encurtando += 1;
    else if (row.direction === "esticando") counts.esticando += 1;
    else counts.estavel += 1;
  }
  const order: ("encurtando" | "estavel" | "esticando" | "suspensos")[] = ["encurtando", "estavel", "esticando", "suspensos"];
  const colors = { encurtando: "#10b981", esticando: "#fbbf24", estavel: "#94a3b8", suspensos: "#f87171" };
  const labels = { encurtando: "Encurtando", esticando: "Esticando", estavel: "Estável", suspensos: "Suspensos" };

  return (
    <section className="panel-v2 p-4 sm:p-5">
      <SectionTitleV2 title="Distribuição do Estado dos Mercados" icon={<IconInfo className="h-3.5 w-3.5" />} />

      <div className="mt-5 flex h-2.5 overflow-hidden rounded-full bg-white/8">
        {order.map((bucket) => (
          <div key={bucket} style={{ width: `${Math.round((counts[bucket] / total) * 100)}%`, background: colors[bucket] }} />
        ))}
      </div>

      <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
        {order.map((bucket) => (
          <span key={bucket} className="flex items-center gap-1.5 text-xs font-semibold text-slate-400">
            <span className="h-2 w-2 rounded-full" style={{ background: colors[bucket] }} />
            {labels[bucket]} {Math.round((counts[bucket] / total) * 100)}% ({counts[bucket]})
          </span>
        ))}
      </div>
    </section>
  );
}
