import type { LiveCopilot } from "@/domain/entities";
import { useToast } from "@/presentation/components/ui/toast/ToastContext";
import {
  ensureNotificationPermission,
  notificationPermission,
} from "@/presentation/utils/browserNotifications";
import { useCallback, useEffect, useState } from "react";

const COPILOT_ALERTS_KEY = "bolao-copilot-alerts-active";

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

function readAlertsActive(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(COPILOT_ALERTS_KEY) === "1";
}

function CopilotAlertsControl({
  permission,
  alertsActive,
  onActivate,
  onRefresh,
}: {
  permission: NotificationPermission | "unsupported";
  alertsActive: boolean;
  onActivate: () => void;
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
      <span
        className="ml-auto inline-flex items-center gap-1.5 rounded-full border border-neon-green/35 bg-neon-green/12 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-neon-green"
        title="Você receberá toast e notificação quando o copiloto sinalizar apostar ou cash-out"
      >
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-neon-green/60 opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-neon-green" />
        </span>
        Alertas ativos
      </span>
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

export function LiveCopilotPanel({ copilot, isLoading, isFetching, onAddBilheteToTicket }: LiveCopilotPanelProps) {
  const [notifyPermission, setNotifyPermission] = useState(notificationPermission());
  const [alertsActive, setAlertsActive] = useState(readAlertsActive);

  const refreshPermission = useCallback(() => {
    const current = notificationPermission();
    setNotifyPermission(current);
    if (current === "granted") {
      setAlertsActive(true);
      window.localStorage.setItem(COPILOT_ALERTS_KEY, "1");
    }
  }, []);

  useEffect(() => {
    refreshPermission();
    const onVisible = () => {
      if (document.visibilityState === "visible") refreshPermission();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [refreshPermission]);

  const handleActivateAlerts = async () => {
    const ok = await ensureNotificationPermission();
    const current = notificationPermission();
    setNotifyPermission(current);
    if (ok && current === "granted") {
      setAlertsActive(true);
      window.localStorage.setItem(COPILOT_ALERTS_KEY, "1");
    }
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
            onActivate={handleActivateAlerts}
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
