import { NavLink } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { navGroups } from "./navConfig";
import { ApiStatusBadge } from "./ApiStatusBadge";
import { BrandMark } from "./BrandMark";
import { IconMenu, IconX } from "@/presentation/components/ui/Icons";
import { springSoft } from "@/presentation/theme/motion";
import type { HealthStatus } from "@/domain/entities";

interface AppMobileHeaderProps {
  mobileOpen: boolean;
  onToggle: () => void;
  onClose: () => void;
  health: HealthStatus | undefined;
  healthPending: boolean;
  healthError: boolean;
}

export function AppMobileHeader({
  mobileOpen,
  onToggle,
  onClose,
  health,
  healthPending,
  healthError,
}: AppMobileHeaderProps) {
  return (
    <header className="sticky top-0 z-50 border-b border-white/[0.06] bg-surface/85 backdrop-blur-2xl lg:hidden">
      <div className="flex items-center gap-3 px-4 py-3">
        <NavLink
          to="/"
          className="flex min-w-0 flex-1 items-center gap-2.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon-green/40 rounded-lg"
          onClick={onClose}
        >
          <BrandMark size="sm" />
          <div className="min-w-0">
            <p className="truncate font-display text-sm font-bold gradient-text">Bolão AI</p>
            <p className="text-[10px] uppercase tracking-[0.15em] text-slate-500">Copa 2026</p>
          </div>
        </NavLink>

        <ApiStatusBadge
          health={health}
          isPending={healthPending}
          isError={healthError}
          compact
        />

        <button
          type="button"
          onClick={onToggle}
          className="btn-icon shrink-0"
          aria-expanded={mobileOpen}
          aria-controls="mobile-nav"
          aria-label={mobileOpen ? "Fechar menu" : "Abrir menu"}
        >
          {mobileOpen ? <IconX /> : <IconMenu />}
        </button>
      </div>

      <AnimatePresence>
        {mobileOpen && (
          <motion.nav
            id="mobile-nav"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={springSoft}
            className="overflow-hidden border-t border-white/[0.06] bg-surface/95 backdrop-blur-xl"
            aria-label="Principal"
          >
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ delay: 0.05 }}
              className="max-h-[70vh] overflow-y-auto px-3 py-3 scrollbar-thin"
            >
              {navGroups.map((group, gi) => (
                <motion.div
                  key={group.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.04 * gi }}
                  className="mb-4 last:mb-0"
                >
                  <p className="mb-2 px-2 font-display text-[11px] font-bold uppercase tracking-[0.12em] text-slate-500">
                    {group.label}
                  </p>
                  <div className="grid grid-cols-2 gap-1.5">
                    {group.items.map(({ to, label, end, Icon }) => (
                      <NavLink
                        key={to}
                        to={to}
                        end={end}
                        onClick={onClose}
                        className={({ isActive }) =>
                          `flex flex-col items-center gap-1.5 rounded-xl px-2 py-3 text-center transition-all duration-200 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon-green/40 ${
                            isActive
                              ? "bg-neon-green/10 text-white ring-1 ring-neon-green/25 shadow-[0_0_16px_rgba(0,255,136,0.1)]"
                              : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                          }`
                        }
                      >
                        <Icon className="h-5 w-5" aria-hidden />
                        <span className="text-[10px] font-medium leading-tight">{label}</span>
                      </NavLink>
                    ))}
                  </div>
                </motion.div>
              ))}
            </motion.div>

            <div className="border-t border-white/5 px-4 py-3">
              <ApiStatusBadge
                health={health}
                isPending={healthPending}
                isError={healthError}
              />
            </div>
          </motion.nav>
        )}
      </AnimatePresence>
    </header>
  );
}
