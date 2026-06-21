/**
 * Painel compacto de apostas abertas da Superbet (aba Meu Bilhete).
 * Busca de /user/open-bets e filtra pelo evento atual.
 */
import { useQuery } from "@tanstack/react-query";
import type { UserOpenBet } from "@/domain/entities";
import { getUserOpenBetsUseCase } from "@/application/container";

const MARKET_LABELS: Record<string, string> = {
  h2h: "1X2",
  "1h_h2h": "1X2 1T",
  "2h_h2h": "1X2 2T",
  over_2_5: "Over 2.5",
  over_1_5: "Over 1.5",
  over_3_5: "Over 3.5",
  btts: "Ambas marcam",
  next_goal: "Próximo gol",
  ft_hcap_home_p0_5: "Handicap Casa +0.5",
  ft_hcap_away_p0_5: "Handicap Fora +0.5",
};

const OUTCOME_LABELS: Record<string, string> = {
  "1": "Casa",
  "2": "Fora",
  X: "Empate",
  yes: "Sim",
  no: "Não",
  over: "Acima",
  under: "Abaixo",
  home: "Casa",
  away: "Fora",
};

function formatMarket(market: string) {
  return MARKET_LABELS[market] ?? market;
}
function formatOutcome(outcome: string) {
  return OUTCOME_LABELS[outcome] ?? outcome;
}

function StatusBadge({ status }: { status: string }) {
  if (status === "open")
    return (
      <span className="rounded-full bg-neon-green/15 px-2 py-0.5 text-[9px] font-bold text-neon-green">
        ABERTA
      </span>
    );
  if (status === "won")
    return (
      <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[9px] font-bold text-emerald-300">
        GANHA
      </span>
    );
  if (status === "lost")
    return (
      <span className="rounded-full bg-red-500/15 px-2 py-0.5 text-[9px] font-bold text-red-400">
        PERDIDA
      </span>
    );
  return (
    <span className="rounded-full bg-white/8 px-2 py-0.5 text-[9px] font-medium text-slate-400">
      {status}
    </span>
  );
}

interface Props {
  eventId: number;
  homeTeam?: string;
  awayTeam?: string;
}

export function LiveOpenBetsPanel({ eventId, homeTeam, awayTeam }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ["user-open-bets"],
    queryFn: () => getUserOpenBetsUseCase.execute(),
    refetchInterval: 30_000,
    staleTime: 20_000,
  });

  const bets: UserOpenBet[] = (data?.bets ?? []).filter(
    (b) =>
      b.superbetEventId === eventId ||
      (homeTeam && awayTeam && b.homeTeam === homeTeam && b.awayTeam === awayTeam),
  );

  if (isLoading) {
    return (
      <div className="rounded-xl border border-white/8 bg-white/[0.02] p-4 text-center text-[11px] text-slate-500">
        Buscando apostas…
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-white/8 bg-white/[0.02]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/6 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="text-base">🎟️</span>
          <span className="text-sm font-bold text-white">Minhas Apostas</span>
          {bets.length > 0 && (
            <span className="rounded-full bg-neon-green/15 px-2 py-0.5 text-[10px] font-bold text-neon-green">
              {bets.length}
            </span>
          )}
        </div>
        <span className="text-[10px] text-slate-600">neste jogo</span>
      </div>

      {bets.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-8 text-center">
          <span className="text-2xl opacity-30">🎟️</span>
          <p className="text-[12px] font-medium text-slate-500">Nenhuma aposta aberta</p>
          <p className="text-[10px] text-slate-600">
            Abra as Minhas Apostas na Superbet e clique em{" "}
            <span className="font-semibold text-slate-400">"Capturar apostas"</span> na extensão.
          </p>
        </div>
      ) : (
        <div className="divide-y divide-white/5">
          {bets.map((bet) => {
            const isMulti = bet.picks.length > 1;
            const profit = bet.potentialReturn - bet.stake;
            const hasCashout = bet.cashoutValue != null && bet.cashoutValue > 0;

            return (
              <div key={bet.id} className="px-4 py-3 space-y-2">
                {/* Linha principal */}
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    {isMulti ? (
                      <div className="space-y-1">
                        <div className="flex items-center gap-1.5">
                          <span className="text-[10px] font-semibold text-slate-400">
                            Múltipla · {bet.picks.length} pernas
                          </span>
                          <StatusBadge status={bet.status} />
                        </div>
                        {bet.picks.map((p, i) => (
                          <div key={i} className="flex items-center gap-1.5 text-[11px] text-slate-300">
                            <span className="text-slate-600">·</span>
                            <span>{formatMarket(p.market)}</span>
                            <span className="text-slate-500">→</span>
                            <span className="font-medium">{formatOutcome(p.outcome)}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold text-white">
                          {formatMarket(bet.picks[0]?.market ?? "")}
                        </span>
                        <span className="text-slate-500">→</span>
                        <span className="text-sm text-slate-300">
                          {formatOutcome(bet.picks[0]?.outcome ?? "")}
                        </span>
                        <StatusBadge status={bet.status} />
                      </div>
                    )}
                  </div>

                  {/* Odds + stake */}
                  <div className="shrink-0 text-right">
                    <div className="text-base font-black font-mono text-white">
                      @{bet.oddsPlaced.toFixed(2)}
                    </div>
                    <div className="text-[10px] text-slate-500">
                      R$ {bet.stake.toFixed(2)}
                    </div>
                  </div>
                </div>

                {/* Retorno potencial + cashout */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3 text-[10px] text-slate-500">
                    <span>
                      Retorno:{" "}
                      <span className="font-mono font-semibold text-neon-green">
                        R$ {bet.potentialReturn.toFixed(2)}
                      </span>
                    </span>
                    <span className="text-slate-700">·</span>
                    <span>
                      Lucro:{" "}
                      <span className="font-mono font-semibold text-neon-green">
                        +R$ {profit.toFixed(2)}
                      </span>
                    </span>
                  </div>
                  {hasCashout && (
                    <div className="flex items-center gap-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 px-2 py-1">
                      <span className="text-[9px] font-bold text-amber-300">CASHOUT</span>
                      <span className="font-mono text-[11px] font-bold text-amber-200">
                        R$ {bet.cashoutValue!.toFixed(2)}
                      </span>
                    </div>
                  )}
                </div>

                {/* Ticket code */}
                {bet.ticketCode && (
                  <p className="text-[9px] font-mono text-slate-700">#{bet.ticketCode}</p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
