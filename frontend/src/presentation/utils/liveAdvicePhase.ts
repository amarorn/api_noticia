/** Fase do modelo in-play: Copa usa `group`; amistosos via `?source=friendly` ou `?phase=friendly`. */
export function resolveLiveAdvicePhase(searchParams: URLSearchParams): string {
  const phase = searchParams.get("phase")?.trim();
  if (phase) return phase;
  if (searchParams.get("source") === "friendly") return "friendly";
  return "group";
}
