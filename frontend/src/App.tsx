import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "@/presentation/components/ui/toast";
import { AppLayout } from "@/presentation/components/layout/AppLayout";
import { DashboardPage } from "@/presentation/pages/DashboardPage";
import { PredictPage } from "@/presentation/pages/PredictPage";
import { BrasileiraoPage } from "@/presentation/pages/BrasileiraoPage";
import { MatchDetailPage } from "@/presentation/pages/MatchDetailPage";
import { HistoricalValidationPage } from "@/presentation/pages/HistoricalValidationPage";
import { NewsFeedPage } from "@/presentation/pages/NewsFeedPage";
import { SquadsPage } from "@/presentation/pages/SquadsPage";
import { WcGroupsPage } from "@/presentation/pages/WcGroupsPage";
import { SchedulePage } from "@/presentation/pages/SchedulePage";
import { FriendliesPage } from "@/presentation/pages/FriendliesPage";
import { LivePage } from "@/presentation/pages/LivePage";
import { LiveInPlayPage } from "@/presentation/pages/LiveInPlayPage";
import { AlbumPage } from "@/presentation/pages/AlbumPage";
import { TeamAlbumPage } from "@/presentation/pages/TeamAlbumPage";

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
        <BrowserRouter>
          <Routes>
            <Route element={<AppLayout />}>
              <Route index element={<DashboardPage />} />
              <Route path="news" element={<NewsFeedPage />} />
              <Route path="predict" element={<PredictPage />} />
              <Route path="validate" element={<HistoricalValidationPage />} />
              <Route path="brasileirao" element={<BrasileiraoPage />} />
              <Route path="match/:home/:away" element={<MatchDetailPage />} />
              <Route path="album" element={<AlbumPage />} />
              <Route path="jogos" element={<SchedulePage />} />
              <Route path="amistosos" element={<FriendliesPage />} />
              <Route path="ao-vivo" element={<LivePage />} />
              <Route path="ao-vivo/:eventId" element={<LiveInPlayPage />} />
              <Route path="convocacoes" element={<SquadsPage />} />
              <Route path="grupos" element={<WcGroupsPage />} />
              <Route path="album/:teamSlug" element={<TeamAlbumPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}
