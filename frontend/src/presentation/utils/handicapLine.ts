/** Converte chave do parser Superbet (ex.: m0_5) em rótulo legível (-0.5). */
export function formatHandicapLineKey(key: string): string {
  if (key === "0") return "0";
  const match = key.match(/^([mp])([\d_]+)$/);
  if (!match) return key;
  const num = match[2].replace("_", ".");
  return `${match[1] === "m" ? "-" : "+"}${num}`;
}

function lineAbs(key: string): number {
  const label = formatHandicapLineKey(key);
  return Math.abs(Number.parseFloat(label.replace("+", "")));
}

/** Linha espelhada na Superbet (m0_5 ↔ p0_5). */
export function mirrorLineKey(key: string): string {
  if (key === "0") return "0";
  if (key.startsWith("m")) return `p${key.slice(1)}`;
  if (key.startsWith("p")) return `m${key.slice(1)}`;
  return key;
}

/** Par de chaves: mandante negativo + visitante positivo no mercado de 2 vias. */
export function pairedHandicapKeys(lineKey: string): { homeLineKey: string; awayLineKey: string } {
  const label = formatHandicapLineKey(lineKey);
  if (label.startsWith("-")) {
    return { homeLineKey: lineKey, awayLineKey: mirrorLineKey(lineKey) };
  }
  if (label.startsWith("+")) {
    return { homeLineKey: mirrorLineKey(lineKey), awayLineKey: lineKey };
  }
  return { homeLineKey: lineKey, awayLineKey: lineKey };
}

/** Odd do lado no handicap FT, incluindo par espelhado da Superbet. */
export function handicapOddForSide(
  handicap: Record<string, { home?: number; away?: number }> | undefined,
  side: "home" | "away",
  lineKey: string,
): number | null {
  if (!handicap) return null;
  const direct = handicap[lineKey]?.[side];
  if (direct != null) return direct;
  const { homeLineKey, awayLineKey } = pairedHandicapKeys(lineKey);
  const pairedKey = side === "home" ? homeLineKey : awayLineKey;
  return handicap[pairedKey]?.[side] ?? null;
}

/** Escolhe a linha principal (0 ou a mais próxima de 0). */
export function pickPrimaryHandicapLine(lines: string[]): string | null {
  if (lines.length === 0) return null;
  if (lines.includes("0")) return "0";
  const negative = lines.filter((k) => k.startsWith("m"));
  if (negative.length > 0) {
    return [...negative].sort((a, b) => lineAbs(a) - lineAbs(b))[0] ?? null;
  }
  return [...lines].sort((a, b) => lineAbs(a) - lineAbs(b))[0] ?? null;
}

export function modelProbKey(side: "home" | "away", lineKey: string): string {
  return `${side}_${lineKey}`;
}

/** Texto explicando botão Superbet vs linha “vitória pura” (−0.5). */
export function superbetHandicapHelp(
  homeTeam: string,
  awayTeam: string,
  homeLineKey: string,
  awayLineKey: string,
): string {
  const homeLine = formatHandicapLineKey(homeLineKey);
  const awayLine = formatHandicapLineKey(awayLineKey);
  if (homeLineKey === awayLineKey) {
    return `Handicap ${homeLine} · probabilidades condicionadas ao placar ao vivo.`;
  }
  return (
    `Na Superbet: ${homeTeam} ${homeLine} ↔ ${awayTeam} ${awayLine}. ` +
    `${awayTeam} ${awayLine} cobre empate ou vitória; ${awayTeam} −0,5 (vitória pura) ` +
    `não é o mesmo botão — veja linha tracejada no gráfico.`
  );
}
