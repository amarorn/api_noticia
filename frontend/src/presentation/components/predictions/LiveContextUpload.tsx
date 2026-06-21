import { useRef, useState } from "react";
import { IconUpload, IconX, IconCheck, IconInfo } from "@/presentation/components/ui/Icons";

const API_BASE = import.meta.env.VITE_API_URL ?? "/api";
const API_KEY = import.meta.env.VITE_API_KEY?.trim() || undefined;

type ContextNote = string;

type UploadState =
  | { type: "idle" }
  | { type: "uploading" }
  | { type: "success"; notes: ContextNote[]; filename: string }
  | { type: "error"; message: string };

type ActiveContext = {
  source_filename?: string;
  referee_name?: string;
  referee_card_lambda?: number;
  home_pregame_xg?: number;
  away_pregame_xg?: number;
  h2h_avg_goals?: number;
  notes?: string[];
};

interface Props {
  eventId: number;
  activeContext: ActiveContext | null;
  onContextChanged?: () => void;
}

export function LiveContextUpload({ eventId, activeContext, onContextChanged }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<UploadState>({ type: "idle" });
  const [expanded, setExpanded] = useState(false);

  async function handleFile(file: File) {
    setState({ type: "uploading" });
    try {
      const form = new FormData();
      form.append("file", file);

      const res = await fetch(`${API_BASE}/worldcup/superbet/live/${eventId}/context`, {
        method: "POST",
        headers: API_KEY ? { "X-API-Key": API_KEY } : {},
        body: form,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `Erro ${res.status}`);
      }

      const data = await res.json();
      setState({ type: "success", notes: data.notes ?? [], filename: file.name });
      onContextChanged?.();
    } catch (err) {
      setState({ type: "error", message: err instanceof Error ? err.message : String(err) });
    }
  }

  async function handleRemove() {
    await fetch(`${API_BASE}/worldcup/superbet/live/${eventId}/context`, {
      method: "DELETE",
      headers: API_KEY ? { "X-API-Key": API_KEY } : {},
    });
    setState({ type: "idle" });
    onContextChanged?.();
  }

  const hasContext = activeContext != null;

  return (
    <div className="rounded-xl border border-zinc-700 bg-zinc-900 p-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <IconInfo className="h-4 w-4 text-blue-400 shrink-0" />
          <span className="text-sm font-medium text-zinc-200">Análise pré-jogo</span>
          {hasContext && (
            <span className="rounded-full bg-blue-500/20 px-2 py-0.5 text-xs font-semibold text-blue-300">
              ativo
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          {hasContext && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="rounded px-2 py-1 text-xs text-zinc-400 hover:text-zinc-200"
            >
              {expanded ? "fechar" : "ver dados"}
            </button>
          )}
          {hasContext ? (
            <button
              onClick={handleRemove}
              title="Remover contexto"
              className="rounded p-1 text-zinc-500 hover:text-red-400"
            >
              <IconX className="h-4 w-4" />
            </button>
          ) : (
            <button
              onClick={() => inputRef.current?.click()}
              disabled={state.type === "uploading"}
              className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-500 disabled:opacity-50"
            >
              <IconUpload className="h-3.5 w-3.5" />
              {state.type === "uploading" ? "Enviando…" : "Subir análise"}
            </button>
          )}
        </div>
      </div>

      {/* Status do upload */}
      {state.type === "success" && !hasContext && (
        <div className="mt-2 flex items-start gap-2 rounded-lg bg-green-500/10 p-2 text-xs text-green-300">
          <IconCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            <strong>{state.filename}</strong> processado com {state.notes.length} enriquecimento(s).
          </span>
        </div>
      )}

      {state.type === "error" && (
        <div className="mt-2 rounded-lg bg-red-500/10 p-2 text-xs text-red-400">
          {state.message}
        </div>
      )}

      {/* Contexto ativo — detalhes expandidos */}
      {hasContext && expanded && (
        <div className="mt-3 space-y-2 border-t border-zinc-700 pt-3">
          {activeContext.source_filename && (
            <p className="text-xs text-zinc-500">
              Arquivo: <span className="text-zinc-300">{activeContext.source_filename}</span>
            </p>
          )}
          <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
            {activeContext.referee_name && (
              <>
                <span className="text-zinc-500">Árbitro</span>
                <span className="text-zinc-200">{activeContext.referee_name}</span>
              </>
            )}
            {activeContext.referee_card_lambda != null && (
              <>
                <span className="text-zinc-500">Amarelos/jogo (árbitro)</span>
                <span className="font-semibold text-amber-300">
                  {activeContext.referee_card_lambda.toFixed(2)}
                </span>
              </>
            )}
            {activeContext.home_pregame_xg != null && (
              <>
                <span className="text-zinc-500">xG casa</span>
                <span className="text-zinc-200">{activeContext.home_pregame_xg.toFixed(2)}</span>
              </>
            )}
            {activeContext.away_pregame_xg != null && (
              <>
                <span className="text-zinc-500">xG fora</span>
                <span className="text-zinc-200">{activeContext.away_pregame_xg.toFixed(2)}</span>
              </>
            )}
            {activeContext.h2h_avg_goals != null && (
              <>
                <span className="text-zinc-500">Média gols H2H</span>
                <span className="text-zinc-200">{activeContext.h2h_avg_goals.toFixed(1)}</span>
              </>
            )}
          </div>
          {activeContext.notes && activeContext.notes.length > 0 && (
            <ul className="mt-1 space-y-1 text-xs text-blue-300">
              {activeContext.notes.map((n, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <span className="mt-px text-blue-500">•</span>
                  {n}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Dica quando não há contexto */}
      {!hasContext && state.type === "idle" && (
        <p className="mt-1.5 text-xs text-zinc-500">
          Suba um .txt com estatísticas do jogo para enriquecer o modelo (árbitro, xG, H2H…)
        </p>
      )}

      <input
        ref={inputRef}
        type="file"
        accept=".txt,.md"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
          e.target.value = "";
        }}
      />
    </div>
  );
}
