import { useMemo, useState } from "react";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import {
  buildLongshotCombos,
  formatLongshotComboTicket,
  formatLongshotProbPct,
  LONGSHOT_MIN_RETURN_BRL,
  LONGSHOT_STAKE_BRL,
  LONGSHOT_TIER_CONFIG,
  type LongshotCombo,
} from "@/presentation/utils/longshotCombos";

function isHandicapLeg(market: string): boolean {
  return market.includes("hcap") || market.includes("_ah_");
}
import {
  sendSuperbetTicketToExtension,
  type SuperbetExtensionTicket,
} from "@/presentation/utils/superbetExtensionBridge";

interface LiveLongshotCombosPanelProps {
  data: SuperbetLiveAdvice;
}

function toExtensionTicket(combo: LongshotCombo, data: SuperbetLiveAdvice): SuperbetExtensionTicket {
  return {
    id: combo.id,
    superbetEventId: data.superbetEventId,
    homeTeam: data.homeTeam,
    awayTeam: data.awayTeam,
    title: `Longshot #${combo.rank} · ${combo.legs.length} pernas`,
    stake: combo.stake,
    combinedOdd: combo.combinedOdd,
    potentialReturn: combo.potentialReturn,
    combinedProb: combo.combinedProb,
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

function ComboCard({
  combo,
  data,
}: {
  combo: LongshotCombo;
  data: SuperbetLiveAdvice;
}) {
  const [copied, setCopied] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createFeedback, setCreateFeedback] = useState<string | null>(null);
  const tier = LONGSHOT_TIER_CONFIG[combo.riskTier];

  const copyTicket = async () => {
    const text = formatLongshotComboTicket(combo);
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    } catch {
      setCopied(false);
    }
  };

  const createTicket = async () => {
    setCreating(true);
    setCreateFeedback(null);
    const result = await sendSuperbetTicketToExtension(toExtensionTicket(combo, data));
    setCreating(false);
    if (result.ok) {
      setCreateFeedback("Enviado à extensão — aba Superbet aberta.");
    } else {
      setCreateFeedback(result.error ?? "Falha ao enviar à extensão.");
    }
    window.setTimeout(() => setCreateFeedback(null), 8000);
  };

  return (
    <article className={`rounded-xl border p-4 ${tier.cardClass}`}>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className={`text-[10px] font-semibold uppercase tracking-wide ${tier.accentClass}`}>
              #{combo.rank} · {combo.legs.length} pernas
            </p>
            <span
              className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide ${tier.badgeClass}`}
            >
              {tier.label}
            </span>
          </div>
          <p className="mt-1 font-mono text-lg font-bold text-white">
            R$ {combo.stake.toFixed(2)}{" "}
            <span className="text-slate-400">→</span>{" "}
            <span className="text-neon-green">R$ {combo.potentialReturn.toFixed(2)}</span>
          </p>
          <p className="mt-1 text-[10px] text-slate-500">{tier.hint}</p>
        </div>
        <div className="text-right">
          <span
            className={`inline-block rounded-full border px-2.5 py-1 font-mono text-sm ${tier.badgeClass}`}
          >
            @{combo.combinedOdd.toFixed(2)}
          </span>
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
              <span className={`font-mono ${tier.oddClass}`}>@{leg.marketOdd.toFixed(2)}</span>
            </div>
            <p className="mt-0.5 text-[10px] text-slate-500">
              Modelo {formatLongshotProbPct(leg.modelProb)}
            </p>
          </li>
        ))}
      </ol>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500">
        <span>
          Prob. cruzada {formatLongshotProbPct(combo.combinedProb)} · EV{" "}
          {(combo.combinedEv * 100).toFixed(1)}%
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

export function LiveLongshotCombosPanel({ data }: LiveLongshotCombosPanelProps) {
  const combos = useMemo(
    () => buildLongshotCombos(data.strategy?.marketScan),
    [data.strategy?.marketScan],
  );

  if (data.isFinished || combos.length === 0) return null;

  return (
    <section
      className="rounded-2xl border border-white/10 bg-white/[0.02] p-5"
      aria-label="Combinações longshot"
    >
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-white">
            Longshot — R$ {LONGSHOT_STAKE_BRL} para ganhar R$ {LONGSHOT_MIN_RETURN_BRL}+
          </h2>
          <p className="mt-1 max-w-2xl text-xs leading-relaxed text-slate-400">
            Cruzamento{" "}
            <span className="text-emerald-300">probabilidade do modelo × odd Superbet</span>.
            Ordenado da <strong className="text-white">maior chance</strong> para a menor — cards
            verdes = menor risco entre as opções @{(LONGSHOT_MIN_RETURN_BRL / LONGSHOT_STAKE_BRL).toFixed(0)}+.
            Handicap não entra junto com vitória 1X2 ou gols do mesmo time (regra do Criar Aposta).
          </p>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-2 text-[10px]">
        {(Object.entries(LONGSHOT_TIER_CONFIG) as Array<[keyof typeof LONGSHOT_TIER_CONFIG, typeof LONGSHOT_TIER_CONFIG.best]>).map(
          ([key, cfg]) => (
            <span
              key={key}
              className={`rounded-full border px-2.5 py-1 font-medium ${cfg.badgeClass}`}
            >
              {cfg.label}
            </span>
          ),
        )}
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {combos.map((combo) => (
          <ComboCard key={combo.id} combo={combo} data={data} />
        ))}
      </div>

      <p className="mt-3 text-[10px] leading-relaxed text-slate-600">
        Só mercados do Criar Aposta Superbet; no máximo um RC por combo; BTTS não combina
        com Resultado Correto; 2T 0x0 + 2T 1x0 são mutuamente exclusivos.
      </p>
    </section>
  );
}
