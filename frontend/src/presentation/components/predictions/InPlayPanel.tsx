import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { predictWcInPlayUseCase, getHandicapAnalysisUseCase } from "@/application/container";
import type { WcInPlayPrediction } from "@/domain/entities";
import { ApiError } from "@/infrastructure/api/client";
import { formatPercent } from "@/presentation/theme";
import { LiveHandicapPanel } from "@/presentation/components/predictions/LiveHandicapPanel";

interface InPlayPanelProps {
  homeTeam: string;
  awayTeam: string;
  phase?: string;
  initialHomeScore?: number;
  initialAwayScore?: number;
  initialMinute?: number;
  superbetEventId?: number;
}

function MarketCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2">
      <p className="text-[11px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-0.5 font-mono text-sm font-semibold text-slate-200">{value}</p>
    </div>
  );
}

function lineLabel(key: string): string {
  return key.replace(/_/g, " ").replace("over", "Over").replace("under", "Under");
}

const COMBO_LABELS: Record<string, string> = {
  btts_and_over_2_5: "BTTS & Over 2.5",
  btts_and_over_3_5: "BTTS & Over 3.5",
  ft_home_and_btts: "Final Casa & BTTS",
  ft_draw_and_btts: "Final Empate & BTTS",
  ft_away_and_btts: "Final Fora & BTTS",
  ht_or_ft_home: "Intervalo ou Final — Casa",
  ht_or_ft_draw: "Intervalo ou Final — Empate",
  ht_or_ft_away: "Intervalo ou Final — Fora",
  home_wins_either_half: "Casa vence algum tempo",
  away_wins_either_half: "Fora vence algum tempo",
  ht_over_0_5_and_match_over_1_5: "Gols 1T Over 0.5 & partida Over 1.5",
  ht_over_0_5_and_match_over_2_5: "Gols 1T Over 0.5 & partida Over 2.5",
  ht_over_1_5_and_match_over_2_5: "Gols 1T Over 1.5 & partida Over 2.5",
  ht_over_1_5_and_match_over_3_5: "Gols 1T Over 1.5 & partida Over 3.5",
  ht_over_0_5_and_2h_over_0_5: "Gols 1T Over 0.5 & 2T Over 0.5",
  ht_over_1_5_and_2h_over_1_5: "Gols 1T Over 1.5 & 2T Over 1.5",
  ht_over_0_5_or_2h_over_0_5: "Gols 1T Over 0.5 ou 2T Over 0.5",
  ht_over_1_5_or_2h_over_1_5: "Gols 1T Over 1.5 ou 2T Over 1.5",
  ht_over_1_5_or_match_over_2_5: "Gols 1T Over 1.5 ou partida Over 2.5",
  ht_over_0_5_or_match_over_2_5: "Gols 1T Over 0.5 ou partida Over 2.5",
};

type InPlayRequest = {
  homeScore: number;
  awayScore: number;
  minute: number;
  superbetEventId?: number;
};

