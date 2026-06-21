import { useState } from "react";
import type { TicketLeg, TicketStore } from "@/presentation/hooks/useTicket";

// ── Helpers ───────────────────────────────────────────────────────────────────

export function confBadge(c: string) {
  if (c === "Alta") return "bg-emerald-500/20 text-emerald-300 border-emerald-500/40";
  if (c === "Média") return "bg-blue-500/20 text-blue-300 border-blue-500/40";
  return "bg-neutral-700/40 text-neutral-400 border-neutral-600/30";
}

export function kickoffTime(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString("pt-BR", {
      hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo",
    });
  } catch { return ""; }
}

// ── Add to ticket button ──────────────────────────────────────────────────────

export function AddBtn({ leg, ticket }: { leg: TicketLeg; ticket: TicketStore }) {
  const added = ticket.has(leg.id);
  return (
    <button
      onClick={e => { e.stopPropagation(); added ? ticket.remove(leg.id) : ticket.add(leg); }}
      title={added ? "Remover do bilhete" : "Adicionar ao bilhete"}
      className={`shrink-0 flex items-center justify-center h-7 w-7 rounded-lg text-sm font-bold transition-all ${
        added
          ? "bg-emerald-500/30 border border-emerald-500/60 text-emerald-300 hover:bg-red-900/40 hover:border-red-500/40 hover:text-red-300"
          : "bg-neutral-800 border border-neutral-700/50 text-neutral-400 hover:bg-emerald-900/40 hover:border-emerald-500/40 hover:text-emerald-300"
      }`}
    >
      {added ? "✓" : "+"}
    </button>
  );
}

// ── Ticket Simulator ──────────────────────────────────────────────────────────

