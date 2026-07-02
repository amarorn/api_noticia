import type { ReactNode } from "react";

interface AppKpiCardProps {
  label: string;
  value: ReactNode;
  hint?: string;
  valueClassName?: string;
  icon?: ReactNode;
}

export function AppKpiCard({ label, value, hint, valueClassName = "text-white", icon }: AppKpiCardProps) {
  return (
    <div className="live-kpi-card">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500">{label}</p>
        {icon ? <div className="live-kpi-icon text-neon-green">{icon}</div> : null}
      </div>
      <p className={`mt-1 font-mono text-lg font-bold ${valueClassName}`}>{value}</p>
      {hint ? <p className="mt-0.5 text-[10px] text-slate-500">{hint}</p> : null}
    </div>
  );
}
