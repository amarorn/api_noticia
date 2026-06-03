export const sourceAccent: Record<string, { bg: string; text: string; border: string }> = {
  globo_esporte: {
    bg: "bg-red-500/15",
    text: "text-red-300",
    border: "border-red-500/25",
  },
  espn_br: {
    bg: "bg-amber-500/15",
    text: "text-amber-300",
    border: "border-amber-500/25",
  },
  uol_esporte: {
    bg: "bg-yellow-500/15",
    text: "text-yellow-200",
    border: "border-yellow-500/25",
  },
  fogaonet: {
    bg: "bg-orange-500/15",
    text: "text-orange-300",
    border: "border-orange-500/25",
  },
  gazeta_esportiva: {
    bg: "bg-emerald-500/15",
    text: "text-emerald-300",
    border: "border-emerald-500/25",
  },
};

export function sourceStyles(sourceId: string) {
  return (
    sourceAccent[sourceId] ?? {
      bg: "bg-white/10",
      text: "text-slate-300",
      border: "border-white/15",
    }
  );
}
