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

/** Escolhe a linha principal (0 ou a mais próxima de 0). */
export function pickPrimaryHandicapLine(lines: string[]): string | null {
  if (lines.length === 0) return null;
  if (lines.includes("0")) return "0";
  return [...lines].sort((a, b) => lineAbs(a) - lineAbs(b))[0] ?? null;
}

export function modelProbKey(side: "home" | "away", lineKey: string): string {
  return `${side}_${lineKey}`;
}
