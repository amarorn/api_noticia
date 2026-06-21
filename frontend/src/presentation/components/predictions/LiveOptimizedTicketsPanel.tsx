import type { SuperbetLiveAdvice } from "@/domain/entities";
import { sendSuperbetTicketToExtension } from "@/presentation/utils/superbetExtensionBridge";
import {
  IconZap,
  IconTrendingUp,
  IconTarget,
  IconBell,
  IconX,
  IconWallet,
} from "@/presentation/components/ui/Icons";

interface OptimizedTicketLeg {
  market: string;
  outcome: string;
  label: string;
  modelProb: number;
  marketOdd: number;
  expectedValue: number;
  edgePp: number;
  kellyQuarter: number;
  classification: string;
}

interface OptimizedTicket {
  legs: OptimizedTicketLeg[];
  combinedOdd: number;
  combinedProb: number;
  combinedEv: number;
  correlationPenalty: number;
  score: number;
  stakeBrl: number;
  stakePct: number;
  periodMix: string;
  nLegs: number;
  valid: boolean;
  validation: {
    valid: boolean;
    errors: Array<{ severity: string; code: string; reason: string }>;
    warnings: Array<{ severity: string; code: string; reason: string }>;
  };
}

interface LiveOptimizedTicketsPanelProps {
  data: SuperbetLiveAdvice;
}

const PERIOD_LABELS: Record<string, string> = {
  "1h": "1º Tempo",
  "2h": "2º Tempo",
  ft: "Tempo Total",
  mixed: "Misto (1T + 2T)",
};

const PERIOD_COLORS: Record<string, string> = {
  "1h": "border-amber-500/30 bg-amber-500/10 text-amber-300",
  "2h": "border-neon-blue/30 bg-neon-blue/10 text-neon-blue",
  ft: "border-neon-green/30 bg-neon-green/10 text-neon-green",
  mixed: "border-purple-500/30 bg-purple-500/10 text-purple-300",
};

const CLASSIFICATION_COLORS: Record<string, string> = {
  forte: "text-neon-green",
  high_confidence: "text-neon-green",
  value_bet: "text-neon-blue",
  watch: "text-amber-300",
  avoid: "text-red-400",
};

const CLASSIFICATION_LABELS: Record<string, string> = {
  forte: "Forte",
  high_confidence: "Alta Confiança",
  value_bet: "Valor",
  watch: "Observar",
  avoid: "Evitar",
};

function formatMarketLabel(market: string): string {
  const map: Record<string, string> = {
    h2h: "1X2",
    "1h_h2h": "1X2 1T",
    "2h_h2h": "1X2 2T",
    over_2_5: "Over 2.5",
    "1h_over_1_5": "Over 1.5 1T",
    "2h_over_1_5": "Over 1.5 2T",
    btts: "Ambas marcam",
    next_goal: "Próximo gol",
  };
  return map[market] || market;
}

function formatOutcome(outcome: string, _market: string, homeTeam: string, awayTeam: string): string {
  if (outcome === "1") return homeTeam;
  if (outcome === "2") return awayTeam;
  if (outcome === "X" || outcome === "draw") return "Empate";
  if (outcome === "yes" || outcome === "sim" || outcome === "over") return "Sim";
  if (outcome === "no" || outcome === "under") return "Não";
  if (outcome === "home") return homeTeam;
  if (outcome === "away") return awayTeam;
  return outcome;
}

