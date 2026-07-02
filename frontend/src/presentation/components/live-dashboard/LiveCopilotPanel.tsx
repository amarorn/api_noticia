import type {
  LiveCopilot,
  LiveCopilotChatMessage,
  LiveCopilotUiAction,
} from "@/domain/entities";
import { useToast } from "@/presentation/components/ui/toast/ToastContext";
import { useCopilotAlertsPreference } from "@/presentation/hooks/useCopilotAlertsPreference";
import { useEffect, useRef, useState } from "react";

const ACTION_STYLES: Record<
  LiveCopilot["acaoAgora"],
  { label: string; className: string; dot: string }
> = {
  apostar: {
    label: "Apostar agora",
    className: "border-neon-green/30 bg-neon-green/10 text-neon-green",
    dot: "bg-neon-green",
  },
  aguardar: {
    label: "Aguardar",
    className: "border-amber-400/25 bg-amber-400/10 text-amber-200",
    dot: "bg-amber-400",
  },
  cashout: {
    label: "Cash-out",
    className: "border-rose-400/30 bg-rose-400/10 text-rose-200",
    dot: "bg-rose-400",
  },
};

interface LiveCopilotPanelProps {
  copilot: LiveCopilot | undefined;
  isLoading?: boolean;
  isFetching?: boolean;
  onAddBilheteToTicket?: () => void;
  agentChat?: {
    history: LiveCopilotChatMessage[];
    pendingActions: LiveCopilotUiAction[];
    isPending: boolean;
    lastMode?: string | null;
    onSend: (message: string) => void;
    onApplyActions: () => void;
    onDismissActions: () => void;
  };
}

