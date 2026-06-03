import { AnimatePresence, motion } from "framer-motion";
import { useToast } from "./ToastContext";
import { IconCheck, IconX, IconInfo } from "@/presentation/components/ui/Icons";

const typeConfig = {
  success: {
    bg: "bg-neon-green/10 border-neon-green/20",
    text: "text-neon-green",
    icon: IconCheck,
    shadow: "shadow-[0_0_16px_rgba(0,255,136,0.12)]",
  },
  error: {
    bg: "bg-red-500/10 border-red-500/20",
    text: "text-red-400",
    icon: IconX,
    shadow: "shadow-[0_0_16px_rgba(239,68,68,0.12)]",
  },
  info: {
    bg: "bg-neon-blue/10 border-neon-blue/20",
    text: "text-neon-blue",
    icon: IconInfo,
    shadow: "shadow-[0_0_16px_rgba(0,212,255,0.12)]",
  },
};

export function ToastContainer() {
  const { toasts, removeToast } = useToast();

  return (
    <div className="fixed right-4 top-4 z-[100] flex flex-col gap-3 sm:right-6 sm:top-6">
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => {
          const config = typeConfig[toast.type];
          const Icon = config.icon;
          return (
            <motion.div
              key={toast.id}
              layout
              initial={{ opacity: 0, x: 40, scale: 0.95 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 20, scale: 0.95 }}
              transition={{ type: "spring", stiffness: 400, damping: 30 }}
              className={`flex min-w-[280px] max-w-sm items-center gap-3 rounded-xl border px-4 py-3 backdrop-blur-xl ${config.bg} ${config.shadow}`}
            >
              <Icon className={`h-4 w-4 shrink-0 ${config.text}`} />
              <p className={`flex-1 text-sm font-medium ${config.text}`}>{toast.message}</p>
              <button
                type="button"
                onClick={() => removeToast(toast.id)}
                className="shrink-0 rounded-lg p-1 text-slate-500 transition-colors hover:bg-white/5 hover:text-white"
                aria-label="Fechar notificação"
              >
                <IconX className="h-3.5 w-3.5" />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
