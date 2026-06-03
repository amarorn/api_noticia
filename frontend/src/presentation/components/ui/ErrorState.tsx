import type { ReactNode } from "react";

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export function ErrorState({
  title = "Algo deu errado",
  message,
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="glass-card flex flex-col items-center gap-4 p-8 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-red-500/10 text-2xl text-red-400">
        !
      </div>
      <div>
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <p className="mt-1 max-w-md text-sm text-slate-400">{message}</p>
      </div>
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn-primary">
          Tentar novamente
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/[0.06]">
      <img
        src="/images/empty-state-ball.png"
        alt=""
        aria-hidden="true"
        className="absolute inset-0 h-full w-full object-cover object-center opacity-20"
        draggable={false}
      />
      <div className="relative flex flex-col items-center gap-3 p-12 text-center">
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <p className="max-w-sm text-sm text-slate-400">{description}</p>
        {action}
      </div>
    </div>
  );
}
