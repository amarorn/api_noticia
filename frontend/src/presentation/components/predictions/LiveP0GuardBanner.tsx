import type { SuperbetLiveAdvice } from "@/domain/entities";

type BetGuardrails = NonNullable<SuperbetLiveAdvice["betGuardrails"]>;

interface LiveP0GuardBannerProps {
  guardrails: BetGuardrails | null | undefined;
}

export function LiveP0GuardBanner({ guardrails }: LiveP0GuardBannerProps) {
  if (!guardrails?.enabled) return null;

  const blockFt = guardrails.blockNewBets;
  const blockAll = blockFt && guardrails.blockNewBets2h;
  const allow2h = guardrails.allow2hSuggestions;
  const palpite = guardrails.pregamePalpite ?? guardrails.inplayPalpite;

  return (
    <section
      className={`rounded-2xl border px-4 py-3 ${
        blockAll
          ? "border-red-500/50 bg-red-500/10"
          : blockFt
            ? "border-amber-500/30 bg-amber-500/5"
            : "border-amber-500/30 bg-amber-500/5"
      }`}
      aria-label="Regras operacionais P0"
    >
      <p
        className={`text-xs font-bold uppercase tracking-wider ${
          blockAll ? "text-red-300" : "text-amber-300"
        }`}
      >
        Regras P0 — proteção de banca
      </p>
      <ul className="mt-2 space-y-1.5 text-sm text-slate-300">
        {blockAll ? (
          <li className="font-semibold text-red-200">
            ⛔ Apostas novas bloqueadas após {guardrails.block2hMinute}&apos; — use apenas
            cash-out.
          </li>
        ) : blockFt && allow2h ? (
          <li className="font-semibold text-amber-200">
            ⚠ Mercados FT bloqueados após {guardrails.blockMinute}&apos; — sugestões limitadas
            ao 2º tempo até {guardrails.block2hMinute}&apos;.
          </li>
        ) : blockFt ? (
          <li className="font-semibold text-red-200">
            ⛔ Apostas novas bloqueadas após {guardrails.blockMinute}&apos;.
          </li>
        ) : (
          <li>
            ✓ Entradas FT permitidas antes de {guardrails.blockMinute}&apos;.
          </li>
        )}
        {guardrails.oneBetPerMarket && (
          <li>✓ Máximo 1 bilhete por mercado por jogo (sem duplicar RF no mesmo palpite).</li>
        )}
        {palpite && (
          <li>
            ✓ Palpite do modelo:{" "}
            <span className="font-mono font-bold text-white">{palpite}</span>
            {guardrails.pregameProb != null && (
              <span className="text-slate-400">
                {" "}
                ({(guardrails.pregameProb * 100).toFixed(0)}% pré-jogo)
              </span>
            )}
            — não aposte contra.
          </li>
        )}
      </ul>
      {guardrails.blockReason && (
        <p
          className={`mt-2 text-xs ${blockAll ? "text-red-200/80" : "text-amber-200/80"}`}
        >
          {guardrails.blockReason}
        </p>
      )}
    </section>
  );
}

export default LiveP0GuardBanner;
