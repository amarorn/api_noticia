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
    <aside
      className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col backdrop-blur-2xl lg:flex"
      style={{
        background: "rgba(5, 8, 17, 0.92)",
        borderRight: "1px solid rgba(0, 245, 160, 0.08)",
        boxShadow: "8px 0 40px rgba(0,0,0,0.50), inset -1px 0 0 rgba(0, 245, 160, 0.04)",
      }}
    >
      <div className="flex h-full flex-col">
        {/* Header da Sidebar */}
        <div className="relative">
          {/* Cantos decorativos */}
          <div className="absolute right-0 top-0 h-4 w-4 border-r border-t border-neon-green/20 rounded-tr-md" />

          <NavLink
            to="/"
            className="flex items-center gap-3 px-5 py-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon-green/40 transition-colors"
            style={{ borderBottom: "1px solid rgba(0, 245, 160, 0.08)" }}
          >
            <BrandMark />
            <div>
              <p className="font-display text-base font-bold gradient-text-cli leading-tight">
                Bolão AI
              </p>
              <p className="font-mono text-[10px] uppercase tracking-widest" style={{ color: "#475569" }}>
                Previsões esportivas
              </p>
            </div>
          </NavLink>
        </div>

        {/* Navegação */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 scrollbar-thin" aria-label="Principal">
          {navGroups.map((group) => (
            <div key={group.id} className="mb-5 last:mb-0">
              {/* Rótulo do grupo com linha decorativa CLI */}
              <div className="mb-2 flex items-center gap-2 px-3">
                <span className="font-mono text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: "#475569" }}>
                  {group.label}
                </span>
                <span
                  className="h-px flex-1"
                  style={{ background: "linear-gradient(to right, rgba(0, 245, 160, 0.12), transparent)" }}
                />
              </div>

              <ul className="space-y-0.5">
                {group.items.map(({ to, label, end, Icon }) => (
                  <li key={to}>
                    <NavLink
                      to={to}
                      end={end}
                      className="nav-link group relative flex items-center gap-3 rounded-xl px-3 py-2.5 transition-all duration-200"
                    >
                      {({ isActive }) => (
                        <>
                          {isActive && (
                            <motion.span
                              layoutId="sidebar-active"
                              className="absolute inset-0 rounded-xl"
                              transition={{ type: "spring", stiffness: 380, damping: 32 }}
                              style={{
                                background: "rgba(0, 245, 160, 0.08)",
                                border: "1px solid rgba(0, 245, 160, 0.18)",
                                boxShadow: "inset 3px 0 0 0 #00f5a0, 0 0 24px rgba(0,245,160,0.08)",
                              }}
                            />
                          )}

                          {/* Ícone com fundo arrojado quando ativo */}
                          <span
                            className={`relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition-all duration-200 ${
                              isActive
                                ? "text-neon-green"
                                : "text-slate-500 group-hover:text-slate-300"
                            }`}
                            style={
                              isActive
                                ? {
                                    background: "rgba(0, 245, 160, 0.12)",
                                    border: "1px solid rgba(0, 245, 160, 0.20)",
                                    boxShadow: "0 0 12px rgba(0,245,160,0.12)",
                                  }
                                : undefined
                            }
                          >
                            <Icon className="h-4 w-4" aria-hidden />
                          </span>

                          <span className="relative z-10 min-w-0 flex-1">
                            <span
                              className={`block text-sm font-medium leading-tight transition-colors ${
                                isActive ? "text-white neon-text" : "text-slate-400 group-hover:text-slate-200"
                              }`}
                            >
                              {label}
                            </span>
                          </span>

                          {/* Bolinha + cursor CLI */}
                          {isActive && (
                            <span className="relative z-10 flex items-center gap-1">
                              <span
                                className="h-1.5 w-1.5 rounded-full"
                                style={{ background: "#00f5a0", boxShadow: "0 0 8px #00f5a0" }}
                              />
                              <span className="font-mono text-[10px]" style={{ color: "rgba(0, 245, 160, 0.5)" }}>
                                _
                              </span>
                            </span>
                          )}
                        </>
                      )}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        {/* Footer da Sidebar com status API */}
        <div className="relative px-4 py-4" style={{ borderTop: "1px solid rgba(0, 245, 160, 0.06)" }}>
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
