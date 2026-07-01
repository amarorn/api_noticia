import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { calculateSuperMultiplaUseCase } from "@/application/container";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import { LONGSHOT_STAKE_BRL } from "@/presentation/utils/longshotCombos";
import type { SuperMultiplaCalculateLeg } from "@/presentation/utils/superMultipla";

export type SuperMultiplaSlipLeg = SuperMultiplaCalculateLeg & {
  label: string;
  modelProb: number;
  expectedValue: number;
  edgePp: number;
};

function parseScore(score: string | null | undefined): { home: number; away: number } {
  if (!score) return { home: 0, away: 0 };
  const match = score.match(/(\d+)\s*[-×x]\s*(\d+)/i);
  if (!match) return { home: 0, away: 0 };
  return { home: Number(match[1]), away: Number(match[2]) };
}

export function marketScanRowToSlipLeg(
  row: NonNullable<SuperbetLiveAdvice["strategy"]>["marketScan"][number],
  data: SuperbetLiveAdvice,
): SuperMultiplaSlipLeg {
  return {
    id: crypto.randomUUID(),
    market: row.market,
    outcome: row.outcome,
    market_odd: row.marketOdd,
    model_prob: row.modelProb,
    superbet_event_id: data.superbetEventId,
    event_name: `${data.homeTeam} vs ${data.awayTeam}`,
    selection_label: row.label,
    is_live: data.isLive,
    minute: data.minute,
    label: row.label,
    modelProb: row.modelProb,
    expectedValue: row.expectedValue,
    edgePp: row.edgePp,
  };
}

export function useSuperMultiplaSlip(
  data: SuperbetLiveAdvice,
  legs: SuperMultiplaSlipLeg[],
  stake: number,
) {
  const scores = useMemo(() => parseScore(data.currentScore), [data.currentScore]);

  const apiLegs = useMemo(
    () =>
      legs.map(({ label: _label, modelProb, expectedValue, edgePp, ...leg }) => ({
        ...leg,
        model_prob: modelProb,
      })),
    [legs],
  );

  const enabled = legs.length >= 2 && stake > 0;

  const query = useQuery({
    queryKey: [
      "super-multipla-calculate",
      data.superbetEventId,
      data.minute,
      stake,
      apiLegs.map((l) => `${l.market}:${l.outcome}:${l.market_odd}`).join("|"),
    ],
    queryFn: () =>
      calculateSuperMultiplaUseCase.execute({
        legs: apiLegs,
        stake,
        betType: "MULTIPLE",
        minute: data.minute,
        homeScore: scores.home,
        awayScore: scores.away,
        superbetEventId: data.superbetEventId,
      }),
    enabled,
    staleTime: 8_000,
    refetchOnWindowFocus: false,
  });

  return {
    result: query.data ?? null,
    isCalculating: query.isFetching,
    error: query.error,
    canCalculate: enabled,
    defaultStake: LONGSHOT_STAKE_BRL,
  };
}
