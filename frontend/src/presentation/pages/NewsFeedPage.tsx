import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  getHealthUseCase,
  getNewsFeedUseCase,
  syncNewsSourcesUseCase,
} from "@/application/container";
import { HeroPageHeader } from "@/presentation/components/layout/PageHeader";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { NewsArticleCard } from "@/presentation/components/news/NewsArticleCard";
import { NewsFeedSkeleton } from "@/presentation/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/presentation/components/ui/EmptyState";

const PAGE_SIZE = 12;
const SYNC_STALE_MS = 60_000;

export function NewsFeedPage() {
  const queryClient = useQueryClient();
  const [sourceFilter, setSourceFilter] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const deferredQuery = useDeferredValue(searchInput.trim());

  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: () => getHealthUseCase.execute(),
    staleTime: 30_000,
    retry: 3,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 5000),
  });

  const syncQuery = useQuery({
    queryKey: ["news-sync"],
    queryFn: () => syncNewsSourcesUseCase.execute(),
    staleTime: SYNC_STALE_MS,
    gcTime: 5 * 60_000,
    enabled: healthQuery.isSuccess,
    refetchOnMount: true,
    refetchOnWindowFocus: false,
    retry: 1,
  });

  useEffect(() => {
    if (syncQuery.isSuccess) {
      queryClient.invalidateQueries({ queryKey: ["health"] });
    }
  }, [syncQuery.isSuccess, syncQuery.dataUpdatedAt, queryClient]);

  const feedQuery = useInfiniteQuery({
    queryKey: ["news-feed", sourceFilter, deferredQuery, syncQuery.dataUpdatedAt],
    queryFn: ({ pageParam }) =>
      getNewsFeedUseCase.execute({
        limit: PAGE_SIZE,
        offset: pageParam,
        source: sourceFilter,
        query: deferredQuery || null,
        days: 30,
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage) => {
      const next = lastPage.offset + lastPage.limit;
      return next < lastPage.total ? next : undefined;
    },
    enabled: syncQuery.isSuccess,
    staleTime: 0,
  });

  const articles = useMemo(
    () => feedQuery.data?.pages.flatMap((p) => p.articles) ?? [],
    [feedQuery.data],
  );

  const sources = feedQuery.data?.pages[0]?.sources ?? [];
  const total = feedQuery.data?.pages[0]?.total ?? 0;
  const featured = articles[0];
  const gridArticles = articles.slice(1);
  const isSearching = deferredQuery.length > 0;

  const waitingApi = healthQuery.isPending || healthQuery.isFetching;
  const isSyncing = syncQuery.isPending || syncQuery.isFetching;
  const isLoadingFeed = syncQuery.isSuccess && feedQuery.isLoading;
  const showSkeleton = waitingApi || isSyncing || isLoadingFeed;

  if (healthQuery.isError) {
    return (
      <PageTransition>
        <ErrorState
          title="API indisponível"
          message="Inicie a API antes do frontend: ./scripts/dev-api.sh (porta 8000)"
          onRetry={() => healthQuery.refetch()}
        />
      </PageTransition>
    );
  }

  if (syncQuery.isError) {
    return (
      <PageTransition>
        <ErrorState
          title="Falha ao atualizar fontes"
          message={
            syncQuery.error instanceof Error
              ? syncQuery.error.message
              : "Não foi possível coletar notícias dos portais"
          }
          onRetry={() => syncQuery.refetch()}
        />
      </PageTransition>
    );
  }

  if (showSkeleton) {
    return (
      <PageTransition>
        <HeroPageHeader
          title="Feed de notícias"
          subtitle={
            waitingApi
              ? "Conectando à API..."
              : isSyncing
                ? "Coletando RSS dos portais e atualizando a base..."
                : "Montando o feed com as notícias mais recentes..."
          }
        />
        {syncQuery.data && isSyncing && (
          <p className="mb-4 text-xs text-slate-500">
            Última base: {syncQuery.data.articlesSilver} artigos • nova coleta em andamento
          </p>
        )}
        <NewsFeedSkeleton />
      </PageTransition>
    );
  }

  if (feedQuery.isError) {
    return (
      <PageTransition>
        <ErrorState
          message={
            feedQuery.error instanceof Error
              ? feedQuery.error.message
              : "Não foi possível carregar o feed"
          }
          onRetry={() => feedQuery.refetch()}
        />
      </PageTransition>
    );
  }

  const lastSync = syncQuery.data;

  return (
    <PageTransition className="space-y-8">
      <header className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-surface-card via-surface-elevated to-transparent p-6 sm:p-8">
        <div className="pointer-events-none absolute -right-8 -top-8 h-40 w-40 rounded-full bg-neon-purple/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-12 left-1/4 h-32 w-32 rounded-full bg-neon-green/15 blur-3xl" />

        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-xl">
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-neon-blue/20 bg-neon-blue/10 px-3 py-1 text-xs font-medium text-neon-blue">
              <span className="text-neon-green" aria-hidden>
                ✦
              </span>
              {lastSync
                ? `Atualizado agora • +${lastSync.collected} coletados`
                : "Datalake em tempo real"}
            </div>
            <h1 className="text-3xl font-bold gradient-text sm:text-4xl">Feed de notícias</h1>
            <p className="mt-2 text-sm leading-relaxed text-slate-400">
              Notícias coletadas de Globo Esporte, ESPN, UOL e outros portais — com times
              detectados e análise de sentimento para alimentar seus palpites.
            </p>
            <p className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
              <span>
                <strong className="text-slate-300">{total}</strong> artigos nos últimos 30 dias
              </span>
              {lastSync && (
                <>
                  <span className="text-slate-700">•</span>
                  <span>
                    Base silver:{" "}
                    <strong className="text-slate-300">{lastSync.articlesSilver}</strong>
                  </span>
                </>
              )}
            </p>
          </div>

          <div className="relative w-full max-w-md">
            <svg
              className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden
            >
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.3-4.3" />
            </svg>
            <input
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Buscar times, jogadores, temas..."
              className="input-field pl-10"
              aria-label="Buscar notícias"
            />
          </div>
        </div>
      </header>

      {sources.length > 0 && (
        <div className="flex flex-wrap gap-2">
          <SourceChip
            active={sourceFilter === null}
            label="Todas"
            count={sources.reduce((n, s) => n + s.count, 0)}
            onClick={() => setSourceFilter(null)}
          />
          {sources.map((s) => (
            <SourceChip
              key={s.id}
              active={sourceFilter === s.id}
              label={s.name}
              count={s.count}
              onClick={() => setSourceFilter(sourceFilter === s.id ? null : s.id)}
            />
          ))}
        </div>
      )}

      {articles.length === 0 ? (
        <EmptyState
          title={isSearching ? "Nenhum resultado" : "Feed vazio"}
          description={
            isSearching
              ? `Não encontramos notícias para "${deferredQuery}". Tente outro termo ou remova o filtro de fonte.`
              : "As fontes foram sincronizadas, mas ainda não há artigos na janela de 30 dias. Tente novamente em instantes."
          }
          action={
            <button
              type="button"
              className="btn-primary mt-2"
              onClick={() => syncQuery.refetch()}
            >
              Atualizar fontes novamente
            </button>
          }
        />
      ) : (
        <>
          {featured && !isSearching && sourceFilter === null && (
            <section>
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-500">
                Em destaque
              </h2>
              <NewsArticleCard article={featured} featured index={0} />
            </section>
          )}

          <section>
            <h2 className="mb-4 text-lg font-semibold text-white">
              {isSearching ? "Resultados" : "Últimas notícias"}
            </h2>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {(isSearching || sourceFilter !== null ? articles : gridArticles).map(
                (article, i) => (
                  <NewsArticleCard
                    key={article.id}
                    article={article}
                    index={i + 1}
                  />
                ),
              )}
            </div>
          </section>

          {feedQuery.hasNextPage && (
            <div className="flex justify-center pt-2">
              <button
                type="button"
                onClick={() => feedQuery.fetchNextPage()}
                disabled={feedQuery.isFetchingNextPage}
                className="btn-primary min-w-[200px]"
              >
                {feedQuery.isFetchingNextPage ? "Carregando..." : "Carregar mais"}
              </button>
            </div>
          )}
        </>
      )}
    </PageTransition>
  );
}

function SourceChip({
  label,
  count,
  active,
  onClick,
}: {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <motion.button
      type="button"
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      className={`rounded-full border px-4 py-1.5 text-xs font-medium transition-all ${
        active
          ? "border-neon-green/40 bg-neon-green/10 text-neon-green shadow-neon"
          : "border-white/10 bg-white/5 text-slate-400 hover:border-white/20 hover:text-white"
      }`}
    >
      {label}
      <span className={`ml-1.5 ${active ? "text-neon-green/80" : "text-slate-500"}`}>
        {count}
      </span>
    </motion.button>
  );
}
