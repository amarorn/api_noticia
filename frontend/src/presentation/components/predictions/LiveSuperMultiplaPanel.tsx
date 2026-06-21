import { useCallback, useEffect, useMemo, useState } from "react";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import type { ComboProposalContext } from "@/application/dtos/comboProposal";
import { qualifyComboProposal } from "@/presentation/utils/comboProposalQualification";
import { SendComboProposalButton } from "@/presentation/components/predictions/SendComboProposalButton";
import { formatLongshotProbPct } from "@/presentation/utils/longshotCombos";
import {
  marketScanRowToSlipLeg,
  useSuperMultiplaSlip,
  type SuperMultiplaSlipLeg,
} from "@/presentation/hooks/useSuperMultiplaSlip";
import {
  SUPER_MULTIPLA_BONUS_PCT,
  SUPER_MULTIPLA_MIN_LEG_ODD,
} from "@/presentation/utils/superMultipla";
import {
  sendSuperbetTicketToExtension,
} from "@/presentation/utils/superbetExtensionBridge";

interface LiveSuperMultiplaPanelProps {
  data: SuperbetLiveAdvice;
}

function legKey(leg: Pick<SuperMultiplaSlipLeg, "market" | "outcome">): string {
  return `${leg.market}:${leg.outcome}`;
}

