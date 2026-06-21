import { useMemo, useState } from "react";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import {
  buildProfileCombos,
  COMBO_MIN_ODD_STEPS,
  COMBO_PROFILE_UI,
  COMBO_PROFILES,
  nearestMinOddStep,
  type ComboMinOddStep,
  type ComboProfileId,
} from "@/presentation/utils/comboProfiles";
import {
  formatLongshotComboTicket,
  formatLongshotProbPct,
  LONGSHOT_STAKE_BRL,
} from "@/presentation/utils/longshotCombos";
import {
  applySuperMultiplaBonus,
  type SuperMultiplaEnrichedCombo,
} from "@/presentation/utils/superMultipla";
import {
  sendSuperbetTicketToExtension,
  type SuperbetExtensionTicket,
} from "@/presentation/utils/superbetExtensionBridge";

interface LiveBestCombosPanelProps {
  data: SuperbetLiveAdvice;
}

function isHandicapLeg(market: string): boolean {
  return market.includes("hcap") || market.includes("_ah_");
}

function toExtensionTicket(
  combo: SuperMultiplaEnrichedCombo,
  data: SuperbetLiveAdvice,
  profileId: ComboProfileId,
): SuperbetExtensionTicket {
  return {
    id: combo.id,
    superbetEventId: data.superbetEventId,
    homeTeam: data.homeTeam,
    awayTeam: data.awayTeam,
    title: `${COMBO_PROFILES[profileId].label} #${combo.rank} · ${combo.legs.length} pernas`,
    stake: combo.stake,
    combinedOdd: combo.combinedOdd,
    potentialReturn: combo.bonusEligible ? combo.finalReturn : combo.potentialReturn,
    combinedProb: combo.combinedProb,
    bonusEligible: combo.bonusEligible,
    legs: combo.legs.map((leg) => ({
      market: leg.market,
      outcome: leg.outcome,
      label: leg.label,
      marketOdd: leg.marketOdd,
      modelProb: leg.modelProb,
    })),
    source: "longshot",
  };
}

function ProfileComboCard({
  combo,
  data,
  profileId,
}: {
  combo: SuperMultiplaEnrichedCombo;
  data: SuperbetLiveAdvice;
  profileId: ComboProfileId;
}) {
  const ui = COMBO_PROFILE_UI[profileId];
  const [copied, setCopied] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createFeedback, setCreateFeedback] = useState<string | null>(null);

  const copyTicket = async () => {
    try {
      await navigator.clipboard.writeText(formatLongshotComboTicket(combo));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    } catch {
      setCopied(false);
    }
  };

  const createTicket = async () => {
    setCreating(true);
    setCreateFeedback(null);
    const result = await sendSuperbetTicketToExtension(
      toExtensionTicket(combo, data, profileId),
    );
    setCreating(false);
    if (result.ok) {
      setCreateFeedback("Enviado à extensão — aba Superbet aberta.");
    } else {
      setCreateFeedback(result.error ?? "Falha ao enviar à extensão.");
    }
    window.setTimeout(() => setCreateFeedback(null), 8000);
  };

  return (
    <article className={`rounded-xl border p-4 ${ui.cardClass}`}>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
            #{combo.rank} · {combo.legs.length} pernas
          </p>
          {combo.bonusEligible ? (
            <span className="mt-1 inline-block rounded-full border border-amber-400/40 bg-amber-500/15 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-amber-200">
              Super Múltipla +5%
            </span>
          ) : null}
          <p className="mt-1 font-mono text-lg font-bold text-white">
            R$ {combo.stake.toFixed(2)}{" "}
            <span className="text-slate-400">→</span>{" "}
            <span className="text-neon-green">
              R$ {(combo.bonusEligible ? combo.finalReturn : combo.potentialReturn).toFixed(2)}
            </span>
            {combo.bonusEligible ? (
              <span className="ml-1 text-xs font-normal text-slate-500 line-through">
                R$ {combo.potentialReturn.toFixed(2)}
              </span>
            ) : null}
          </p>
        </div>
        <div className="text-right">
          <span
            className={`inline-block rounded-full border px-2.5 py-1 font-mono text-sm ${ui.badgeClass}`}
          >
            @{combo.combinedOdd.toFixed(2)}
          </span>
          {combo.productOdd != null && combo.productOdd > combo.combinedOdd + 0.01 ? (
            <p className="mt-0.5 font-mono text-[10px] text-slate-500 line-through">
              @{combo.productOdd.toFixed(2)} produto
            </p>
          ) : null}
          <p className="mt-1 text-[10px] font-medium text-neon-green">
            Hit {formatLongshotProbPct(combo.combinedProb)}
          </p>
        </div>
      </div>

      <ol className="space-y-1.5">
        {combo.legs.map((leg) => (
          <li
            key={`${leg.market}-${leg.outcome}`}
            className="rounded-lg border border-white/6 bg-black/20 px-3 py-2"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-2 text-xs">
              <span className="text-slate-200">
                {isHandicapLeg(leg.market) && (
                  <span className="mr-1.5 rounded bg-violet-500/20 px-1 py-0.5 text-[9px] font-semibold uppercase text-violet-200">
                    HC
                  </span>
                )}
                {leg.label}
              </span>
              <span className="font-mono text-slate-300">@{leg.marketOdd.toFixed(2)}</span>
            </div>
            <p className="mt-0.5 text-[10px] text-slate-500">
              Modelo {formatLongshotProbPct(leg.modelProb)}
            </p>
          </li>
        ))}
      </ol>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500">
        <span>
          EV {(combo.combinedEv * 100).toFixed(1)}% · prob. cruzada{" "}
          {formatLongshotProbPct(combo.combinedProb)}
        </span>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={creating}
            onClick={() => void createTicket()}
            className="rounded-md border border-violet-400/35 bg-violet-500/15 px-2.5 py-1 text-[10px] font-semibold text-violet-100 transition hover:bg-violet-500/25 disabled:opacity-50"
          >
            {creating ? "Enviando…" : "Criar bilhete"}
          </button>
          <button
            type="button"
            onClick={() => void copyTicket()}
            className="rounded-md border border-white/10 px-2 py-1 text-[10px] font-medium text-slate-300 transition hover:border-white/25 hover:text-white"
          >
            {copied ? "Copiado ✓" : "Copiar"}
          </button>
        </div>
      </div>
      {createFeedback && (
        <p className="mt-2 text-[10px] text-violet-200">{createFeedback}</p>
      )}
    </article>
  );
}

