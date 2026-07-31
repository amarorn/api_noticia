import { NavLink } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { navGroups } from "./navConfig";
import { ApiStatusBadge } from "./ApiStatusBadge";
import { BrandMark } from "./BrandMark";
import { IconMenu, IconX } from "@/presentation/components/ui/Icons";
import { springSoft } from "@/presentation/theme/motion";
import type { HealthStatus } from "@/domain/entities";
import { NotificationBell } from "@/presentation/components/ui/notifications";

interface AppMobileHeaderProps {
  mobileOpen: boolean;
  onToggle: () => void;
  onClose: () => void;
  health: HealthStatus | undefined;
  healthPending: boolean;
  healthError: boolean;
  hideBar?: boolean;
}

export function AppMobileHeader({
  mobileOpen,
  onToggle,
  onClose,
  health,
  healthPending,
  healthError,
  hideBar = false,
}: AppMobileHeaderProps) {
  return (
    <>
    {!hideBar && (
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
            <p className="text-[10px] uppercase tracking-[0.15em] text-slate-500">Campeonatos</p>
          </div>
        </NavLink>

        <ApiStatusBadge
          health={health}
          isPending={healthPending}
          isError={healthError}
          compact
        />

        <NotificationBell buttonClassName="btn-icon relative shrink-0" />

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

    </header>
    )}

      <AnimatePresence>
        {hideBar && mobileOpen && (
          <motion.button
            type="button"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
            aria-label="Fechar menu"
            onClick={onClose}
          />
        )}
        {mobileOpen && (
          <motion.nav
            id="mobile-nav"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={springSoft}
            className={`overflow-hidden border-t border-white/[0.06] bg-surface-100/95 backdrop-blur-xl ${
              hideBar ? "fixed inset-x-0 top-0 z-50 max-h-screen border-b lg:hidden" : ""
            }`}
            aria-label="Principal"
          >
            {hideBar && (
              <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
                <p className="font-display text-sm font-bold text-white">Menu</p>
                <button type="button" onClick={onClose} className="btn-icon" aria-label="Fechar menu">
                  <IconX />
                </button>
              </div>
            )}
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
                  <div className="mb-2 flex items-center gap-2 px-2">
                    <span className="font-display text-[11px] font-bold uppercase tracking-[0.12em] text-slate-500">
                      {group.label}
                    </span>
                    <span className="h-px flex-1 bg-gradient-to-r from-white/[0.08] to-transparent" />
                  </div>
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
                        <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${{
                          false: "",
                        }}`}>
                          <Icon className="h-5 w-5" aria-hidden />
                        </span>
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
    </>
  );
}
