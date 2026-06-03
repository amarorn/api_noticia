import { NavLink } from "react-router-dom";
import { motion } from "framer-motion";
import { navGroups } from "./navConfig";
import { ApiStatusBadge } from "./ApiStatusBadge";
import { BrandMark } from "./BrandMark";
import type { HealthStatus } from "@/domain/entities";

interface AppSidebarProps {
  health: HealthStatus | undefined;
  healthPending: boolean;
  healthError: boolean;
}

export function AppSidebar({ health, healthPending, healthError }: AppSidebarProps) {
  return (
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col border-r border-white/[0.06] bg-surface/80 backdrop-blur-2xl lg:flex">
      <div className="flex h-full flex-col">
        <NavLink
          to="/"
          className="flex items-center gap-3 border-b border-white/[0.06] px-5 py-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon-green/40"
        >
          <BrandMark />
          <div>
            <p className="font-display text-base font-bold gradient-text-animated leading-tight">
              Bolão AI
            </p>
            <p className="text-[9px] uppercase tracking-[0.2em] text-slate-600">
              Previsões esportivas
            </p>
          </div>
        </NavLink>

        <nav className="flex-1 overflow-y-auto px-3 py-4 scrollbar-thin" aria-label="Principal">
          {navGroups.map((group) => (
            <div key={group.id} className="mb-5 last:mb-0">
              <p className="mb-2 px-3 font-display text-[10px] font-bold uppercase tracking-[0.18em] text-slate-600">
                {group.label}
              </p>
              <ul className="space-y-0.5">
                {group.items.map(({ to, label, end, Icon, description }) => (
                  <li key={to}>
                    <NavLink
                      to={to}
                      end={end}
                      className="nav-link group relative flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors duration-200"
                    >
                      {({ isActive }) => (
                        <>
                          {isActive && (
                            <motion.span
                              layoutId="sidebar-active"
                              className="absolute inset-0 rounded-xl border border-neon-green/20 bg-neon-green/10 shadow-[inset_3px_0_0_0_#00ff88,0_0_20px_rgba(0,255,136,0.08)]"
                              transition={{ type: "spring", stiffness: 380, damping: 32 }}
                            />
                          )}
                          <Icon
                            className={`nav-link-icon relative z-10 h-4 w-4 shrink-0 transition-colors duration-200 ${
                              isActive ? "text-neon-green" : "text-slate-500 group-hover:text-slate-300"
                            }`}
                            aria-hidden
                          />
                          <span className="relative z-10 min-w-0 flex-1">
                            <span
                              className={`block text-sm font-medium leading-tight transition-colors ${
                                isActive ? "text-white" : "text-slate-400 group-hover:text-slate-200"
                              }`}
                            >
                              {label}
                            </span>
                            {description && (
                              <span className="block truncate text-[10px] text-slate-600 group-hover:text-slate-500">
                                {description}
                              </span>
                            )}
                          </span>
                        </>
                      )}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        <div className="border-t border-white/[0.06] px-4 py-4">
          <ApiStatusBadge
            health={health}
            isPending={healthPending}
            isError={healthError}
          />
        </div>
      </div>
    </aside>
  );
}
