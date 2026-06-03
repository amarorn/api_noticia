import { useElapsedSeconds } from "@/presentation/hooks/useElapsedSeconds";

interface SlowLoadingPanelProps {
  active: boolean;
  title: string;
  hint?: string;
  steps?: string[];
}

export function SlowLoadingPanel({
  active,
  title,
  hint = "Na primeira carga após subir a API, o treino dos modelos pode levar até 2 minutos.",
  steps = [
    "Carregando histórico de jogos",
    "Estimando parâmetros Dixon-Coles",
    "Montando ensemble de palpites",
  ],
}: SlowLoadingPanelProps) {
  const elapsed = useElapsedSeconds(active);
  if (!active) return null;

  const stepIndex = Math.min(Math.floor(elapsed / 25), steps.length - 1);

  return (
    <div
      className="glass-card mb-6 space-y-4 border-neon-blue/20 bg-neon-blue/5 p-5"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-display text-sm font-semibold text-white">{title}</p>
          <p className="mt-1 text-xs text-slate-400">{hint}</p>
        </div>
        <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 font-mono text-xs text-neon-blue">
          {elapsed}s
        </span>
      </div>

      <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
        <div
          className="h-full rounded-full bg-gradient-to-r from-neon-green to-neon-blue transition-all duration-1000 ease-out"
          style={{ width: `${Math.min(92, 12 + elapsed * 1.4)}%` }}
        />
      </div>

      <p className="text-xs text-slate-500">
        <span className="text-neon-green">{steps[stepIndex]}</span>
        {elapsed > 60 && " — ainda processando, aguarde…"}
      </p>
    </div>
  );
}