export function InPlayPanel({
  homeTeam,
  awayTeam,
  phase = "group",
  initialHomeScore = 0,
  initialAwayScore = 0,
  initialMinute = 0,
  superbetEventId,
}: InPlayPanelProps) {
  const [homeScore, setHomeScore] = useState(initialHomeScore);
  const [awayScore, setAwayScore] = useState(initialAwayScore);
  const [minute, setMinute] = useState(initialMinute);
  const [request, setRequest] = useState<InPlayRequest | null>(null);

  const query = useQuery({
    queryKey: [
      "wc-inplay",
      homeTeam,
      awayTeam,
      phase,
      request?.homeScore,
      request?.awayScore,
      request?.minute,
      request?.superbetEventId,
    ],
    queryFn: () =>
      predictWcInPlayUseCase.execute({
        homeTeam,
        awayTeam,
        homeScore: request!.homeScore,
        awayScore: request!.awayScore,
        minute: request!.minute,
        phase,
        superbetEventId: request!.superbetEventId,
      }),
    enabled: request != null,
    staleTime: 30_000,
  });

  const data: WcInPlayPrediction | undefined = query.data;

  const handicapQuery = useQuery({
    queryKey: ["wc-handicap", superbetEventId, phase, request?.minute],
    queryFn: () =>
      getHandicapAnalysisUseCase.execute({
        eventId: superbetEventId!,
        phase,
        bankroll: 1000,
      }),
    enabled:
      request != null &&
      superbetEventId != null &&
      Number.isFinite(superbetEventId) &&
      superbetEventId > 0,
    staleTime: 30_000,
  });

  const errorMessage =
    query.error instanceof ApiError
      ? query.error.message
      : query.error instanceof Error
        ? query.error.message
        : "Não foi possível calcular mercados ao vivo.";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card rounded-xl p-5"
    >
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-slate-200">Mercados ao vivo</h3>
        <p className="text-xs text-slate-500">
          Informe placar e minuto, depois clique em Calcular · Monte Carlo no tempo restante
        </p>
      </div>

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          {homeTeam}
          <input
            type="number"
            min={0}
            max={20}
            value={homeScore}
            onChange={(e) => setHomeScore(Number(e.target.value))}
            className="w-16 rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 font-mono text-sm text-white"
          />
        </label>
        <span className="pb-2 text-slate-500">x</span>
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          {awayTeam}
          <input
            type="number"
            min={0}
            max={20}
            value={awayScore}
            onChange={(e) => setAwayScore(Number(e.target.value))}
            className="w-16 rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 font-mono text-sm text-white"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          Minuto
          <input
            type="number"
            min={0}
            max={120}
            value={minute}
            onChange={(e) => setMinute(Number(e.target.value))}
            className="w-20 rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 font-mono text-sm text-white"
          />
        </label>
        <button
          type="button"
          onClick={() =>
            setRequest({
              homeScore: Number.isFinite(homeScore) ? homeScore : 0,
              awayScore: Number.isFinite(awayScore) ? awayScore : 0,
              minute: Number.isFinite(minute) ? minute : 0,
              superbetEventId,
            })
          }
          disabled={!homeTeam || !awayTeam || query.isFetching}
          className="rounded-lg bg-neon-green/15 px-4 py-2 text-sm font-medium text-neon-green transition hover:bg-neon-green/25 disabled:opacity-50"
        >
          {query.isFetching ? "Calculando…" : "Calcular"}
        </button>
      </div>

      {query.isError && (
        <p className="mb-3 rounded-lg border border-amber-500/20 bg-amber-500/8 px-3 py-2 text-xs text-amber-400">
          {errorMessage}
        </p>
      )}

      {data && (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span>
              Placar {data.currentScore} · {data.minute}&apos;
            </span>
            <span>
              λ restante {data.lambdaRemainingHome.toFixed(2)} x{" "}
              {data.lambdaRemainingAway.toFixed(2)}
            </span>
            <span className="rounded-full border border-neon-purple/30 bg-neon-purple/10 px-2 py-0.5 font-mono text-neon-purple">
              ρ = {data.rhoUsed.toFixed(3)}
            </span>
          </div>

          <p className="mb-2 text-[11px] uppercase tracking-wider text-slate-500">Resultado final</p>
          <div className="mb-4 grid grid-cols-3 gap-2">
            <MarketCell label="Casa" value={formatPercent(data.probFinalHome)} />
            <MarketCell label="Empate" value={formatPercent(data.probFinalDraw)} />
            <MarketCell label="Fora" value={formatPercent(data.probFinalAway)} />
          </div>

          <p className="mb-2 text-[11px] uppercase tracking-wider text-slate-500">Intervalo</p>
          <div className="mb-4 grid grid-cols-3 gap-2">
            <MarketCell label="Casa" value={formatPercent(data.probHtHome)} />
            <MarketCell label="Empate" value={formatPercent(data.probHtDraw)} />
            <MarketCell label="Fora" value={formatPercent(data.probHtAway)} />
          </div>

          <p className="mb-2 text-[11px] uppercase tracking-wider text-slate-500">Próximo gol</p>
          <div className="mb-4 grid grid-cols-3 gap-2">
            <MarketCell label={homeTeam} value={formatPercent(data.probNextGoalHome)} />
            <MarketCell label="Sem mais gols" value={formatPercent(data.probNoMoreGoals)} />
            <MarketCell label={awayTeam} value={formatPercent(data.probNextGoalAway)} />
          </div>

          <p className="mb-2 text-[11px] uppercase tracking-wider text-slate-500">Linhas finais</p>
          <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {Object.entries(data.finalLineProbs).map(([key, prob]) => (
              <MarketCell key={key} label={lineLabel(key)} value={formatPercent(prob)} />
            ))}
            <MarketCell label="Ambos marcam" value={formatPercent(data.bttsFinal)} />
          </div>

          {Object.keys(data.topHtFt).length > 0 && (
            <div className="mb-4">
              <p className="mb-2 text-[11px] uppercase tracking-wider text-slate-500">
                Intervalo / Resultado final
              </p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(data.topHtFt).map(([combo, prob]) => (
                  <span
                    key={combo}
                    className="rounded-lg border border-white/5 bg-white/[0.03] px-2.5 py-1 font-mono text-xs text-slate-300"
                  >
                    {combo}{" "}
                    <span className="text-neon-purple">{formatPercent(prob)}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {Object.keys(data.comboMarkets).length > 0 && (
            <div className="mb-4">
              <p className="mb-2 text-[11px] uppercase tracking-wider text-slate-500">
                Mercados combinados
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                {Object.entries(data.comboMarkets).map(([key, prob]) => (
                  <MarketCell
                    key={key}
                    label={COMBO_LABELS[key] ?? key}
                    value={formatPercent(prob)}
                  />
                ))}
              </div>
            </div>
          )}

          {Object.keys(data.topFinalScores).length > 0 && (
            <div>
              <p className="mb-2 text-[11px] uppercase tracking-wider text-slate-500">
                Placares finais mais prováveis
              </p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(data.topFinalScores).map(([score, prob]) => (
                  <span
                    key={score}
                    className="rounded-lg border border-white/5 bg-white/[0.03] px-2.5 py-1 font-mono text-xs text-slate-300"
                  >
                    {score}{" "}
                    <span className="text-neon-green">{formatPercent(prob)}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {data.marketBenchmark?.h2h && (
            <div className="mt-4">
              <p className="mb-2 text-[11px] uppercase tracking-wider text-slate-500">
                Modelo vs Superbet
              </p>
              <div className="grid gap-2 sm:grid-cols-3">
                {Object.entries(data.marketBenchmark.h2h).map(([key, row]) => (
                  <MarketCell
                    key={key}
                    label={`${key} edge`}
                    value={`${(row.edge * 100).toFixed(1)} pp`}
                  />
                ))}
              </div>
            </div>
          )}

          {superbetEventId != null && superbetEventId > 0 && (
            <section className="mt-6 border-t border-white/8 pt-4">
              <div className="mb-3 flex items-center gap-2">
                <span className="font-mono text-[10px] text-neon-blue">:: HANDICAP</span>
                <span className="h-px flex-1 bg-gradient-to-r from-neon-blue/20 to-transparent" />
              </div>
              <LiveHandicapPanel
                analysis={handicapQuery.data}
                homeTeam={homeTeam}
                awayTeam={awayTeam}
                isLoading={handicapQuery.isLoading || handicapQuery.isFetching}
              />
            </section>
          )}

          <p className="mt-3 text-[10px] text-slate-600">
            {data.nSimulations.toLocaleString("pt-BR")} simulações
          </p>
        </>
      )}
    </motion.div>
  );
}
