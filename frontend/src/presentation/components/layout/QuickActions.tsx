import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { IconCalendar, IconUsers, IconZap } from "@/presentation/components/ui/Icons";

const actions = [
  { to: "/jogos", label: "Ver tabela", Icon: IconCalendar, accent: "blue" as const },
  { to: "/convocacoes", label: "Convocações", Icon: IconUsers, accent: "purple" as const },
  { to: "/predict", label: "Palpite avulso", Icon: IconZap, accent: "green" as const },
] as const;

const accentMap = {
  blue: {
    idle: "border-white/8 bg-white/[0.04] text-slate-300",
    hover: "hover:border-neon-blue/25 hover:bg-neon-blue/5 hover:text-neon-blue",
    active: "active:scale-[0.98]",
  },
  purple: {
    idle: "border-white/8 bg-white/[0.04] text-slate-300",
    hover: "hover:border-neon-purple/25 hover:bg-neon-purple/5 hover:text-neon-purple",
    active: "active:scale-[0.98]",
  },
  green: {
    idle: "border-white/8 bg-white/[0.04] text-slate-300",
    hover: "hover:border-neon-green/25 hover:bg-neon-green/5 hover:text-neon-green",
    active: "active:scale-[0.98]",
  },
};

export function QuickActions() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: 0.08 }}
      className="flex flex-wrap gap-2"
    >
      {actions.map(({ to, label, Icon, accent }) => {
        const cls = accentMap[accent];
        return (
          <Link
            key={to}
            to={to}
            className={`group inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-medium transition-all duration-300 ${cls.idle} ${cls.hover} ${cls.active}`}
          >
            <Icon className="h-3.5 w-3.5 transition-transform duration-200 group-hover:scale-110" aria-hidden />
            <span>{label}</span>
          </Link>
        );
      })}
    </motion.div>
  );
}