export function LiveOptimizedTicketsPanel({ data }: LiveOptimizedTicketsPanelProps) {
  const tickets = data.optimizedTickets;
  if (!tickets) return null;

  const allTickets: Array<{ period: string; tickets: OptimizedTicket[] }> = [
    { period: "1h", tickets: tickets.tickets_1h || [] },
    { period: "2h", tickets: tickets.tickets_2h || [] },
    { period: "ft", tickets: tickets.tickets_ft || [] },
    { period: "mixed", tickets: tickets.tickets_mixed || [] },
  ];

  const totalTickets = allTickets.reduce((sum, g) => sum + g.tickets.length, 0);
  if (totalTickets === 0) return null;

  const handleSendToExtension = async (ticket: OptimizedTicket) => {
    const result = await sendSuperbetTicketToExtension({
      id: `opt-${Date.now()}`,
      superbetEventId: data.superbetEventId || 0,
      homeTeam: data.homeTeam,
      awayTeam: data.awayTeam,
      title: `Bilhete ${PERIOD_LABELS[ticket.periodMix] || ticket.periodMix}`,
      stake: ticket.stakeBrl,
      combinedOdd: ticket.combinedOdd,
      potentialReturn: ticket.stakeBrl * ticket.combinedOdd,
      combinedProb: ticket.combinedProb,
      legs: ticket.legs.map((leg) => ({
        market: leg.market,
        outcome: leg.outcome,
        label: leg.label,
        marketOdd: leg.marketOdd,
        modelProb: leg.modelProb,
      })),
      source: "inplay_combo",
    });

    if (!result.ok) {
      alert(result.error || "Falha ao enviar à extensão");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <IconZap className="h-4 w-4 text-neon-green" />
        <h3 className="text-sm font-semibold text-white">Bilhetes Otimizados</h3>
        <span className="rounded-full bg-neon-green/15 px-2 py-0.5 text-[10px] font-bold text-neon-green">
          {totalTickets}
        </span>
      </div>

      {allTickets.map(
        (group) =>
          group.tickets.length > 0 && (
            <div key={group.period} className="space-y-3">
              <div className="flex items-center gap-2">
                <span
                  className={`rounded-lg border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${PERIOD_COLORS[group.period]}`}
                >
                  {PERIOD_LABELS[group.period]}
                </span>
                <span className="text-[10px] text-slate-500">{group.tickets.length} bilhete(s)</span>
              </div>

              {group.tickets.map((ticket, idx) => (
                <div
                  key={idx}
                  className={`rounded-xl border p-4 transition-all hover:border-neon-green/40 ${
                    ticket.valid
                      ? "border-white/10 bg-white/[0.03]"
                      : "border-red-500/20 bg-red-500/5"
                  }`}
                >
                  {/* Header do bilhete */}
                  <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="rounded-lg bg-white/5 px-2 py-0.5 text-[10px] font-mono font-bold text-white">
                        {ticket.nLegs} pernas
                      </span>
                      <span className="rounded-lg bg-neon-green/10 px-2 py-0.5 text-[10px] font-semibold text-neon-green">
                        Odd {ticket.combinedOdd.toFixed(2)}
                      </span>
                      <span
                        className={`rounded-lg px-2 py-0.5 text-[10px] font-semibold ${
                          ticket.combinedEv > 0.15
                            ? "bg-neon-green/15 text-neon-green"
                            : ticket.combinedEv > 0.05
                              ? "bg-neon-blue/15 text-neon-blue"
                              : "bg-amber-500/15 text-amber-300"
                        }`}
                      >
                        EV +{(ticket.combinedEv * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 text-[10px] text-slate-500">
                      <IconTarget className="h-3 w-3" />
                      Prob {(ticket.combinedProb * 100).toFixed(1)}%
                      {ticket.correlationPenalty > 0 && (
                        <span className="text-amber-400">
                          · Penalidade {(ticket.correlationPenalty * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Pernas */}
                  <div className="mb-3 space-y-2">
                    {ticket.legs.map((leg, legIdx) => (
                      <div
                        key={legIdx}
                        className="flex items-center justify-between rounded-lg bg-white/[0.02] px-3 py-2"
                      >
                        <div className="flex items-center gap-2">
                          <span
                            className={`text-[10px] font-semibold uppercase ${CLASSIFICATION_COLORS[leg.classification] || "text-slate-400"}`}
                          >
                            {CLASSIFICATION_LABELS[leg.classification] || leg.classification}
                          </span>
                          <span className="text-xs text-white">
                            {formatMarketLabel(leg.market)}
                          </span>
                          <span className="text-xs text-slate-400">
                            →{" "}
                            {formatOutcome(leg.outcome, leg.market, data.homeTeam, data.awayTeam)}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 text-[10px] text-slate-500">
                          <span className="flex items-center gap-1">
                            <IconTrendingUp className="h-3 w-3" />
                            {(leg.modelProb * 100).toFixed(0)}%
                          </span>
                          <span className="font-mono text-slate-300">@{leg.marketOdd.toFixed(2)}</span>
                          <span
                            className={`font-semibold ${leg.expectedValue > 0 ? "text-neon-green" : "text-red-400"}`}
                          >
                            EV {(leg.expectedValue * 100).toFixed(1)}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Stake e ações */}
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3 text-[10px] text-slate-500">
                      <span className="flex items-center gap-1">
                        <IconWallet className="h-3 w-3" />
                        Stake R$ {ticket.stakeBrl.toFixed(2)}
                      </span>
                      <span>{ticket.stakePct.toFixed(2)}% da banca</span>
                      <span className="font-mono text-slate-300">
                        Retorno R$ {(ticket.stakeBrl * ticket.combinedOdd).toFixed(2)}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleSendToExtension(ticket)}
                      className="rounded-lg border border-neon-green/30 bg-neon-green/10 px-3 py-1.5 text-xs font-semibold text-neon-green transition-colors hover:bg-neon-green/20"
                    >
                      Enviar à Superbet
                    </button>
                  </div>

                  {/* Warnings/Errors */}
                  {ticket.validation.warnings.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {ticket.validation.warnings.map((w, wIdx) => (
                        <p key={wIdx} className="flex items-center gap-1 text-[10px] text-amber-400">
                          <IconBell className="h-3 w-3" />
                          {w.reason}
                        </p>
                      ))}
                    </div>
                  )}
                  {ticket.validation.errors.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {ticket.validation.errors.map((e, eIdx) => (
                        <p key={eIdx} className="flex items-center gap-1 text-[10px] text-red-400">
                          <IconX className="h-3 w-3" />
                          {e.reason}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ),
      )}
    </div>
  );
}
