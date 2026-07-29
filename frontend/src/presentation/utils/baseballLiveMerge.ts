import type { BaseballSuperbetLiveAdvice } from "@/domain/entities";

export type BaseballAdviceSource = "fast" | "full";

export function mergeBaseballLiveAdvice(
  fast: BaseballSuperbetLiveAdvice | undefined,
  full: BaseballSuperbetLiveAdvice | undefined,
): { data: BaseballSuperbetLiveAdvice | undefined; source: BaseballAdviceSource | null } {
  if (!fast && !full) return { data: undefined, source: null };
  if (!full) return { data: fast, source: "fast" };
  if (!fast) return { data: full, source: "full" };

  const fastTs = Date.parse(fast.capturedAt ?? "") || 0;
  const fullTs = Date.parse(full.capturedAt ?? "") || 0;
  if (fullTs >= fastTs) return { data: full, source: "full" };

  return {
    data: {
      ...fast,
      strategy: full.strategy ?? fast.strategy,
      trendReport: full.trendReport ?? fast.trendReport,
      marketBenchmark: full.marketBenchmark ?? fast.marketBenchmark,
      betGuardrails: full.betGuardrails ?? fast.betGuardrails,
      cashout: full.cashout ?? fast.cashout,
      scoreStale: fast.scoreStale ?? full.scoreStale,
    },
    source: "fast",
  };
}
