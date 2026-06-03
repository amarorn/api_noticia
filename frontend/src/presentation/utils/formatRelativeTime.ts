export function formatRelativeTime(iso: string | null): string {
  if (!iso) return "Data não informada";

  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Data não informada";

  const diffMs = Date.now() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return "agora";
  if (diffMin < 60) return `há ${diffMin} min`;
  if (diffHour < 24) return `há ${diffHour}h`;
  if (diffDay < 7) return `há ${diffDay} dia${diffDay > 1 ? "s" : ""}`;

  return date.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
    year: date.getFullYear() !== new Date().getFullYear() ? "numeric" : undefined,
  });
}
