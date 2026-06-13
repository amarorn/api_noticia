import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/infrastructure/api/client";
import { PageHeader } from "@/presentation/components/layout/PageHeader";
import { PageTransition } from "@/presentation/components/layout/PageTransition";

interface MetricSection {
  [key: string]: string | number | null | undefined;
}

interface BenchmarkSnapshot {
  run_id: string;
  timestamp: string;
  source: string;
  metrics: {
    wc_pregame: MetricSection;
    wc_walkforward: MetricSection;
    inplay: MetricSection;
    reconciliation: MetricSection;
    gbm?: MetricSection;
  };
  deltas?: Record<string, number | null>;
}

interface BenchmarkHistoryResponse {
  updated_at: string | null;
  latest: BenchmarkSnapshot | null;
  snapshots: BenchmarkSnapshot[];
  summary_labels: Record<string, string>;
}

interface EnsembleStatusResponse {
  mode: "shadow" | "canary" | "production";
  ready_for_production: boolean;
  shadow_mode_active: boolean;
  n_feedback_high_confidence: number;
  n_reconcile_pairs: number;
  n_tick_examples: number;
  inplay_delta_brier: number | null;
  feedback_gbm_accepted: boolean;
  checks: Record<string, boolean>;
  missing: string[];
  recommendation: string;
  assessed_at: string;
}

function formatTs(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(iso));
}

function formatPct(value: number | null | undefined, digits = 1): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

function formatNum(value: number | null | undefined, digits = 4): string {
  if (value == null) return "—";
  return Number(value).toFixed(digits);
}

function deltaClass(key: string, delta: number | null | undefined): string {
  if (delta == null || delta === 0) return "text-muted";
  const lowerIsBetter = key.includes("brier") || key.includes("pnl") === false && key.includes("delta");
  const improved = lowerIsBetter ? delta < 0 : delta > 0;
  if (key.includes("pnl") || key.includes("accuracy") || key.includes("hit_rate")) {
    return delta > 0 ? "text-emerald-400" : delta < 0 ? "text-red-400" : "text-muted";
  }
  if (key.includes("delta_brier")) {
    return delta < 0 ? "text-emerald-400" : delta > 0 ? "text-red-400" : "text-muted";
  }
  return improved ? "text-emerald-400" : "text-red-400";
}

function DeltaBadge({ metricKey, delta }: { metricKey: string; delta?: number | null }) {
  if (delta == null || delta === 0) return null;
  const sign = delta > 0 ? "+" : "";
  return (
    <span className={`ml-2 text-xs ${deltaClass(metricKey, delta)}`}>
      ({sign}
      {metricKey.includes("accuracy") || metricKey.includes("hit_rate")
        ? formatPct(delta, 1)
        : formatNum(delta, 4)}
      )
    </span>
  );
}

function SummaryCard({
  label,
  value,
  sub,
  metricKey,
  delta,
}: {
  label: string;
  value: string;
  sub?: string;
  metricKey: string;
  delta?: number | null;
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-surface-elevated/40 p-4">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-foreground">
        {value}
        <DeltaBadge metricKey={metricKey} delta={delta} />
      </p>
      {sub ? <p className="mt-1 text-xs text-muted">{sub}</p> : null}
    </div>
  );
}

function sourceLabel(source: string): string {
  const map: Record<string, string> = {
    "run-model-benchmark": "Benchmark manual",
    full_improvement: "Pipeline completo",
    wc_benchmark: "Benchmark WC",
    wc_walkforward: "Walkforward WC",
  };
  return map[source] ?? source;
}

