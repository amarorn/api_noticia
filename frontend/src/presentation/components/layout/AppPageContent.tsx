import type { ReactNode } from "react";

interface AppPageContentProps {
  children: ReactNode;
  className?: string;
}

/** Área de conteúdo principal — mesmo padding do dashboard ao vivo. */
export function AppPageContent({ children, className = "" }: AppPageContentProps) {
  return <div className={`live-page-body space-y-4 ${className}`.trim()}>{children}</div>;
}
