import type { SuperbetLiveAdvice, WcComboTicket } from "@/domain/entities";
import {
  SendComboProposalButton,
} from "@/presentation/components/predictions/SendComboProposalButton";
import { ComboTicketLast10Panel } from "@/presentation/components/predictions/ComboTicketLast10Panel";
import { buildProposalFromKxlTicket } from "@/presentation/utils/comboProposalPayload";

type ComboLeg = WcComboTicket extends { mainBets: infer M }
  ? M extends Array<infer L>
    ? L
    : never
  : never;

const ACCURACY_STYLES: Record<string, string> = {
  alta: "border-neon-green/40 bg-neon-green/10 text-neon-green",
  media: "border-amber-500/35 bg-amber-500/10 text-amber-300",
  baixa: "border-white/15 bg-white/5 text-slate-400",
  sem_dados: "border-white/10 bg-white/[0.03] text-slate-500",
};

interface ComboTicketPanelProps {
  homeTeam: string;
  awayTeam: string;
  ticket?: WcComboTicket | null;
  patternAccuracy?: SuperbetLiveAdvice["strategy"] extends infer S
    ? S extends { patternAccuracy: infer P }
      ? P
      : null
    : null;
  /** @deprecated use ticket + patternAccuracy */
  strategy?: SuperbetLiveAdvice["strategy"];
  superbetEventId?: number | null;
  minute?: number | null;
}

function BetLine({ leg, index, variant }: { leg: ComboLeg; index: number; variant: "main" | "reserve" }) {
  const prefix = variant === "main" ? "Aposta" : "Aposta Reserva";
  const evPositive = leg.expectedValue != null && leg.expectedValue > 0;
  return (
    <div
      className={`rounded-xl border px-4 py-3 ${
        variant === "main"
          ? "border-neon-blue/30 bg-neon-blue/[0.06]"
          : "border-white/10 bg-white/[0.03]"
      }`}
    >
      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
        {prefix} {index}
      </p>
      <p className="mt-1 text-sm font-medium text-white">{leg.label}</p>
      <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-400">
        <span className="rounded-md bg-white/5 px-2 py-0.5">
          Acerto histórico: {(leg.hitRate * 100).toFixed(0)}% ({leg.hits}/{leg.total})
        </span>
        <span className="rounded-md bg-white/5 px-2 py-0.5">{leg.patternRef}</span>
        {leg.marketOdd != null && (
          <span className="rounded-md bg-neon-blue/10 px-2 py-0.5 text-neon-blue">
            Odd {leg.marketOdd.toFixed(2)}
          </span>
        )}
        {leg.expectedValue != null && (
          <span
            className={`rounded-md px-2 py-0.5 ${
              evPositive ? "bg-neon-green/10 text-neon-green" : "bg-red-500/10 text-red-300"
            }`}
          >
            EV {(leg.expectedValue * 100).toFixed(1)}%
          </span>
        )}
        {leg.edgePp != null && (
          <span className="rounded-md bg-white/5 px-2 py-0.5">Edge {leg.edgePp.toFixed(1)} pp</span>
        )}
      </div>
      {leg.bookChecked && leg.availableOnBook && leg.superbetMarket && (
        <p className="mt-2 rounded-md border border-neon-blue/25 bg-neon-blue/10 px-2 py-1.5 text-[11px] font-medium text-neon-blue">
          Criar Aposta: {leg.superbetMarket} → {leg.superbetPick}
          {leg.marketOdd != null ? ` @${leg.marketOdd.toFixed(2)}` : ""}
        </p>
      )}
      {leg.lineAdjustment && (
        <p className="mt-1 text-[11px] text-amber-400/90">{leg.lineAdjustment}</p>
      )}
      {leg.bookChecked && leg.availableOnBook === false && (
        <p className="mt-1 text-[11px] font-medium text-red-300/90">
          Linha não encontrada na Superbet — não inclua no bilhete.
        </p>
      )}
    </div>
  );
}

