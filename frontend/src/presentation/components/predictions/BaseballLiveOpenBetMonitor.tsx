import type { BaseballSuperbetLiveAdvice } from "@/domain/entities";
import { formatPercent } from "@/presentation/theme";
import { CashoutAlertProgress } from "@/presentation/components/predictions/CashoutAlertProgress";
import { CashoutRiskBanner } from "@/presentation/components/predictions/CashoutRiskBanner";
import type { RegisteredBetEntry } from "@/presentation/components/predictions/LiveOpenBetMonitor";
import { getCashoutAlertConfig } from "@/presentation/utils/cashoutAlertStorage";
import {
  assessCashoutRisk,
  buildCashoutLiveContext,
} from "@/presentation/utils/cashoutRiskAssessment";

const ACTION_LABELS: Record<string, string> = {
  cashout: "Cash-out agora",
  cashout_parcial: "Cash-out parcial (50–70%)",
  manter: "Manter aposta",
  aguardar: "Aguardar — reavaliar",
};

const ACTION_COLORS: Record<string, string> = {
  cashout: "border-red-500/40 bg-red-500/15 text-red-300",
  cashout_parcial: "border-amber-500/40 bg-amber-500/15 text-amber-300",
  manter: "border-emerald-500/40 bg-emerald-500/15 text-emerald-300",
  aguardar: "border-white/15 bg-white/5 text-slate-300",
};

const MARKET_LABELS: Record<string, string> = {
  moneyline: "Vencedor (ML)",
  h2h: "Vencedor (ML)",
  spread: "Run line",
  total_runs: "Total de corridas",
  team_total_runs: "Total por time",
  f5_total: "Total F5",
  f5_moneyline: "1X2 F5",
  f5_spread: "Handicap F5",
};

function pickLabel(data: BaseballSuperbetLiveAdvice, bet: RegisteredBetEntry): string {
  const { market, outcome } = bet;
  const m = market === "h2h" ? "moneyline" : market;
  if (m === "moneyline") {
    if (outcome === "1") return data.homeTeam;
    if (outcome === "2") return data.awayTeam;
  }
  if (m === "total_runs") {
    if (outcome.startsWith("over_")) return `Mais de ${outcome.replace("over_", "").replace("_", ".")}`;
    if (outcome.startsWith("under_")) return `Menos de ${outcome.replace("under_", "").replace("_", ".")}`;
  }
  return bet.picks?.[0]?.label ?? outcome;
}

function modelProbForBet(data: BaseballSuperbetLiveAdvice, bet: RegisteredBetEntry): number | null {
  const s = data.inplaySummary;
  const market = bet.market === "h2h" ? "moneyline" : bet.market;
  const outcome = bet.outcome;

  if (market === "moneyline") {
    if (outcome === "1") return s.probHomeWin;
    if (outcome === "2") return s.probAwayWin;
    return s.moneylineProbs[outcome] ?? null;
  }
  if (market === "spread") return s.spreadProbs[outcome] ?? null;
  if (market === "total_runs") return s.totalProbs[outcome] ?? null;
  if (market === "team_total_runs") return s.teamTotalProbs?.[outcome] ?? null;
  return s.periodProbs?.[outcome] ?? null;
}

interface BaseballLiveOpenBetMonitorProps {
  data: BaseballSuperbetLiveAdvice;
  bet: RegisteredBetEntry;
  cashout: BaseballSuperbetLiveAdvice["cashout"];
  betIndex: number;
  totalBets: number;
  isFetching: boolean;
  pollSeconds: number;
  onAutoMonitorChange: (on: boolean) => void;
}

