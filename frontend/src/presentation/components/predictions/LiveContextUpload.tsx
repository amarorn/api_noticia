import { useRef, useState } from "react";
import { IconUpload, IconX, IconCheck, IconInfo } from "@/presentation/components/ui/Icons";

const API_BASE = import.meta.env.VITE_API_URL ?? "/api";
const API_KEY = import.meta.env.VITE_API_KEY?.trim() || undefined;

type ContextNote = string;

type UploadState =
  | { type: "idle" }
  | { type: "uploading" }
  | { type: "fetching" }
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
  perplexity_citations?: string[];
};

interface Props {
  eventId: number;
  homeTeam?: string;
  awayTeam?: string;
  activeContext: ActiveContext | null;
  onContextChanged?: () => void;
}

export function LiveContextUpload({ eventId, homeTeam, awayTeam, activeContext, onContextChanged }: Props) {
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

  async function handleFetchPerplexity(forceRefresh = false) {
    if (!homeTeam || !awayTeam) return;
    setState({ type: "fetching" });
    try {
      const qs = new URLSearchParams({
        home_team: homeTeam,
        away_team: awayTeam,
        ...(forceRefresh ? { force_refresh: "true" } : {}),
      });
      const res = await fetch(
        `${API_BASE}/worldcup/superbet/live/${eventId}/fetch-context?${qs}`,
        {
          method: "POST",
          headers: API_KEY ? { "X-API-Key": API_KEY } : {},
        },
      );

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `Erro ${res.status}`);
      }

      const data = await res.json();
      setState({
        type: "success",
        notes: data.notes ?? [],
        filename: "Perplexity",
      });
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
  const isBusy = state.type === "uploading" || state.type === "fetching";
  const canPerplexity = !!(homeTeam && awayTeam);

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
          {activeContext?.perplexity_citations && activeContext.perplexity_citations.length > 0 && (
            <span className="rounded-full bg-purple-500/20 px-2 py-0.5 text-[10px] font-semibold text-purple-300">
              Perplexity
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
            <>
              {canPerplexity && (
                <button
                  onClick={() => handleFetchPerplexity(true)}
                  disabled={isBusy}
                  title="Atualizar via Perplexity"
                  className="rounded px-2 py-1 text-[10px] text-purple-400 hover:text-purple-200 disabled:opacity-40"
                >
                  {state.type === "fetching" ? "buscando…" : "↻ atualizar"}
                </button>
              )}
              <button
                onClick={handleRemove}
                title="Remover contexto"
                className="rounded p-1 text-zinc-500 hover:text-red-400"
              >
                <IconX className="h-4 w-4" />
              </button>
            </>
          ) : (
            <div className="flex items-center gap-1.5">
              {canPerplexity && (
                <button
                  onClick={() => handleFetchPerplexity()}
                  disabled={isBusy}
                  className="flex items-center gap-1.5 rounded-lg bg-purple-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-purple-600 disabled:opacity-50"
                >
                  {state.type === "fetching" ? (
                    <>
                      <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                      Buscando…
                    </>
                  ) : (
                    "✦ Auto-buscar"
                  )}
                </button>
              )}
              <button
                onClick={() => inputRef.current?.click()}
                disabled={isBusy}
                title="Subir análise manualmente"
                className="flex items-center gap-1.5 rounded-lg border border-zinc-600 bg-zinc-800 px-2.5 py-1.5 text-xs text-zinc-300 hover:bg-zinc-700 disabled:opacity-50"
              >
                <IconUpload className="h-3.5 w-3.5" />
                {state.type === "uploading" ? "Enviando…" : "Subir .txt"}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Status */}
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
              Fonte: <span className="text-zinc-300">{activeContext.source_filename}</span>
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
          {activeContext.perplexity_citations && activeContext.perplexity_citations.length > 0 && (
            <div className="mt-2 space-y-0.5">
              <p className="text-[10px] text-zinc-600">Fontes Perplexity:</p>
              {activeContext.perplexity_citations.slice(0, 3).map((url, i) => (
                <a
                  key={i}
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block truncate text-[10px] text-purple-400 hover:text-purple-300"
                >
                  {url}
                </a>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Dica quando não há contexto */}
      {!hasContext && state.type === "idle" && (
        <p className="mt-1.5 text-xs text-zinc-500">
          {canPerplexity
            ? "Busca automática de árbitro, forma, H2H e xG via Perplexity."
            : "Suba um .txt com estatísticas do jogo para enriquecer o modelo."}
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