export function LiveBestCombosPanel({ data }: LiveBestCombosPanelProps) {
  const [profileId, setProfileId] = useState<ComboProfileId>("balanced");
  const [minOdd, setMinOdd] = useState<ComboMinOddStep>(
    COMBO_PROFILES.balanced.defaultMinOdd,
  );

  const activeProfile = COMBO_PROFILES[profileId];

  const combos = useMemo(
    () =>
      buildProfileCombos(data.strategy?.marketScan, profileId, {
        minCombinedOdd: minOdd,
        halfMarkets: data.halfMarkets,
        superbetEventId: data.superbetEventId,
      }).map(applySuperMultiplaBonus),
    [data.strategy?.marketScan, data.halfMarkets, data.superbetEventId, profileId, minOdd],
  );

  const selectProfile = (id: ComboProfileId) => {
    setProfileId(id);
    setMinOdd(COMBO_PROFILES[id].defaultMinOdd);
  };

  if (data.isFinished) return null;

  const sliderIndex = COMBO_MIN_ODD_STEPS.indexOf(minOdd);
  const effectiveSliderIndex = sliderIndex >= 0 ? sliderIndex : 0;

  return (
    <section
      className="rounded-2xl border border-white/10 bg-white/[0.02] p-5"
      aria-label="Melhor combo por perfil"
    >
      <div className="mb-4">
        <h2 className="text-base font-semibold text-white">Melhor combo</h2>
        <p className="mt-1 max-w-3xl text-xs leading-relaxed text-slate-400">
          Cruza <span className="text-emerald-300">probabilidade do modelo × odd Superbet</span> em
          pernas compatíveis (Criar Aposta). Escolha o perfil e o patamar mínimo de odd combinada.
        </p>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {(Object.keys(COMBO_PROFILES) as ComboProfileId[]).map((id) => {
          const profile = COMBO_PROFILES[id];
          const ui = COMBO_PROFILE_UI[id];
          const active = profileId === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => selectProfile(id)}
              className={`rounded-xl border px-3 py-2 text-left transition ${
                active ? ui.activeTabClass : ui.tabClass
              }`}
            >
              <span className="block text-sm font-semibold">{profile.label}</span>
              <span className="mt-0.5 block text-[10px] opacity-80">{profile.hint}</span>
            </button>
          );
        })}
      </div>

      <div className="mb-5 rounded-xl border border-white/8 bg-black/20 px-4 py-3">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <label htmlFor="combo-min-odd" className="text-xs font-medium text-slate-300">
            Odd combinada mínima
          </label>
          <span className="font-mono text-sm font-bold text-white">@{minOdd.toFixed(0)}+</span>
        </div>
        <input
          id="combo-min-odd"
          type="range"
          min={0}
          max={COMBO_MIN_ODD_STEPS.length - 1}
          step={1}
          value={effectiveSliderIndex}
          onChange={(e) => {
            const step = COMBO_MIN_ODD_STEPS[Number(e.target.value)] ?? minOdd;
            setMinOdd(step);
          }}
          className="h-2 w-full cursor-pointer appearance-none rounded-full bg-white/10 accent-violet-400"
        />
        <div className="mt-2 flex justify-between text-[10px] text-slate-600">
          {COMBO_MIN_ODD_STEPS.map((step) => (
            <button
              key={step}
              type="button"
              onClick={() => setMinOdd(step)}
              className={`rounded px-1 py-0.5 transition hover:text-slate-300 ${
                minOdd === step ? "font-semibold text-violet-300" : ""
              }`}
            >
              @{step}
            </button>
          ))}
        </div>
        {activeProfile.maxCombinedOdd != null && (
          <p className="mt-2 text-[10px] text-slate-500">
            Perfil {activeProfile.label}: odd até @{activeProfile.maxCombinedOdd} · stake padrão R${" "}
            {LONGSHOT_STAKE_BRL}
          </p>
        )}
      </div>

      {combos.length === 0 ? (
        <p className="text-xs text-slate-500">
          Nenhuma múltipla compatível com @{minOdd}+ neste refresh. Tente perfil{" "}
          <button
            type="button"
            onClick={() => selectProfile("safe")}
            className="text-emerald-300 underline-offset-2 hover:underline"
          >
            Seguro
          </button>{" "}
          ou reduza a odd mínima.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {combos.map((combo) => (
            <ProfileComboCard
              key={`${profileId}-${combo.id}`}
              combo={combo}
              data={data}
              profileId={profileId}
            />
          ))}
        </div>
      )}

      <p className="mt-3 text-[10px] leading-relaxed text-slate-600">
        Probabilidades tratadas como independentes. Odd mínima atual: @
        {nearestMinOddStep(minOdd)} · ordenação:{" "}
        {activeProfile.sortBy === "prob"
          ? "maior chance"
          : activeProfile.sortBy === "ev"
            ? "maior EV"
            : "equilíbrio"}
        .
      </p>
    </section>
  );
}
