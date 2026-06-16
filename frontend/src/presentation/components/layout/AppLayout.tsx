import { useEffect, useState } from "react";
import { useLocation, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getHealthUseCase } from "@/application/container";
import { AppSidebar } from "./AppSidebar";
import { AppMobileHeader } from "./AppMobileHeader";
import { PageBreadcrumb } from "./PageBreadcrumb";
import { AmbientBackground } from "./AmbientBackground";
import { AnimatedOutlet } from "./AnimatedOutlet";
import { ApiOfflineBanner } from "./ApiOfflineBanner";
import { ToastContainer } from "@/presentation/components/ui/toast";
import { allNavItems } from "./navConfig";

export function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [bannerDismissed, setBannerDismissed] = useState(false);
  const location = useLocation();

  const {
    data: health,
    isError: healthError,
    isPending: healthPending,
    refetch: refetchHealth,
  } = useQuery({
    queryKey: ["health"],
    queryFn: () => getHealthUseCase.execute(),
    staleTime: 60_000,
    retry: 1,
  });

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!healthError) {
      setBannerDismissed(false);
    }
  }, [healthError]);

  useEffect(() => {
    document.title = pageTitle(location.pathname);
  }, [location.pathname]);

  return (
    <div className="min-h-screen">
      <a href="#main-content" className="skip-link">
        Ir para o conteúdo
      </a>

      <ToastContainer />
      <AmbientBackground />

      <AppSidebar
        health={health}
        healthPending={healthPending}
        healthError={healthError}
      />

      <div className="relative flex min-h-screen flex-col lg:pl-64">
        <AppMobileHeader
          mobileOpen={mobileOpen}
          onToggle={() => setMobileOpen((v) => !v)}
          onClose={() => setMobileOpen(false)}
          health={health}
          healthPending={healthPending}
          healthError={healthError}
        />

        <main
          id="main-content"
          className="relative mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 sm:py-8"
        >
          {!healthPending && healthError && !bannerDismissed && (
            <ApiOfflineBanner
              onRetry={() => refetchHealth()}
              onDismiss={() => setBannerDismissed(true)}
            />
          )}
          <PageBreadcrumb />
          <AnimatedOutlet />
        </main>

        <footer className="relative border-t border-white/[0.06] px-4 py-6 sm:px-6">
          <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-3 sm:flex-row">
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-neon-green/40" />
              <p className="font-display text-xs tracking-wide text-slate-500">
                Bolão AI · Dixon-Coles + Logística + KXL
              </p>
            </div>
            <nav className="flex flex-wrap justify-center gap-x-4 gap-y-1" aria-label="Rodapé">
              {allNavItems.slice(0, 4).map(({ to, label }) => (
                <Link
                  key={to}
                  to={to}
                  className="text-xs text-slate-500 transition-colors duration-200 hover:text-neon-green focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon-green/40 rounded"
                >
                  {label}
                </Link>
              ))}
            </nav>
          </div>
        </footer>
      </div>
    </div>
  );
}

function pageTitle(pathname: string): string {
  const item = allNavItems.find((nav) =>
    nav.end ? pathname === nav.to : pathname.startsWith(nav.to) && nav.to !== "/",
  );
  if (pathname === "/" || !item) {
    return item?.label ? `${item.label} · Bolão AI` : "Bolão AI — Previsões Esportivas";
  }
  return `${item.label} · Bolão AI`;
}
