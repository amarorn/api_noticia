import { useQuery } from "@tanstack/react-query";
import { NavLink } from "react-router-dom";
import { navGroups } from "./navConfig";
import { ApiStatusBadge } from "./ApiStatusBadge";
import { BrandMark } from "./BrandMark";
import { getUserOpenBetsUseCase } from "@/application/container";
import { LIVE_TOPBAR_HEIGHT_PX } from "./liveDashboardChromeContext";
import type { HealthStatus } from "@/domain/entities";

interface AppSidebarProps {
  health: HealthStatus | undefined;
  healthPending: boolean;
  healthError: boolean;
  hideHeader?: boolean;
}

export function AppSidebar({
  health,
  healthPending,
  healthError,
  hideHeader = false,
}: AppSidebarProps) {
  const openBetsQuery = useQuery({
    queryKey: ["user-open-bets", "sidebar"],
    queryFn: () => getUserOpenBetsUseCase.execute(),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
  const latestOpenBet = openBetsQuery.data?.bets[0];

  return (
    <aside
      className={`fixed left-0 z-40 hidden w-64 flex-col lg:flex ${
        hideHeader ? "live-unified-chrome bottom-0" : "inset-y-0 h-screen backdrop-blur-2xl"
      }`}
      style={{
        top: hideHeader ? LIVE_TOPBAR_HEIGHT_PX : undefined,
        background: hideHeader ? undefined : "rgba(5, 8, 17, 0.92)",
        borderRight: "1px solid rgba(0, 245, 160, 0.08)",
        boxShadow: hideHeader
          ? "inset -1px 0 0 rgba(0, 245, 160, 0.04)"
          : "8px 0 40px rgba(0,0,0,0.50), inset -1px 0 0 rgba(0, 245, 160, 0.04)",
      }}
    >
      <div className="flex h-full flex-col">
        {!hideHeader && (
        <div className="relative">
          <div className="absolute right-0 top-0 h-4 w-4 rounded-tr-md border-r border-t border-neon-green/20" />

          <NavLink
            to="/"
            className="flex items-center gap-3 px-5 py-5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon-green/40"
            style={{ borderBottom: "1px solid rgba(0, 245, 160, 0.08)" }}
          >
            <BrandMark />
            <div>
              <p className="font-display text-base font-bold leading-tight gradient-text-cli">
                Bolão AI
              </p>
              <p className="font-mono text-[10px] uppercase tracking-widest" style={{ color: "#475569" }}>
                Previsões esportivas
              </p>
            </div>
          </NavLink>
        </div>
        )}

        <nav
          className={`flex-1 overflow-y-auto px-3 scrollbar-thin ${hideHeader ? "pt-3" : "py-4"}`}
          aria-label="Principal"
        >
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
                            <span
                              className="absolute inset-0 rounded-xl bg-neon-green/8"
                            />
                          )}

                          <span
                            className={`relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition-colors duration-200 ${
                              isActive
                                ? "bg-neon-green/15 text-neon-green"
                                : "text-slate-500 group-hover:text-slate-300"
                            }`}
                          >
                            <Icon className="h-4 w-4" aria-hidden />
                          </span>

                          <span className="relative z-10 min-w-0 flex-1">
                            <span
                              className={`block text-sm font-medium leading-tight transition-colors ${
                                isActive ? "text-white" : "text-slate-400 group-hover:text-slate-200"
                              }`}
                            >
                              {label}
                            </span>
                          </span>

                          {isActive && (
                            <span
                              className="relative z-10 h-1.5 w-1.5 shrink-0 rounded-full bg-neon-green"
                            />
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

        {/* Footer da Sidebar: estratégia ativa + status API */}
        <div className="relative space-y-3 px-4 py-4" style={{ borderTop: "1px solid rgba(0, 245, 160, 0.06)" }}>
          <div className="rounded-xl border border-neon-green/15 bg-neon-green/[0.04] px-3 py-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
              Estratégia ativa
            </p>
            <p className="mt-0.5 text-sm font-bold text-neon-green">V2 operacional</p>
            <p className="mt-1 truncate font-mono text-[10px] text-slate-500">
              {latestOpenBet
                ? `Superbet #${latestOpenBet.ticketCode ?? latestOpenBet.id}`
                : "Nenhuma aposta aberta"}
            </p>
          </div>
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