export function ModelBenchmarkPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["model-benchmark-history"],
    queryFn: () => apiFetch<BenchmarkHistoryResponse>("/worldcup/benchmarks/history"),
  });

  const { data: ensemble } = useQuery({
    queryKey: ["inplay-ensemble-status"],
    queryFn: () => apiFetch<EnsembleStatusResponse>("/worldcup/inplay/ensemble-status"),
  });

  const latest = data?.latest;
  const m = latest?.metrics;
  const d = latest?.deltas ?? {};

  const rows = data?.snapshots?.slice().reverse() ?? [];

  return (
    <PageTransition>
      <PageHeader
        title="Qualidade dos modelos"
        description="Benchmark atual e histórico de evolução (WC pré-jogo, in-play e apostas reais)."
      />

      {isLoading ? (
        <p className="text-muted">Carregando histórico…</p>
      ) : error ? (
        <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/10 p-4 text-sm text-yellow-200">
          Histórico ainda não gerado. Execute no backend:{" "}
          <code className="rounded bg-black/30 px-1">run-model-benchmark --seed-only</code>
        </div>
      ) : (
        <>
          {ensemble ? (
            <section
              className={`mb-6 rounded-xl border p-4 ${
                ensemble.ready_for_production
                  ? "border-emerald-500/40 bg-emerald-500/10"
                  : ensemble.mode === "canary"
                    ? "border-yellow-500/40 bg-yellow-500/10"
                    : "border-border/60 bg-surface-elevated/40"
              }`}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted">Ensemble in-play (GBM)</p>
                  <p className="mt-1 text-lg font-semibold capitalize text-foreground">
                    Modo {ensemble.mode}
                    {ensemble.shadow_mode_active ? " · shadow ativo" : " · produção"}
                  </p>
                  <p className="mt-2 text-sm text-muted">{ensemble.recommendation}</p>
                </div>
                <div className="grid gap-2 text-sm sm:grid-cols-3">
                  <div>
                    <span className="text-muted">Alta conf.</span>
                    <p className="font-medium">
                      {ensemble.n_feedback_high_confidence} / 500
                    </p>
                  </div>
                  <div>
                    <span className="text-muted">Ticks rotulados</span>
                    <p className="font-medium">{ensemble.n_tick_examples}</p>
                  </div>
                  <div>
                    <span className="text-muted">Δ Brier in-play</span>
                    <p className="font-medium">{formatNum(ensemble.inplay_delta_brier)}</p>
                  </div>
                </div>
              </div>
              {data?.latest?.metrics?.wc_walkforward?.mean_accuracy != null ? (
                <p className="mt-3 text-xs text-muted">
                  Walkforward WC: {formatPct(data.latest.metrics.wc_walkforward.mean_accuracy as number)}{" "}
                  · Brier {formatNum(data.latest.metrics.wc_walkforward.mean_brier as number)}
                </p>
              ) : null}
            </section>
          ) : null}

          {latest && m ? (
            <section className="mb-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <SummaryCard
                label="WC holdout (acc)"
                value={formatPct(m.wc_pregame.artifact_holdout_accuracy as number)}
                sub={`Artefato ${formatTs(String(m.wc_pregame.artifact_created_at ?? latest.timestamp))}`}
                metricKey="wc_pregame.artifact_holdout_accuracy"
                delta={d["wc_pregame.artifact_holdout_accuracy"]}
              />
              <SummaryCard
                label="WC Brier (benchmark)"
                value={formatNum(m.wc_pregame.benchmark_brier as number)}
                sub={String(m.wc_pregame.benchmark_best_model ?? "ensemble")}
                metricKey="wc_pregame.benchmark_brier"
                delta={d["wc_pregame.benchmark_brier"]}
              />
              <SummaryCard
                label="In-play Brier (live)"
                value={formatNum(m.inplay.live_brier_modelo as number)}
                sub={`${m.inplay.n_live_events ?? 0} eventos · ${m.inplay.n_live_ticks ?? 0} ticks`}
                metricKey="inplay.live_brier_modelo"
                delta={d["inplay.live_brier_modelo"]}
              />
              <SummaryCard
                label="In-play vs mercado"
                value={formatNum(m.inplay.live_delta_brier as number)}
                sub={
                  m.inplay.live_brier_mercado != null
                    ? `Mercado ${formatNum(m.inplay.live_brier_mercado as number)}`
                    : undefined
                }
                metricKey="inplay.live_delta_brier"
                delta={d["inplay.live_delta_brier"]}
              />
              <SummaryCard
                label="Walkforward acc média"
                value={formatPct(m.wc_walkforward.mean_accuracy as number)}
                sub={`${m.wc_walkforward.editions_evaluated ?? "—"} edições`}
                metricKey="wc_walkforward.mean_accuracy"
                delta={d["wc_walkforward.mean_accuracy"]}
              />
              <SummaryCard
                label="Walkforward Brier média"
                value={formatNum(m.wc_walkforward.mean_brier as number)}
                metricKey="wc_walkforward.mean_brier"
                delta={d["wc_walkforward.mean_brier"]}
              />
              <SummaryCard
                label="Hit rate apostas"
                value={formatPct(m.reconciliation.hit_rate as number)}
                sub={`${m.reconciliation.n_bets ?? 0} bilhetes`}
                metricKey="reconciliation.hit_rate"
                delta={d["reconciliation.hit_rate"]}
              />
              <SummaryCard
                label="P&L reconciliação"
                value={
                  m.reconciliation.pnl != null
                    ? new Intl.NumberFormat("pt-BR", {
                        style: "currency",
                        currency: "BRL",
                      }).format(Number(m.reconciliation.pnl))
                    : "—"
                }
                metricKey="reconciliation.pnl"
                delta={d["reconciliation.pnl"]}
              />
            </section>
          ) : null}

          <section className="overflow-x-auto rounded-xl border border-border/60">
            <table className="min-w-full text-sm">
              <thead className="bg-surface-elevated/60 text-left text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="px-4 py-3">Data</th>
                  <th className="px-4 py-3">Origem</th>
                  <th className="px-4 py-3">WC acc</th>
                  <th className="px-4 py-3">WC Brier</th>
                  <th className="px-4 py-3">WF acc</th>
                  <th className="px-4 py-3">WF Brier</th>
                  <th className="px-4 py-3">In-play Brier</th>
                  <th className="px-4 py-3">Δ mercado</th>
                  <th className="px-4 py-3">Hit rate</th>
                  <th className="px-4 py-3">P&L</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {rows.map((row) => {
                  const wm = row.metrics;
                  return (
                    <tr key={row.run_id} className="hover:bg-surface-elevated/30">
                      <td className="whitespace-nowrap px-4 py-3">{formatTs(row.timestamp)}</td>
                      <td className="px-4 py-3">{sourceLabel(row.source)}</td>
                      <td className="px-4 py-3">
                        {formatPct(wm.wc_pregame.artifact_holdout_accuracy as number)}
                      </td>
                      <td className="px-4 py-3">
                        {formatNum(
                          (wm.wc_pregame.benchmark_brier ?? wm.wc_pregame.artifact_brier) as number
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {formatPct(wm.wc_walkforward.mean_accuracy as number)}
                      </td>
                      <td className="px-4 py-3">{formatNum(wm.wc_walkforward.mean_brier as number)}</td>
                      <td className="px-4 py-3">{formatNum(wm.inplay.live_brier_modelo as number)}</td>
                      <td className="px-4 py-3">{formatNum(wm.inplay.live_delta_brier as number)}</td>
                      <td className="px-4 py-3">{formatPct(wm.reconciliation.hit_rate as number)}</td>
                      <td className="px-4 py-3">
                        {wm.reconciliation.pnl != null
                          ? Number(wm.reconciliation.pnl).toFixed(2)
                          : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>

          {data?.updated_at ? (
            <p className="mt-4 text-xs text-muted">
              Histórico atualizado em {formatTs(data.updated_at)} · {data.snapshots.length}{" "}
              medições
            </p>
          ) : null}
        </>
      )}
    </PageTransition>
  );
}