export function ComboTicketPanel({
  homeTeam,
  awayTeam,
  ticket: ticketProp,
  patternAccuracy: accuracyProp,
  strategy,
  superbetEventId,
  minute,
}: ComboTicketPanelProps) {
  const ticket = ticketProp ?? strategy?.comboTicket ?? null;
  const accuracy = accuracyProp ?? strategy?.patternAccuracy ?? ticket?.accuracy ?? null;
  const kxlProposal =
    ticket?.available && ticket.mainBets.length > 0
      ? buildProposalFromKxlTicket(
          {
            title: ticket.title,
            mainBets: ticket.mainBets,
            comboOdd: ticket.comboOdd,
            comboEv: ticket.comboEv,
            suggestedStakeValue: ticket.suggestedStakeValue,
            bookCoverage: ticket.bookCoverage,
          },
          {
            homeTeam,
            awayTeam,
            superbetEventId,
            minute,
          },
        )
      : null;

  if (!ticket && !accuracy) return null;

  return (
    <section className="rounded-2xl border border-neon-blue/25 bg-neon-blue/[0.04] p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Bilhete combo — estudo KXL</h2>
          <p className="text-xs text-slate-500">
            Eixos escolhidos pelo score KXL deste confronto · envio só com odd Superbet e EV positivo
          </p>
        </div>
        {accuracy && (
          <span
            className={`rounded-lg border px-3 py-1.5 text-[11px] font-bold uppercase tracking-wide ${
              ACCURACY_STYLES[accuracy.label] ?? ACCURACY_STYLES.sem_dados
            }`}
          >
            Acurácia {accuracy.label.replace("_", " ")}
          </span>
        )}
      </div>

      {accuracy && (
        <p className="mb-4 text-xs leading-relaxed text-slate-400">{accuracy.reason}</p>
      )}

      {ticket?.available &&
        ticket.mainBets.some((leg) => leg.bookChecked === false) &&
        !superbetEventId && (
          <p className="mb-4 rounded-lg border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-[11px] leading-relaxed text-amber-100/90">
            Odds ainda não cruzadas com a Superbet. Abra pelo botão <strong>Ao vivo</strong> na
            tabela (ou informe o evento) para validar linhas e EV automaticamente.
          </p>
        )}

      {!ticket?.available ? (
        <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-slate-400">
          {ticket?.reason ??
            "Sem combo seguro para este confronto — padrões insuficientes ou eixos correlacionados."}
        </div>
      ) : (
        <>
          <p className="mb-3 text-xs font-medium text-neon-blue">
            {ticket.title ?? `${homeTeam} x ${awayTeam}`}
          </p>

          <div className="mb-4 space-y-2">
            <p className="text-[11px] uppercase tracking-wider text-slate-500">Apostas principais (combo)</p>
            <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] leading-relaxed text-amber-100/90">
              No <strong className="text-amber-50">Criar Aposta</strong> da Superbet use{" "}
              <strong className="text-amber-50">só estas 2 pernas</strong>. Reservas são singles
              separados — não empilhe tudo no mesmo bilhete @2.00.
            </p>
            {ticket.mainBets.map((leg, idx) => (
              <BetLine key={`main-${leg.label}-${idx}`} leg={leg} index={idx + 1} variant="main" />
            ))}
          </div>

          {ticket.reserveBets.length > 0 && (
            <div className="mb-4 space-y-2 border-t border-white/8 pt-4">
              <p className="text-[11px] uppercase tracking-wider text-slate-500">
                Apostas reserva (singles — só se confirmadas na Superbet)
              </p>
              {ticket.reserveBets.map((leg, idx) => (
                <BetLine key={`res-${leg.label}-${idx}`} leg={leg} index={idx + 1} variant="reserve" />
              ))}
            </div>
          )}

          <div className="mb-4 grid gap-2 sm:grid-cols-3 lg:grid-cols-4">
            <Metric
              label="Stake sugerido"
              value={`${ticket.suggestedStakePct.toFixed(1)}%`}
              sub={`R$ ${ticket.suggestedStakeValue.toFixed(0)}`}
            />
            <Metric
              label="Acerto combo est."
              value={`${(ticket.combinedHitRateEstimate * 100).toFixed(0)}%`}
              sub="produto das taxas 9/10+"
            />
            {ticket.comboOdd != null && (
              <Metric
                label="Odd combo Superbet"
                value={ticket.comboOdd.toFixed(2)}
                sub={
                  ticket.comboEv != null
                    ? `EV ${(ticket.comboEv * 100).toFixed(1)}%`
                    : "pernas cruzadas"
                }
              />
            )}
            <Metric
              label="Padrões"
              value={String(accuracy?.patternCount ?? "—")}
              sub={
                ticket.bookCoverage
                  ? `${ticket.bookCoverage.mainAvailable}/${ticket.bookCoverage.mainTotal} na casa`
                  : "linhas históricas"
              }
            />
          </div>

          {ticket.strategyNotes.length > 0 && (
            <ul className="space-y-1.5 text-xs text-slate-400">
              {ticket.strategyNotes.map((note) => (
                <li key={note} className="flex gap-2">
                  <span className="text-neon-blue" aria-hidden="true">
                    •
                  </span>
                  <span>{note}</span>
                </li>
              ))}
            </ul>
          )}

          <ComboTicketLast10Panel analysis={ticket.last10Analysis} />

          {kxlProposal && (
            <SendComboProposalButton proposal={kxlProposal} className="mt-4" />
          )}
        </>
      )}
    </section>
  );
}

function Metric({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-xl border border-white/8 bg-white/[0.03] px-3 py-2.5">
      <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="font-mono text-lg font-semibold text-white">{value}</p>
      <p className="text-[11px] text-slate-500">{sub}</p>
    </div>
  );
}
