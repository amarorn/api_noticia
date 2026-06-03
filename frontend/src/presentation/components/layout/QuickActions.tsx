import { Link } from "react-router-dom";
import { IconCalendar, IconUsers, IconZap } from "@/presentation/components/ui/Icons";

const actions = [
  { to: "/jogos", label: "Ver tabela", Icon: IconCalendar },
  { to: "/convocacoes", label: "Convocações", Icon: IconUsers },
  { to: "/predict", label: "Palpite avulso", Icon: IconZap },
] as const;

export function QuickActions() {
  return (
    <div className="flex flex-wrap gap-2">
      {actions.map(({ to, label, Icon }) => (
        <Link
          key={to}
          to={to}
          className="inline-flex items-center gap-2 rounded-xl border border-white/8 bg-white/[0.04] px-3 py-2 text-xs font-medium text-slate-300 transition-all duration-200 hover:border-neon-green/25 hover:bg-neon-green/5 hover:text-neon-green active:scale-[0.98]"
        >
          <Icon className="h-3.5 w-3.5" aria-hidden />
          {label}
        </Link>
      ))}
    </div>
  );
}
