import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

/** Altura da top bar unificada — sidebar inicia abaixo dela */
export const LIVE_TOPBAR_HEIGHT_PX = 68;

export interface LiveDashboardChromeData {
  isLive: boolean;
  lastUpdate: string;
  nextUpdate: string;
  isFetching: boolean;
  onRefresh: () => void;
}

interface LiveDashboardChromeContextValue {
  chrome: LiveDashboardChromeData | null;
  setChrome: (data: LiveDashboardChromeData | null) => void;
}

const LiveDashboardChromeContext = createContext<LiveDashboardChromeContextValue | null>(null);

export function LiveDashboardChromeProvider({ children }: { children: ReactNode }) {
  const [chrome, setChrome] = useState<LiveDashboardChromeData | null>(null);
  const value = useMemo(() => ({ chrome, setChrome }), [chrome]);
  return (
    <LiveDashboardChromeContext.Provider value={value}>
      {children}
    </LiveDashboardChromeContext.Provider>
  );
}

export function useLiveDashboardChrome() {
  const ctx = useContext(LiveDashboardChromeContext);
  if (!ctx) {
    throw new Error("useLiveDashboardChrome deve ser usado dentro de LiveDashboardChromeProvider");
  }
  return ctx;
}

export function useLiveDashboardChromeOptional() {
  return useContext(LiveDashboardChromeContext);
}
