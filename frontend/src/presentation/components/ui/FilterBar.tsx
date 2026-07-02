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
    <section className="live-glass-panel space-y-2.5 px-3 py-3 sm:px-4" aria-label={label}>
      <p className="section-label">{label}</p>
      <div className="relative -mx-0.5">
        <div className="flex flex-wrap gap-2 overflow-x-auto px-0.5 pb-0.5 scrollbar-thin snap-x snap-mandatory">
          {children}
        </div>
        <div
          className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-[rgba(10,16,32,0.9)] to-transparent sm:hidden"
          aria-hidden
        />
      </div>
    </section>
  );
}
