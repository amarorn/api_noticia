import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  walletRepository,
  type ReconciliationItem,
  type WalletSummary,
} from "@/infrastructure/repositories/walletRepository";
import { PageHeader } from "@/presentation/components/layout/PageHeader";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { WalletSyncBanner } from "@/presentation/components/wallet/WalletSyncBanner";

const DEFAULT_USER = "jamarorn";

function formatBRL(value: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    minimumFractionDigits: 2,
  }).format(value);
}

function formatPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function computeRoi(pnl: number, staked: number): number | null {
  if (staked <= 0) return null;
  return pnl / staked;
}

function formatRoiSigned(roi: number | null): string {
  if (roi === null) return "—";
  const pct = roi * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`;
}

function roiTextColor(roi: number | null): string {
  if (roi === null) return "text-slate-400";
  if (roi > 0) return "text-emerald-400";
  if (roi < 0) return "text-red-400";
  return "text-slate-300";
}

// ---------------------------------------------------------------------------
// CSV Dropzone
// ---------------------------------------------------------------------------

function CsvDropzone({
  userId,
  onUploaded,
}: {
  userId: string;
  onUploaded: () => void;
}) {
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const upload = useMutation({
    mutationFn: (file: File) => walletRepository.upload(file, userId),
    onSuccess: () => {
      setError(null);
      onUploaded();
    },
    onError: (err: Error) => setError(err.message),
  });

  const handleFile = (file: File | null | undefined) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Por favor envie um arquivo .csv");
      return;
    }
    upload.mutate(file);
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handleFile(e.dataTransfer.files[0]);
      }}
      onClick={() => inputRef.current?.click()}
      className={`cursor-pointer rounded-2xl border-2 border-dashed p-8 text-center transition-colors ${
        dragOver
          ? "border-emerald-400 bg-emerald-500/10"
          : "border-white/15 bg-white/5 hover:border-white/30"
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
      {upload.isPending ? (
        <div>
          <div className="text-sm text-emerald-300">Enviando e processando...</div>
        </div>
      ) : upload.isSuccess ? (
        <div>
          <div className="text-base font-semibold text-emerald-400">
            CSV processado: {upload.data.n_rows} linhas
          </div>
          <div className="mt-1 text-xs text-slate-400">
            {upload.data.n_inplay_bets_placed} bilhetes in-play · {upload.data.n_wins} ganhos ·
            P&L bruto {formatBRL(upload.data.pnl)}
          </div>
          <div className="mt-2 text-xs text-slate-500">
            Clique para enviar outro CSV
          </div>
        </div>
      ) : (
        <div>
          <div className="text-base font-semibold text-slate-200">
            Arraste o CSV de transações Superbet
          </div>
          <div className="mt-1 text-xs text-slate-500">
            ou salve em{" "}
            <span className="font-mono text-slate-400">
              data/lake/inbox/wallet/{userId}/
            </span>{" "}
            · usuário: <span className="font-mono">{userId}</span>
          </div>
        </div>
      )}
      {error && (
        <div className="mt-3 text-xs text-red-400">{error}</div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// KPI Cards
// ---------------------------------------------------------------------------

function KpiCard({
  label,
  value,
  trend,
  hint,
}: {
  label: string;
  value: string;
  trend?: "up" | "down" | "neutral";
  hint?: string;
}) {
  const trendColor =
    trend === "up" ? "text-emerald-400" : trend === "down" ? "text-red-400" : "text-slate-300";
  const trendIcon = trend === "up" ? "▲" : trend === "down" ? "▼" : "━";

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
      <div className="text-xs uppercase tracking-wider text-slate-400">{label}</div>
      <div className={`mt-2 text-2xl font-bold ${trendColor}`}>
        {trend && <span className="mr-2 text-base">{trendIcon}</span>}
        {value}
      </div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

function WalletKpiCards({ summary }: { summary: WalletSummary }) {
  const pnlTrend = summary.pnl > 0 ? "up" : summary.pnl < 0 ? "down" : "neutral";
  const roiTrend = summary.roi > 0 ? "up" : summary.roi < 0 ? "down" : "neutral";
  const hitTrend = summary.hit_rate >= 0.5 ? "up" : summary.hit_rate < 0.4 ? "down" : "neutral";

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      <KpiCard
        label="P&L"
        value={formatBRL(summary.pnl)}
        trend={pnlTrend}
        hint={`${summary.n_bets_placed} bilhetes`}
      />
      <KpiCard
        label="ROI"
        value={formatPct(summary.roi)}
        trend={roiTrend}
        hint={`Stake ${formatBRL(summary.total_staked)}`}
      />
      <KpiCard
        label="Hit Rate"
        value={formatPct(summary.hit_rate)}
        trend={hitTrend}
        hint={`${summary.n_bets_won} ganhos`}
      />
      <KpiCard
        label="Saldo Atual"
        value={formatBRL(summary.current_balance)}
        hint={`Depósitos ${formatBRL(summary.total_deposits)}`}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Balance chart (saldo no tempo)
// ---------------------------------------------------------------------------

function BalanceChart({ summary }: { summary: WalletSummary }) {
  if (!summary.balance_series.length) {
    return null;
  }

  const points = summary.balance_series;
  const maxBalance = Math.max(...points.map((p) => p.balance), 1);
  const minBalance = Math.min(...points.map((p) => p.balance), 0);
  const range = Math.max(maxBalance - minBalance, 1);

  const width = 720;
  const height = 180;
  const path = points
    .map((p, i) => {
      const x = (i / Math.max(points.length - 1, 1)) * width;
      const y = height - ((p.balance - minBalance) / range) * height;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const lastPoint = points[points.length - 1];
  const trend = lastPoint.balance >= points[0].balance ? "up" : "down";
  const stroke = trend === "up" ? "#10b981" : "#ef4444";

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-200">Saldo ao longo do tempo</h3>
        <div className="text-xs text-slate-500">
          {points.length} pontos · {formatBRL(minBalance)} → {formatBRL(maxBalance)}
        </div>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-[180px] w-full">
        <path d={path} fill="none" stroke={stroke} strokeWidth="2" />
        <line x1="0" y1={height} x2={width} y2={height} stroke="rgba(255,255,255,0.1)" />
      </svg>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ROI breakdown
// ---------------------------------------------------------------------------

function RoiBreakdownSection({
  summary,
  reconciliationItems,
}: {
  summary: WalletSummary;
  reconciliationItems: ReconciliationItem[];
}) {
  const reconciled = useMemo(() => {
    if (!reconciliationItems.length) return null;
    const staked = reconciliationItems.reduce((s, it) => s + it.stake, 0);
    const pnl = reconciliationItems.reduce((s, it) => s + it.pnl, 0);
    const matched = reconciliationItems.filter((it) => it.match_confidence >= 0.5).length;
    const highConf = reconciliationItems.filter((it) => it.match_confidence >= 0.7).length;
    return {
      n: reconciliationItems.length,
      staked,
      pnl,
      roi: computeRoi(pnl, staked),
      matched,
      highConf,
    };
  }, [reconciliationItems]);

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-5 space-y-5">
      <div>
        <h3 className="text-sm font-semibold text-slate-200">Seu ROI</h3>
        <p className="mt-1 text-xs text-slate-500">
          ROI = P&L ÷ stake líquido · {formatBRL(summary.pnl)} ÷ {formatBRL(summary.total_staked)}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <div className="rounded-xl bg-white/5 px-4 py-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500">ROI geral</div>
          <div className={`mt-1 text-xl font-bold ${roiTextColor(summary.roi)}`}>
            {formatRoiSigned(summary.roi)}
          </div>
        </div>
        <div className="rounded-xl bg-white/5 px-4 py-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500">P&L</div>
          <div className={`mt-1 text-xl font-bold ${roiTextColor(computeRoi(summary.pnl, summary.total_staked))}`}>
            {formatBRL(summary.pnl)}
          </div>
        </div>
        <div className="rounded-xl bg-white/5 px-4 py-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500">Hit rate</div>
          <div className="mt-1 text-xl font-bold text-slate-200">{formatPct(summary.hit_rate)}</div>
          <div className="text-[10px] text-slate-500">{summary.n_bets_won} ganhos</div>
        </div>
        <div className="rounded-xl bg-white/5 px-4 py-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500">Stake</div>
          <div className="mt-1 text-xl font-bold text-slate-200">{formatBRL(summary.total_staked)}</div>
          <div className="text-[10px] text-slate-500">{summary.n_bets_placed} bilhetes</div>
        </div>
      </div>

      {summary.daily_pnl.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            ROI por dia
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-slate-500 border-b border-white/10">
                  <th className="pb-2 pr-4">Data</th>
                  <th className="pb-2 pr-4 text-right">ROI</th>
                  <th className="pb-2 pr-4 text-right">P&L</th>
                  <th className="pb-2 pr-4 text-right">Stake</th>
                  <th className="pb-2 text-right">Apostas</th>
                </tr>
              </thead>
              <tbody>
                {summary.daily_pnl.map((d) => {
                  const roi = computeRoi(d.pnl, d.staked);
                  return (
                    <tr
                      key={d.date}
                      className={`border-b border-white/5 ${d.is_today ? "bg-emerald-500/5" : ""}`}
                    >
                      <td className="py-2 pr-4 font-mono text-slate-300">
                        {d.date}
                        {d.is_today && (
                          <span className="ml-2 rounded bg-emerald-500/20 px-1.5 py-0.5 text-[10px] text-emerald-300">
                            hoje
                          </span>
                        )}
                        {d.supplemental && !d.is_today && (
                          <span className="ml-1 text-[10px] text-slate-600">+ext</span>
                        )}
                      </td>
                      <td className={`py-2 pr-4 text-right font-semibold ${roiTextColor(roi)}`}>
                        {formatRoiSigned(roi)}
                      </td>
                      <td className={`py-2 pr-4 text-right font-mono ${d.pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                        {formatBRL(d.pnl)}
                      </td>
                      <td className="py-2 pr-4 text-right font-mono text-slate-400">
                        {formatBRL(d.staked)}
                      </td>
                      <td className="py-2 text-right text-slate-500">{d.n_bets}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {summary.by_game_type.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            ROI por categoria
          </h4>
          <div className="space-y-2">
            {summary.by_game_type.map((g) => {
              const roi = computeRoi(g.pnl, g.staked);
              return (
                <div
                  key={g.category}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-white/5 px-3 py-2 text-xs"
                >
                  <div className="flex items-center gap-2">
                    <span className="capitalize font-medium text-slate-200">{g.category}</span>
                    <span className="text-slate-500">({g.n_bets} apostas)</span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className={`font-semibold ${roiTextColor(roi)}`}>
                      {formatRoiSigned(roi)}
                    </span>
                    <span className={g.pnl >= 0 ? "text-emerald-400" : "text-red-400"}>
                      {formatBRL(g.pnl)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {reconciled && (
        <div className="rounded-xl border border-white/10 bg-black/20 px-4 py-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            ROI reconciliado (com snapshot do modelo)
          </h4>
          <div className="mt-2 flex flex-wrap items-baseline gap-x-6 gap-y-1">
            <span className={`text-lg font-bold ${roiTextColor(reconciled.roi)}`}>
              {formatRoiSigned(reconciled.roi)}
            </span>
            <span className="text-xs text-slate-400">
              {reconciled.n} pares · P&L {formatBRL(reconciled.pnl)} · stake {formatBRL(reconciled.staked)}
            </span>
          </div>
          <p className="mt-1 text-[10px] text-slate-600">
            Match ≥ 0,5: {reconciled.matched} · alta confiança ≥ 0,7: {reconciled.highConf}
          </p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Daily P&L bars
// ---------------------------------------------------------------------------

function DailyPnlBars({ summary }: { summary: WalletSummary }) {
  const days = summary.daily_pnl;
  if (!days.length) return null;

  const maxAbs = Math.max(...days.map((d) => Math.abs(d.pnl)), 1);

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
      <h3 className="mb-3 text-sm font-semibold text-slate-200">P&L por dia</h3>
      <div className="space-y-2">
        {days.map((d) => {
          const widthPct = (Math.abs(d.pnl) / maxAbs) * 100;
          const positive = d.pnl >= 0;
          return (
            <div
              key={d.date}
              className={`flex items-center gap-3 ${d.is_today ? "opacity-100" : ""}`}
            >
              <div className="w-28 shrink-0 text-xs text-slate-400">
                {d.date}
                {d.is_today && <span className="ml-1 text-emerald-400">· hoje</span>}
              </div>
              <div className="relative flex h-6 flex-1 items-center bg-white/5 rounded">
                <div
                  className={`absolute h-full rounded ${positive ? "bg-emerald-500/60" : "bg-red-500/60"}`}
                  style={{ width: `${widthPct}%` }}
                />
                <span className="relative ml-2 text-xs font-mono text-white">
                  {formatBRL(d.pnl)}
                </span>
              </div>
              <div className="w-14 shrink-0 text-right text-xs text-slate-500">
                {formatRoiSigned(computeRoi(d.pnl, d.staked))}
              </div>
              <div className="w-12 shrink-0 text-right text-xs text-slate-500">
                {d.n_bets} bets
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Game type breakdown
// ---------------------------------------------------------------------------

function BetTypeBreakdown({ summary }: { summary: WalletSummary }) {
  if (!summary.by_game_type.length) return null;

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
      <h3 className="mb-3 text-sm font-semibold text-slate-200">Onde o dinheiro vai</h3>
      <div className="space-y-2">
        {summary.by_game_type.map((g) => {
          const positive = g.pnl >= 0;
          return (
            <div key={g.category} className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <span className="capitalize">{g.category}</span>
                <span className="text-slate-500">({g.n_bets} bets)</span>
              </div>
              <div className="flex items-center gap-3">
                <span className={`font-semibold ${roiTextColor(computeRoi(g.pnl, g.staked))}`}>
                  {formatRoiSigned(computeRoi(g.pnl, g.staked))}
                </span>
                <span className={positive ? "text-emerald-400" : "text-red-400"}>
                  {formatBRL(g.pnl)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Reconciliation table
// ---------------------------------------------------------------------------

function ReconciliationTable({ items }: { items: ReconciliationItem[] }) {
  if (!items.length) {
    return (
      <div className="rounded-2xl border border-white/10 bg-white/5 p-6 text-center text-sm text-slate-400">
        Nenhuma aposta reconciliada ainda. Clique em "Reconciliar" acima após o upload.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 overflow-hidden">
      <div className="px-5 py-3 border-b border-white/10">
        <h3 className="text-sm font-semibold text-slate-200">Aposta × Modelo</h3>
        <div className="text-xs text-slate-500">
          Match heurístico por timestamp. Confidence ≥ 0.5 considerado válido.
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="bg-white/5">
            <tr className="text-left text-slate-400">
              <th className="px-4 py-2">Data</th>
              <th className="px-4 py-2">Jogo</th>
              <th className="px-4 py-2">Min</th>
              <th className="px-4 py-2 text-right">Stake</th>
              <th className="px-4 py-2 text-right">Resultado</th>
              <th className="px-4 py-2 text-right">Modelo</th>
              <th className="px-4 py-2 text-right">Conf.</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it, idx) => {
              const placedDate = it.placed_at ? new Date(it.placed_at) : null;
              const matched = it.event_id !== null;
              const confColor =
                it.match_confidence >= 0.7
                  ? "text-emerald-400"
                  : it.match_confidence >= 0.5
                    ? "text-amber-300"
                    : "text-slate-500";
              return (
                <tr
                  key={`${it.placed_at}-${idx}`}
                  className="border-t border-white/5 hover:bg-white/5"
                >
                  <td className="px-4 py-2 font-mono text-slate-300">
                    {placedDate
                      ? placedDate.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })
                      : "—"}
                  </td>
                  <td className="px-4 py-2">
                    {matched ? (
                      <span>
                        <span className="text-slate-200">
                          {it.home_team} × {it.away_team}
                        </span>
                        {it.home_score !== null && it.away_score !== null && (
                          <span className="ml-2 text-slate-500">
                            ({it.home_score}-{it.away_score})
                          </span>
                        )}
                      </span>
                    ) : (
                      <span className="text-slate-600">sem match</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-slate-400">
                    {it.match_minute !== null ? `${it.match_minute}'` : "—"}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-slate-200">
                    {formatBRL(it.stake)}
                  </td>
                  <td
                    className={`px-4 py-2 text-right font-mono ${
                      it.won ? "text-emerald-400" : "text-red-400"
                    }`}
                  >
                    {it.won ? "✓ +" : "✗ "}
                    {formatBRL(it.pnl)}
                  </td>
                  <td className="px-4 py-2 text-right text-slate-400">
                    {it.model_generosity_home !== null
                      ? `gen ${(it.model_generosity_home * 100).toFixed(0)}%`
                      : "—"}
                  </td>
                  <td className={`px-4 py-2 text-right ${confColor}`}>
                    {it.match_confidence > 0 ? it.match_confidence.toFixed(2) : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Model error heatmap
// ---------------------------------------------------------------------------

function ModelErrorHeatmap({
  buckets,
}: {
  buckets: { min_bucket?: string; diff_bucket?: string; n_bets: number; avg_brier: number; hit_rate: number; total_pnl: number }[];
}) {
  const minLabels = useMemo(() => Array.from(new Set(buckets.map((b) => b.min_bucket).filter(Boolean))) as string[], [buckets]);
  const diffLabels = useMemo(() => Array.from(new Set(buckets.map((b) => b.diff_bucket).filter(Boolean))) as string[], [buckets]);

  if (!buckets.length || !minLabels.length || !diffLabels.length) {
    return (
      <div className="rounded-2xl border border-white/10 bg-white/5 p-6 text-center text-sm text-slate-400">
        Heatmap exigirá mais bilhetes reconciliados para ser significativo.
      </div>
    );
  }

  const map = new Map<string, typeof buckets[0]>();
  for (const b of buckets) {
    map.set(`${b.min_bucket}|${b.diff_bucket}`, b);
  }

  const colorFor = (brier: number) => {
    // 0 = perfeito (verde), 1 = pior caso (vermelho)
    const intensity = Math.min(brier, 1);
    const r = Math.round(255 * intensity);
    const g = Math.round(180 * (1 - intensity));
    return `rgb(${r}, ${g}, 100)`;
  };

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
      <h3 className="mb-3 text-sm font-semibold text-slate-200">Onde o modelo erra</h3>
      <div className="text-xs text-slate-500 mb-3">
        Eixo Y: minuto · Eixo X: |goal_diff| · Cor: Brier (verde = acurado, vermelho = errado)
      </div>
      <table className="text-xs">
        <thead>
          <tr>
            <th className="px-2 py-1 text-slate-500">min \ diff</th>
            {diffLabels.map((d) => (
              <th key={d} className="px-2 py-1 text-slate-400">{d}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {minLabels.map((m) => (
            <tr key={m}>
              <td className="px-2 py-1 text-slate-400">{m}</td>
              {diffLabels.map((d) => {
                const cell = map.get(`${m}|${d}`);
                if (!cell) {
                  return <td key={d} className="px-2 py-1 text-slate-700">—</td>;
                }
                return (
                  <td
                    key={d}
                    className="px-2 py-1 text-center"
                    title={`n=${cell.n_bets}, brier=${cell.avg_brier.toFixed(3)}, hit=${(cell.hit_rate * 100).toFixed(0)}%, pnl=${formatBRL(cell.total_pnl)}`}
                  >
                    <div
                      className="rounded px-2 py-1 font-mono text-[11px]"
                      style={{ backgroundColor: colorFor(cell.avg_brier), color: "#0a0a0a" }}
                    >
                      {cell.avg_brier.toFixed(2)}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">n={cell.n_bets}</div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function CarteiraPage() {
  const [userId, setUserId] = useState(DEFAULT_USER);
  const queryClient = useQueryClient();

  const summaryQ = useQuery({
    queryKey: ["wallet-summary", userId],
    queryFn: () => walletRepository.getSummary(userId),
  });

  const reconciliationQ = useQuery({
    queryKey: ["wallet-reconciliation", userId],
    queryFn: () => walletRepository.getReconciliation(userId, 500, 0),
  });

  const errorsQ = useQuery({
    queryKey: ["wallet-errors", userId],
    queryFn: () => walletRepository.getModelErrors(userId),
  });

  const syncQ = useQuery({
    queryKey: ["wallet-sync-status", userId],
    queryFn: () => walletRepository.getSyncStatus(userId),
    refetchOnWindowFocus: true,
  });

  const reconcileMut = useMutation({
    mutationFn: () => walletRepository.reconcile(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["wallet-reconciliation", userId] });
      queryClient.invalidateQueries({ queryKey: ["wallet-errors", userId] });
    },
  });

  const onUploaded = () => {
    queryClient.invalidateQueries({ queryKey: ["wallet-summary", userId] });
    queryClient.invalidateQueries({ queryKey: ["wallet-sync-status", userId] });
    reconcileMut.mutate();
  };

  const onInboxSynced = () => {
    queryClient.invalidateQueries({ queryKey: ["wallet-sync-status", userId] });
    queryClient.invalidateQueries({ queryKey: ["wallet-summary", userId] });
    queryClient.invalidateQueries({ queryKey: ["wallet-reconciliation", userId] });
    queryClient.invalidateQueries({ queryKey: ["wallet-errors", userId] });
  };

  return (
    <PageTransition>
      <PageHeader
        title="Carteira & Performance"
        subtitle="Suba seu CSV da Superbet e veja onde o modelo erra mais"
      />
      <div className="mx-auto max-w-6xl space-y-3 p-4">
        <div className="flex items-center gap-3">
          <label className="text-xs text-slate-400">Usuário:</label>
          <input
            type="text"
            value={userId}
            onChange={(e) => setUserId(e.target.value.trim() || DEFAULT_USER)}
            className="rounded-lg border border-white/10 bg-white/5 px-3 py-1 text-sm font-mono text-slate-200"
          />
          <button
            onClick={() => reconcileMut.mutate()}
            disabled={reconcileMut.isPending}
            className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-300 hover:bg-emerald-500/20 disabled:opacity-50"
          >
            {reconcileMut.isPending ? "Reconciliando..." : "Reconciliar com snapshots"}
          </button>
        </div>

        {syncQ.data && (
          <WalletSyncBanner status={syncQ.data} onImportSuccess={onInboxSynced} />
        )}

        <CsvDropzone userId={userId} onUploaded={onUploaded} />

        {summaryQ.isLoading && (
          <div className="text-center text-sm text-slate-400 py-8">Carregando carteira...</div>
        )}

        {summaryQ.data && summaryQ.data.n_transactions > 0 && (
          <>
            <WalletKpiCards summary={summaryQ.data} />

            <RoiBreakdownSection
              summary={summaryQ.data}
              reconciliationItems={reconciliationQ.data?.items ?? []}
            />

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="lg:col-span-2">
                <BalanceChart summary={summaryQ.data} />
              </div>
              <BetTypeBreakdown summary={summaryQ.data} />
            </div>

            <DailyPnlBars summary={summaryQ.data} />

            <ReconciliationTable items={reconciliationQ.data?.items ?? []} />

            {errorsQ.data && <ModelErrorHeatmap buckets={errorsQ.data.buckets} />}
          </>
        )}

        {summaryQ.data?.n_transactions === 0 && !summaryQ.isLoading && (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-8 text-center text-slate-400">
            Nenhuma transação encontrada para <span className="font-mono">{userId}</span>.
            Suba um CSV acima para começar.
          </div>
        )}
      </div>
    </PageTransition>
  );
}