export function TicketSimulator({
  ticket,
  suggestions = [],
}: {
  ticket: TicketStore;
  suggestions?: TicketLeg[];
}) {
  const [stake, setStake] = useState(10);
  const [bankroll, setBankroll] = useState(500);
  const { legs, remove, clear } = ticket;

  const combinedOdd = legs.reduce((acc, l) => acc * l.fairOdd, 1);
  const combinedProb = legs.reduce((acc, l) => acc * l.modelProb, 1);
  const potentialReturn = stake * combinedOdd;
  const profit = potentialReturn - stake;
  const ev = (combinedProb * combinedOdd - 1) * 100;
  const kellyFrac = combinedOdd > 1
    ? Math.max(0, (combinedProb * combinedOdd - 1) / (combinedOdd - 1) * 0.25)
    : 0;
  const kellySuggest = kellyFrac * bankroll;

  const evColor = ev >= 5 ? "text-emerald-300" : ev >= 0 ? "text-blue-300" : "text-red-400";
  const evLabel = ev >= 5 ? "✅ EV Positivo" : ev >= 0 ? "⚠️ Neutro" : "❌ EV Negativo";

  return (
    <div className="space-y-4">

      {/* ── Ticket visual ── */}
      <div className="rounded-2xl border border-dashed border-neutral-700/60 bg-neutral-950/60 overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-dashed border-neutral-800">
          <div className="flex items-center gap-2">
            <span className="text-base">🎟️</span>
            <span className="text-sm font-bold text-white">Meu Bilhete</span>
            {legs.length > 0 && (
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-600 text-[10px] font-black text-white">
                {legs.length}
              </span>
            )}
          </div>
          {legs.length > 0 && (
            <button onClick={clear}
              className="text-[10px] text-red-400 hover:text-red-300 transition-colors font-semibold">
              🗑 Limpar tudo
            </button>
          )}
        </div>

        {/* Legs */}
        {legs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 gap-2 text-center px-4">
            <div className="text-3xl opacity-30">🎟️</div>
            <div className="text-sm text-neutral-500">Bilhete vazio</div>
            <div className="text-xs text-neutral-600">
              Clique em <span className="font-bold text-neutral-400">+</span> em qualquer pick para adicionar
            </div>
          </div>
        ) : (
          <div className="divide-y divide-dashed divide-neutral-800">
            {legs.map((leg, i) => (
              <div key={leg.id} className="flex items-start gap-3 px-4 py-3">
                <span className="text-[10px] font-black text-neutral-600 mt-0.5 w-4 shrink-0">{i + 1}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    {leg.type === "live" && (
                      <span className="text-[9px] font-bold text-red-400 bg-red-900/30 border border-red-700/30 px-1.5 py-0.5 rounded-full">
                        ⚡ AO VIVO {leg.liveMinute ? `${leg.liveMinute}'` : ""}
                      </span>
                    )}
                    {leg.type === "combo" && (
                      <span className="text-[9px] font-bold text-emerald-400 bg-emerald-900/30 border border-emerald-700/30 px-1.5 py-0.5 rounded-full">
                        COMBO
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-neutral-500 truncate mb-0.5">
                    {leg.home} × {leg.away}
                    {leg.liveScore && <span className="ml-1 font-mono text-white">{leg.liveScore}</span>}
                    {leg.group && <span className="ml-1 text-emerald-600"> Gr.{leg.group}</span>}
                    {!leg.liveScore && <span className="text-neutral-600"> · {kickoffTime(leg.kickoff)}</span>}
                  </div>
                  <div className="text-sm font-semibold text-white leading-snug">{leg.label}</div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${confBadge(leg.confidence)}`}>
                      {leg.confidence}
                    </span>
                    <span className="text-[10px] text-neutral-500">{(leg.modelProb * 100).toFixed(0)}% prob.</span>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-lg font-black font-mono text-emerald-300">{leg.fairOdd.toFixed(2)}</div>
                  <button onClick={() => remove(leg.id)}
                    className="text-[10px] text-neutral-600 hover:text-red-400 transition-colors mt-0.5">
                    ✕ remover
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Perforation */}
        {legs.length > 0 && (
          <div className="relative border-t border-dashed border-neutral-700/60">
            <div className="absolute -left-3 top-1/2 -translate-y-1/2 h-6 w-6 rounded-full bg-neutral-950 border border-neutral-800" />
            <div className="absolute -right-3 top-1/2 -translate-y-1/2 h-6 w-6 rounded-full bg-neutral-950 border border-neutral-800" />
          </div>
        )}

        {/* Footer — calculations */}
        {legs.length > 0 && (
          <div className="px-4 py-4 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs text-neutral-500">Odd Combinada</div>
                <div className="text-3xl font-black font-mono text-white">{combinedOdd.toFixed(2)}</div>
              </div>
              <div className="text-right">
                <div className="text-xs text-neutral-500">Prob. Combinada</div>
                <div className="text-xl font-black font-mono text-blue-300">{(combinedProb * 100).toFixed(1)}%</div>
              </div>
            </div>

            <div className={`rounded-xl border p-3 text-center ${
              ev >= 5 ? "border-emerald-700/40 bg-emerald-950/40" :
              ev >= 0 ? "border-blue-700/40 bg-blue-950/30" :
              "border-red-800/40 bg-red-950/30"
            }`}>
              <div className={`text-xs font-bold mb-0.5 ${evColor}`}>{evLabel}</div>
              <div className={`text-2xl font-black font-mono ${evColor}`}>
                {ev >= 0 ? "+" : ""}{ev.toFixed(1)}% EV
              </div>
              <div className="text-[10px] text-neutral-500 mt-0.5">
                Valor esperado = prob × odd − 1
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-[10px] text-neutral-500 uppercase tracking-wider font-semibold block mb-1">
                  Valor da aposta (R$)
                </label>
                <div className="flex items-center gap-2">
                  {[5, 10, 20, 50].map(v => (
                    <button key={v} onClick={() => setStake(v)}
                      className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition-all ${
                        stake === v
                          ? "bg-blue-600 text-white"
                          : "bg-neutral-800 text-neutral-400 hover:bg-neutral-700"
                      }`}>
                      R${v}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-2 rounded-xl bg-neutral-800/60 border border-neutral-700/50 px-3 py-2">
                <span className="text-xs text-neutral-400 font-semibold">R$</span>
                <input
                  type="number" min={1} step={1} value={stake}
                  onChange={e => setStake(Math.max(1, Number(e.target.value)))}
                  className="flex-1 bg-transparent text-white font-mono text-lg font-bold focus:outline-none"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl bg-black/40 border border-neutral-800 p-3 text-center">
                <div className="text-[10px] text-neutral-500 mb-0.5">Retorno Potencial</div>
                <div className="text-2xl font-black font-mono text-emerald-300">R${potentialReturn.toFixed(2)}</div>
              </div>
              <div className="rounded-xl bg-black/40 border border-neutral-800 p-3 text-center">
                <div className="text-[10px] text-neutral-500 mb-0.5">Lucro Potencial</div>
                <div className={`text-2xl font-black font-mono ${profit >= 0 ? "text-emerald-300" : "text-red-400"}`}>
                  {profit >= 0 ? "+" : ""}R${profit.toFixed(2)}
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-amber-700/30 bg-amber-950/20 p-3">
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs font-bold text-amber-400">Kelly Fracionado 25%</div>
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-neutral-600">Banca</span>
                  <input
                    type="number" value={bankroll} min={10} step={10}
                    onChange={e => setBankroll(Math.max(10, Number(e.target.value)))}
                    className="w-20 bg-neutral-800 border border-neutral-700 rounded px-2 py-0.5 text-xs font-mono text-white focus:outline-none"
                  />
                </div>
              </div>
              <div className="flex items-end gap-3">
                <div>
                  <div className="text-[10px] text-neutral-500">Fração recomendada</div>
                  <div className="text-lg font-black font-mono text-amber-300">{(kellyFrac * 100).toFixed(1)}%</div>
                </div>
                <div>
                  <div className="text-[10px] text-neutral-500">Valor sugerido</div>
                  <div className="text-lg font-black font-mono text-amber-300">R${kellySuggest.toFixed(2)}</div>
                </div>
                <div className="ml-auto text-right">
                  <div className="text-[10px] text-neutral-500">ROI esperado</div>
                  <div className={`text-lg font-black font-mono ${evColor}`}>
                    {ev >= 0 ? "+" : ""}{(ev * kellyFrac).toFixed(1)}%
                  </div>
                </div>
              </div>
              {kellyFrac === 0 && (
                <div className="text-[10px] text-red-400 mt-1">
                  ⚠️ Kelly negativo — odd não compensa o risco calculado pelo modelo
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Pick suggestions ── */}
      {suggestions.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-white">Picks disponíveis</span>
            <span className="text-[10px] text-neutral-500 bg-neutral-800 px-2 py-0.5 rounded-full">
              Clique + para adicionar
            </span>
          </div>
          <div className="space-y-2">
            {suggestions.map(leg => (
              <div key={leg.id}
                className={`flex items-center gap-3 rounded-xl border p-3 transition-all ${
                  ticket.has(leg.id)
                    ? "border-emerald-600/40 bg-emerald-950/20"
                    : "border-neutral-800/60 bg-neutral-900/40 hover:border-neutral-700/60"
                }`}
              >
                <AddBtn leg={leg} ticket={ticket} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    {leg.type === "live" && (
                      <span className="text-[9px] font-bold text-red-400 bg-red-900/20 px-1 rounded">⚡ LIVE {leg.liveMinute ? `${leg.liveMinute}'` : ""}</span>
                    )}
                    {leg.type === "combo" && (
                      <span className="text-[9px] font-bold text-emerald-400 bg-emerald-900/20 px-1 rounded">COMBO</span>
                    )}
                  </div>
                  <div className="text-xs text-neutral-500 truncate">
                    {leg.home} × {leg.away}
                    {leg.group && <span className="ml-1 text-emerald-600"> Gr.{leg.group}</span>}
                  </div>
                  <div className="text-sm font-semibold text-white leading-snug truncate">{leg.label}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-base font-black font-mono text-white">{leg.fairOdd.toFixed(2)}</div>
                  <div className="text-[10px] text-neutral-500">{(leg.modelProb * 100).toFixed(0)}%</div>
                </div>
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${confBadge(leg.confidence)} shrink-0`}>
                  {leg.confidence}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Floating ticket badge ─────────────────────────────────────────────────────

export function FloatingTicketBadge({
  count,
  onClick,
}: {
  count: number;
  onClick: () => void;
}) {
  if (count === 0) return null;
  return (
    <button
      onClick={onClick}
      className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-2xl bg-emerald-600 hover:bg-emerald-500 shadow-xl shadow-emerald-950/60 px-4 py-3 text-white font-bold text-sm transition-all"
    >
      🎟️ Meu Bilhete
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white text-emerald-700 text-[10px] font-black">
        {count}
      </span>
    </button>
  );
}
