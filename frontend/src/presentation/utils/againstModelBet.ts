import type { OutcomeLabel } from "@/domain/entities";
import type { AgainstModelAlert } from "@/presentation/components/predictions/LiveAgainstModelAlert";

export function normalizeH2hOutcome(outcome: string): OutcomeLabel | null {
  const key = outcome.trim().toLowerCase();
  if (key === "1" || key === "home") return "1";
  if (key === "2" || key === "away") return "2";
  if (key === "x" || key === "draw" || key === "0") return "X";
  return null;
}

/** Palpite in-play por maior probabilidade final (espelho simplificado do backend). */
export function inplayH2hPalpite(probs: {
  probFinalHome: number;
  probFinalDraw: number;
  probFinalAway: number;
}): OutcomeLabel {
  const entries: [OutcomeLabel, number][] = [
    ["1", probs.probFinalHome],
    ["X", probs.probFinalDraw],
    ["2", probs.probFinalAway],
  ];
  entries.sort((a, b) => b[1] - a[1]);
  return entries[0][0];
}

/** Rascunho local ao cadastrar aposta manual (sem API). */
export function draftAgainstModelAlert(
  bet: { market: string; outcome: string; stake: number; oddsPlaced: number },
  data: {
    homeTeam: string;
    awayTeam: string;
    inplaySummary: {
      probFinalHome: number;
      probFinalDraw: number;
      probFinalAway: number;
    };
  },
  pregame?: { palpite: OutcomeLabel; prob: number } | null,
): AgainstModelAlert | null {
  if (bet.market !== "h2h") return null;
  const betOutcome = normalizeH2hOutcome(bet.outcome);
  if (!betOutcome) return null;

  const inplayPalpite = inplayH2hPalpite(data.inplaySummary);
  const inplayProb =
    inplayPalpite === "1"
      ? data.inplaySummary.probFinalHome
      : inplayPalpite === "X"
        ? data.inplaySummary.probFinalDraw
        : data.inplaySummary.probFinalAway;

  const vsInplay = betOutcome !== inplayPalpite;
  const vsPregame = pregame != null && betOutcome !== pregame.palpite;
  if (!vsInplay && !vsPregame) return null;

  const label =
    betOutcome === "1"
      ? `Vitória ${data.homeTeam}`
      : betOutcome === "2"
        ? `Vitória ${data.awayTeam}`
        : "Empate";

  const parts: string[] = [];
  if (vsPregame && pregame) {
    parts.push(`pré-jogo apontava ${pregame.palpite} (${(pregame.prob * 100).toFixed(0)}%)`);
  }
  if (vsInplay) {
    parts.push(`ao vivo o modelo favorece ${inplayPalpite} (${(inplayProb * 100).toFixed(0)}%)`);
  }

  return {
    betId: null,
    market: "h2h",
    betOutcome,
    betOutcomeLabel: label,
    stake: bet.stake,
    oddsPlaced: bet.oddsPlaced,
    pregamePalpite: pregame?.palpite ?? inplayPalpite,
    pregameProb: pregame?.prob ?? 0,
    pregameUncertainty: null,
    inplayPalpite,
    inplayProb,
    inplayProbs: {
      "1": data.inplaySummary.probFinalHome,
      X: data.inplaySummary.probFinalDraw,
      "2": data.inplaySummary.probFinalAway,
    },
    severity: vsPregame && vsInplay ? "critical" : vsInplay ? "high" : "medium",
    againstPregame: vsPregame,
    againstInplay: vsInplay,
    message: `Sua aposta (${label}, R$ ${bet.stake.toFixed(2)}) está contra o modelo: ${parts.join(" · ")}.`,
  };
}
