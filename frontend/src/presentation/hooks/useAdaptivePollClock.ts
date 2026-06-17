import { useEffect, useState } from "react";

/** Re-render periódico para recalcular tier de poll quando a idade da captura cresce. */
export function useAdaptivePollClock(enabled: boolean, tickMs = 5_000): number {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    const id = window.setInterval(() => setTick((value) => value + 1), tickMs);
    return () => window.clearInterval(id);
  }, [enabled, tickMs]);

  return tick;
}
