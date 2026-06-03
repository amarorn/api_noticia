import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { getHealthUseCase } from "@/application/container";
import {
  IconDashboard,
  IconNewspaper,
  IconZap,
  IconHistory,
  IconTrophy,
  IconAlbum,
  IconCalendar,
  IconUsers,
  IconMenu,
  IconX,
  IconWifi,
} from "@/presentation/components/ui/Icons";

const navItems = [
  { to: "/", label: "Dashboard WC", end: true, Icon: IconDashboard },
  { to: "/jogos", label: "Jogos", Icon: IconCalendar },
  { to: "/convocacoes", label: "Convocações", Icon: IconUsers },
  { to: "/album", label: "Álbum", Icon: IconAlbum },
  { to: "/news", label: "Notícias", Icon: IconNewspaper },
  { to: "/predict", label: "Palpite avulso", Icon: IconZap },
  { to: "/validate", label: "Histórico", Icon: IconHistory },
  { to: "/brasileirao", label: "Brasileirão", Icon: IconTrophy },
];

export function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);

  const { data: health, isError: healthError, isPending: healthPending } = useQuery({
    queryKey: ["health"],
    queryFn: () => getHealthUseCase.execute(),
    staleTime: 60_000,
    retry: 1,
  });

  return (
    <div className="min-h-screen">
      {/* Background ambient blobs */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -left-32 top-0 h-96 w-96 rounded-full bg-neon-purple/8 blur-3xl" />
        <div className="absolute -right-32 top-1/3 h-96 w-96 rounded-full bg-neon-blue/8 blur-3xl" />
        <div className="absolute bottom-0 left-1/3 h-64 w-64 rounded-full bg-neon-green/8 blur-3xl" />
      </div>

      <header className="sticky top-0 z-50 border-b border-white/[0.06] bg-surface/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 sm:px-6">
          {/* Logo */}
          <NavLink to="/" className="flex shrink-0 items-center gap-3 mr-2">
            <motion.div
              whileHover={{ rotate: 180 }}
              transition={{ duration: 0.45 }}
              className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-neon-green to-neon-blue text-sm font-black text-surface shadow-neon"
            >
              AI
            </motion.div>
            <div className="hidden sm:block">
              <p className="text-base font-bold gradient-text leading-tight">Bolão AI</p>
              <p className="text-[9px] uppercase tracking-widest text-slate-600">
                Previsões esportivas
              </p>
            </div>
          </NavLink>

          {/* Desktop nav */}
          <nav className="hidden flex-1 items-center gap-0.5 md:flex">
            {navItems.map(({ to, label, end, Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `flex items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-medium transition-all ${
                    isActive
                      ? "bg-white/10 text-white shadow-neon-blue"
                      : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                  }`
                }
              >
                <Icon className="h-3.5 w-3.5 shrink-0" />
                {label}
              </NavLink>
            ))}
          </nav>

          {/* Status badge */}
          <div className="ml-auto hidden items-center lg:flex">
            {healthError && !healthPending && (
              <div
                className="flex items-center gap-2 rounded-xl border border-amber-500/25 bg-amber-500/8 px-3 py-1.5 text-xs text-amber-300"
                title="Inicie a API na porta 8000"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
                API offline
              </div>
            )}
            {healthPending && (
              <div className="flex items-center gap-2 text-xs text-slate-600">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-600" />
                Conectando…
              </div>
            )}
            {health && (
              <div className="flex items-center gap-2 rounded-xl border border-neon-green/20 bg-neon-green/5 px-3 py-1.5 text-xs">
                <IconWifi className="h-3 w-3 text-neon-green" />
                <span className="text-neon-green font-medium">Online</span>
                <span className="text-white/20">|</span>
                <span className="text-slate-400">{health.articlesSilver} artigos</span>
              </div>
            )}
          </div>

          {/* Mobile menu button */}
          <button
            type="button"
            onClick={() => setMobileOpen((v) => !v)}
            className="btn-icon ml-auto md:hidden"
            aria-label={mobileOpen ? "Fechar menu" : "Abrir menu"}
          >
            {mobileOpen ? <IconX /> : <IconMenu />}
          </button>
        </div>

        {/* Mobile drawer */}
        <AnimatePresence>
          {mobileOpen && (
            <motion.nav
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden border-t border-white/[0.06] bg-surface/95 backdrop-blur-xl md:hidden"
            >
              <div className="grid grid-cols-2 gap-1.5 p-3 sm:grid-cols-5">
                {navItems.map(({ to, label, end, Icon }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={end}
                    onClick={() => setMobileOpen(false)}
                    className={({ isActive }) =>
                      `flex flex-col items-center gap-1.5 rounded-xl px-2 py-3 text-center transition-all ${
                        isActive
                          ? "bg-white/10 text-white"
                          : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                      }`
                    }
                  >
                    <Icon className="h-5 w-5" />
                    <span className="text-[10px] font-medium leading-tight">{label}</span>
                  </NavLink>
                ))}
              </div>

              {/* API status on mobile */}
              {health && (
                <div className="border-t border-white/5 px-4 py-2.5 text-xs text-slate-500">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-neon-green" />
                    API Online · {health.articlesSilver} artigos
                  </span>
                </div>
              )}
            </motion.nav>
          )}
        </AnimatePresence>
      </header>

      <main className="relative mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <Outlet />
      </main>

      <footer className="relative border-t border-white/[0.05] py-5 text-center text-xs text-slate-700">
        Bolão AI · Ensemble Dixon-Coles + Logística + KXL
      </footer>
    </div>
  );
}
