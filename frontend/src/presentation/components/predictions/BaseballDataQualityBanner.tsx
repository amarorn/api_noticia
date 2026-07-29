import type { BaseballSuperbetLiveAdvice } from "@/domain/entities";
import type { BaseballAdviceSource } from "@/presentation/utils/baseballLiveMerge";
import {
  buildBaseballDataQuality,
  type BaseballQualityLevel,
} from "@/presentation/utils/baseballOperationalUtils";

const LEVEL_STYLES: Record<
  BaseballQualityLevel,
  { border: string; bg: string; title: string; dot: string }
> = {
  ok: {
    border: "border-emerald-500/25",
    bg: "bg-emerald-500/5",
    title: "text-emerald-300",
    dot: "bg-emerald-400",
  },
  caution: {
    border: "border-amber-500/25",
    bg: "bg-amber-500/5",
    title: "text-amber-300",
    dot: "bg-amber-400",
  },
  warning: {
    border: "border-rose-500/30",
    bg: "bg-rose-500/5",
    title: "text-rose-300",
    dot: "bg-rose-400",
  },
  blocked: {
    border: "border-red-500/30",
    bg: "bg-red-500/10",
    title: "text-red-300",
    dot: "bg-red-400",
  },
};

const TONE_STYLES = {
  ok: "text-emerald-300/90",
  warn: "text-amber-300/90",
  bad: "text-rose-300/90",
  muted: "text-slate-500",
} as const;

interface BaseballDataQualityBannerProps {
  data: BaseballSuperbetLiveAdvice;
  adviceSource?: BaseballAdviceSource | null;
  scoreIsFresh?: boolean;
  capturedAt?: string | null;
}

export function BaseballDataQualityBanner({
  data,
  adviceSource,
  scoreIsFresh,
  capturedAt,
}: BaseballDataQualityBannerProps) {
  const quality = buildBaseballDataQuality(data, {
    adviceSource,
    scoreIsFresh,
    capturedAt,
  });
  const styles = LEVEL_STYLES[quality.level];

  return (
    <section
      className={`rounded-xl border px-4 py-3 ${styles.border} ${styles.bg}`}
      aria-label="Qualidade operacional dos dados"
    >
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className={`flex items-center gap-2 text-sm font-semibold ${styles.title}`}>
            <span className={`h-2 w-2 rounded-full ${styles.dot}`} aria-hidden />
            {quality.title}
          </div>
          <p className="mt-0.5 text-xs text-slate-400">{quality.subtitle}</p>
        </div>
        {data.gamePhase ? (
          <span className="rounded-full border border-white/10 bg-black/30 px-2.5 py-1 text-[10px] uppercase tracking-wide text-slate-300">
            {data.gamePhase.phase.replace(/_/g, " ")}
          </span>
        ) : null}
      </div>
      <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {quality.items.map((item) => (
          <li
            key={item.label}
            className="rounded-lg border border-white/[0.06] bg-black/20 px-3 py-2"
          >
            <div className={`text-[10px] font-semibold uppercase tracking-wider ${TONE_STYLES[item.tone]}`}>
              {item.label}
            </div>
            <div className="mt-0.5 text-xs text-slate-300">{item.detail}</div>
          </li>
        ))}
      </ul>
    </section>
  );
}
