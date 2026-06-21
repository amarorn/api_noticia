import type { SuperbetLiveAdvice } from "@/domain/entities";
import { formatPercent } from "@/presentation/theme";
import { CashoutAlertProgress } from "@/presentation/components/predictions/CashoutAlertProgress";
import { getCashoutAlertConfig } from "@/presentation/utils/cashoutAlertStorage";

export interface RegisteredBet {
  market: string;
  outcome: string;
  stake: number;
  oddsPlaced: number;
  potentialReturn?: number;
  ticketCode?: string | null;
  offeredCashout?: number | null;
  picks?: Array<{ market: string; outcome: string; label?: string }>;
  bonusEligible?: boolean;
  bonusPercentage?: number;
  finalPayout?: number;
}

export interface RegisteredBetEntry extends RegisteredBet {
  id: string;
  autoMonitor: boolean;
  cashoutValue?: number | null;
}

export function createRegisteredBetId(): string {
  return `bet-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

const ACTION_LABELS: Record<string, string> = {
  cashout: "Cash-out agora",
  cashout_parcial: "Cash-out parcial (50–70%)",
  manter: "Manter aposta",
  aguardar: "Aguardar — reavaliar",
};

const ACTION_COLORS: Record<string, string> = {
  cashout: "border-red-500/40 bg-red-500/15 text-red-300",
  cashout_parcial: "border-amber-500/40 bg-amber-500/15 text-amber-300",
  manter: "border-neon-green/40 bg-neon-green/15 text-neon-green",
  aguardar: "border-white/15 bg-white/5 text-slate-300",
};

const MARKET_LABELS: Record<string, string> = {
  h2h: "1X2 (Resultado Final)",
  over_2_5: "Over 2.5 gols",
  btts: "Ambos marcam (BTTS)",
  next_goal: "Próximo gol",
};

function pickLabel(data: SuperbetLiveAdvice, bet: RegisteredBet): string {
  const { market, outcome } = bet;
  if (market === "h2h") {
    if (outcome === "1") return data.homeTeam;
    if (outcome === "2") return data.awayTeam;
    if (outcome === "X") return "Empate";
  }
  if (market === "btts") return outcome === "yes" ? "Sim (ambos marcam)" : "Não";
  if (market === "over_2_5") return outcome === "yes" ? "Over 2.5" : "Under 2.5";
  if (market === "next_goal") {
    if (outcome === "home") return `Gol ${data.homeTeam}`;
    if (outcome === "away") return `Gol ${data.awayTeam}`;
  }
  return outcome;
}

function modelProbForBet(data: SuperbetLiveAdvice, bet: RegisteredBet): number | null {
  const s = data.inplaySummary;
  const key = `${bet.market}:${bet.outcome}`.toLowerCase();
  const map: Record<string, number | undefined> = {
    "h2h:1": s.probFinalHome,
    "h2h:x": s.probFinalDraw,
    "h2h:2": s.probFinalAway,
    "btts:yes": s.btts,
    "over_2_5:yes": s.over25,
    "next_goal:home": s.probNextGoalHome,
    "next_goal:away": s.probNextGoalAway,
  };
  const p = map[key];
  return p != null ? p : null;
}

function liveOddForBet(data: SuperbetLiveAdvice, bet: RegisteredBet): number | null {
  const { market, outcome } = bet;
  if (market === "h2h") {
    const k = outcome === "X" ? "X" : outcome;
    return data.h2hOdds[k] ?? null;
  }
  if (market === "btts") {
    return outcome === "yes" ? data.bttsOdds.yes ?? null : data.bttsOdds.no ?? null;
  }
  if (market === "next_goal") {
    return data.nextGoalOdds[outcome] ?? null;
  }
  if (market === "over_2_5") {
    const row = data.aportes.find((a) => a.market === "over_2_5");
    return row?.marketOdd ?? null;
  }
  return null;
}

function houseFavorite(data: SuperbetLiveAdvice): { label: string; odd: number } | null {
  const entries = (["1", "X", "2"] as const)
    .map((k) => ({ k, odd: data.h2hOdds[k] }))
    .filter((e) => e.odd != null && e.odd > 1) as Array<{ k: "1" | "X" | "2"; odd: number }>;
  if (entries.length === 0) return null;
  const fav = entries.reduce((a, b) => (a.odd < b.odd ? a : b));
  const label =
    fav.k === "1" ? data.homeTeam : fav.k === "2" ? data.awayTeam : "Empate";
  return { label, odd: fav.odd };
}

interface LiveOpenBetMonitorProps {
  data: SuperbetLiveAdvice;
  bet: RegisteredBetEntry;
  cashout: SuperbetLiveAdvice["cashout"];
  betIndex: number;
  totalBets: number;
  isFetching: boolean;
  pollSeconds: number;
  onEdit: () => void;
  onRemove: () => void;
  onAutoMonitorChange: (on: boolean) => void;
}

export function LiveOpenBetMonitor({
  data,
  bet,
  cashout,
  betIndex,
  totalBets,
  isFetching,
  pollSeconds,
  onEdit,
  onRemove,
  onAutoMonitorChange,
}: LiveOpenBetMonitorProps) {
  const autoMonitor = bet.autoMonitor;
  const alertConfig = getCashoutAlertConfig(bet.id);
  const currentCashout = bet.offeredCashout ?? bet.cashoutValue ?? null;
  const isMulti = (bet.picks?.length ?? 0) > 1;
  const pick = isMulti ? null : pickLabel(data, bet);
  const marketLabel = isMulti
    ? `Múltipla · ${bet.picks!.length} pernas`
    : (MARKET_LABELS[bet.market] ?? bet.market);
  const displayReturn =
    bet.bonusEligible && bet.finalPayout != null
      ? bet.finalPayout
      : (bet.potentialReturn ?? bet.stake * bet.oddsPlaced);
  const modelP = isMulti ? null : modelProbForBet(data, bet);
  const liveOdd = isMulti ? null : liveOddForBet(data, bet);
  const placedImplied = 1 / Math.max(bet.oddsPlaced, 1.01);
  const house = houseFavorite(data);

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-neon-blue/30 bg-neon-blue/[0.06] p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
              Aposta {betIndex} de {totalBets}
              {bet.ticketCode && (
                <span className="ml-2 rounded bg-white/10 px-1.5 py-0.5 font-mono text-[9px] text-slate-400">
                  #{bet.ticketCode}
                </span>
              )}
            </p>
            <p className="mt-1 text-base font-semibold text-white">
              {isMulti ? marketLabel : `${marketLabel} → ${pick}`}
            </p>
            {isMulti && bet.picks && (
              <ul className="mt-2 space-y-1 text-xs text-slate-400">
                {bet.picks.map((p) => (
                  <li key={`${p.market}-${p.outcome}`}>
                    · {p.label ?? `${p.market} ${p.outcome}`}
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-1 font-mono text-sm text-slate-300">
              Aposta R$ {bet.stake.toFixed(2)} · odd {bet.oddsPlaced.toFixed(2)} · ganho potencial R${" "}
              {displayReturn.toFixed(2)}
              {bet.bonusEligible ? (
                <span className="ml-2 rounded-full border border-amber-400/35 bg-amber-500/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-amber-200">
                  Super Múltipla +{((bet.bonusPercentage ?? 0.05) * 100).toFixed(0)}%
                </span>
              ) : null}
            </p>
            {bet.bonusEligible && bet.potentialReturn != null && bet.finalPayout != null ? (
              <p className="mt-0.5 text-[10px] text-slate-500">
                Bruto R$ {bet.potentialReturn.toFixed(2)} + bônus → R$ {bet.finalPayout.toFixed(2)}
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {autoMonitor && data.isLive && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-neon-green/30 bg-neon-green/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-neon-green">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-neon-green" />
                Monitorando · {pollSeconds}s
              </span>
            )}
            <button
              type="button"
              onClick={onEdit}
              className="rounded-lg border border-white/15 px-2.5 py-1 text-xs text-slate-400 hover:text-white"
            >
              Editar
            </button>
            <button
              type="button"
              onClick={onRemove}
              className="rounded-lg border border-white/15 px-2.5 py-1 text-xs text-slate-400 hover:text-red-300"
            >
              Remover
            </button>
          </div>
        </div>
        {isFetching && autoMonitor && (
          <p className="mt-2 text-[11px] text-slate-500">Atualizando análise…</p>
        )}
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

      <div className="rounded-xl border border-violet-500/20 bg-violet-500/[0.05] p-4">
        <p className="text-[10px] font-bold uppercase tracking-widest text-violet-300/80">
          Onde a casa está concentrada
        </p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {house && (
            <HouseRow
              label="Favorito 1X2 (casa de apostas)"
              value={`${house.label} @ ${house.odd.toFixed(2)}`}
              hint="Menor odd = onde a Superbet concentra o volume"
            />
          )}
          <HouseRow
            label="Sua entrada"
            value={
              isMulti || pick == null
                ? `@ ${bet.oddsPlaced.toFixed(2)} (${formatPercent(placedImplied)} implícita)`
                : `${pick} @ ${bet.oddsPlaced.toFixed(2)} (${formatPercent(placedImplied)} implícita)`
            }
            hint="Odd que você pegou ao entrar"
          />
          {liveOdd != null && (
            <HouseRow
              label="Mercado ao vivo (seu palpite)"
              value={`@ ${liveOdd.toFixed(2)} (${formatPercent(1 / liveOdd)} agora)`}
              hint="Odd atual na Superbet para o mesmo palpite"
            />
          )}
          {modelP != null && (
            <HouseRow
              label="Modelo (seu palpite)"
              value={formatPercent(modelP)}
              hint={
                modelP < placedImplied
                  ? "Modelo abaixo da sua entrada — pressão para cash-out"
                  : "Modelo ainda acima da entrada — pode manter"
              }
              tone={modelP < placedImplied ? "warn" : "ok"}
            />
          )}
        </div>
      </div>

      {cashout && autoMonitor ? (
        <div
          className={`rounded-xl border p-4 ${ACTION_COLORS[cashout.action] ?? ACTION_COLORS.aguardar}`}
        >
          <p className="text-lg font-bold">{ACTION_LABELS[cashout.action] ?? cashout.action}</p>
          <p className="mt-2 text-sm opacity-90">{cashout.reason}</p>
          <div className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
            <span>P(modelo): {formatPercent(cashout.currentModelProb)}</span>
            <span>EV residual: {(cashout.remainingEv * 100).toFixed(1)}%</span>
            <span>Cash-out justo ≈ R$ {cashout.estimatedFairCashout.toFixed(2)}</span>
          </div>
          {bet.offeredCashout != null && bet.offeredCashout > 0 && (
            <p className="mt-2 text-xs font-medium">
              Superbet oferece R$ {bet.offeredCashout.toFixed(2)}
              {bet.offeredCashout >= cashout.estimatedFairCashout * 0.95
                ? " — perto ou acima do justo, saída faz sentido se o modelo pedir cash-out"
                : " — abaixo do justo, só saia se quiser travar lucro/pequena perda"}
            </p>
          )}
          <p className="mt-3 text-[11px] opacity-75">
            Compare o justo com o botão verde da Superbet. Cadastre o valor oferecido no formulário
            (Editar) para ver a comparação automática.
          </p>
        </div>
      ) : (
        <p className="text-sm text-slate-500">
          Ative o monitoramento automático para reavaliar saída a cada {pollSeconds}s.
        </p>
      )}
    </div>
  );
}

function HouseRow({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint: string;
  tone?: "ok" | "warn";
}) {
  return (
    <div className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2">
      <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
      <p
        className={`mt-0.5 text-sm font-medium ${
          tone === "warn" ? "text-amber-300" : tone === "ok" ? "text-neon-green" : "text-white"
        }`}
      >
        {value}
      </p>
      <p className="mt-0.5 text-[10px] text-slate-500">{hint}</p>
    </div>
  );
}
