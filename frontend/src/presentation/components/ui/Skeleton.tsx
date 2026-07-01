interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className = "" }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse rounded-xl bg-white/5 ${className}`}
      aria-hidden
    />
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
