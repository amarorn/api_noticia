interface ApiOfflineBannerProps {
  onRetry: () => void;
  onDismiss: () => void;
}

export function ApiOfflineBanner({ onRetry, onDismiss }: ApiOfflineBannerProps) {
  return (
    <div
      role="alert"
      className="mb-4 flex flex-col gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="min-w-0">
        <p className="text-sm font-medium text-amber-200">API offline</p>
        <p className="mt-0.5 text-xs text-amber-300/80">
          Inicie a API com{" "}
          <code className="rounded bg-black/20 px-1 py-0.5 font-mono text-[11px]">
            ./scripts/dev-api-stable.sh
          </code>{" "}
          e tente novamente.
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <button type="button" onClick={onRetry} className="btn-ghost text-xs">
          Tentar novamente
        </button>
        <button type="button" onClick={onDismiss} className="btn-ghost text-xs text-slate-400">
          Fechar
        </button>
      </div>
    </div>
  );
}
