import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { apiFetch } from "@/infrastructure/api/client";
import { formatPercent } from "@/presentation/theme";

interface BetAdvicePanelProps {
  homeTeam: string;
  awayTeam: string;
  superbetEventId?: number;
  phase?: string;
}

const ACTION_LABELS: Record<string, string> = {
  cashout: "Cash-out agora",
  cashout_parcial: "Cash-out parcial",
  manter: "Manter aposta",
  aguardar: "Aguardar",
  aportar: "Aportar",
  aportar_pequeno: "Aporte pequeno",
};

const ACTION_COLORS: Record<string, string> = {
  cashout: "text-red-400 border-red-500/30 bg-red-500/10",
  cashout_parcial: "text-amber-400 border-amber-500/30 bg-amber-500/10",
  manter: "text-neon-green border-neon-green/30 bg-neon-green/10",
  aguardar: "text-slate-300 border-white/10 bg-white/5",
  aportar: "text-neon-green border-neon-green/30 bg-neon-green/10",
  aportar_pequeno: "text-neon-blue border-neon-blue/30 bg-neon-blue/10",
};

type BetAdviceResponse = {
  homeTeam: string;
  awayTeam: string;
  minute: number;
  currentScore: string | null;
  cashout: {
    action: string;
    confidence: number;
    reason: string;
    currentModelProb: number;
    remainingEv: number;
    estimatedFairCashout: number;
    potentialReturn: number;
  } | null;
  aportes: Array<{
    label: string;
    market: string;
    outcome: string;
    modelProb: number;
    marketOdd: number;
    expectedValue: number;
    edgePp: number;
    suggestedStakePct: number;
    suggestedStakeValue: number;
    action: string;
  }>;
};

function mapAdvice(raw: Record<string, unknown>): BetAdviceResponse {
  const cash = raw.cashout as Record<string, unknown> | null;
  return {
    homeTeam: String(raw.home_team),
    awayTeam: String(raw.away_team),
    minute: Number(raw.minute),
    currentScore: raw.current_score != null ? String(raw.current_score) : null,
    cashout: cash
      ? {
          action: String(cash.action),
          confidence: Number(cash.confidence),
          reason: String(cash.reason),
          currentModelProb: Number(cash.current_model_prob),
          remainingEv: Number(cash.remaining_ev),
          estimatedFairCashout: Number(cash.estimated_fair_cashout),
          potentialReturn: Number(cash.potential_return),
        }
      : null,
    aportes: ((raw.aportes as Array<Record<string, unknown>>) ?? []).map((a) => ({
      label: String(a.label),
      market: String(a.market),
      outcome: String(a.outcome),
      modelProb: Number(a.model_prob),
      marketOdd: Number(a.market_odd),
      expectedValue: Number(a.expected_value),
      edgePp: Number(a.edge_pp),
      suggestedStakePct: Number(a.suggested_stake_pct),
      suggestedStakeValue: Number(a.suggested_stake_value),
      action: String(a.action),
    })),
  };
}

