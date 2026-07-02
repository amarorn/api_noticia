import { createContext, useContext } from "react";

interface AppShellContextValue {
  toggleMobileNav: () => void;
}

export const AppShellContext = createContext<AppShellContextValue | null>(null);

export function useAppShell() {
  return useContext(AppShellContext);
}
