import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "@/presentation/components/ui/toast";
import { NotificationsProvider } from "@/presentation/components/ui/notifications";
import { AppLayout } from "@/presentation/components/layout/AppLayout";
import { DashboardPage } from "@/presentation/pages/DashboardPage";
import { PredictPage } from "@/presentation/pages/PredictPage";
import { MatchDetailPage } from "@/presentation/pages/MatchDetailPage";
import { AnalysisPage } from "@/presentation/pages/AnalysisPage";
import { HistoricalValidationPage } from "@/presentation/pages/HistoricalValidationPage";
import { HistoricoPage } from "@/presentation/pages/HistoricoPage";
import { NewsFeedPage } from "@/presentation/pages/NewsFeedPage";
import { SquadsPage } from "@/presentation/pages/SquadsPage";
import { WcGroupsPage } from "@/presentation/pages/WcGroupsPage";
import { SchedulePage } from "@/presentation/pages/SchedulePage";
import { FriendliesPage } from "@/presentation/pages/FriendliesPage";
import { LivePage } from "@/presentation/pages/LivePage";
import { LiveDashboardPage } from "@/presentation/pages/LiveDashboardPage";
import { LiveOperationalPage } from "@/presentation/pages/LiveOperationalPage";
import { BasketLiveInPlayPage } from "@/presentation/pages/BasketLiveInPlayPage";
import { BasketMultiLiveInPlayPage } from "@/presentation/pages/BasketMultiLiveInPlayPage";
import { BaseballLiveInPlayPage } from "@/presentation/pages/BaseballLiveInPlayPage";
import { AlbumPage } from "@/presentation/pages/AlbumPage";
import { TeamAlbumPage } from "@/presentation/pages/TeamAlbumPage";
import { CarteiraPage } from "@/presentation/pages/CarteiraPage";
import { BetPerformancePage } from "@/presentation/pages/BetPerformancePage";
import { BetQueryPage } from "@/presentation/pages/BetQueryPage";
import { BetSimulatorPage } from "@/presentation/pages/BetSimulatorPage";
import { ModelBenchmarkPage } from "@/presentation/pages/ModelBenchmarkPage";
import { MatchTicketsPage } from "@/presentation/pages/MatchTicketsPage";
import { PreGameAnalysisPage } from "@/presentation/pages/PreGameAnalysisPage";
import { CopaCentralPage } from "@/presentation/pages/CopaCentralPage";
import { CasinoPage } from "@/presentation/pages/CasinoPage";
import { NotFoundPage } from "@/presentation/pages/NotFoundPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 2,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <NotificationsProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<AppLayout />}>
              <Route index element={<DashboardPage />} />
              {/* Rotas PT-BR (canônicas no menu) */}
              <Route path="historico" element={<HistoricoPage />} />
              <Route path="noticias" element={<NewsFeedPage />} />
              <Route path="palpite-avulso" element={<PredictPage />} />
              <Route path="analise/:mandante/:visitante" element={<AnalysisPage />} />
              {/* Aliases legados EN */}
              <Route path="news" element={<Navigate to="/noticias" replace />} />
              <Route path="predict" element={<Navigate to="/palpite-avulso" replace />} />
              <Route path="validate" element={<HistoricalValidationPage />} />
              <Route path="brasileirao" element={<Navigate to="/" replace />} />
              <Route path="match/:home/:away" element={<MatchDetailPage />} />
              <Route path="bilhetes/:home/:away" element={<MatchTicketsPage />} />
              <Route path="album" element={<AlbumPage />} />
              <Route path="jogos" element={<SchedulePage />} />
              <Route path="amistosos" element={<FriendliesPage />} />
              <Route path="ao-vivo" element={<LivePage />} />
              <Route path="ao-vivo/:eventId" element={<LiveDashboardPage />} />
              <Route path="aovivo-v2/:eventId" element={<LiveOperationalPage />} />
              <Route path="ao-vivo/:eventId/painel" element={<Navigate to="/ao-vivo/:eventId" replace />} />
              <Route path="ao-vivo/basquete/multi" element={<BasketMultiLiveInPlayPage />} />
              <Route path="ao-vivo/basquete/:eventId" element={<BasketLiveInPlayPage />} />
              <Route path="ao-vivo/beisebol/:eventId" element={<BaseballLiveInPlayPage />} />
              <Route path="casino" element={<CasinoPage />} />
              <Route path="convocacoes" element={<SquadsPage />} />
              <Route path="grupos" element={<WcGroupsPage />} />
              <Route path="album/:teamSlug" element={<TeamAlbumPage />} />
              <Route path="carteira" element={<CarteiraPage />} />
              <Route path="performance" element={<BetPerformancePage />} />
              <Route path="query" element={<BetQueryPage />} />
              <Route path="simular" element={<BetSimulatorPage />} />
              <Route path="modelos" element={<ModelBenchmarkPage />} />
              <Route path="pre-jogo" element={<PreGameAnalysisPage />} />
              <Route path="central" element={<CopaCentralPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
        </NotificationsProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}