export function BaseballLiveOpenBetMonitor({
  data,
  bet,
  cashout,
  betIndex,
  totalBets,
  isFetching,
  pollSeconds,
  onAutoMonitorChange,
}: BaseballLiveOpenBetMonitorProps) {
  const autoMonitor = bet.autoMonitor;
  const alertConfig = getCashoutAlertConfig(bet.id);
  const currentCashout = bet.offeredCashout ?? bet.cashoutValue ?? null;
  const marketKey = bet.market === "h2h" ? "moneyline" : bet.market;
  const marketLabel = MARKET_LABELS[marketKey] ?? marketKey;
  const pick = pickLabel(data, bet);
  const displayReturn = bet.potentialReturn ?? bet.stake * bet.oddsPlaced;
  const modelP = modelProbForBet(data, bet);
  const placedImplied = 1 / Math.max(bet.oddsPlaced, 1.01);

  const riskAssessment = assessCashoutRisk(
    {
      id: bet.id,
      stake: bet.stake,
      oddsPlaced: bet.oddsPlaced,
      potentialReturn: displayReturn,
      cashoutValue: currentCashout,
      picks:
        bet.picks?.map((p) => ({
          market: p.market,
          outcome: p.outcome,
          label: p.label,
        })) ?? [{ market: bet.market, outcome: bet.outcome }],
    },
    buildCashoutLiveContext({
      currentScore: data.currentScore,
      minute: (data.inning ?? data.minute ?? 1) * 10,
      periodLabel: data.periodLabel,
    }),
  );

  const mlFav =
    data.h2hOdds["1"] != null && data.h2hOdds["2"] != null
      ? data.h2hOdds["1"] < data.h2hOdds["2"]
        ? { label: data.homeTeam, odd: data.h2hOdds["1"] }
        : { label: data.awayTeam, odd: data.h2hOdds["2"] }
      : null;

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/[0.06] p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
              Aposta {betIndex} de {totalBets}
              {bet.ticketCode ? (
                <span className="ml-2 rounded bg-white/10 px-1.5 py-0.5 font-mono text-[9px] text-slate-400">
                  #{bet.ticketCode}
                </span>
              ) : null}
            </p>
            <p className="mt-1 text-base font-semibold text-white">
              {marketLabel} → {pick}
            </p>
            <p className="mt-1 font-mono text-sm text-slate-300">
              R$ {bet.stake.toFixed(2)} · odd {bet.oddsPlaced.toFixed(2)} · ganho potencial R${" "}
              {displayReturn.toFixed(2)}
            </p>
            <p className="mt-1 text-[11px] text-slate-500">
              Entrada {data.inning} · {data.periodLabel ?? `${data.inning}I`}
            </p>
          </div>
          {autoMonitor && data.isLive ? (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-emerald-300">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
              Monitorando · {pollSeconds}s
            </span>
          ) : null}
        </div>
        {isFetching && autoMonitor ? (
          <p className="mt-2 text-[11px] text-slate-500">Atualizando cash-out…</p>
        ) : null}
        <label className="mt-3 flex items-center gap-2 text-xs text-slate-400">
          <input
            type="checkbox"
            checked={autoMonitor}
            onChange={(e) => onAutoMonitorChange(e.target.checked)}
            className="rounded border-white/20"
          />
          Monitorar automaticamente (reanalisa cash-out a cada {pollSeconds}s)
        </label>
      </div>

      <CashoutAlertProgress config={alertConfig} currentCashout={currentCashout} />

      {riskAssessment.alert ? (
        <CashoutRiskBanner assessment={riskAssessment} />
      ) : null}

      {mlFav ? (
        <div className="rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-slate-400">
          Favorito ML: {mlFav.label} @ {mlFav.odd.toFixed(2)}
        </div>
      ) : null}

      {cashout ? (
        <div
          className={`rounded-xl border p-4 ${
            ACTION_COLORS[cashout.action] ?? ACTION_COLORS.aguardar
          }`}
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold">
              {ACTION_LABELS[cashout.action] ?? cashout.action}
            </p>
            <span className="text-[11px] opacity-80">
              conf. {(cashout.confidence * 100).toFixed(0)}%
              {cashout.trendInfluenced ? (
                <span className="ml-2 rounded bg-violet-500/20 px-1.5 py-0.5 text-[9px] uppercase text-violet-200">
                  tendência{cashout.trendUrgency ? ` · ${cashout.trendUrgency}` : ""}
                </span>
              ) : null}
            </span>
          </div>
          <p className="mt-2 text-xs leading-relaxed opacity-90">{cashout.reason}</p>
          <div className="mt-3 grid gap-2 text-[11px] sm:grid-cols-2">
            <div>
              Modelo agora: {formatPercent(cashout.currentModelProb)} · entrada{" "}
              {formatPercent(placedImplied)}
            </div>
            <div>EV residual: {(cashout.remainingEv * 100).toFixed(1)}%</div>
            <div>Fair ~ R$ {cashout.estimatedFairCashout.toFixed(2)}</div>
            <div>Retorno pot. R$ {cashout.potentialReturn.toFixed(2)}</div>
          </div>
        </div>
      ) : modelP != null ? (
        <div className="rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-slate-400">
          P(modelo) atual: {formatPercent(modelP)} — ative o monitor para recomendação de cash-out.
        </div>
      ) : null}
    </div>
  );
}

export function normalizeBaseballAdviceMarket(market: string): string {
  return market === "h2h" ? "moneyline" : market;
}
