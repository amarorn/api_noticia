import type { NewsSentimentLabel } from "@/domain/entities";

const config: Record<
  NewsSentimentLabel,
  { label: string; className: string; dot: string }
> = {
  positive: {
    label: "Tom positivo",
    className: "bg-neon-green/10 text-neon-green border-neon-green/20",
    dot: "bg-neon-green",
  },
  negative: {
    label: "Tom negativo",
    className: "bg-red-500/10 text-red-300 border-red-500/20",
    dot: "bg-red-400",
  },
  neutral: {
    label: "Neutro",
    className: "bg-white/5 text-slate-400 border-white/10",
    dot: "bg-slate-500",
  },
};

export function SentimentBadge({ label }: { label: NewsSentimentLabel }) {
  const c = config[label];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${c.className}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${c.dot}`} />
      {c.label}
    </span>
  );
}