export function BetAdvicePanel({
  homeTeam,
  awayTeam,
  superbetEventId,
  phase = "friendly",
}: BetAdvicePanelProps) {
  const [market, setMarket] = useState("h2h");
  const [outcome, setOutcome] = useState("1");
  const [stake, setStake] = useState(100);
  const [oddsPlaced, setOddsPlaced] = useState(2.0);
  const [bankroll, setBankroll] = useState(1000);
  const [enabled, setEnabled] = useState(false);

  const query = useQuery({
    queryKey: [
      "bet-advice",
      homeTeam,
      awayTeam,
      superbetEventId,
      market,
      outcome,
      stake,
      oddsPlaced,
      bankroll,
    ],
    queryFn: async () => {
      const raw = await apiFetch<Record<string, unknown>>("/worldcup/bet/advice", {
        method: "POST",
        body: JSON.stringify({
          home_team: homeTeam,
          away_team: awayTeam,
          superbet_event_id: superbetEventId,
          phase,
          bankroll,
          user_bet: {
            market,
            outcome,
            stake,
            odds_placed: oddsPlaced,
          },
        }),
      });
      return mapAdvice(raw);
    },
    enabled: enabled && !!superbetEventId,
    refetchInterval: enabled ? 60_000 : false,
    staleTime: 30_000,
  });

  const data = query.data;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card rounded-xl p-5"
    >
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-slate-200">Cash-out e aportes</h3>
        <p className="text-xs text-slate-500">
          Captura ao vivo via Superbet · atualiza a cada 60s após analisar
        </p>
      </div>

      {!superbetEventId && (
        <p className="text-xs text-amber-400">
          Informe o ID Superbet na URL (?superbet=13247229) para ativar recomendações.
        </p>
      )}

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          Mercado
          <select
            value={market}
            onChange={(e) => setMarket(e.target.value)}
            className="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-white"
          >
            <option value="h2h">Resultado (1X2)</option>
            <option value="over_2_5">Over 2.5</option>
            <option value="btts">Ambos marcam</option>
            <option value="next_goal">Próximo gol</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          Palpite
          <select
            value={outcome}
            onChange={(e) => setOutcome(e.target.value)}
            className="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-white"
          >
            <option value="1">Casa (1)</option>
            <option value="X">Empate (X)</option>
            <option value="2">Fora (2)</option>
            <option value="yes">Sim / Over</option>
            <option value="home">Casa (gol)</option>
            <option value="away">Fora (gol)</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          Valor apostado (R$)
          <input
            type="number"
            min={1}
            value={stake}
            onChange={(e) => setStake(Number(e.target.value))}
            className="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 font-mono text-sm text-white"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          Odd na entrada
          <input
            type="number"
            min={1.01}
            step={0.01}
            value={oddsPlaced}
            onChange={(e) => setOddsPlaced(Number(e.target.value))}
            className="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 font-mono text-sm text-white"
          />
        </label>
      </div>

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          Banca (R$)
          <input
            type="number"
            min={100}
            value={bankroll}
            onChange={(e) => setBankroll(Number(e.target.value))}
            className="w-28 rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 font-mono text-sm text-white"
          />
        </label>
        <button
          type="button"
          disabled={!superbetEventId || query.isFetching}
          onClick={() => setEnabled(true)}
          className="rounded-lg bg-neon-purple/15 px-4 py-2 text-sm font-medium text-neon-purple hover:bg-neon-purple/25 disabled:opacity-50"
        >
          {query.isFetching ? "Analisando…" : "Analisar ao vivo"}
        </button>
      </div>

      {query.isError && (
        <p className="text-xs text-amber-400">Não foi possível gerar recomendações.</p>
      )}

      {data && (
        <div className="space-y-4">
          {data.currentScore && (
            <p className="text-xs text-slate-500">
              {data.homeTeam} x {data.awayTeam} · {data.currentScore} @ {data.minute}&apos;
            </p>
          )}

          {data.cashout && (
            <div
              className={`rounded-xl border px-4 py-3 ${ACTION_COLORS[data.cashout.action] ?? ACTION_COLORS.aguardar}`}
            >
              <p className="text-sm font-semibold">
                {ACTION_LABELS[data.cashout.action] ?? data.cashout.action}
                <span className="ml-2 font-mono text-xs opacity-80">
                  conf. {formatPercent(data.cashout.confidence)}
                </span>
              </p>
              <p className="mt-1 text-xs opacity-90">{data.cashout.reason}</p>
              <div className="mt-2 flex flex-wrap gap-3 font-mono text-[11px]">
                <span>Prob. modelo: {formatPercent(data.cashout.currentModelProb)}</span>
                <span>EV residual: {(data.cashout.remainingEv * 100).toFixed(1)}%</span>
                <span>Cash-out justo ~R$ {data.cashout.estimatedFairCashout.toFixed(2)}</span>
              </div>
            </div>
          )}

          {data.aportes.length > 0 && (
            <div>
              <p className="mb-2 text-[11px] uppercase tracking-wider text-slate-500">
                Onde aportar (edge vs Superbet)
              </p>
              <div className="space-y-2">
                {data.aportes.map((a) => (
                  <div
                    key={`${a.market}-${a.outcome}`}
                    className={`rounded-lg border px-3 py-2 ${ACTION_COLORS[a.action] ?? ""}`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-sm font-medium">{a.label}</span>
                      <span className="font-mono text-xs">
                        odd {a.marketOdd.toFixed(2)} · edge {a.edgePp.toFixed(1)} pp
                      </span>
                    </div>
                    <p className="mt-1 text-xs opacity-80">
                      {ACTION_LABELS[a.action]} · ~R$ {a.suggestedStakeValue.toFixed(2)} (
                      {a.suggestedStakePct.toFixed(1)}% da banca) · EV{" "}
                      {(a.expectedValue * 100).toFixed(1)}%
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {data.aportes.length === 0 && (
            <p className="text-xs text-slate-500">
              Nenhum aporte com edge suficiente neste momento (mercado fechado ou sem odds).
            </p>
          )}
        </div>
      )}
    </motion.div>
  );
}