export function LiveSuperMultiplaPanel({ data }: LiveSuperMultiplaPanelProps) {
  const minLegOdd = data.superMultipla?.minLegOddForBonus ?? SUPER_MULTIPLA_MIN_LEG_ODD;
  const bonusPct = data.superMultipla?.bonusPct ?? SUPER_MULTIPLA_BONUS_PCT;
  const defaultStake = data.superMultipla?.defaultStake ?? 5;
  const [stake, setStake] = useState(defaultStake);
  const [legs, setLegs] = useState<SuperMultiplaSlipLeg[]>([]);
  const [creating, setCreating] = useState(false);
  const [createFeedback, setCreateFeedback] = useState<string | null>(null);

  const pickPool = useMemo(() => {
    const scan = data.strategy?.marketScan ?? [];
    return [...scan]
      .filter((row) => row.marketOdd >= minLegOdd)
      .sort((a, b) => b.expectedValue - a.expectedValue)
      .slice(0, 10);
  }, [data.strategy?.marketScan, minLegOdd]);

  const { result, isCalculating, canCalculate } = useSuperMultiplaSlip(data, legs, stake);

  const addLeg = useCallback(
    (row: (typeof pickPool)[number]) => {
      setLegs((prev) => {
        const key = `${row.market}:${row.outcome}`;
        if (prev.some((leg) => legKey(leg) === key)) return prev;
        if (prev.length >= 6) return prev;
        return [...prev, marketScanRowToSlipLeg(row, data)];
      });
    },
    [data],
  );

  const removeLeg = useCallback((key: string) => {
    setLegs((prev) => prev.filter((leg) => legKey(leg) !== key));
  }, []);

  const loadSuggestion = useCallback(
    (index: number) => {
      const combo = data.superMultipla?.suggestedCombos[index];
      if (!combo?.legs?.length) return;
      setStake(combo.stake);
      setLegs(
        combo.legs.map((leg) => ({
          id: leg.id ?? crypto.randomUUID(),
          market: leg.market,
          outcome: leg.outcome,
          market_odd: leg.marketOdd,
          model_prob: leg.modelProb,
          superbet_event_id: data.superbetEventId,
          event_name: `${data.homeTeam} vs ${data.awayTeam}`,
          selection_label: leg.label,
          is_live: data.isLive,
          minute: data.minute,
          label: leg.label,
          modelProb: leg.modelProb,
          expectedValue: leg.expectedValue ?? 0,
          edgePp: leg.edgePp ?? 0,
        })),
      );
    },
    [data],
  );

  useEffect(() => {
    if (legs.length > 0) return;
    const first = data.superMultipla?.suggestedCombos?.[0];
    if (first?.legs?.length) loadSuggestion(0);
  }, [data.superMultipla?.suggestedCombos, legs.length, loadSuggestion]);

  const proposal: ComboProposalContext | null = useMemo(() => {
    if (!result || legs.length < 2) return null;
    const combinedEv = result.combinedEv ?? legs.reduce((p, l) => p * l.modelProb, 1) * result.totalOdds - 1;
    const combinedProb = result.combinedProb ?? legs.reduce((p, l) => p * l.modelProb, 1);
    const ctx: ComboProposalContext = {
      homeTeam: data.homeTeam,
      awayTeam: data.awayTeam,
      superbetEventId: data.superbetEventId,
      minute: data.minute,
      title: `Super Múltipla · ${legs.length} pernas`,
      combinedOdd: result.totalOdds,
      combinedProb,
      combinedEv,
      suggestedStake: stake,
      modelSource: "inplay_market_scan",
      qualified: false,
      disqualifyReason: null,
      legs: legs.map((leg) => ({
        market: leg.market,
        outcome: leg.outcome,
        label: leg.label,
        modelProb: leg.modelProb,
        marketOdd: leg.market_odd,
        expectedValue: leg.expectedValue,
        edgePp: leg.edgePp,
      })),
    };
    return qualifyComboProposal(ctx);
  }, [data, legs, result, stake]);

  const createTicket = useCallback(async () => {
    if (!result || legs.length < 2) return;
    setCreating(true);
    setCreateFeedback(null);
    const combinedProb =
      result.combinedProb ?? legs.reduce((p, l) => p * l.modelProb, 1);
    const res = await sendSuperbetTicketToExtension({
      id: `super-multipla-${Date.now()}`,
      superbetEventId: data.superbetEventId,
      homeTeam: data.homeTeam,
      awayTeam: data.awayTeam,
      title: `Super Múltipla · ${legs.length} pernas`,
      stake,
      combinedOdd: result.totalOdds,
      potentialReturn: result.bonusEligible ? result.finalPayout : result.potentialPayout,
      combinedProb,
      bonusEligible: result.bonusEligible,
      legs: legs.map((leg) => ({
        market: leg.market,
        outcome: leg.outcome,
        label: leg.label,
        marketOdd: leg.market_odd,
        modelProb: leg.modelProb,
      })),
      source: "super_multipla",
    });
    setCreating(false);
    if (res.ok) {
      setCreateFeedback("Enviado à extensão — aba Superbet aberta.");
    } else {
      setCreateFeedback(res.error ?? "Falha ao enviar à extensão.");
    }
    window.setTimeout(() => setCreateFeedback(null), 8000);
  }, [data, legs, result, stake]);

  if (data.isFinished) return null;

  return (
    <section
      className="rounded-2xl border border-amber-500/25 bg-gradient-to-br from-amber-500/[0.08] to-orange-700/[0.04] p-5"
      aria-label="Minha Super Múltipla"
    >
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-white">Minha Super Múltipla</h2>
          <p className="mt-1 max-w-2xl text-xs text-slate-400">
            Monte 2+ pernas com odd ≥ {minLegOdd.toFixed(2)} para promo{" "}
            <span className="text-amber-200">+{(bonusPct * 100).toFixed(0)}% no retorno</span>.
            Validação Criar Aposta em tempo real.
          </p>
        </div>
        <label className="flex items-center gap-2 text-xs text-slate-300">
          Stake R$
          <input
            type="number"
            min={1}
            step={1}
            value={stake}
            onChange={(e) => setStake(Math.max(1, Number(e.target.value) || 1))}
            className="w-20 rounded-lg border border-white/10 bg-black/30 px-2 py-1 font-mono text-sm text-white"
          />
        </label>
      </div>

      {(data.superMultipla?.suggestedCombos.length ?? 0) > 0 && (
        <div className="mb-4 flex flex-wrap gap-2">
          {data.superMultipla!.suggestedCombos.slice(0, 3).map((combo, idx) => (
            <button
              key={combo.id}
              type="button"
              onClick={() => loadSuggestion(idx)}
              className="rounded-lg border border-white/10 bg-black/20 px-3 py-1.5 text-[10px] text-slate-300 transition hover:border-amber-400/40 hover:text-amber-100"
            >
              Sugestão #{idx + 1} @{combo.combinedOdd.toFixed(2)}
              {combo.productOdd != null && combo.productOdd > combo.combinedOdd + 0.01
                ? ` (≠ @${combo.productOdd.toFixed(2)})`
                : ""}
              {combo.bonusEligible ? " · +5%" : ""}
            </button>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            Mercados disponíveis
          </p>
          <ul className="max-h-52 space-y-1.5 overflow-y-auto pr-1">
            {pickPool.map((row) => {
              const selected = legs.some((leg) => legKey(leg) === `${row.market}:${row.outcome}`);
              return (
                <li key={`${row.market}-${row.outcome}`}>
                  <button
                    type="button"
                    disabled={selected}
                    onClick={() => addLeg(row)}
                    className="flex w-full items-center justify-between gap-2 rounded-lg border border-white/6 bg-black/20 px-3 py-2 text-left text-xs transition hover:border-amber-400/30 disabled:opacity-40"
                  >
                    <span className="truncate text-slate-200">{row.label}</span>
                    <span className="shrink-0 font-mono text-slate-400">@{row.marketOdd.toFixed(2)}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            Slip ({legs.length} perna{legs.length === 1 ? "" : "s"})
          </p>
          {legs.length === 0 ? (
            <p className="rounded-lg border border-dashed border-white/10 px-3 py-6 text-center text-xs text-slate-500">
              Adicione pernas ou use uma sugestão acima.
            </p>
          ) : (
            <ol className="space-y-1.5">
              {legs.map((leg) => (
                <li
                  key={leg.id ?? legKey(leg)}
                  className="flex items-center justify-between gap-2 rounded-lg border border-white/8 bg-black/25 px-3 py-2 text-xs"
                >
                  <span className="truncate text-slate-200">{leg.label}</span>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className="font-mono text-slate-400">@{leg.market_odd.toFixed(2)}</span>
                    <button
                      type="button"
                      onClick={() => removeLeg(legKey(leg))}
                      className="text-[10px] text-red-300 hover:text-red-200"
                    >
                      Remover
                    </button>
                  </div>
                </li>
              ))}
            </ol>
          )}

          <div className="mt-4 rounded-xl border border-white/8 bg-black/20 p-3">
            {!canCalculate ? (
              <p className="text-xs text-slate-500">Mínimo 2 pernas para calcular.</p>
            ) : isCalculating && !result ? (
              <p className="text-xs text-slate-400">Calculando…</p>
            ) : result ? (
              <>
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-mono text-lg font-bold text-white">
                    @{result.totalOdds.toFixed(2)}
                  </span>
                  {result.productOdds != null &&
                  result.productOdds > result.totalOdds + 0.01 ? (
                    <span className="font-mono text-xs text-slate-500 line-through">
                      @{result.productOdds.toFixed(2)} produto
                    </span>
                  ) : null}
                  {result.bonusEligible ? (
                    <span className="rounded-full border border-amber-400/40 bg-amber-500/15 px-2 py-0.5 text-[9px] font-semibold uppercase text-amber-200">
                      Super Múltipla +5%
                    </span>
                  ) : null}
                </div>
                <p className="mt-2 font-mono text-sm text-neon-green">
                  R$ {stake.toFixed(2)} → R$ {result.finalPayout.toFixed(2)}
                  {result.bonusEligible ? (
                    <span className="ml-1 text-xs text-slate-500 line-through">
                      R$ {result.potentialPayout.toFixed(2)}
                    </span>
                  ) : null}
                </p>
                {result.combinedProb != null ? (
                  <p className="mt-1 text-[10px] text-slate-500">
                    Hit est. {formatLongshotProbPct(result.combinedProb)}
                    {result.combinedEv != null ? ` · EV ${(result.combinedEv * 100).toFixed(1)}%` : ""}
                  </p>
                ) : null}
                {result.warnings.length > 0 && (
                  <ul className="mt-2 space-y-1 text-[10px] text-amber-200/90">
                    {result.warnings.map((w) => (
                      <li key={w}>⚠ {w}</li>
                    ))}
                  </ul>
                )}
              </>
            ) : null}
          </div>

          {result && legs.length >= 2 && (
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                disabled={creating}
                onClick={() => void createTicket()}
                className="rounded-md border border-violet-400/35 bg-violet-500/15 px-2.5 py-1 text-[10px] font-semibold text-violet-100 transition hover:bg-violet-500/25 disabled:opacity-50"
              >
                {creating ? "Enviando…" : "Criar bilhete"}
              </button>
              {proposal?.qualified ? (
                <SendComboProposalButton proposal={proposal} compact />
              ) : null}
            </div>
          )}
          {createFeedback && (
            <p className="mt-2 text-[10px] text-violet-200">{createFeedback}</p>
          )}
        </div>
      </div>
    </section>
  );
}
