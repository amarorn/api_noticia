import { motion } from "framer-motion";

interface RoundTab {
  value: number | "all";
  label: string;
  count?: number;
}

interface RoundTabsProps {
  tabs: RoundTab[];
  active: number | "all";
  onChange: (value: number | "all") => void;
}

export function RoundTabs({ tabs, active, onChange }: RoundTabsProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {tabs.map((tab) => {
        const isActive = active === tab.value;
        return (
          <button
            key={tab.value}
            type="button"
            onClick={() => onChange(tab.value)}
            className={`relative rounded-xl px-4 py-2 text-sm font-medium transition-all duration-200 active:scale-[0.98] ${
              isActive
                ? "text-white"
                : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
            }`}
          >
            {isActive && (
              <motion.span
                layoutId="round-tab-active"
                className="absolute inset-0 rounded-xl border border-neon-green/20 bg-neon-green/10 shadow-[0_0_16px_rgba(0,255,136,0.08)]"
                transition={{ type: "spring", stiffness: 380, damping: 32 }}
              />
            )}
            <span className="relative z-10 flex items-center gap-2">
              {tab.label}
              {tab.count != null && (
                <span
                  className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
                    isActive
                      ? "bg-neon-green/20 text-neon-green"
                      : "bg-white/5 text-slate-500"
                  }`}
                >
                  {tab.count}
                </span>
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
}
