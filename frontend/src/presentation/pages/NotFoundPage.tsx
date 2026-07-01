import { Link, useLocation } from "react-router-dom";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { allNavItems } from "@/presentation/components/layout/navConfig";

export function NotFoundPage() {
  const location = useLocation();

  return (
    <PageTransition className="mx-auto max-w-lg space-y-6 py-10 text-center">
      <p className="font-mono text-xs uppercase tracking-widest text-slate-500">404</p>
      <h1 className="font-display text-2xl font-bold text-white">Página não encontrada</h1>
      <p className="text-sm text-slate-400">
        A rota <code className="rounded bg-slate-800 px-1.5 py-0.5">{location.pathname}</code> não
        existe ou foi movida.
      </p>
      <div className="flex flex-wrap justify-center gap-2">
        <Link
          to="/"
          className="rounded-lg border border-neon-green/30 bg-neon-green/10 px-4 py-2 text-sm text-neon-green"
        >
          Ir ao Dashboard
        </Link>
      </div>
      <div className="rounded-xl border border-slate-700/50 bg-slate-900/40 p-4 text-left">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
          Rotas disponíveis
        </p>
        <ul className="grid gap-1 text-sm text-slate-300 sm:grid-cols-2">
          {allNavItems.map((item) => (
            <li key={item.to}>
              <Link to={item.to} className="hover:text-neon-green">
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </PageTransition>
  );
}
