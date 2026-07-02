import { useEffect, useState, useCallback, useMemo } from "react";
import { useLocation, Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getHealthUseCase, getWcScheduleUseCase } from "@/application/container";
import { AppSidebar } from "./AppSidebar";
import { AppMobileHeader } from "./AppMobileHeader";
import { PageBreadcrumb } from "./PageBreadcrumb";
import { AmbientBackground } from "./AmbientBackground";
import { AnimatedOutlet } from "./AnimatedOutlet";
import { ApiOfflineBanner } from "./ApiOfflineBanner";
import { ToastContainer } from "@/presentation/components/ui/toast";
import { allNavItems } from "./navConfig";
import { AppShellContext } from "./appShellContext";
import { LiveDashboardChromeProvider, useLiveDashboardChromeOptional } from "./liveDashboardChromeContext";
import { LiveDashboardTopBar } from "@/presentation/components/live-dashboard/LiveDashboardTopBar";

export function AppLayout() {
  return (
    <LiveDashboardChromeProvider>
      <AppLayoutInner />
    </LiveDashboardChromeProvider>
  );
}

function AppLayoutInner() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [bannerDismissed, setBannerDismissed] = useState(false);
  const [showScrollTop, setShowScrollTop] = useState(false);
  const location = useLocation();
  const queryClient = useQueryClient();
  const isBasketLiveDashboard = /^\/ao-vivo\/basquete\/[^/]+$/.test(location.pathname);
  const isFootballLiveDashboard =
    /^\/ao-vivo\/[^/]+$/.test(location.pathname) &&
    !location.pathname.includes("/basquete/");
  const isLiveDashboard = isFootballLiveDashboard || isBasketLiveDashboard;

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

  // Monitora scroll para mostrar botão voltar ao topo
  const handleScroll = useCallback((e: React.UIEvent<HTMLElement>) => {
    const target = e.currentTarget;
    setShowScrollTop(target.scrollTop > 400);
    // Persiste posição de scroll para navegação de volta
    sessionStorage.setItem(`scroll:${location.pathname}`, String(target.scrollTop));
  }, [location.pathname]);

  // Restaura scroll ao voltar; em rota nova, força topo (evita “página em branco”)
  useEffect(() => {
    const main = document.getElementById("main-scroll");
    if (!main) return;
    if (location.state?.noScroll) return;

    const saved = sessionStorage.getItem(`scroll:${location.pathname}`);
    if (saved) {
      main.scrollTop = Number(saved);
    } else {
      main.scrollTop = 0;
      window.scrollTo({ top: 0, behavior: "instant" });
    }
  }, [location.pathname, location.key, location.state]);

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

  // Pré-carrega calendário WC em background — Jogos abre rápido na sidebar
  useEffect(() => {
    void queryClient.prefetchQuery({
      queryKey: ["wc-schedule"],
      queryFn: () => getWcScheduleUseCase.execute(),
      staleTime: 10 * 60_000,
    });
  }, [queryClient]);

  const scrollToTop = useCallback(() => {
    const main = document.getElementById("main-scroll");
    if (main) {
      main.scrollTo({ top: 0, behavior: "smooth" });
    }
  }, []);

  const toggleMobileNav = useCallback(() => setMobileOpen((v) => !v), []);

  const shellValue = useMemo(() => ({ toggleMobileNav }), [toggleMobileNav]);
  const liveChrome = useLiveDashboardChromeOptional()?.chrome;

  return (
    <AppShellContext.Provider value={shellValue}>
    <div className={`flex h-screen w-screen overflow-hidden ${isLiveDashboard ? "flex-col bg-transparent" : "bg-surface"}`}>
      <a href="#main-content" className="skip-link">
        Ir para o conteúdo
      </a>

      {/* Scanline overlay CLI */}
      <div className="scanline-overlay" aria-hidden />

      <ToastContainer />
      <AmbientBackground />

      {isLiveDashboard && liveChrome && (
        <LiveDashboardTopBar
          isLive={liveChrome.isLive}
          lastUpdate={liveChrome.lastUpdate}
          nextUpdate={liveChrome.nextUpdate}
          isFetching={liveChrome.isFetching}
          onRefresh={liveChrome.onRefresh}
          onMenu={toggleMobileNav}
        />
      )}

      <div className={`flex min-h-0 flex-1 overflow-hidden ${isLiveDashboard ? "" : ""}`}>
      {/* Sidebar Desktop */}
      <AppSidebar
        health={health}
        healthPending={healthPending}
        healthError={healthError}
        hideHeader={isLiveDashboard}
      />

      {/* Área de conteúdo */}
      <div className="relative flex flex-1 flex-col overflow-hidden lg:ml-64">
        {/* Mobile Header — barra oculta no dashboard ao vivo (top bar própria) */}
        <AppMobileHeader
          hideBar={isLiveDashboard}
          mobileOpen={mobileOpen}
          onToggle={() => setMobileOpen((v) => !v)}
          onClose={() => setMobileOpen(false)}
          health={health}
          healthPending={healthPending}
          healthError={healthError}
        />

        {/* Scroll wrapper com scroll inteligente */}
        <main
          id="main-scroll"
          className={`relative flex-1 overflow-y-auto overflow-x-hidden scroll-smooth scrollbar-thin ${
            isLiveDashboard ? "live-dashboard-main bg-transparent" : ""
          }`}
          onScroll={handleScroll}
        >
          {/* Breadcrumb / banner — omitido no dashboard ao vivo (header próprio) */}
          {!isLiveDashboard && (
            <div className="sticky top-0 z-30">
              <div
                className="absolute inset-0 backdrop-blur-xl"
                style={{
                  background: "linear-gradient(to bottom, rgba(5,8,17,0.95) 0%, rgba(5,8,17,0.80) 50%, transparent 100%)",
                  WebkitMaskImage: "linear-gradient(to bottom, black 0%, black 55%, transparent 100%)",
                  maskImage: "linear-gradient(to bottom, black 0%, black 55%, transparent 100%)",
                }}
              />
              <div className="relative mx-auto max-w-7xl px-4 pt-3 sm:px-6 sm:pt-4">
                {!healthPending && healthError && !bannerDismissed && (
                  <ApiOfflineBanner
                    onRetry={() => refetchHealth()}
                    onDismiss={() => setBannerDismissed(true)}
                  />
                )}
                <PageBreadcrumb />
              </div>
            </div>
          )}
          {isLiveDashboard && !healthPending && healthError && !bannerDismissed && (
            <div className="px-2 pt-2 sm:px-4">
              <ApiOfflineBanner
                onRetry={() => refetchHealth()}
                onDismiss={() => setBannerDismissed(true)}
              />
            </div>
          )}

          {/* Conteúdo da página */}
          <div
            id="main-content"
            className={`relative mx-auto pb-4 sm:pb-6 ${
              isLiveDashboard ? "max-w-none px-2 pt-0 sm:px-4" : "max-w-7xl px-4 sm:px-6"
            }`}
          >
            <AnimatedOutlet />
          </div>

          {/* Footer dentro do scroll */}
          <footer
            className={`relative z-20 border-t px-4 py-5 sm:px-6 ${isLiveDashboard ? "hidden lg:block" : ""}`}
            style={{ borderColor: "rgba(0, 245, 160, 0.06)" }}
          >
            <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-3 sm:flex-row">
              <div className="flex items-center gap-2">
                <span
                  className="h-2 w-2 rounded-full shadow-glow-sm"
                  style={{ background: "rgba(0, 245, 160, 0.6)" }}
                />
                <p className="font-mono text-xs tracking-wide text-slate-500">
                  <span style={{ color: "rgba(0, 245, 160, 0.5)" }}>{"// "}</span>
                  Bolão AI · Dixon-Coles + Logística + KXL
                </p>
              </div>
              <div className="flex items-center gap-4">
                <nav
                  className="flex flex-wrap justify-center gap-x-4 gap-y-1"
                  aria-label="Rodapé"
                >
                  {allNavItems.slice(0, 4).map(({ to, label }) => (
                    <Link
                      key={to}
                      to={to}
                      className="font-mono text-xs text-slate-500 transition-colors duration-200 hover:text-neon-green focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon-green/40 rounded"
                    >
                      {label}
                    </Link>
                  ))}
                </nav>
                <div
                  className="hidden h-3 w-px sm:block"
                  style={{ background: "rgba(0,245,160,0.15)" }}
                />
                {/* CLI Status mini */}
                <span className="font-mono text-[10px] tracking-wider text-slate-600">
                  {typeof health?.articlesSilver === "number"
                    ? `${health.articlesSilver.toLocaleString("pt-BR")} ARTICLES`
                    : "—"}
                </span>
              </div>
            </div>
          </footer>
        </main>

        {/* Botão voltar ao topo */}
        <button
          type="button"
          onClick={scrollToTop}
          aria-label="Voltar ao topo"
          className={`fixed bottom-6 right-6 z-50 flex h-10 w-10 items-center justify-center rounded-xl border border-neon-green/20 bg-surface-100/90 backdrop-blur-xl text-neon-green shadow-neon-subtle transition-all duration-300 hover:border-neon-green/40 hover:shadow-neon ${
            showScrollTop ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0 pointer-events-none"
          }`}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
          </svg>
        </button>
      </div>
      </div>
    </div>
    </AppShellContext.Provider>
  );
}

function pageTitle(pathname: string): string {
  const item = allNavItems.find((nav) =>
    nav.end ? pathname === nav.to : pathname.startsWith(nav.to) && nav.to !== "/",
  );
  if (pathname === "/" || !item) {
    return item?.label
      ? `${item.label} · Bolão AI`
      : "Bolão AI — Previsões Esportivas";
  }
  return `${item.label} · Bolão AI`;
}
