interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className = "" }: SkeletonProps) {
  return (
    <div
      className={`live-skeleton-shimmer rounded-xl ${className}`}
      aria-hidden
    />
  );
}

export function MatchScoreboardSkeleton() {
  return (
    <div className="live-scoreboard mx-2 mt-2 sm:mx-4">
      <div className="relative flex items-center justify-between gap-4 px-5 py-4">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <Skeleton className="h-12 w-12 shrink-0 rounded-full" />
          <Skeleton className="h-5 w-28 max-w-full" />
        </div>
        <div className="flex shrink-0 flex-col items-center gap-2 px-2">
          <Skeleton className="h-10 w-24 rounded-lg" />
          <Skeleton className="h-3 w-20 rounded-full" />
        </div>
        <div className="flex min-w-0 flex-1 items-center justify-end gap-3">
          <Skeleton className="hidden h-5 w-28 max-w-full sm:block" />
          <Skeleton className="h-12 w-12 shrink-0 rounded-full" />
        </div>
      </div>
      <div className="px-5 pb-5 pt-1">
        <Skeleton className="h-1.5 w-full rounded-full" />
      </div>
    </div>
  );
}

export function LiveDashboardContentSkeleton() {
  return (
    <div className="space-y-4 animate-fade-in">
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="live-glass-panel-glow glow-border p-4">
          <div className="mb-4 flex items-center gap-2">
            <Skeleton className="h-4 w-36" />
            <Skeleton className="h-5 w-16 rounded-full" />
          </div>
          <div className="mb-4 flex items-end justify-between gap-4">
            <div className="space-y-2">
              <Skeleton className="h-9 w-16" />
              <Skeleton className="h-3 w-24" />
            </div>
            <div className="space-y-2 text-right">
              <Skeleton className="ml-auto h-9 w-16" />
              <Skeleton className="ml-auto h-3 w-24" />
            </div>
          </div>
          <Skeleton className="h-48 w-full rounded-xl" />
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="live-kpi-card">
              <Skeleton className="h-7 w-7 rounded-lg" />
              <Skeleton className="mt-2 h-3 w-20" />
              <Skeleton className="mt-2 h-8 w-14" />
              <Skeleton className="mt-2 h-3 w-full" />
            </div>
          ))}
        </div>
      </div>

      <div className="live-glass-panel p-4">
        <div className="mb-3 flex items-center justify-between">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-5 w-8 rounded-full" />
        </div>
        <div className="flex gap-3 overflow-hidden">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="min-w-[220px] live-glass-panel p-4">
              <Skeleton className="h-3 w-12" />
              <Skeleton className="mt-3 h-4 w-full" />
              <Skeleton className="mt-2 h-3 w-24" />
              <div className="mt-4 flex justify-between">
                <Skeleton className="h-8 w-16" />
                <Skeleton className="h-10 w-10 rounded-full" />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="live-glass-panel overflow-hidden">
        <div className="flex items-center justify-between border-b border-white/[0.04] px-4 py-3">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-7 w-52 rounded-lg" />
        </div>
        <div className="space-y-2 p-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full rounded-lg" />
          ))}
        </div>
      </div>

      <div className="live-glass-panel flex items-center justify-center gap-2 px-4 py-2.5">
        <Skeleton className="h-3 w-3 rounded-full" />
        <Skeleton className="h-3 w-64" />
      </div>
    </div>
  );
}

export function MatchCardSkeleton() {
  return (
    <div className="glass-card p-4 space-y-3">
      <Skeleton className="h-5 w-2/3" />
      <Skeleton className="h-3 w-1/2" />
      <div className="flex gap-2">
        <Skeleton className="h-20 flex-1 rounded-lg" />
        <Skeleton className="h-20 flex-1 rounded-lg" />
      </div>
      <Skeleton className="h-8 w-full rounded-lg" />
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <MatchCardSkeleton key={i} />
      ))}
    </div>
  );
}

export function BasketLiveContentSkeleton() {
  return (
    <div className="space-y-4 animate-fade-in">
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="live-glass-panel-glow glow-border p-4">
          <Skeleton className="mb-4 h-4 w-40" />
          <div className="mb-4 grid grid-cols-2 gap-4">
            <Skeleton className="h-16 rounded-xl" />
            <Skeleton className="h-16 rounded-xl" />
          </div>
          <Skeleton className="h-44 w-full rounded-xl" />
        </div>
        <div className="grid grid-cols-2 gap-2 xl:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="live-kpi-card">
              <Skeleton className="h-7 w-7 rounded-lg" />
              <Skeleton className="mt-2 h-3 w-20" />
              <Skeleton className="mt-2 h-8 w-14" />
              <Skeleton className="mt-2 h-3 w-full" />
            </div>
          ))}
        </div>
      </div>
      <div className="live-glass-panel p-4">
        <Skeleton className="mb-3 h-4 w-48" />
        <div className="flex gap-3 overflow-hidden">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="min-w-[220px] live-glass-panel p-4">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="mt-3 h-8 w-16" />
            </div>
          ))}
        </div>
      </div>
      <div className="live-glass-panel overflow-hidden p-4">
        <Skeleton className="mb-3 h-4 w-44" />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="mb-2 h-10 w-full rounded-lg" />
        ))}
      </div>
    </div>
  );
}

export function LiveMatchSkeleton() {
  return (
    <div className="space-y-3">
      {/* Header do jogo */}
      <div className="glass-card p-3 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 flex-1">
            <Skeleton className="h-8 w-8 rounded-lg" />
            <Skeleton className="h-4 w-24" />
          </div>
          <div className="text-center px-2">
            <Skeleton className="h-8 w-16 mx-auto" />
            <Skeleton className="h-3 w-12 mx-auto mt-1" />
          </div>
          <div className="flex items-center gap-2 flex-1 justify-end">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-8 w-8 rounded-lg" />
          </div>
        </div>
        <Skeleton className="h-6 w-full rounded-lg" />
      </div>
      {/* Cards de mercado */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-3">
        <div className="glass-card p-3 space-y-3">
          <Skeleton className="h-4 w-32" />
          <div className="grid grid-cols-3 gap-2">
            <Skeleton className="h-20 rounded-lg" />
            <Skeleton className="h-20 rounded-lg" />
            <Skeleton className="h-20 rounded-lg" />
          </div>
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </div>
        <div className="glass-card p-3 space-y-3">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-32 rounded-lg" />
          <Skeleton className="h-4 w-full" />
        </div>
      </div>
    </div>
  );
}

export function NewsCardSkeleton({ tall = false }: { tall?: boolean }) {
  return (
    <div className={`glass-card space-y-3 p-4 ${tall ? "min-h-[240px]" : ""}`}>
      <div className="flex gap-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-20" />
      </div>
      <Skeleton className="h-6 w-full" />
      <Skeleton className="h-6 w-4/5" />
      <Skeleton className="h-14 w-full" />
      <Skeleton className="h-8 w-full" />
    </div>
  );
}

export function NewsFeedSkeleton() {
  return (
    <div className="space-y-4">
      <NewsCardSkeleton tall />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <NewsCardSkeleton key={i} />
        ))}
      </div>
    </div>
  );
}
