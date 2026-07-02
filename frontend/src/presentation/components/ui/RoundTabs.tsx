import { motion } from "framer-motion";
import { LiveDashboardTabs } from "@/presentation/components/live-dashboard/LiveDashboardTabs";

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
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="-mx-2 sm:-mx-4"
    >
      <LiveDashboardTabs
        tabs={tabs.map((tab) => ({
          id: String(tab.value),
          label: tab.label,
          count: tab.count,
        }))}
        activeId={String(active)}
        onChange={(id) => onChange(id === "all" ? "all" : Number(id))}
      />
    </motion.div>
  );
}
