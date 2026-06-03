interface FilterChipProps {
  label: string;
  active: boolean;
  onClick: () => void;
  count?: number;
}

export function FilterChip({ label, active, onClick, count }: FilterChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`chip-filter shrink-0 ${active ? "chip-filter-active" : "chip-filter-idle"}`}
    >
      {label}
      {count != null && (
        <span className="ml-1.5 text-[11px] opacity-70">({count})</span>
      )}
    </button>
  );
}

interface FilterBarProps {
  label: string;
  children: React.ReactNode;
}

export function FilterBar({ label, children }: FilterBarProps) {
  return (
    <section className="space-y-3" aria-label={label}>
      <p className="section-label">{label}</p>
      <div className="relative -mx-1">
        <div className="flex gap-2 overflow-x-auto px-1 pb-1 scrollbar-thin snap-x snap-mandatory">
          {children}
        </div>
        <div
          className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-surface/90 to-transparent"
          aria-hidden
        />
      </div>
    </section>
  );
}
