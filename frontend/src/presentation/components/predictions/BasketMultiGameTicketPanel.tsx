import { useMemo, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { buildBasketMultiGameTicketsUseCase } from "@/application/container";
import type { BasketSuperbetLiveEvent } from "@/domain/entities";
import { sendSuperbetTicketToExtension } from "@/presentation/utils/superbetExtensionBridge";
import { buildBasketMultiLiveLink } from "@/presentation/pages/BasketMultiLiveInPlayPage";

interface BasketMultiGameTicketPanelProps {
  events: BasketSuperbetLiveEvent[];
  selectedEventIds: number[];
  onClearSelection: () => void;
}

function buildBasketInPlayLink(eventId: number): string {
  return `/ao-vivo/basquete/${eventId}`;
}

function formatPct(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function formatEv(value: number | null | undefined): string {
  if (value == null) return "—";
  const pct = value * 100;
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

export function BasketMultiGameTicketPanel({
  events,
  selectedEventIds,
  onClearSelection,
}: BasketMultiGameTicketPanelProps) {
  const [stake, setStake] = useState(10);
  const [selectedTicketIndex, setSelectedTicketIndex] = useState(0);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);
  const [extensionFeedback, setExtensionFeedback] = useState<string | null>(null);
  const [sendingExtension, setSendingExtension] = useState(false);

  const selectedEvents = useMemo(
    () => events.filter((event) => selectedEventIds.includes(event.eventId)),
    [events, selectedEventIds],
  );

  const mutation = useMutation({
    mutationFn: () =>
      buildBasketMultiGameTicketsUseCase.execute({
        eventIds: selectedEventIds,
        bankroll: 1000,
        stake,
        fast: true,
        maxTickets: 5,
      }),
  });

  const tickets = mutation.data?.suggestedTickets ?? [];
  const activeTicket = tickets[selectedTicketIndex] ?? tickets[0] ?? null;

  const handleCopy = async () => {
    if (!activeTicket) return;
    const lines = [
      `Múltipla basquete (${activeTicket.legs.length} jogos)`,
      `Odd combinada: @${activeTicket.combinedOdd.toFixed(2)}`,
      `EV modelo: ${formatEv(activeTicket.combinedEv)}`,
      `Stake sugerida: R$ ${activeTicket.stakeBrl.toFixed(2)}`,
      "",
      ...activeTicket.legs.map(
        (leg) =>
          `#${leg.superbetEventId} ${leg.homeTeam} × ${leg.awayTeam} — ${leg.marketDisplay} · ${leg.label} @${leg.marketOdd.toFixed(2)} (EV ${formatEv(leg.expectedValue)})`,
      ),
    ];
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      setCopyFeedback("Copiado!");
      window.setTimeout(() => setCopyFeedback(null), 2500);
    } catch {
      setCopyFeedback("Não foi possível copiar.");
    }
  };

  const handleSendExtension = useCallback(async () => {
    if (!activeTicket || activeTicket.legs.length < 2) return;
    setSendingExtension(true);
    setExtensionFeedback(null);
    const firstLeg = activeTicket.legs[0];
    const res = await sendSuperbetTicketToExtension({
      id: `basket-multi-${Date.now()}`,
      superbetEventId: firstLeg.superbetEventId,
      homeTeam: activeTicket.legs.map((leg) => leg.homeTeam).join(" · "),
      awayTeam: activeTicket.legs.map((leg) => leg.awayTeam).join(" · "),
      title: `Basquete multi · ${activeTicket.legs.length} jogos`,
      stake: activeTicket.stakeBrl,
      combinedOdd: activeTicket.combinedOdd,
      potentialReturn: activeTicket.finalPayout,
      combinedProb: activeTicket.combinedProb ?? undefined,
      bonusEligible: activeTicket.bonusEligible,
      crossGame: true,
      legs: activeTicket.legs.map((leg) => ({
        market: leg.market,
        outcome: leg.outcome,
        label: leg.label,
        marketOdd: leg.marketOdd,
        modelProb: leg.modelProb,
        superbetEventId: leg.superbetEventId,
        homeTeam: leg.homeTeam,
        awayTeam: leg.awayTeam,
        superbetMarket: leg.marketDisplay,
      })),
      source: "basket_multi_game",
    });
    setSendingExtension(false);
    if (res.ok) {
      setExtensionFeedback("Enviado — a extensão abrirá cada jogo na Superbet.");
    } else {
      setExtensionFeedback(res.error ?? "Falha ao enviar à extensão.");
    }
    window.setTimeout(() => setExtensionFeedback(null), 9000);
  }, [activeTicket]);

  if (selectedEventIds.length < 2) return null;

  return (
    <section className="live-glass-panel mb-6 p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="section-label">Bilhete multi-jogo (basquete)</h2>
          <p className="mt-1 text-xs text-slate-400">
            {selectedEventIds.length} jogo(s) selecionado(s) · 1 palpite por jogo · odds independentes
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-xs text-slate-400">
            Stake R$
            <input
              type="number"
              min={1}
              step={1}
              value={stake}
              onChange={(e) => setStake(Number(e.target.value) || 10)}
              className="w-20 rounded-md border border-white/10 bg-black/20 px-2 py-1 text-sm text-white"
            />
          </label>
          <button
            type="button"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="rounded-lg border border-amber-500/30 bg-amber-500/15 px-3 py-1.5 text-xs font-semibold text-amber-200 hover:border-amber-400/40 disabled:opacity-50"
          >
            {mutation.isPending ? "Calculando…" : "Montar bilhete"}
          </button>
          <button
            type="button"
            onClick={onClearSelection}
            className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-400 hover:text-white"
          >
            Limpar
          </button>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        {selectedEvents.map((event) => (
          <span
            key={event.eventId}
            className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-slate-300"
          >
            {event.homeTeam} × {event.awayTeam}
          </span>
        ))}
      </div>

      {mutation.isError ? (
        <p className="text-sm text-red-300">
          {mutation.error instanceof Error
            ? mutation.error.message
            : "Falha ao montar bilhete multi-jogo."}
        </p>
      ) : null}

      {mutation.data && tickets.length === 0 ? (
        <p className="text-sm text-slate-400">
          Nenhum bilhete sugerido com EV mínimo para os jogos selecionados.
          {mutation.data.skippedEvents.length > 0
            ? ` ${mutation.data.skippedEvents.length} jogo(s) sem palpite.`
            : ""}
        </p>
      ) : null}

      {activeTicket ? (
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div>
              <div className="text-sm font-semibold text-amber-200">
                @{activeTicket.combinedOdd.toFixed(2)} · EV {formatEv(activeTicket.combinedEv)} · prob{" "}
                {formatPct(activeTicket.combinedProb)}
              </div>
              <div className="text-xs text-slate-400">
                R$ {activeTicket.stakeBrl.toFixed(2)} → R$ {activeTicket.finalPayout.toFixed(2)}
                {activeTicket.bonusEligible ? ` (+${(activeTicket.bonusPercentage * 100).toFixed(0)}% bônus)` : ""}
              </div>
            </div>
            {tickets.length > 1 ? (
              <div className="flex gap-1">
                {tickets.map((ticket, index) => (
                  <button
                    key={ticket.ticketId}
                    type="button"
                    onClick={() => setSelectedTicketIndex(index)}
                    className={`rounded-md px-2 py-1 text-[11px] ${
                      index === selectedTicketIndex
                        ? "bg-amber-500/25 text-amber-100"
                        : "bg-white/5 text-slate-400"
                    }`}
                  >
                    #{index + 1} ({ticket.legs.length}p)
                  </button>
                ))}
              </div>
            ) : null}
          </div>

          <ul className="space-y-2">
            {activeTicket.legs.map((leg) => (
              <li
                key={`${leg.superbetEventId}:${leg.market}:${leg.outcome}`}
                className="rounded-lg border border-white/10 bg-black/20 px-3 py-2"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <div className="text-xs font-medium text-white">
                      {leg.homeTeam} × {leg.awayTeam}
                    </div>
                    <div className="text-[11px] text-slate-400">
                      {leg.marketDisplay || leg.market}
                    </div>
                    <div className="text-sm text-amber-100">{leg.label}</div>
                    <div className="text-[11px] text-slate-500">
                      EV {formatEv(leg.expectedValue)} · edge {leg.edgePp.toFixed(1)} pp ·{" "}
                      {leg.action}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-sm text-white">@{leg.marketOdd.toFixed(2)}</div>
                    <Link
                      to={buildBasketInPlayLink(leg.superbetEventId)}
                      className="text-[11px] text-amber-300 hover:underline"
                    >
                      Abrir jogo
                    </Link>
                  </div>
                </div>
              </li>
            ))}
          </ul>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Link
              to={buildBasketMultiLiveLink(selectedEventIds)}
              className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs font-semibold text-amber-200 hover:border-amber-400/40"
            >
              Painel ao vivo multi
            </Link>
            <button
              type="button"
              onClick={() => void handleSendExtension()}
              disabled={sendingExtension}
              className="rounded-lg border border-emerald-500/30 bg-emerald-500/15 px-3 py-1.5 text-xs font-semibold text-emerald-200 hover:border-emerald-400/40 disabled:opacity-50"
            >
              {sendingExtension ? "Enviando…" : "Enviar à extensão"}
            </button>
            <button
              type="button"
              onClick={() => void handleCopy()}
              className="rounded-lg border border-white/15 px-3 py-1.5 text-xs text-slate-200 hover:bg-white/5"
            >
              Copiar pernas
            </button>
            {extensionFeedback ? (
              <span className="text-xs text-emerald-300">{extensionFeedback}</span>
            ) : null}
            {copyFeedback ? (
              <span className="text-xs text-emerald-300">{copyFeedback}</span>
            ) : null}
          </div>

          <p className="mt-3 text-[11px] text-slate-500">
            A extensão Bolão AI visita cada jogo na Superbet, clica a perna e preenche a stake no
            cupom múltipla. Recarregue a extensão em chrome://extensions após atualizar.
          </p>

          {activeTicket.warnings.length > 0 ? (
            <ul className="mt-2 space-y-1 text-[11px] text-amber-200/80">
              {activeTicket.warnings.map((warning) => (
                <li key={warning}>• {warning}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {mutation.data?.perGameBest.length ? (
        <details className="mt-3 text-xs text-slate-500">
          <summary className="cursor-pointer hover:text-slate-300">
            Melhor palpite por jogo ({mutation.data.perGameBest.length})
          </summary>
          <ul className="mt-2 space-y-1">
            {mutation.data.perGameBest.map((leg) => (
              <li key={leg.superbetEventId}>
                {leg.homeTeam} × {leg.awayTeam}: {leg.marketDisplay} · {leg.label} @
                {leg.marketOdd.toFixed(2)}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}
