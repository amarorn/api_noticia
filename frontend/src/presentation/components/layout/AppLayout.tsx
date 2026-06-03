import { NavLink, Outlet } from "react-router-dom";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { getHealthUseCase } from "@/application/container";

const navItems = [
  { to: "/", label: "Dashboard WC", end: true },
  { to: "/news", label: "Notícias" },
  { to: "/predict", label: "Palpite avulso" },
  { to: "/validate", label: "Validar histórico" },
  { to: "/brasileirao", label: "Brasileirão" },
];

export function AppLayout() {
  const { data: health, isError: healthError, isPending: healthPending } = useQuery({
    queryKey: ["health"],
    queryFn: () => getHealthUseCase.execute(),
    staleTime: 60_000,
    retry: 1,
  });

  return (
    <div className="min-h-screen">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -left-32 top-0 h-96 w-96 rounded-full bg-neon-purple/10 blur-3xl" />
        <div className="absolute -right-32 top-1/3 h-96 w-96 rounded-full bg-neon-blue/10 blur-3xl" />
        <div className="absolute bottom-0 left-1/3 h-64 w-64 rounded-full bg-neon-green/10 blur-3xl" />
      </div>

      <header className="sticky top-0 z-50 border-b border-white/5 bg-surface/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <NavLink to="/" className="flex items-center gap-3">
            <motion.div
              whileHover={{ rotate: 180 }}
              transition={{ duration: 0.5 }}
              className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-neon-green to-neon-blue text-lg font-black text-surface"
            >
              AI
            </motion.div>
            <div>
              <p className="text-lg font-bold gradient-text leading-tight">Bolão AI</p>
              <p className="text-[10px] uppercase tracking-widest text-slate-500">
                Previsões esportivas
              </p>
            </div>
          </NavLink>

          <nav className="hidden items-center gap-1 md:flex">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `rounded-xl px-4 py-2 text-sm font-medium transition-all ${
                    isActive
                      ? "bg-white/10 text-white shadow-neon-blue"
                      : "text-slate-400 hover:bg-white/5 hover:text-white"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          {healthError && !healthPending && (
            <div
              className="hidden max-w-md items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-200 lg:flex"
              title="Inicie a API na porta 8000"
            >
              <span className="h-2 w-2 rounded-full bg-amber-400" />
              API offline — em outro terminal: ./scripts/dev-api.sh
            </div>
          )}
          {healthPending && (
            <div className="hidden text-xs text-slate-500 lg:block">Conectando API…</div>
          )}
          {health && (
            <div className="hidden items-center gap-2 rounded-xl border border-neon-green/20 bg-neon-green/5 px-3 py-1.5 text-xs lg:flex">
              <span className="h-2 w-2 animate-pulse rounded-full bg-neon-green" />
              <span className="text-neon-green">Online</span>
              <span className="text-slate-500">|</span>
              <span className="text-slate-400">{health.articlesSilver} artigos</span>
            </div>
          )}
        </div>

        <nav className="flex gap-1 overflow-x-auto border-t border-white/5 px-4 py-2 md:hidden">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-medium ${
                  isActive ? "bg-white/10 text-white" : "text-slate-400"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="relative mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <Outlet />
      </main>

      <footer className="relative border-t border-white/5 py-6 text-center text-xs text-slate-600">
        Bolão AI — Ensemble Dixon-Coles + Logística + Contexto IA
      </footer>
    </div>
  );
}
