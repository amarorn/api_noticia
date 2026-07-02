import type { ReactNode } from "react";

interface AppTableShellProps {
  children: ReactNode;
  className?: string;
  footer?: ReactNode;
}

export function AppTableShell({ children, className = "", footer }: AppTableShellProps) {
  return (
    <div className={`app-table-shell ${className}`.trim()}>
      <div className="overflow-x-auto">{children}</div>
      {footer ? <div className="border-t border-white/8 px-4 py-3 text-xs text-slate-500">{footer}</div> : null}
    </div>
  );
}
