import type {
  InplayHalfPeriodTickets,
  InplayHalfTickets,
  InplayTicketCombo,
  InplayTicketLeg,
  SuperbetLiveAdvice,
} from "@/domain/entities";
import {
  SendComboProposalButton,
} from "@/presentation/components/predictions/SendComboProposalButton";
import { buildProposalFromInplayCombo, buildProposalFromInplayLeg } from "@/presentation/utils/comboProposalPayload";

interface LiveHalfTicketsPanelProps {
  data: SuperbetLiveAdvice;
}

function formatPct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

function LegRow({ leg, data }: { leg: InplayTicketLeg; data: SuperbetLiveAdvice }) {
  const proposal = buildProposalFromInplayLeg(leg, {
    homeTeam: data.homeTeam,
    awayTeam: data.awayTeam,
    superbetEventId: data.superbetEventId,
    minute: data.minute,
  });

  return (
    <li className="rounded-lg border border-white/8 bg-black/20 px-3 py-2">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <span className="text-sm text-slate-100">{leg.label}</span>
        <span className="font-mono text-sm text-neon-green">@{leg.marketOdd.toFixed(2)}</span>
      </div>
      <div className="mt-1 flex flex-wrap gap-3 text-[11px] text-slate-500">
        <span>Modelo {formatPct(leg.modelProb)}</span>
        <span>Edge {leg.edgePp.toFixed(1)} pp</span>
        <span>EV {(leg.expectedValue * 100).toFixed(1)}%</span>
      </div>
      <SendComboProposalButton proposal={proposal} compact className="mt-2" />
    </li>
  );
}

function ComboCard({
  combo,
  data,
}: {
  combo: InplayTicketCombo;
  data: SuperbetLiveAdvice;
}) {
  const proposal = buildProposalFromInplayCombo(combo, {
    homeTeam: data.homeTeam,
    awayTeam: data.awayTeam,
    superbetEventId: data.superbetEventId,
    minute: data.minute,
  });

  return (
    <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/[0.06] p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-emerald-200">{combo.title}</h4>
        <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 font-mono text-xs text-emerald-300">
          @{combo.combinedOdd.toFixed(2)}
        </span>
      </div>
      <ul className="space-y-1.5">
        {combo.legs.map((leg) => (
          <li key={`${leg.market}-${leg.outcome}`} className="text-xs text-slate-300">
            • {leg.label}{" "}
            <span className="font-mono text-slate-500">@{leg.marketOdd.toFixed(2)}</span>
          </li>
        ))}
      </ul>
      <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-slate-400">
        <span>Hit est. {formatPct(combo.combinedProb)}</span>
        <span>EV {(combo.combinedEv * 100).toFixed(1)}%</span>
        <span>
          Stake {combo.suggestedStakePct.toFixed(1)}% (R$ {combo.suggestedStakeValue.toFixed(0)})
        </span>
      </div>
      {combo.notes.length > 0 && (
        <p className="mt-2 text-[10px] leading-relaxed text-slate-500">{combo.notes[0]}</p>
      )}
      <SendComboProposalButton proposal={proposal} compact className="mt-3" />
    </div>
  );
}

function PeriodSection({
  title,
  badge,
  block,
  data,
}: {
  title: string;
  badge: string;
  block: InplayHalfPeriodTickets;
  data: SuperbetLiveAdvice;
}) {
  return (
    <section className="rounded-xl border border-white/8 bg-white/[0.02] p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        <span className="rounded-full bg-white/8 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
          {badge}
        </span>
      </div>

      {!block.available && (
        <p className="text-xs text-slate-500">
          {block.closedReason ?? "Sem sugestões neste período."}
        </p>
      )}

      {block.singles.length > 0 && (
        <div className="mb-3">
          <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-slate-500">
            Simples
          </p>
          <ul className="space-y-2">
            {block.singles.map((leg) => (
              <LegRow key={`${leg.market}-${leg.outcome}`} leg={leg} data={data} />
            ))}
          </ul>
        </div>
      )}

      {block.combos.length > 0 && (
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-slate-500">
            Múltiplas (mesmo tempo)
          </p>
          <div className="space-y-2">
            {block.combos.map((combo) => (
              <ComboCard key={combo.id} combo={combo} data={data} />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

/** Bilhetes simples e múltiplas separados por 1º e 2º tempo. */
export function LiveHalfTicketsPanel({ data }: LiveHalfTicketsPanelProps) {
  const tickets: InplayHalfTickets | null = data.halfTickets;
  if (data.isFinished) return null;

  if (!tickets) {
    return (
      <section className="rounded-2xl border border-white/10 bg-white/[0.02] p-4">
        <h2 className="text-base font-semibold text-white">Bilhetes por tempo</h2>
        <p className="mt-2 text-xs text-slate-500">
          Aguardando dados do refresh completo (~60s). Use o botão violeta acima para enviar a
          leitura principal à estação.
        </p>
      </section>
    );
  }

  const hasContent =
    tickets.firstHalf.singles.length > 0 ||
    tickets.firstHalf.combos.length > 0 ||
    tickets.secondHalf.singles.length > 0 ||
    tickets.secondHalf.combos.length > 0 ||
    tickets.mixedCombos.length > 0;

  const showMixed = tickets.mixedCombos.length > 0 && data.minute <= 45;

  return (
    <section className="rounded-2xl border border-white/10 bg-white/[0.02] p-4">
      <div className="mb-4">
        <h2 className="text-base font-semibold text-white">Bilhetes por tempo</h2>
        <p className="mt-1 text-xs text-slate-500">
          Palpites do market_scan (modelo in-play × odd Superbet, EV+) · duplas decorrelacionadas
        </p>
      </div>

      {!hasContent && (
        <p className="mb-3 text-xs text-slate-500">
          Sem duplas montadas neste minuto — mercados do 1T encerrados no intervalo ou sem par
          decorrelacionado com EV+. Envie palpites simples pelo botão violeta no hero.
        </p>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <PeriodSection title="1º Tempo" badge="1T" block={tickets.firstHalf} data={data} />
        <PeriodSection title="2º Tempo" badge="2T" block={tickets.secondHalf} data={data} />
      </div>

      {showMixed && (
        <div className="mt-4 border-t border-white/8 pt-4">
          <h3 className="mb-2 text-sm font-semibold text-violet-200">Bilhetes mistos (1T + 2T)</h3>
          <p className="mb-3 text-xs text-slate-500">
            Combine um palpite do 1º tempo com outro do 2º — monte como múltipla na Superbet.
          </p>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {tickets.mixedCombos.map((combo) => (
              <ComboCard key={combo.id} combo={combo} data={data} />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
