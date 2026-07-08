import type { SuperbetLiveAdvice } from "@/domain/entities";
import type { LiveAdviceScoreTick } from "@/presentation/hooks/useLiveAdviceQueries";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";
import { ChipV2 } from "./live-ui-v2";

export function LiveMatchHeaderV2({
  data,
  scoreTick,
}: {
  data: SuperbetLiveAdvice;
  scoreTick: LiveAdviceScoreTick;
}) {
  const score = scoreTick?.currentScore ?? data.currentScore ?? "0x0";
  const minute = scoreTick?.minute ?? data.minute;
  const period = scoreTick?.periodLabel ?? data.periodLabel;
  const isLive = data.isLive && !data.isFinished;
  const status = data.isFinished ? "Encerrado" : isLive ? "Ao vivo" : data.status ?? "Suspenso";
  const timelineMax = minute > 90 ? Math.max(120, minute) : 90;
  const timelinePct = Math.max(0, Math.min(100, Math.round((minute / timelineMax) * 100)));

  return (
    <header className="panel-v2 p-5 sm:p-6">
      <div className="flex min-w-0 items-center justify-between gap-4">
        <div className="flex min-w-0 flex-1 items-center justify-start gap-3 sm:gap-5">
          <TeamFlag team={data.homeTeam} size={56} />
          <span className="truncate text-lg font-bold text-white sm:text-xl">{data.homeTeam}</span>
        </div>
        <div className="shrink-0 text-center">
          <p className="font-mono text-4xl font-black tracking-tight text-white sm:text-5xl">{score.replace("x", " × ")}</p>
          <div className="mt-2 flex items-center justify-center gap-2">
            <ChipV2 label={`${minute}'${period ? ` · ${period}` : ""}`} tone="cyan" />
            <ChipV2 label={status} tone={isLive ? "green" : "slate"} />
          </div>
        </div>
        <div className="flex min-w-0 flex-1 items-center justify-end gap-3 sm:gap-5">
          <span className="truncate text-right text-lg font-bold text-white sm:text-xl">{data.awayTeam}</span>
          <TeamFlag team={data.awayTeam} size={56} />
        </div>
      </div>

      <div className="relative mt-7">
        <div className="timeline-track-v2">
          <div className="timeline-fill-v2" style={{ width: `${timelinePct}%` }} />
        </div>
        <div
          className="absolute -top-2.5 -translate-x-1/2"
          style={{ left: `${timelinePct}%` }}
        >
          <span className="pill-v2 border border-emerald-400/30 bg-emerald-400/90 text-slate-950">{minute}'</span>
        </div>
      </div>
    </header>
  );
}
