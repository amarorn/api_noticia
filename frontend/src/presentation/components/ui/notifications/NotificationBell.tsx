import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { IconBell, IconCheck, IconInfo, IconX } from "@/presentation/components/ui/Icons";
import {
  useNotifications,
  type AppNotification,
  type NotificationType,
} from "./NotificationsContext";

const typeStyles: Record<
  NotificationType,
  { icon: typeof IconInfo; text: string; bg: string; border: string }
> = {
  success: {
    icon: IconCheck,
    text: "text-neon-green",
    bg: "bg-neon-green/10",
    border: "border-neon-green/20",
  },
  error: {
    icon: IconX,
    text: "text-red-400",
    bg: "bg-red-500/10",
    border: "border-red-500/20",
  },
  info: {
    icon: IconInfo,
    text: "text-neon-blue",
    bg: "bg-neon-blue/10",
    border: "border-neon-blue/20",
  },
};

function formatTime(ts: number): string {
  return new Intl.DateTimeFormat("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(ts);
}

function sourceLabel(source: AppNotification["source"]): string | null {
  if (source === "copilot") return "Copiloto";
  if (source === "cashout") return "Cash-out";
  return null;
}

interface NotificationBellProps {
  className?: string;
  buttonClassName?: string;
}

export function NotificationBell({ className = "", buttonClassName = "" }: NotificationBellProps) {
  const {
    notifications,
    unreadCount,
    removeNotification,
    markAsRead,
    markAllAsRead,
    clearAll,
  } = useNotifications();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  const toggle = () => {
    setOpen((prev) => {
      const next = !prev;
      if (!prev) markAllAsRead();
      return next;
    });
  };

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <button
        type="button"
        onClick={toggle}
        className={
          buttonClassName ||
          "relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-slate-300 transition hover:border-neon-green/35 hover:text-neon-green"
        }
        aria-label={
          unreadCount > 0
            ? `Notificações (${unreadCount} não lidas)`
            : "Notificações"
        }
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        <IconBell className="h-4 w-4" />
        {unreadCount > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-neon-green px-1 text-[9px] font-bold text-surface-100 shadow-[0_0_8px_rgba(0,245,160,0.5)]">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 420, damping: 32 }}
            className="absolute right-0 top-[calc(100%+0.5rem)] z-[120] w-[min(92vw,22rem)] overflow-hidden rounded-2xl border border-white/10 bg-surface-100/95 shadow-[0_16px_48px_rgba(0,0,0,0.45)] backdrop-blur-xl"
            role="dialog"
            aria-label="Painel de notificações"
          >
            <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
              <div>
                <p className="font-display text-sm font-bold text-white">Notificações</p>
                <p className="text-[10px] text-slate-500">
                  {notifications.length === 0
                    ? "Nenhuma notificação"
                    : `${notifications.length} no histórico`}
                </p>
              </div>
              {notifications.length > 0 && (
                <button
                  type="button"
                  onClick={clearAll}
                  className="rounded-lg px-2 py-1 text-[10px] font-medium text-slate-500 transition hover:bg-white/5 hover:text-slate-300"
                >
                  Limpar todas
                </button>
              )}
            </div>

            <div className="max-h-[min(60vh,24rem)] overflow-y-auto scrollbar-thin">
              {notifications.length === 0 ? (
                <div className="px-4 py-10 text-center">
                  <IconBell className="mx-auto mb-2 h-6 w-6 text-slate-600" />
                  <p className="text-sm text-slate-400">Sem notificações por enquanto</p>
                  <p className="mt-1 text-[11px] text-slate-600">
                    Alertas do copiloto e cash-out aparecem aqui.
                  </p>
                </div>
              ) : (
                <ul className="divide-y divide-white/[0.05]">
                  {notifications.map((item) => {
                    const style = typeStyles[item.type];
                    const Icon = style.icon;
                    const tag = sourceLabel(item.source);
                    return (
                      <li
                        key={item.id}
                        className={`group relative px-4 py-3 transition-colors hover:bg-white/[0.03] ${
                          item.read ? "" : "bg-white/[0.02]"
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <span
                            className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border ${style.bg} ${style.border}`}
                          >
                            <Icon className={`h-3.5 w-3.5 ${style.text}`} />
                          </span>
                          <div className="min-w-0 flex-1">
                            <div className="mb-1 flex flex-wrap items-center gap-2">
                              <p className="text-sm font-semibold text-white">{item.title}</p>
                              {tag && (
                                <span className="rounded-md bg-white/5 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-slate-500">
                                  {tag}
                                </span>
                              )}
                            </div>
                            <p className="text-xs leading-relaxed text-slate-400">{item.body}</p>
                            <p className="mt-1.5 font-mono text-[10px] text-slate-600">
                              {formatTime(item.createdAt)}
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              markAsRead(item.id);
                              removeNotification(item.id);
                            }}
                            className="shrink-0 rounded-lg p-1.5 text-slate-600 opacity-70 transition hover:bg-white/5 hover:text-white group-hover:opacity-100"
                            aria-label="Fechar notificação"
                          >
                            <IconX className="h-3.5 w-3.5" />
                          </button>
                        </div>
                        {!item.read && (
                          <span className="absolute left-1.5 top-1/2 h-1.5 w-1.5 -translate-y-1/2 rounded-full bg-neon-green" />
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