function BilheteSection({
  copilot,
  onAddBilheteToTicket,
}: {
  copilot: LiveCopilot;
  onAddBilheteToTicket?: () => void;
}) {
  const { addToast } = useToast();
  const bilhete = copilot.bilhete;
  if (!bilhete || bilhete.tipo === "nenhum" || bilhete.pernas.length === 0) {
    if (bilhete?.resumo) {
      return (
        <p className="mt-3 rounded-xl border border-white/8 bg-black/20 px-3 py-2 text-xs text-slate-400">
          {bilhete.resumo}
        </p>
      );
    }
    return null;
  }

  return (
    <div className="mt-4 rounded-xl border border-cyan-400/15 bg-cyan-400/[0.04] p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h3 className="text-[11px] font-black uppercase tracking-widest text-white">
          Melhor bilhete
        </h3>
        <span className="rounded-full border border-cyan-400/25 bg-cyan-400/10 px-2 py-0.5 text-[9px] font-bold uppercase text-cyan-200">
          {bilhete.tipo}
        </span>
        {bilhete.valid ? (
          <span className="rounded-full border border-neon-green/25 bg-neon-green/10 px-2 py-0.5 text-[9px] font-bold text-neon-green">
            Validado
          </span>
        ) : (
          <span className="rounded-full border border-amber-400/25 bg-amber-400/10 px-2 py-0.5 text-[9px] font-bold text-amber-200">
            Revisar
          </span>
        )}
        {bilhete.combinedOdd != null && (
          <span className="ml-auto font-mono text-sm font-bold text-white">
            @ {bilhete.combinedOdd.toFixed(2)}
          </span>
        )}
      </div>

      {bilhete.titulo && <p className="text-sm font-semibold text-slate-100">{bilhete.titulo}</p>}
      {bilhete.resumo && <p className="mt-1 text-xs leading-relaxed text-slate-400">{bilhete.resumo}</p>}

      <div className="mt-3 space-y-2">
        {bilhete.pernas.map((perna) => (
          <div
            key={`${perna.market}-${perna.outcome}-${perna.rank}`}
            className="rounded-lg border border-white/[0.06] bg-black/30 px-3 py-2"
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-xs font-semibold text-white">
                  {perna.rank}. {perna.label}
                </p>
                <p className="mt-0.5 text-[10px] uppercase tracking-wide text-slate-500">
                  {perna.papel === "ancora" ? "Âncora" : "Complemento"}
                </p>
                {perna.rationale && (
                  <p className="mt-1 text-[11px] text-slate-400">{perna.rationale}</p>
                )}
              </div>
              {perna.marketOdd != null && (
                <span className="shrink-0 font-mono text-xs font-bold text-slate-200">
                  {perna.marketOdd.toFixed(2)}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {(bilhete.avisosCorrelacao.length > 0 || bilhete.validationWarnings.length > 0) && (
        <ul className="mt-2 space-y-1">
          {[...bilhete.avisosCorrelacao, ...bilhete.validationWarnings].map((msg) => (
            <li key={msg} className="text-[10px] text-amber-200/85">
              {msg}
            </li>
          ))}
        </ul>
      )}

      {onAddBilheteToTicket && (
        <button
          type="button"
          onClick={() => {
            onAddBilheteToTicket();
            addToast("Pernas do bilhete adicionadas ao simulador.", "success");
          }}
          className="mt-3 w-full rounded-xl border border-neon-green/30 bg-neon-green/10 py-2 text-xs font-bold text-neon-green transition hover:bg-neon-green/15"
        >
          Adicionar bilhete ao simulador
        </button>
      )}
    </div>
  );
}

function CopilotAlertsControl({
  permission,
  alertsActive,
  onActivate,
  onDeactivate,
  onRefresh,
}: {
  permission: NotificationPermission | "unsupported";
  alertsActive: boolean;
  onActivate: () => void;
  onDeactivate: () => void;
  onRefresh: () => void;
}) {
  if (permission === "unsupported") {
    return (
      <span className="ml-auto rounded-full border border-white/8 bg-white/5 px-2 py-0.5 text-[10px] text-slate-500">
        Alertas indisponíveis
      </span>
    );
  }

  if (permission === "granted" && alertsActive) {
    return (
      <button
        type="button"
        onClick={onDeactivate}
        className="ml-auto inline-flex items-center gap-1.5 rounded-full border border-neon-green/35 bg-neon-green/12 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-neon-green transition hover:border-rose-400/35 hover:bg-rose-400/10 hover:text-rose-200"
        title="Clique para desativar alertas de apostar e cash-out"
      >
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-neon-green/60 opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-neon-green" />
        </span>
        Alertas ativos
      </button>
    );
  }

  if (permission === "denied") {
    return (
      <button
        type="button"
        onClick={onRefresh}
        className="ml-auto rounded-full border border-rose-400/30 bg-rose-400/10 px-2.5 py-1 text-[10px] font-semibold text-rose-200 hover:bg-rose-400/15"
        title="Permissão negada — habilite notificações nas configurações do navegador"
      >
        Alertas bloqueados
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={onActivate}
      className="ml-auto inline-flex items-center gap-1 rounded-full border border-sky-400/30 bg-sky-400/10 px-2.5 py-1 text-[10px] font-semibold text-sky-200 transition hover:border-sky-300/50 hover:bg-sky-400/15"
    >
      <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M13.73 21a2 2 0 01-3.46 0" strokeLinecap="round" />
      </svg>
      Ativar alertas
    </button>
  );
}

const AGENT_QUICK_PROMPTS = [
  "O que apostar agora?",
  "Monte um bilhete seguro",
  "Devo fazer cash-out?",
];

function CopilotAgentChat({
  enabled,
  agentChat,
}: {
  enabled: boolean;
  agentChat: NonNullable<LiveCopilotPanelProps["agentChat"]>;
}) {
  const [input, setInput] = useState("");
  const [expanded, setExpanded] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (agentChat.history.length > 0) setExpanded(true);
  }, [agentChat.history.length]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [agentChat.history, agentChat.isPending]);

  if (!enabled) return null;

  const submit = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || agentChat.isPending) return;
    setInput("");
    agentChat.onSend(trimmed);
  };

  return (
    <div className="mt-4 rounded-xl border border-violet-400/15 bg-violet-400/[0.04] p-3">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2 text-left"
      >
        <span className="text-[11px] font-black uppercase tracking-widest text-white">
          Agente interativo
        </span>
        {agentChat.lastMode && agentChat.lastMode !== "narrate" && (
          <span className="rounded-full border border-violet-400/25 bg-violet-400/10 px-2 py-0.5 text-[9px] font-bold uppercase text-violet-200">
            {agentChat.lastMode}
          </span>
        )}
        <svg
          viewBox="0 0 24 24"
          className={`ml-auto h-4 w-4 text-slate-400 transition ${expanded ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {expanded && (
        <>
          <div
            ref={scrollRef}
            className="mt-3 max-h-52 space-y-2 overflow-y-auto rounded-lg border border-white/[0.06] bg-black/25 p-2"
          >
            {agentChat.history.length === 0 && !agentChat.isPending && (
              <p className="px-2 py-3 text-xs text-slate-500">
                Pergunte ao agente — ele consulta o motor EV/Kelly e pode montar bilhete ou trocar
                de aba. Requer <code className="text-slate-400">LIVE_COPILOT_MODE=agent</code>.
              </p>
            )}
            {agentChat.history.map((msg, idx) => (
              <div
                key={`${msg.role}-${idx}`}
                className={`rounded-lg px-3 py-2 text-xs leading-relaxed ${
                  msg.role === "user"
                    ? "ml-6 border border-sky-400/20 bg-sky-400/10 text-sky-100"
                    : "mr-6 border border-white/[0.06] bg-white/[0.04] text-slate-200"
                }`}
              >
                {msg.content}
              </div>
            ))}
            {agentChat.isPending && (
              <div className="mr-6 rounded-lg border border-white/[0.06] bg-white/[0.04] px-3 py-2 text-xs text-slate-400">
                Analisando jogo…
              </div>
            )}
          </div>

          {agentChat.pendingActions.length > 0 && (
            <div className="mt-3 rounded-lg border border-neon-green/20 bg-neon-green/[0.06] p-3">
              <p className="text-[11px] font-semibold text-neon-green">
                Plano sugerido ({agentChat.pendingActions.length}{" "}
                {agentChat.pendingActions.length === 1 ? "ação" : "ações"})
              </p>
              <ul className="mt-2 space-y-1 text-[11px] text-slate-300">
                {agentChat.pendingActions.map((action, idx) => (
                  <li key={`${action.type}-${idx}`}>
                    {action.type === "notify" && (action.title || action.body || "Notificação")}
                    {action.type === "add_ticket_legs" &&
                      `Adicionar ${action.legs.length} perna(s) ao simulador`}
                    {action.type === "switch_tab" && `Ir para aba ${action.tab ?? "?"}`}
                  </li>
                ))}
              </ul>
              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  onClick={agentChat.onApplyActions}
                  className="flex-1 rounded-lg border border-neon-green/30 bg-neon-green/10 py-2 text-xs font-bold text-neon-green transition hover:bg-neon-green/15"
                >
                  Executar plano
                </button>
                <button
                  type="button"
                  onClick={agentChat.onDismissActions}
                  className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-400 hover:bg-white/10"
                >
                  Ignorar
                </button>
              </div>
            </div>
          )}

          <div className="mt-3 flex flex-wrap gap-1.5">
            {AGENT_QUICK_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                disabled={agentChat.isPending}
                onClick={() => submit(prompt)}
                className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[10px] text-slate-300 transition hover:border-violet-400/30 hover:text-violet-200 disabled:opacity-50"
              >
                {prompt}
              </button>
            ))}
          </div>

          <form
            className="mt-3 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              submit(input);
            }}
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ex.: vale entrar no over 2.5 agora?"
              disabled={agentChat.isPending}
              maxLength={2000}
              className="min-w-0 flex-1 rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-xs text-white placeholder:text-slate-600 focus:border-violet-400/40 focus:outline-none disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={agentChat.isPending || !input.trim()}
              className="shrink-0 rounded-xl border border-violet-400/30 bg-violet-400/10 px-4 py-2 text-xs font-bold text-violet-200 transition hover:bg-violet-400/15 disabled:opacity-50"
            >
              Enviar
            </button>
          </form>
        </>
      )}
    </div>
  );
}

export function LiveCopilotPanel({
  copilot,
  isLoading,
  isFetching,
  onAddBilheteToTicket,
  agentChat,
}: LiveCopilotPanelProps) {
  const { addToast } = useToast();
  const {
    alertsActive,
    notifyPermission,
    activateAlerts,
    deactivateAlerts,
    refreshPermission,
  } = useCopilotAlertsPreference();

  const handleDeactivateAlerts = () => {
    deactivateAlerts();
    addToast("Alertas do copiloto desativados.", "info");
  };

  if (isLoading && !copilot) {
    return (
      <div className="live-glass-panel-glow glow-border rounded-2xl p-4">
        <div className="mb-3 flex items-center gap-2">
          <div className="live-skeleton-shimmer h-4 w-32 rounded-md" />
          <div className="live-skeleton-shimmer h-5 w-20 rounded-full" />
        </div>
        <div className="space-y-2">
          <div className="live-skeleton-shimmer h-3 w-full rounded-md" />
          <div className="live-skeleton-shimmer h-3 w-4/5 rounded-md" />
          <div className="live-skeleton-shimmer mt-4 h-16 w-full rounded-xl" />
        </div>
      </div>
    );
  }

  if (!copilot) return null;

  const action = ACTION_STYLES[copilot.acaoAgora] ?? ACTION_STYLES.aguardar;
  const showApostarPulse = copilot.acaoAgora === "apostar" && copilot.picks.length > 0;

  return (
    <div
      className={`live-glass-panel-glow glow-border relative overflow-hidden rounded-2xl p-4 ${
        showApostarPulse ? "ring-1 ring-neon-green/40 shadow-[0_0_28px_rgba(0,245,160,0.12)]" : ""
      }`}
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          background:
            "radial-gradient(ellipse at top left, rgba(0,245,160,0.08), transparent 55%), radial-gradient(ellipse at bottom right, rgba(0,224,255,0.06), transparent 50%)",
        }}
      />

      <div className="relative">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h2 className="text-xs font-black uppercase tracking-widest text-white">Copiloto GPT</h2>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${action.className}`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${action.dot}`} />
            {action.label}
          </span>
          <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-semibold text-slate-300">
            {copilot.confiancaGeral}
          </span>
          {copilot.model && !alertsActive && notifyPermission !== "granted" && (
            <span className="text-[10px] text-slate-500">{copilot.model}</span>
          )}
          {isFetching && (
            <span className="text-[10px] text-slate-500">{copilot.cached ? "cache · " : ""}atualizando…</span>
          )}
          <CopilotAlertsControl
            permission={notifyPermission}
            alertsActive={alertsActive}
            onActivate={activateAlerts}
            onDeactivate={handleDeactivateAlerts}
            onRefresh={refreshPermission}
          />
        </div>

        {notifyPermission === "granted" && alertsActive && (
          <p className="mb-3 flex items-center gap-2 rounded-xl border border-neon-green/15 bg-neon-green/[0.06] px-3 py-2 text-[11px] text-neon-green/90">
            <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 11.08V12a10 10 0 11-5.93-9.14" strokeLinecap="round" />
              <path d="M22 4L12 14.01l-3-3" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Monitorando o jogo — avisamos quando surgir momento de apostar ou cash-out.
            {copilot.model ? (
              <span className="ml-auto shrink-0 text-[10px] text-slate-500">{copilot.model}</span>
            ) : null}
          </p>
        )}

        {!copilot.enabled && (
          <p className="mb-3 rounded-xl border border-white/8 bg-black/20 px-3 py-2 text-xs text-slate-400">
            GPT desativado — configure <code className="text-slate-300">OPENAI_API_KEY</code> no backend.
            Exibindo sinais quantitativos abaixo.
          </p>
        )}

        {copilot.momento && (
          <p className="mb-3 text-sm leading-relaxed text-slate-200">{copilot.momento}</p>
        )}

        {copilot.waitReason && copilot.acaoAgora === "aguardar" && (
          <p className="mb-3 text-xs text-amber-200/90">{copilot.waitReason}</p>
        )}

        {copilot.picks.length > 0 && (
          <div className="space-y-2">
            {copilot.picks.map((pick) => (
              <div
                key={`${pick.market}-${pick.outcome}-${pick.rank}`}
                className="rounded-xl border border-white/[0.06] bg-black/25 px-3 py-2.5"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-white">{pick.label}</p>
                    <p className="mt-1 text-xs leading-relaxed text-slate-400">{pick.rationale}</p>
                  </div>
                  <span className="shrink-0 rounded-md border border-neon-green/20 bg-neon-green/10 px-2 py-0.5 text-[10px] font-bold text-neon-green">
                    {pick.confidence}
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-slate-400">
                  {pick.marketOdd != null && (
                    <span>
                      Odd <strong className="text-slate-200">{pick.marketOdd.toFixed(2)}</strong>
                    </span>
                  )}
                  {pick.expectedValue != null && (
                    <span>
                      EV{" "}
                      <strong className="text-neon-green">
                        {(pick.expectedValue * 100).toFixed(1)}%
                      </strong>
                    </span>
                  )}
                  {pick.edgePp != null && (
                    <span>
                      Edge{" "}
                      <strong className="text-slate-200">
                        {pick.edgePp >= 0 ? "+" : ""}
                        {pick.edgePp.toFixed(1)} pp
                      </strong>
                    </span>
                  )}
                  {pick.suggestedStakePct != null && pick.suggestedStakePct > 0 && (
                    <span>
                      Stake{" "}
                      <strong className="text-slate-200">{pick.suggestedStakePct.toFixed(2)}%</strong>
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {copilot.alertas.length > 0 && (
          <ul className="mt-3 space-y-1.5">
            {copilot.alertas.map((alerta) => (
              <li
                key={alerta}
                className="flex items-start gap-2 text-xs text-slate-400 before:mt-1.5 before:h-1 before:w-1 before:shrink-0 before:rounded-full before:bg-amber-400 before:content-['']"
              >
                {alerta}
              </li>
            ))}
          </ul>
        )}

        <BilheteSection copilot={copilot} onAddBilheteToTicket={onAddBilheteToTicket} />

        {agentChat && (
          <CopilotAgentChat enabled={copilot.enabled} agentChat={agentChat} />
        )}

        {copilot.error && copilot.enabled && (
          <p className="mt-3 text-[11px] text-rose-300/80">Fallback ativo: {copilot.error}</p>
        )}

        <p className="mt-3 text-[10px] leading-relaxed text-slate-600">
          Orientação estatística — não garante resultado. Picks validados contra o motor EV/Kelly.
        </p>
      </div>
    </div>
  );
}
