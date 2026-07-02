import type { ReactNode, ComponentType } from "react";
import { motion } from "framer-motion";

interface EmptyStateProps {
  title: string;
  description: string;
  action?: ReactNode;
  icon?: ComponentType<{ className?: string }>;
  iconColor?: string;
}

export function EmptyState({
  title,
  description,
  action,
  icon: Icon,
  iconColor = "#00d4ff",
}: EmptyStateProps) {
  return (
    <div className="live-glass-panel-glow glow-border relative overflow-hidden">
      {/* Background mesh sutil */}
      <div
        className="absolute inset-0 opacity-20"
        style={{
          backgroundImage: `radial-gradient(ellipse 60% 50% at 50% 50%, ${iconColor}08, transparent 60%)`,
        }}
      />
      <div className="relative flex flex-col items-center gap-4 p-10 text-center sm:p-12">
        {Icon && (
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", stiffness: 260, damping: 20 }}
            className="flex h-16 w-16 items-center justify-center rounded-2xl"
            style={{ backgroundColor: `${iconColor}12`, color: iconColor, border: `1px solid ${iconColor}20` }}
          >
            <Icon className="h-7 w-7" />
          </motion.div>
        )}
        <div>
          <h3 className="text-lg font-semibold text-white">{title}</h3>
          <p className="mx-auto mt-1 max-w-sm text-sm leading-relaxed text-slate-400">{description}</p>
        </div>
        {action && <div className="mt-1">{action}</div>}
      </div>
    </div>
  );
}

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
    <div className="glass-card flex flex-col items-center gap-5 p-8 text-center">
      <motion.div
        initial={{ scale: 0.5, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: "spring", stiffness: 260, damping: 20 }}
        className="flex h-16 w-16 items-center justify-center rounded-2xl border border-red-500/20 bg-red-500/10 text-red-400"
      >
        <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303.087 7.454 7.454M15.75 9a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z" />
        </svg>
      </motion.div>
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
