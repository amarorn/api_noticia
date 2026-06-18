import type { SuperbetLiveAdvice } from "@/domain/entities";
import { SCOREALARM_GOAL_EVENT_TYPE } from "@/presentation/utils/liveTimelineReactive";

interface LiveTimelinePanelProps {
  data: SuperbetLiveAdvice;
  /** Minuto do gol que disparou refetch reativo (destaque visual). */
  highlightGoalMinute?: number | null;
  reactiveBoosted?: boolean;
}

/** Timeline de eventos ao vivo (ScoreAlarm overview). */
export function LiveTimelinePanel({
  data,
  highlightGoalMinute = null,
  reactiveBoosted = false,
}: LiveTimelinePanelProps) {
  const ctx = data.scorealarm;
  const events = ctx?.timeline ?? [];
  if (!ctx?.available || events.length === 0) return null;

  return (
    <section className="glass-card p-3" aria-label="Timeline de eventos">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Timeline ao vivo
        </h2>
        {reactiveBoosted && (
          <span className="rounded-full border border-neon-green/30 bg-neon-green/10 px-2 py-0.5 text-[10px] font-semibold text-neon-green">
            Poll acelerado pós-gol
          </span>
        )}
        {ctx.stale && (
          <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-300">
            Cache ScoreAlarm
          </span>
        )}
      </div>

      <ol className="max-h-56 space-y-1.5 overflow-y-auto pr-1">
        {events.map((ev, idx) => {
          const isFreshGoal =
            ev.type === SCOREALARM_GOAL_EVENT_TYPE &&
            highlightGoalMinute != null &&
            ev.minute === highlightGoalMinute &&
            idx === 0;
          return (
          <li
            key={`${ev.minute}-${ev.type}-${ev.team}-${idx}`}
            className={`flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-xs ${
              isFreshGoal
                ? "border-neon-green/40 bg-neon-green/10"
                : "border-white/6 bg-white/[0.02]"
            }`}
          >
            <span className="w-10 shrink-0 font-mono font-bold text-amber-300">
              {ev.minute}&apos;
            </span>
            <span className="shrink-0 text-base leading-none" aria-hidden="true">
              {ev.icon}
            </span>
            <span className="min-w-0 flex-1 truncate text-slate-200">
              <span className="text-slate-400">{ev.label}</span>
              {ev.team ? (
                <>
                  {" "}
                  · <span className="text-white">{ev.team}</span>
                </>
              ) : null}
            </span>
            {ev.score && (
              <span className="shrink-0 font-mono text-[11px] text-neon-green">{ev.score}</span>
            )}
          </li>
          );
        })}
      </ol>
    </section>
  );
}
