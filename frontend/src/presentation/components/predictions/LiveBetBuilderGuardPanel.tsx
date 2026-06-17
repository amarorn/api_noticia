import type { SuperbetLiveAdvice } from "@/domain/entities";

type BetGuardrails = NonNullable<SuperbetLiveAdvice["betGuardrails"]>;

interface LiveBetBuilderGuardPanelProps {
  guardrails: BetGuardrails | null | undefined;
}

function severityClass(severity: string | undefined): string {
  if (severity === "critical") return "border-red-500/40 bg-red-500/10 text-red-100";
  if (severity === "high") return "border-amber-500/40 bg-amber-500/10 text-amber-100";
  return "border-slate-500/30 bg-slate-500/10 text-slate-200";
}

export function LiveBetBuilderGuardPanel({ guardrails }: LiveBetBuilderGuardPanelProps) {
  if (!guardrails?.enabled) return null;

  const traps = guardrails.htTrapWarnings ?? [];
  const rules = guardrails.betBuilderRules ?? [];
  if (traps.length === 0 && rules.length === 0) return null;

  return (
    <section
      className="rounded-2xl border border-violet-500/30 bg-violet-500/5 px-4 py-3"
      aria-label="Proteção Criar Aposta e over 1T"
    >
      <p className="text-xs font-bold uppercase tracking-wider text-violet-300">
        Criar Aposta — evite armadilhas
      </p>

      {traps.length > 0 && (
        <ul className="mt-3 space-y-2">
          {traps.map((trap, idx) => (
            <li
              key={`${trap.code}-${idx}`}
              className={`rounded-xl border px-3 py-2 text-sm ${severityClass(trap.severity)}`}
            >
              <p className="font-semibold">{trap.title}</p>
              <p className="mt-1 text-xs opacity-90">{trap.reason}</p>
            </li>
          ))}
        </ul>
      )}

      {rules.length > 0 && (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-slate-400">
          {rules.map((rule) => (
            <li key={rule}>{rule}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default LiveBetBuilderGuardPanel;
