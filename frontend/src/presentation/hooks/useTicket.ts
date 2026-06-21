import { useCallback, useState } from "react";

export interface TicketLeg {
  id: string;
  home: string;
  away: string;
  group: string | null;
  kickoff: string;
  label: string;
  market: string;
  fairOdd: number;
  modelProb: number;
  confidence: string;
  type: "single" | "combo" | "live";
  liveMinute?: number;
  liveScore?: string;
}

export const TICKET_STORAGE_KEY = "copa_central_ticket_v1";

function loadLegs(): TicketLeg[] {
  try {
    return JSON.parse(localStorage.getItem(TICKET_STORAGE_KEY) ?? "[]");
  } catch {
    return [];
  }
}

export function useTicket() {
  const [legs, setLegs] = useState<TicketLeg[]>(loadLegs);

  const persist = (next: TicketLeg[]) => {
    setLegs(next);
    localStorage.setItem(TICKET_STORAGE_KEY, JSON.stringify(next));
  };

  const add = useCallback((leg: TicketLeg) => {
    setLegs(prev => {
      if (prev.find(l => l.id === leg.id)) return prev;
      const next = [...prev, leg];
      localStorage.setItem(TICKET_STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const remove = useCallback((id: string) => {
    setLegs(prev => {
      const next = prev.filter(l => l.id !== id);
      localStorage.setItem(TICKET_STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const clear = useCallback(() => persist([]), []);

  const has = (id: string) => legs.some(l => l.id === id);

  return { legs, add, remove, clear, has };
}

export type TicketStore = ReturnType<typeof useTicket>;
