import { useMutation } from "@tanstack/react-query";
import {
  walletRepository,
  type WalletSyncStatus,
} from "@/infrastructure/repositories/walletRepository";

function formatDaysSince(days: number | null): string {
  if (days === null) return "";
  if (days < 1) return "hoje";
  if (days < 2) return "1 dia";
  return `${Math.floor(days)} dias`;
}

function formatLastUpload(iso: string | null): string {
  if (!iso) return "nunca";
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

interface WalletSyncBannerProps {
  status: WalletSyncStatus;
  onImportSuccess: () => void;
}

export function WalletSyncBanner({ status, onImportSuccess }: WalletSyncBannerProps) {
  const importMut = useMutation({
    mutationFn: () => walletRepository.importInbox(status.user_id),
    onSuccess: () => onImportSuccess(),
  });

  const hasPending = status.n_pending > 0;
  const isStale = status.stale;
  const neverUploaded = status.n_uploads === 0 && status.last_upload_at === null;

  if (!status.inbox_enabled) return null;
  if (!hasPending && !isStale && !neverUploaded) return null;

  const tone = hasPending ? "emerald" : "amber";
  const border =
    tone === "emerald"
      ? "border-emerald-500/30 bg-emerald-500/10"
      : "border-amber-500/30 bg-amber-500/10";
  const titleColor = tone === "emerald" ? "text-emerald-200" : "text-amber-200";
  const bodyColor = tone === "emerald" ? "text-emerald-300/85" : "text-amber-300/85";

  let title = "CSV desatualizado";
  let body = "";

  if (hasPending) {
    title = `${status.n_pending} CSV na inbox pronto para importar`;
    body = `Arquivos: ${status.pending_csv_files.join(", ")}. Clique em importar ou arraste mais exports para:`;
  } else if (neverUploaded) {
    title = "Nenhum CSV importado ainda";
    body =
      "Exporte o extrato na Superbet e envie pelo dropzone abaixo, ou salve na pasta inbox para importação automática:";
  } else if (isStale) {
    title = `CSV desatualizado — último upload há ${formatDaysSince(status.days_since_upload)}`;
    body = `Último envio: ${formatLastUpload(status.last_upload_at)} (limite: ${status.stale_threshold_days} dias). Exporte um CSV novo na Superbet e salve em:`;
  }

  const importLabel = hasPending
    ? importMut.isPending
      ? "Importando..."
      : "Importar da inbox"
    : importMut.isPending
      ? "Verificando..."
      : "Verificar pasta inbox";

  return (
    <div
      role="alert"
      className={`flex flex-col gap-3 rounded-xl border px-4 py-3 sm:flex-row sm:items-start sm:justify-between ${border}`}
    >
      <div className="min-w-0 space-y-1">
        <p className={`text-sm font-medium ${titleColor}`}>{title}</p>
        <p className={`text-xs ${bodyColor}`}>{body}</p>
        <code className="mt-1 block truncate rounded bg-black/20 px-2 py-1 font-mono text-[11px] text-slate-300">
          {status.inbox_dir}/
        </code>
        {importMut.isError && (
          <p className="text-xs text-red-400">{(importMut.error as Error).message}</p>
        )}
        {importMut.isSuccess && (
          <p className="text-xs text-emerald-400">
            {importMut.data.n_imported > 0
              ? `Importados ${importMut.data.n_imported} arquivo(s)`
              : "Nenhum CSV novo na pasta"}
            {importMut.data.reconciliation?.n_pairs
              ? ` · ${importMut.data.reconciliation.n_pairs} pares reconciliados`
              : ""}
          </p>
        )}
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => importMut.mutate()}
          disabled={importMut.isPending}
          className={`rounded-lg border px-3 py-1.5 text-xs font-medium disabled:opacity-50 ${
            hasPending
              ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-200 hover:bg-emerald-500/25"
              : "border-amber-500/40 bg-amber-500/15 text-amber-200 hover:bg-amber-500/25"
          }`}
        >
          {importLabel}
        </button>
      </div>
    </div>
  );
}
