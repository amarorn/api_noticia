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
    <div className="glass-card p-5 space-y-4">
      <Skeleton className="h-6 w-2/3" />
      <Skeleton className="h-4 w-1/2" />
      <div className="flex gap-3">
        <Skeleton className="h-24 flex-1" />
        <Skeleton className="h-24 flex-1" />
      </div>
      <Skeleton className="h-10 w-full" />
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <MatchCardSkeleton key={i} />
      ))}
    </div>
  );
}

export function NewsCardSkeleton({ tall = false }: { tall?: boolean }) {
  return (
    <div className={`glass-card space-y-4 p-5 ${tall ? "min-h-[280px]" : ""}`}>
      <div className="flex gap-2">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="h-5 w-20" />
      </div>
      <Skeleton className="h-7 w-full" />
      <Skeleton className="h-7 w-4/5" />
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-9 w-full" />
    </div>
  );
}

export function NewsFeedSkeleton() {
  return (
    <div className="space-y-6">
      <NewsCardSkeleton tall />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <NewsCardSkeleton key={i} />
        ))}
      </div>
    </div>
  );
}
